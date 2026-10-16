"""Compiler contracts proven independently of PostgreSQL SQL and binding syntax."""
import pytest

from asqueel.compiler import PostgresCompiler, QueryCompiler, quote_identifier
from asqueel.contracts import Column, CompiledQuery, Relation, ResolvedModel, Table
from asqueel.query_plan import Fragment, Identifier, Parameter, SqlStatement


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


def test_write_plans_keep_assignments_and_parameters_structured(model):
    dialect, formatter = SentinelDialect(), SentinelFormatter()
    compiler = QueryCompiler(model, dialect, formatter)
    plan = compiler.plan_update('invoice', {'id': 4}, '$id=:__value_0',
                                sqlparams={'__value_0': 1}, returning='$id')
    assert plan.operation == 'update'
    assert plan.assignments[0].column == 'ID%'
    assert plan.assignments[0].value == Fragment((Parameter('___value_0'),))
    assert dict(plan.params) == {'___value_0': 4, '__value_0': 1}
    assert not dialect.plans
    assert compiler.plan_insert('invoice', {}, returning=None).assignments == ()
    deleted = compiler.plan_delete('invoice', 'TRUE', returning=None)
    assert deleted.operation == 'delete' and not deleted.projections


def test_postgres_facade_preserves_exact_compiled_sql_and_legacy_quoting(model):
    compiler = PostgresCompiler(model)
    selected = compiler.select('invoice', '$id', where='$id=:id', sqlparams={'id': 4}, limit=0)
    assert selected.sql == ('SELECT "t0"."ID%%" AS "id"\n FROM "physical"."Bills%%" AS "t0"\n'
                            'WHERE "t0"."ID%%"=%(id)s\nLIMIT 0')
    inserted = compiler.insert('invoice', {'id': 4}, returning='$id')
    assert inserted.sql == ('INSERT INTO "physical"."Bills%%" AS "t0" ("ID%%") '
                            'VALUES (%(__value_0)s)\nRETURNING "t0"."ID%%" AS "id"')
    assert quote_identifier('a"50%') == '"a""50%%"'
