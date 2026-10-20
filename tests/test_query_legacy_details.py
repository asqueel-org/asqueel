"""Legacy details of the query layer: #ENV text, #BAG paths, sqlparams, warnings, fetchRecord compilation."""
import warnings

import pytest

from asqueel import UnusedQueryParameterWarning
from tests.option_tables_support import migrated_db


def declare(pkg):
    customer = pkg.table('customer', pkey='id')
    customer.column('id', dtype='L')
    customer.column('code')
    customer.column('tenant', dtype='L')
    customer.formulaColumn('who', sql_formula='#ENV(user)', dtype='T')


@pytest.fixture
def customers(tmp_path):
    with migrated_db('sqlite', tmp_path, declare) as db:
        table = db.table('app.customer')
        table.sql_insert([{'id': 1, 'code': 'a', 'tenant': 1}, {'id': 2, 'code': 'b', 'tenant': 1}])
        db.commit()
        yield table


@pytest.mark.parametrize('value, text', [(None, ''), ('', ''), (['a', 'b'], 'a,b'), (('x', None), 'x,'), (7, '7')])
def test_env_macro_formats_values_as_legacy_to_text(customers, value, text):
    with customers.db.tempEnv(user=value):
        assert customers.query(columns='$who', where='$id=1').fetch()[0]['who'] == text


@pytest.mark.parametrize('macro', ['#BAG', '#BAGCOLS'])
def test_bag_macros_refuse_a_relation_path(customers, macro):
    with pytest.raises(ValueError, match=f'{macro} takes a column of the queried table'):
        customers.query(columns=f'$id,{macro}(@customer_id.code)').fetch()


def test_sqlparams_leave_out_the_environment_parameters(customers):
    query = customers.query(columns='$code', where='$tenant=:env_tenant AND $id=:pk', pk=1)
    with customers.db.tempEnv(tenant=1):
        assert set(query.sqlparams) == {'pk'}
        assert query.test() == (query.sqltext, query.sqlparams)


def test_unused_keyword_warning_points_at_the_caller(customers):
    with pytest.warns(UnusedQueryParameterWarning) as caught:
        customers.query(columns='$code', colour='red').fetch()
    assert caught[0].filename == __file__


def test_fetch_record_with_order_by_compiles_once(customers):
    query = customers.query(columns='$code', order_by='$code DESC', colour='red')
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter('always')
        assert query.fetchRecord()['code'] == 'b'
        assert query.fetchRecord()['code'] == 'b'
    assert len([w for w in caught if issubclass(w.category, UnusedQueryParameterWarning)]) == 1
