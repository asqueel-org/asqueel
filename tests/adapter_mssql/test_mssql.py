"""SQL Server write and SELECT rendering on the hierarchical model, without a connection."""
import pytest

from asqueel import AsqueelDb, SqlDatabaseConfig
from asqueel.contracts import UnsupportedFeatureError
from asqueel.adapters.mssql import SqlDbAdapter as MssqlAdapter
from asqueel.errors import MigrationError
from tests.unit_of_work import empty_database


@pytest.fixture
def db():
    source = SqlDatabaseConfig()
    pkg = source.source.db('render', implementation='mssql').packages().package('s', sqlschema='s', sqlprefix=False)
    table = pkg.table('t', pkey='id')
    table.column('id', dtype='I')
    table.column('amount', dtype='N')
    table.column('first', dtype='I', sql_value='1 -- value')
    table.column('second', dtype='I')
    ticket = pkg.table('ticket', pkey='id')
    ticket.column('id', dtype='serial')
    pair = pkg.table('pair', pkey='pair_key')
    pair.column('code', dtype='A', size=':4')
    pair.column('year', dtype='I')
    pair.compositeColumn('pair_key', columns='code,year')
    pkg.table('nokey').column('amount', dtype='N')
    database = AsqueelDb(source)
    try:
        yield database
    finally:
        database.close()


def model(db, name):
    return db.table(f's.{name}').model


def prepare(sql, params=None):
    return MssqlAdapter(None).prepare_sql(sql, params or {}, {})


def test_implementation_name_loads_the_adapter():
    db = empty_database(implementation='mssql').session()
    try:
        assert db.implementation == 'mssql'
        assert type(db.adapter) is MssqlAdapter
        assert db.adapter.dbroot is db
    finally:
        db.shared.close()


def test_capabilities_declare_no_returning():
    assert MssqlAdapter.capabilities == {
        'select', 'insert', 'update', 'delete', 'left_join', 'limit', 'offset',
        'default_values', 'for_update'}


@pytest.mark.parametrize(('operation', 'record', 'expected'), [
    ('insert', {'amount': 3}, 'INSERT INTO "s"."t"("amount","first") VALUES (%(amount)s,1 -- value\n)'),
    ('delete', {'id': 4}, 'DELETE FROM "s"."t" WHERE "id"=%(__pkey__0)s'),
])
def test_dml_rendering(db, operation, record, expected):
    compiled = getattr(db.write_compiler, operation)(model(db, 't'), record, {})
    assert compiled.sql == expected


def test_default_values_without_returning(db):
    assert db.write_compiler.insert(model(db, 'ticket'), {}, {}).sql == 'INSERT INTO "s"."ticket" DEFAULT VALUES'


@pytest.mark.xfail(strict=True, reason='asqueel#21: WriteCompiler does not enforce the adapter capabilities; '
                                       'an IDENTITY value is lost without RETURNING')
def test_values_decided_by_the_database_are_not_lost(db):
    with pytest.raises(UnsupportedFeatureError, match='returning_insert'):
        db.write_compiler.insert(model(db, 'ticket'), {}, {})
    with pytest.raises(UnsupportedFeatureError, match='returning_update'):
        db.write_compiler.update(model(db, 't'), {'id': 1, 'second': 2}, {})


def test_malformed_statements_are_rejected(db):
    with pytest.raises(ValueError, match='at least one column'):
        db.write_compiler.update(model(db, 'ticket'), {'unknown': 1}, {}, pkey=1)
    with pytest.raises(ValueError, match='no primary key'):
        db.write_compiler.delete(model(db, 'nokey'), {'amount': 1}, {})
    for options in ({'limit': -1}, {'limit': True}, {'columns': ' '}):
        with pytest.raises(ValueError):
            MssqlAdapter(None).compileSql(**{'maintable': '"s"."t"', 'columns': '1', **options})


