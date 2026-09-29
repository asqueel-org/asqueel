"""Resolve the native Genro expression profile into driver-independent query plans.

The data dialect owns SQL tokenization and rendering. Binding formatters own
placeholder syntax and escaping. Authored SQL fragments remain trusted code.
"""
from __future__ import annotations

import re
from collections.abc import Mapping

from .contracts import CompiledQuery, ResolvedModel, ResultColumn, UnsupportedFeatureError
from .dialects.base import DataDialect
from .drivers.base import BindingFormatter
from .model import _unique_target
from .query_plan import (
    Assignment, Identifier, Join, Parameter, Projection, QueryPlan,
    SqlStatement, TableRef, concat, separated,
)

_IDENT = r"[A-Za-z_][A-Za-z_0-9]*"
_PARAM = re.compile(r":" + _IDENT)
_FIELD = re.compile(r"\$(" + _IDENT + r")")
_PATH = re.compile(r"@(" + _IDENT + r"(?:\." + _IDENT + r")+)")


def quote_identifier(name: str) -> str:
    """Legacy convenience: PostgreSQL quoting followed by psycopg escaping.

    New code should use the dialect and formatter boundaries explicitly.
    This result assumes execution with a parameter mapping, even when empty.
    """
    from .dialects.postgres import PostgresDialect
    from .drivers.psycopg import PsycopgDriver

    dialect = PostgresDialect()
    statement = SqlStatement((dialect.quote_identifier(name),), dialect=dialect.name)
    return PsycopgDriver().prepare(statement).sql


def _characters(sql, tokens):
    # Dialects may emit either contiguous code or individual code characters.
    for kind, value in tokens(sql):
        if kind == 'code':
            yield from (('code', char) for char in value)
        else:
            yield kind, value


def _runs(sql, tokens):
    buffer = []
    for kind, value in tokens(sql):
        if kind == 'code':
            buffer.append(value)
        else:
            if buffer:
                yield 'code', ''.join(buffer)
                buffer.clear()
            yield kind, value
    if buffer:
        yield 'code', ''.join(buffer)


def _split(sql: str, tokens) -> list[str]:
    values: list[str] = []
    current: list[str] = []
    depth = 0
    for kind, value in _characters(sql, tokens):
        if kind == 'code':
            if value in '([':
                depth += 1
            elif value in ')]':
                depth -= 1
                if depth < 0:
                    raise ValueError('Unbalanced expression')
            elif value == ',' and depth == 0:
                values.append(''.join(current).strip())
                current.clear()
                continue
        current.append(value)
    if depth:
        raise ValueError('Unbalanced expression')
    values.append(''.join(current).strip())
    if any(not value for value in values):
        raise ValueError('Empty projection or expression')
    return values


def _reference(expression):
    if match := _FIELD.fullmatch(expression):
        return match.group(1)
    if re.fullmatch(r'\$"(?:[^"]|"")+"', expression):
        return expression[2:-1].replace('""', '"')
    return None


def _projection_alias(expression, tokens):
    # Locate AS only outside protected tokens and nested expressions (CAST AS).
    masked = ''.join(value if kind == 'code' else ' ' * len(value)
                     for kind, value in tokens(expression))
    depth = 0
    candidates = []
    for index, char in enumerate(masked):
        if char in '([':
            depth += 1
        elif char in ')]':
            depth -= 1
        elif depth == 0 and re.match(r'(?i)\bAS\s', masked[index:]) and (
                index == 0 or not (masked[index - 1].isalnum() or masked[index - 1] == '_')):
            candidates.append(index)
    if not candidates:
        return expression.strip(), None
    index = candidates[-1]
    alias = expression[index + 2:].strip()
    if re.fullmatch(_IDENT, alias):
        return expression[:index].strip(), alias
    if re.fullmatch(r'"(?:[^"]|"")+"', alias):
        return expression[:index].strip(), alias[1:-1].replace('""', '"')
    raise ValueError('A projection alias must be one SQL identifier')


