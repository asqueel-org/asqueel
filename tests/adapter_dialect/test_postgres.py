"""PostgreSQL write and SELECT rendering on the hierarchical model, without a connection."""
import pytest

from asqueel import AsqueelDb, SqlDatabaseConfig
from asqueel.contracts import UnsupportedFeatureError
from asqueel.adapters.postgres import SqlDbAdapter as PostgresAdapter
from asqueel.write_compiler import WriteCompiler


@pytest.fixture
def db():
    source = SqlDatabaseConfig()
    pkg = source.source.db('render', implementation='postgres').packages().package('s', sqlschema='s', sqlprefix=False)
    table = pkg.table('t', pkey='id')
    table.column('id', dtype='I')
    table.column('amount', dtype='N')
    table.column('first', dtype='I', sql_value='1 -- value')
    table.column('second', dtype='I')
    ticket = pkg.table('ticket', pkey='id')
    ticket.column('id', dtype='serial')
    pkg.table('nokey').column('amount', dtype='N')
    database = AsqueelDb(source)
    try:
        yield database
    finally:
        database.closeConnection()


def model(db, name):
    return db.table(f's.{name}').model


@pytest.mark.parametrize(('operation', 'record', 'expected'), [
    ('insert', {'amount': 3}, 'INSERT INTO "s"."t"("amount","first") VALUES (%(amount)s,1 -- value\n) RETURNING "first" AS "first"'),
    ('delete', {'id': 4}, 'DELETE FROM "s"."t" WHERE "id"=%(__pkey__0)s'),
])
def test_dml_rendering(db, operation, record, expected):
    compiled = getattr(db.write_compiler, operation)(model(db, 't'), record, {})
    assert compiled.sql == expected


def test_default_values_and_returning_are_independent_capabilities(db):
    ticket = model(db, 'ticket')
    assert db.write_compiler.insert(ticket, {}, {}).sql == 'INSERT INTO "s"."ticket" DEFAULT VALUES RETURNING "id" AS "id"'
    adapter = PostgresAdapter(db, capabilities=PostgresAdapter.capabilities - {'returning_insert'})
    assert WriteCompiler(adapter).insert(ticket, {}, {}).sql == 'INSERT INTO "s"."ticket" DEFAULT VALUES'


@pytest.mark.xfail(strict=True, reason='asqueel#21: WriteCompiler does not enforce the adapter capabilities')
def test_missing_write_capabilities_are_rejected(db):
    ticket = model(db, 'ticket')
    adapter = PostgresAdapter(db, capabilities=PostgresAdapter.capabilities - {'returning_insert'})
    with pytest.raises(UnsupportedFeatureError, match='returning_insert'):
        WriteCompiler(adapter).insert(ticket, {}, {})
    with pytest.raises(UnsupportedFeatureError, match='default_values'):
        WriteCompiler(PostgresAdapter(db, capabilities=frozenset({'insert'}))).insert(ticket, {}, {})


def test_malformed_statements_are_rejected(db):
    with pytest.raises(ValueError, match='at least one column'):
        db.write_compiler.update(model(db, 'ticket'), {'unknown': 1}, {}, pkey=1)
    with pytest.raises(ValueError, match='no primary key'):
        db.write_compiler.delete(model(db, 'nokey'), {'amount': 1}, {})
    for options in ({'limit': -1}, {'limit': True}, {'columns': ' '}):
        with pytest.raises(ValueError):
            PostgresAdapter(None).compileSql(**{'maintable': '"s"."t"', 'columns': '1', **options})


def test_clauses_have_fixed_separators_without_repairing_expression_text(db):
    select = PostgresAdapter(None).compileSql('"s"."t"', '1', joins=['LEFT JOIN "s"."t" AS "t1" ON TRUE -- join'],
                                           where='TRUE -- predicate', order_by='1 -- order', limit=1)
    assert 'TRUE -- join\nWHERE TRUE -- predicate\nORDER BY 1 -- order\nLIMIT 1' in select
    table = model(db, 't')
    # A sql_value is always emitted, so a record key set to None places it before 'second'.
    update = db.write_compiler.update(table, {'id': 1, 'first': None, 'second': 2}, {}).sql
    assert '"first"=1 -- value\n,"second"=%(second)s WHERE "id"=%(__pkey__0)s' in update
    insert = db.write_compiler.insert(table, {'id': 1, 'first': None, 'second': 2}, {}).sql
    assert 'VALUES (%(id)s,1 -- value\n,%(second)s)' in insert
