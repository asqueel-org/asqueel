"""PostgreSQL adapter on psycopg 3, after legacy ``gnrpostgres3``.

The names ``postgres`` and ``postgres3`` both load this adapter.
"""
from __future__ import annotations

import re
from typing import Any

from ..contracts import UnsupportedFeatureError
from ._bag_xml import bag_xml_subquery
from .._sql_parameters import parameter_matches, substitute_parameters_and_text
from .base import SqlDbAdapter as SqlDbBaseAdapter, mask_bounds


class SqlDbAdapter(SqlDbBaseAdapter):
    """PostgreSQL SQL and psycopg named parameter bindings."""

    dialect = 'postgres'
    binding = 'psycopg_named'
    capabilities = frozenset({
        'select', 'insert', 'update', 'delete', 'returning_insert',
        'returning_update', 'returning_delete', 'left_join', 'limit', 'offset',
        'default_values', 'for_update', 'cached_fetch',
    })

    def connect(self, conninfo: str, **kwargs: Any) -> Any:
        if 'foreignKeys' in kwargs:
            raise ValueError('foreignKeys is a SQLite connection option, not available on PostgreSQL')
        # psycopg is the PostgreSQL extra: imported only when connecting.
        import psycopg

        if kwargs.get('autocommit'):
            raise ValueError('autocommit is incompatible with explicit transactions')
        return psycopg.connect(conninfo, **kwargs)

    def cursor(self, connection, cursorname=None):
        """A named server-side cursor when ``cursorname`` is given, else a client cursor."""
        from psycopg.rows import tuple_row

        return connection.cursor(cursorname or '', row_factory=tuple_row)

    def vacuum(self, table='', full=False):
        """Legacy vacuum: ``VACUUM [FULL] ANALYZE [table]`` on a separate autocommit connection."""
        import psycopg

        conninfo, connect_kwargs = self.dbroot._connection_settings()
        sql = f"VACUUM {'FULL ' if full else ''}ANALYZE {table}".rstrip()
        with psycopg.connect(conninfo, **{**connect_kwargs, 'autocommit': True}) as connection:
            connection.execute(sql)

    def prepareSqlText(self, sql, kwargs):
        """Named arguments as psycopg ``%(name)s``, every other ``%`` doubled; ``REGEXP`` as ``~*``.

        Execution always passes a mapping, so psycopg reads ``%%`` as ``%`` even without parameters.
        """
        sql = self.adaptTupleListSet(sql, kwargs)
        sql = substitute_parameters_and_text(
            sql, lambda m: '%(' + m['parameter'] + ')s', lambda text: text.replace('%', '%%'), self.dialect)
        return sql.replace('REGEXP', '~*'), kwargs

    def adaptTupleListSet(self, sql, sqlargs):
        """gnrpostgres3.adaptTupleListSet: unroll IN values for psycopg 3.

        The old psycopg2 adapter kept a single tuple binding, which psycopg 3
        cannot use after IN. Reuse the existing legacy psycopg3 algorithm instead.
        """
        for key, values in list(sqlargs.items()):
            if not isinstance(values, (list, set, tuple)):
                continue
            if not isinstance(values, list):
                values = list(values)
            if not values:
                pattern = r'''((\"?t\d+)(_t\d+)*\"?.\"?\w+\"?" +)(NOT +)*(IN) *:%s''' % key
                positions = {m.start() for m in parameter_matches(sql, self.dialect)}
                sql = re.sub(pattern, lambda m: ('TRUE' if m.group(4) else 'FALSE')
                             if m.end() - len(key) - 1 in positions else m[0], sql, flags=re.I)
            else:
                def unroll(match):
                    sqlargs.pop(key, None)
                    base = match.group(2)
                    names = []
                    for i, value in enumerate(values):
                        name = '%s_%s' % (base, i)
                        names.append(':' + name)
                        sqlargs[name] = value
                    return '%s(%s)' % (match.group(1), ','.join(names))
                positions = {m.start() for m in parameter_matches(sql, self.dialect)}
                sql = re.sub(r'( *IN) *(?::)(%s)\b' % re.escape(key),
                             lambda m: unroll(m) if m.start(2) - 1 in positions else m[0],
                             sql, flags=re.I)
        return sql

    def create_table_as(self, schema, table, sql):
        """An UNLOGGED table: a cached fetch is rebuilt from its query, never recovered."""
        return f'CREATE UNLOGGED TABLE {self.adaptSqlName(schema)}.{self.adaptSqlName(table)} AS {sql}'

    def create_unique_index(self, schema, table, column):
        """The index name is left to PostgreSQL: the table name may already take 63 bytes."""
        return f'CREATE UNIQUE INDEX ON {self.adaptSqlName(schema)}.{self.adaptSqlName(table)} ({self.adaptSqlName(column)})'

    def table_columns_sql(self):
        """``(name, is_text)`` of the columns of table ``:table`` in schema ``:schema``, in order."""
        return ("SELECT column_name, data_type IN ('text', 'character varying', 'character') "
                "FROM information_schema.columns WHERE table_schema = :schema AND table_name = :table "
                "ORDER BY ordinal_position")

    def cached_fetch_lock(self):
        """A transaction advisory lock on the key: a new key has no catalog row to lock yet."""
        return 'SELECT pg_advisory_xact_lock(hashtext(:key))'

    def adaptSqlName(self, name: str) -> str:
        quoted = super().adaptSqlName(name)
        if len(name.encode('utf-8')) > 63:
            raise ValueError('PostgreSQL identifiers must not exceed 63 UTF-8 bytes')
        return quoted

    def bag_item_formula(self, bagcolumn: str, dtype: str) -> str:
        """Legacy XPath extraction and casts, with the existing text fallback.

        The compiler binds calculated_path in the owning formula's scope and
        resolves bagcolumn using the ordinary field/relation expression path.
        """
        expression = f'CAST((xpath(:calculated_path, CAST({bagcolumn} AS XML)))[1] AS text)'
        destination = {
            'N': 'numeric', 'B': 'boolean', 'D': 'date',
            'H': 'time without time zone', 'HZ': 'time with time zone',
            'DH': 'timestamp without time zone', 'DHZ': 'timestamp with time zone',
            'I': 'integer', 'L': 'bigint', 'R': 'real', 'F': 'real',
        }.get(dtype, 'text')
        return expression if destination == 'text' else f'CAST(({expression}) AS {destination})'

    def json_sql_subquery(self, sql, alias, columns):
        """Reuse the legacy row wrapper, with the agreed empty-array result."""
        aggregate = self.aggregate_sql_subquery(sql, 'json', alias, ())
        return f"COALESCE({aggregate}, '[]'::jsonb)"

    def xml_sql_subquery(self, sql, alias, columns):
        """Render the agreed typed Bag wire from an ordered child SELECT."""
        return bag_xml_subquery(sql, alias, columns, self.asTranslator)

    def aggregate_sql_subquery(self, sql, mode, alias, columns):
        """Existing subQueryColumn wrappers over a resolved string SELECT."""
        row = self.adaptSqlName(alias)
        if mode == 'json':
            aggregate = f'jsonb_agg(row_to_json({row}))'
        elif mode == 'xml':
            fields = ', '.join(f'{row}.{self.adaptSqlName(c)} AS {self.adaptSqlName(c)}'
                               for c in columns)
            aggregate = f'CAST(xmlagg(xmlelement(name {row}, xmlforest({fields}))) AS text)'
        else:
            raise UnsupportedFeatureError(f'Unsupported subquery aggregate mode: {mode!r}')
        return f'(SELECT {aggregate} FROM ({sql}) AS {row})'

    def unaccentFormula(self, field):
        return 'unaccent({prefix}{field})'.format(field=field,
                                                  prefix='' if field[0] in ('@', '$') else '$')

    def mask_field_sql(self, field, mode='2-4', placeholder='*'):
        """Legacy PostgreSQL masking expression."""
        placeholder = placeholder.replace("'", "''")
        if mode == 'email':
            # Mask local part of email, keep domain visible (default 2 chars visible at start)
            sql_formula = f"""
                CASE
                    WHEN position('@' in {field}) > 0 THEN
                        substring({field} from 1 for 2) ||
                        repeat('{placeholder}', greatest(length(split_part({field}, '@', 1)) - 2, 0)) ||
                        '@' ||
                        split_part({field}, '@', 2)
                    ELSE
                        {field}
                END
            """.strip()

        elif mode == 'creditcard':
            # Show only last 4 digits
            sql_formula = f"""
                CASE
                    WHEN length({field}) > 4 THEN
                        repeat('{placeholder}', length({field}) - 4) || right({field}, 4)
                    ELSE
                        {field}
                END
            """.strip()

        elif mode == 'phone':
            # Keep country code (3 chars) and last 3 digits visible
            sql_formula = f"""
                CASE
                    WHEN length({field}) > 6 THEN
                        substring({field} from 1 for 3) ||
                        repeat('{placeholder}', length({field}) - 6) ||
                        right({field}, 3)
                    ELSE
                        {field}
                END
            """.strip()

        else:
            visible_start, visible_end = mask_bounds(mode)
            sql_formula = f"""
                CASE
                    WHEN length({field}) > {visible_start + visible_end} THEN
                        substring({field} from 1 for {visible_start}) ||
                        repeat('{placeholder}', length({field}) - {visible_start} - {visible_end}) ||
                        right({field}, {visible_end})
                    ELSE
                        {field}
                END
            """.strip()

        return sql_formula
