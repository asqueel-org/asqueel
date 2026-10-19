"""Legacy SELECT algorithm over DbTableObj.relations, without descriptor plans.

Reference: fa35e5ad compiledQuery/getFieldAlias/_findRelationAlias/
_getRelationAlias. The agreed exception is many-side traversal: no exploding
rows or implicit DISTINCT. Many aggregates use correlated scalar SELECTs.
"""
from collections.abc import Mapping
from copy import deepcopy
from dataclasses import replace
import re

from ._legacy_sql import FieldReferences, embed_field_parameters, projection_columns, split_sql, _bag_item_path, _in_range
from .contracts import ResultColumn, UnsupportedFeatureError
from .environment import SqlEnvironment
from .object_tree import DbModel
from .common import split_names
from .model import column_ui, _formula_definition, _formula_parameters, _subquery_definition, _parse_row_policies
from ._sql_bindings import SqlBindings
from ._many_aggregates import aggregate_columns
from .sql_compiled_query import SqlCompiledQuery


# New, explicitly agreed call boundary. It does not replace legacy field parsing.
_MANY_CALL = re.compile(r'(@\w+(?:\.@?\w+)*)\.(\w+)\s*\(')
_CALL_BOUNDARIES = re.compile(r"'[^']*'|\"[^\"]*\"|[()]")
_THIS = re.compile(r'#THIS\.([\w\.@]+)')
_IN_RANGE = re.compile(r"#IN_RANGE\s*\(\s*((?:\$|@|\:)?[\w\.\@]+)\s*,\s*((?:\$|@|\:)?[\w\.\@]+)\s*,\s*((?:\$|@|\:)?[\w\.\@]+)\s*\)\s*", re.MULTILINE)
_PERIOD = re.compile(r"#PERIOD\s*\(\s*((?:\$|@)?[\w\.\@]+)\s*,\s*:?(\w+)\)")
_BAG = re.compile(r"#BAG\s*\(\s*((?:\$|@)?[\w\.\@]+)\s*\)(\s*AS\s*(\w*))?")
_BAGCOLS = re.compile(r"#BAGCOLS\s*\(\s*((?:\$|@)?[\w\.\@]+)\s*\)(\s*AS\s*(\w*))?")
_ENV = re.compile(r"#ENV\(([^,)]+)(,[^),]+)?\)")
_COLREL = re.compile(r'([@$]\w+(?:\.\w+)*)')
_TEMPLATE = re.compile(r'#TEMPLATE\s*\(')
_TEMPLATE_LITERAL = re.compile(r"\s*'((?:[^']|'')*)'\s*", re.S)
_TEMPLATE_ARGUMENT = re.compile(r'(.+)\s+as\s+(\w+)\s*', re.I | re.S)
_TEMPLATE_MARK = '$'
_TEMPLATE_FIELD = re.compile(re.escape(_TEMPLATE_MARK) + r'(?:\{(\w+)\}|(' + re.escape(_TEMPLATE_MARK) + r'))?')


def _to_text(value):
    """Legacy gnrstring.toText without locale: None and '' as '', sequences joined with ','."""
    if isinstance(value, (list, tuple)):
        return ','.join(_to_text(item) for item in value)
    return '' if value is None or value == '' else str(value)


def _closing_parenthesis(text, start):
    depth, quote = 1, None
    for position in range(start, len(text)):
        char = text[position]
        if quote:
            if char == quote:
                quote = None
        elif char in '\'"':
            quote = char
        elif char == '(':
            depth += 1
        elif char == ')':
            depth -= 1
            if not depth:
                return position
    raise ValueError('#TEMPLATE: missing closing parenthesis')


def expand_templates(text, adapter):
    """#TEMPLATE('${n} - ${s}', $name AS n, $surname AS s) as the adapter's concatenation."""
    match = _TEMPLATE.search(text or '')
    while match:
        end = _closing_parenthesis(text, match.end())
        literal, *arguments = split_sql(text[match.end():end])
        found = _TEMPLATE_LITERAL.fullmatch(literal)
        if not found:
            raise ValueError('#TEMPLATE: the first argument must be a quoted template')
        expressions = {}
        for argument in arguments:
            named = _TEMPLATE_ARGUMENT.fullmatch(argument.strip())
            if not named:
                raise ValueError(f'#TEMPLATE: {argument.strip()!r} needs "AS <name>"')
            if named[2] in expressions:
                raise ValueError(f'#TEMPLATE: duplicate name {named[2]!r}')
            expressions[named[2]] = named[1].strip()
        template, parts, used, last = found[1].replace("''", "'"), [], set(), 0
        for field in _TEMPLATE_FIELD.finditer(template):
            parts.append((template[last:field.start()], True))
            last = field.end()
            if field[2]:
                parts.append((_TEMPLATE_MARK, True))
            elif field[1] in expressions:
                used.add(field[1])
                parts.append((expressions[field[1]], False))
            elif field[1]:
                raise ValueError(f'#TEMPLATE: {_TEMPLATE_MARK}{{{field[1]}}} has no argument')
            else:
                raise ValueError(f'#TEMPLATE: write a literal {_TEMPLATE_MARK} as {_TEMPLATE_MARK * 2}')
        parts.append((template[last:], True))
        if expressions.keys() - used:
            raise ValueError(f'#TEMPLATE: unused arguments {sorted(expressions.keys() - used)}')
        sql = adapter.concat_template([part for part in parts if part != ('', True)])
        text = text[:match.start()] + sql + text[end + 1:]
        match = _TEMPLATE.search(text, match.start() + len(sql))
    return text


