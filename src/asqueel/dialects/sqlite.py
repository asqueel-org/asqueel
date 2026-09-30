"""SQLite rendering with attached schemas and connection-level write locking."""
from dataclasses import replace

from .postgres import PostgresDialect, _tokens
from ..contracts import UnsupportedFeatureError
from ..query_plan import Fragment, Identifier


class SqliteDialect(PostgresDialect):
    """Common SELECT/DML syntax; SQLite-specific RETURNING and pagination."""

    name = 'sqlite'

    def tokens(self, expression):
        if not isinstance(expression, str):
            raise TypeError('SQL expressions must be strings')
        return _tokens(expression, sqlite=True)

    def quote_identifier(self, name):
        if not isinstance(name, str) or not name or '\x00' in name:
            raise ValueError('SQL identifiers must be nonempty strings without NUL')
        return '"' + name.replace('"', '""') + '"'

    def render(self, plan):
        # SQLite has no FOR UPDATE. The driver begins an IMMEDIATE transaction
        # before any statement, covering the read/modify/write cycle in hooks.
        if type(plan.for_update) is not bool:
            raise ValueError('for_update must be a boolean')
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
