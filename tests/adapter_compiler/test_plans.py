"""Compiler contracts proven independently of PostgreSQL SQL and binding syntax."""
import pytest

from asqueel import SqlDatabaseConfig, AsqueelDb
from asqueel.write_compiler import WriteCompiler


@pytest.fixture
def db():
    config = SqlDatabaseConfig()
    pkg = config.source.db('plans', implementation='postgres').packages().package('app', sqlschema='physical')
    customer = pkg.table('customer', pkey='id')
    customer.column('id')
    customer.column('name')
    invoice = pkg.table('invoice', pkey='id', sqlname='Bills%')
    invoice.column('id', dtype='L', sqlname='ID%', x_identity='invoice-id')
    invoice.column('customer_id').relation('app.customer.id')
    invoice.column('amount', dtype='N')
    invoice.formulaColumn('double', '$amount * 2', dtype='N')
    database = AsqueelDb(config)
    try:
        yield database
    finally:
        database.closeConnection()


def writer(db):
    return WriteCompiler(db.adapter)


def test_write_plans_keep_assignments_and_parameters_structured(db):
    table = db.table('app.invoice').model
    updated = writer(db).update(table, {'id': 4}, {}, pkey=1)
    assert dict(updated.params) == {'id': 4, '__pkey__0': 1}
    assert updated.sql.startswith('UPDATE "physical"."Bills%')
    assert 'DEFAULT VALUES' in writer(db).insert(table, {}, {}).sql
    assert 'RETURNING' not in writer(db).delete(table, {'id': 4}, {}).sql


def test_postgres_facade_preserves_exact_compiled_sql_and_legacy_quoting(db):
    selected = db.compiler.select('app.customer', '$id', where='$id=:id', sqlparams={'id': 4}, limit=1)
    assert selected.sql == ('SELECT "t0"."id" AS "id"\n FROM "physical"."app_customer" AS "t0"\n'
                            'WHERE ("t0"."id"=%(id)s)\nLIMIT 1')
    inserted = writer(db).insert(db.table('app.customer').model, {'id': 4}, {})
    assert inserted.sql == 'INSERT INTO "physical"."app_customer"("id") VALUES (%(id)s)'
    assert db.adapter.adaptSqlName('a"50%') == '"a""50%"'
    with pytest.raises(ValueError, match='63 UTF-8 bytes'):
        db.adapter.adaptSqlName('x' * 64)


@pytest.mark.xfail(strict=True, reason="asqueel#19: a '%' in a physical table/column name is not escaped for psycopg")
def test_compiled_sql_escapes_percent_in_physical_names(db):
    selected = db.compiler.select('app.invoice', '$id', where='$id=:id', sqlparams={'id': 4}, limit=1)
    assert selected.sql == ('SELECT "t0"."ID%%" AS "id"\n FROM "physical"."Bills%%" AS "t0"\n'
                            'WHERE ("t0"."ID%%"=%(id)s)\nLIMIT 1')
    inserted = writer(db).insert(db.table('app.invoice').model, {'id': 4}, {})
    assert inserted.sql == 'INSERT INTO "physical"."Bills%%"("ID%%") VALUES (%(id)s)'