class _Context:
    def __init__(self, model, table, params, dialect, joins=True):
        self.model, self.table = model, table
        self.dialect = dialect
        self.available = dict(params or {})
        self.params = {}
        self.joins = {}
        self.allow_joins = joins
        self.formulas = set()

    @staticmethod
    def table_ref(table, alias='t0'):
        return TableRef(table.physical_schema, table.physical_name, alias)

    def binding(self, name):
        if name not in self.available:
            raise ValueError(f'Missing query parameter: {name}')
        self.params[name] = self.available[name]
        return Parameter(name)

    def field(self, table, alias, name):
        try:
            column = table.columns[name]
        except KeyError:
            raise ValueError(f'Unknown column {table.key}.{name}') from None
        if column.formula is None:
            return concat(Identifier(alias), '.', Identifier(column.physical_name))
        key = (table.key, name)
        if key in self.formulas:
            raise ValueError(f'Cyclic formula: {table.key}.{name}')
        self.formulas.add(key)
        try:
            return concat('(', self.expression(column.formula, table, alias), ')')
        finally:
            self.formulas.remove(key)

    def related(self, path, table, alias):
        if not self.allow_joins:
            raise UnsupportedFeatureError('Relation paths are not supported in native DML')
        parts = path.split('.')
        for name in parts[:-1]:
            try:
                relation = table.relations[name]
            except KeyError:
                raise ValueError(f'Unknown relation {table.key}.{name}') from None
            target = self.model.table(relation.target)
            key = (alias, name)
            if key not in self.joins:
                target_alias = f't{len(self.joins) + 1}'
                if not relation.columns or len(relation.columns) != len(relation.target_columns):
                    raise ValueError(f'Invalid join columns for {table.key}.{name}')
                if any(column not in table.columns for column in relation.columns) or any(
                        column not in target.columns for column in relation.target_columns):
                    raise ValueError(f'Unknown join columns for {table.key}.{name}')
                if not _unique_target(target, relation.target_columns):
                    raise UnsupportedFeatureError(f'{table.key}.{name}: target must have a unique key')
                terms = []
                for source, dest in zip(relation.columns, relation.target_columns):
                    if table.columns[source].formula or target.columns[dest].formula:
                        raise UnsupportedFeatureError('Formula join keys are outside native V1')
                    terms.append(concat(self.field(table, alias, source), ' = ',
                                        self.field(target, target_alias, dest)))
                self.joins[key] = Join(self.table_ref(target, target_alias),
                                       separated(terms, ' AND '))
            alias = self.joins[key].table.alias
            table = target
        return self.field(table, alias, parts[-1]), table, parts[-1]

    def expression(self, expression, table=None, alias='t0'):
        if not isinstance(expression, str) or not expression.strip():
            raise ValueError('Expected nonempty SQL expression')
        table = table or self.table
        result = []
        for kind, code in _runs(expression, self.dialect.tokens):
            if kind == 'field':
                result.append(self.field(table, alias, code[2:-1].replace('""', '"')))
                continue
            if kind != 'code':
                result.append(code)
                if kind == 'line_comment' and not code.endswith('\n'):
                    result.append('\n')
                continue
            if re.search(r'(?i)\baggregateRows\b', code):
                raise UnsupportedFeatureError('aggregateRows has been removed; use explicit SQL aggregates')
            i = 0
            while i < len(code):
                if match := _PARAM.match(code, i):
                    result.append(self.binding(match.group()[1:]))
                    i = match.end()
                elif match := _FIELD.match(code, i):
                    result.append(self.field(table, alias, match.group(1)))
                    i = match.end()
                elif match := _PATH.match(code, i):
                    result.append(self.related(match.group(1), table, alias)[0])
                    i = match.end()
                elif code[i] == ';':
                    raise UnsupportedFeatureError('Statement separators are not SQL expressions')
                elif code[i] in '$@' or (code[i] == '#' and re.match(r'#[A-Za-z_]', code[i:])):
                    raise UnsupportedFeatureError('Unsupported Genro expression syntax')
                else:
                    result.append(code[i])
                    i += 1
        return concat(*result)

    def projection(self, columns):
        if columns is None:
            return ()
        if isinstance(columns, str):
            expressions = _split(columns, self.dialect.tokens)
        else:
            expressions = list(columns)
        expanded = []
        for expression in expressions:
            if expression.strip() == '*':
                expanded.extend('$"' + name.replace('"', '""') + '"' for name in self.table.columns)
            else:
                expanded.append(expression)
        if not expanded:
            raise ValueError('At least one result column is required')
        projections, names = [], set()
        for expression in expanded:
            value, name = _projection_alias(expression, self.dialect.tokens)
            source = column = None
            if (field_name := _reference(value)) is not None:
                column = self.table.columns.get(field_name)
                if column is not None:
                    source = column.identity or self.table.key + '.' + column.name
                name = name or field_name
            elif match := _PATH.fullmatch(value):
                _, owner, field = self.related(match.group(1), self.table, 't0')
                column = owner.columns[field]
                source = column.identity or owner.key + '.' + column.name
                name = name or match.group(1).replace('.', '_')
            if name is None:
                raise ValueError('Computed SQL expressions require an explicit AS alias')
            if name in names:
                raise ValueError(f'Duplicate result alias: {name}')
            names.add(name)
            metadata = ResultColumn(name, column.dtype if column else None,
                                    source, column.ui if column else {})
            projections.append(Projection(self.expression(value), name, metadata))
        return tuple(projections)


