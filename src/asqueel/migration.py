# Copyright 2025 Softwell S.r.l. - SPDX-License-Identifier: Apache-2.0
"""Rendering of the SQL source into the normalized migration JSON.

The twin of :class:`asqueel_migration.JsonStructureProducer`: that one
reads the ergonomic human JSON, this one renders the composed recipe of a
:class:`~asqueel.builder.SqlBuilder`, prepared as for the live model, and
the two converge on the same ``structure-1.0`` dict for the same physical
model. The normalization rules are not reimplemented here — every entity is
built by the ``asqueel_migration.structures`` factories, which own the
structural hashes and the attribute cleaning.

Only the physical plane travels, under the physical names (``sqlschema``,
``sqlprefix``, ``sqlname``). Virtual columns render nothing, a relation
renders a foreign key only with ``foreign_key=True``, and the semantic
attributes (``name_*``, ``group``, ``one_name``, ``x_*``, …) stop at this
boundary by construction: each entity is filled from an enumerated key
set, never from the node's attribute dict.

Two grammar conveniences become real entities here:

- ``indexed=True`` or ``indexed={...}`` on a column, and every relation
  column, materialize an index item (``structure-1.0`` has no ``indexed``
  column attribute), as legacy ``fill_json_relations_and_indexes``; a
  relation to target columns other than the target pkey also indexes them.
  An index over exactly the pkey columns is skipped, the primary key
  already indexes them.
- ``unique=True`` on a ``compositeColumn`` becomes a multi-column UNIQUE
  constraint; single-column uniqueness stays the column attribute.
"""

from __future__ import annotations

import json

from asqueel_migration import StructureValidator, apply_migration, database_for, plan_migration
from asqueel_migration.exceptions import SqlMigrationError
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
from genro_builders.renderer import RendererBase

from .runtime import connection_settings
from .contracts import UnsupportedFeatureError
from .errors import MigrationError
from .common import INDEX_OPTIONS as _INDEX_OPTIONS
from .common import default_index_name, indexed_attributes, package_sqlschema, table_sqlname
from .common import SQL_ACTIONS, SQL_COLUMN_KEYS, sql_column_attributes
from .common import split_names as _names
from .object_tree_renderer import prepare_render_source

#: Relation attributes that reach the JSON, mapped to their contract key.
_RELATION_ACTIONS = {"onDelete_sql": "on_delete", "onUpdate_sql": "on_update"}

#: Containers whose children render in their place.
_COLLECTIONS = frozenset({"packages", "extensions", "tables", "columns",
                          "composites", "constraints", "indexes"})


def _ancestor(node, tag):
    current = node.parent_node
    while current.node_tag != tag:
        current = current.parent_node
    return current


def _package_storage(dtype, attributes):
    """Legacy logical types -> storage, as legacy ``convert_colattr``; ``size`` may be rewritten."""
    dtype = {'X': 'T', 'Z': 'T', 'P': 'T'}.get(dtype, dtype)
    size = attributes.get('size')
    if size:
        if ':' in size:
            attributes['size'] = '0:' + size.split(':')[1]
            dtype = 'A'
        elif ',' not in size:
            if dtype in ('A', 'T'):
                dtype = 'C'
            elif dtype == 'N':
                attributes['size'] = size + ',0'
    elif dtype in ('A', 'C'):
        dtype = 'T'
    return dtype


