"""Resolve the native asqueel expression profile into driver-independent query plans.

The data dialect owns SQL tokenization and rendering. Binding formatters own
placeholder syntax and escaping. Authored SQL fragments remain trusted code.
"""
from __future__ import annotations

import re
from collections.abc import Collection, Mapping
from dataclasses import replace

from ._compiler_bindings import _Bindings
from ._legacy_sql import _bag_item_path, _in_range
from .contracts import (CompiledQuery, EnvironmentBinding, ResolvedModel, ResultColumn,
                        UnsupportedFeatureError)
from .environment import SqlEnvironment
from .dialects.base import DataDialect
from .drivers.base import BindingFormatter
from .model import (
    _formula_definition, _formula_parameters, _resolve_aliases, _unique_target,
    _subquery_definition, validate_row_policies,
)
from .model_sections import thaw
from .query_plan import (
    _IDENT, _PARAM, Assignment, Identifier, Join, Projection, QueryPlan,
    SqlStatement, TableRef, _column_reference, concat, separated,
)

_FIELD = re.compile(r"\$(" + _IDENT + r")")
_PATH = re.compile(r"@(" + _IDENT + r"(?:\.@?" + _IDENT + r")*\." + _IDENT + r")")
_THIS = re.compile(r"#THIS\.(@?" + _IDENT + r"(?:\.@?" + _IDENT + r")*)")
_MACRO = re.compile(r"#(" + _IDENT + r")")
# Legacy grammar: simple field/path/parameter operands, not arbitrary SQL calls.
_IN_RANGE = re.compile(
    r"#IN_RANGE\s*\(\s*((?:\$|@|\:)?[\w\.\@]+)\s*,\s*"
    r"((?:\$|@|\:)?[\w\.\@]+)\s*,\s*((?:\$|@|\:)?[\w\.\@]+)\s*\)")
_PERIOD = re.compile(r"#PERIOD\s*\(\s*((?:\$|@)?[\w\.\@]+)\s*,\s*:?(\w+)\)")


def _replace_macro(expression, pattern, replacement, tokens):
    # Unlike the legacy whole-string regex, preserve quoted SQL and comments.
    return ''.join(pattern.sub(replacement, text) if kind == 'code' else text
                   for kind, text in _runs(expression, tokens))


