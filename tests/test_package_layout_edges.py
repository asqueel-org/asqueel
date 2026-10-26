"""Edges of the legacy package layout: binding by module name, custom types, refused members."""
import textwrap

import pytest

from asqueel import AsqueelDb, SqlDatabaseConfig
from asqueel.contracts import UnsupportedFeatureError

MAIN = '''
class Package:
    def config_attributes(self):
        return dict(sqlschema='main', sqlprefix=False)

    def custom_type_money(self):
        return dict(dtype='N', size='12,2', format='#,###.00')
'''

CUSTOMER = '''
class Table:
    def config_db(self, pkg):
        tbl = pkg.table('customer', pkey='id')
        tbl.column('id', dtype='serial')
        tbl.column('name')
        tbl.column('balance', dtype='money')

    def trigger_onInserting(self, record):
        record['name'] = record['name'].upper()
'''


def write_package(folder, main=MAIN, **modules):
    (folder / 'model').mkdir(parents=True)
    (folder / 'main.py').write_text(textwrap.dedent(main))
    for name, source in modules.items():
        (folder / 'model' / f'{name}.py').write_text(textwrap.dedent(source))
    return str(folder)


def config(tmp_path, path):
    source = SqlDatabaseConfig()
    root = source.source.db('layout', implementation='sqlite')
    root.connection('main', database=str(tmp_path / 'layout.sqlite'))
    root.packages().package('sales', path=path)
    return source


def test_custom_type_gives_any_column_attribute(tmp_path):
    model = AsqueelDb(config(tmp_path, write_package(tmp_path / 'sales', customer=CUSTOMER))).model
    balance = model.table('sales.customer').column('balance')
    assert (balance.attributes['dtype'], balance.attributes['size']) == ('N', '12,2')
    assert balance.attributes['format'] == '#,###.00'


def test_a_layer_extending_a_layout_table_keeps_its_table_class(tmp_path):
    base = config(tmp_path, write_package(tmp_path / 'sales', customer=CUSTOMER))
    overlay = SqlDatabaseConfig()
    overlay.source.db('layout').packages().package('sales').table('customer').column('extra')
    db = AsqueelDb(overlay, parents=[base]).session()
    try:
        db.migrate()
        assert db.table('sales.customer').insert({'name': 'ada'})['name'] == 'ADA'
    finally:
        db.closeConnection()
        db.shared.close()


def test_a_model_module_declares_the_table_named_after_it(tmp_path):
    folder = write_package(tmp_path / 'sales', cust=CUSTOMER)
    with pytest.raises(ValueError, match="model/cust.py declares no table 'cust'"):
        AsqueelDb(config(tmp_path, folder))


def test_package_without_config_attributes_loads(tmp_path):
    main = '''
class Package:
    pass
'''
    folder = write_package(tmp_path / 'sales', main=main, customer=CUSTOMER.replace("dtype='money'", "dtype='N'"))
    source = config(tmp_path, folder)
    assert AsqueelDb(source).model.table('sales.customer') is not None


@pytest.mark.parametrize('main, member', [
    (MAIN + '\nclass Table:\n    pass\n', 'main.py Table'),
    (MAIN.replace('class Package:', 'class Package:\n    def onBuildingDbobj(self):\n        pass\n'),
     'Package.onBuildingDbobj'),
    (MAIN.replace('class Package:', 'class Package:\n    def config_db(self, pkg):\n        pass\n'),
     'Package.config_db'),
])
def test_main_members_without_a_counterpart_are_named(tmp_path, main, member):
    folder = write_package(tmp_path / 'sales', main=main, customer=CUSTOMER)
    with pytest.raises(UnsupportedFeatureError, match=member):
        AsqueelDb(config(tmp_path, folder))


def test_cnd_relation_refuses_an_explicit_foreign_key():
    source = SqlDatabaseConfig()
    pkg = source.source.db('cnd').packages().package('app')
    pkg.table('customer', pkey='id').column('id', dtype='L')
    column = pkg.table('invoice', pkey='id').column('customer_id', dtype='L')
    with pytest.raises(ValueError, match='a relation with cnd= has no foreign key'):
        column.relation('app.customer.id', cnd='$customer_id = @customer_id.id', foreign_key=True)


@pytest.mark.parametrize('extra, check', [
    ("indexed='y'", lambda column: column.attributes['indexed'] is True),
    ('encrypted=True', None),
])
def test_custom_type_values_follow_the_column_rules(tmp_path, extra, check):
    main = MAIN.replace("format='#,###.00')", f"format='#,###.00', {extra})")
    source = config(tmp_path, write_package(tmp_path / 'sales', main=main, customer=CUSTOMER))
    if check is None:
        with pytest.raises(UnsupportedFeatureError, match='encrypted is not available in this release'):
            AsqueelDb(source)
    else:
        assert check(AsqueelDb(source).model.table('sales.customer').column('balance'))


def test_custom_type_without_dtype_raises(tmp_path):
    main = MAIN.replace("dtype='N', ", '')
    with pytest.raises(ValueError, match=r'custom_type_money\(\) returns no dtype'):
        AsqueelDb(config(tmp_path, write_package(tmp_path / 'sales', main=main, customer=CUSTOMER)))
