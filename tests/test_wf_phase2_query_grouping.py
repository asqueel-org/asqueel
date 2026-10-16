"""Phase 2 contract — QueryPlan clauses, DISTINCT, GROUP BY and HAVING (R15–R22, R28–R30, D4/D5/D8/D10)."""
import pytest

from asqueel.contracts import ResultColumn, UnsupportedFeatureError
from asqueel.dialects.postgres import PostgresDialect
from asqueel.dialects.sqlite import SqliteDialect
from asqueel.query_plan import Identifier, Projection, QueryPlan, TableRef, concat

from tests import query_completion_support as support

shop = support.shop
DIALECTS = [PostgresDialect, SqliteDialect]


def text(statement):
    return ''.join(part if isinstance(part, str) else f'<bind:{part.name}>'
                   for part in statement.parts)


def column(name):
    return concat(Identifier('t0'), '.', Identifier(name))


def select(dialect, **options):
    projection = Projection(column('customer_id'), 'customer_id', ResultColumn('customer_id', 'L'))
    return QueryPlan('select', TableRef('sales', 'invoice'), projections=(projection,),
                     dialect=dialect.name, **options)


def grouped(rows, key):
    return sorted(rows, key=lambda row: (row[key] is None, row[key]))


@pytest.mark.parametrize('dialect_class', DIALECTS)
def test_plan_rejects_grouping_outside_select(dialect_class):
    dialect = dialect_class()
    plan = QueryPlan('delete', TableRef('sales', 'invoice'), where=concat('TRUE'),
                     group_by=column('customer_id'), dialect=dialect.name)
    with pytest.raises(UnsupportedFeatureError):
        dialect.render(plan)
