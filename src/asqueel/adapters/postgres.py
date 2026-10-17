"""PostgreSQL adapter on psycopg 3, after legacy ``gnrpostgres3``.

The names ``postgres`` and ``postgres3`` both load this adapter.
"""
from __future__ import annotations

import re
from typing import Any

from ..contracts import UnsupportedFeatureError
from ._bag_xml import bag_xml_subquery
from .base import SQL_PARAMS, SqlDbAdapter as SqlDbBaseAdapter, mask_bounds


class SqlDbAdapter(SqlDbBaseAdapter):
    """PostgreSQL SQL and psycopg named parameter bindings."""

    dialect = 'postgres'
    binding = 'psycopg_named'
    capabilities = frozenset({
        'select', 'insert', 'update', 'delete', 'returning_insert',
        'returning_update', 'returning_delete', 'left_join', 'limit', 'offset',
        'default_values', 'for_update',
    })

    def connect(self, conninfo: str, **kwargs: Any) -> Any:
        # psycopg is the PostgreSQL extra: imported only when connecting.
        import psycopg

        if kwargs.get('autocommit'):
            raise ValueError('autocommit is incompatible with explicit transactions')
        return psycopg.connect(conninfo, **kwargs)

    def cursor(self, connection):  # wf:phase-2:new
        from psycopg.rows import tuple_row

        return connection.cursor(row_factory=tuple_row)

    def prepareSqlText(self, sql, kwargs):  # wf:phase-2:new
        """Named arguments as psycopg ``%(name)s``; ``REGEXP`` as ``~*``."""
        sql = self.adaptTupleListSet(sql, kwargs)
        return SQL_PARAMS.sub(r'%(\1)s\2', sql).replace('REGEXP', '~*'), kwargs

    def adaptTupleListSet(self, sql, sqlargs):  # wf:phase-2:new
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
                sql = re.sub(pattern, lambda m: 'TRUE' if m.group(4) else 'FALSE', sql, flags=re.I)
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
                sql = re.sub(r'( *IN) *(?::)(%s)\b' % key, unroll, sql, flags=re.I)
        return sql

    def adaptSqlName(self, name: str) -> str:  # wf:phase-2:new
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

    def unaccentFormula(self, field):  # wf:phase-2:new
        return 'unaccent({prefix}{field})'.format(field=field,
                                                  prefix='' if field[0] in ('@', '$') else '$')

    def mask_field_sql(self, field, mode='2-4', placeholder='*'):  # wf:phase-2:new
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