def distinct_ordering(context, projections, order_by):
    """Reject a DISTINCT ORDER BY item that is not one of the projected columns (R18, D10).

    DISTINCT removes rows before ORDER BY, so a sort key outside the projection
    has no single value per result row.
    """
    aliases = {projection.alias for projection in projections}
    expressions = [projection.expression for projection in projections]
    for item in _split(order_by, context.dialect.tokens):
        term = re.sub(r'(?i)\s+NULLS\s+(?:FIRST|LAST)$', '', item.strip()).strip()
        term = re.sub(r'(?i)\s+(?:ASC|DESC)$', '', term).strip()
        if re.fullmatch(_IDENT, term) or re.fullmatch(r'"(?:[^"]|"")+"', term):
            name = term[1:-1].replace('""', '"') if term.startswith('"') else term
            if name in aliases:
                continue
        elif context.expression(term) in expressions:
            continue
        raise UnsupportedFeatureError(
            f'ORDER BY {item!r} with distinct must be a projected alias or expression')


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
                 *, parent=None, outer=None, namespace='', bindings=None, db=None):
        self.model, self.table = model, table
        self.dialect, self.snapshot = dialect, snapshot
        self.bindings = bindings if bindings is not None else _Bindings(params, dialect, snapshot)
        self.environment_keys = self.bindings.environment_keys
        self.policy_parameter_index = 0
        self.joins = {}
        self.allow_joins = joins
        self.formulas = parent.formulas if parent else set()
        self.formula_definitions = parent.formula_definitions if parent else {}
        self.formula_attributes = parent.formula_attributes if parent else {}
        self.db = parent.db if parent else db
        self.formula_bindings = {}
        self.namespace = namespace
        self.basealias = namespace + 't0'
        self.outer = outer
        self.period_parameters = {}

    @staticmethod
    def table_ref(table, alias='t0'):
        return TableRef(table.physical_schema, table.physical_name, alias)

    def environment_binding(self):
        if not self.environment_keys:
            return None
        keys = tuple(sorted(self.environment_keys))
        return EnvironmentBinding(keys, {k: self.snapshot[k] for k in keys if k in self.snapshot})

    def _period(self, match):
        """Legacy expandPeriod predicates, using Toolbox's existing decoder."""
        from genro_toolbox.dates import parse_period

        field, name = match.groups()
        self.bindings.resolve(name)
        if name not in self.period_parameters:
            if any(key not in self.snapshot for key in ('workdate', 'locale')):
                raise ValueError('#PERIOD requires workdate and locale in the compilation environment')
            self.environment_keys.update(('workdate', 'locale'))
            # Legacy accepts None as no period and commas as range separators.
            text = self.bindings.available[name] or ''
            if not isinstance(text, str):
                raise ValueError('#PERIOD requires a string or an empty period')
            start, end = parse_period(text.replace(',', ';'), self.snapshot['workdate'],
                                      self.snapshot['locale'])

            def parameter(suffix, value):
                if value is None:
                    return None
                generated = self.bindings.add(name + suffix, value)
                return ':' + generated

            lower = parameter('_from', start)
            upper = parameter('_to', end) if end != start else lower
            self.period_parameters[name] = (lower, upper)
        lower, upper = self.period_parameters[name]
        if lower is None and upper is None:
            return ' true '
        if lower == upper:
            return f' {field} = {lower} '
        if lower is not None and upper is not None:
            return f' ({field} BETWEEN {lower} AND {upper}) '
        return f' {field} >= {lower} ' if lower is not None else f' {field} <= {upper} '

    def where(self, expression):
        """Expand only the legacy WHERE query macros before resolving fields."""
        if expression is None:
            return None
        if not isinstance(expression, str):
            raise ValueError('Expected nonempty SQL expression')
        expression = _replace_macro(expression, _IN_RANGE, _in_range, self.dialect.tokens)
        expression = _replace_macro(expression, _PERIOD, self._period, self.dialect.tokens)
        return self.expression(expression)

    def policy_binding(self, value):
        name = f'__policy_{self.policy_parameter_index}'
        self.policy_parameter_index += 1
        name = self.bindings.add(name, value)
        return self.bindings.binding(name)

    def policy_field(self, field, *, write=False, allow_alias=False):
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
        column = owner.columns[name]
        if allow_alias and column.alias_target is not None:
            target, target_name = column.alias_target
            column = self.model.table(target).columns[target_name]
        if column.is_virtual:
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

    def native_partition_predicates(self, ignore_partition):
        """Read the scalar value already resolved by the native model render.

        No current_/allowed_ environment convention is inferred here. These
        declarations concern SELECT; legacy write lifecycle is a separate step.
        """
        if ignore_partition:
            return []
        conditions = []
        for option in self.table.options.values():
            if option.name != 'partition' or not option.enabled:
                continue
            attrs = option.attributes
            value = self.scalar(attrs.get('value'))
            if value is None:
                if attrs.get('required', False):
                    raise ValueError(f'{self.table.key}: missing required partition {attrs["name"]}')
                continue
            field, _ = self.policy_field(attrs['field'], allow_alias=True)
            conditions.append(concat(field, ' = ', self.policy_binding(value)))
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
        conditions.extend(self.native_partition_predicates(ignore_partition))
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
                    if not _column_reference(projection.expression):
                        raise UnsupportedFeatureError('mark requires physical column projections; opaque expressions/formulas are unsupported')
                column = self.table.columns[name]
                metadata = ResultColumn('_isdeleted', column.dtype,
                                        column.identity or self.table.key + '.' + name, column.ui)
                projections += (Projection(field, '_isdeleted', metadata),)
        return projections, self.combine_where(predicate, conditions)

    def select_plan(self, columns='*', where=None, order_by=None, limit=None, offset=None,
                    *, exclude_draft=True, exclude_logical_deleted=True,
                    ignore_partition=False, for_update=False, distinct=False,
                    group_by=None, having=None, bagFields=False) -> QueryPlan:
        """One SELECT algorithm for the root and correlated child scopes.

        Keep identifiers and parameters structured until the dialect/driver
        boundary; child scopes differ in ownership and defaults, not clauses.
        """
        if type(for_update) is not bool:
            raise ValueError('for_update must be a boolean')
        if type(bagFields) is not bool:
            raise ValueError('bagFields must be a boolean')
        if distinct is None:
            distinct = False
        if distinct is not True and distinct is not False:
            raise ValueError(f'distinct must be True, False or None, not {distinct!r}')
        if having is not None and group_by is None:
            raise UnsupportedFeatureError('having requires group_by')
        if for_update and (distinct or group_by is not None):
            raise UnsupportedFeatureError('for_update is incompatible with distinct or group_by')
        if exclude_logical_deleted == 'mark' and (distinct or group_by is not None):
            raise UnsupportedFeatureError('mark is incompatible with distinct or group_by')
        if isinstance(group_by, str) and group_by.strip() == '*':
            raise UnsupportedFeatureError(
                "group_by='*' is unsupported; group by the projected columns, and project "
                'the aggregates explicitly')
        projections = self.projection(columns, bagFields=bagFields)
        if not projections:
            raise ValueError('SELECT needs result columns')
        predicate = self.where(where)
        grouping = self.expression(group_by) if group_by is not None else None
        aggregate_filter = self.expression(having) if having is not None else None
        if distinct and order_by is not None:
            distinct_ordering(self, projections, order_by)
        ordering = self.expression(order_by) if order_by is not None else None
        projections, predicate = self.select_policies(
            projections, predicate, exclude_draft=exclude_draft,
            exclude_logical_deleted=exclude_logical_deleted, ignore_partition=ignore_partition)
        for clause, value in [('LIMIT', limit), ('OFFSET', offset)]:
            if value is not None:
                if isinstance(value, bool) or not isinstance(value, int) or value < 0:
                    raise ValueError(f'{clause} must be a nonnegative integer')
        return QueryPlan('select', self.table_ref(self.table, self.basealias), projections,
                         tuple(self.joins.values()), predicate, ordering, limit, offset,
                         params=self.bindings.params, dialect=self.dialect.name,
                         environment=self.environment_binding(), for_update=for_update,
                         input_parameters=tuple(sorted(self.bindings.consumed_inputs)),
                         distinct=distinct, group_by=grouping, having=aggregate_filter)

    def subquery(self, definition, owner, outer_alias, *, exists=False, bindings=None,
                 aggregate=None, row_alias=None):
        if not self.allow_joins:
            raise UnsupportedFeatureError('Subquery columns are not supported in native DML')
        if isinstance(definition, str):
            # Legacy resolves subquery_* on the current SELECT root, unlike
            # sql_formula_* which belongs to the column's owning table.
            method_name = 'subquery_' + definition
            label = f'{self.table.key}.{method_name}()'
            if self.db is None:
                raise UnsupportedFeatureError(f'{label} requires a database-bound table')
            method = getattr(self.db.table(self.table.key), method_name, None)
            if not callable(method):
                raise UnsupportedFeatureError(f'{self.table.key}: missing table method {method_name}()')
            definition = method()
            if not isinstance(definition, Mapping):
                raise ValueError(f'{label} must return a subquery mapping')
            # Own the returned collections; never modify a mapping kept by the
            # application. Validation and SQL compilation follow the dict path.
            definition = _subquery_definition(definition, label)
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
        known = {'table', 'columns', 'where', 'sqlparams', 'order_by',
                 'limit', 'offset', 'exclude_draft', 'exclude_logical_deleted',
                 'ignore_partition', 'cast', 'distinct', 'group_by', 'having', 'bagFields'}
        if options.keys() - known:
            raise UnsupportedFeatureError(f'Unsupported subquery options: {sorted(options.keys() - known)}')
        if exists and 'cast' in options:
            raise UnsupportedFeatureError('Cast applies to scalar subqueries, not EXISTS')
        if not isinstance(options.get('table'), str) or not options['table']:
            raise ValueError('A subquery requires a table')
        if not isinstance(options.get('where'), str) or not options['where'].strip():
            raise ValueError('A subquery requires an explicit WHERE expression')
        local = options.get('sqlparams')
        if local is None:
            local = {}
        if not isinstance(local, Mapping):
            raise ValueError('Subquery sqlparams must be a mapping')
        bindings = (bindings if bindings is not None else self.bindings).child(local, 's')
        child = _Context(self.model, self.model.table(options['table']), None,
                         self.dialect, self.snapshot, parent=self,
                         outer=(self, owner, outer_alias), namespace=bindings.namespace,
                         bindings=bindings)
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
        # Legacy formula defaults: no implicit pkey/order, include drafts and
        # deleted rows, bypass partition unless explicitly requested otherwise.
        plan = child.select_plan(
            normalized, where=options['where'], order_by=options.get('order_by'),
            limit=options.get('limit'), offset=options.get('offset'),
            distinct=options.get('distinct', False), group_by=options.get('group_by'),
            having=options.get('having'), exclude_draft=options.get('exclude_draft', False),
            exclude_logical_deleted=options.get('exclude_logical_deleted', False),
            ignore_partition=options.get('ignore_partition', True),
            bagFields=options.get('bagFields', False))
        if aggregate is not None:
            if 'cast' in options:
                raise UnsupportedFeatureError('Cast of a row source is not supported for JSON/XML subQueryColumn')
            return self.dialect.aggregate_subquery(plan, aggregate, row_alias)
        if not exists and len(plan.projections) != 1:
            raise ValueError('A scalar subquery requires exactly one result column')
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
        capability = column.attributes.get('x_requires_compilation')
        if capability and capability not in ('formulaColumn', 'subQueryColumn', 'bagItemColumn'):
            raise UnsupportedFeatureError(f'{table.key}.{name}: requires {capability} compiler capability')
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
            formula, select, exists, subqueries = self.formula_definition(table, column)
            bindings = self.formula_scope(table, alias, column)
            if select is not None or exists is not None:
                is_exists = exists is not None
                mode = column.attributes.get('mode') if capability == 'subQueryColumn' else None
                # Legacy only stores other modes as subquery_aggr; it does not
                # synthesize an aggregate function around the plain select.
                aggregate = mode if mode in ('json', 'xml') else None
                row_alias = f'{table.key.replace(".", "_")}_{column.name}_{mode}' if aggregate else None
                query = self.subquery(exists if is_exists else select, table, alias,
                                      exists=is_exists, bindings=bindings,
                                      aggregate=aggregate, row_alias=row_alias)
                return concat('EXISTS ' if is_exists else '', query)
            formula = _replace_macro(formula, _IN_RANGE, _in_range, self.dialect.tokens)
            return concat('(', self.expression(formula, table, alias,
                                               subqueries=subqueries, bindings=bindings,
                                               this_owner=(self, table, alias)), ')')
        finally:
            self.formulas.remove(key)

    def formula_definition(self, table, column):
        """Normalize declarations lazily, once per column in this compilation."""
        key = (table.key, column.name)
        if key not in self.formula_definitions:
            capability = column.attributes.get('x_requires_compilation')
            if capability == 'bagItemColumn':
                # Keep the source declaration intact. Generated var_* values use
                # the same per-formula bindings as authored SQL formulas.
                attrs = thaw(column.attributes)
                attrs['sql_formula'] = self.dialect.bag_item_formula(attrs['bagcolumn'], column.dtype)
                attrs['var_calculated_path'] = _bag_item_path(attrs['itempath'])
                definition = _formula_definition(attrs, f'{table.key}.{column.name}')
                self.formula_attributes[key] = attrs
            elif capability == 'subQueryColumn':
                if column.attributes.get('mode') == 'xml' and isinstance(column.attributes.get('query'), str):
                    # Legacy needs query['columns'] to declare its XML fields.
                    raise UnsupportedFeatureError(
                        f'{table.key}.{column.name}: legacy XML subQueryColumn requires a query mapping')
                definition = (None, _subquery_definition(column.attributes.get('query'),
                              f'{table.key}.{column.name}.query'), None, {})
            elif capability == 'formulaColumn':
                attrs = column.attributes
                if attrs.get('subqueries'):
                    raise UnsupportedFeatureError(
                        f'{table.key}.{column.name}: use the existing select_* declarations')
                if attrs.get('handler') is not None:
                    raise UnsupportedFeatureError(f'{table.key}.{column.name}: formula handlers are unsupported')
                if attrs.get('sql_formula') is True:
                    attrs = thaw(attrs)
                    method_name = 'sql_formula_' + column.name
                    if self.db is None:
                        raise UnsupportedFeatureError(
                            f'{table.key}.{column.name}: {method_name} requires a database-bound table')
                    method = getattr(self.db.table(table.key), method_name, None)
                    if not callable(method):
                        raise UnsupportedFeatureError(
                            f'{table.key}.{column.name}: missing table method {method_name}(attr)')
                    # Legacy evaluates the method before select_* and var_*.
                    # Its edits belong to this compilation, never to the model.
                    formula = method(attrs)
                    if not isinstance(formula, str) or not formula.strip():
                        raise ValueError(
                            f'{table.key}.{column.name}: {method_name}(attr) must return nonempty SQL')
                    attrs['sql_formula'] = formula
                definition = _formula_definition(attrs, f'{table.key}.{column.name}')
                self.formula_attributes[key] = attrs
            else:
                definition = column.formula, column.select, column.exists, column.subqueries
            self.formula_definitions[key] = definition
        return self.formula_definitions[key]

    def formula_scope(self, table, alias, column):
        # A formula owns its locals, independently of the formula referring to it.
        # Repeated uses on the same SQL row reuse bindings without caching SQL.
        key = (table.key, alias, column.name)
        if key not in self.formula_bindings:
            attrs = self.formula_attributes.get((table.key, column.name), column.attributes)
            local = _formula_parameters(f'{table.key}.{column.name}', **attrs)
            self.formula_bindings[key] = self.bindings.child(local, 'f') if local else self.bindings
        return self.formula_bindings[key]

    def related(self, path, table, alias):
        if not self.allow_joins:
            raise UnsupportedFeatureError('Relation paths are not supported in native DML')
        parts = path.replace('@', '').split('.')
        for name in parts[:-1]:
            try:
                relation = table.relations[name]
            except KeyError:
                raise ValueError(f'Unknown relation {table.key}.{name}') from None
            if relation.kind == 'virtual':
                raise UnsupportedFeatureError(f'{table.key}.{name}: {relation.kind} navigation requires an additional compiler capability')
            target = self.model.table(relation.target)
            key = (alias, name)
            if key not in self.joins:
                target_alias = f'{self.namespace}t{len(self.joins) + 1}'
                if not relation.columns or len(relation.columns) != len(relation.target_columns):
                    raise ValueError(f'Invalid join columns for {table.key}.{name}')
                if any(column not in table.columns for column in relation.columns) or any(
                        column not in target.columns for column in relation.target_columns):
                    raise ValueError(f'Unknown join columns for {table.key}.{name}')
                # Inverses already swap the key pairs in the resolved model.
                # Their unique side is the source; the target may have many rows.
                if relation.kind == 'inverse':
                    if not _unique_target(table, relation.columns):
                        raise UnsupportedFeatureError(f'{table.key}.{name}: source must have a unique key')
                elif not _unique_target(target, relation.target_columns):
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
                   this_owner=None, bindings=None):
        if not isinstance(expression, str) or not expression.strip():
            raise ValueError('Expected nonempty SQL expression')
        table = table or self.table
        alias = alias or self.basealias
        bindings = bindings if bindings is not None else self.bindings
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
                    result.append(self.subquery(subqueries[match.group(1)], table, alias,
                                                bindings=bindings))
                    i = match.end()
                elif match := _PARAM.match(code, i):
                    if match['keyword'] is None:
                        result.append(bindings.binding(match['name']))
                    else:
                        result.extend(bindings.collection(
                            match['name'], match['keyword'][:3].upper() == 'NOT'))
                    i = match.end()
                elif match := _FIELD.match(code, i):
                    result.append(self.field(table, alias, match.group(1)))
                    i = match.end()
                elif match := _PATH.match(code, i):
                    result.append(self.related(match.group(1), table, alias)[0])
                    i = match.end()
                elif match := _MACRO.match(code, i):
                    raise UnsupportedFeatureError(
                        f'Unsupported macro #{match.group(1)} in this expression')
                elif code[i] == ';':
                    raise UnsupportedFeatureError('Statement separators are not SQL expressions')
                elif code[i] in '$@' or (code[i] == '#' and re.match(r'#[A-Za-z_]', code[i:])):
                    raise UnsupportedFeatureError('Unsupported asqueel expression syntax')
                else:
                    result.append(code[i])
                    i += 1
        if subqueries and subqueries.keys() - used_subqueries:
            raise ValueError(f'Unused named subqueries: {sorted(subqueries.keys() - used_subqueries)}')
        return concat(*result)

    def star_columns(self, *, bagFields=False):
        # Legacy starColumns: physical fields first, then static virtuals.
        # RETURNING keeps all physical fields and never expands virtuals.
        physical = [name for name, col in self.table.columns.items()
                    if not col.is_virtual and (not self.allow_joins or bagFields or col.dtype != 'X')]
        virtual = [name for name, col in self.table.columns.items()
                   if self.allow_joins and col.is_virtual and col.attributes.get('static')]
        return ('$"' + name.replace('"', '""') + '"' for name in physical + virtual)

    def result_column(self, table, field, name):
        column = table.columns.get(field)
        if column is None:
            return ResultColumn(name, None)
        return ResultColumn(name, column.dtype,
                            column.identity or table.key + '.' + column.name, column.ui)

    def projection(self, columns, *, bagFields=False):
        if columns is None:
            return ()
        if isinstance(columns, str):
            expressions = _split(columns, self.dialect.tokens)
        else:
            expressions = list(columns)
        expanded = []
        for expression in expressions:
            if expression.strip() == '*':
                expanded.extend(self.star_columns(bagFields=bagFields))
            else:
                expanded.append(expression)
        if not expanded:
            raise ValueError('At least one result column is required')
        projections, names = [], set()
        for expression in expanded:
            value, name = _projection_alias(expression, self.dialect.tokens)
            metadata = None
            resolved_value = None
            if (field_name := _reference(value)) is not None:
                name = name or field_name
                metadata = self.result_column(self.table, field_name, name)
            elif match := _PATH.fullmatch(value):
                resolved_value, owner, field = self.related(match.group(1), self.table, self.basealias)
                name = name or match.group(1).replace('@', '').replace('.', '_')
                metadata = self.result_column(owner, field, name)
            if name is None:
                raise ValueError('Computed SQL expressions require an explicit AS alias')
            if name in names:
                raise ValueError(f'Duplicate result alias: {name}')
            names.add(name)
            metadata = metadata if metadata is not None else ResultColumn(name)
            projections.append(Projection(resolved_value if resolved_value is not None
                                          else self.expression(value), name, metadata))
        return tuple(projections)


