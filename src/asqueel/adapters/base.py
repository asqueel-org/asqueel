"""Base adapter, after legacy ``_gnrbaseadapter.SqlDbAdapter``.

The database is the abstraction; the adapter adapts it to one implementation:
SQL text, quoting, capabilities, connection, cursor and value conversion.
Backend modules override what differs.
"""
from __future__ import annotations

from ..contracts import UnsupportedFeatureError


class SqlDbAdapter:
    """Common SQL; each backend adapter overrides its own peculiarities."""

    dialect = ''
    binding = ''
    capabilities: frozenset[str] = frozenset()

    def __init__(self, dbroot, **options):
        self.dbroot = dbroot
        capabilities = options.pop('capabilities', None)
        if options:
            raise ValueError(f'Unknown adapter options: {sorted(options)}')
        if capabilities is not None:
            unknown = set(capabilities) - type(self).capabilities
            if unknown:
                raise ValueError(f'Unknown {self.dialect} capabilities: {sorted(unknown)}')
            self.capabilities = frozenset(capabilities)

    def _require(self, capability):
        if capability not in self.capabilities:
            raise UnsupportedFeatureError(f'{self.dialect}: unsupported capability {capability}')

    def asTranslator(self, as_: str) -> str:  # wf:phase-2:new
        """Legacy asTranslator: quote result aliases; let the DB handle length.

        A generated expression alias can exceed PostgreSQL's identifier length,
        as in the existing priced_rows_pct scalar subquery. Physical identifiers
        keep their separate adaptSqlName validation.
        """
        return '"' + as_.replace('"', '""') + '"'

    def adaptSqlName(self, name: str) -> str:  # wf:phase-2:new
        if not isinstance(name, str) or not name or '\x00' in name:
            raise ValueError('SQL identifiers must be nonempty strings without NUL')
        return '"' + name.replace('"', '""') + '"'

    def empty_collection(self, negated: bool) -> str:
        """Operand-free replacement of ``IN`` / ``NOT IN`` for an empty collection."""
        return "<> ALL('{}')" if negated else "= ANY('{}')"

    def string_join(self, expressions: list[str], separator: str) -> str:  # wf:phase-2:new
        """Legacy string_join: skip NULL terms, keep empty strings."""
        literal = "'" + separator.replace("'", "''") + "'"
        return f"array_to_string(ARRAY[{', '.join(expressions)}]::text[], {literal})"

    def concat_template(self, parts: list[tuple[str, bool]]) -> str:
        """#TEMPLATE: literal text and expressions; a NULL expression gives ''."""
        terms = [f"'{text.replace(chr(39), chr(39) * 2)}'" if literal else text
                 for text, literal in parts]
        return f"concat({', '.join(terms)})" if terms else "''"

    def join_sql_subquery(self, sql, alias):
        """Concatenate an ordered row source, preserving empty-value positions."""
        row = self.adaptSqlName(alias)
        return (f"(SELECT COALESCE(string_agg({row}.value, {row}.separator), '') "
                f'FROM ({sql}) AS {row})')

    def compileSql(self, maintable, columns, distinct='', joins=None, where=None,  # wf:phase-2:new
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
                  f' FROM {maintable} AS {self.adaptSqlName(maintable_as)}']
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
