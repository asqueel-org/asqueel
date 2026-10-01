"""Phase 4 contract — integrated acceptance of collections, grouping, DISTINCT and count.

Plan 30 step 6 fixture: customers with and without invoices, duplicate totals,
NULL customers, draft and logically deleted invoices, two organizations behind a
partition policy, and remapped physical table, column and (on PostgreSQL)
schema names.
"""
from decimal import Decimal
from uuid import uuid4

import pytest

from asqueel import AsqueelDb, CompiledQuery, SqlDatabaseConfig
from asqueel.contracts import UnsupportedFeatureError

from tests.native_support import postgres_dsn
from tests.query_completion_support import BACKENDS, amount

CUSTOMERS = [(1, 'Ada'), (2, 'Grace'), (3, 'Linus'), (4, 'Margaret')]
# id, organization, customer, total, draft, deleted
INVOICES = [
    (20, 1, 1, '100.00', False, None),
    (21, 1, 1, '100.00', False, None),
    (22, 1, 2, '50.00', False, None),
    (23, 1, None, '10.00', False, None),
    (24, 1, 2, '50.00', True, None),
    (25, 1, 3, '30.00', False, '2026-01-01 00:00:00'),
    (30, 2, 1, '70.00', False, None),
    (31, 2, 3, '70.00', False, None),
    (32, 2, None, '5.00', False, None),
]


def declare(schema_node):
    tables = schema_node.tables()
    customer = tables.table('customer', pkey='id', x_sql_name='clients')
    columns = customer.columns()
    columns.column('id', dtype='L')
    columns.column('name', dtype='T', x_sql_name='display')
    customer.virtual_columns().formulaColumn('invoice_count', dtype='L', select=dict(
        table='billing.invoice', columns='COUNT(*)', where='$customer_id = #THIS.id'))
    invoice = tables.table('invoice', pkey='id', x_sql_name='bills',
                           x_partition={'field': 'organization_id', 'current': 'organization'},
                           x_draft_field='draft', x_logical_deletion_field='deleted_at')
    columns = invoice.columns()
    columns.column('id', dtype='L')
    columns.column('organization_id', dtype='L', x_sql_name='org')
    columns.column('customer_id', dtype='L', x_sql_name='client_ref').relation(
        'billing.customer.id', foreign_key=True, x_name='customer')
    columns.column('total', dtype='N', size='12,2', x_sql_name='amount_due')
    columns.column('draft', dtype='B')
    columns.column('deleted_at', dtype='DH')
    invoice.virtual_columns().formulaColumn('double_total', dtype='N', sql_formula='$total * 2')


class Billing:
    def __init__(self, db, prefix):
        self.db = db
        self.prefix = prefix

    def invoices(self, **options):
        return self.db.table('billing.invoice').query(**options)

    def org(self, organization):
        return self.db.temp_env(organization=organization)


def seed(db, prefix):
    for row in CUSTOMERS:
        db.execute(f'INSERT INTO {prefix}clients (id, display) VALUES (:id, :name)',
                   dict(zip(('id', 'name'), row)))
    for invoice_id, org, customer, total, draft, deleted in INVOICES:
        db.execute(f'INSERT INTO {prefix}bills (id, org, client_ref, amount_due, draft, deleted_at) '
                   'VALUES (:id, :org, :customer, :total, :draft, :deleted)',
                   {'id': invoice_id, 'org': org, 'customer': customer, 'total': Decimal(total),
                    'draft': draft, 'deleted': deleted})
    db.commit()