class _SelectCompiler:
    """Shared SELECT pipeline; model-specific lookup belongs to the context."""

    def __init__(self, model, dialect: DataDialect, formatter: BindingFormatter,
                 *, environment: SqlEnvironment | None = None, _db=None):
        if dialect.name != formatter.dialect:
            raise ValueError('The data dialect and binding formatter are incompatible')
        self.model = model
        self.dialect = dialect
        self.formatter = formatter
        self.environment = environment if environment is not None else SqlEnvironment()
        self._db = _db

    def _context(self, table, params=None) -> _Context:
        raise NotImplementedError

    def compile_plan(self, plan: QueryPlan) -> CompiledQuery:
        """Ask the configured dialect to render and formatter to prepare bindings."""
        if plan.dialect != self.dialect.name:
            raise ValueError('Query plan belongs to a different data dialect')
        query = self.formatter.prepare(self.dialect.render(plan))
        return replace(query, input_parameters=plan.input_parameters)

    def plan_select(self, table, columns='*', where=None, sqlparams=None, order_by=None,
                    limit=None, offset=None, *, exclude_draft=True,
                    exclude_logical_deleted=True, ignore_partition=False,
                    for_update=False, distinct=False, group_by=None, having=None, bagFields=False,
                    **options) -> QueryPlan:
        """Resolve a select without rendering the root or formatting parameters.

        Correlated child plans are rendered by the dialect into structured
        fragments; driver parameter formatting happens only at compile_plan.
        """
        if options:
            if 'aggregateRows' in options:
                raise UnsupportedFeatureError('aggregateRows has been removed; use explicit SQL aggregates')
            raise UnsupportedFeatureError(f'Unsupported query options: {sorted(options)}')
        return self._context(table, sqlparams).select_plan(
            columns, where, order_by, limit, offset, exclude_draft=exclude_draft,
            exclude_logical_deleted=exclude_logical_deleted, ignore_partition=ignore_partition,
            for_update=for_update, distinct=distinct, group_by=group_by, having=having,
            bagFields=bagFields)

    def select(self, table, columns='*', where=None, sqlparams=None, order_by=None,
               limit=None, offset=None, *, exclude_draft=True,
               exclude_logical_deleted=True, ignore_partition=False,
               for_update=False, distinct=False, group_by=None, having=None, **options):
        return self.compile_plan(self.plan_select(table, columns, where, sqlparams, order_by,
                                                  limit, offset, exclude_draft=exclude_draft,
                                                  exclude_logical_deleted=exclude_logical_deleted,
                                                  ignore_partition=ignore_partition,
                                                  for_update=for_update, distinct=distinct,
                                                  group_by=group_by, having=having, **options))