class SqlMigrationRenderer(RendererBase):
    """Render the composed recipe as the normalized ``structure-1.0`` JSON.

    Reached as ``recipe.render(mode='migration', foreignKeys=True)``. The
    source is prepared by the same function as the live model, so options
    and package rules act here too. With no target the structure is returned
    as a dict; a path, a writable or a callable receives it as JSON text.
    The result passes :class:`asqueel_migration.StructureValidator` before it
    is handed out, so nothing leaves the renderer that the migrator would
    refuse.
    """

    mode = "migration"
    render_type = "object"

    def preprocess(self, source):
        return prepare_render_source(self)

    def rendered_item(self, node, item, runtime_attrs, *, tag, **opts):
        # A node without children renders its raw value, not a list.
        item = item if isinstance(item, list) else []
        if tag in _COLLECTIONS:
            return item
        attributes = runtime_attrs
        name = attributes.get("name", node.label)
        if tag == "db":
            return {"tag": tag, "name": name, "children": item}
        if tag == "extension":
            return {"tag": tag, "name": name}
        if tag == "package":
            implementation = _ancestor(node, "db").attr.get("implementation")
            return {"tag": "package", "name": name, "tables": item,
                    "sqlschema": package_sqlschema(attributes, implementation)}
        if tag == "table":
            return self._table(node, name, attributes, item)
        if tag == "relation":
            return {"tag": tag, "attributes": attributes}
        if tag == "compositeColumn" or node._get_meta("projects_column"):
            return {"tag": "compositeColumn" if tag == "compositeColumn" else "column", "name": name,
                    "attributes": attributes, "relations": [child for child in item
                                                            if child["tag"] == "relation"],
                    "projects_relation": bool(node._get_meta("projects_relation"))}
        if tag in ("index", "constraint"):
            return {"tag": tag, "attributes": attributes}
        return None

    def _table(self, node, table_name, attributes, children) -> dict:
        package = _ancestor(node, "tables").parent_node
        package_name = package.attr.get("name", package.label)
        implementation = _ancestor(node, "db").attr.get("implementation")
        schema_name = attributes.get("sqlschema") or package_sqlschema(package.attr, implementation)
        sqlname = table_sqlname(package_name, package.attr, table_name, attributes)
        columns = [child for child in children if child["tag"] == "column"]
        composites = {child["name"]: child for child in children if child["tag"] == "compositeColumn"}
        names = {column["name"]: column["attributes"].get("sqlname") or column["name"] for column in columns}
        remapped = any(source != physical for source, physical in names.items())

        def physical(value):
            return [names[field] for part in _names(value)
                    for field in (_names(composites[part]["attributes"]["columns"]) if part in composites else [part])]

        item = new_table_item(schema_name, sqlname)
        pkey_columns = physical(attributes.get("pkey"))
        if pkey_columns:
            item["attributes"]["pkeys"] = ",".join(pkey_columns)
        if attributes.get("comment"):
            item["attributes"]["comment"] = attributes["comment"]
        for column in columns:
            item["columns"][names[column["name"]]] = self._column_item(
                schema_name, sqlname, names[column["name"]], column["attributes"], pkey_columns,
                implementation=implementation)
        relations = []
        auto_indexes: dict[tuple[str, ...], dict | None] = {}
        for owner in (*columns, *composites.values()):
            if not owner["projects_relation"]:
                continue
            owner_columns = (physical(owner["attributes"]["columns"]) if owner["tag"] == "compositeColumn"
                             else [names[owner["name"]]])
            for relation in owner["relations"]:
                if not relation["attributes"].get("foreign_key"):
                    continue
                if relation["attributes"].get("indexed", True):
                    auto_indexes.setdefault(tuple(owner_columns))
                relations.append((owner_columns, relation["attributes"]))
        for child in children:
            if child["tag"] != "constraint":
                continue
            constraint_attributes = child["attributes"]
            if constraint_attributes.get("constraint_type") == "CHECK":
                if remapped:
                    raise UnsupportedFeatureError(f"{package_name}.{table_name}: CHECK with remapped columns")
                constraint = new_constraint_item(
                    schema_name, sqlname, None, "CHECK", constraint_name=constraint_attributes.get("name"),
                    check_clause=constraint_attributes.get("check_clause"))
            else:
                constraint = new_constraint_item(
                    schema_name, sqlname, physical(constraint_attributes.get("columns")), "UNIQUE",
                    constraint_name=constraint_attributes.get("name"))
            item["constraints"][constraint["entity_name"]] = constraint
        for composite in composites.values():
            if not composite["attributes"].get("unique"):
                continue
            constraint = new_constraint_item(schema_name, sqlname,
                                             physical(composite["attributes"]["columns"]), "UNIQUE")
            item["constraints"].setdefault(constraint["entity_name"], constraint)
        for child in children:
            if child["tag"] != "index":
                continue
            index_attributes = child["attributes"]
            declared = index_attributes.get("columns")
            index_columns = ({names[field]: order for field, order in declared.items()}
                             if isinstance(declared, dict) else dict.fromkeys(physical(declared)))
            if index_attributes.get("where") and remapped:
                raise UnsupportedFeatureError(f"{package_name}.{table_name}: partial index with remapped columns")
            attributes_item = {"columns": index_columns}
            for key in _INDEX_OPTIONS:
                if index_attributes.get(key):
                    attributes_item[key] = index_attributes[key]
            source_columns = list(declared) if isinstance(declared, dict) else _names(declared)
            index = new_index_item(
                schema_name, sqlname, list(index_columns), attributes=attributes_item,
                index_name=(None if index_attributes.get("name") == default_index_name(table_name, source_columns)
                            else index_attributes.get("name")))
            item["indexes"][index["entity_name"]] = index
        for column in columns:
            column_name = names[column["name"]]
            indexed = column["attributes"].get("indexed")
            if not indexed or column_name in pkey_columns:
                continue
            index_attributes = indexed_attributes([column_name], indexed)
            if index_attributes is None:
                item["columns"][column_name]["attributes"]["unique"] = True
            else:
                auto_indexes[(column_name,)] = index_attributes
        _fill_auto_indexes(schema_name, sqlname, item, auto_indexes, pkey_columns)
        return {"tag": "table", "key": (package_name, table_name),
                "schema": schema_name, "name": sqlname, "item": item, "pkey": pkey_columns,
                "names": names, "composites": {key: physical(composite["attributes"]["columns"])
                                               for key, composite in composites.items()},
                "relations": relations}

    @staticmethod
    def _column_item(schema_name, table_name, column_name, source, pkey_columns, *,
                     implementation) -> dict:
        attributes = {key: source[key] for key in COL_JSON_KEYS if source.get(key) is not None}
        attributes.update({SQL_COLUMN_KEYS[key]: value for key, value
                           in sql_column_attributes(source, implementation).items()})
        attributes["dtype"] = attributes.get("dtype") or ("A" if attributes.get("size") else "T")
        attributes["dtype"] = _package_storage(attributes["dtype"], attributes)
        if column_name in pkey_columns:
            attributes["notnull"] = "_auto_"
            if len(pkey_columns) == 1:
                attributes.pop("unique", None)
        item: dict = new_column_item(schema_name, table_name, column_name, attributes=attributes)
        return item

    def finalize(self, result, target=None, *, foreignKeys=True, **opts):
        fragments = result if isinstance(result, list) else [result]
        if len(fragments) != 1 or fragments[0]["tag"] != "db":
            raise ValueError("Migration rendering requires exactly one database root")
        database = fragments[0]
        structure = new_structure_root(database["name"])
        root = structure["root"]
        packages = [child for child in database["children"] if child["tag"] == "package"]
        for package in packages:
            root["schemas"].setdefault(package["sqlschema"], new_schema_item(package["sqlschema"]))
        tables = {}
        for package in packages:
            for table in package["tables"]:
                root["schemas"].setdefault(table["schema"], new_schema_item(table["schema"]))
                root["schemas"][table["schema"]]["tables"][table["name"]] = table["item"]
                tables[table["key"]] = table
        target_indexes = []
        for table in tables.values():
            for columns, attributes in table["relations"]:
                parts = [part.strip() for part in str(attributes["related_column"]).split(".")]
                remote = tables[(parts[0], parts[1])]
                if len(parts) == 3:
                    remote_columns = remote["composites"].get(parts[2]) or [remote["names"][parts[2]]]
                else:
                    remote_columns = remote["pkey"]
                if remote_columns != remote["pkey"]:
                    target_indexes.append((remote, remote_columns))
                if not attributes.get("foreign_key") or not foreignKeys:
                    continue
                relation_attributes: dict[str, object] = {
                    "related_schema": remote["schema"],
                    "related_table": remote["name"],
                    "related_columns": remote_columns,
                    "constraint_type": "FOREIGN KEY",
                }
                for key, contract_key in _RELATION_ACTIONS.items():
                    # GenroPy onUpdate_sql defaults to cascade.
                    value = attributes.get(key) or ("cascade" if key == "onUpdate_sql" else None)
                    if value and SQL_ACTIONS[value.lower()]:
                        relation_attributes[contract_key] = SQL_ACTIONS[value.lower()]
                deferred = attributes.get("deferred")
                if attributes.get("deferrable") or deferred:
                    relation_attributes["deferrable"] = True
                if attributes.get("initially_deferred") or deferred:
                    relation_attributes["initially_deferred"] = True
                relation = new_relation_item(table["schema"], table["name"], columns,
                                             attributes=relation_attributes,
                                             constraint_name=attributes.get("constraint_name"))
                table["item"]["relations"][relation["entity_name"]] = relation
        for remote, columns in target_indexes:
            item = remote["item"]
            if len(columns) == 1 and item["columns"][columns[0]]["attributes"].get("unique"):
                continue
            if any(constraint["attributes"].get("constraint_type") == "UNIQUE"
                   and list(constraint["attributes"].get("columns") or ()) == columns
                   for constraint in item["constraints"].values()):
                continue
            index = new_index_item(remote["schema"], remote["name"], columns,
                                   attributes={"columns": dict.fromkeys(columns)})
            _refuse_uncovered(remote["schema"], remote["name"], columns,
                              item["indexes"].get(index["entity_name"]), None)
            item["indexes"].setdefault(index["entity_name"], index)
        for extension in database["children"]:
            if extension["tag"] == "extension":
                root["extensions"][extension["name"]] = new_extension_item(extension["name"])
        structure = StructureValidator().validate(structure)
        if target is None:
            return structure
        return super().finalize(json.dumps(structure, ensure_ascii=False, indent=2) + "\n", target)


