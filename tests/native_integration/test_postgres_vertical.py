"""Cross-component acceptance tests, independent of the migration facade."""
import os
from uuid import uuid4

import psycopg
from psycopg import sql
import pytest

from genro_sql import SqlBuilder
from genro_sql.compiler import PostgresCompiler
from genro_sql.importers import inspect_postgres
from genro_sql.model import resolve_model
from genro_sql.runtime import PostgresDatabase


pytestmark = pytest.mark.postgresql


@pytest.fixture
def native_database():
    params = {
        'host': os.environ.get('GNR_TEST_PG_HOST', '127.0.0.1'),
        'port': os.environ.get('GNR_TEST_PG_PORT', '5432'),
        'user': os.environ.get('GNR_TEST_PG_USER', 'postgres'),
        'dbname': 'postgres',
        'connect_timeout': 3,
    }
    if os.environ.get('GNR_TEST_PG_PASSWORD'):
        params['password'] = os.environ['GNR_TEST_PG_PASSWORD']
    try:
        connection = psycopg.connect(**params, autocommit=True)
    except psycopg.OperationalError as exc:
        pytest.fail(f'PostgreSQL acceptance tests require a reachable test server: {exc}')
    schema = 'v1_acceptance_' + uuid4().hex
    with connection:
        connection.execute(sql.SQL('CREATE SCHEMA {}').format(sql.Identifier(schema)))
        try:
            connection.execute(sql.SQL('''
                CREATE TABLE {}."crm_customer" (
                    id bigint PRIMARY KEY, "display name" text NOT NULL
                )
            ''').format(sql.Identifier(schema)))
            connection.execute(sql.SQL('''
                CREATE TABLE {}."crm_invoice" (
                    id bigint PRIMARY KEY, customer_id bigint,
                    total numeric, CONSTRAINT customer_fk FOREIGN KEY (customer_id)
                    REFERENCES {}."crm_customer"(id)
                )
            ''').format(sql.Identifier(schema), sql.Identifier(schema)))
            yield params, schema, connection
        finally:
            connection.execute(sql.SQL('DROP SCHEMA {} CASCADE').format(sql.Identifier(schema)))


def recipe(schema):
    builder = SqlBuilder()
    tables = builder.source.db('acceptance').schemas().schema(
        'crm', x_sql_schema=schema, x_sql_prefix=True,
    ).tables()
    customer = tables.table('customer', pkey='id').columns()
    customer.column('id', dtype='L')
    customer.column('name', dtype='T', notnull=True, x_sql_name='display name',
                    x_ui={'label': 'Cliente'})
    invoice = tables.table('invoice', pkey='id')
    columns = invoice.columns()
    columns.column('id', dtype='L')
    columns.column('customer_id', dtype='L').relation('crm.customer.id', foreign_key=True)
    columns.column('total', dtype='N')
    invoice.virtual_columns().formulaColumn('double_total', sql_formula='$total * 2', dtype='N')
    return builder


def test_native_model_compiler_runtime_and_import(native_database):
    params, schema, connection = native_database
    model = resolve_model(recipe(schema), ui={'crm.customer.name': {'placeholder': 'Nome'}})
    compiler = PostgresCompiler(model)

    def scenario():
        with PostgresDatabase(connect_kwargs=params) as db:
            with db.transaction() as tx:
                customer = tx.execute(compiler.insert('crm.customer', {
                    'id': 1, 'name': "L'impresa 50%",
                }))
                assert customer.rows[0]['name'] == "L'impresa 50%"
                tx.execute(compiler.insert('crm.invoice', {
                    'id': 11, 'customer_id': 1, 'total': 10,
                }))
                tx.execute(compiler.insert('crm.invoice', {
                    'id': 12, 'customer_id': None, 'total': None,
                }))
            query = compiler.select(
                'crm.invoice', columns='$id, @customer_id.name AS customer, $double_total',
                where='$id >= :start', params={'start': 11}, order_by='$id',
            )
            result = db.execute(query)
            assert [(r['id'], r['customer'], r['double_total']) for r in result.rows] == [
                (11, "L'impresa 50%", 20), (12, None, None),
            ]
            assert result.columns[1].ui['label'] == 'Cliente'
            assert result.columns[1].ui['placeholder'] == 'Nome'
            updated = db.execute(compiler.update(
                'crm.invoice', {'total': 15}, where='$id = :id', params={'id': 11},
            ))
            assert updated.rows[0]['total'] == 15
            with pytest.raises(psycopg.errors.UniqueViolation):
                with db.transaction() as tx:
                    tx.execute(compiler.insert('crm.customer', {'id': 2, 'name': 'Rollback'}))
                    tx.execute(compiler.insert('crm.customer', {'id': 1, 'name': 'Duplicate'}))
            assert not (db.execute(compiler.select(
                'crm.customer', where='$id = :id', params={'id': 2},
            ))).rows
            deleted = db.execute(compiler.delete(
                'crm.invoice', where='$id = :id', params={'id': 12},
            ))
            assert deleted.rowcount == 1
    scenario()
    imported = inspect_postgres(connection, [schema], ui={
        f'{schema}.crm_customer.display name': {'label': 'Cliente'},
    })
    assert not imported.warnings
    assert imported.model.table(f'{schema}.crm_customer').columns['display name'].ui['label'] == 'Cliente'
    query = PostgresCompiler(imported.model).select(f'{schema}.crm_invoice', columns='$id, $total')
    with connection.cursor() as cursor:
        cursor.execute(query.sql, dict(query.params))
        assert cursor.fetchall() == [(11, 15)]



def test_python_error_rolls_back_transaction_and_database_remains_usable(native_database):
    params, schema, connection = native_database
    compiler = PostgresCompiler(resolve_model(recipe(schema)))
    with PostgresDatabase(connect_kwargs=params) as db:
        with pytest.raises(RuntimeError, match='abort transaction'):
            with db.transaction() as tx:
                tx.execute(compiler.insert('crm.customer', {'id': 9, 'name': 'Aborted'}))
                raise RuntimeError('abort transaction')
        assert not db.execute(compiler.select('crm.customer')).rows
        db.execute(compiler.insert('crm.customer', {'id': 10, 'name': 'Committed'}))
        assert db.execute(compiler.select('crm.customer', columns='$id')).rows == [{'id': 10}]
    assert connection.execute(sql.SQL('SELECT id FROM {}.crm_customer').format(
        sql.Identifier(schema))).fetchall() == [(10,)]


def test_separate_database_transactions_keep_independent_commit_and_rollback(native_database):
    params, schema, _ = native_database
    compiler = PostgresCompiler(resolve_model(recipe(schema)))
    with PostgresDatabase(connect_kwargs=params) as first, PostgresDatabase(connect_kwargs=params) as second:
        with pytest.raises(RuntimeError, match='abort first'):
            with first.transaction() as tx:
                tx.execute(compiler.insert('crm.customer', {'id': 31, 'name': 'Abort'}))
                second.execute(compiler.insert('crm.customer', {'id': 32, 'name': 'Commit'}))
                raise RuntimeError('abort first')
        assert first.execute(compiler.select('crm.customer', columns='$id')).rows == [{'id': 32}]
