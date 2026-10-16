"""Execute string method references through the existing drivers on both dialects."""

from uuid import uuid4

import pytest

from asqueel import SqlDatabaseConfig, build_database
from tests.native_compiler.test_subquery_methods import declare, install
from tests.native_formulas.conftest import SQL_TYPES
from tests.native_support import postgres_dsn


@pytest.fixture(scope='module', params=['postgresql', 'sqlite'])
def db(request, tmp_path_factory):
    backend = request.param
    schema = 'sq_methods_' + uuid4().hex
    config = SqlDatabaseConfig()
    root = config.source.db('methods', implementation=backend)
    declare(root.packages().package('app', sqlschema=schema))
    root.connection(
        implementation=backend,
        **(
            {'dsn': postgres_dsn()}
            if backend == 'postgresql'
            else {'database': str(tmp_path_factory.mktemp('sq_methods') / 'test.db')}
        ),
    )
    with build_database(config) as db:
        install(db)
        quote = db.dialect.quote_identifier
        try:
            if backend == 'postgresql':
                db.execute('CREATE SCHEMA ' + quote(schema))
            for table in db.model.tables.values():
                columns = ','.join(
                    f'{quote(c.sqlname)} {SQL_TYPES.get(c.dtype, "TEXT")}'
                    for c in table.columns.values()

                )
                db.execute(f'CREATE TABLE {quote(schema)}.{quote(table.sqlname)} ({columns})')
            db.execute(f'INSERT INTO {quote(schema)}.app_owner(id) VALUES (1),(2)')
            db.execute(
                f'INSERT INTO {quote(schema)}.app_line(id,owner_id,amount) VALUES (1,1,10),(2,1,20)'
            )
            db.commit()
            yield db
        finally:
            db.rollback()
            if backend == 'postgresql':
                db.execute('DROP SCHEMA ' + quote(schema) + ' CASCADE')
                db.commit()


def test_values_nested_scope_and_query_reuse(db):
    columns = '$scalar,$alias,$named,$present,$nested,$from_formula,$collection_None,:factor AS caller'
    if db.dialect.name == 'sqlite':
        columns = columns.replace('$present,', '')
    query = db.table('app.owner').query(
        columns,
        where='$id=:id',
        id=1,
        factor=19,
    )
    expected = dict(
        scalar=140,
        alias=140,
        named=283,
        present=True,
        nested=220,
        from_formula=145,
        collection_None=10,
        caller=19,
    )
    if db.dialect.name == 'sqlite':
        expected.pop('present', None)
    assert [dict(row) for row in query.fetch()] == [expected]
    with db.tempEnv(factor=23):
        assert [dict(row) for row in query.fetch()] == [
            {
                **expected,
                'scalar': 460,
                'alias': 460,
                'named': 923,
                'nested': 460,
                'from_formula': 465,
            }
        ]
    assert [dict(row) for row in query.fetch()] == [expected]


def test_related_owner_and_no_rows(db):
    row = (
        db.table('app.line')
        .query('@owner_id.scalar AS result,@owner_id.from_formula AS supplied', where='$id=1')
        .fetch()[0]
    )
    assert dict(row) == dict(result=220, supplied=225)
    query = db.table('app.owner').query('$scalar,$present', where='$id=2')
    assert [dict(row) for row in query.fetch()] == [dict(scalar=None, present=False)]


def test_json_method_return_value_and_distinct(db):
    if db.dialect.name == 'sqlite':
        from asqueel.contracts import UnsupportedFeatureError

        with pytest.raises(UnsupportedFeatureError, match='SQLite does not support'):
            db.table('app.owner').query('$collection_json').compiled
    else:
        assert [dict(row) for row in db.table('app.owner').query(
            '$collection_json', where='$id=1', distinct=True
        ).fetch()] == [dict(collection_json=[dict(amount=10)])]