def _fill_auto_indexes(schema_name, table_name, item, auto_indexes, pkey_columns) -> None:
    """Materialize the indexes ``indexed=`` and relations imply.

    ``auto_indexes`` maps the columns to the ``indexed={...}`` attributes,
    ``None`` for a plain index. An explicit ``index`` over the same
    columns wins — it carries a readable name and options the sugar
    cannot express — and an index over exactly the pkey columns is
    dropped: the primary key is already one.
    """
    for key, attributes in auto_indexes.items():
        columns = list(key)
        # As legacy, a column of the pkey gets no index of its own.
        if columns == pkey_columns or (len(columns) == 1 and (
                columns[0] in pkey_columns or item['columns'][columns[0]]['attributes'].get('unique'))):
            continue
        index = new_index_item(
            schema_name, table_name, columns,
            attributes=attributes or {"columns": dict.fromkeys(columns)},
        )
        _refuse_uncovered(schema_name, table_name, columns, item["indexes"].get(index['entity_name']),
                          attributes and index['attributes'])
        item["indexes"].setdefault(index["entity_name"], index)


def _refuse_uncovered(schema_name, table_name, columns, existing, attributes) -> None:
    """Refuse an implied index that an explicit ``index()`` on the same columns would replace.

    The migration engine keeps one index per column set: the explicit one wins, so
    ``indexed={...}`` options that differ from it, or a full index a relation needs
    under a partial or non-btree explicit one, would be lost.
    """
    if existing is None:
        return
    if attributes and {key: value for key, value in existing['attributes'].items() if key != 'index_name'} != {
            key: value for key, value in attributes.items() if key != 'index_name'}:
        raise UnsupportedFeatureError(
            f'{schema_name}.{table_name}: indexed={{...}} on {columns} conflicts with the explicit index on the same columns; declare the options in one of them')
    if existing['attributes'].get('where') or existing['attributes'].get('method') not in (None, 'btree'):
        raise UnsupportedFeatureError(
            f'{schema_name}.{table_name}: partial/non-btree index does not cover required full index on {columns}; migration engine permits one index per column set')


