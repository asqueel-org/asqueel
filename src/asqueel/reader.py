# Copyright 2025 Softwell S.r.l. - SPDX-License-Identifier: Apache-2.0
"""Reverse projection: normalized migration JSON back into a model tree.

The inverse of :class:`~asqueel.migration.SqlMigrationRenderer`,
and the analogue of :func:`asqueel_migration.xml_producer.struct_to_xml`
for the recipe form: it de-normalizes ``structure-1.0`` into the grammar
of :class:`~asqueel.builder.SqlBuilder`, so a database that only
exists as introspected JSON becomes a source tree — and, through
:class:`~asqueel.emitter.SqlPythonEmitter`, a Python recipe.

The law it answers to is migration-equivalent round-tripping::

    render(SqlModelReader(structure).to_builder()) ~= structure

where equivalence ignores only readable foreign-key constraint names, matching
the default ``SqlMigrator(ignore_constraint_name=True)`` behavior. No physical
schema semantics are invented or dropped. Two consequences shape the module:

- **structural hashes are not recipe names, where a name is optional**.
  A relation comes back anonymous, so a readable database FK name normalizes to
  its structural hash on re-render; a hash-named multi-column UNIQUE constraint
  comes back as ``unique=True`` on a composite. An index is the exception: its
  name is the grammar's collection key AND the physical ``index_name``
  echoed into the JSON, so it travels verbatim — dropping it would rename
  the index in the database.
- **the sugar is not re-derived**. ``indexed=True`` and the automatic
  index of a foreign key (D3) are authoring conveniences of the forward
  path; here every index in the JSON is written out as a real ``index``
  element, and a foreign key whose supporting index is absent from the
  JSON carries ``indexed=False``.

A multi-column foreign key returns as a ``compositeColumn`` with a readable
name derived from its ordered members (D4), on both sides of the relation
when the target columns are not the target's pkey. Collisions get a stable
numeric suffix; the ordered member tuple, not that display name, identifies
the composite internally. Anything the ``structure-1.0`` contract does not
declare — an unknown attribute key, an event trigger — is a loud error naming
its JSON path: unsupported schema features are never dropped silently.
"""

from __future__ import annotations

from typing import cast

from asqueel_migration.structures import COL_JSON_KEYS

from .builder import SqlBuilder
from .common import INDEX_OPTIONS as _INDEX_OPTIONS
from .common import split_names as _names

#: Table attribute keys the grammar can express.
_TABLE_KEYS = frozenset({"pkeys", "comment"})

#: Relation attribute keys the grammar can express.
_RELATION_KEYS = frozenset({
    "columns", "constraint_name", "constraint_type", "related_schema",
    "related_table", "related_columns", "on_delete", "on_update",
    "deferrable", "initially_deferred",
})

#: Constraint attribute keys the grammar can express.
_CONSTRAINT_KEYS = frozenset({
    "columns", "constraint_name", "constraint_type", "check_clause",
})

#: Index attribute keys the grammar can express.
_INDEX_KEYS = frozenset({
    "columns", "index_name", "unique", "method", "where", "tablespace",
    "with_options",
})


class SqlModelReadError(ValueError):
    """The JSON carries something the canonical grammar cannot express.

    Args:
        path: the JSON path of the offending entity.
        message: what is wrong with it.
    """

    def __init__(self, path: str, message: str) -> None:
        self.path = path
        super().__init__(f"{path}: {message}")


class _ImportedModel(SqlBuilder):
    """Anonymous recipe whose document is built by the reader."""

    def __init__(self, populate) -> None:
        self._populate = populate
        super().__init__()

    def main(self, root) -> None:
        self._populate(root)


