"""PostgreSQL rendering of already-resolved plans, without rescanning SQL.

No model lookup, connection or driver binding belongs at this boundary.
"""
from __future__ import annotations



from ..contracts import UnsupportedFeatureError
from ._bag_xml import bag_xml_subquery



class PostgresDialect:
    """The native PostgreSQL data dialect, independent of any Python driver."""

    name = 'postgresql'
    capabilities = frozenset({
        'select', 'insert', 'update', 'delete', 'returning_insert',
        'returning_update', 'returning_delete', 'left_join', 'limit', 'offset',
        'default_values', 'for_update',
    })

    def __init__(self, *, capabilities: frozenset[str] | None = None):
        if capabilities is not None:
            unknown = set(capabilities) - type(self).capabilities
            if unknown:
                raise ValueError(f'Unknown PostgreSQL capabilities: {sorted(unknown)}')
            self.capabilities = frozenset(capabilities)

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


    def join_sql_subquery(self, sql, alias):
        """Concatenate an ordered row source, preserving empty-value positions."""
        row = self.quote_identifier(alias)
        return (f"(SELECT COALESCE(string_agg({row}.value, {row}.separator), '') "
                f'FROM ({sql}) AS {row})')

    def json_sql_subquery(self, sql, alias, columns):
        """Reuse the legacy row wrapper, with the agreed empty-array result."""
        aggregate = self.aggregate_sql_subquery(sql, 'json', alias, ())
        return f"COALESCE({aggregate}, '[]'::jsonb)"

    def xml_sql_subquery(self, sql, alias, columns):
        """Render the agreed typed Bag wire from an ordered child SELECT."""
        return bag_xml_subquery(sql, alias, columns, self.as_translator)

    def aggregate_sql_subquery(self, sql, mode, alias, columns):
        """Existing subQueryColumn wrappers over a resolved string SELECT."""
        row = self.quote_identifier(alias)
        if mode == 'json':
            aggregate = f'jsonb_agg(row_to_json({row}))'
        elif mode == 'xml':
            fields = ', '.join(f'{row}.{self.quote_identifier(c)} AS {self.quote_identifier(c)}'
                               for c in columns)
            aggregate = f'CAST(xmlagg(xmlelement(name {row}, xmlforest({fields}))) AS text)'
        else:
            raise UnsupportedFeatureError(f'Unsupported subquery aggregate mode: {mode!r}')
        return f'(SELECT {aggregate} FROM ({sql}) AS {row})'

    def as_translator(self, name: str) -> str:
        """Legacy asTranslator: quote result aliases; let the DB handle length.

        A generated expression alias can exceed PostgreSQL's identifier length,
        as in the existing priced_rows_pct scalar subquery. Physical identifiers
        keep their separate quote_identifier validation.
        """
        return '"' + name.replace('"', '""') + '"'

    def quote_identifier(self, name: str) -> str:
        if not isinstance(name, str) or not name or '\x00' in name:
            raise ValueError('SQL identifiers must be nonempty strings without NUL')
        if len(name.encode('utf-8')) > 63:
            raise ValueError('PostgreSQL identifiers must not exceed 63 UTF-8 bytes')
        return '"' + name.replace('"', '""') + '"'


    def empty_collection(self, negated: bool) -> str:
        """Operand-free replacement of ``IN`` / ``NOT IN`` for an empty collection."""
        return "<> ALL('{}')" if negated else "= ANY('{}')"

    def concat_non_null(self, expressions: list[str], separator: str) -> str:
        """Legacy reason formulas: skip NULL terms, keep empty strings."""
        literal = "'" + separator.replace("'", "''") + "'"
        return f"array_to_string(ARRAY[{', '.join(expressions)}]::text[], {literal})"

    def concat_template(self, parts: list[tuple[str, bool]]) -> str:
        """#TEMPLATE: literal text and expressions; a NULL expression gives ''."""
        terms = [f"'{text.replace(chr(39), chr(39) * 2)}'" if literal else text
                 for text, literal in parts]
        return f"concat({', '.join(terms)})" if terms else "''"


    def _require(self, capability):
        if capability not in self.capabilities:
            raise UnsupportedFeatureError(f'{self.name}: unsupported capability {capability}')

    def compile_sql(self, maintable, columns, distinct='', joins=None, where=None,
                    group_by=None, having=None, order_by=None, limit=None, offset=None,
                    for_update=False, maintable_as='t0'):
        """Legacy compileSql over resolved strings."""
        self._require('select')
        if not columns.strip():
            raise ValueError('SELECT needs result columns')
        for name, value in (('limit', limit), ('offset', offset)):
            if value is not None and (type(value) is not int or value < 0):
                raise ValueError(f'{name} must be a nonnegative integer')
            if value is not None:
                self._require(name)
        if for_update:
            self._require('for_update')
        result = [f'SELECT {distinct}{columns}',
                  f' FROM {maintable} AS {self.quote_identifier(maintable_as)}']
        for join in joins or ():
            self._require('left_join')
            result.append(f'       {join}')
        for name, value in (('WHERE', where), ('GROUP BY', group_by), ('HAVING', having),
                            ('ORDER BY', order_by)):
            if value:
                result.append(f'{name} {value}')
        # Retain the already agreed zero/offset contract of the native adapters.
        if limit is not None:
            result.append(f'LIMIT {limit}')
        if offset is not None:
            result.append(f'OFFSET {offset}')
        if for_update:
            result.append(f'FOR UPDATE OF {maintable_as}')
        return '\n'.join(result)