__all__ = ["SqlMigrationRenderer"]


# ---------------------------------------------------------------------------
# Plan and apply a migration against the live database
# ---------------------------------------------------------------------------

def migration_plan(db, *, allow_removals=False, foreignKeys=True, force=False, backup=False) -> dict:
    """Compare ``db.model`` with the live database and return the plan; change nothing.

    The plan is the dict of :func:`asqueel_migration.plan_migration`:
    ``sql``, ``warnings``, ``skipped`` (the changes the backend cannot apply,
    also in ``warnings``) and ``empty``. ``foreignKeys=False`` projects no
    foreign key, the relation indexes stay; ``force`` converts a filled column
    whose values may not convert (they become NULL) and ``backup`` keeps the
    old values in ``<column>__<old dtype>`` (it implies ``force``), as the
    legacy migration options.
    """
    database, desired = _migration_target(db, foreignKeys)
    try:
        return plan_migration(database, desired, allow_removals=allow_removals, force=force, backup=backup)
    except SqlMigrationError as error:
        raise MigrationError(str(error)) from error
    finally:
        database.closeConnection()


def migrate(db, *, allow_removals=False, foreignKeys=True, force=False, backup=False) -> dict:
    """Apply the plan and return the result; the options are those of :func:`migration_plan`.

    The result is the dict of :func:`asqueel_migration.apply_migration`.
    Refuses before any DDL when the plan has skipped changes. With ``backup``,
    every backup column that keeps lost values adds a warning to the result.
    After applying, raises :class:`MigrationError` if differences remain.
    """
    database, desired = _migration_target(db, foreignKeys)
    options = dict(allow_removals=allow_removals, force=force, backup=backup)
    try:
        plan = plan_migration(database, desired, **options)
        if plan['skipped']:
            raise MigrationError('The backend cannot apply these changes: ' + '; '.join(plan['skipped']))
        result = apply_migration(database, desired, expected_plan=plan['plan_id'], **options)
    except SqlMigrationError as error:
        raise MigrationError(str(error)) from error
    finally:
        database.closeConnection()
    for column, report in result['backups'].items():
        if 'error' in report:
            result['warnings'].append(f"{column}: conversion not verified ({report['error']}), "
                                      f"kept in backup column {report['backup_column']}")
        else:
            result['warnings'].append(f"{column}: {report['lost_values']} value(s) not converted, "
                                      f"kept in backup column {report['backup_column']}")
    # Not ``verified``: on SQLite a serial pkey reads back as a skipped
    # alter_column_type with no SQL, which the previous check accepted too.
    if not result['remaining']['empty']:
        raise MigrationError('Migration applied, but differences remain:\n' + result['remaining']['sql'])
    return result


