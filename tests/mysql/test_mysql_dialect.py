"""MySQL write and SELECT rendering on the hierarchical model, without a connection."""
import pytest

from asqueel import AsqueelDb, SqlDatabaseConfig
from asqueel.contracts import UnsupportedFeatureError
from asqueel.adapters.mysql import SqlDbAdapter as MysqlAdapter
from asqueel._sql_parameters import substitute_parameters


@pytest.fixture
def db():
    source = SqlDatabaseConfig()
    pkg = source.source.db('render', implementation='mysql').packages().package('s', sqlschema='s', sqlprefix=False)
    table = pkg.table('t', pkey='id')
    table.column('id', dtype='I')
    table.column('amount', dtype='N')
    table.column('first', dtype='I', sql_value='1 -- value')
    table.column('second', dtype='I')
    table.column('name', dtype='T')
    ticket = pkg.table('ticket', pkey='id')
    ticket.column('id', dtype='serial')
    database = AsqueelDb(source)
    try:
        yield database
    finally:
        database.closeConnection()


def model(db, name):
    return db.table(f's.{name}').model


def test_adapter_profile(db):
    assert db.adapter.dialect == 'mysql'
    assert db.adapter.binding == 'pymysql_named'
    assert not {'returning_insert', 'returning_update', 'returning_delete'} & db.adapter.capabilities


@pytest.mark.parametrize(('operation', 'record', 'expected'), [
    ('insert', {'id': 1, 'amount': 3}, 'INSERT INTO "s"."t"("id","amount","first") VALUES (%(id)s,%(amount)s,1 -- value\n)'),
    ('delete', {'id': 4}, 'DELETE FROM "s"."t" WHERE "id"=%(__pkey__0)s'),
])
def test_dml_rendering_has_no_returning(db, operation, record, expected):
    compiled = getattr(db.write_compiler, operation)(model(db, 't'), record, {})
    assert compiled.sql == expected


def test_default_values_is_an_empty_column_list(db):
    sql, _ = db.adapter.prepareSqlText('INSERT INTO "s"."ticket" DEFAULT VALUES', {})
    assert sql == 'INSERT INTO "s"."ticket" () VALUES ()'


@pytest.mark.xfail(strict=True, reason='asqueel#21: without RETURNING the values the database decides '
                                       'are not written back, and nothing refuses the write')
def test_insert_needing_database_values_is_refused(db):
    with pytest.raises(UnsupportedFeatureError):
        db.write_compiler.insert(model(db, 'ticket'), {}, {})
    with pytest.raises(UnsupportedFeatureError):
        db.write_compiler.insert(model(db, 't'), {'id': 1}, {})


def test_returning_and_lock_are_refused(db):
    with pytest.raises(UnsupportedFeatureError, match='RETURNING'):
        db.adapter.prepareSqlText('DELETE FROM "s"."t" RETURNING "id"', {})
    with pytest.raises(UnsupportedFeatureError, match='table locks'):
        db.write_compiler.lock_table(model(db, 't'), {})
    # The words inside literals, identifiers and comments are text.
    sql, _ = db.adapter.prepareSqlText('''SELECT 'RETURNING', "LOCK" -- RETURNING\nFROM x''', {})
    assert 'RETURNING' in sql


def test_text_preparation(db):
    sql, params = db.adapter.prepareSqlText(
        "SELECT name FROM t WHERE name ILIKE :p AND code ~* 'x' AND note LIKE '50%' "
        "AND tag = 'ILIKE' AND id IN :ids", {'p': 'a%', 'ids': (1, 2)})
    assert sql == ("SELECT name FROM t WHERE name LIKE %(p)s AND code  REGEXP  'x' AND note LIKE '50%%' "
                   "AND tag = 'ILIKE' AND id IN(%(ids_0)s,%(ids_1)s)")
    assert params == {'p': 'a%', 'ids_0': 1, 'ids_1': 2}


def test_empty_in_list_is_constant(db):
    sql, _ = db.adapter.prepareSqlText(
        'SELECT 1 FROM t AS t0 WHERE "t0"."id" IN :none AND "t0"."id" NOT IN :none', {'none': []})
    assert sql == 'SELECT 1 FROM t AS t0 WHERE FALSE AND TRUE'


def test_tokenizer_skips_backticks_and_hash_comments():
    sql = 'SELECT `:a`, :b # :c\n, :d /* :e /* */ :f'
    names = []
    substitute_parameters(sql, lambda m: names.append(m['parameter']) or m[0], 'mysql')
    assert names == ['b', 'd', 'f']


def test_offset_without_limit_and_for_update():
    adapter = MysqlAdapter(None)
    sql = adapter.compileSql('"s"."t"', '1', offset=5)
    assert sql.endswith('LIMIT 18446744073709551615\nOFFSET 5')
    assert adapter.compileSql('"s"."t"', '1', for_update='NOWAIT').endswith('FOR UPDATE OF t0 NOWAIT')


def test_identifier_length():
    adapter = MysqlAdapter(None)
    assert adapter.adaptSqlName('a' * 64) == '"' + 'a' * 64 + '"'
    with pytest.raises(ValueError, match='64 characters'):
        adapter.adaptSqlName('a' * 65)


def test_sql_functions():
    adapter = MysqlAdapter(None)
    assert adapter.string_join(['a', 'b'], ', ') == "CONCAT_WS(', ', a, b)"
    assert adapter.string_join([], ',') == "''"
    assert adapter.concat_template([("it's ", True), ('x', False)]) == \
        "CONCAT('it''s ', COALESCE(CAST((x) AS CHAR), ''))"
    assert adapter.string_agg('$code', ',') == "GROUP_CONCAT($code SEPARATOR ',')"


@pytest.mark.parametrize(('call', 'args'), [
    ('join_sql_subquery', ('SELECT 1', 'r')),
    ('json_sql_subquery', ('SELECT 1', 'r', '1')),
    ('xml_sql_subquery', ('SELECT 1', 'r', '1')),
    ('aggregate_sql_subquery', ('SELECT 1', 'json', 'r', ())),
    ('bag_item_formula', ('$bag', 'T')),
    ('ageAtDate', ('$born',)),
])
def test_unsupported_functions_raise(call, args):
    with pytest.raises(UnsupportedFeatureError, match='mysql'):
        getattr(MysqlAdapter(None), call)(*args)


@pytest.mark.parametrize(('options', 'message'), [
    ({'conninfo': 'host=x'}, 'conninfo'),
    ({'dbname': 'x', 'foreignKeys': True}, 'foreignKeys'),
    ({'dbname': 'x', 'autocommit': True}, 'autocommit'),
    ({'dbname': 'x', 'sslmode': 'require'}, 'Unsupported MySQL options'),
    ({}, 'database name'),
])
def test_connect_option_errors(options, message):
    with pytest.raises(ValueError, match=message):
        MysqlAdapter(None).connect(**options)
