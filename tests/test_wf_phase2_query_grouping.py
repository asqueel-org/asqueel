"""Phase 2 contract — QueryPlan clauses, DISTINCT, GROUP BY and HAVING (R15–R22, R28–R30, D4/D5/D8/D10)."""
import pytest

from asqueel.contracts import ResultColumn, UnsupportedFeatureError
from asqueel.dialects.postgres import PostgresDialect
from asqueel.dialects.sqlite import SqliteDialect
from asqueel.query_plan import Identifier, Parameter, Projection, QueryPlan, TableRef, concat

from tests import query_completion_support as support
from tests.query_completion_support import amount, flat

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
def test_plan_renders_distinct_group_by_and_having_in_clause_order(dialect_class):
    dialect = dialect_class()
    plan = select(dialect, distinct=True, group_by=column('customer_id'),
                  having=concat('COUNT(*) >= ', Parameter('minimum')),
                  order_by=column('customer_id'), limit=2, params={'minimum': 1})
    assert text(dialect.render(plan)) == (
        'SELECT DISTINCT "t0"."customer_id" AS "customer_id" FROM "sales"."invoice" AS "t0" '
        'GROUP BY "t0"."customer_id" HAVING COUNT(*) >= <bind:minimum> '
        'ORDER BY "t0"."customer_id" LIMIT 2')


@pytest.mark.parametrize('dialect_class', DIALECTS)
def test_plan_defaults_render_no_new_clause(dialect_class):
    dialect = dialect_class()
    rendered = text(dialect.render(select(dialect)))
    assert rendered == 'SELECT "t0"."customer_id" AS "customer_id" FROM "sales"."invoice" AS "t0"'


@pytest.mark.parametrize('dialect_class', DIALECTS)
@pytest.mark.parametrize('options', [
    {'for_update': True, 'distinct': True},
    {'for_update': True, 'group_by': column('customer_id')},
    {'having': concat('COUNT(*) > 1')},
], ids=['for-update-distinct', 'for-update-group-by', 'having-without-group-by'])
def test_plan_rejects_invalid_combinations_on_every_dialect(dialect_class, options):
    # R28, R29; HAVING without GROUP BY decided at planning
    dialect = dialect_class()
    with pytest.raises(UnsupportedFeatureError):
        dialect.render(select(dialect, **options))


@pytest.mark.parametrize('dialect_class', DIALECTS)
def test_plan_rejects_grouping_outside_select(dialect_class):
    dialect = dialect_class()
    plan = QueryPlan('delete', TableRef('sales', 'invoice'), where=concat('TRUE'),
                     group_by=column('customer_id'), dialect=dialect.name)
    with pytest.raises(UnsupportedFeatureError):
        dialect.render(plan)


def test_distinct_true_projects_only_the_requested_columns(shop):
    # R15
    query = shop.query(columns='$total', distinct=True, order_by='$total')
    assert flat(query.compiled.sql).startswith('SELECT DISTINCT ')
    rows = query.fetch()
    assert [set(row) for row in rows] == [{'total'}] * 4
    assert [amount(row['total']) for row in rows] == [
        amount('7.00'), amount('15.50'), amount('40.00'), amount('125.00')]


@pytest.mark.parametrize('value', [False, None])
def test_distinct_false_and_none_mean_no_distinct(shop, value):
    # D5
    query = shop.query(columns='$total', distinct=value, order_by='$total')
    assert 'DISTINCT' not in query.compiled.sql
    assert len(query.fetch()) == 5


@pytest.mark.parametrize('value', ['', 1, 'yes'])
def test_distinct_other_values_are_rejected(shop, value):
    # D5: an invalid value, like for_update, not an unsupported feature
    with pytest.raises(ValueError, match='distinct') as error:
        shop.query(columns='$total', distinct=value).compiled
    assert error.type is ValueError


def test_distinct_through_a_to_one_path(shop):
    rows = shop.query(columns='@customer.name AS name', distinct=True).fetch()
    assert sorted(rows, key=lambda row: (row['name'] is None, row['name'])) == [
        {'name': 'Ada'}, {'name': 'Grace'}, {'name': 'Linus'}, {'name': None}]


def test_distinct_order_by_outside_projection_is_rejected(shop):
    # R18, D10
    with pytest.raises(UnsupportedFeatureError, match=r'(?i)order.by'):
        shop.query(columns='$customer_id', distinct=True, order_by='$total').compiled


def test_distinct_order_by_inside_projection_is_accepted(shop):
    rows = shop.query(columns='$total', distinct=True, order_by='$total DESC').fetch()
    assert [amount(row['total']) for row in rows] == [
        amount('125.00'), amount('40.00'), amount('15.50'), amount('7.00')]
    aliased = shop.query(columns='$customer_id AS customer', distinct=True,
                         order_by='customer').fetch()
    assert len(aliased) == 4


