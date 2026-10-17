"""Cross-component acceptance tests, independent of the migration facade."""
from tests.unit_of_work import completed
import os
from uuid import uuid4

import psycopg
from psycopg import sql
import pytest

from asqueel import SqlDatabaseConfig
from asqueel.compiler import PostgresCompiler
from asqueel.adapters.postgres import SqlDbAdapter as PostgresAdapter
from asqueel.importers import inspect_postgres
from asqueel.model import resolve_model
from asqueel.runtime import PostgresDatabase
from asqueel.write_compiler import WriteCompiler


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
    config = SqlDatabaseConfig()
    pkg = config.source.db('acceptance').packages().package('crm', sqlschema=schema, sqlprefix=True)
    customer = pkg.table('customer', pkey='id')
    customer.column('id', dtype='L')
    customer.column('name', dtype='T', notnull=True, sqlname='display name',
                    x_ui_label='Cliente', x_ui_placeholder='Nome')
    invoice = pkg.table('invoice', pkey='id')
    invoice.column('id', dtype='L')
    invoice.column('customer_id', dtype='L').relation('crm.customer.id', foreign_key=True)
    invoice.column('total', dtype='N')
    invoice.formulaColumn('double_total', sql_formula='$total * 2', dtype='N')
    return config


def writer():
    return WriteCompiler(PostgresAdapter(None))


def test_native_model_compiler_runtime_and_import(native_database):
    params, schema, connection = native_database
    model = resolve_model(recipe(schema))
    compiler = PostgresCompiler(model)
    write = writer()

    def scenario():
        with PostgresDatabase(connect_kwargs=params) as db:
            with completed(db) as tx:
                tx.execute(write.insert(model.table('crm.customer'), {
                    'id': 1, 'name': "L'impresa 50%",
                }, {}))
                tx.execute(write.insert(model.table('crm.invoice'), {
                    'id': 11, 'customer_id': 1, 'total': 10,
                }, {}))
                tx.execute(write.insert(model.table('crm.invoice'), {
                    'id': 12, 'customer_id': None, 'total': None,
                }, {}))
            assert db.execute(compiler.select(
                'crm.customer', columns='$name', where='$id = :id', sqlparams={'id': 1},
            )).rows[0]['name'] == "L'impresa 50%"
            query = compiler.select(
                'crm.invoice', columns='$id, @customer_id.name AS customer, $double_total',
                where='$id >= :start', sqlparams={'start': 11}, order_by='$id',
            )
            result = db.execute(query)
            assert [(r['id'], r['customer'], r['double_total']) for r in result.rows] == [
                (11, "L'impresa 50%", 20), (12, None, None),
            ]
            assert result.columns[1].ui['label'] == 'Cliente'
            assert result.columns[1].ui['placeholder'] == 'Nome'
            updated = db.execute(write.update(model.table('crm.invoice'), {'id': 11, 'total': 15}, {}))
            assert updated.rowcount == 1
            assert db.execute(compiler.select(
                'crm.invoice', columns='$total', where='$id = :id', sqlparams={'id': 11},
            )).rows[0]['total'] == 15
            db.commit()
            with pytest.raises(psycopg.errors.UniqueViolation):
                with completed(db) as tx:
                    tx.execute(write.insert(model.table('crm.customer'), {'id': 2, 'name': 'Rollback'}, {}))
                    tx.execute(write.insert(model.table('crm.customer'), {'id': 1, 'name': 'Duplicate'}, {}))
            assert not (db.execute(compiler.select(
                'crm.customer', where='$id = :id', sqlparams={'id': 2},
            ))).rows
            deleted = db.execute(write.delete(model.table('crm.invoice'), {'id': 12}, {}))
            assert deleted.rowcount == 1
            db.commit()
    scenario()
    imported = inspect_postgres(connection, [schema], ui={
        f'{schema}.crm_customer.display name': {'label': 'Cliente'},
    })
    assert not imported.warnings
    assert imported.model.table(f'{schema}.crm_customer').columns['display name'].ui['label'] == 'Cliente'


@pytest.mark.xfail(strict=True, reason='asqueel#22: inspect_postgres returns the removed contracts.ResolvedModel, '
                                       'which the compiler rejects')
def test_imported_model_compiles_selects(native_database):
    _, schema, connection = native_database
    connection.execute(sql.SQL("INSERT INTO {}.crm_customer VALUES (1, 'x')").format(sql.Identifier(schema)))
    connection.execute(sql.SQL('INSERT INTO {}.crm_invoice VALUES (11, 1, 15)').format(sql.Identifier(schema)))
    imported = inspect_postgres(connection, [schema])
    query = PostgresCompiler(imported.model).select(f'{schema}.crm_invoice', columns='$id, $total')
    with connection.cursor() as cursor:
        cursor.execute(query.sql, dict(query.params))
        assert cursor.fetchall() == [(11, 15)]


def test_python_error_rolls_back_transaction_and_database_remains_usable(native_database):
    params, schema, connection = native_database
    model = resolve_model(recipe(schema))
    compiler, customer = PostgresCompiler(model), model.table('crm.customer')
    with PostgresDatabase(connect_kwargs=params) as db:
        with pytest.raises(RuntimeError, match='abort transaction'):
            with completed(db) as tx:
                tx.execute(writer().insert(customer, {'id': 9, 'name': 'Aborted'}, {}))
                raise RuntimeError('abort transaction')
        assert not db.execute(compiler.select('crm.customer')).rows
        db.execute(writer().insert(customer, {'id': 10, 'name': 'Committed'}, {}))
        assert [dict(row) for row in db.execute(compiler.select('crm.customer', columns='$id')).rows] == [{'id': 10}]
        db.commit()
    assert connection.execute(sql.SQL('SELECT id FROM {}.crm_customer').format(
        sql.Identifier(schema))).fetchall() == [(10,)]


def test_separate_database_transactions_keep_independent_commit_and_rollback(native_database):
    params, schema, _ = native_database
    model = resolve_model(recipe(schema))
    compiler, customer = PostgresCompiler(model), model.table('crm.customer')
    with PostgresDatabase(connect_kwargs=params) as first, PostgresDatabase(connect_kwargs=params) as second:
        with pytest.raises(RuntimeError, match='abort first'):
            with completed(first) as tx:
                tx.execute(writer().insert(customer, {'id': 31, 'name': 'Abort'}, {}))
                second.execute(writer().insert(customer, {'id': 32, 'name': 'Commit'}, {}))
                second.commit()
                raise RuntimeError('abort first')
        assert [dict(row) for row in first.execute(compiler.select('crm.customer', columns='$id')).rows] == [{'id': 32}]
