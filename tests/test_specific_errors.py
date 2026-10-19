"""Every refusal names the feature the user wrote, in the form '... is not available in this release'."""
from types import SimpleNamespace

import pytest

from asqueel import AsqueelDb, SqlDatabase, SqlDatabaseConfig, UnsupportedFeatureError, UnusedQueryParameterWarning
from asqueel.adapters.base import SqlDbAdapter
from asqueel.configuration import _owned_handler
from asqueel.projection import _constraint_index_feature, _index_feature


def config(select=None, **virtual):
    config = SqlDatabaseConfig()
    pkg = config.source.db('specific', implementation='sqlite').packages().package('app')
    customer = pkg.table('customer', pkey='id')
    customer.column('id', dtype='L')
    customer.column('code', dtype='T')
    customer.composites().compositeColumn(name='identity', columns='id,code')
    if select is not None:
        customer.formulaColumn('sub', select=dict(table='app.invoice', columns='SUM($total)',
                                                  where='$customer_id=#THIS.id', **select))
    for tag, attributes in virtual.items():
        getattr(customer, tag)('computed', **attributes)
    invoice = pkg.table('invoice', pkey='id')
    invoice.column('id', dtype='L')
    invoice.column('total', dtype='N')
    invoice.column('customer_id', dtype='L').relation('app.customer.id', relation_name='invoices')
    line = pkg.table('line', pkey='id')
    line.column('id', dtype='L')
    line.column('invoice_id', dtype='L').relation('app.invoice.id', relation_name='lines')
    return config


def database(source):
    return SqlDatabase(model=source.render(mode='objects_tree'), config=_owned_handler(source))


@pytest.fixture
def db():
    with database(config()) as opened:
        yield opened


def compile_customer(db, columns, **options):
    return db.table('app.customer').query(columns, **options).compiled


def test_composite_column_in_place_of_a_physical_column(db):
    with pytest.raises(UnsupportedFeatureError,
                       match='app.customer.identity: compositeColumn in place of a physical column is not available'):
        compile_customer(db, '$id', where='$identity IS NULL')


@pytest.mark.parametrize('key, value', [('subqueries', {'s': {'table': 'app.invoice'}}), ('handler', 'compute')])
def test_formula_column_subqueries_and_handler(key, value):
    with database(config(formulaColumn={'sql_formula': '$id', key: value})) as db:
        with pytest.raises(UnsupportedFeatureError,
                           match=f'app.customer.computed: formulaColumn {key}= is not available in this release'):
            compile_customer(db, '$computed')


def test_py_column():
    with database(config(pyColumn={'py_method': 'compute'})) as db:
        with pytest.raises(UnsupportedFeatureError,
                           match='app.customer.computed: pyColumn is not available in this release'):
            compile_customer(db, '$computed')


def test_path_through_a_many_relation(db):
    with pytest.raises(UnsupportedFeatureError,
                       match='@invoices: a path through the many relation @invoices is not available'):
        compile_customer(db, '@invoices.total')


def test_many_operation_after_a_many_relation(db):
    with pytest.raises(UnsupportedFeatureError,
                       match='@invoices.@lines: a path through the many relation @invoices is not available'):
        compile_customer(db, '@invoices.@lines.sum($id)')


def test_many_operation_without_handler(db):
    with pytest.raises(UnsupportedFeatureError, match=r'many_median is not available in this release'):
        compile_customer(db, '@invoices.median($total)')


def test_aggregate_function(db):
    with pytest.raises(UnsupportedFeatureError, match=r'aggr: median\(\) is not available in this release'):
        compile_customer(db, '@invoices.aggr(median($total))')


@pytest.mark.parametrize('key', ['join_on', 'cnd', 'between'])
def test_aggregate_on_a_relation_with_a_custom_join(key):
    source = config()
    model = source.render(mode='objects_tree')
    model.relations.get_node('app.customer.@invoices').attr[key] = '$total>0'
    with SqlDatabase(model=model, config=_owned_handler(source)) as opened:
        with pytest.raises(UnsupportedFeatureError,
                           match=f'@invoices: aggr on a relation with {key}= is not available'):
            compile_customer(opened, '@invoices.aggr(sum($total))')


@pytest.mark.parametrize('macro', ['#PREF', '#TSQUERY', '#ENV', '#BAG'])
def test_macro(db, macro):
    with pytest.raises(UnsupportedFeatureError, match=f'macro {macro} is not available in this release'):
        compile_customer(db, '$id', where=f'{macro}($code)')


def test_column_wildcard(db):
    with pytest.raises(UnsupportedFeatureError, match=r"column wildcard '\*@invoices' is not available"):
        compile_customer(db, '*@invoices')


