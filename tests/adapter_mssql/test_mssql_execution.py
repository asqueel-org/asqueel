"""The SQL Server adapter against a live server: migration, queries, writes and transactions."""
from datetime import date
from decimal import Decimal

import pytest

from asqueel import AsqueelDb, SqlDatabaseConfig
from asqueel.compiler import QueryCompiler
from asqueel.contracts import CompiledQuery, UnsupportedFeatureError
from asqueel.adapters.mssql import SqlDbAdapter as MssqlAdapter
from asqueel.errors import MigrationError
from asqueel.write_compiler import WriteCompiler
from tests.unit_of_work import completed

pymssql = pytest.importorskip('pymssql')
pytestmark = pytest.mark.mssql


def recipe(params):
    config = SqlDatabaseConfig()
    db = config.source.db('shop', implementation='mssql')
    db.connection(name=params['dbname'], host=params['host'], port=params['port'],
                  user=params['user'], password=params['password'])
    pkg = db.packages().package('crm', sqlschema='crm')
    customer = pkg.table('customer', pkey='id', order_by='$id')
    customer.column('id', dtype='L')
    customer.column('name', dtype='T', sqlname='display name')
    customer.column('vip', dtype='B')
    customer.column('born', dtype='D')
    customer.column('amount', dtype='N', size='10,2')
    customer.formulaColumn('label', sql_formula="CONCAT($name, '!')", dtype='T')
    invoice = pkg.table('invoice', pkey='id')
    invoice.column('id', dtype='L')
    invoice.column('customer_id', dtype='L').relation('crm.customer.id', foreign_key=True)
    invoice.column('total', dtype='N', size='12,2')
    return config


@pytest.fixture
def database(mssql_database):
    db = AsqueelDb(recipe(mssql_database)).session()
    try:
        db.migrate()
        db.commit()
        yield db
    finally:
        db.shared.close()


def rows(query):
    return [dict(row) for row in query.fetch()]


def test_migration_creates_the_model_and_converges(database):
    assert database.migration_plan()['sql'].strip() == ''


@pytest.mark.xfail(strict=True, reason='asqueel-org/asqueel-migration#34: a numeric column without size never converges')
def test_numeric_without_size_converges(mssql_database):
    config = recipe(mssql_database)
    config.source.get_node('db.packages.crm.tables.invoice').value.column('rate', dtype='N')
    db = AsqueelDb(config)
    try:
        db.migrate()
    finally:
        db.close()


def test_queries_and_writes(database):
    customer = database.table('crm.customer')
    customer.insert({'id': 1, 'name': "L'impresa 50%", 'vip': True, 'amount': Decimal('3.5'),
                     'born': date(2000, 1, 1)})
    customer.insert({'id': 2, 'name': 'bob', 'vip': False})
    customer.insert({'id': 3, 'name': 'Cy', 'vip': None})
    database.table('crm.invoice').insert({'id': 10, 'customer_id': 1, 'total': 5})
    database.commit()
    assert rows(customer.query(columns='$id,$name,$vip,$amount,$born,$label', where='$id = 1')) == [
        {'id': 1, 'name': "L'impresa 50%", 'vip': True, 'amount': Decimal('3.50'),
         'born': date(2000, 1, 1), 'label': "L'impresa 50%!"}]
    assert rows(customer.query(columns='$id', where='$vip IS NOT TRUE')) == [{'id': 2}, {'id': 3}]
    assert rows(customer.query(columns='$id', where='$name ILIKE :n', n='B%')) == [{'id': 2}]
    assert rows(customer.query(columns='$id', where='$id IN :ids', ids=[1, 3])) == [{'id': 1}, {'id': 3}]
    assert rows(customer.query(columns='$id', where='$id IN :ids', ids=[])) == []
    assert rows(customer.query(columns='$id', where='$id NOT IN :ids', ids=[])) == [{'id': 1}, {'id': 2}, {'id': 3}]
    assert rows(customer.query(columns='$id', limit=2)) == [{'id': 1}, {'id': 2}]
    assert rows(customer.query(columns='$id', limit=1, offset=1)) == [{'id': 2}]
    assert rows(customer.query(columns='$id', offset=2)) == [{'id': 3}]
    assert rows(database.table('crm.invoice').query(columns='$id,@customer_id.name AS cname')) == [
        {'id': 10, 'cname': "L'impresa 50%"}]
    assert rows(customer.query(columns='$id', where='$id = 1', for_update=True)) == [{'id': 1}]
    database.rollback()
    customer.update({'id': 2, 'name': 'Bob'})
    customer.delete({'id': 3})
    database.commit()
    assert rows(customer.query(columns='$id,$name')) == [{'id': 1, 'name': "L'impresa 50%"},
                                                         {'id': 2, 'name': 'Bob'}]


