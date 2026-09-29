"""PostgreSQL expression scanning and rendering of already-resolved plans.

No model lookup, connection or driver binding belongs at this boundary.
"""
from __future__ import annotations

import re

from ..contracts import UnsupportedFeatureError
from ..query_plan import Fragment, Identifier, Parameter, QueryPlan, SqlStatement, concat, separated

_DOLLAR = re.compile(r"\$(?:[A-Za-z_][A-Za-z_0-9]*)?\$")

def _tokens(sql: str):
    """Yield (kind, text), preserving SQL strings, identifiers and comments."""
    i = 0
    while i < len(sql):
        start = i
        if sql.startswith('--', i):
            end = sql.find('\n', i)
            i = len(sql) if end < 0 else end + 1
            yield 'line_comment', sql[start:i]
        elif sql.startswith('/*', i):
            depth = 1
            i += 2
            while i < len(sql) and depth:
                if sql.startswith('/*', i):
                    depth += 1
                    i += 2
                elif sql.startswith('*/', i):
                    depth -= 1
                    i += 2
                else:
                    i += 1
            if depth:
                raise ValueError('Unclosed SQL comment')
            yield 'comment', sql[start:i]
        elif sql[i] in "'\"" or sql.startswith('$"', i):
            field_reference = sql.startswith('$"', i)
            if field_reference:
                i += 1
            delimiter = sql[i]
            # PostgreSQL E'...' supports backslash escapes; ordinary strings do not.
            escaped = delimiter == "'" and i > 0 and sql[i - 1] in 'eE' and (
                i < 2 or not (sql[i - 2].isalnum() or sql[i - 2] == '_'))
            i += 1
            closed = False
            while i < len(sql):
                if escaped and sql[i] == '\\':
                    i += 2
                elif sql[i] == delimiter:
                    i += 1
                    if i < len(sql) and sql[i] == delimiter:
                        i += 1
                    else:
                        closed = True
                        break
                else:
                    i += 1
            if not closed:
                raise ValueError('Unclosed SQL quoted token')
            kind = 'field' if field_reference else ('identifier' if delimiter == '"' else 'string')
            yield kind, sql[start:i]
        elif match := _DOLLAR.match(sql, i):
            end = sql.find(match.group(), match.end())
            if end < 0:
                raise ValueError('Unclosed SQL dollar quote')
            i = end + len(match.group())
            yield 'string', sql[start:i]
        elif sql.startswith('::', i):
            i += 2
            yield 'operator', sql[start:i]
        else:
            # Keep code characters individually: scanners can match a contiguous
            # code run without mistaking protected delimiters for expression syntax.
            i += 1
            yield 'code', sql[start:i]