class _TreeContext:
    def __init__(self, model, table, params, adapter, snapshot, *, parent=None,
                 alias_prefix='t', bindings=None):
        self.model, self.table = model, table
        self.adapter, self.snapshot = adapter, snapshot
        self.bindings = bindings if bindings is not None else SqlBindings(params)
        self.params = self.bindings.params
        self.input_origins = self.bindings.inputs
        self.consumed_inputs = self.bindings.consumed
        self.environment_keys = parent.environment_keys if parent else set()
        self.parent = parent
        self.alias_prefix = alias_prefix
        self.basealias = alias_prefix + '0'
        self.active_formulas = parent.active_formulas if parent else set()
        self.formula_definitions = parent.formula_definitions if parent else {}
        self.formula_bindings = {}
        self.period_parameters = {}
        self.references = FieldReferences()
        self._many_columns = {}
        self.aliases = {self.sql_fullname(table): self.basealias}
        self.cpl: SqlCompiledQuery = SqlCompiledQuery(self.sql_fullname(table), maintable_as=self.basealias, dialect=adapter.dialect)
        self.cpl.relationDict = self.references.paths

    def sql_fullname(self, table):
        quote = self.adapter.adaptSqlName
        return '.'.join(quote(name) for name in (table.sqlschema, table.sqlname) if name)

    @staticmethod
    def physical_column(table, name):
        column = table.columns.get(name)
        if column is not None:
            return column
        if name in table.virtual_columns:
            raise UnsupportedFeatureError(
                f'{table.fullname}.{name}: virtual column in place of a physical column is not available in this release')
        raise ValueError(f'Unknown column {table.fullname}.{name}')

    def field(self, table, alias, name):
        column = self.physical_column(table, name)
        quote = self.adapter.adaptSqlName
        return '%s.%s' % (quote(alias), quote(column.sqlname))

    def get_field_alias(self, path, curr=None, basealias=None, parent=None):
        """getFieldAlias: traverse relations, then physical field or alias recursion."""
        if curr is None and path in self._many_columns:
            return self._compile_many_column(*self._many_columns[path])
        curr = self.table.relations if curr is None else curr
        basealias = basealias or self.basealias
        *pathlist, name = path.removeprefix('$').split('.')
        if pathlist:
            basealias, curr = self._find_relation_alias(
                list(pathlist), curr, basealias, [], parent)
        table = self.model.table(curr.tbl_name, pkg=curr.pkg_name)
        column = table.virtual_columns.get(name) or table.composites.get(name)
        if column is None and name not in table.columns:
            column = table.dynamic_columns.get(name.lower())
        if column is None:
            return self.field(table, basealias, name)
        key = (table.fullname, name)
        if key in self.active_formulas:
            raise ValueError(f'Cyclic formula/alias: {table.fullname}.{name}')
        self.active_formulas.add(key)
        try:
            if column.attributes.get('relation_path'):
                return self.get_field_alias(column.attributes['relation_path'], curr,
                                            basealias, '.'.join(pathlist))
            return self.formula(table, column, curr, basealias)
        finally:
            self.active_formulas.remove(key)

    def formula_definition(self, table, column):
        """Legacy method -> attributes -> select_* -> var_*, on a local copy."""
        key = (table.fullname, column.name)
        if key not in self.formula_definitions:
            attrs = deepcopy(column.attributes)
            if column.tag == 'bagItemColumn':
                attrs['sql_formula'] = self.adapter.bag_item_formula(attrs['bagcolumn'], column.dtype)
                attrs['var_calculated_path'] = _bag_item_path(attrs['itempath'])
                definition = _formula_definition(attrs, column.fullname)
            elif column.tag == 'subQueryColumn':
                mode, aggr = attrs.get('mode'), attrs.get('aggr')
                if aggr is not None and mode is not None:
                    raise ValueError(f'{column.fullname}: subQueryColumn takes aggr and mode, not both')
                if mode not in (None, 'json', 'xml'):
                    raise ValueError(f"{column.fullname}: subQueryColumn mode '{mode}' is not valid; use aggr")
                if mode == 'xml' and isinstance(attrs.get('query'), str):
                    raise UnsupportedFeatureError(
                        f'{column.fullname}: legacy XML subQueryColumn requires a query mapping')
                query = _subquery_definition(attrs.get('query'), column.fullname)
                if aggr is not None:
                    aggregates = aggregate_columns(split_sql(aggr), column.fullname)
                    if len(aggregates) != 1:
                        raise ValueError(f'{column.fullname}: subQueryColumn aggr takes one aggregate')
                    (columns, _, attrs['mode']), = aggregates
                    query = dict(query, columns=columns)
                definition = (None, query, None, {})
            elif column.tag == 'compositeColumn':
                attrs = {'sql_formula': self.composite_formula(table, column)}
                definition = _formula_definition(attrs, column.fullname)
            elif column.tag == 'formulaColumn':
                if attrs.get('sql_formula') is True:
                    name = 'sql_formula_' + column.name
                    method = getattr(table.dbtable, name, None)
                    if not callable(method):
                        raise UnsupportedFeatureError(f'{column.fullname}: missing table method {name}(attr)')
                    attrs['sql_formula'] = method(attrs)
                    if not isinstance(attrs['sql_formula'], str) or not attrs['sql_formula'].strip():
                        raise ValueError(f'{column.fullname}: {name}(attr) must return nonempty SQL')
                definition = _formula_definition(attrs, column.fullname)
            else:
                raise UnsupportedFeatureError(f'{column.fullname}: {column.tag} is not available in this release')
            self.formula_definitions[key] = definition, attrs
        return self.formula_definitions[key]

    @staticmethod
    def composite_formula(table, column):
        """Legacy _buildCompositeColumnFormula: the members as the string '["a", 1]'."""
        chunks = []
        for name in split_names(column.attributes['columns']):
            dtype = table.columns[name].dtype
            if dtype in ('A', 'C', 'T'):
                chunks.append(f""" '"' ||  ${name} || '"' """)
            elif dtype in ('L', 'F', 'R', 'B'):
                chunks.append(f'${name}')
            else:
                chunks.append(f""" '"' ||  ${name} || '::{dtype}"' """)
        return "'[' || " + " ||', '||".join(chunks) + " || ']' "

    def formula(self, table, column, curr, alias):
        (formula, select, exists, subqueries), attrs = self.formula_definition(table, column)
        key = (table.fullname, alias, column.name)
        if key not in self.formula_bindings:
            values = _formula_parameters(column.fullname, **attrs)
            self.formula_bindings[key] = self.bindings.child(values, 'f') if values else self.bindings
        bindings = self.formula_bindings[key]
        if column.tag == 'formulaColumn' and formula is not None:
            formula = _ENV.sub(lambda m: self.expand_env(m, table, column), formula)
        if select is not None or exists is not None:
            formula = '#default'
            subqueries = {'default': (select, False) if select is not None else (exists, True)}
        # Bind the authored expression before inserting children: their local
        # names already belong to their own scope and must never be remangled.
        formula = expand_templates(formula, self.adapter)
        formula = self.expand_many_operations(formula, curr=curr)
        formula = bindings.substitute(formula)
        for name, (definition, is_exists) in subqueries.items():
            aggregate = attrs.get('mode') if column.tag == 'subQueryColumn' else None
            query = self.subquery(definition, curr, alias, bindings,
                                  exists=is_exists, aggregate=aggregate,
                                  row_alias=f'{table.fullname.replace(".", "_")}_{column.name}_{aggregate}')
            query = f'EXISTS {query}' if is_exists else query
            formula = re.sub('#' + re.escape(name) + r'\b', lambda m: query, formula)
        # Legacy discovers formula dependencies locally, resolving against the
        # column owner rather than treating them as fields of the root table.
        formula = _THIS.sub(lambda m: self.get_field_alias(m[1], curr, alias), formula)
        refs = FieldReferences()
        formula = refs.discover(formula)
        formula = _IN_RANGE.sub(self.expand_in_range, formula)
        self._check_macros(formula)
        refs.resolve(lambda path: self.get_field_alias(path, curr, alias))
        return f'( {refs.substitute(formula, safe=True)} )'

    def expand_env(self, match, table, column):
        """Legacy expandEnv: environment key, fallback key, then the env_<name>() table method."""
        name, fallback = match[1], match[2][1:] if match[2] else None
        for key in (name, fallback):
            if key and key in self.snapshot:
                return "'" + _to_text(self.snapshot[key]).replace("'", "''") + "'"
        owner = self._known_table(fallback) if fallback else table
        handler = getattr(owner.dbtable, 'env_' + name, None)
        if handler is None:
            raise ValueError(f"{column.fullname}: #ENV({name}) finds no environment key '{name}' "
                             f"and no method env_{name}")
        return handler()

    def expand_bag(self, match, separateCols):
        """Legacy expandBag/expandBagcols: the plain column in the SQL, the Bag built after fetch."""
        field, alias = match[1], match[3]
        if '@' in field:
            macro = '#BAGCOLS' if separateCols else '#BAG'
            raise ValueError(f'{macro} takes a column of the queried table, not the relation path {field}')
        self.cpl.evaluateBagColumns.append(((alias or field).replace('$', ''), separateCols))
        return f'{field} AS {alias}' if alias else field

    def subquery(self, definition, owner, alias, bindings, *, exists=False,
                 aggregate=None, row_alias=None):
        """getFieldAlias select_* branch: correlated child, same SELECT compiler."""
        if isinstance(definition, str):
            name = 'subquery_' + definition
            method = getattr(self.table.dbtable, name, None)
            if not callable(method):
                raise UnsupportedFeatureError(f'{self.table.fullname}: missing table method {name}()')
            definition = method()
            if not isinstance(definition, Mapping):
                raise ValueError(f'{name} must return a subquery mapping')
            definition = _subquery_definition(definition, f'{self.table.fullname}.{name}')
        if not isinstance(definition, Mapping):
            raise ValueError('A subquery must be a mapping')
        options = deepcopy(dict(definition))
        for old, new in (('excludeDraft', 'exclude_draft'),
                         ('excludeLogicalDeleted', 'exclude_logical_deleted'),
                         ('ignorePartition', 'ignore_partition')):
            if old in options:
                if new in options:
                    raise ValueError(f'Conflicting subquery options: {old}, {new}')
                options[new] = options.pop(old)
        for name, value in [('subtable', '*'), ('addPkeyColumn', False), ('ignoreTableOrderBy', True)]:
            if name in options and (given := options.pop(name)) != value:
                raise UnsupportedFeatureError(
                    f'subquery option {name}={given!r} is not available in this release')
        known = {'table', 'where', 'columns', 'sqlparams', 'cast', 'order_by',
                 'limit', 'offset', 'distinct', 'group_by', 'having', 'bagFields',
                 'exclude_draft', 'exclude_logical_deleted', 'ignore_partition'}
        for name in sorted(options.keys() - known):
            raise UnsupportedFeatureError(f'subquery option {name!r} is not available in this release')
        if exists and 'cast' in options:
            raise UnsupportedFeatureError('Cast applies to scalar subqueries, not EXISTS')
        table = self._known_table(options.pop('table'))
        where = options.pop('where')
        where = _THIS.sub(lambda m: self.get_field_alias(m[1], owner, alias), where)
        cast = options.pop('cast', None)
        child_bindings = bindings.child(options.pop('sqlparams', None), 's')
        child = type(self)(self.model, table, None, self.adapter, self.snapshot,
                           parent=self, alias_prefix=alias + '_t', bindings=child_bindings)
        columns = options.pop('columns', '1' if exists else '*')
        columns = columns if isinstance(columns, str) else ','.join(columns)
        options.setdefault('exclude_draft', False)
        options.setdefault('exclude_logical_deleted', False)
        options.setdefault('ignore_partition', True)
        plan = child.select_plan(columns, where=where, **options)
        sql = plan.get_sqltext(self.adapter)
        if aggregate == 'join':
            return self.adapter.join_sql_subquery(sql, child.basealias + '_rows')
        if aggregate == 'to_json':
            return self.adapter.json_sql_subquery(sql, child.basealias + '_rows', plan.columns)
        if aggregate == 'to_xml':
            return self.adapter.xml_sql_subquery(sql, child.basealias + '_rows', plan.columns)
        if aggregate in ('json', 'xml'):
            if cast:
                raise UnsupportedFeatureError('Cast of a row source is not supported for JSON/XML subQueryColumn')
            return self.adapter.aggregate_sql_subquery(sql, aggregate, row_alias,
                                                       [c.name for c in plan.result_columns])
        if not exists and len(projection_columns(child.expanded_columns, self.adapter.asTranslator)) != 1:
            raise ValueError('A scalar subquery requires exactly one result column')
        return f' CAST( ( {sql} ) AS {cast}) ' if cast else f' ( {sql} ) '

    def _find_relation_alias(self, pathlist, curr, basealias, newpath, parent=None):
        name = pathlist.pop(0)
        node = curr.get_node(name)
        if node is None:
            raise ValueError(f'Relation {name} not found')
        alias, newpath = self._get_relation_alias(node, newpath, basealias, parent)
        curr = curr[name]
        if pathlist:
            return self._find_relation_alias(pathlist, curr, alias, newpath,
                                             f'{parent}.{name}' if parent else name)
        return alias, curr

    @staticmethod
    def _is_many(joiner):
        return joiner['mode'] != 'O' and not joiner.get('one_one', False)

    def _sql_column(self, table, name):
        # Equivalent to legacy sqlnamemapper lookup, directly on the hierarchy.
        # In particular an absent physical target remains a KeyError.
        column = table.columns.get(name)
        if column is None:
            raise KeyError(name)
        return self.adapter.adaptSqlName(column.sqlname)

    def _get_relation_alias(self, node, path, basealias, parent=None):
        """_getRelationAlias, retaining allocation order and physical path keys."""
        joiner = node.attr['joiner']
        if self._is_many(joiner):
            raise UnsupportedFeatureError(
                f'{node.label}: a path through the many relation {node.label} is not available in this release')
        newpath = path + [joiner['many_relation'].split('.', 1)[-1]]
        key = tuple(newpath + [basealias])
        if key in self.aliases:
            return self.aliases[key], newpath
        alias = f'{self.alias_prefix}{len(self.aliases)}'
        self.aliases[key] = alias
        target, origin = ((joiner['one_relation'], joiner['many_relation'])
                          if joiner['mode'] == 'O' else
                          (joiner['many_relation'], joiner['one_relation']))
        target_table, from_table = self.model.table(target), self.model.table(origin)
        target_column, from_column = target.split('.')[-1], origin.split('.')[-1]
        pairs = []
        target_sqlcolumn = None
        from_sqlcolumn = (self._sql_column(from_table, from_column)
                          if not joiner.get('virtual') else None)
        if from_sqlcolumn:
            pairs.append((from_sqlcolumn, self._sql_column(target_table, target_column)))
        elif from_column in from_table.composites:
            from_columns = from_table.composites[from_column].attributes['columns']
            target_columns = target_table.column(target_column).attributes.get('columns')
            if not target_columns:
                raise ValueError('Relation with multikey works only with compositeColumns')
            pairs = list(zip(
                (self._sql_column(from_table, c) for c in from_columns.split(',')),
                (self._sql_column(target_table, c) for c in target_columns.split(','))))
        else:
            target_sqlcolumn = self._sql_column(target_table, target_column)
        quote = self.adapter.adaptSqlName
        adapted_alias, adapted_base = quote(alias), quote(basealias)
        # Native joiners include absent keys with None. Never mutate the shared joiner.
        condition = joiner.get('join_on') or joiner.get('cnd')
        if condition:
            pass
        elif joiner.get('between'):
            value, low, high = joiner['between'].split(';')
            condition = f"""
                ({low} IS NULL AND {high} IS NOT NULL AND {value}<{high}) OR
                ({low} IS NOT NULL AND {high} IS NULL AND {value}>={low}) OR
                ({low} IS NOT NULL AND {high} IS NOT NULL AND
                    {value} >= {low} AND {value} < {high}) OR
                ({low} IS NULL AND {high} IS NULL)
            """
        elif joiner.get('case_insensitive') == 'Y':
            condition = f'lower({adapted_alias}.{target_sqlcolumn}) = lower({adapted_base}.{from_sqlcolumn})'
        elif pairs:
            condition = ' AND '.join(f'({adapted_base}.{left})={adapted_alias}.{right}'
                                     for left, right in pairs)
        else:
            condition = f'(${from_column})={adapted_alias}.{target_sqlcolumn}'
        self._check_macros(condition)
        if parent:
            condition = _COLREL.sub(lambda m: parent + '.' + m[0].replace('$', ''), condition)
        condition = self.expand_many_operations(condition)
        condition = self.bindings.substitute(condition)
        joinrefs = FieldReferences()
        condition = joinrefs.discover(condition)
        for field in joinrefs.paths.values():
            self.get_field_alias(field)
        self.references.paths.update(joinrefs.paths)
        self.cpl.joins.append(
            f'LEFT JOIN {self.sql_fullname(target_table)} AS {adapted_alias} ON ({condition})')
        return alias, newpath

    def _dispatch_many_operation(self, relation, operation, arguments, **context):
        """The agreed getattr boundary; unsupported operations remain explicit."""
        handler = getattr(self, f'many_{operation}', None)
        if handler is None:
            label = getattr(relation, 'label', None) or relation.name
            raise UnsupportedFeatureError(
                f'{label}.{operation}(...): many_{operation} is not available in this release')
        return handler(relation, arguments, **context)

    def expand_many_operations(self, expression, *, curr=None, projection=False):
        """Recognize relation.operation(arguments) before legacy field discovery.

        Boundaries accept nested parentheses; the legacy split handles commas.
        Aggregated SQL is resolved later with formula references, so its fields
        and parameter manglers never pass through the outer discovery again.
        """
        if not expression:
            return expression
        origin = self.table.relations if curr is None else curr
        for match in _MANY_CALL.finditer(expression):
            curr = origin
            segments = match[1].split('.')
            node = None
            for index, name in enumerate(segments):
                node = curr.get_node(name)
                if node is None:
                    node = self._virtual_relation(curr, name)
                    if node is None:
                        break
                    many = True
                else:
                    many = self._is_many(node.attr['joiner'])
                if many and index != len(segments) - 1:
                    raise UnsupportedFeatureError(
                        f'{match[1]}: a path through the many relation {name} is not available in this release')
                if index != len(segments) - 1:
                    curr = curr[name]
            else:
                if many:
                    operation = match[2]
                    arguments, end = self._many_arguments(expression, match.end(), match[1])
                    order_by = None
                    if operation == 'order_by':
                        if len(arguments) != 1:
                            raise ValueError('order_by requires one quoted query ordering')
                        value = arguments[0].strip()
                        if len(value) < 2 or value[0] not in ("'", '"') or value[-1] != value[0]:
                            raise ValueError('order_by requires one quoted query ordering')
                        order_by = value[1:-1].replace(value[0] * 2, value[0])
                        following = re.match(r'\s*\.aggr\s*\(', expression[end:])
                        if following is None:
                            raise UnsupportedFeatureError('order_by must be followed by aggr')
                        arguments, end = self._many_arguments(expression, end + following.end(), match[1])
                        operation = 'aggr'
                    if (projection and operation == 'aggr'
                            and (expression[:match.start()].strip() or expression[end:].strip())):
                        raise UnsupportedFeatureError('aggr must be a standalone projection')
                    context = dict(curr=origin, path=match[1], projection=projection)
                    if order_by is not None:
                        context['order_by'] = order_by
                    expanded = self._dispatch_many_operation(node, operation, arguments, **context)
                    return (expression[:match.start()] + expanded
                            + self.expand_many_operations(expression[end:],
                                                          curr=origin, projection=projection))
        return expression

    @staticmethod
    def _many_arguments(expression, start, path):
        """Use the existing call boundaries and legacy argument splitter."""
        depth = 1
        for boundary in _CALL_BOUNDARIES.finditer(expression, start):
            if boundary[0] == '(':
                depth += 1
            elif boundary[0] == ')':
                depth -= 1
            if depth == 0:
                text = expression[start:boundary.start()]
                return tuple(split_sql(text)) if text.strip() else (), boundary.end()
        raise ValueError(f'{path}: missing closing parenthesis')

    def many_aggr(self, relation, arguments, *, curr, path, projection=False, order_by=None):
        """Expand approved projections; reuse scalar subquery compilation."""
        if not projection:
            raise UnsupportedFeatureError('aggr is currently supported only in projections')
        columns = []
        for expression, name, aggregate in aggregate_columns(arguments, path):
            token = f'_many_{len(self._many_columns)}'
            while token in self.table.columns or token in self.table.virtual_columns or token in self._many_columns:
                token = '_' + token
            self._many_columns[token] = (relation, expression, curr, path, aggregate, order_by)
            columns.append(f'${token} AS {self.adapter.asTranslator(name)}')
        return ','.join(columns)

    def _virtual_relation(self, curr, name):
        table = self.model.table(curr.tbl_name, pkg=curr.pkg_name)
        return next((child for child in table.children.values()
                     if child.tag == 'virtualRelation'
                     and child.attributes.get('name') == name.removeprefix('@')), None)

    def _virtual_many_condition(self, attrs, curr, alias):
        """Bind one declaration before combining it with any other level.

        Virtual var_* values are source-row SQL expressions, not DB-API values.
        Allocate their names with the existing mangler, then consume those local
        bindings by expanding the expressions; only actual values remain in params.
        """
        condition = attrs.get('condition')
        if not condition:
            return None
        values = {key: value for key, value in attrs.items()
                  if key.startswith('var_') and re.search(':' + key + r'\b', condition)}
        bindings = self.bindings.child(values, 'v') if values else self.bindings
        condition = bindings.substitute(condition)
        for key, value in values.items():
            refs = FieldReferences()
            value = refs.discover(value)
            refs.resolve(lambda field: self.get_field_alias(field, curr, alias))
            value = self.bindings.substitute(refs.substitute(value))
            name = bindings.names[key]
            condition = re.sub(':' + name + r'\b', lambda m: f'({value})', condition)
            bindings.params.pop(name, None)
        return condition

    def _many_base_relation(self, relation, curr, alias):
        """Walk derivations to an ordinary many edge or a direct table declaration."""
        conditions = []
        visited = set()
        while getattr(relation, 'tag', None) == 'virtualRelation':
            attrs = relation.attributes
            key = (curr.pkg_name, curr.tbl_name, attrs['name'])
            if key in visited:
                raise ValueError(f'Cyclic virtual relation: {".".join(key)}')
            visited.add(key)
            if attrs.get('ask'):
                raise UnsupportedFeatureError('Virtual aggregates with ask are not supported')
            if attrs.get('table'):
                condition = attrs.get('condition')
                if not isinstance(condition, str) or not condition.strip():
                    raise ValueError('virtualRelation: table requires a nonempty condition')
            elif not attrs.get('relation'):
                raise UnsupportedFeatureError('Virtual aggregates require a base relation or table')
            condition = self._virtual_many_condition(attrs, curr, alias)
            if condition:
                conditions.append(condition)
            if attrs.get('table'):
                break
            parts = attrs['relation'].split('.')
            if len(parts) > 1:
                alias, curr = self._find_relation_alias(parts[:-1], curr, alias, [])
            relation = curr.get_node(parts[-1])
            if relation is None:
                relation = self._virtual_relation(curr, parts[-1])
            if relation is None:
                raise ValueError(f'Unknown relation {curr.pkg_name}.{curr.tbl_name}.{parts[-1]}')
        return relation, curr, alias, list(reversed(conditions))

    def _many_joiner_condition(self, relation):
        """Reuse ordinary key correlation; direct tables supply their own condition."""
        joiner = relation.attr['joiner']
        if not self._is_many(joiner):
            raise UnsupportedFeatureError('aggr requires a relation towards many')
        for key in ('join_on', 'cnd', 'between'):
            if joiner.get(key):
                raise UnsupportedFeatureError(
                    f'{relation.label}: aggr on a relation with {key}= is not available in this release')
        target = self.model.table(joiner['many_relation'])
        owner = self.model.table(joiner['one_relation'])
        remote = joiner['many_relation'].split('.')[-1]
        local = joiner['one_relation'].split('.')[-1]
        remote_fields = (target.composites[remote].attributes['columns'].split(',')
                         if remote in target.composites else [remote])
        local_fields = (owner.composites[local].attributes['columns'].split(',')
                        if local in owner.composites else [local])
        if len(remote_fields) != len(local_fields):
            raise ValueError('Relation key length mismatch')
        comparisons = []
        for left, right in zip(remote_fields, local_fields):
            left, right = '$' + left, '#THIS.' + right
            if joiner.get('case_insensitive') == 'Y':
                left, right = f'lower({left})', f'lower({right})'
            comparisons.append(f'{left}={right}')
        where = ' AND '.join(comparisons)
        return target, where

    def _compile_many_column(self, relation, expression, curr, path, aggregate, order_by):
        """Correlate a many edge with its owner, then use the select_* algorithm."""
        prefix = path.split('.')[:-1]
        alias = self.basealias
        if prefix:
            alias, curr = self._find_relation_alias(prefix, curr, alias, [])
        relation, curr, alias, conditions = self._many_base_relation(relation, curr, alias)
        if getattr(relation, 'tag', None) == 'virtualRelation':
            target = self._known_table(relation.attributes['table'])
            where = ' AND '.join(f'({item})' for item in conditions)
        else:
            target, where = self._many_joiner_condition(relation)
            if conditions:
                where = ' AND '.join(f'({item})' for item in [where, *conditions])
        options = dict(table=target.fullname, columns=expression, where=where)
        if aggregate in ('join', 'to_json', 'to_xml'):
            # Row order belongs to the correlated SELECT, not the outer query.
            options['order_by'] = (order_by if order_by is not None else
                                   target.attributes.get('order_by'))
        return self.subquery(options, curr, alias, self.bindings, aggregate=aggregate)

    @staticmethod
    def _check_macros(expression):
        macro = re.search(r'#[A-Za-z_]\w*', expression or '')
        if macro and macro[0] == '#ENV':
            raise ValueError('#ENV is expanded only in a formulaColumn sql_formula')
        if macro and macro[0] in ('#BAG', '#BAGCOLS'):
            raise ValueError(f'{macro[0]} is expanded only in the query columns')
        if macro:
            raise UnsupportedFeatureError(f'macro {macro[0]} is not available in this release')

    def result_column(self, field, name):
        if field in self._many_columns:
            return ResultColumn(name)
        path = self.references.paths[field]
        column = self.table.column(path)
        identity = column.attributes.get('x_identity') or column.fullname
        return ResultColumn(name, column.dtype, identity,
                            column_ui(column.fullname, identity, None))

    def projection(self, columns):
        result, metadata = [], []
        for column in projection_columns(columns, self.adapter.asTranslator):
            parts = split_sql(column, ' AS ')
            item = None
            if len(parts) == 2:
                value, name = parts[0].strip(), parts[-1].strip()
                if re.fullmatch(r'"(?:[^"]|"")*"', name):
                    name = name[1:-1].replace('""', '"')
                elif not re.fullmatch(r'[a-z_][a-z_0-9]*', name):
                    name = None
                if name is not None:
                    field = re.fullmatch(r'\$(\w+)', value)
                    item = self.result_column(field[1], name) if field else ResultColumn(name)
            if item is not None:
                metadata.append(item)
            else:
                # Partial metadata cannot be matched reliably to cursor positions.
                metadata.append(None)
            result.append(self.references.substitute(column, safe=True))
        return ',\n'.join(result), tuple(metadata) if all(metadata) else ()

    def select_plan(self, columns='*', where=None, order_by=None, limit=None, offset=None,
                    *, exclude_draft=True, exclude_logical_deleted=True,
                    ignore_partition=False, for_update=False, distinct=False,
                    group_by=None, having=None, bagFields=False, addPkeyColumn=False,
                    count=False) -> SqlCompiledQuery:
        for name, value in [('for_update', for_update), ('bagFields', bagFields), ('addPkeyColumn', addPkeyColumn)]:
            if type(value) is not bool:
                raise ValueError(f'{name} must be a boolean')
        if distinct is not None and type(distinct) is not bool:
            raise ValueError('distinct must be True, False or None')
        aggregate = bool(distinct or group_by)
        if for_update and aggregate:
            raise UnsupportedFeatureError('for_update is incompatible with distinct or group_by')
        if group_by == '*':
            group_by = None
        # Child SELECTs use ignoreTableOrderBy=True, as in legacy queryCompile.
        if self.parent is None and not aggregate and order_by is None:
            order_by = self.table.attributes.get('order_by')
        if self.table.pkey:
            self.references.paths['pkey'] = self.table.pkey
        columns = columns if isinstance(columns, str) else ','.join(columns)
        columns, where, order_by, group_by, having = (
            expand_templates(clause, self.adapter) if clause else clause
            for clause in (columns, where, order_by, group_by, having))
        columns = columns.replace('  ', ' ').replace('\n', '').replace(' as ', ' AS ').replace(' ,', ',')
        if self.parent is None:
            columns = _BAG.sub(lambda m: self.expand_bag(m, False), columns)
            columns = _BAGCOLS.sub(lambda m: self.expand_bag(m, True), columns)
        # Recognize the agreed many-call boundary before split handles columns.
        try:
            selected = split_sql(columns)
        except ValueError:
            # Preserve the existing many-call diagnostic before legacy split.
            self.expand_many_operations(columns)
            raise
        columns = ','.join(self.expand_many_operations(column, projection=True)
                           for column in selected)
        # Legacy SqlQuery includes X fields whenever the read requests a lock.
        columns = self.expand_columns(columns, bagFields=bagFields or for_update)
        if count:
            # Legacy compiledQuery: groups return their keys, DISTINCT retains
            # its projection; only an ordinary query becomes COUNT(*).
            order_by = ''
            if group_by:
                columns = group_by
            elif not distinct:
                columns = 'count(*) AS "gnr_row_count"'
        elif addPkeyColumn and self.table.pkey and not aggregate:
            columns += f',${self.table.pkey} AS "pkey"'
            columns = columns.lstrip(',')
        if not columns:
            raise ValueError('SELECT needs result columns')
        # The legacy expands WHERE macros, adds implicit filters, then embeds
        # field-valued parameters and discovers every clause's references.
        if where:
            where = _IN_RANGE.sub(self.expand_in_range, where)
            where = _PERIOD.sub(self.expand_period, where)
        columns, where = self.select_policies(columns, where,
            exclude_draft=exclude_draft, exclude_logical_deleted=exclude_logical_deleted,
            ignore_partition=ignore_partition, aggregate=aggregate or count)
        columns, where, order_by, group_by, having = (
            self.expand_many_operations(clause)
            for clause in (columns, where, order_by, group_by, having))
        for clause in (columns, where, order_by, group_by, having):
            self._check_macros(clause)
        self.expanded_columns = columns
        columns = self.references.discover(columns)
        if where:
            where, consumed = embed_field_parameters(where, self.bindings.embed_values, self.table)
            where = self.expand_many_operations(where)
            self.consumed_inputs.update(consumed & self.input_origins)
            where = self.references.discover(where)
        order_by = self.references.discover(order_by) if order_by else None
        group_by = self.references.discover(group_by) if group_by else None
        having = self.references.discover(having) if having else None
        for column in split_sql(columns):
            parts = split_sql(column, ' AS ')
            if len(parts) > 1:
                value, alias = parts[0], ' AS '.join(parts[1:])
                self.cpl.aliasDict[self.adapter.asTranslator(alias.strip())] = value.strip()
        columns = self.bindings.substitute(columns)
        where = self.bindings.substitute(where) if where else where
        order_by = self.bindings.substitute(order_by) if order_by else order_by
        group_by = self.bindings.substitute(group_by) if group_by else group_by
        having = self.bindings.substitute(having) if having else having
        self.references.resolve(self.get_field_alias)
        self.cpl.columns, self.cpl.result_columns = self.projection(columns)
        self.cpl.where = self.references.substitute(where) if where else ''
        self.cpl.order_by = self.references.substitute(order_by) if order_by else ''
        self.cpl.joins = [self.references.substitute(join) for join in self.cpl.joins]
        self.cpl.group_by = self.references.substitute(group_by) if group_by else ''
        self.cpl.having = self.references.substitute(having) if having else ''
        self.cpl.distinct = 'DISTINCT ' if distinct else ''
        self.cpl.for_update = for_update
        if for_update and self.table.columns:
            names = (self.model.physical_columns(self.table, self.table.pkey)
                     if self.table.pkey else tuple(self.table.columns))
            self.cpl.lock_column = self.adapter.adaptSqlName(self.table.columns[names[0]].sqlname)
        self.cpl.limit, self.cpl.offset = limit, offset
        for clause in (self.cpl.columns, self.cpl.where, self.cpl.order_by,
                       self.cpl.group_by, self.cpl.having, *self.cpl.joins):
            for name, _ in re.findall(r':env_(\S\w*)(\W|$)', clause):
                parameter = 'env_' + name
                if parameter not in self.params:
                    self.environment_keys.add(name)
                    self.params[parameter] = self.snapshot.get(name)
                if parameter in self.input_origins:
                    self.consumed_inputs.add(parameter)
        self.cpl.params = self.params
        self.cpl.environment_keys = tuple(sorted(self.environment_keys))
        self.cpl.input_parameters = tuple(sorted(self.consumed_inputs))
        self.cpl.local_parameters = tuple(sorted(self.bindings.state['generated']))
        return self.cpl

    def star_columns(self, *, bagFields):
        """Legacy starColumns: physical fields, then static virtual columns."""
        return (['$' + name for name, col in self.table.columns.items() if bagFields or col.dtype != 'X']
                + ['$' + name for name, col in self.table.virtual_columns.items() if col.attributes.get('static')])

    def expand_columns(self, columns, *, bagFields):
        expanded = []
        for column in split_sql(columns):
            column = column.strip()
            if column == '*':
                expanded.extend(self.star_columns(bagFields=bagFields))
            elif column.startswith('*'):
                raise UnsupportedFeatureError(
                    f'column wildcard {column!r} is not available in this release; use * or explicit columns')
            elif column:
                expanded.append(column)
        return ','.join(expanded)

    # Approved existing PostgreSQL correction: typed comparisons before IS NULL.
    # Share the same four-branch helper with the previous compiler, no scanner.
    expand_in_range = staticmethod(_in_range)

    def expand_period(self, match):
        """Legacy expandPeriod with the existing Toolbox decoder and allocator."""
        from genro_toolbox.dates import parse_period
        field, name = match.groups()
        if name in self.input_origins:
            self.consumed_inputs.add(name)
        if name not in self.bindings.available and name.startswith('env_'):
            key = name[4:]
            self.environment_keys.add(key)
            if key in self.snapshot:
                self.bindings.available[name] = self.snapshot[key]
        if name not in self.bindings.available:
            raise ValueError(f'Missing query parameter: {name}')
        if name not in self.period_parameters:
            if any(key not in self.snapshot for key in ('workdate', 'locale')):
                raise ValueError('#PERIOD requires workdate and locale in the compilation environment')
            self.environment_keys.update(('workdate', 'locale'))
            text = self.bindings.available[name] or ''
            if not isinstance(text, str):
                raise ValueError('#PERIOD requires a string or an empty period')
            start, end = parse_period(text.replace(',', ';'), self.snapshot['workdate'], self.snapshot['locale'])
            lower = ':' + self.bindings.add(name + '_from', start) if start is not None else None
            upper = (lower if end == start else ':' + self.bindings.add(name + '_to', end)) if end is not None else None
            self.period_parameters[name] = lower, upper
        lower, upper = self.period_parameters[name]
        if lower is None and upper is None:
            return ' true '
        if lower == upper:
            return f' {field} = {lower} '
        if lower is not None and upper is not None:
            return f' ({field} BETWEEN {lower} AND {upper}) '
        return f' {field} >= {lower} ' if lower is not None else f' {field} <= {upper} '

    def _known_table(self, name):
        table = self.model.table(name)
        if table is None:
            raise ValueError(f'Unknown package/schema {name.split(".")[0]!r}')
        return table

    def policy_field(self, field, *, allow_alias=False, dtype=None):
        column = self.table.column(field)
        if column is None:
            raise ValueError(f'Unknown column {self.table.fullname}.{field.removeprefix("$")}')
        if column.tag != 'column' or (not allow_alias and field.removeprefix('$') in self.table.virtual_columns):
            raise ValueError(f'{self.table.fullname}: policy field {field!r} must be a physical column')
        if dtype and column.dtype != dtype:
            raise ValueError(f'{self.table.fullname}: draft field must have boolean type')
        return field if field.startswith(('$', '@')) else '$' + field

    def partition_conditions(self, ignore_partition):
        """Legacy getPartitionCondition, without the ``__allowed_partition`` fallback."""
        if ignore_partition:
            return []
        field = next((key[len('partition_'):] for key in self.table.attributes
                      if key.startswith('partition_')), None)
        if field is None:
            return []
        path = self.table.attributes['partition_' + field]
        current, allowed = f'current_{path}', f'allowed_{path}'
        self.environment_keys.update((current, allowed))
        if self.snapshot.get(current):
            return [f'${field} = :env_{current}']
        if self.snapshot.get(allowed):
            return [f'${field} IS NULL OR ${field} IN :env_{allowed}']
        return []

    def select_policies(self, columns, where, *, exclude_draft,
                        exclude_logical_deleted, ignore_partition, aggregate):
        """Legacy root-only filter order: WHERE, partition, deletion, draft."""
        if type(exclude_draft) is not bool or type(ignore_partition) is not bool:
            raise ValueError('exclude_draft and ignore_partition must be boolean')
        if (exclude_logical_deleted is not True and exclude_logical_deleted is not False
                and exclude_logical_deleted != 'mark'):
            raise ValueError('exclude_logical_deleted must be True, False or mark')
        policies = _parse_row_policies(self.table.attributes)
        conditions = [where] if where else []
        conditions.extend(self.partition_conditions(ignore_partition))
        if policies.logical_deletion_field:
            field = self.policy_field(policies.logical_deletion_field)
            if exclude_logical_deleted is True:
                conditions.append(f'{field} IS NULL')
            elif exclude_logical_deleted == 'mark' and not aggregate:
                columns += f',{field} AS "_isdeleted"'
        if policies.draft_field and exclude_draft:
            field = self.policy_field(policies.draft_field, dtype='B')
            conditions.append(f'{field} IS NOT TRUE')
        return columns, ' AND '.join(f'({condition})' for condition in conditions)


