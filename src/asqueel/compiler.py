"""Resolve the native Genro expression profile into driver-independent query plans.

The data dialect owns SQL tokenization and rendering. Binding formatters own
placeholder syntax and escaping. Authored SQL fragments remain trusted code.
"""
from __future__ import annotations

import re
from collections.abc import Collection, Mapping
from dataclasses import replace

from .contracts import (CompiledQuery, EnvironmentBinding, ResolvedModel, ResultColumn,
                        UnsupportedFeatureError)
from .environment import SqlEnvironment
from .dialects.base import DataDialect
from .drivers.base import BindingFormatter
from .model import _resolve_aliases, _unique_target, validate_row_policies
from .query_plan import (
    Assignment, Identifier, Join, Parameter, Projection, QueryPlan,
    SqlStatement, TableRef, concat, separated,
)

_IDENT = r"[A-Za-z_][A-Za-z_0-9]*"
_PARAM = re.compile(r":" + _IDENT)
_FIELD = re.compile(r"\$(" + _IDENT + r")")
_PATH = re.compile(r"@(" + _IDENT + r"(?:\.@?" + _IDENT + r")*\." + _IDENT + r")")
_THIS = re.compile(r"#THIS\.(@?" + _IDENT + r"(?:\.@?" + _IDENT + r")*)")
_MACRO = re.compile(r"#(" + _IDENT + r")")


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
    def __init__(self, model, table, params, dialect, snapshot, joins=True,
                 *, parent=None, outer=None, namespace=''):
        self.model, self.table = model, table
        self.dialect = dialect
        self.snapshot = snapshot
        self.environment_keys = parent.environment_keys if parent else set()
        self.policy_parameter_index = 0
        self.available = dict(params or {})
        self.params = parent.params if parent else {}
        self.joins = {}
        self.allow_joins = joins
        self.formulas = parent.formulas if parent else set()
        self.state = parent.state if parent else {'counter': 0, 'names': set(self.available)}
        self.state['names'].update(self.available)
        self.binding_names = {}
        self.namespace = namespace
        self.basealias = namespace + 't0'
        self.outer = outer
        self.input_origins = set(parent.input_origins) if parent else set(self.available)
        self.consumed_inputs = parent.consumed_inputs if parent else set()

    @staticmethod
    def table_ref(table, alias='t0'):
        return TableRef(table.physical_schema, table.physical_name, alias)

    def binding(self, name):
        if name in self.input_origins:
            self.consumed_inputs.add(name)
        if name not in self.available:
            if name.startswith('env_'):
                key = name[4:]
                self.environment_keys.add(key)
                if key in self.snapshot:
                    self.available[name] = self.snapshot[key]
            if name not in self.available:
                raise ValueError(f'Missing query parameter: {name}')
        if name not in self.binding_names:
            bound_name = self.namespace + name
            if self.namespace:
                while bound_name in self.state['names']:
                    bound_name = '_' + bound_name
            self.state['names'].add(bound_name)
            self.binding_names[name] = bound_name
        bound_name = self.binding_names[name]
        self.params[bound_name] = self.available[name]
        return Parameter(bound_name)

    def environment_binding(self):
        if not self.environment_keys:
            return None
        keys = tuple(sorted(self.environment_keys))
        return EnvironmentBinding(keys, {k: self.snapshot[k] for k in keys if k in self.snapshot})

    def policy_binding(self, value):
        name = f'__policy_{self.policy_parameter_index}'
        self.policy_parameter_index += 1
        while name in self.available:
            name = '_' + name
        self.available[name] = value
        return self.binding(name)

    def policy_field(self, field, *, write=False):
        if field.startswith('@'):
            if write:
                raise UnsupportedFeatureError('Relational partition writes require ignore_partition=True in this profile')
            match = _PATH.fullmatch(field)
            if match is None:
                raise ValueError(f'Invalid partition relation path: {field}')
            expression, owner, name = self.related(match.group(1), self.table, self.basealias)
        else:
            name = _reference(field) if field.startswith('$') else field
            owner = self.table
            expression = self.field(owner, self.basealias, name)
        if owner.columns[name].is_virtual:
            raise UnsupportedFeatureError('Row policies require physical columns')
        return expression, name

    @staticmethod
    def scalar(value):
        if isinstance(value, Collection) and not isinstance(value, (str, bytes)):
            raise ValueError('Partition values must be scalars, not nested collections')
        if isinstance(value, Mapping):
            raise ValueError('Partition values must be scalars, not mappings')
        return value

    def scope_values(self, scope):
        keys = [scope.current] + ([scope.allowed] if scope.allowed is not None else [])
        self.environment_keys.update(keys)
        has_current = scope.current in self.snapshot
        has_allowed = scope.allowed is not None and scope.allowed in self.snapshot
        if not has_current and not has_allowed:
            raise ValueError(f'Missing partition context for {scope.field}')
        current = self.scalar(self.snapshot[scope.current]) if has_current else None
        allowed = None
        if has_allowed:
            value = self.snapshot[scope.allowed]
            if not isinstance(value, Collection) or isinstance(value, (str, bytes, Mapping)):
                raise ValueError(f'Allowed partition values for {scope.field} must be a collection')
            allowed = tuple(self.scalar(v) for v in value)
        return has_current, current, allowed

    def partition_predicates(self, ignore_partition=False, *, write=False):
        if type(ignore_partition) is not bool:
            raise ValueError('ignore_partition must be boolean')
        if ignore_partition:
            return []
        conditions = []
        for scope in self.table.policies.partitions:
            field, _ = self.policy_field(scope.field, write=write)
            has_current, current, allowed = self.scope_values(scope)
            if has_current:
                conditions.append(concat(field, ' IS NULL') if current is None else
                                  concat(field, ' = ', self.policy_binding(current)))
            if allowed is not None:
                if not allowed:
                    conditions.append(concat('FALSE'))
                    continue
                terms = []
                nonnull = [v for v in allowed if v is not None]
                if nonnull:
                    terms.append(concat(field, ' IN (', separated(self.policy_binding(v) for v in nonnull), ')'))
                if scope.include_null or None in allowed:
                    terms.append(concat(field, ' IS NULL'))
                conditions.append(concat('(', separated(terms, ' OR '), ')'))
        return conditions

    @staticmethod
    def combine_where(predicate, conditions):
        if not conditions:
            return predicate
        fragments = ([predicate] if predicate is not None else []) + conditions
        return separated((concat('(', fragment, ')') for fragment in fragments), ' AND ')

    def guard_values(self, values, *, insert=False, ignore_partition=False):
        if not isinstance(values, Mapping):
            raise TypeError('DML values must be a mapping of logical column names')
        values = dict(values)
        if type(ignore_partition) is not bool:
            raise ValueError('ignore_partition must be boolean')
        if ignore_partition:
            return values
        for scope in self.table.policies.partitions:
            _, name = self.policy_field(scope.field, write=True)
            has_current, current, allowed = self.scope_values(scope)
            if name not in values:
                if not insert:
                    continue
                if not has_current:
                    raise ValueError(f'INSERT requires partition value {name} without a current value')
                values[name] = current
            value = self.scalar(values[name])
            current_ok = not has_current or value == current
            allowed_ok = (allowed is None or bool(allowed) and (
                value in allowed or value is None and scope.include_null))
            if not current_ok or not allowed_ok:
                raise ValueError(f'Value for partition {scope.field} is outside the active scope')
        return values

    def select_policies(self, projections, predicate, *, exclude_draft,
                        exclude_logical_deleted, ignore_partition):
        if type(exclude_draft) is not bool:
            raise ValueError('exclude_draft must be boolean')
        if exclude_logical_deleted is not True and exclude_logical_deleted is not False and exclude_logical_deleted != 'mark':
            raise ValueError('exclude_logical_deleted must be True, False or mark')
        conditions = self.partition_predicates(ignore_partition)
        policy = self.table.policies
        if policy.draft_field and exclude_draft:
            field, _ = self.policy_field(policy.draft_field)
            conditions.append(concat(field, ' IS NOT TRUE'))
        if policy.logical_deletion_field:
            field, name = self.policy_field(policy.logical_deletion_field)
            if exclude_logical_deleted is True:
                conditions.append(concat(field, ' IS NULL'))
            elif exclude_logical_deleted == 'mark':
                if any(p.alias == '_isdeleted' for p in projections):
                    raise ValueError('The _isdeleted result alias is reserved in mark mode')
                for projection in projections:
                    parts = projection.expression.parts
                    if not (len(parts) == 3 and isinstance(parts[0], Identifier)
                            and parts[1] == '.' and isinstance(parts[2], Identifier)):
                        raise UnsupportedFeatureError('mark requires physical column projections; opaque expressions/formulas are unsupported')
                column = self.table.columns[name]
                metadata = ResultColumn('_isdeleted', column.dtype,
                                        column.identity or self.table.key + '.' + name, column.ui)
                projections += (Projection(field, '_isdeleted', metadata),)
        return projections, self.combine_where(predicate, conditions)

    def subquery(self, definition, owner, outer_alias, *, exists=False):
        if not self.allow_joins:
            raise UnsupportedFeatureError('Subquery columns are not supported in native DML')
        if not isinstance(definition, Mapping):
            raise ValueError('A subquery must be a mapping')
        options = dict(definition)
        for old, new in [('excludeDraft', 'exclude_draft'),
                         ('excludeLogicalDeleted', 'exclude_logical_deleted'),
                         ('ignorePartition', 'ignore_partition')]:
            if old in options:
                if new in options:
                    raise ValueError(f'Conflicting subquery options: {old}, {new}')
                options[new] = options.pop(old)
        for name, value in [('subtable', '*'), ('addPkeyColumn', False),
                            ('ignoreTableOrderBy', True)]:
            if name in options:
                actual = options.pop(name)
                if type(actual) is not type(value) or actual != value:
                    raise UnsupportedFeatureError(f'Unsupported subquery option: {name}={actual!r}')
        known = {'table', 'columns', 'where', 'params', 'sqlparams', 'order_by',
                 'limit', 'offset', 'exclude_draft', 'exclude_logical_deleted',
                 'ignore_partition', 'cast'}
        if options.keys() - known:
            raise UnsupportedFeatureError(f'Unsupported subquery options: {sorted(options.keys() - known)}')
        if exists and 'cast' in options:
            raise UnsupportedFeatureError('Cast applies to scalar subqueries, not EXISTS')
        if not isinstance(options.get('table'), str) or not options['table']:
            raise ValueError('A subquery requires a table')
        if not isinstance(options.get('where'), str) or not options['where'].strip():
            raise ValueError('A subquery requires an explicit WHERE expression')
        available = dict(self.available)
        local = {}
        for name in ('params', 'sqlparams'):
            values = options.get(name)
            if values is not None:
                if not isinstance(values, Mapping):
                    raise ValueError(f'Subquery {name} must be a mapping')
                if local.keys() & values.keys():
                    raise ValueError('Duplicate subquery parameter declarations')
                local.update(values)
        available.update(local)
        self.state['counter'] += 1
        namespace = f's{self.state["counter"]}_'
        child = _Context(self.model, self.model.table(options['table']), available,
                         self.dialect, self.snapshot, parent=self,
                         outer=(self, owner, outer_alias), namespace=namespace)
        child.input_origins.difference_update(local)
        columns = options.get('columns', '1 AS __exists' if exists else '*')
        expressions = _split(columns, self.dialect.tokens) if isinstance(columns, str) else list(columns)
        # Subquery expressions need no public output alias. Give opaque scalar
        # expressions a deterministic internal one while preserving field metadata.
        normalized = []
        for index, expression in enumerate(expressions):
            value, output_name = _projection_alias(expression, self.dialect.tokens)
            if (output_name is None and value != '*' and _reference(value) is None
                    and _PATH.fullmatch(value) is None):
                expression = value + f' AS __value_{index}'
            normalized.append(expression)
        projections = child.projection(normalized)
        if not exists and len(projections) != 1:
            raise ValueError('A scalar subquery requires exactly one result column')
        predicate = child.expression(options['where'])
        ordering = child.expression(options['order_by']) if options.get('order_by') is not None else None
        projections, predicate = child.select_policies(
            projections, predicate, exclude_draft=options.get('exclude_draft', False),
            exclude_logical_deleted=options.get('exclude_logical_deleted', False),
            ignore_partition=options.get('ignore_partition', False))
        if not exists and len(projections) != 1:
            raise ValueError('A scalar subquery requires exactly one result column')
        plan = QueryPlan('select', child.table_ref(child.table, child.basealias), projections,
                         tuple(child.joins.values()), predicate, ordering,
                         options.get('limit'), options.get('offset'), params=child.params,
                         dialect=self.dialect.name, environment=child.environment_binding())
        statement = self.dialect.render(plan)
        result = concat('(', *statement.parts, ')')
        if 'cast' in options:
            cast = options['cast']
            # Type names are authored SQL but not arbitrary statement fragments.
            if (not isinstance(cast, str) or not re.fullmatch(
                    r'[A-Za-z_][A-Za-z_0-9]*(?:\.[A-Za-z_][A-Za-z_0-9]*)?'
                    r'(?:\s+[A-Za-z_][A-Za-z_0-9]*)*(?:\(\s*\d+(?:\s*,\s*\d+)?\s*\))?(?:\[\])*', cast)):
                raise ValueError('Unsupported subquery cast type')
            result = concat('CAST(', result, ' AS ', cast, ')')
        return result

    def field(self, table, alias, name):
        try:
            column = table.columns[name]
        except KeyError:
            raise ValueError(f'Unknown column {table.key}.{name}') from None
        if sum(value is not None for value in
               (column.formula, column.relation_path, column.select, column.exists)) > 1:
            raise ValueError(f'Column has conflicting virtual definitions: {table.key}.{name}')
        if column.subqueries and column.formula is None:
            raise ValueError(f'Named subqueries require a formula: {table.key}.{name}')
        if not column.is_virtual:
            return concat(Identifier(alias), '.', Identifier(column.physical_name))
        key = (table.key, name)
        if key in self.formulas:
            raise ValueError(f'Cyclic formula/alias: {table.key}.{name}')
        self.formulas.add(key)
        try:
            if column.relation_path is not None:
                path = column.relation_path
                if match := _PATH.fullmatch(path):
                    return self.related(match.group(1), table, alias)[0]
                name = _reference(path) if path.startswith('$') else path
                if name not in table.columns:
                    raise ValueError(f'Invalid alias relation path: {path}')
                return self.field(table, alias, name)
            if column.select is not None or column.exists is not None:
                is_exists = column.exists is not None
                query = self.subquery(column.exists if is_exists else column.select, table, alias,
                                      exists=is_exists)
                return concat('EXISTS ' if is_exists else '', query)
            return concat('(', self.expression(column.formula, table, alias,
                                               subqueries=column.subqueries,
                                               this_owner=(self, table, alias)), ')')
        finally:
            self.formulas.remove(key)

    def related(self, path, table, alias):
        if not self.allow_joins:
            raise UnsupportedFeatureError('Relation paths are not supported in native DML')
        parts = path.replace('@', '').split('.')
        for name in parts[:-1]:
            try:
                relation = table.relations[name]
            except KeyError:
                raise ValueError(f'Unknown relation {table.key}.{name}') from None
            target = self.model.table(relation.target)
            key = (alias, name)
            if key not in self.joins:
                target_alias = f'{self.namespace}t{len(self.joins) + 1}'
                if not relation.columns or len(relation.columns) != len(relation.target_columns):
                    raise ValueError(f'Invalid join columns for {table.key}.{name}')
                if any(column not in table.columns for column in relation.columns) or any(
                        column not in target.columns for column in relation.target_columns):
                    raise ValueError(f'Unknown join columns for {table.key}.{name}')
                if not _unique_target(target, relation.target_columns):
                    raise UnsupportedFeatureError(f'{table.key}.{name}: target must have a unique key')
                terms = []
                for source, dest in zip(relation.columns, relation.target_columns):
                    if table.columns[source].is_virtual or target.columns[dest].is_virtual:
                        raise UnsupportedFeatureError('Virtual join keys are outside native V1')
                    terms.append(concat(self.field(table, alias, source), ' = ',
                                        self.field(target, target_alias, dest)))
                self.joins[key] = Join(self.table_ref(target, target_alias),
                                       separated(terms, ' AND '))
            alias = self.joins[key].table.alias
            table = target
        return self.field(table, alias, parts[-1]), table, parts[-1]

    def expression(self, expression, table=None, alias=None, *, subqueries=None,
                   this_owner=None):
        if not isinstance(expression, str) or not expression.strip():
            raise ValueError('Expected nonempty SQL expression')
        table = table or self.table
        alias = alias or self.basealias
        result = []
        used_subqueries = set()
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
                if match := _THIS.match(code, i):
                    owner_context = this_owner or self.outer
                    if owner_context is None:
                        raise UnsupportedFeatureError('#THIS requires a correlated subquery')
                    context, owner, outer_alias = owner_context
                    path = match.group(1)
                    result.append(context.related(path.lstrip('@'), owner, outer_alias)[0]
                                  if '.' in path else context.field(owner, outer_alias, path))
                    i = match.end()
                elif (match := _MACRO.match(code, i)) and subqueries and match.group(1) in subqueries:
                    used_subqueries.add(match.group(1))
                    result.append(self.subquery(subqueries[match.group(1)], table, alias))
                    i = match.end()
                elif match := _PARAM.match(code, i):
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
        if subqueries and subqueries.keys() - used_subqueries:
            raise ValueError(f'Unused named subqueries: {sorted(subqueries.keys() - used_subqueries)}')
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
                expanded.extend('$"' + name.replace('"', '""') + '"'
                                for name, column in self.table.columns.items()
                                if self.allow_joins or not column.is_virtual)
            else:
                expanded.append(expression)
        if not expanded:
            raise ValueError('At least one result column is required')
        projections, names = [], set()
        for expression in expanded:
            value, name = _projection_alias(expression, self.dialect.tokens)
            source = column = None
            resolved_value = None
            if (field_name := _reference(value)) is not None:
                column = self.table.columns.get(field_name)
                if column is not None:
                    source = column.identity or self.table.key + '.' + column.name
                name = name or field_name
            elif match := _PATH.fullmatch(value):
                resolved_value, owner, field = self.related(match.group(1), self.table, self.basealias)
                column = owner.columns[field]
                source = column.identity or owner.key + '.' + column.name
                name = name or match.group(1).replace('@', '').replace('.', '_')
            if name is None:
                raise ValueError('Computed SQL expressions require an explicit AS alias')
            if name in names:
                raise ValueError(f'Duplicate result alias: {name}')
            names.add(name)
            metadata = ResultColumn(name, column.dtype if column else None,
                                    source, column.ui if column else {})
            projections.append(Projection(resolved_value if resolved_value is not None
                                          else self.expression(value), name, metadata))
        return tuple(projections)