class PostgresDialect:
    """The native PostgreSQL data dialect, independent of any Python driver."""

    name = 'postgresql'
    capabilities = frozenset({
        'select', 'insert', 'update', 'delete', 'returning_insert',
        'returning_update', 'returning_delete', 'left_join', 'limit', 'offset',
        'default_values',
    })

    def __init__(self, *, capabilities: frozenset[str] | None = None):
        if capabilities is not None:
            unknown = set(capabilities) - type(self).capabilities
            if unknown:
                raise ValueError(f'Unknown PostgreSQL capabilities: {sorted(unknown)}')
            self.capabilities = frozenset(capabilities)

    def quote_identifier(self, name: str) -> str:
        if not isinstance(name, str) or not name or '\x00' in name:
            raise ValueError('SQL identifiers must be nonempty strings without NUL')
        if len(name.encode('utf-8')) > 63:
            raise ValueError('PostgreSQL identifiers must not exceed 63 UTF-8 bytes')
        return '"' + name.replace('"', '""') + '"'

    def tokens(self, expression: str):
        if not isinstance(expression, str):
            raise TypeError('SQL expressions must be strings')
        return _tokens(expression)

    def _require(self, capability):
        if capability not in self.capabilities:
            raise UnsupportedFeatureError(f'{self.name}: unsupported capability {capability}')

    def _has_expression(self, fragment: Fragment) -> bool:
        # Mask structural nodes rather than interpreting model references here.
        text = ''.join(part if isinstance(part, str) else 'x' for part in fragment.parts)
        return any(kind not in {'comment', 'line_comment'} and value.strip() for kind, value in self.tokens(text))

    def _fragment(self, fragment: Fragment) -> Fragment:
        """Terminate trailing line comments before adding structural SQL.

        Scan the entire fragment, not individual string parts: lexical tokens
        can span parts, while identifiers/parameters stay structured in output.
        """
        text = ''.join(part if isinstance(part, str)
                       else self.quote_identifier(part.name) if isinstance(part, Identifier)
                       else '0' for part in fragment.parts)
        tokens = list(self.tokens(text))
        if tokens and tokens[-1][0] == 'line_comment' and not tokens[-1][1].endswith('\n'):
            return concat(fragment, '\n')
        return fragment

    def render(self, plan: QueryPlan) -> SqlStatement:
        if plan.dialect != self.name:
            raise ValueError(f'Cannot render {plan.dialect!r} plan with {self.name}')
        operation = plan.operation
        if operation not in {'select', 'insert', 'update', 'delete'}:
            raise UnsupportedFeatureError(f'Unsupported operation: {operation}')
        self._require(operation)
        if plan.where is not None and not self._has_expression(plan.where):
            raise ValueError('WHERE needs an expression, not whitespace or comments')
        if operation in {'update', 'delete'} and plan.where is None:
            raise ValueError('UPDATE/DELETE require an explicit predicate')
        if operation in {'select', 'delete'} and plan.assignments:
            raise ValueError(f'{operation.upper()} cannot have assignments')
        if operation == 'insert' and plan.where is not None:
            raise ValueError('INSERT cannot have a WHERE clause in this profile')
        if operation != 'select' and (plan.joins or plan.order_by is not None
                                      or plan.limit is not None or plan.offset is not None):
            raise UnsupportedFeatureError('DML joins, ordering and pagination are outside this profile')
        if operation == 'select' and not plan.projections:
            raise ValueError('SELECT needs result columns')
        if operation == 'update' and not plan.assignments:
            raise ValueError('UPDATE requires at least one assignment')
        names = [item.column for item in plan.assignments]
        if len(names) != len(set(names)):
            raise ValueError('Duplicate assignment column')
        aliases = [item.alias for item in plan.projections]
        if len(aliases) != len(set(aliases)):
            raise ValueError('Duplicate projection alias')
        for projection in plan.projections:
            if not self._has_expression(projection.expression):
                raise ValueError('Empty projection expression')
            if projection.column.name != projection.alias:
                raise ValueError('Projection alias must match result metadata')
        for assignment in plan.assignments:
            if not self._has_expression(assignment.value):
                raise ValueError('Empty assignment expression')
        table = concat(Identifier(plan.table.schema), '.', Identifier(plan.table.name),
                       ' AS ', Identifier(plan.table.alias))
        projections = separated(concat(self._fragment(p.expression), ' AS ', Identifier(p.alias))
                                for p in plan.projections)
        if operation == 'select':
            statement = concat('SELECT ', projections, ' FROM ', table)
            joined_aliases = {plan.table.alias}
            for join in plan.joins:
                if join.kind != 'left':
                    raise UnsupportedFeatureError(f'Unsupported join kind: {join.kind}')
                self._require('left_join')
                if join.table.alias in joined_aliases:
                    raise ValueError('Duplicate table alias')
                joined_aliases.add(join.table.alias)
                if not self._has_expression(join.condition):
                    raise ValueError('JOIN requires a condition')
                statement = concat(statement, ' LEFT JOIN ', Identifier(join.table.schema), '.',
                                   Identifier(join.table.name), ' AS ', Identifier(join.table.alias),
                                   ' ON ', self._fragment(join.condition))
        elif operation == 'insert':
            statement = concat('INSERT INTO ', table)
            if plan.assignments:
                statement = concat(statement, ' (',
                                   separated(Identifier(a.column) for a in plan.assignments),
                                   ') VALUES (', separated(self._fragment(a.value) for a in plan.assignments), ')')
            else:
                self._require('default_values')
                statement = concat(statement, ' DEFAULT VALUES')
        elif operation == 'update':
            statement = concat('UPDATE ', table, ' SET ', separated(
                concat(Identifier(a.column), ' = ', self._fragment(a.value)) for a in plan.assignments))
        else:
            statement = concat('DELETE FROM ', table)
        if plan.where is not None:
            statement = concat(statement, ' WHERE ', self._fragment(plan.where))
        if plan.order_by is not None:
            if not self._has_expression(plan.order_by):
                raise ValueError('ORDER BY requires an expression')
            statement = concat(statement, ' ORDER BY ', self._fragment(plan.order_by))
        for clause, value in [('limit', plan.limit), ('offset', plan.offset)]:
            if value is not None:
                self._require(clause)
                if isinstance(value, bool) or not isinstance(value, int) or value < 0:
                    raise ValueError(f'{clause.upper()} must be a nonnegative integer')
                statement = concat(statement, f' {clause.upper()} {value}')
        if operation != 'select' and plan.projections:
            self._require('returning_' + operation)
            statement = concat(statement, ' RETURNING ', projections)
        parts: list[str | Parameter] = []
        for part in statement.parts:
            if isinstance(part, Identifier):
                parts.append(self.quote_identifier(part.name))
            elif isinstance(part, Parameter):
                if not isinstance(part.name, str) or not part.name:
                    raise ValueError('Parameter names must be nonempty strings')
                if part.name not in plan.params:
                    raise ValueError(f'Missing query parameter: {part.name}')
                parts.append(part)
            elif isinstance(part, str):
                parts.append(part)
            else:
                raise TypeError(f'Invalid SQL fragment part: {type(part).__name__}')
        return SqlStatement(tuple(parts), plan.params,
                            tuple(p.column for p in plan.projections), self.name)