class SqlModelReader:
    """Build a SQL model tree out of a normalized ``structure-1.0`` dict.

    Args:
        normalized: the migration JSON, ``{'root': {...}}``.
    """

    def __init__(self, normalized: dict) -> None:
        self.normalized = normalized

    @staticmethod
    def _mount(path, parent, tag, **kwargs):
        try:
            return getattr(parent, tag)(**kwargs)
        except (TypeError, ValueError) as error:
            raise SqlModelReadError(path, str(error)) from error

    def to_builder(self) -> SqlBuilder:
        """De-normalize the structure into a created, validated model.

        Returns:
            A created :class:`~asqueel.builder.SqlBuilder` whose
            source tree projects back to the structure it was read from.

        Raises:
            SqlModelReadError: the JSON declares something outside the
                canonical grammar.
            SqlModelValidationError: the resulting model is inconsistent.
        """
        model = _ImportedModel(self._build)
        model.create()
        model.validate_model()
        return model

    # -- document --------------------------------------------------------

    def _build(self, root_node) -> None:
        root = self.normalized["root"]
        if root.get("event_triggers"):
            raise SqlModelReadError(
                "root.event_triggers",
                "event triggers are outside the canonical grammar",
            )
        self._plan_composites(root)
        db = self._mount(
            "root.entity_name", root_node, "db", name=root.get("entity_name"),
        )
        tables = {}
        schemas_node = self._mount("root.schemas", db, "schemas")
        for schema_name, schema in root.get("schemas", {}).items():
            schema_path = f"root.schemas.{schema_name}"
            schema_node = self._mount(
                schema_path, schemas_node, "schema", name=schema_name,
            )
            tables_node = self._mount(
                f"{schema_path}.tables", schema_node, "tables",
            )
            for table_name, table in schema.get("tables", {}).items():
                tables[(schema_name, table_name)] = self._add_table(
                    tables_node, schema_name, table_name, table,
                )
        extensions = root.get("extensions", {})
        extensions_node = (
            self._mount("root.extensions", db, "extensions") if extensions else None
        )
        for extension_name, extension in extensions.items():
            self._check_keys(
                f"root.extensions.{extension_name}",
                extension.get("attributes") or {}, frozenset(),
            )
            self._mount(
                f"root.extensions.{extension_name}", extensions_node, "extension",
                name=extension_name,
            )
        for table in tables.values():
            self._fill_relations(table)
            self._fill_constraints(table)
            self._fill_indexes(table)

    def _add_table(self, tables_node, schema_name, table_name,
                   table) -> dict:
        path = self._table_path(schema_name, table_name)
        attributes = table.get("attributes") or {}
        self._check_keys(path, attributes, _TABLE_KEYS)
        kwargs = {"name": table_name}
        if attributes.get("pkeys"):
            kwargs["pkey"] = attributes["pkeys"]
        if attributes.get("comment"):
            kwargs["comment"] = attributes["comment"]
        node = self._mount(path, tables_node, "table", **kwargs)
        pkey = _names(attributes.get("pkeys"))
        columns = {}
        columns_node = self._mount(f"{path}.columns", node, "columns")
        for column_name, column in table.get("columns", {}).items():
            columns[column_name] = self._add_column(
                columns_node, path, column_name, column, pkey,
            )
        composites = {}
        planned_composites = self._composites[(schema_name, table_name)]
        composites_node = (
            self._mount(f"{path}.composites", node, "composites")
            if planned_composites else None
        )
        for key, members in planned_composites.items():
            composites[key] = self._mount(
                f"{path}.composites.{members['name']}",
                composites_node, "compositeColumn", name=members["name"],
                columns=",".join(members["columns"]),
                **({"unique": True} if members["unique"] else {}),
            )
        return {"node": node, "path": path, "json": table, "pkey": pkey,
                "columns": columns, "composites": composites,
                "constraints": None, "indexes": None}

    def _add_column(self, table_node, path, column_name, column,
                    pkey):
        attributes = dict(column.get("attributes") or {})
        self._check_keys(
            f"{path}.columns.{column_name}", attributes, COL_JSON_KEYS,
        )
        if column_name in pkey:
            attributes.pop("notnull", None)
        return self._mount(
            f"{path}.columns.{column_name}", table_node, "column",
            name=column_name, **attributes,
        )

    # -- composites ------------------------------------------------------

    def _plan_composites(self, root) -> None:
        """Collect every composite the relations and constraints need.

        Both sides of a multi-column foreign key need one, and the target
        side belongs to a table that may be built before the relation is
        read — so the whole plan is computed before the first element is
        mounted.
        """
        self._composites: dict[tuple[str, str], dict] = {}
        self._used_composite_names: dict[tuple[str, str], set[str]] = {}
        self._pkeys: dict[tuple[str, str], list[str]] = {}
        for schema_name, schema in root.get("schemas", {}).items():
            for table_name, table in schema.get("tables", {}).items():
                key = (schema_name, table_name)
                self._composites[key] = {}
                self._used_composite_names[key] = set(
                    table.get("columns", {}),
                )
                self._pkeys[key] = _names(
                    (table.get("attributes") or {}).get("pkeys"),
                )
        for schema_name, schema in root.get("schemas", {}).items():
            for table_name, table in schema.get("tables", {}).items():
                key = (schema_name, table_name)
                table_path = self._table_path(schema_name, table_name)
                for name, relation in table.get("relations", {}).items():
                    self._plan_relation_composites(
                        key, relation, f"{table_path}.relations.{name}",
                    )
                for name, constraint in table.get("constraints", {}).items():
                    self._plan_constraint_composite(key, name, constraint)

    def _plan_relation_composites(self, key, relation, path) -> None:
        attributes = relation["attributes"]
        columns = _names(attributes.get("columns"))
        if len(columns) > 1:
            self._need_composite(key, columns, path=path)
        target = (attributes.get("related_schema"),
                  attributes.get("related_table"))
        if target not in self._composites:
            raise SqlModelReadError(
                path,
                f"related target table '{'.'.join(str(part) for part in target)}' "
                "does not exist in the normalized structure",
            )
        related = _names(attributes.get("related_columns"))
        if len(related) > 1 and related != self._pkeys.get(target):
            self._need_composite(target, related, path=path)

    def _plan_constraint_composite(self, key, name,
                                   constraint) -> None:
        attributes = constraint["attributes"]
        if attributes.get("constraint_type") == "CHECK":
            return
        columns = _names(attributes.get("columns"))
        if len(columns) < 2:
            return
        if attributes.get("constraint_name") != name:
            return
        self._need_composite(key, columns, unique=True)

    def _need_composite(self, key, columns, unique=False, path=None) -> str:
        """Register the deterministic composite over ``columns`` (D4)."""
        if key not in self._composites:
            raise SqlModelReadError(
                path or "root.schemas",
                f"table '{'.'.join(str(part) for part in key)}' does not exist",
            )
        column_key = tuple(columns)
        planned = self._composites[key].get(column_key)
        if planned is None:
            base = "_".join(columns)
            name = base
            suffix = 2
            while name in self._used_composite_names[key]:
                name = f"{base}_{suffix}"
                suffix += 1
            self._used_composite_names[key].add(name)
            planned = {
                "name": name, "columns": list(columns), "unique": False,
            }
            self._composites[key][column_key] = planned
        planned["unique"] = planned["unique"] or unique
        return cast(str, planned["name"])

    # -- second pass -----------------------------------------------------

    def _table_collection(self, table, tag):
        node = table[tag]
        if node is None:
            node = self._mount(f"{table['path']}.{tag}", table["node"], tag)
            table[tag] = node
        return node

    def _fill_relations(self, table) -> None:
        indexed = {
            tuple(_names(index["attributes"].get("columns")))
            for index in table["json"].get("indexes", {}).values()
        }
        for name, relation in table["json"].get("relations", {}).items():
            path = f"{table['path']}.relations.{name}"
            attributes = relation["attributes"]
            self._check_keys(
                path, attributes, _RELATION_KEYS,
            )
            columns = _names(attributes.get("columns"))
            owner = (table["columns"][columns[0]] if len(columns) == 1
                     else table["composites"][tuple(columns)])
            kwargs = {"to": self._target(attributes), "foreign_key": True}
            for action in ("on_delete", "on_update"):
                if attributes.get(action):
                    kwargs[action] = attributes[action]
            if attributes.get("deferrable"):
                kwargs["deferrable"] = True
            if attributes.get("initially_deferred"):
                kwargs["initially_deferred"] = True
            if tuple(columns) not in indexed:
                kwargs["indexed"] = False
            self._mount(path, owner, "relation", **kwargs)

    def _target(self, attributes) -> str:
        """``relation.to`` for a foreign key, in its shortest exact form."""
        schema_name = attributes.get("related_schema")
        table_name = attributes.get("related_table")
        columns = _names(attributes.get("related_columns"))
        if len(columns) == 1:
            return f"{schema_name}.{table_name}.{columns[0]}"
        if columns == self._pkeys.get((schema_name, table_name)):
            return f"{schema_name}.{table_name}"
        planned = self._composites[(schema_name, table_name)][tuple(columns)]
        return f"{schema_name}.{table_name}.{planned['name']}"

    def _fill_constraints(self, table) -> None:
        for name, constraint in table["json"].get("constraints", {}).items():
            attributes = constraint["attributes"]
            path = f"{table['path']}.constraints.{name}"
            self._check_keys(path, attributes, _CONSTRAINT_KEYS)
            constraint_name = attributes.get("constraint_name")
            if attributes.get("constraint_type") == "CHECK":
                self._mount(
                    path, self._table_collection(table, "constraints"),
                    "constraint", name=constraint_name,
                    constraint_type="CHECK",
                    check_clause=attributes.get("check_clause"),
                )
            else:
                columns = _names(attributes.get("columns"))
                if len(columns) > 1 and constraint_name == name:
                    continue
                self._mount(
                    path, self._table_collection(table, "constraints"),
                    "constraint", name=constraint_name,
                    constraint_type="UNIQUE", columns=",".join(columns),
                )

    def _fill_indexes(self, table) -> None:
        for name, index in table["json"].get("indexes", {}).items():
            attributes = index["attributes"]
            self._check_keys(
                f"{table['path']}.indexes.{name}", attributes, _INDEX_KEYS,
            )
            kwargs = {
                "columns": attributes.get("columns"),
                "name": attributes.get("index_name") or name,
            }
            for option in _INDEX_OPTIONS:
                if attributes.get(option):
                    kwargs[option] = attributes[option]
            self._mount(
                f"{table['path']}.indexes.{name}",
                self._table_collection(table, "indexes"), "index", **kwargs,
            )

    # -- strictness ------------------------------------------------------

    @staticmethod
    def _table_path(schema_name, table_name) -> str:
        return f"root.schemas.{schema_name}.tables.{table_name}"

    @staticmethod
    def _check_keys(path, attributes, declared) -> None:
        """Refuse any attribute key outside the ``structure-1.0`` set."""
        for key in attributes:
            if key not in declared:
                raise SqlModelReadError(
                    f"{path}.attributes.{key}",
                    "attribute is not part of the structure-1.0 contract "
                    f"({', '.join(sorted(declared))})",
                )


__all__ = ["SqlModelReadError", "SqlModelReader"]