class QueryCompiler:
    """Resolve Genro syntax, then delegate SQL and binding to explicit adapters."""

    def __init__(self, model: ResolvedModel, dialect: DataDialect, formatter: BindingFormatter,
                 *, environment: SqlEnvironment | None = None):
        if dialect.name != formatter.dialect:
            raise ValueError('The data dialect and binding formatter are incompatible')
        if any(column.relation_path is not None and column.alias_target is None
               for table in model.tables.values() for column in table.columns.values()):
            model = replace(model, tables=_resolve_aliases(dict(model.tables)))
        self.model = validate_row_policies(model)
        self.dialect = dialect
        self.formatter = formatter
        self.environment = environment if environment is not None else SqlEnvironment()

    def compile_plan(self, plan: QueryPlan) -> CompiledQuery:
        """Ask the configured dialect to render and formatter to prepare bindings."""
        if plan.dialect != self.dialect.name:
            raise ValueError('Query plan belongs to a different data dialect')
        query = self.formatter.prepare(self.dialect.render(plan))
        return replace(query, input_parameters=plan.input_parameters)

    def _context(self, table, params=None, joins=True):
        return _Context(self.model, self.model.table(table), params, self.dialect,
                        self.environment.snapshot(), joins=joins)

    def plan_select(self, table, columns='*', where=None, params=None, order_by=None,
                    limit=None, offset=None, *, exclude_draft=True,
                    exclude_logical_deleted=True, ignore_partition=False,
                    for_update=False, **options) -> QueryPlan:
        """Resolve a select without rendering the root or formatting parameters.

        Correlated child plans are rendered by the dialect into structured
        fragments; driver parameter formatting happens only at compile_plan.
        """
        if options:
            if 'aggregateRows' in options:
                raise UnsupportedFeatureError('aggregateRows has been removed; use explicit SQL aggregates')
            raise UnsupportedFeatureError(f'Unsupported query options: {sorted(options)}')
        if type(for_update) is not bool:
            raise ValueError('for_update must be a boolean')
        context = self._context(table, params)
        projections = context.projection(columns)
        if not projections:
            raise ValueError('SELECT needs result columns')
        predicate = context.expression(where) if where is not None else None
        ordering = context.expression(order_by) if order_by is not None else None
        projections, predicate = context.select_policies(
            projections, predicate, exclude_draft=exclude_draft,
            exclude_logical_deleted=exclude_logical_deleted, ignore_partition=ignore_partition)
        for clause, value in [('LIMIT', limit), ('OFFSET', offset)]:
            if value is not None:
                if isinstance(value, bool) or not isinstance(value, int) or value < 0:
                    raise ValueError(f'{clause} must be a nonnegative integer')
        return QueryPlan('select', context.table_ref(context.table), projections,
                         tuple(context.joins.values()), predicate, ordering, limit, offset,
                         params=context.params, dialect=self.dialect.name,
                         environment=context.environment_binding(), for_update=for_update,
                         input_parameters=tuple(sorted(context.consumed_inputs)))

    def select(self, table, columns='*', where=None, params=None, order_by=None,
               limit=None, offset=None, *, exclude_draft=True,
               exclude_logical_deleted=True, ignore_partition=False,
               for_update=False, **options):
        return self.compile_plan(self.plan_select(table, columns, where, params, order_by,
                                                  limit, offset, exclude_draft=exclude_draft,
                                                  exclude_logical_deleted=exclude_logical_deleted,
                                                  ignore_partition=ignore_partition,
                                                  for_update=for_update, **options))

    def _values(self, context, values):
        if not isinstance(values, Mapping):
            raise TypeError('DML values must be a mapping of logical column names')
        assignments = []
        for index, (name, value) in enumerate(values.items()):
            column = context.table.columns.get(name)
            if column is None:
                raise ValueError(f'Unknown column {context.table.key}.{name}')
            if column.is_virtual:
                kind = 'formula' if column.formula is not None else 'alias'
                raise ValueError(f'Cannot write {kind} column {name}')
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

    def plan_insert(self, table, values, returning='*', *, ignore_partition=False) -> QueryPlan:
        """Resolve insert assignments and returning metadata into a plan."""
        context = self._context(table, joins=False)
        values = context.guard_values(values, insert=True, ignore_partition=ignore_partition)
        assignments = self._values(context, values)
        projections = context.projection(returning)
        return QueryPlan('insert', context.table_ref(context.table), projections,
                         assignments=assignments, params=context.params, dialect=self.dialect.name,
                         environment=context.environment_binding(),
                         input_parameters=tuple(sorted(context.consumed_inputs)))

    def insert(self, table, values, returning='*', *, ignore_partition=False):
        return self.compile_plan(self.plan_insert(table, values, returning, ignore_partition=ignore_partition))

    def plan_update(self, table, values, where, params=None, returning='*', *, ignore_partition=False) -> QueryPlan:
        """Resolve a guarded update without executing or rendering SQL."""
        context = self._context(table, params, joins=False)
        values = context.guard_values(values, ignore_partition=ignore_partition)
        assignments = self._values(context, values)
        if not assignments:
            raise ValueError('UPDATE requires at least one value')
        predicate = self._where(context, where)
        predicate = context.combine_where(predicate, context.partition_predicates(ignore_partition, write=True))
        projections = context.projection(returning)
        return QueryPlan('update', context.table_ref(context.table), projections,
                         where=predicate, assignments=assignments, params=context.params,
                         dialect=self.dialect.name, environment=context.environment_binding(),
                         input_parameters=tuple(sorted(context.consumed_inputs)))

    def update(self, table, values, where, params=None, returning='*', *, ignore_partition=False):
        return self.compile_plan(self.plan_update(table, values, where, params, returning,
                                                   ignore_partition=ignore_partition))

    def plan_delete(self, table, where, params=None, returning='*', *, ignore_partition=False) -> QueryPlan:
        """Resolve a guarded delete without executing or rendering SQL."""
        context = self._context(table, params, joins=False)
        predicate = self._where(context, where)
        predicate = context.combine_where(predicate, context.partition_predicates(ignore_partition, write=True))
        projections = context.projection(returning)
        return QueryPlan('delete', context.table_ref(context.table), projections,
                         where=predicate, params=context.params, dialect=self.dialect.name,
                         environment=context.environment_binding(),
                         input_parameters=tuple(sorted(context.consumed_inputs)))

    def delete(self, table, where, params=None, returning='*', *, ignore_partition=False):
        return self.compile_plan(self.plan_delete(table, where, params, returning, ignore_partition=ignore_partition))


    def _tombstone(self, table):
        owner = self.model.table(table)
        name = owner.policies.logical_deletion_field
        if name and name.startswith('$'):
            name = _reference(name)
        if not name or name not in owner.columns or owner.columns[name].is_virtual:
            raise ValueError('Soft deletion requires a physical logical_deletion_field')
        return name

    def soft_delete(self, table, value, where, params=None, returning='*', *, ignore_partition=False):
        """Write the explicit tombstone value; normal partition write guards apply."""
        if value is None:
            raise ValueError('soft_delete requires a non-None tombstone value')
        return self.update(table, {self._tombstone(table): value}, where, params, returning,
                           ignore_partition=ignore_partition)

    def restore(self, table, where, params=None, returning='*', *, ignore_partition=False):
        """Clear the tombstone without applying draft/deleted read filters."""
        return self.update(table, {self._tombstone(table): None}, where, params, returning,
                           ignore_partition=ignore_partition)


class PostgresCompiler(QueryCompiler):
    """Compatible convenience facade selecting PostgreSQL and psycopg adapters."""

    def __init__(self, model: ResolvedModel, *, environment: SqlEnvironment | None = None):
        from .dialects.postgres import PostgresDialect
        from .drivers.psycopg import PsycopgDriver

        super().__init__(model, PostgresDialect(), PsycopgDriver(), environment=environment)
