"""PostgreSQL rendering of already-resolved plans, without rescanning SQL.

No model lookup, connection or driver binding belongs at this boundary.
The tokens service remains for the previous compiler's expression handling.
"""
from __future__ import annotations

import re

from dataclasses import replace
from typing import cast

from ..contracts import ResultColumn, UnsupportedFeatureError
from ..query_plan import (Fragment, Identifier, Parameter, Projection, QueryPlan, SqlStatement,
                          _column_reference, concat, separated)

_DOLLAR = re.compile(r"\$(?:[A-Za-z_][A-Za-z_0-9]*)?\$")

def _tokens(sql: str, *, sqlite=False):
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
        elif sql[i] in "'\"" or sql.startswith('$"', i) or (sqlite and sql[i] in "`["):
            field_reference = sql.startswith('$"', i)
            if field_reference:
                i += 1
            delimiter = ']' if sql[i] == '[' else sql[i]
            # PostgreSQL E'...' supports backslash escapes; ordinary strings do not.
            escaped = not sqlite and delimiter == "'" and i > 0 and sql[i - 1] in 'eE' and (
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

    def aggregate_subquery(self, plan: QueryPlan, mode: str, alias: str) -> Fragment:
        """Legacy subQueryColumn wrapper over an already resolved child SELECT.

        jsonb and XML-as-text preserve DISTINCT support from the corrected
        legacy model. Bindings stay structured until the root driver pass.
        """
        row = Identifier(alias)
        if mode == 'json':
            aggregate = concat('jsonb_agg(row_to_json(', row, '))')
        elif mode == 'xml':
            fields = separated(concat(row, '.', Identifier(cast(str, p.alias)),
                                      ' AS ', Identifier(cast(str, p.alias)))
                               for p in plan.projections)
            aggregate = concat('CAST(xmlagg(xmlelement(name ', row,
                               ', xmlforest(', fields, '))) AS text)')
        else:
            raise UnsupportedFeatureError(f'Unsupported subquery aggregate mode: {mode!r}')
        statement = self.render(plan)
        return concat('(SELECT ', aggregate, ' FROM (', *statement.parts, ') AS ', row, ')')

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

    def tokens(self, expression: str):
        if not isinstance(expression, str):
            raise TypeError('SQL expressions must be strings')
        return _tokens(expression)

    def empty_collection(self, negated: bool) -> str:
        """Operand-free replacement of ``IN`` / ``NOT IN`` for an empty collection."""
        return "<> ALL('{}')" if negated else "= ANY('{}')"

    def concat_non_null(self, expressions: list[str], separator: str) -> str:
        """Legacy reason formulas: skip NULL terms, keep empty strings."""
        literal = "'" + separator.replace("'", "''") + "'"
        return f"array_to_string(ARRAY[{', '.join(expressions)}]::text[], {literal})"

    def _grouping(self, plan: QueryPlan) -> None:
        """Reject the DISTINCT/GROUP BY/HAVING combinations no backend here supports."""
        if type(plan.distinct) is not bool:
            raise ValueError('distinct must be a boolean')
        if plan.operation != 'select' and (plan.distinct or plan.group_by is not None
                                           or plan.having is not None):
            raise UnsupportedFeatureError('DISTINCT, GROUP BY and HAVING apply to SELECT only')
        if plan.having is not None and plan.group_by is None:
            raise UnsupportedFeatureError('having requires group_by')
        if plan.for_update and (plan.distinct or plan.group_by is not None):
            raise UnsupportedFeatureError('for_update is incompatible with distinct or group_by')

    def _count(self, plan: QueryPlan) -> SqlStatement:
        """Count rows directly when every projection is a plain column, else over a subquery."""
        inner = replace(plan, operation='select', order_by=None, for_update=False)
        if not plan.distinct and plan.group_by is None and all(
                _column_reference(projection.expression) for projection in plan.projections):
            column = ResultColumn('count')
            return self.render(replace(inner, projections=(
                Projection(Fragment(('count(*)',)), column.name, column),)))
        column = ResultColumn('count')
        nested = self.render(inner)
        parts = ('SELECT count(*) AS ', self.quote_identifier(column.name), ' FROM (',
                 *nested.parts, ') AS ', self.quote_identifier('count_source'))
        return SqlStatement(parts, plan.params, (column,), self.name, environment=plan.environment)

    def _require(self, capability):
        if capability not in self.capabilities:
            raise UnsupportedFeatureError(f'{self.name}: unsupported capability {capability}')

    def compile_sql(self, maintable, columns, distinct='', joins=None, where=None,
                    group_by=None, having=None, order_by=None, limit=None, offset=None,
                    for_update=False, maintable_as='t0'):
        """Legacy compileSql over strings; separate from the previous plan renderer."""
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

    def _has_expression(self, fragment: Fragment) -> bool:
        # Check the plan's presence of a value, never interpret SQL at rendering.
        return any(not isinstance(part, str) or part.strip() for part in fragment.parts)

    def render(self, plan: QueryPlan) -> SqlStatement:
        if plan.dialect != self.name:
            raise ValueError(f'Cannot render {plan.dialect!r} plan with {self.name}')
        if plan.operation == 'count':
            return self._count(plan)
        operation = plan.operation
        if operation not in {'select', 'insert', 'update', 'delete'}:
            raise UnsupportedFeatureError(f'Unsupported operation: {operation}')
        self._require(operation)
        if type(plan.for_update) is not bool:
            raise ValueError('for_update must be a boolean')
        self._grouping(plan)
        if plan.for_update:
            if operation != 'select':
                raise UnsupportedFeatureError('FOR UPDATE is only supported for SELECT')
            self._require('for_update')
        if plan.where is not None and not self._has_expression(plan.where):
            raise ValueError('WHERE needs a nonempty expression')
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
        aliases = [item.alias for item in plan.projections if item.alias is not None]
        if len(aliases) != len(set(aliases)):
            raise ValueError('Duplicate projection alias')
        for projection in plan.projections:
            if not self._has_expression(projection.expression):
                raise ValueError('Empty projection expression')
            if projection.alias is not None and (
                    projection.column is None or projection.column.name != projection.alias):
                raise ValueError('Projection alias must match result metadata')
        for assignment in plan.assignments:
            if not self._has_expression(assignment.value):
                raise ValueError('Empty assignment expression')
        table = concat(Identifier(plan.table.schema), '.', Identifier(plan.table.name),
                       ' AS ', Identifier(plan.table.alias))
        projections = separated((
            p.expression if p.alias is None
            else concat(p.expression, ' AS ', Identifier(p.alias))
            for p in plan.projections), separator=',\n')
        if operation == 'select':
            # Legacy compileSql joins clauses with newlines unconditionally.
            # Fragment text is preserved; this boundary does not parse SQL.
            statement = concat('SELECT ' + ('DISTINCT ' if plan.distinct else ''),
                               projections, '\n FROM ', table)
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
                statement = concat(statement, '\n LEFT JOIN ', Identifier(join.table.schema), '.',
                                   Identifier(join.table.name), ' AS ', Identifier(join.table.alias),
                                   ' ON ', join.condition)
        elif operation == 'insert':
            statement = concat('INSERT INTO ', table)
            if plan.assignments:
                statement = concat(statement, ' (',
                                   separated(Identifier(a.column) for a in plan.assignments),
                                   ') VALUES (', separated(a.value for a in plan.assignments), ')')
            else:
                self._require('default_values')
                statement = concat(statement, ' DEFAULT VALUES')
        elif operation == 'update':
            statement = concat('UPDATE ', table, ' SET ', separated(
                concat(Identifier(a.column), ' = ', a.value) for a in plan.assignments))
        else:
            statement = concat('DELETE FROM ', table)
        if plan.where is not None:
            statement = concat(statement, '\nWHERE ', plan.where)
        for clause, fragment in [('GROUP BY', plan.group_by), ('HAVING', plan.having)]:
            if fragment is not None:
                if not self._has_expression(fragment):
                    raise ValueError(f'{clause} requires an expression')
                statement = concat(statement, f'\n{clause} ', fragment)
        if plan.order_by is not None:
            if not self._has_expression(plan.order_by):
                raise ValueError('ORDER BY requires an expression')
            statement = concat(statement, '\nORDER BY ', plan.order_by)
        for clause, value in [('limit', plan.limit), ('offset', plan.offset)]:
            if value is not None:
                self._require(clause)
                if isinstance(value, bool) or not isinstance(value, int) or value < 0:
                    raise ValueError(f'{clause.upper()} must be a nonnegative integer')
                statement = concat(statement, f'\n{clause.upper()} {value}')
        if plan.for_update:
            statement = concat(statement, '\nFOR UPDATE OF ', Identifier(plan.table.alias))
        if operation != 'select' and plan.projections:
            self._require('returning_' + operation)
            statement = concat(statement, '\nRETURNING ', projections)
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
        columns = (cast(tuple[ResultColumn, ...], tuple(p.column for p in plan.projections))
                   if all(p.column is not None for p in plan.projections) else ())
        return SqlStatement(tuple(parts), plan.params, columns, self.name,
                            environment=plan.environment)
