"""Every refusal names the feature the user wrote, in the form '... is not available in this release'."""
from types import SimpleNamespace

import pytest

from asqueel import AsqueelDb, SqlDatabaseConfig, UnsupportedFeatureError, UnusedQueryParameterWarning
from asqueel.adapters.base import SqlDbAdapter


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
    return AsqueelDb(source)


@pytest.fixture
def db():
    opened = database(config())
    try:
        yield opened
    finally:
        opened.closeConnection()


def compile_customer(db, columns, **options):
    return db.table('app.customer').query(columns, **options).compiled


def test_composite_column_compiles_to_the_legacy_string(db):
    sql = db.table('app.customer').query('$id', where='$identity IS NULL').sqltext
    assert """'[' || "t0"."id" ||', '|| '"' || "t0"."code" || '"' || ']'""" in ' '.join(sql.split())


@pytest.mark.parametrize('key, value', [('subqueries', {'s': {'table': 'app.invoice'}}), ('handler', 'compute')])
def test_formula_column_subqueries_and_handler(key, value):
    with pytest.raises(ValueError, match=f"Element 'formulaColumn' does not accept '{key}'"):
        config(formulaColumn={'sql_formula': '$id', key: value})


def test_py_column():
    db = database(config(pyColumn={'py_method': 'compute'}))
    try:
        with pytest.raises(UnsupportedFeatureError,
                           match='app.customer.computed: pyColumn is not available in this release'):
            compile_customer(db, '$computed')
    finally:
        db.closeConnection()


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
    opened = AsqueelDb(source)
    model = opened.model
    model.relations.get_node('app.customer.@invoices').attr[key] = '$total>0'
    try:
        with pytest.raises(UnsupportedFeatureError,
                           match=f'@invoices: aggr on a relation with {key}= is not available'):
            compile_customer(opened, '@invoices.aggr(sum($total))')
    finally:
        opened.closeConnection()


@pytest.mark.parametrize('macro', ['#PREF', '#TSQUERY'])
def test_macro(db, macro):
    with pytest.raises(UnsupportedFeatureError, match=f'macro {macro} is not available in this release'):
        compile_customer(db, '$id', where=f'{macro}($code)')


@pytest.mark.parametrize(('macro', 'message'), [('#ENV', '#ENV is expanded only in a formulaColumn sql_formula'),
                                                ('#BAG', '#BAG is expanded only in the query columns')])
def test_macro_outside_its_clause(db, macro, message):
    with pytest.raises(ValueError, match=message):
        compile_customer(db, '$id', where=f'{macro}($code)')


def test_column_wildcard(db):
    with pytest.raises(UnsupportedFeatureError, match=r"column wildcard '\*@invoices' is not available"):
        compile_customer(db, '*@invoices')


@pytest.mark.parametrize('option, value', [('subtable', 'open'), ('addPkeyColumn', True), ('ignoreTableOrderBy', False)])
def test_subquery_option_with_a_value_other_than_the_legacy_default(option, value):
    db = database(config({option: value}))
    try:
        with pytest.raises(UnsupportedFeatureError,
                           match=f'subquery option {option}={value!r} is not available in this release'):
            compile_customer(db, '$sub')
    finally:
        db.closeConnection()


def test_unknown_subquery_option():
    db = database(config({'locale': 'it'}))
    try:
        with pytest.raises(UnsupportedFeatureError, match="subquery option 'locale' is not available in this release"):
            compile_customer(db, '$sub')
    finally:
        db.closeConnection()


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
            db.packages().package('main', sqlschema='main', sqlprefix=False).tables().table('item', pkey='id').columns().column('id', dtype='I')
    db = AsqueelDb(Config).session()
    try:
        db.updateEnv(storename='branch')
        with pytest.raises(UnsupportedFeatureError,
                           match="environment key storename='branch': database stores are not available"):
            db.table('main.item').query().fetch()
    finally:
        db.closeConnection()
        db.shared.close()