def test_clauses_have_fixed_separators_without_repairing_expression_text(db):
    select = MssqlAdapter(None).compileSql('"s"."t"', '1', joins=['LEFT JOIN "s"."t" AS "t1" ON 1=1 -- join'],
                                         where='1=1 -- predicate', order_by='1 -- order', limit=1, offset=2)
    assert '1=1 -- join\nWHERE 1=1 -- predicate\nORDER BY 1 -- order\nOFFSET 2 ROWS\nFETCH NEXT 1 ROWS ONLY' in select
    table = model(db, 't')
    update = db.write_compiler.update(table, {'id': 1, 'first': None, 'second': 2}, {}).sql
    assert '"first"=1 -- value\n,"second"=%(second)s WHERE "id"=%(__pkey__0)s' in update


@pytest.mark.parametrize(('options', 'expected'), [
    ({'limit': 5}, 'SELECT TOP (5) "id"\n FROM "s"."t" AS "t0"'),
    ({'limit': 5, 'distinct': 'DISTINCT '}, 'SELECT DISTINCT TOP (5) "id"\n FROM "s"."t" AS "t0"'),
    ({'offset': 3}, 'SELECT "id"\n FROM "s"."t" AS "t0"\nORDER BY (SELECT NULL)\nOFFSET 3 ROWS'),
    ({'for_update': True}, 'SELECT "id"\n FROM "s"."t" AS "t0" WITH (UPDLOCK, ROWLOCK)'),
])
def test_pagination_and_locking_syntax(options, expected):
    assert MssqlAdapter(None).compileSql('"s"."t"', '"id"', **options) == expected


def test_for_update_modes_are_refused():
    with pytest.raises(UnsupportedFeatureError, match='NOWAIT'):
        MssqlAdapter(None).compileSql('"s"."t"', '1', for_update='NOWAIT')


def test_parameters_outside_literals_identifiers_and_comments():
    query = prepare("SELECT :a, ':b', [x:c], \"y:d\" /* :e /* :f */ :g */ -- :h\n FROM t WHERE v = :i",
                    {'a': 1, 'i': 2})
    assert query.sql == ("SELECT %(a)s, ':b', [x:c], \"y:d\" /* :e /* :f */ :g */ -- :h\n"
                         " FROM t WHERE v = %(i)s")
    assert query.input_parameters == ('a', 'i')


def test_percent_outside_bindings_stays_as_written():
    query = prepare("SELECT 'a%%', '50%' /* 10% */ -- 1%\n WHERE v LIKE 'a%' AND w = :w", {'w': 1})
    assert query.sql == "SELECT 'a%%', '50%' /* 10% */ -- 1%\n WHERE v LIKE 'a%' AND w = %(w)s"


@pytest.mark.parametrize('sql', ["SELECT '%(w)s', :w", "SELECT 1 /* %(other)d */", "SELECT '%(' + :w"])
def test_text_pymssql_would_read_as_a_binding_raises(sql):
    with pytest.raises(UnsupportedFeatureError, match='outside a binding'):
        prepare(sql, {'w': 1})


def test_legacy_operators_are_adapted():
    assert prepare("SELECT 1 WHERE name ILIKE :n AND 'ILIKE' = 'ILIKE'", {'n': 'a%'}).sql == (
        "SELECT 1 WHERE name LIKE %(n)s AND 'ILIKE' = 'ILIKE'")
    assert prepare('SELECT 1 WHERE "t0"."vip" IS NOT TRUE').sql == (
        'SELECT 1 WHERE ("t0"."vip" IS NULL OR "t0"."vip" !=1)')
    assert prepare('SELECT 1 WHERE "t0"."vip" IS FALSE').sql == (
        'SELECT 1 WHERE ("t0"."vip" IS NOT NULL AND "t0"."vip" =0)')


def test_lists_unroll_and_an_empty_list_is_a_constant_predicate():
    query = prepare('SELECT 1 WHERE "t0"."id" IN :ids', {'ids': [1, 2]})
    assert query.sql == 'SELECT 1 WHERE "t0"."id" IN (%(ids0)s,%(ids1)s) '
    assert query.params == {'ids0': 1, 'ids1': 2}
    assert prepare('SELECT 1 WHERE "t0"."id" IN :ids', {'ids': []}).sql == 'SELECT 1 WHERE (1=0)'
    assert prepare('SELECT 1 WHERE "t0"."id" NOT IN :ids', {'ids': []}).sql == 'SELECT 1 WHERE (1=1)'


