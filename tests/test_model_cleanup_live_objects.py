"""Model cleanup, Phase 4: dynamic columns live in virtual_columns as legacy; physical columns on the table."""
from asqueel import AsqueelDb, SqlDatabaseConfig, SqlTable


class Customer(SqlTable):
    def formulaColumn_loud(self):
        return dict(name='loud', sql_formula='upper($code)', dtype='T')

    def formulaColumn_scaled(self):
        return dict(name='scaled', sql_formula=f"$year * {self.db.currentEnv.get('factor', 1)}", dtype='L')


def database():
    config = SqlDatabaseConfig()
    root = config.source.db('live', implementation='sqlite')
    root.connection('main', database=':memory:')
    pkg = root.packages().package('app', sqlschema='main', sqlprefix=False)
    customer = pkg.table('customer', pkey='id', x_table_class=Customer)
    customer.column('id', dtype='serial')
    customer.column('code')
    customer.column('year', dtype='L')
    doc = pkg.table('doc', pkey='identity')
    doc.column('code')
    doc.column('year', dtype='L')
    doc.compositeColumn('identity', columns='code,year')
    return AsqueelDb(config)


def test_a_dynamic_column_is_one_object_inside_virtual_columns():
    table = database().model.table('app.customer')
    first = table.column('loud')
    assert table.column('loud') is first
    assert table.virtual_columns['loud'] is first
    assert table.dynamic_columns['loud'] is first


def test_dynamic_columns_are_rebuilt_with_a_new_environment():
    db = database()
    table = db.model.table('app.customer')
    db.currentEnv['factor'] = 2
    first = table.column('scaled')
    assert '2' in first.attributes['sql_formula']
    db.clearCurrentEnv()
    db.currentEnv['factor'] = 5
    second = table.column('scaled')
    assert second is not first
    assert '5' in second.attributes['sql_formula']


def test_physical_columns_are_read_from_the_table():
    model = database().model
    assert not hasattr(model, 'physical_columns')
    assert list(model.table('app.doc').physical_columns('identity')) == ['code', 'year']
    assert list(model.table('app.customer').physical_columns('id')) == ['id']
