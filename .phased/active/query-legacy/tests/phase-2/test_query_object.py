"""The query object as legacy: compiled once, environment read at execution, unused keywords warned (Macro 5, Phase 2)."""
import pytest

import asqueel
from asqueel import UnusedQueryParameterWarning
from asqueel.contracts import UnsupportedFeatureError
from tests.option_tables_support import IMPLEMENTATIONS, migrated_db


def declare(pkg):
    customer = pkg.table('customer', pkey='id')
    customer.column('id', dtype='serial')
    customer.column('code')
    customer.column('tenant', dtype='L')


@pytest.fixture(params=IMPLEMENTATIONS)
def customers(request, tmp_path):
    with migrated_db(request.param, tmp_path, declare) as db:
        table = db.table('app.customer')
        table.sql_insert([{'code': 'a', 'tenant': 1}, {'code': 'b', 'tenant': 2}, {'code': 'c', 'tenant': 2}])
        db.commit()
        yield table


def missing(name):
    return pytest.raises(UnsupportedFeatureError, match=f'{name} is not available in this release')


def test_compiled_is_built_once_and_cached(customers):
    query = customers.query(columns='$code', where='$tenant=:tenant', tenant=2)
    assert query.compiled is query.compiled
    assert query.sqltext == query.compiled.sql


def test_test_returns_the_sql_text_and_its_parameters(customers):
    query = customers.query(columns='$code', where='$tenant=:tenant', tenant=2)
    sqltext, sqlparams = query.test()
    assert sqltext == query.sqltext
    assert 2 in dict(sqlparams).values()


def test_environment_parameters_are_read_again_at_every_execution(customers):
    query = customers.query(columns='$code', where='$tenant=:env_tenant', order_by='$code')
    with customers.db.tempEnv(tenant=1):
        assert [row['code'] for row in query.fetch()] == ['a']
    with customers.db.tempEnv(tenant=2):
        assert [row['code'] for row in query.fetch()] == ['b', 'c']


def test_environment_mismatch_error_is_gone():
    assert not hasattr(asqueel, 'EnvironmentMismatchError')


def test_unused_keyword_runs_the_query_with_a_warning_naming_it(customers):
    with pytest.warns(UnusedQueryParameterWarning) as caught:
        rows = customers.query(columns='$code', where='$tenant=:tenant', tenant=1, colour='red').fetch()
    assert [row['code'] for row in rows] == ['a']
    message = str(caught[0].message)
    assert 'colour' in message
    assert 'tenant' in message


def test_unused_query_parameter_warning_is_a_user_warning():
    assert issubclass(UnusedQueryParameterWarning, UserWarning)


@pytest.mark.parametrize('option', [{'distinct': True}, {'group_by': '$tenant'}])
def test_for_update_with_distinct_or_group_by_fails_when_the_query_is_built(customers, option):
    with pytest.raises(UnsupportedFeatureError, match='for_update is incompatible with distinct or group_by'):
        customers.query(columns='$tenant', for_update=True, **option)


@pytest.mark.parametrize('columns', [None, ''])
def test_empty_columns_name_the_missing_feature(customers, columns):
    with missing(f'columns={columns!r}'):
        customers.query(columns=columns)


@pytest.mark.parametrize('name', ['readColumns', 'countRecords', 'recordAs', 'cachedRecord',
                                  'sqlWhereFromBag', 'whereTranslator'])
def test_table_methods_of_absent_features_name_them(customers, name):
    with missing(name):
        getattr(customers, name)


@pytest.mark.parametrize('name', ['query', 'whereTranslator'])
def test_database_methods_of_absent_features_name_them(customers, name):
    with missing(f'db.{name}'):
        getattr(customers.db, name)