@pytest.fixture(params=BACKENDS)
def billing(request, tmp_path):
    if request.param == 'sqlite':
        path = tmp_path / 'billing.db'

        class SqliteRecipe(SqlDatabaseConfig):
            def main(self, root):
                db = root.db('billing')
                db.connection(name=str(path), implementation='sqlite')
                declare(db.schemas().schema('billing'))

        db = AsqueelDb(SqliteRecipe)
        try:
            db.execute('CREATE TABLE billing.clients (id INTEGER PRIMARY KEY, display TEXT)')
            db.execute('CREATE TABLE billing.bills (id INTEGER PRIMARY KEY, org INTEGER, '
                       'client_ref INTEGER, amount_due NUMERIC, draft BOOLEAN, deleted_at TEXT)')
            db.commit()
            seed(db, 'billing.')
            yield Billing(db, 'billing.')
        finally:
            db.rollback()
            db.close()
        return
    schema = 'query_acceptance_' + uuid4().hex
    dsn = postgres_dsn()

    class PostgresRecipe(SqlDatabaseConfig):
        def main(self, root):
            declare(root.db('billing', conninfo=dsn).schemas().schema(
                'billing', x_sql_schema=schema))

    db = AsqueelDb(PostgresRecipe)
    try:
        for statement in (
                f'CREATE SCHEMA "{schema}"',
                f'CREATE TABLE "{schema}".clients (id bigint PRIMARY KEY, display text)',
                f'CREATE TABLE "{schema}".bills (id bigint PRIMARY KEY, org bigint, '
                f'client_ref bigint REFERENCES "{schema}".clients(id), '
                'amount_due numeric(12,2), draft boolean, deleted_at timestamp)'):
            db.execute(CompiledQuery(statement))
        db.commit()
        seed(db, f'"{schema}".')
        yield Billing(db, f'"{schema}".')
    finally:
        db.rollback()
        db.execute(CompiledQuery(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE'))
        db.commit()
        db.close()


def by(rows, *keys):
    return sorted((tuple(row[key] for key in keys) for row in rows),
                  key=lambda item: tuple((value is None, value) for value in item))


def test_grouped_collection_query_follows_the_organization(billing):
    query = billing.invoices(
        columns='@customer.name AS name, COUNT(*) AS n, SUM($total) AS total_sum',
        where='$customer_id IN :customers', group_by='@customer.name',
        having='SUM($total) >= :minimum', sqlparams={'customers': [1, 2, 4], 'minimum': 50})
    with billing.org(1):
        sql = query.compiled.sql
        rows = query.fetch()
        assert [(name, n, amount(total)) for name, n, total in by(rows, 'name', 'n', 'total_sum')] == [
            ('Ada', 2, amount('200.00')), ('Grace', 1, amount('50.00'))]
        assert query.count() == 2
    with billing.org(2):
        assert [(row['name'], amount(row['total_sum'])) for row in query.fetch()] == [
            ('Ada', amount('70.00'))]
        assert query.count() == 1
    assert '"client_ref"' in sql and '"amount_due"' in sql and '"bills"' in sql


def test_distinct_totals_and_their_count_per_organization(billing):
    query = billing.invoices(columns='$total', distinct=True)
    with billing.org(1):
        assert sorted(amount(row['total']) for row in query.fetch()) == [
            amount('10.00'), amount('50.00'), amount('100.00')]
        assert query.count() == 3
    with billing.org(2):
        assert query.count() == 2


def test_empty_not_in_keeps_null_customers_and_counts_them(billing):
    query = billing.invoices(columns='$id', where='$customer_id NOT IN :excluded',
                             sqlparams={'excluded': []}, order_by='$id')
    with billing.org(1):
        assert [row['id'] for row in query.fetch()] == [20, 21, 22, 23]
        assert query.count() == 4


def test_draft_rows_enter_groups_only_when_requested(billing):
    options = dict(columns='$customer_id, SUM($total) AS total_sum', where='$customer_id = :c',
                   group_by='$customer_id', sqlparams={'c': 2})
    with billing.org(1):
        assert [amount(row['total_sum']) for row in billing.invoices(**options).fetch()] == [
            amount('50.00')]
        drafts = billing.invoices(exclude_draft=False, **options)
        assert [amount(row['total_sum']) for row in drafts.fetch()] == [amount('100.00')]
        assert drafts.count() == 1


def test_grouped_pagination_and_count_rejection(billing):
    query = billing.invoices(columns='$customer_id, COUNT(*) AS n', where='$customer_id IS NOT NULL',
                             group_by='$customer_id', order_by='$customer_id', limit=1, offset=1)
    with billing.org(1):
        assert [row['customer_id'] for row in query.fetch()] == [2]
        with pytest.raises(UnsupportedFeatureError):
            query.count()


def test_formula_grouping_and_null_groups(billing):
    formula = billing.invoices(columns='$double_total, COUNT(*) AS n', group_by='$double_total')
    with billing.org(1):
        assert [(amount(total), n) for total, n in by(formula.fetch(), 'double_total', 'n')] == [
            (amount('20.00'), 1), (amount('100.00'), 1), (amount('200.00'), 2)]
    nulls = billing.invoices(columns='$customer_id, COUNT(*) AS n', group_by='$customer_id')
    with billing.org(2):
        assert by(nulls.fetch(), 'customer_id', 'n') == [(1, 1), (3, 1), (None, 1)]
        assert nulls.count() == 3


def test_distinct_correlated_formula_over_customers_without_invoices(billing):
    # the formula subquery keeps the partition and admits drafts and deleted rows
    query = billing.db.table('billing.customer').query(columns='$invoice_count', distinct=True)
    with billing.org(1):
        assert sorted(row['invoice_count'] for row in query.fetch()) == [0, 1, 2]
        assert query.count() == 3


def test_direct_sql_collection_on_physical_names(billing):
    rows = billing.db.execute(f'SELECT id FROM {billing.prefix}bills WHERE client_ref IN :ids',
                              {'ids': [1]}).rows
    assert sorted(row['id'] for row in rows) == [20, 21, 30]
