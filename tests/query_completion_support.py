"""Shared dataset of the query completion contract tests (document 31).

The rows are the legacy oracle dataset of docs/design/31-query-contract-matrix.md:
invoice 13 has no customer, invoice 14 is logically deleted. Every expected
result of the contract tests refers to this dataset. PostgreSQL runs in a
random physical schema mapped to the logical schema ``sales``.
"""
import re
from decimal import Decimal
from uuid import uuid4

import pytest

from asqueel import AsqueelDb, CompiledQuery, SqlDatabaseConfig
from tests.native_support import postgres_dsn

CUSTOMERS = [(1, 'Ada'), (2, 'Grace'), (3, 'Linus')]
INVOICES = [
    (10, 1, '125.00', 'First order', None),
    (11, 2, '40.00', None, None),
    (12, 1, '15.50', 'Second order', None),
    (13, None, '7.00', 'No customer', None),
    (14, 2, '40.00', None, '2026-01-01 00:00:00'),
    (15, 3, '40.00', None, None),
]
VISIBLE = [10, 11, 12, 13, 15]
ALL_IDS = [10, 11, 12, 13, 14, 15]
BACKENDS = ['sqlite', pytest.param('postgresql', marks=pytest.mark.postgresql)]
PLACEHOLDER = r'%\(\w+\)s|:\w+'

PG_DDL = (
    'CREATE SCHEMA "{schema}"',
    'CREATE TABLE "{schema}".customer (id bigint PRIMARY KEY, name text NOT NULL)',
    'CREATE TABLE "{schema}".invoice (id bigint PRIMARY KEY, '
    'customer_id bigint REFERENCES "{schema}".customer(id), '
    'total numeric(12,2) NOT NULL, note text, __del_ts timestamp)',
)
SQLITE_DDL = (
    'CREATE TABLE sales.customer (id INTEGER PRIMARY KEY, name TEXT NOT NULL)',
    'CREATE TABLE sales.invoice (id INTEGER PRIMARY KEY, '
    'customer_id INTEGER REFERENCES customer(id), total NUMERIC NOT NULL, note TEXT, '
    '__del_ts TEXT)',
)


def declare_tables(schema_node):
    tables = schema_node.tables()
    customer = tables.table('customer', pkey='id')
    customer_columns = customer.columns()
    customer_columns.column('id', dtype='L')
    customer_columns.column('name', dtype='T', notnull=True)
    customer.virtual_columns().formulaColumn('selected_invoices', dtype='L', select=dict(
        table='sales.invoice', columns='COUNT(*)',
        where='$customer_id = #THIS.id AND $id IN :ids'))
    invoice = tables.table('invoice', pkey='id', x_logical_deletion_field='__del_ts')
    columns = invoice.columns()
    columns.column('id', dtype='L')
    columns.column('customer_id', dtype='L').relation(
        'sales.customer.id', foreign_key=True, x_name='customer')
    columns.column('total', dtype='N', size='12,2', notnull=True)
    columns.column('note', dtype='T')
    columns.column('__del_ts', dtype='DH')
    virtuals = invoice.virtual_columns()
    virtuals.formulaColumn('double_total', dtype='N', sql_formula='$total * 2')
    virtuals.aliasColumn('client_name', relation_path='@customer.name')


class Shop:
    """One seeded database on one backend, with the physical invoice table name."""

    def __init__(self, backend, db, invoice_sql):
        self.backend = backend
        self.db = db
        self.invoice_sql = invoice_sql

    def query(self, **options):
        return self.db.table('sales.invoice').query(**options)

    def ids(self, **options):
        options.setdefault('columns', '$id')
        options.setdefault('order_by', '$id')
        return [row['id'] for row in self.query(**options).fetch()]

    def direct_ids(self, sql, params=None):
        rows = self.db.execute(sql.format(invoice=self.invoice_sql), params).rows
        return sorted(row['id'] for row in rows)


def seed(db, invoice_sql):
    for row in CUSTOMERS:
        db.table('sales.customer').insert(dict(zip(('id', 'name'), row)))
    for invoice_id, customer_id, total, note, deleted in INVOICES:
        db.execute(f'INSERT INTO {invoice_sql} (id, customer_id, total, note, __del_ts) '
                   'VALUES (:id, :customer_id, :total, :note, :deleted)',
                   {'id': invoice_id, 'customer_id': customer_id, 'total': Decimal(total),
                    'note': note, 'deleted': deleted})
    db.commit()


@pytest.fixture(params=BACKENDS)
def shop(request, tmp_path):
    if request.param == 'sqlite':
        path = tmp_path / 'shop.db'

        class SqliteRecipe(SqlDatabaseConfig):
            def main(self, root):
                db = root.db('shop')
                db.connection(name=str(path), implementation='sqlite')
                declare_tables(db.schemas().schema('sales'))

        db = AsqueelDb(SqliteRecipe)
        try:
            for statement in SQLITE_DDL:
                db.execute(statement)
            db.commit()
            seed(db, 'sales.invoice')
            yield Shop('sqlite', db, 'sales.invoice')
        finally:
            db.rollback()
            db.close()
        return
    schema = 'query_completion_' + uuid4().hex
    dsn = postgres_dsn()

    class PostgresRecipe(SqlDatabaseConfig):
        def main(self, root):
            declare_tables(root.db('shop', conninfo=dsn).schemas().schema(
                'sales', x_sql_schema=schema))

    db = AsqueelDb(PostgresRecipe)
    try:
        for statement in PG_DDL:
            db.execute(CompiledQuery(statement.format(schema=schema)))
        db.commit()
        invoice_sql = f'"{schema}".invoice'
        seed(db, invoice_sql)
        yield Shop('postgresql', db, invoice_sql)
    finally:
        db.rollback()
        db.execute(CompiledQuery(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE'))
        db.commit()
        db.close()


def amount(value):
    """Backend-neutral numeric comparison: SQLite NUMERIC returns int/float."""
    return None if value is None else Decimal(str(value)).quantize(Decimal('0.01'))


def flat(sql):
    return re.sub(r'\s+', ' ', sql)


def in_lists(sql):
    """Placeholder groups of every ``IN (...)`` list in the SQL text."""
    return [re.findall(PLACEHOLDER, group)
            for group in re.findall(r'(?i)\bIN \(((?:\s*(?:%\(\w+\)s|:\w+)\s*,?)+)\)', flat(sql))]