class QueryCompiler:
    """Compile against the hierarchy with a fresh local context per request."""

    def __init__(self, model, adapter, *, environment=None, _db=None):
        if not isinstance(model, DbModel):
            raise TypeError('QueryCompiler requires a hierarchical DbModel')
        self.model, self.adapter = model, adapter
        self.environment = environment if environment is not None else SqlEnvironment()

    def _context(self, table, params=None) -> _TreeContext:
        found = self.model.table(table)
        if found is None:
            raise ValueError(f'Unknown package/schema {table.split(".")[0]!r}')
        return _TreeContext(self.model, found, params, self.adapter,
                            self.environment.snapshot())

    @staticmethod
    def _check_options(options):
        if options:
            if 'aggregateRows' in options:
                raise UnsupportedFeatureError('aggregateRows has been removed; use explicit SQL aggregates')
            name = sorted(options)[0]
            raise UnsupportedFeatureError(f'query option {name!r} is not available in this release')

    def compile_plan(self, plan):
        if plan.dialect != self.adapter.dialect:
            raise ValueError('Query plan belongs to a different adapter dialect')
        sql = plan.get_sqltext(self.adapter)
        query = self.adapter.prepare_sql(sql, plan.params, self.environment.snapshot())
        environment_inputs = {'env_' + key for key in plan.environment_keys}
        used_inputs = (set(query.input_parameters) - environment_inputs - set(plan.local_parameters)) | set(plan.input_parameters)
        return replace(query, columns=plan.result_columns, environment_keys=plan.environment_keys,
                       for_update=plan.for_update, lock_table=plan.maintable, lock_column=plan.lock_column,
                       input_parameters=tuple(sorted(used_inputs)),
                       evaluateBagColumns=tuple(plan.evaluateBagColumns))

    def plan_select(self, table, columns='*', where=None, sqlparams=None, order_by=None,
                    limit=None, offset=None, *, exclude_draft=True,
                    exclude_logical_deleted=True, ignore_partition=False,
                    for_update=False, distinct=False, group_by=None, having=None, bagFields=False, addPkeyColumn=False,
                    **options) -> SqlCompiledQuery:
        """Resolve clauses; SQL assembly and preparation happen in compile_plan."""
        self._check_options(options)
        return self._context(table, sqlparams).select_plan(
            columns, where, order_by, limit, offset, exclude_draft=exclude_draft,
            exclude_logical_deleted=exclude_logical_deleted, ignore_partition=ignore_partition,
            for_update=for_update, distinct=distinct, group_by=group_by, having=having,
            bagFields=bagFields, addPkeyColumn=addPkeyColumn)

    def plan_count(self, table, columns='*', where=None, sqlparams=None, order_by=None,
                   limit=None, offset=None, *, exclude_draft=True,
                   exclude_logical_deleted=True, ignore_partition=False,
                   for_update=False, distinct=False, group_by=None, having=None,
                   bagFields=False, addPkeyColumn=False, **options) -> SqlCompiledQuery:
        """Legacy count branch; grouped/distinct SQL still returns result rows."""
        self._check_options(options)
        return self._context(table, sqlparams).select_plan(
            columns, where, order_by, limit, offset, exclude_draft=exclude_draft,
            exclude_logical_deleted=exclude_logical_deleted, ignore_partition=ignore_partition,
            for_update=for_update, distinct=distinct, group_by=group_by, having=having,
            bagFields=bagFields, addPkeyColumn=addPkeyColumn, count=True)

    def count(self, table, columns='*', where=None, sqlparams=None, order_by=None,
              limit=None, offset=None, **options):
        return self.compile_plan(self.plan_count(table, columns, where, sqlparams, order_by,
                                                 limit, offset, **options))

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


class PostgresCompiler(QueryCompiler):
    """The hierarchical compiler on the PostgreSQL adapter, without a database."""

    def __init__(self, model, *, environment=None):
        from .adapters.postgres import SqlDbAdapter
        super().__init__(model, SqlDbAdapter(None), environment=environment)
