"""subQueryColumn with aggr=, and the #ENV, #BAG, #BAGCOLS macros as legacy (Macro 5, Phase 4)."""
import pytest
from genro_bag import Bag

from asqueel import AsqueelDb, SqlDatabaseConfig
from tests.option_tables_support import IMPLEMENTATIONS, migrated_db
from tests.package_layout_support import write_layout

PAYLOAD = '<GenRoBag><value>hello</value><sub><x>one</x></sub></GenRoBag>'

CUSTOMER = '''
class Table:
    def config_db(self, pkg):
        customer = pkg.table('customer', pkey='id')
        customer.column('id', dtype='L')
        customer.column('code')
        customer.column('payload', dtype='X')
        lines = dict(table='app.invoice', where='$customer_id=#THIS.id')
        customer.subQueryColumn('total', query=lines, aggr='sum($amount)', dtype='N')
        customer.subQueryColumn('lines', query=lines, aggr='count()', dtype='L')
        customer.subQueryColumn('codes', query=dict(lines, order_by='$code DESC'), aggr="join($code, ',')", dtype='T')
        customer.subQueryColumn('first_code', query=dict(lines, columns='MIN($code)'), dtype='T')
        customer.formulaColumn('who', sql_formula='#ENV(user)', dtype='T')
        customer.formulaColumn('nick', sql_formula='#ENV(nick,user)', dtype='T')
        customer.formulaColumn('region', sql_formula='#ENV(region)', dtype='T')
        customer.formulaColumn('ghost', sql_formula='#ENV(ghost)', dtype='T')

    def env_region(self):
        return "'north'"
'''


def declare(pkg):
    invoice = pkg.table('invoice', pkey='id')
    invoice.column('id', dtype='serial')
    invoice.column('customer_id', dtype='L').relation('app.customer.id', relation_name='invoices')
    invoice.column('code')
    invoice.column('amount', dtype='N')


@pytest.fixture(params=IMPLEMENTATIONS)
def db(request, tmp_path):
    with migrated_db(request.param, tmp_path, declare, path=write_layout(tmp_path / 'app', customer=CUSTOMER)) as db:
        db.table('app.customer').sql_insert([{'id': 1, 'code': 'a', 'payload': PAYLOAD},
                                             {'id': 2, 'code': 'b', 'payload': None}])
        db.table('app.invoice').sql_insert([{'customer_id': 1, 'code': 'i1', 'amount': 10},
                                            {'customer_id': 1, 'code': 'i2', 'amount': 5}])
        db.commit()
        yield db


def column(db, name, **kwargs):
    rows = db.table('app.customer').query(columns=f'$id,${name}', order_by='$id', **kwargs).fetch()
    return [row[name] for row in rows]


def test_subquery_aggr_sum_and_count(db):
    assert column(db, 'total') == [15, None]
    assert column(db, 'lines') == [2, 0]


def test_subquery_aggr_join_follows_the_query_order_by(db):
    assert column(db, 'codes') == ['i2,i1', '']


def test_subquery_without_aggr_nor_mode_is_a_plain_subquery(db):
    assert column(db, 'first_code') == ['i1', None]


def test_env_macro_inlines_the_environment_value_with_quotes_doubled(db):
    with db.tempEnv(user="O'Hara"):
        assert column(db, 'who') == ["O'Hara", "O'Hara"]


def test_env_macro_falls_back_to_its_second_key(db):
    with db.tempEnv(user='anna'):
        assert column(db, 'nick') == ['anna', 'anna']


def test_env_macro_calls_the_table_handler_when_the_key_is_missing(db):
    assert column(db, 'region') == ['north', 'north']
    with db.tempEnv(region='south'):
        assert column(db, 'region') == ['south', 'south']


def test_env_macro_without_key_nor_handler_names_the_key(db):
    with pytest.raises(ValueError, match="#ENV\\(ghost\\).*'ghost'"):
        column(db, 'ghost')


def test_env_macro_text_stays_the_one_of_the_first_compilation(db):
    query = db.table('app.customer').query(columns='$who', where='$id=1')
    with db.tempEnv(user='first'):
        assert query.fetch()[0]['who'] == 'first'
    with db.tempEnv(user='second'):
        assert query.fetch()[0]['who'] == 'first'


def test_env_macro_in_a_where_clause_is_refused(db):
    with pytest.raises(ValueError, match='#ENV is expanded only in a formulaColumn sql_formula'):
        db.table('app.customer').query(columns='$id', where="$code = #ENV(user)").fetch()


@pytest.mark.parametrize('macro', ['#BAG', '#BAGCOLS'])
def test_bag_macros_in_a_where_clause_are_refused(db, macro):
    with pytest.raises(ValueError, match=f'{macro} is expanded only in the query columns'):
        db.table('app.customer').query(columns='$id', where=f'{macro}($payload) IS NULL').fetch()


def test_bag_macro_returns_the_column_as_a_bag(db):
    rows = db.table('app.customer').query(columns='$id,#BAG($payload) AS doc', order_by='$id').fetch()
    assert isinstance(rows[0]['doc'], Bag)
    assert rows[0]['doc']['value'] == 'hello'
    assert isinstance(rows[1]['doc'], Bag)
    assert len(rows[1]['doc']) == 0


def test_bagcols_macro_spreads_the_leaves_into_columns(db):
    rows = db.table('app.customer').query(columns='$id,#BAGCOLS($payload)', order_by='$id').fetch()
    assert rows[0]['payload_value'] == 'hello'
    assert rows[0]['payload_sub_x'] == 'one'
    assert rows[0]['payload'] is None


def memory_package():
    config = SqlDatabaseConfig()
    root = config.source.db('subqueries', implementation='sqlite')
    root.connection('main', database=':memory:')
    pkg = root.packages().package('app', sqlschema='main', sqlprefix=False)
    customer = pkg.table('customer', pkey='id')
    customer.column('id', dtype='L')
    customer.column('code')
    return config, customer


def compile_column(config, name):
    return AsqueelDb(config).table('app.customer').query(columns=f'${name}').compiled


LINES = dict(table='app.customer', where='$id=#THIS.id')


def test_subquery_aggr_takes_one_aggregate():
    config, customer = memory_package()
    with pytest.raises(ValueError, match='one aggregate'):
        customer.subQueryColumn('pair', query=LINES, aggr='sum($id), count()')
        compile_column(config, 'pair')


def test_subquery_aggr_and_mode_together_are_an_error():
    config, customer = memory_package()
    with pytest.raises(ValueError, match='aggr and mode'):
        customer.subQueryColumn('both', query=LINES, aggr='count()', mode='json')
        compile_column(config, 'both')


@pytest.mark.parametrize('mode', ['sum', 'join', 'to_json', 'to_xml'])
def test_subquery_mode_other_than_json_or_xml_is_an_error(mode):
    config, customer = memory_package()
    with pytest.raises(ValueError, match=f"mode '{mode}'"):
        customer.subQueryColumn('other', query=dict(LINES, columns='$code'), mode=mode)
        compile_column(config, 'other')