class QueryCompiler:
    """Resolve Genro syntax, then delegate SQL and binding to explicit adapters."""

    def __init__(self, model: ResolvedModel, dialect: DataDialect, formatter: BindingFormatter):
        if dialect.name != formatter.dialect:
            raise ValueError('The data dialect and binding formatter are incompatible')
        self.model = model
        self.dialect = dialect
        self.formatter = formatter

    def compile_plan(self, plan: QueryPlan) -> CompiledQuery:
        """Ask the configured dialect to render and formatter to prepare bindings."""
        if plan.dialect != self.dialect.name:
            raise ValueError('Query plan belongs to a different data dialect')
        return self.formatter.prepare(self.dialect.render(plan))

    def _context(self, table, params=None, joins=True):
        return _Context(self.model, self.model.table(table), params, self.dialect, joins=joins)

    def plan_select(self, table, columns='*', where=None, params=None, order_by=None,
                    limit=None, offset=None, **options) -> QueryPlan:
        """Resolve a select without rendering SQL or formatting parameters."""
        if options:
            if 'aggregateRows' in options:
                raise UnsupportedFeatureError('aggregateRows has been removed; use explicit SQL aggregates')
            raise UnsupportedFeatureError(f'Unsupported query options: {sorted(options)}')
        context = self._context(table, params)
        projections = context.projection(columns)
        if not projections:
            raise ValueError('SELECT needs result columns')
        predicate = context.expression(where) if where is not None else None
        ordering = context.expression(order_by) if order_by is not None else None
        for clause, value in [('LIMIT', limit), ('OFFSET', offset)]:
            if value is not None:
                if isinstance(value, bool) or not isinstance(value, int) or value < 0:
                    raise ValueError(f'{clause} must be a nonnegative integer')
        return QueryPlan('select', context.table_ref(context.table), projections,
                         tuple(context.joins.values()), predicate, ordering, limit, offset,
                         params=context.params, dialect=self.dialect.name)

    def select(self, table, columns='*', where=None, params=None, order_by=None,
               limit=None, offset=None, **options):
        return self.compile_plan(self.plan_select(table, columns, where, params, order_by,
                                                  limit, offset, **options))

    def _values(self, context, values):
        if not isinstance(values, Mapping):
            raise TypeError('DML values must be a mapping of logical column names')
        assignments = []
        for index, (name, value) in enumerate(values.items()):
            column = context.table.columns.get(name)
            if column is None:
                raise ValueError(f'Unknown column {context.table.key}.{name}')
            if column.formula is not None:
                raise ValueError(f'Cannot write formula column {name}')
            parameter = f'__value_{index}'
            while parameter in context.available:
                parameter = '_' + parameter
            context.available[parameter] = value
            assignments.append(Assignment(column.physical_name, concat(context.binding(parameter))))
        return tuple(assignments)

    @staticmethod
    def _where(context, where):
        if not isinstance(where, str) or not where.strip():
            raise ValueError("UPDATE/DELETE require a predicate; use where='TRUE' explicitly for all rows")
        if not any(kind not in {'comment', 'line_comment'} and value.strip()
                   for kind, value in _runs(where, context.dialect.tokens)):
            raise ValueError('A comment is not a write predicate')
        return context.expression(where)

    def plan_insert(self, table, values, returning='*') -> QueryPlan:
        """Resolve insert assignments and returning metadata into a plan."""
        context = self._context(table, joins=False)
        assignments = self._values(context, values)
        projections = context.projection(returning)
        return QueryPlan('insert', context.table_ref(context.table), projections,
                         assignments=assignments, params=context.params, dialect=self.dialect.name)

    def insert(self, table, values, returning='*'):
        return self.compile_plan(self.plan_insert(table, values, returning))

    def plan_update(self, table, values, where, params=None, returning='*') -> QueryPlan:
        """Resolve a guarded update without executing or rendering SQL."""
        context = self._context(table, params, joins=False)
        assignments = self._values(context, values)
        if not assignments:
            raise ValueError('UPDATE requires at least one value')
        predicate = self._where(context, where)
        projections = context.projection(returning)
        return QueryPlan('update', context.table_ref(context.table), projections,
                         where=predicate, assignments=assignments, params=context.params,
                         dialect=self.dialect.name)

    def update(self, table, values, where, params=None, returning='*'):
        return self.compile_plan(self.plan_update(table, values, where, params, returning))

    def plan_delete(self, table, where, params=None, returning='*') -> QueryPlan:
        """Resolve a guarded delete without executing or rendering SQL."""
        context = self._context(table, params, joins=False)
        predicate = self._where(context, where)
        projections = context.projection(returning)
        return QueryPlan('delete', context.table_ref(context.table), projections,
                         where=predicate, params=context.params, dialect=self.dialect.name)

    def delete(self, table, where, params=None, returning='*'):
        return self.compile_plan(self.plan_delete(table, where, params, returning))


class PostgresCompiler(QueryCompiler):
    """Compatible convenience facade selecting PostgreSQL and psycopg adapters."""

    def __init__(self, model: ResolvedModel):
        from .dialects.postgres import PostgresDialect
        from .drivers.psycopg import PsycopgDriver

        super().__init__(model, PostgresDialect(), PsycopgDriver())
