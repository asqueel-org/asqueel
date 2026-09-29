"""Compiler contracts proven independently of PostgreSQL SQL and binding syntax."""
import pytest

from genro_sql.compiler import PostgresCompiler, QueryCompiler, quote_identifier
from genro_sql.contracts import Column, CompiledQuery, Relation, ResolvedModel, ResultColumn, Table
from genro_sql.query_plan import Fragment, Identifier, Parameter, SqlStatement, TableRef


class SentinelDialect:
    name = 'sentinel'
    capabilities = frozenset({'select', 'insert', 'update', 'delete'})

    def __init__(self):
        self.token_inputs = []
        self.plans = []

    def quote_identifier(self, name):
        return '[' + name + ']'

    def tokens(self, expression):
        # Deliberately unlike PostgreSQL: angle quotes are one protected token.
        self.token_inputs.append(expression)
        while expression:
            index = expression.find('«')
            if index < 0:
                yield 'code', expression
                return
            yield 'code', expression[:index]
            end = expression.index('»', index)
            yield 'string', expression[index:end + 1]
            expression = expression[end + 1:]

    def render(self, plan):
        self.plans.append(plan)
        parts = ['SENTINEL:' + plan.operation + ':']
        for projection in plan.projections:
            for part in projection.expression.parts:
                parts.append(self.quote_identifier(part.name) if isinstance(part, Identifier) else part)
        return SqlStatement(tuple(parts), plan.params, tuple(p.column for p in plan.projections), self.name)


class SentinelFormatter:
    dialect = 'sentinel'
    binding = 'sentinel_binding'

    def __init__(self):
        self.statements = []

    def prepare(self, statement):
        self.statements.append(statement)
        sql = ''.join('{' + p.name + '}' if isinstance(p, Parameter) else p
                      for p in statement.parts)
        return CompiledQuery(sql, statement.params, statement.columns, self.dialect, self.binding)


@pytest.fixture
def model():
    customer = Table('customer', schema='app', sql_schema='physical', sql_prefix='app_',
                     pkey=('id',), columns={'id': Column('id'), 'name': Column('name')})
    invoice = Table('invoice', schema='app', sql_schema='physical', sql_name='Bills%', columns={
        'id': Column('id', 'L', sql_name='ID%', identity='invoice-id'),
        'customer_id': Column('customer_id'),
        'amount': Column('amount', 'N'),
        'double': Column('double', 'N', formula='$amount * 2'),
    }, relations={'customer': Relation('customer', customer.key, ('customer_id',), ('id',))})
    return ResolvedModel({customer.key: customer, invoice.key: invoice})


def test_neutral_lexer_renderer_and_formatter_are_actual_injected_dependencies(model):
    dialect, formatter = SentinelDialect(), SentinelFormatter()
    compiler = QueryCompiler(model, dialect, formatter)
    query = compiler.select('invoice', '$id, «$hidden,:unused,100%» AS literal, :p AS value',
                            params={'p': '50%'}, where='$id=:p')
    assert dialect.token_inputs
    assert query.sql == 'SENTINEL:select:[t0].[ID%]«$hidden,:unused,100%»{p}'
    assert query.dialect == 'sentinel'
    assert query.binding == 'sentinel_binding'
    assert dict(query.params) == {'p': '50%'}
    assert formatter.statements[0].parts[-1] == Parameter('p')
    assert dialect.plans[0].dialect == 'sentinel'
    assert query.columns[0].source == 'invoice-id'


def test_plan_generation_does_not_render_or_escape_sql(model):
    dialect, formatter = SentinelDialect(), SentinelFormatter()
    compiler = QueryCompiler(model, dialect, formatter)
    plan = compiler.plan_select('invoice', '$id, $double, @customer.name',
                                where='$id=:id', params={'id': 7}, limit=0, offset=0)
    assert not dialect.plans and not formatter.statements
    assert plan.table == TableRef('physical', 'Bills%', 't0')
    assert plan.projections[0].expression == Fragment((Identifier('t0'), '.', Identifier('ID%')))
    assert plan.projections[0].column == ResultColumn('id', 'L', 'invoice-id', {})
    assert plan.where == Fragment((Identifier('t0'), '.', Identifier('ID%'), '=', Parameter('id')))
    assert plan.joins[0].table == TableRef('physical', 'app_customer', 't1')
    assert plan.joins[0].condition == Fragment((Identifier('t0'), '.', Identifier('customer_id'),
                                                ' = ', Identifier('t1'), '.', Identifier('id')))
    assert plan.limit == 0 and plan.offset == 0
    with pytest.raises(TypeError):
        plan.params['id'] = 8
    compiler.compile_plan(plan)
    assert len(dialect.plans) == len(formatter.statements) == 1


def test_write_plans_keep_assignments_and_parameters_structured(model):
    dialect, formatter = SentinelDialect(), SentinelFormatter()
    compiler = QueryCompiler(model, dialect, formatter)
    plan = compiler.plan_update('invoice', {'id': 4}, '$id=:__value_0',
                                params={'__value_0': 1}, returning='$id')
    assert plan.operation == 'update'
    assert plan.assignments[0].column == 'ID%'
    assert plan.assignments[0].value == Fragment((Parameter('___value_0'),))
    assert dict(plan.params) == {'___value_0': 4, '__value_0': 1}
    assert not dialect.plans
    assert compiler.plan_insert('invoice', {}, returning=None).assignments == ()
    deleted = compiler.plan_delete('invoice', 'TRUE', returning=None)
    assert deleted.operation == 'delete' and not deleted.projections


def test_adapter_mismatch_and_plan_mismatch_are_rejected(model):
    dialect, formatter = SentinelDialect(), SentinelFormatter()
    formatter.dialect = 'different'
    with pytest.raises(ValueError, match='incompatible'):
        QueryCompiler(model, dialect, formatter)
    formatter.dialect = 'sentinel'
    compiler = QueryCompiler(model, dialect, formatter)
    foreign_plan = PostgresCompiler(model).plan_select('invoice')
    with pytest.raises(ValueError, match='different data dialect'):
        compiler.compile_plan(foreign_plan)


def test_postgres_facade_preserves_exact_compiled_sql_and_legacy_quoting(model):
    compiler = PostgresCompiler(model)
    selected = compiler.select('invoice', '$id', where='$id=:id', params={'id': 4}, limit=0)
    assert selected.sql == ('SELECT "t0"."ID%%" AS "id" FROM "physical"."Bills%%" AS "t0" '
                            'WHERE "t0"."ID%%"=%(id)s LIMIT 0')
    inserted = compiler.insert('invoice', {'id': 4}, returning='$id')
    assert inserted.sql == ('INSERT INTO "physical"."Bills%%" AS "t0" ("ID%%") '
                            'VALUES (%(__value_0)s) RETURNING "t0"."ID%%" AS "id"')
    assert quote_identifier('a"50%') == '"a""50%%"'