def test_group_by_resolves_like_where_and_keeps_the_null_group(shop):
    # R19
    query = shop.query(columns='$customer_id, SUM($total) AS total_sum', group_by='$customer_id')
    assert 'GROUP BY "t0"."customer_id"' in flat(query.compiled.sql)
    assert [item.name for item in query.compiled.columns] == ['customer_id', 'total_sum']
    assert query.compiled.columns[0].dtype == 'L'
    rows = grouped(query.fetch(), 'customer_id')
    assert [(row['customer_id'], amount(row['total_sum'])) for row in rows] == [
        (1, amount('140.50')), (2, amount('40.00')), (3, amount('40.00')), (None, amount('7.00'))]


def test_group_by_relation_path_uses_one_join(shop):
    query = shop.query(columns='@customer.name AS name, SUM($total) AS total_sum',
                       group_by='@customer.name')
    assert flat(query.compiled.sql).count(' LEFT JOIN ') == 1
    rows = grouped(query.fetch(), 'name')
    assert [(row['name'], amount(row['total_sum'])) for row in rows] == [
        ('Ada', amount('140.50')), ('Grace', amount('40.00')), ('Linus', amount('40.00')),
        (None, amount('7.00'))]


def test_group_by_alias_column_and_formula(shop):
    alias = shop.query(columns='$client_name, COUNT(*) AS n', group_by='$client_name')
    assert flat(alias.compiled.sql).count(' LEFT JOIN ') == 1
    assert [(row['client_name'], row['n']) for row in grouped(alias.fetch(), 'client_name')] == [
        ('Ada', 2), ('Grace', 1), ('Linus', 1), (None, 1)]
    formula = shop.query(columns='$double_total, COUNT(*) AS n', group_by='$double_total')
    rows = sorted(formula.fetch(), key=lambda row: amount(row['double_total']))
    assert [(amount(row['double_total']), row['n']) for row in rows] == [
        (amount('14.00'), 1), (amount('31.00'), 1), (amount('80.00'), 2), (amount('250.00'), 1)]


def test_group_by_star_is_rejected(shop):
    # R20, D4
    with pytest.raises(UnsupportedFeatureError, match=r'\*'):
        shop.query(columns='SUM($total) AS total_sum', group_by='*').compiled


def test_having_binds_its_parameters(shop):
    # R21
    query = shop.query(columns='$customer_id, SUM($total) AS total_sum', group_by='$customer_id',
                       having='SUM($total) >= :minimum', sqlparams={'minimum': 40})
    assert 'HAVING SUM("t0"."total") >= ' in flat(query.compiled.sql)
    assert list(query.compiled.params.values()) == [40]
    assert sorted(row['customer_id'] for row in query.fetch()) == [1, 2, 3]


def test_having_accepts_collection_parameters(shop):
    query = shop.query(columns='$customer_id, COUNT(*) AS n', group_by='$customer_id',
                       having='$customer_id IN :ids', sqlparams={'ids': [1, 3]})
    assert sorted(row['customer_id'] for row in query.fetch()) == [1, 3]


def test_having_without_group_by_is_rejected(shop):
    with pytest.raises(UnsupportedFeatureError, match=r'(?s)having.*group_by|group_by.*having'):
        shop.query(columns='SUM($total) AS total_sum', having='SUM($total) > 50').compiled


def test_aggregate_projection_without_group_by(shop):
    # R22
    assert [{key: amount(value) for key, value in row.items()}
            for row in shop.query(columns='SUM($total) AS total_sum').fetch()] == [
        {'total_sum': amount('227.50')}]


def test_grouped_pagination_and_empty_dataset(shop):
    query = shop.query(columns='$customer_id, COUNT(*) AS n', where='$customer_id IS NOT NULL',
                       group_by='$customer_id', order_by='$customer_id', limit=2, offset=1)
    assert [row['customer_id'] for row in query.fetch()] == [2, 3]
    empty = shop.query(columns='$customer_id, COUNT(*) AS n', where='$id < 0',
                       group_by='$customer_id')
    assert empty.fetch() == []


@pytest.mark.parametrize('options', [
    {'distinct': True, 'columns': '$customer_id'},
    {'group_by': '$customer_id', 'columns': '$customer_id, COUNT(*) AS n'},
], ids=['distinct', 'group-by'])
def test_for_update_with_distinct_or_group_by_is_rejected(shop, options):
    # R28, R29
    with pytest.raises(UnsupportedFeatureError, match=r'(?i)for.update'):
        shop.query(for_update=True, **options).compiled


@pytest.mark.parametrize('options', [
    {'distinct': True, 'columns': '$total'},
    {'group_by': '$customer_id', 'columns': '$customer_id'},
], ids=['distinct', 'group-by'])
def test_mark_with_distinct_or_group_by_is_rejected(shop, options):
    # R30, D8
    with pytest.raises(UnsupportedFeatureError, match='mark'):
        shop.query(exclude_logical_deleted='mark', **options).compiled