class QueryCompiler(_SelectCompiler):
    """Resolve asqueel syntax, then delegate SQL and binding to explicit adapters."""

    def __init__(self, model: ResolvedModel, dialect: DataDialect, formatter: BindingFormatter,
                 *, environment: SqlEnvironment | None = None, _db=None):
        if model.attributes.get('x_legacy_expanded'):
            raise UnsupportedFeatureError('Expanded legacy model requires legacy runtime/compiler providers; migration projection remains available')
        if dialect.name != formatter.dialect:
            raise ValueError('The data dialect and binding formatter are incompatible')
        if any(column.relation_path is not None and column.alias_target is None
               for table in model.tables.values() for column in table.columns.values()):
            model = replace(model, tables=_resolve_aliases(dict(model.tables)))
        super().__init__(validate_row_policies(model), dialect, formatter,
                         environment=environment, _db=_db)

    def _context(self, table, params=None, joins=True) -> _Context:
        resolved = self.model.table(table)
        if not joins:
            from .model_source import require_write_capabilities
            require_write_capabilities(resolved)
        return _Context(self.model, resolved, params, self.dialect,
                        self.environment.snapshot(), joins=joins, db=self._db)

    def plan_count(self, table, columns='*', where=None, sqlparams=None, order_by=None,
                   limit=None, offset=None, *, for_update=False, **options) -> QueryPlan:
        """Resolve the same select, without pagination or ordering, as a count."""
        for clause, value in [('limit', limit), ('offset', offset)]:
            if value is not None:
                raise UnsupportedFeatureError(
                    f'count() cannot apply {clause}; count the query without limit/offset')
        plan = self.plan_select(table, columns, where, sqlparams, None, None, None, **options)
        return replace(plan, operation='count')

    def count(self, table, columns='*', where=None, sqlparams=None, order_by=None,
              limit=None, offset=None, **options):
        return self.compile_plan(self.plan_count(table, columns, where, sqlparams, order_by,
                                                 limit, offset, **options))

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
            parameter = context.bindings.add(f'__value_{index}', value)
            assignments.append(Assignment(column.physical_name, concat(context.bindings.binding(parameter))))
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
                         assignments=assignments, params=context.bindings.params, dialect=self.dialect.name,
                         environment=context.environment_binding(),
                         input_parameters=tuple(sorted(context.bindings.consumed_inputs)))

    def insert(self, table, values, returning='*', *, ignore_partition=False):
        return self.compile_plan(self.plan_insert(table, values, returning, ignore_partition=ignore_partition))

    def plan_update(self, table, values, where, sqlparams=None, returning='*', *, ignore_partition=False) -> QueryPlan:
        """Resolve a guarded update without executing or rendering SQL."""
        context = self._context(table, sqlparams, joins=False)
        values = context.guard_values(values, ignore_partition=ignore_partition)
        assignments = self._values(context, values)
        if not assignments:
            raise ValueError('UPDATE requires at least one value')
        predicate = self._where(context, where)
        predicate = context.combine_where(predicate, context.partition_predicates(ignore_partition, write=True))
        projections = context.projection(returning)
        return QueryPlan('update', context.table_ref(context.table), projections,
                         where=predicate, assignments=assignments, params=context.bindings.params,
                         dialect=self.dialect.name, environment=context.environment_binding(),
                         input_parameters=tuple(sorted(context.bindings.consumed_inputs)))

    def update(self, table, values, where, sqlparams=None, returning='*', *, ignore_partition=False):
        return self.compile_plan(self.plan_update(table, values, where, sqlparams, returning,
                                                   ignore_partition=ignore_partition))

    def plan_delete(self, table, where, sqlparams=None, returning='*', *, ignore_partition=False) -> QueryPlan:
        """Resolve a guarded delete without executing or rendering SQL."""
        context = self._context(table, sqlparams, joins=False)
        predicate = self._where(context, where)
        predicate = context.combine_where(predicate, context.partition_predicates(ignore_partition, write=True))
        projections = context.projection(returning)
        return QueryPlan('delete', context.table_ref(context.table), projections,
                         where=predicate, params=context.bindings.params, dialect=self.dialect.name,
                         environment=context.environment_binding(),
                         input_parameters=tuple(sorted(context.bindings.consumed_inputs)))

    def delete(self, table, where, sqlparams=None, returning='*', *, ignore_partition=False):
        return self.compile_plan(self.plan_delete(table, where, sqlparams, returning, ignore_partition=ignore_partition))


    def _tombstone(self, table):
        owner = self.model.table(table)
        name = owner.policies.logical_deletion_field
        if name and name.startswith('$'):
            name = _reference(name)
        if not name or name not in owner.columns or owner.columns[name].is_virtual:
            raise ValueError('Soft deletion requires a physical logical_deletion_field')
        return name

    def soft_delete(self, table, value, where, sqlparams=None, returning='*', *, ignore_partition=False):
        """Write the explicit tombstone value; normal partition write guards apply."""
        if value is None:
            raise ValueError('soft_delete requires a non-None tombstone value')
        return self.update(table, {self._tombstone(table): value}, where, sqlparams, returning,
                           ignore_partition=ignore_partition)

    def restore(self, table, where, sqlparams=None, returning='*', *, ignore_partition=False):
        """Clear the tombstone without applying draft/deleted read filters."""
        return self.update(table, {self._tombstone(table): None}, where, sqlparams, returning,
                           ignore_partition=ignore_partition)


class PostgresCompiler(QueryCompiler):
    """Compatible convenience facade selecting PostgreSQL and psycopg adapters."""

    def __init__(self, model: ResolvedModel, *, environment: SqlEnvironment | None = None):
        from .dialects.postgres import PostgresDialect
        from .drivers.psycopg import PsycopgDriver

        super().__init__(model, PostgresDialect(), PsycopgDriver(), environment=environment)
