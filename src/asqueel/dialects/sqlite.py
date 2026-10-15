"""SQLite rendering with attached schemas and connection-level write locking."""
from dataclasses import replace

from .postgres import PostgresDialect, _tokens
from ..contracts import UnsupportedFeatureError
from ..query_plan import Fragment, Identifier


class SqliteDialect(PostgresDialect):
    """Common SELECT/DML syntax; SQLite-specific RETURNING and pagination."""

    name = 'sqlite'

    def bag_item_formula(self, bagcolumn, dtype):
        raise UnsupportedFeatureError('SQLite does not support legacy bagItemColumn XPath extraction')

    def aggregate_subquery(self, plan, mode, alias):
        # The legacy JSON/XML wrappers use PostgreSQL functions. Do not invent
        # different SQL, empty-result semantics or Python codecs for SQLite.
        raise UnsupportedFeatureError(f'SQLite does not support legacy subQueryColumn mode={mode!r}')

    def aggregate_sql_subquery(self, sql, mode, alias, columns):
        raise UnsupportedFeatureError(f'SQLite does not support legacy subQueryColumn mode={mode!r}')

    def tokens(self, expression):
        if not isinstance(expression, str):
            raise TypeError('SQL expressions must be strings')
        return _tokens(expression, sqlite=True)

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

    def render(self, plan):
        if plan.operation == 'count':
            return self._count(plan)
        # SQLite has no FOR UPDATE. The driver begins an IMMEDIATE transaction
        # before any statement, covering the read/modify/write cycle in hooks.
        if type(plan.for_update) is not bool:
            raise ValueError('for_update must be a boolean')
        # Clearing for_update below would hide the combinations it is rejected with.
        self._grouping(plan)
        if plan.for_update:
            self._require('for_update')
        if plan.for_update and plan.operation != 'select':
            raise UnsupportedFeatureError('FOR UPDATE is only supported for SELECT')
        projections = plan.projections
        if plan.operation != 'select':
            projections = tuple(replace(p, expression=self._returning(p.expression, plan.table.alias))
                                for p in projections)
        limit = plan.limit
        if plan.offset is not None and limit is None:
            limit = 9223372036854775807
        return super().render(replace(plan, projections=projections, for_update=False, limit=limit))

    def compile_sql(self, maintable, columns, distinct='', joins=None, where=None,
                    group_by=None, having=None, order_by=None, limit=None, offset=None,
                    for_update=False, maintable_as='t0'):
        if for_update:
            self._require('for_update')
        if offset is not None and limit is None:
            limit = 9223372036854775807
        return super().compile_sql(maintable, columns, distinct, joins, where, group_by,
                                   having, order_by, limit, offset, False, maintable_as)

    def _returning(self, fragment, alias):
        # Remove only structured references to the DML target alias, never text
        # in literals or parameters. SQLite cannot resolve that alias in RETURNING.
        parts = list(fragment.parts)
        result = []
        index = 0
        while index < len(parts):
            if (parts[index] == Identifier(alias) and index + 1 < len(parts)
                    and parts[index + 1] == '.'):
                index += 2
            else:
                result.append(parts[index])
                index += 1
        return Fragment(tuple(result))
