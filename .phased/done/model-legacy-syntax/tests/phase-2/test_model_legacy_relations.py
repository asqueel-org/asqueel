"""Relations, indexes and composite columns in their legacy spelling (Macro 4, Phase 2)."""
import pytest

from asqueel import AsqueelDb, SqlDatabaseConfig


def package():
    config = SqlDatabaseConfig()
    root = config.source.db('legacy', implementation='sqlite')
    root.connection('main', database=':memory:')
    pkg = root.packages().package('app', sqlschema='main', sqlprefix=False)
    customer = pkg.table('customer', pkey='id')
    customer.column('id', dtype='L')
    customer.column('code', dtype='A', size='0:10')
    customer.column('valid_from', dtype='D')
    customer.column('valid_to', dtype='D')
    return config, pkg, customer


def invoice(pkg, **relation):
    table = pkg.table('invoice', pkey='id')
    table.column('id', dtype='L')
    table.column('date', dtype='D')
    table.column('ccode', dtype='A', size='0:10')
    table.column('customer_id', dtype='L').relation('app.customer.id', **relation)
    return table


def test_one_one_star_names_the_inverse_after_the_many_table():
    config, pkg, customer = package()
    invoice(pkg, one_one='*')
    sql = AsqueelDb(config).table('app.customer').query(columns='@invoice.date').sqltext
    assert 'LEFT JOIN "main"."invoice"' in sql


def test_one_one_true_keeps_the_default_inverse_name():
    config, pkg, customer = package()
    invoice(pkg, one_one=True, relation_name='inv')
    sql = AsqueelDb(config).table('app.customer').query(columns='@inv.date').sqltext
    assert 'LEFT JOIN "main"."invoice"' in sql


@pytest.mark.parametrize('key', ['cnd', 'join_on'])
def test_cnd_and_join_on_replace_the_join_condition(key):
    config, pkg, customer = package()
    invoice(pkg, **{key: '$ccode = @customer_id.code'})
    sql = AsqueelDb(config).table('app.invoice').query(columns='@customer_id.code').sqltext
    condition = sql.split(' ON ', 1)[1]
    assert 'ccode' in condition and 'code' in condition
    assert 'customer_id' not in condition


def test_cnd_relation_projects_no_foreign_key(tmp_path):
    config, pkg, customer = package()
    config.source.get_node('db').value.get_node('connection').attr['database'] = str(tmp_path / 'cnd.db')
    invoice(pkg, cnd='$ccode = @customer_id.code')
    commands = AsqueelDb(config).migration_plan().commands
    assert 'FOREIGN KEY' not in commands.upper()


def test_between_builds_the_legacy_range_condition():
    config, pkg, customer = package()
    invoice(pkg, between='$date;@customer_id.valid_from;@customer_id.valid_to')
    sql = AsqueelDb(config).table('app.invoice').query(columns='@customer_id.code').sqltext
    condition = sql.split(' ON ', 1)[1]
    assert 'valid_from' in condition and 'valid_to' in condition


def indexes(config):
    model = AsqueelDb(config).model.table('app.customer')
    return {name: dict(index.attributes) for name, index in model.indexes.items()}


def test_index_takes_columns_first_and_a_legacy_default_name():
    config, pkg, customer = package()
    customer.index('code')
    customer.index(['valid_from', 'valid_to'], unique=True)
    customer.index(columns='code,valid_from', name='ix_named')
    found = indexes(config)
    assert found['customer_code_key']['columns'] == 'code'
    assert found['customer_valid_from_valid_to_key']['columns'] == 'valid_from,valid_to'
    assert found['customer_valid_from_valid_to_key']['unique'] is True
    assert found['ix_named']['columns'] == 'code,valid_from'


def composite(pkg, pkey):
    table = pkg.table('line', pkey=pkey)
    table.column('doc', dtype='L')
    table.column('pos', dtype='L')
    table.compositeColumn('doc_pos', columns='doc,pos')
    return table


def test_composite_primary_key_is_declared_by_its_composite_column():
    config, pkg, customer = package()
    composite(pkg, 'doc_pos')
    model = AsqueelDb(config).model.table('app.line')
    assert model.pkey == 'doc_pos'
    assert model.pkeys == ['doc', 'pos']


def test_comma_joined_primary_key_is_not_a_legacy_form():
    config, pkg, customer = package()
    composite(pkg, 'doc,pos')
    with pytest.raises(ValueError, match="pkey 'doc,pos'"):
        AsqueelDb(config)