@pytest.mark.parametrize(('sql', 'message'), [
    ("SELECT 'a' || 'b'", r'\|\| concatenation'),
    ('SELECT 1 WHERE name ~* :p', r'~\* regular expression'),
    ('SELECT 1 WHERE name REGEXP :p', 'REGEXP regular expression'),
    ('LOCK "s"."t" IN ACCESS EXCLUSIVE MODE', 'no LOCK statement'),
    ('DELETE FROM "s"."pair" WHERE ("code","year") IN (SELECT 1, 2)', 'row-value IN'),
])
def test_sql_outside_tsql_raises(sql, message):
    with pytest.raises(UnsupportedFeatureError, match=message):
        prepare(sql, {'p': 'x'})


def test_operators_inside_literals_are_text():
    assert prepare("SELECT 'a || b', [c || d]").sql == "SELECT 'a || b', [c || d]"


def test_shared_compiler_constructs_without_tsql_form_raise(db):
    with pytest.raises(UnsupportedFeatureError, match='LOCK'):
        db.write_compiler.lock_table(model(db, 't'), {})
    pair = model(db, 'pair')
    with pytest.raises(UnsupportedFeatureError, match='row-value IN'):
        db.write_compiler.delete_selection(pair, db.compiler.plan_select('s.pair', columns='$code,$year'), {})


def test_composite_column_formula_raises(db):
    with pytest.raises(UnsupportedFeatureError, match='concatenation'):
        db.compiler.select('s.pair', columns='$pair_key')


def test_formula_functions():
    adapter = MssqlAdapter(None)
    assert adapter.string_join([], '-') == "''"
    assert adapter.string_join(['$a'], '-') == "CONCAT_WS('-', $a, NULL)"
    assert adapter.string_join(['$a', '$b'], "'") == "CONCAT_WS('''', $a, $b)"
    assert adapter.string_agg('$a', ',') == "string_agg($a,',')"
    assert adapter.ageAtDate('$born', timeUnit='day') == (
        'CAST(ROUND(DATEDIFF_BIG(second, $born, CAST(:env_workdate AS date)) / CAST(86400 AS numeric(38, 10)), 0) AS bigint)')
    with pytest.raises(ValueError, match='timeUnit'):
        adapter.ageAtDate('$born', timeUnit='century')
    for call in (lambda: adapter.bag_item_formula('$b', 'T'),
                 lambda: adapter.join_sql_subquery('SELECT 1', 'r'),
                 lambda: adapter.json_sql_subquery('SELECT 1', 'r', ''),
                 lambda: adapter.xml_sql_subquery('SELECT 1', 'r', ()),
                 lambda: adapter.aggregate_sql_subquery('SELECT 1', 'json', 'r', ()),
                 lambda: adapter.mask_field_sql('$a'),
                 adapter.setConstraintsDeferred,
                 adapter.vacuum):
        with pytest.raises(UnsupportedFeatureError):
            call()


def test_identifier_length():
    adapter = MssqlAdapter(None)
    assert adapter.adaptSqlName('a' * 128) == '"' + 'a' * 128 + '"'
    with pytest.raises(ValueError, match='128'):
        adapter.adaptSqlName('a' * 129)


@pytest.mark.parametrize(('conninfo', 'options', 'message'), [
    ('server=x', {}, 'not a conninfo string'),
    ('', {'foreignKeys': True}, 'foreignKeys'),
    ('', {'autocommit': True}, 'autocommit'),
    ('', {'sslmode': 'require'}, 'Unsupported SQL Server options'),
])
def test_connection_options_outside_the_driver_fields_raise(conninfo, options, message):
    with pytest.raises(ValueError, match=message):
        MssqlAdapter(None).connect(conninfo, **options)


def test_migration_refuses_a_conninfo_string():
    config = SqlDatabaseConfig()
    config.source.db('shop', implementation='mssql', conninfo='server=x').packages().package(
        'crm', sqlschema='crm').table('item', pkey='id').column('id', dtype='L')
    database = AsqueelDb(config)
    try:
        with pytest.raises(MigrationError, match='not a conninfo string'):
            database.migration_plan()
    finally:
        database.close()
