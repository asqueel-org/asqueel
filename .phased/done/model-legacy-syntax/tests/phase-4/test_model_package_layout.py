"""A package folder in the legacy layout, loaded by the asqueel configuration (Macro 4, Phase 4)."""
import textwrap

import pytest

from asqueel import AsqueelDb, SqlDatabaseConfig
from asqueel.contracts import UnsupportedFeatureError

MAIN = '''
class Package:
    def config_attributes(self):
        return dict(sqlschema='main', sqlprefix=False, name_long='Sales')

    def custom_type_money(self):
        return dict(dtype='N', size='12,2', name_long='Money')
'''

CUSTOMER = '''
class Table:
    def config_db(self, pkg):
        tbl = pkg.table('customer', pkey='id', name_long='Customer')
        tbl.column('id', dtype='serial')
        tbl.column('name')
        tbl.column('balance', dtype='money', name_long='Balance')

    def trigger_onInserting(self, record):
        record['name'] = record['name'].upper()
'''

INVOICE = '''
class Table:
    def config_db(self, pkg):
        tbl = pkg.table('invoice', pkey='id')
        tbl.column('id', dtype='serial')
        tbl.column('customer_id', dtype='L').relation('sales.customer.id', relation_name='invoices')
'''


def write_package(folder, **tables):
    (folder / 'model').mkdir(parents=True)
    (folder / 'main.py').write_text(textwrap.dedent(MAIN))
    for name, source in tables.items():
        (folder / 'model' / f'{name}.py').write_text(textwrap.dedent(source))
    return folder


def database(tmp_path, **tables):
    folder = write_package(tmp_path / 'sales', **tables)
    config = SqlDatabaseConfig()
    root = config.source.db('layout', implementation='sqlite')
    root.connection('main', database=str(tmp_path / 'layout.sqlite'))
    root.packages().package('sales', path=str(folder))
    return AsqueelDb(config)


def test_tables_come_from_config_db_and_package_attributes_from_main(tmp_path):
    db = database(tmp_path, customer=CUSTOMER, invoice=INVOICE)
    model = db.model
    assert model.package('sales').attributes['name_long'] == 'Sales'
    assert sorted(model.package('sales').tables) == ['customer', 'invoice']
    assert model.table('sales.customer').name_long == 'Customer'


def test_custom_type_method_supplies_the_column_attributes(tmp_path):
    db = database(tmp_path, customer=CUSTOMER)
    balance = db.model.table('sales.customer').column('balance')
    assert balance.attributes['dtype'] == 'N'
    assert balance.attributes['size'] == '12,2'
    assert balance.name_long == 'Balance'


def test_the_table_class_is_the_runtime_table(tmp_path):
    db = database(tmp_path, customer=CUSTOMER)
    db.migrate()
    record = db.table('sales.customer').insert({'name': 'ada'})
    assert record['name'] == 'ADA'


def test_config_db_custom_names_the_missing_feature(tmp_path):
    custom = CUSTOMER + '''
    def config_db_custom(self, pkg):
        pass
'''
    with pytest.raises(UnsupportedFeatureError, match='config_db_custom is not available in this release'):
        database(tmp_path, customer=custom)


def test_a_layout_package_sits_beside_a_recipe_package(tmp_path):
    folder = write_package(tmp_path / 'sales', customer=CUSTOMER)
    config = SqlDatabaseConfig()
    root = config.source.db('layout', implementation='sqlite')
    root.connection('main', database=str(tmp_path / 'layout.sqlite'))
    packages = root.packages()
    packages.package('sales', path=str(folder))
    crm = packages.package('crm', sqlschema='main')
    crm.options().type('code', dtype='A', size='0:10')
    contact = crm.table('contact', pkey='id')
    contact.column('id', dtype='serial')
    contact.column('code', dtype='code')
    contact.column('customer_id', dtype='L').relation('sales.customer.id')
    model = AsqueelDb(config).model
    assert model.table('crm.contact').column('code').attributes['size'] == '0:10'
    assert model.table('sales.customer').column('balance').attributes['size'] == '12,2'