@pytest.mark.parametrize('option, value', [('subtable', 'open'), ('addPkeyColumn', True), ('ignoreTableOrderBy', False)])
def test_subquery_option_with_a_value_other_than_the_legacy_default(option, value):
    with database(config({option: value})) as db:
        with pytest.raises(UnsupportedFeatureError,
                           match=f'subquery option {option}={value!r} is not available in this release'):
            compile_customer(db, '$sub')


def test_unknown_subquery_option():
    with database(config({'locale': 'it'})) as db:
        with pytest.raises(UnsupportedFeatureError, match="subquery option 'locale' is not available in this release"):
            compile_customer(db, '$sub')


def test_compiler_query_option(db):
    with pytest.raises(UnsupportedFeatureError, match="query option 'relationDict' is not available in this release"):
        db.compiler.plan_select('app.customer', '$id', relationDict={})


@pytest.mark.parametrize('option', [
    'ignoreTableOrderBy', '_storename', 'storename', 'locale', 'mode', 'checkPermissions', 'aliasPrefix',
    'relationDict', 'joinConditions', 'sqlContextName', 'lazy', 'eager', 'virtual_columns', 'ignoreMissing',
    'ignoreDuplicate', 'subtable',
])
def test_query_option(db, option):
    with pytest.raises(UnsupportedFeatureError, match=f"query option '{option}' is not available in this release"):
        db.table('app.customer').query('$id', **{option: 'value'})


def test_unused_query_keyword(db):
    with pytest.warns(UnusedQueryParameterWarning,
                      match="query keyword 'amount' is not used by the query; its parameters are: "):
        compile_customer(db, '$id', amount=3)


def test_selection(db):
    with pytest.raises(UnsupportedFeatureError, match=r'selection\(\): .* not available in this release'):
        db.table('app.customer').query('$id').selection()


def test_mask_field_sql_on_an_adapter_without_it():
    adapter = SimpleNamespace(dialect='other')
    with pytest.raises(UnsupportedFeatureError, match='other: mask_field_sql is not available in this release'):
        SqlDbAdapter.mask_field_sql(adapter, 'code')


def test_storename_in_the_environment(tmp_path):
    class Config(SqlDatabaseConfig):
        def main(self, root):
            db = root.db(implementation='sqlite')
            db.connection(name=str(tmp_path / 'specific.db'))
            db.schemas().schema('main').tables().table('item', pkey='id').columns().column('id', dtype='I')
    db = AsqueelDb(Config)
    try:
        db.updateEnv(storename='branch')
        with pytest.raises(UnsupportedFeatureError,
                           match="environment key storename='branch': database stores are not available"):
            db.table('main.item').query().fetch()
    finally:
        db.close()


@pytest.mark.parametrize('item, feature', [
    ({'options': ['fillfactor=70']}, 'storage options'),
    ({'tablespace': 'fast'}, 'a tablespace'),
    ({'columns': ['a', 'b'], 'key_count': 1}, 'included columns'),
    ({'method': 'hash'}, 'method hash'),
    ({'default_opclasses': False}, 'non-default operator classes'),
    ({'default_collations': False}, 'non-default collations'),
    ({'ordering': [3]}, 'non-default ordering'),
    ({'valid': False}, 'NOT VALID'),
    ({'nulls_not_distinct': True}, 'NULLS NOT DISTINCT'),
])
def test_constraint_index_feature(item, feature):
    plain = {'columns': ['a'], 'key_count': 1, 'method': 'btree', 'ordering': [0]}
    assert _constraint_index_feature(plain) is None
    assert _constraint_index_feature({**plain, **item}) == feature


@pytest.mark.parametrize('item, feature', [
    ({'columns': ['a', None]}, 'expression columns'),
    ({'key_count': 2}, 'included columns'),
    ({'ordering': [1]}, 'NULLS FIRST/LAST ordering'),
    ({'default_opclasses': False}, 'non-default operator classes'),
    ({'default_collations': False}, 'non-default collations'),
    ({'valid': False}, 'NOT VALID'),
    ({'nulls_not_distinct': True}, 'NULLS NOT DISTINCT'),
    ({'options': ['fillfactor=70']}, 'storage options'),
    ({'tablespace': 'fast'}, 'a tablespace'),
])
def test_index_feature(item, feature):
    plain = {'columns': ['a'], 'key_count': 1, 'ordering': [0], 'default_opclasses': True,
             'default_collations': True, 'valid': True, 'nulls_not_distinct': False,
             'options': None, 'tablespace': None}
    assert _index_feature(plain) is None
    if 'columns' in item:
        plain['key_count'] = len(item['columns'])
    assert _index_feature({**plain, **item}) == feature