def test_explicit_pipeline(database):
    adapter = MssqlAdapter(None)
    model = database.model
    compiler = QueryCompiler(model, adapter)
    writer = WriteCompiler(adapter)
    database.execute(writer.insert(model.table('crm.customer'), {'id': 1, 'name': "L'impresa 50%"},
                                   database.environment_snapshot()))
    # pymssql leaves a literal % as written: the author does not double it.
    plan = compiler.plan_select('crm.customer', columns="$name, '50%' AS pct",
                                where='$id = :id', sqlparams={'id': 1})
    prepared = compiler.compile_plan(plan)
    assert '%(id)s' in prepared.sql
    assert [dict(row) for row in database.execute(prepared).fetchall()] == [
        {'name': "L'impresa 50%", 'pct': '50%'}]
    assert database.execute(CompiledQuery('SELECT 1 AS ok', dialect='mssql', binding='pymssql_named'))
    database.rollback()


def test_duplicate_key_rolls_back_and_the_database_remains_usable(database):
    customer = database.table('crm.customer')
    with pytest.raises(pymssql.IntegrityError):
        with completed(database):
            customer.insert({'id': 1, 'name': 'First'})
            customer.insert({'id': 1, 'name': 'Duplicate'})
    assert rows(customer.query(columns='$id')) == []
    customer.insert({'id': 2, 'name': 'Committed'})
    database.commit()
    assert rows(customer.query(columns='$id')) == [{'id': 2}]


def test_formula_functions_execute(database):
    adapter = database.adapter
    joined = adapter.string_join(["'a'", 'NULL', "''", "'b'"], '-')
    single = adapter.string_join(['NULL'], '-')
    age = adapter.ageAtDate("CAST('2026-01-01' AS date)", 'at', 'day')
    row = database.execute(f'SELECT {joined} AS joined, {single} AS single, {age} AS age',
                           {'at': date(2026, 1, 11)}).fetchall()[0]
    assert (row['joined'], row['single'], row['age']) == ('a--b', '', 10)
    database.analyze()
    database.rollback()


def test_percent_in_literals_and_comments_runs(database):
    row = database.execute("SELECT 'a%' AS text, :v AS v /* 50% */ WHERE 'abc' LIKE 'a%' -- 1%\n",
                           {'v': 1}).fetchall()[0]
    assert (row['text'], row['v']) == ('a%', 1)
    database.rollback()


def test_unsupported_maintenance_raises(database):
    with pytest.raises(UnsupportedFeatureError):
        database.setConstraintsDeferred()
    with pytest.raises(UnsupportedFeatureError):
        database.vacuum()


def test_migration_needs_a_database_name(mssql_params):
    config = SqlDatabaseConfig()
    config.source.db('shop', implementation='mssql', connect_kwargs=dict(mssql_params)).packages().package(
        'crm', sqlschema='crm').table('item', pkey='id').column('id', dtype='L')
    db = AsqueelDb(config)
    try:
        with pytest.raises(MigrationError, match='connection.name'):
            db.migration_plan()
    finally:
        db.close()
