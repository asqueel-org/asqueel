"""Read-only PostgreSQL catalog import for the native profile."""
from __future__ import annotations

from dataclasses import dataclass, replace
import re
from typing import Any

from .contracts import Column, Relation, ResolvedModel, Table
from .model import column_ui


@dataclass(frozen=True)
class ImportResult:
    model: ResolvedModel
    warnings: tuple[str, ...]


def _query(connection, sql: str, schemas: list[str]) -> list[dict[str, Any]]:
    with connection.cursor() as cursor:
        cursor.execute(sql, (schemas,))
        names = [d.name if hasattr(d, 'name') else d[0] for d in cursor.description]
        return [dict(row) if isinstance(row, dict) else dict(zip(names, row))
                for row in cursor.fetchall()]


def inspect_postgres(connection, schemas, *, ui=None) -> ImportResult:
    """Compatibility facade for the read-only structural catalog provider."""
    from .catalog_provider import PostgresCatalogProvider

    return PostgresCatalogProvider().inspect(connection, schemas, ui=ui)


def _inspect_postgres(connection, schemas, *, ui=None) -> ImportResult:
    """Import explicitly selected schemas without DDL, commits or rollbacks.

    The caller owns the connection and snapshot/transaction. Unsupported objects
    are reported; catalog definitions remain metadata, never executable migration
    instructions. Reapply the same UI overlay on each import to preserve it.
    """
    if isinstance(schemas, str):
        raise TypeError('schemas must be a sequence of schema names, not a string')
    schemas = list(dict.fromkeys(schemas))
    if not schemas or any(not isinstance(s, str) or not s for s in schemas):
        raise ValueError('At least one explicit nonempty schema is required')
    warnings: list[str] = []
    known_schemas = _query(connection, 'SELECT nspname AS name FROM pg_catalog.pg_namespace WHERE nspname=ANY(%s)', schemas)
    missing = set(schemas) - {row['name'] for row in known_schemas}
    warnings.extend(f'{name}: requested schema does not exist' for name in sorted(missing))
    objects = _query(connection, '''
        SELECT n.nspname AS schema_name, c.relname AS table_name,
               c.relkind AS kind, c.relispartition AS is_partition,
               c.relrowsecurity AS row_security,
               EXISTS(SELECT 1 FROM pg_catalog.pg_inherits h
                      WHERE h.inhrelid=c.oid OR h.inhparent=c.oid) AS inheritance
        FROM pg_catalog.pg_class c
        JOIN pg_catalog.pg_namespace n ON n.oid=c.relnamespace
        WHERE n.nspname=ANY(%s) AND c.relkind IN ('r','p','v','m','f','S')
        ORDER BY n.nspname,c.relname
    ''', schemas)
    tables = {}
    for obj in objects:
        key = f"{obj['schema_name']}.{obj['table_name']}"
        if obj['kind'] != 'r' or obj['is_partition'] or obj['inheritance']:
            warnings.append(f'{key}: unmanaged object kind={obj["kind"]}, partition={obj["is_partition"]}, inheritance={obj["inheritance"]}')
            continue
        if obj['row_security']:
            warnings.append(f'{key}: row security is enforced by PostgreSQL, not modeled')
        tables[key] = Table(obj['table_name'], obj['schema_name'], attributes={
            'provenance': {'kind': 'postgres', 'schema': obj['schema_name'], 'table': obj['table_name']},
            'constraints': (), 'indexes': (),
        }, identity=key)
    column_rows = _query(connection, '''
        SELECT n.nspname AS schema_name,c.relname AS table_name,a.attname AS name,
               pg_catalog.format_type(a.atttypid,a.atttypmod) AS dtype,
               a.attnotnull AS notnull, a.attidentity AS identity_kind,
               a.attgenerated AS generated,
               a.attcollation=typ.typcollation AS default_collation,
               coll.collname AS collation_name,cn.nspname AS collation_schema,
               pg_catalog.pg_get_serial_sequence(format('%%I.%%I',n.nspname,c.relname),a.attname) AS owned_sequence,
               EXISTS(SELECT 1 FROM pg_catalog.pg_depend dep
                      JOIN pg_catalog.pg_class seq ON seq.oid=dep.refobjid AND seq.relkind='S'
                      WHERE dep.classid='pg_catalog.pg_attrdef'::regclass AND dep.objid=d.oid
                        AND dep.refclassid='pg_catalog.pg_class'::regclass) AS sequence_default,
               pg_catalog.pg_get_expr(d.adbin,d.adrelid) AS "default",
               pg_catalog.col_description(c.oid,a.attnum) AS comment
        FROM pg_catalog.pg_attribute a
        JOIN pg_catalog.pg_class c ON c.oid=a.attrelid
        JOIN pg_catalog.pg_namespace n ON n.oid=c.relnamespace
        JOIN pg_catalog.pg_type typ ON typ.oid=a.atttypid
        LEFT JOIN pg_catalog.pg_collation coll ON coll.oid=a.attcollation
        LEFT JOIN pg_catalog.pg_namespace cn ON cn.oid=coll.collnamespace
        LEFT JOIN pg_catalog.pg_attrdef d ON d.adrelid=c.oid AND d.adnum=a.attnum
        WHERE n.nspname=ANY(%s) AND a.attnum>0 AND NOT a.attisdropped
          AND c.relkind IN ('r','p')
        ORDER BY n.nspname,c.relname,a.attnum
    ''', schemas)
    for row in column_rows:
        key = f"{row['schema_name']}.{row['table_name']}"
        if key not in tables:
            continue
        name = row['name']
        path = f'{key}.{name}'
        attrs = dict(row)
        attrs['provenance'] = {'kind': 'postgres', 'column': path}
        if row['generated']:
            warnings.append(f'{path}: generated column; write restrictions belong to PostgreSQL')
        attrs['raw_type'] = row['dtype']
        dtype, size = normalize_postgres_type(row['dtype'])
        if size:
            attrs['size'] = size
        if dtype == row['dtype'] and dtype != 'jsonb':
            warnings.append(f'{path}: type {dtype} has no asqueel code; raw type preserved')
        column = Column(name, dtype, ui=column_ui({}, path, path, ui),
                        identity=path, attributes=attrs)
        tables[key] = replace(tables[key], columns={**tables[key].columns, name: column})
    constraints = _query(connection, '''
        SELECT n.nspname AS schema_name,c.relname AS table_name,k.conname AS name,
               k.contype AS kind, k.condeferrable AS deferrable,
               k.condeferred AS initially_deferred,
               k.confdeltype AS on_delete_code,k.confupdtype AS on_update_code,
               k.convalidated AS validated, k.confmatchtype AS match_type,
               k.confdelsetcols AS delete_set_columns,
               pg_catalog.pg_get_constraintdef(k.oid,true) AS definition,
               ARRAY(SELECT a.attname FROM unnest(k.conkey) WITH ORDINALITY x(num,pos)
                     JOIN pg_catalog.pg_attribute a ON a.attrelid=c.oid AND a.attnum=x.num
                     ORDER BY x.pos) AS columns,
               tn.nspname AS target_schema,tc.relname AS target_table,
               ARRAY(SELECT a.attname FROM unnest(k.confkey) WITH ORDINALITY x(num,pos)
                     JOIN pg_catalog.pg_attribute a ON a.attrelid=tc.oid AND a.attnum=x.num
                     ORDER BY x.pos) AS target_columns
        FROM pg_catalog.pg_constraint k
        JOIN pg_catalog.pg_class c ON c.oid=k.conrelid
        JOIN pg_catalog.pg_namespace n ON n.oid=c.relnamespace
        LEFT JOIN pg_catalog.pg_class tc ON tc.oid=k.confrelid
        LEFT JOIN pg_catalog.pg_namespace tn ON tn.oid=tc.relnamespace
        WHERE n.nspname=ANY(%s) ORDER BY n.nspname,c.relname,k.conname
    ''', schemas)
    for row in constraints:
        key = f"{row['schema_name']}.{row['table_name']}"
        if key not in tables:
            continue
        table = tables[key]
        attrs = dict(table.attributes)
        attrs['constraints'] = (*attrs['constraints'], row)
        tables[key] = replace(table, attributes=attrs,
                              pkey=tuple(row['columns']) if row['kind'] == 'p' else table.pkey)
    for row in constraints:
        key = f"{row['schema_name']}.{row['table_name']}"
        if key not in tables or row['kind'] != 'f':
            continue
        target = f"{row['target_schema']}.{row['target_table']}"
        if target not in tables:
            warnings.append(f'{key}.{row["name"]}: foreign key target {target} is outside imported tables')
            continue
        # Constraint names preserve multiple FKs between the same two tables.
        name = row['name']
        relation = Relation(name, target, tuple(row['columns']), tuple(row['target_columns']))
        tables[key] = replace(tables[key], relations={**tables[key].relations, name: relation})
    indexes = _query(connection, '''
        SELECT n.nspname AS schema_name,t.relname AS table_name,i.relname AS name,
               x.indisunique AS "unique",x.indisprimary AS "primary",
               x.indisvalid AS valid,pg_catalog.pg_get_indexdef(i.oid) AS definition,
               am.amname AS method, x.indnkeyatts AS key_count,
               x.indnullsnotdistinct AS nulls_not_distinct,
               i.reloptions AS options,i.reltablespace AS tablespace,
               ARRAY(SELECT a.attname FROM unnest(x.indkey) WITH ORDINALITY k(num,pos)
                     LEFT JOIN pg_catalog.pg_attribute a ON a.attrelid=t.oid AND a.attnum=k.num
                     ORDER BY k.pos) AS columns,
               x.indoption::smallint[] AS ordering,
               NOT EXISTS(SELECT 1 FROM unnest(x.indkey,x.indcollation) k(num,coll)
                          JOIN pg_catalog.pg_attribute a ON a.attrelid=t.oid AND a.attnum=k.num
                          WHERE k.coll<>a.attcollation) AS default_collations,
               NOT EXISTS(SELECT 1 FROM unnest(x.indclass) op(oid)
                          JOIN pg_catalog.pg_opclass cls ON cls.oid=op.oid
                          WHERE NOT cls.opcdefault) AS default_opclasses,
               EXISTS(SELECT 1 FROM pg_catalog.pg_constraint k
                      WHERE k.conindid=x.indexrelid) AS constraint_owned,
               pg_catalog.pg_get_expr(x.indpred,x.indrelid) AS predicate
        FROM pg_catalog.pg_index x
        JOIN pg_catalog.pg_class t ON t.oid=x.indrelid
        JOIN pg_catalog.pg_namespace n ON n.oid=t.relnamespace
        JOIN pg_catalog.pg_class i ON i.oid=x.indexrelid
        JOIN pg_catalog.pg_am am ON am.oid=i.relam
        WHERE n.nspname=ANY(%s) ORDER BY n.nspname,t.relname,i.relname
    ''', schemas)
    for row in indexes:
        key = f"{row['schema_name']}.{row['table_name']}"
        if key in tables:
            attrs = dict(tables[key].attributes)
            attrs['indexes'] = (*attrs['indexes'], row)
            tables[key] = replace(tables[key], attributes=attrs)
    unmanaged = _query(connection, '''
        SELECT n.nspname AS schema_name,t.tgname AS name,'trigger' AS kind
        FROM pg_catalog.pg_trigger t
        JOIN pg_catalog.pg_class c ON c.oid=t.tgrelid
        JOIN pg_catalog.pg_namespace n ON n.oid=c.relnamespace
        WHERE n.nspname=ANY(%s) AND NOT t.tgisinternal
    ''', schemas)
    routines = _query(connection, """
        SELECT n.nspname AS schema_name,p.proname AS name,'routine' AS kind
        FROM pg_catalog.pg_proc p
        JOIN pg_catalog.pg_namespace n ON n.oid=p.pronamespace
        WHERE n.nspname=ANY(%s)
    """, schemas)
    warnings.extend(f'{r["schema_name"]}.{r["name"]}: unmanaged {r["kind"]}'
                    for r in [*unmanaged, *routines])
    return ImportResult(ResolvedModel(tables, name=connection.info.dbname, warnings=tuple(warnings)), tuple(warnings))


def normalize_postgres_type(raw_type: str) -> tuple[str, str | None]:
    """Normalize common types while retaining unknown dialect types verbatim."""
    match = re.search(r'\(([^)]+)\)', raw_type)
    size = match.group(1) if match else None
    base = re.sub(r'\([^)]*\)', '', raw_type).strip()
    codes = {
        'integer': 'I', 'smallint': 'I', 'bigint': 'L', 'boolean': 'B',
        'bytea': 'O', 'character varying': 'A', 'character': 'C', 'text': 'T',
        'numeric': 'N', 'double precision': 'R', 'real': 'R', 'money': 'M',
        'date': 'D', 'time with time zone': 'HZ', 'time without time zone': 'H',
        'timestamp with time zone': 'DHZ', 'timestamp without time zone': 'DH',
        'jsonb': 'jsonb', 'tsvector': 'TSV', 'vector': 'VEC',
    }
    if base == 'character varying' and size:
        size = '0:' + size
    return codes.get(base, raw_type), size
