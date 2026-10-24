"""Model cleanup, Phase 4: dynamic columns live in virtual_columns as legacy; physical columns on the table."""
from asqueel import AsqueelDb, SqlDatabaseConfig
from tests.package_layout_support import write_layout

CUSTOMER = '''
class Table:
    def config_db(self, pkg):
        customer = pkg.table('customer', pkey='id')
        customer.column('id', dtype='serial')
        customer.column('code')
        customer.column('year', dtype='L')

    def formulaColumn_loud(self):
        return dict(name='loud', sql_formula='upper($code)', dtype='T')

    def formulaColumn_scaled(self):
        return dict(name='scaled', sql_formula=f"$year * {self.db.currentEnv.get('factor', 1)}", dtype='L')
'''


def database(tmp_path):
    config = SqlDatabaseConfig()
    root = config.source.db('live', implementation='sqlite')
    root.connection('main', database=':memory:')
    pkg = root.packages().package(
        'app', sqlschema='main', sqlprefix=False, path=write_layout(tmp_path / 'app', customer=CUSTOMER))
    doc = pkg.table('doc', pkey='identity')
    doc.column('code')
    doc.column('year', dtype='L')
    doc.compositeColumn('identity', columns='code,year')
    return AsqueelDb(config)


def test_a_dynamic_column_is_one_object_inside_virtual_columns(tmp_path):
    table = database(tmp_path).model.table('app.customer')
    first = table.column('loud')
    assert table.column('loud') is first
    assert table.virtual_columns['loud'] is first
    assert table.dynamic_columns['loud'] is first


def test_dynamic_columns_are_rebuilt_with_a_new_environment(tmp_path):
    db = database(tmp_path)
    table = db.model.table('app.customer')
    db.currentEnv['factor'] = 2
    first = table.column('scaled')
    assert '2' in first.attributes['sql_formula']
    db.clearCurrentEnv()
    db.currentEnv['factor'] = 5
    second = table.column('scaled')
    assert second is not first
    assert '5' in second.attributes['sql_formula']


def test_physical_columns_are_read_from_the_table(tmp_path):
    model = database(tmp_path).model
    assert not hasattr(model, 'physical_columns')
    assert list(model.table('app.doc').physical_columns('identity')) == ['code', 'year']
    assert list(model.table('app.customer').physical_columns('id')) == ['id']


def test_membership_ignores_case_as_lookup_does():
    config = SqlDatabaseConfig()
    root = config.source.db('case', implementation='sqlite')
    root.connection('main', database=':memory:')
    item = root.packages().package('app', sqlschema='main', sqlprefix=False).table('item', pkey='id')
    item.options().sysFields()
    item.column('fullName')
    table = AsqueelDb(config).model.table('app.item')
    assert 'fullname' in table.columns and 'fullName' in table.columns
    assert 'sysfields' in table.options and 'sysFields' in table.options
    assert None not in table.columns
