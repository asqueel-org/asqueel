# Copyright 2025 Softwell S.r.l. - SPDX-License-Identifier: Apache-2.0
"""Projection of a SQL model tree into the normalized migration JSON.

The twin of :class:`asqueel_migration.JsonStructureProducer`: that one
reads the ergonomic human JSON, this one reads a built
:class:`~asqueel.builder.SqlBuilder` tree, and the two converge
on the same ``structure-1.0`` dict for the same physical model. The
normalization rules are not reimplemented here — every entity is built
by the ``asqueel_migration.structures`` factories, which own the
structural hashes and the attribute cleaning.

Only the physical plane travels. Virtual columns project nothing, a
relation projects only with ``foreign_key=True``, and the semantic
attributes (``name_*``, ``group``, ``one_name``, ``x_*``, …) stop at this
boundary by construction: each entity is filled from an enumerated key
set, never from the node's attribute dict.

Two grammar conveniences become real entities here:

- ``indexed=True`` on a column, and every foreign-key column, materialize
  an index item (``structure-1.0`` has no ``indexed`` column attribute);
  an index over exactly the pkey columns is skipped, the primary key
  already indexes them.
- ``unique=True`` on a ``compositeColumn`` becomes a multi-column UNIQUE
  constraint; single-column uniqueness stays the column attribute.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import cast

from asqueel_migration import PgDatabase, SqliteDatabase, SqlMigrator, StructureValidator
from asqueel_migration.structures import (
    COL_JSON_KEYS,
    new_column_item,
    new_constraint_item,
    new_extension_item,
    new_index_item,
    new_relation_item,
    new_schema_item,
    new_structure_root,
    new_table_item,
)

from .catalog import SqlModelCatalog
from .configuration import connection_settings
from .errors import MigrationError
from .common import INDEX_OPTIONS as _INDEX_OPTIONS
from .common import split_names as _names
from .projection import to_physical_builder
from .validators import SqlModelValidator

#: Relation attributes that reach the JSON, mapped to their contract key.
_RELATION_ACTIONS = ("on_delete", "on_update")


class SqlMigrationRenderer:
    """Render a built SQL model as the normalized ``structure-1.0`` JSON.

    Args:
        builder: a created :class:`~asqueel.builder.SqlBuilder`.
    """

    def __init__(self, builder) -> None:
        self.builder = builder

    def render(self) -> dict:
        """Project the model, a fresh structure each call.

        The model is domain-validated first and the result is passed
        through :class:`asqueel_migration.StructureValidator` before it
        is handed out, so nothing leaves this method that the migrator
        would refuse.

        Returns:
            The normalized structure, ``{'root': {...}}``.

        Raises:
            SqlModelValidationError: the model itself is inconsistent.
            SqlValidationError: the projection breaks the contract.
        """
        SqlModelValidator().validate(self.builder)
        self._catalog = SqlModelCatalog(self.builder)
        self._db_name = self._catalog.db_name
        self._schemas = self._catalog.schemas
        self._extensions = self._catalog.extensions
        self._tables = self._catalog.tables
        structure = new_structure_root(self._db_name)
        root = structure["root"]
        for schema_name in self._schemas:
            root["schemas"][schema_name] = new_schema_item(schema_name)
        for (schema_name, table_name), table in self._tables.items():
            root["schemas"][schema_name]["tables"][table_name] = self._table_item(
                schema_name, table_name, table,
            )
        for extension_name in self._extensions:
            root["extensions"][extension_name] = new_extension_item(extension_name)
        return cast(dict, StructureValidator().validate(structure))

    # -- projection ------------------------------------------------------

    def _table_item(self, schema_name, table_name, table) -> dict:
        item = new_table_item(schema_name, table_name)
        pkey = table["node"].get_attr("pkey")
        pkey_columns = _names(pkey)
        if pkey_columns:
            item["attributes"]["pkeys"] = ",".join(pkey_columns)
        comment = table["node"].get_attr("comment")
        if comment:
            item["attributes"]["comment"] = comment
        for column_name, node in table["columns"].items():
            item["columns"][column_name] = self._column_item(
                schema_name, table_name, column_name, node, pkey_columns,
            )
        auto_index_columns = self._fill_relations(schema_name, table_name, table, item)
        self._fill_constraints(schema_name, table_name, table, item)
        self._fill_indexes(schema_name, table_name, table, item)
        for column_name, node in table["columns"].items():
            if node.get_attr("indexed"):
                auto_index_columns.append([column_name])
        self._fill_auto_indexes(
            schema_name, table_name, item, auto_index_columns, pkey_columns,
        )
        return cast(dict, item)

    def _column_item(self, schema_name, table_name, column_name, node,
                     pkey_columns) -> dict:
        attributes = {
            key: node.get_attr(key) for key in COL_JSON_KEYS
            if node.get_attr(key) is not None
        }
        if "dtype" not in attributes:
            attributes["dtype"] = "A" if attributes.get("size") else "T"
        if column_name in pkey_columns:
            attributes["notnull"] = "_auto_"
            if len(pkey_columns) == 1:
                attributes.pop("unique", None)
        return cast(
            dict,
            new_column_item(
                schema_name, table_name, column_name, attributes=attributes,
            ),
        )

    def _fill_relations(self, schema_name, table_name, table,
                        item) -> list[list[str]]:
        """Project the foreign keys; return the columns they must index."""
        indexed: list[list[str]] = []
        for _path, owner_name, node in table["relations"]:
            if not node.get_attr("foreign_key"):
                continue
            owner = table["family"].get(owner_name)
            if owner is None or not owner._get_meta("projects_relation"):
                continue
            columns = (_names(owner.get_attr("columns"))
                       if owner.node_tag == "compositeColumn" else [owner_name])
            target_schema, target_table, target_columns = self._resolve_target(node)
            attributes: dict[str, object] = {
                "related_schema": target_schema,
                "related_table": target_table,
                "related_columns": target_columns,
                "constraint_type": "FOREIGN KEY",
            }
            for key in _RELATION_ACTIONS:
                if node.get_attr(key):
                    attributes[key] = node.get_attr(key)
            deferred = node.get_attr("deferred")
            if node.get_attr("deferrable") or deferred:
                attributes["deferrable"] = True
            if node.get_attr("initially_deferred") or deferred:
                attributes["initially_deferred"] = True
            relation = new_relation_item(
                schema_name, table_name, columns, attributes=attributes,
            )
            item["relations"][relation["entity_name"]] = relation
            if node.get_attr("indexed", True):
                indexed.append(columns)
        return indexed

    def _resolve_target(self, node) -> tuple[str, str, list[str]]:
        """``relation.to`` as ``(schema, table, columns)``.

        A two-part target means the target's pkey columns; a three-part
        one names a single column, or the compositeColumn packing the
        target key. The domain validator has already proved they resolve.
        """
        parts = [part.strip() for part in str(node.get_attr("to")).split(".")]
        target = self._tables[(parts[0], parts[1])]
        if len(parts) == 3:
            composite = target["composites"].get(parts[2])
            if composite is None:
                return parts[0], parts[1], [parts[2]]
            return parts[0], parts[1], _names(composite.get_attr("columns"))
        return parts[0], parts[1], _names(target["node"].get_attr("pkey"))

    def _fill_constraints(self, schema_name, table_name, table,
                          item) -> None:
        for _path, node in table["constraints"]:
            if node.get_attr("constraint_type") == "CHECK":
                constraint = new_constraint_item(
                    schema_name, table_name, None, "CHECK",
                    constraint_name=node.get_attr("name"),
                    check_clause=node.get_attr("check_clause"),
                )
            else:
                constraint = new_constraint_item(
                    schema_name, table_name, _names(node.get_attr("columns")),
                    "UNIQUE", constraint_name=node.get_attr("name"),
                )
            item["constraints"][constraint["entity_name"]] = constraint
        for node in table["composites"].values():
            if not node.get_attr("unique"):
                continue
            constraint = new_constraint_item(
                schema_name, table_name, _names(node.get_attr("columns")), "UNIQUE",
            )
            item["constraints"].setdefault(constraint["entity_name"], constraint)

    def _fill_indexes(self, schema_name, table_name, table,
                      item) -> None:
        for _path, node in table["indexes"]:
            columns = node.get_attr("columns")
            if not isinstance(columns, dict):
                columns = dict.fromkeys(_names(columns))
            attributes = {"columns": columns}
            for key in _INDEX_OPTIONS:
                if node.get_attr(key):
                    attributes[key] = node.get_attr(key)
            index = new_index_item(
                schema_name, table_name, list(columns),
                attributes=attributes, index_name=node.get_attr("name"),
            )
            item["indexes"][index["entity_name"]] = index

    def _fill_auto_indexes(self, schema_name, table_name, item, column_sets,
                           pkey_columns) -> None:
        """Materialize the indexes ``indexed=True`` and foreign keys imply.

        An explicit ``index`` over the same columns wins — it carries a
        readable name and options the sugar cannot express — and an index
        over exactly the pkey columns is dropped: the primary key is
        already one.
        """
        for columns in column_sets:
            if columns == pkey_columns:
                continue
            index = new_index_item(
                schema_name, table_name, columns,
                attributes={"columns": dict.fromkeys(columns)},
            )
            item["indexes"].setdefault(index["entity_name"], index)


__all__ = ["SqlMigrationRenderer"]


# ---------------------------------------------------------------------------
# Plan and apply a migration against the live database
# ---------------------------------------------------------------------------

#: Prefix asqueel-migration gives a change the backend cannot apply
#: (``CommandBuilder.unsupported``). Matched as text until asqueel-migration
#: reports skipped changes as data; the dependency upper bound keeps it stable.
_SKIPPED_PREFIX = "unsupported '"


@dataclass(frozen=True)
class MigrationPlan:
    """The DDL that brings a live database to its model, computed against that database.

    ``skipped`` lists the changes the backend cannot apply (for example a
    column type change on SQLite); ``warnings`` includes them.
    """

    commands: str
    warnings: tuple[str, ...]
    skipped: tuple[str, ...]

    @property
    def empty(self) -> bool:
        return not self.commands.strip()


def migration_plan(db, *, allow_removals=False) -> MigrationPlan:
    """Compare ``db.model`` with the live database and return the plan; change nothing."""
    migrator = _prepared_migrator(db, allow_removals=allow_removals)
    try:
        return _plan_of(migrator)
    finally:
        migrator.db.closeConnection()


def migrate(db, *, allow_removals=False) -> MigrationPlan:
    """Apply the plan and return it.

    Refuses before any DDL when the plan has skipped changes. After applying,
    compares again and raises :class:`MigrationError` if differences remain.
    """
    migrator = _prepared_migrator(db, allow_removals=allow_removals)
    try:
        plan = _plan_of(migrator)
        if plan.skipped:
            raise MigrationError('The backend cannot apply these changes: ' + '; '.join(plan.skipped))
        if not plan.empty:
            migrator.applyChanges()
    finally:
        migrator.db.closeConnection()
    remaining = migration_plan(db, allow_removals=allow_removals)
    if not remaining.empty:
        raise MigrationError('Migration applied, but differences remain:\n' + remaining.commands)
    return plan


def _plan_of(migrator) -> MigrationPlan:
    warnings = tuple(migrator.warnings)
    skipped = tuple(warning for warning in warnings if warning.startswith(_SKIPPED_PREFIX))
    return MigrationPlan(migrator.getChanges(), warnings, skipped)


def _prepared_migrator(db, *, allow_removals):
    """Project the model and prepare the backend migrator, its commands computed."""
    implementation, conninfo, kwargs = connection_settings(db.config)
    if implementation == 'sqlite':
        params = dict(kwargs or {})
        params.setdefault('dbname', conninfo)
        if params['dbname'] == ':memory:':
            raise MigrationError('Migrations require persistent SQLite files')
    elif implementation == 'postgresql':
        # psycopg is the PostgreSQL extra: a SQLite-only install does not have it.
        from psycopg.conninfo import conninfo_to_dict
        params = conninfo_to_dict(conninfo or '', **(kwargs or {}))
    else:
        raise MigrationError(f'Unsupported migration backend: {implementation}')
    if not params.get('dbname'):
        raise MigrationError('Declare connection.name (or an explicit dbname in the legacy connection settings)')
    desired = SqlMigrationRenderer(to_physical_builder(db.model)).render()
    # The physical destination is owned by connection settings, not the recipe root label.
    desired['root']['entity_name'] = params['dbname']
    schemas = sorted(desired['root']['schemas'])
    if not schemas:
        raise MigrationError('Declare at least one nonempty managed schema before migrating')
    database_class = SqliteDatabase if implementation == 'sqlite' else PgDatabase
    database = database_class(params, application_schemas=schemas)
    migrator = SqlMigrator(database, ignore_constraint_name=True, removeDisabled=not allow_removals)
    migrator.ormStructure = desired
    try:
        migrator.prepareMigrationCommands()
    except BaseException:
        database.closeConnection()
        raise
    return migrator
