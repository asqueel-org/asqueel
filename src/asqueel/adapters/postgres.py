"""PostgreSQL adapter on psycopg 3, after legacy ``gnrpostgres3``.

The names ``postgres`` and ``postgres3`` both load this adapter.
"""
from __future__ import annotations

from ..contracts import UnsupportedFeatureError
from ._bag_xml import bag_xml_subquery
from .base import SqlDbAdapter as SqlDbBaseAdapter


class SqlDbAdapter(SqlDbBaseAdapter):
    """PostgreSQL SQL and psycopg named parameter bindings."""

    dialect = 'postgres'
    binding = 'psycopg_named'
    capabilities = frozenset({
        'select', 'insert', 'update', 'delete', 'returning_insert',
        'returning_update', 'returning_delete', 'left_join', 'limit', 'offset',
        'default_values', 'for_update',
    })

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
