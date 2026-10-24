"""db.adapter SQL functions as legacy: string_agg, unaccentFormula, mask_field_sql, ageAtDate.

Expected SQL is the output of the legacy adapters at GenroPy 95da66ee.
"""
from datetime import date

import pytest

from asqueel import SqlDatabaseConfig, UnsupportedFeatureError, AsqueelDb
from asqueel.adapters.postgres import SqlDbAdapter as PostgresAdapter
from asqueel.adapters.sqlite import SqlDbAdapter as SqliteAdapter
from tests.unit_of_work import empty_database
from tests.native_support import postgres_dsn
from tests.package_layout_support import write_layout


BACKENDS = ['sqlite', pytest.param('postgres', marks=pytest.mark.postgresql)]


@pytest.fixture(params=BACKENDS)
def db(request):
    database = (empty_database(postgres_dsn(), implementation='postgres') if request.param == 'postgres'
                else empty_database(':memory:', implementation='sqlite'))
    try:
        yield database
    finally:
        database.rollback()
        database.closeConnection()


def value(db, expression, params=None):
    return db.execute(f'SELECT {expression} AS value', params or {}).fetchall()[0]['value']


def test_string_agg_as_legacy():
    assert PostgresAdapter(None).string_agg('$name', ', ') == "string_agg($name,', ')"
    assert SqliteAdapter(None).string_agg('$name', ', ') == "group_concat($name,', ')"
    assert PostgresAdapter(None).string_agg('$name', "'") == "string_agg($name,'''')"


def test_string_agg_runs(db):
    rows = "SELECT 'a' AS name UNION ALL SELECT 'b'"
    assert value(db, f"(SELECT {db.adapter.string_agg('t.name', '-')} FROM ({rows}) AS t)") in ('a-b', 'b-a')


def test_unaccent_formula_as_legacy():
    assert PostgresAdapter(None).unaccentFormula('name') == 'unaccent($name)'
    assert PostgresAdapter(None).unaccentFormula('$name') == 'unaccent($name)'
    assert PostgresAdapter(None).unaccentFormula('@customer_id.name') == 'unaccent(@customer_id.name)'
    assert SqliteAdapter(None).unaccentFormula('$name') == '$name'


def test_age_at_date_as_legacy():
    adapter = PostgresAdapter(None)
    assert adapter.ageAtDate('$born') == (
        'CAST((EXTRACT (EPOCH FROM(cast(:env_workdate as date))) -  \n'
        '                        EXTRACT (EPOCH FROM($born)))/86400 as bigint)')
    assert adapter.ageAtDate('$born', 'refdate', 'year') == (
        'CAST((EXTRACT (EPOCH FROM(cast(:refdate as date))) -  \n'
        '                        EXTRACT (EPOCH FROM($born)))/31536000 as bigint)')
    with pytest.raises(ValueError, match='timeUnit'):
        adapter.ageAtDate('$born', timeUnit='fortnight')


def test_age_at_date_raises_on_sqlite():
    with pytest.raises(UnsupportedFeatureError, match='ageAtDate'):
        SqliteAdapter(None).ageAtDate('$born')


@pytest.mark.postgresql
def test_age_at_date_runs_on_postgres():
    db = empty_database(postgres_dsn(), implementation='postgres')
    try:
        age = db.adapter.ageAtDate("DATE '2026-01-01'", 'refdate')
        assert value(db, age, {'refdate': date(2026, 1, 11)}) == 10
        with db.tempEnv(workdate=date(2027, 1, 1)):
            assert value(db, db.adapter.ageAtDate("DATE '2026-01-01'", timeUnit='year')) == 1
    finally:
        db.rollback()
        db.closeConnection()


@pytest.mark.parametrize(('field', 'mode', 'placeholder', 'expected'), [
    ("'johndoe@example.com'", 'email', '*', 'jo*****@example.com'),
    ("'nomail'", 'email', '*', 'nomail'),
    ("'4111111111111111'", 'creditcard', '*', '************1111'),
    ("'1234'", 'creditcard', '*', '1234'),
    ("'+391234567890'", 'phone', '#', '+39#######890'),
    ("'ABCDEFGHIJ'", '3-2', '*', 'ABC*****IJ'),
    ("'ABCDE'", '3-2', '*', 'ABCDE'),
    ("'ABCDEFGHIJ'", '2-4', "'", "AB''''GHIJ"),
])
def test_mask_field_sql_runs(db, field, mode, placeholder, expected):
    assert value(db, db.adapter.mask_field_sql(field, mode=mode, placeholder=placeholder)) == expected


@pytest.mark.parametrize('adapter', [PostgresAdapter(None), SqliteAdapter(None)], ids=['postgres', 'sqlite'])
@pytest.mark.parametrize('mode', ['2', 'a-b', '1-2-3', ''])
def test_mask_field_sql_rejects_an_invalid_mode(adapter, mode):
    with pytest.raises(ValueError, match='mask_field_sql'):
        adapter.mask_field_sql('$code', mode=mode)


CUSTOMER = '''
class Table:
    def config_db(self, pkg):
        customer = pkg.table('customer', pkey='id')
        customer.column('id', dtype='L')
        customer.column('email')
        customer.formulaColumn('masked_email', sql_formula=True)

    def sql_formula_masked_email(self, attr):
        return self.db.adapter.mask_field_sql('$email', mode='email')
'''


def test_table_formula_reaches_the_adapter(tmp_path):
    config = SqlDatabaseConfig()
    db = config.source.db('shop')
    db.connection(name=str(tmp_path / 'shop.db'), implementation='sqlite')
    db.packages().package('app', path=write_layout(tmp_path / 'app', customer=CUSTOMER))
    database = AsqueelDb(config)
    try:
        database.execute('CREATE TABLE "app_customer" ("id" BIGINT, "email" TEXT)')
        database.execute("INSERT INTO \"app_customer\" VALUES (1, 'ada@example.com')")
        rows = database.table('app.customer').query('$masked_email').fetch()
        assert [row['masked_email'] for row in rows] == ['ad*@example.com']
        database.rollback()
    finally:
        database.closeConnection()
