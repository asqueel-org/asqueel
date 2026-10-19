"""Legacy model features absent from this release raise an error that names them (Macro 4, Phase 3)."""
import pytest

from asqueel import AsqueelDb, SqlDatabaseConfig
from asqueel.contracts import UnsupportedFeatureError


def package():
    config = SqlDatabaseConfig()
    root = config.source.db('missing', implementation='sqlite')
    root.connection('main', database=':memory:')
    pkg = root.packages().package('app', sqlschema='main', sqlprefix=False)
    customer = pkg.table('customer', pkey='id')
    customer.column('id', dtype='L')
    customer.column('name')
    invoice = pkg.table('invoice', pkey='id')
    invoice.column('id', dtype='L')
    invoice.column('customer_id', dtype='L').relation('app.customer.id', relation_name='invoices')
    return config, pkg, customer


def missing(name):
    return pytest.raises(UnsupportedFeatureError, match=f'{name} is not available in this release')


@pytest.mark.parametrize('key', ['variant', 'ext_mypkg', 'mixin'])
def test_table_attribute_of_an_absent_feature_names_it(key):
    _, pkg, _ = package()
    with missing(key):
        pkg.table('other', pkey='id', **{key: True})


@pytest.mark.parametrize('key', ['localized', 'variant', 'ext_mypkg'])
def test_column_attribute_of_an_absent_feature_names_it(key):
    _, _, customer = package()
    with missing(key):
        customer.column('label', **{key: True})


def test_join_column_names_the_missing_element():
    _, _, customer = package()
    with missing('joinColumn'):
        customer.joinColumn('linked', dtype='L')


@pytest.mark.parametrize('name', ['rowcaption', 'newrecord_caption', 'starColumns', 'getRelation',
                                  'getJoiner', 'relations_one', 'relations_many', 'manyRelationsList',
                                  'relationExplorer'])
def test_model_and_table_accessors_of_absent_features_name_them(name):
    config, _, _ = package()
    db = AsqueelDb(config)
    for target in (db.model.table('app.customer'), db.table('app.customer')):
        with missing(name):
            getattr(target, name)


@pytest.mark.parametrize('name', ['tableMixin', 'packageMixin'])
def test_mixin_installers_name_the_missing_feature(name):
    config, _, _ = package()
    db = AsqueelDb(config)
    with missing(name):
        getattr(db, name)


def test_set_join_condition_names_the_missing_feature():
    config, _, _ = package()
    db = AsqueelDb(config)
    with missing('setJoinCondition'):
        db.table('app.customer').query().setJoinCondition


def test_jc_keyword_names_the_join_condition_feature():
    config, _, _ = package()
    db = AsqueelDb(config)
    with missing('join condition keyword jc_open'):
        db.table('app.customer').query(jc_open='@invoices:$id IS NOT NULL')