def _migration_target(db, foreignKeys):
    """Render the migration structure and open the database facade of ``db``."""
    implementation, conninfo, kwargs = connection_settings(db.config)
    # 'name:module' names the implementation before the colon, as legacy.
    implementation = implementation.partition(':')[0]
    if implementation == 'sqlite':
        params = dict(kwargs or {})
        params.setdefault('dbname', conninfo)
    elif implementation in ('postgres', 'postgres3'):
        # psycopg is the PostgreSQL extra: a SQLite-only install does not have it.
        from psycopg.conninfo import conninfo_to_dict
        params = conninfo_to_dict(conninfo or '', **(kwargs or {}))
    else:
        raise MigrationError(f'Unsupported migration backend: {implementation}')
    if not params.get('dbname'):
        raise MigrationError('Declare connection.name (or an explicit dbname in the legacy connection settings)')
    desired = db.config.builder.render(mode='migration', foreignKeys=foreignKeys)
    # The physical destination is owned by connection settings, not the recipe root label.
    desired['root']['entity_name'] = params['dbname']
    schemas = sorted(desired['root']['schemas'])
    if not schemas or not db.model.tables:
        raise MigrationError('Declare at least one nonempty managed schema before migrating')
    connection = None
    if implementation == 'sqlite' and params['dbname'] == ':memory:':
        # A private :memory: database exists only on the application's connection.
        db._check_idle()
        state = db._connection_state
        if state['connection'] is None:
            app_conninfo, app_kwargs = db._connection_settings()
            state['connection'] = db.adapter.connect(app_conninfo, **app_kwargs)
        connection = state['connection']
    return database_for(implementation, params, application_schemas=schemas, connection=connection), desired
