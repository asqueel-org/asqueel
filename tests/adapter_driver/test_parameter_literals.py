"""Issue #35: parameter-like text must survive SQL preparation unchanged."""
from copy import deepcopy
import sqlite3

import psycopg
import pytest

from asqueel._sql_bindings import SqlBindings
from asqueel.adapters.postgres import SqlDbAdapter as PostgresAdapter
from asqueel.adapters.sqlite import SqlDbAdapter as SqliteAdapter
from tests.native_support import postgres_dsn


@pytest.fixture(params=[PostgresAdapter(None), SqliteAdapter(None)], ids=['postgresql', 'sqlite'])
def driver(request):
    return request.param


@pytest.mark.parametrize('quoted', [
    "'doc:xyz'", "'it''s :xyz'", "'line one\n:xyz'", '"doc:xyz"', '"doc"":xyz"',
    '-- :xyz\n', '-- :xyz\r', '/* :xyz */',
])
def test_only_unquoted_parameters_are_bound(driver, quoted):
    sql = f'SELECT {quoted} || :xyz || :xyz'
    query = driver.prepare_sql(sql, {'xyz': 'value'}, {})
    placeholder = '%(xyz)s' if driver.dialect == 'postgres' else ':xyz'
    assert query.sql == f'SELECT {quoted} || {placeholder} || {placeholder}'
    assert query.params == {'xyz': 'value'}
    assert query.input_parameters == ('xyz',)


def test_literals_do_not_create_parameters_or_environment_dependencies(driver):
    sql = "SELECT 'doc:xyz', ':env_workdate', ':env_secret' /* :missing */ -- :other\n"
    query = driver.prepare_sql(sql, None, {'secret': 'unused'})
    assert query.sql == sql
    assert query.params == {}
    assert query.input_parameters == ()
    assert query.environment_keys == ()


@pytest.mark.parametrize('protected', [
    '$$:xyz :env_secret$$', '$tag$:xyz $$ :env_secret$tag$',
    '$Tag$:xyz $tag$ :env_secret$Tag$', '$étiquette$:xyz$étiquette$',
    r"E'it\'s :xyz'", r"e'backslash\\ :xyz'",
    '/* outer /* inner */ :xyz :env_secret */',
    '/* outer /* inner /* deeper */ */ :xyz */',
])
def test_postgresql_quoting_and_nested_comments(protected):
    query = PostgresAdapter(None).prepare_sql(f'SELECT {protected}, :value::text', {'value': 'ok'}, {})
    assert query.sql == f'SELECT {protected}, %(value)s::text'
    assert query.params == {'value': 'ok'}
    assert query.input_parameters == ('value',)
    assert query.environment_keys == ()


@pytest.mark.parametrize('protected', ["'unterminated :hidden", '"unterminated :hidden',
                                       '$tag$unterminated :hidden', '/* unterminated :hidden'])
def test_unterminated_regions_are_left_for_database_validation(protected):
    query = PostgresAdapter(None).prepare_sql(f'SELECT :value, {protected}', {'value': 1}, {})
    assert query.sql == f'SELECT %(value)s, {protected}'
    assert query.input_parameters == ('value',)


def test_dialect_specific_quoting():
    sqlite = SqliteAdapter(None).prepare_sql('SELECT [:xyz], `a``:xyz`, :value', {'value': 1}, {})
    assert sqlite.input_parameters == ('value',)
    pg = PostgresAdapter(None).prepare_sql('SELECT ARRAY[:value], :value::integer', {'value': 1}, {})
    assert pg.sql == 'SELECT ARRAY[%(value)s], %(value)s::integer'
    # An identifier may contain a dollar sign; it cannot open a dollar string.
    pg = PostgresAdapter(None).prepare_sql('SELECT name$tag$ || :value', {'value': 1}, {})
    assert pg.input_parameters == ('value',)
    # Ordinary PG strings do not treat a backslash as an escaped closing quote.
    pg = PostgresAdapter(None).prepare_sql(r"SELECT 'a\', :value", {'value': 1}, {})
    assert pg.sql == r"SELECT 'a\', %(value)s"


def test_casts_adjacent_parameters_and_legacy_escape(driver):
    query = driver.prepare_sql(r"SELECT :a+:b, :a::text, 'doc\:xyz'", {'a': 1, 'b': 2}, {})
    assert query.input_parameters == ('a', 'b')
    assert query.params == {'a': 1, 'b': 2}
    assert "'doc:xyz'" in query.sql


def test_environment_binding_uses_only_real_occurrences(driver):
    query = driver.prepare_sql("SELECT ':env_secret', :env_value", {}, {'value': 'ok'})
    assert query.params == {'env_value': 'ok'}
    assert query.environment_keys == ('value',)


@pytest.mark.parametrize('values', [[1, 2], []])
def test_collection_expansion_preserves_literals_and_comments(driver, values):
    params = {'ids': values}
    before = deepcopy(params)
    prefix = "SELECT 'IN :ids', 'doc:ids' /* IN :ids */ -- IN :ids\n"
    query = driver.prepare_sql(prefix + 'WHERE 1 IN :ids', params, {})
    assert query.sql.startswith(prefix)
    assert query.input_parameters == ('ids',)
    assert params == before
    if values:
        assert 'IN :' not in query.sql[len(prefix):]
        assert sorted(query.params.values()) == [1, 2]


def test_formula_scope_renames_only_real_parameters(driver):
    bindings = SqlBindings({'xyz': 'caller'}, dialect=driver.dialect).child({'xyz': 'local'}, 'f')
    sql = "'doc:xyz' || :xyz /* :xyz */ || ':env_secret'"
    assert bindings.substitute(sql) == "'doc:xyz' || :f1_xyz /* :xyz */ || ':env_secret'"
    assert bindings.params == {'xyz': 'caller', 'f1_xyz': 'local'}
    assert bindings.consumed == set()


_LIVE_CASES = [
    ("SELECT 'prefix' || 'doc:xyz' || 'suffix'", {}, ('prefixdoc:xyzsuffix',)),
    ("SELECT ':x' AS lit, :x AS bound", {'x': 'VALUE'}, (':x', 'VALUE')),
    ("SELECT ':x' AS lit -- :y comment", {}, (':x',)),
    ("SELECT 'doc:ids' AS literal, 1 IN :ids AS member /* IN :ids */",
     {'ids': [1, 2]}, ('doc:ids', True)),
]


@pytest.mark.parametrize('sql, params, expected', _LIVE_CASES)
def test_sqlite_results(sql, params, expected):
    query = SqliteAdapter(None).prepare_sql(sql, params, {})
    with sqlite3.connect(':memory:') as conn:
        assert conn.execute(query.sql, dict(query.params)).fetchone() == expected


@pytest.mark.postgresql
@pytest.mark.parametrize('sql, params, expected', _LIVE_CASES + [
    ("SELECT $$doc:xyz$$ AS literal, $tag$:env_secret$tag$ AS env_literal, :value::text AS bound",
     {'value': 'ok'}, ('doc:xyz', ':env_secret', 'ok')),
    (r"SELECT E'it\'s :xyz', :value::text /* outer /* inner */ :hidden */",
     {'value': 'ok'}, ("it's :xyz", 'ok')),
])
def test_postgresql_results(sql, params, expected):
    query = PostgresAdapter(None).prepare_sql(sql, params, {})
    with psycopg.connect(postgres_dsn()) as conn:
        conn.read_only = True
        assert conn.execute(query.sql, dict(query.params)).fetchone() == expected
