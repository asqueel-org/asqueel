"""SQLite rendering with attached schemas and connection-level write locking."""

from .postgres import PostgresDialect
from ..contracts import UnsupportedFeatureError


class SqliteDialect(PostgresDialect):
    """Common SELECT/DML syntax; SQLite-specific RETURNING and pagination."""

    name = 'sqlite'

    def bag_item_formula(self, bagcolumn, dtype):
        raise UnsupportedFeatureError('SQLite does not support legacy bagItemColumn XPath extraction')


    def aggregate_sql_subquery(self, sql, mode, alias, columns):
        raise UnsupportedFeatureError(f'SQLite does not support legacy subQueryColumn mode={mode!r}')


    def quote_identifier(self, name):
        if not isinstance(name, str) or not name or '\x00' in name:
            raise ValueError('SQL identifiers must be nonempty strings without NUL')
        return '"' + name.replace('"', '""') + '"'

    def empty_collection(self, negated):
        # SQLite has no array literal; an empty row source is the portable form.
        return 'NOT IN (SELECT 1 WHERE 0)' if negated else 'IN (SELECT 1 WHERE 0)'

    def concat_non_null(self, expressions, separator):
        # Prefix each non-NULL term, then remove exactly the first separator.
        # Unlike trim(), this preserves separator characters in the values.
        literal = "'" + separator.replace("'", "''") + "'"
        terms = [f"COALESCE({literal} || ({expression}), '')" for expression in expressions]
        joined = ' || '.join(terms) or "''"
        return f'substr({joined}, {len(separator) + 1})'


    def compile_sql(self, maintable, columns, distinct='', joins=None, where=None,
                    group_by=None, having=None, order_by=None, limit=None, offset=None,
                    for_update=False, maintable_as='t0'):
        if for_update:
            self._require('for_update')
        if offset is not None and limit is None:
            limit = 9223372036854775807
        return super().compile_sql(maintable, columns, distinct, joins, where, group_by,
                                   having, order_by, limit, offset, False, maintable_as)
