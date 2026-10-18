"""Closed grammar: what lies outside it raises, naming what the user wrote."""
import pytest

from asqueel import AsqueelDb, SqlDatabaseConfig, SqlTable
from asqueel.contracts import UnsupportedFeatureError


def package():
    config = SqlDatabaseConfig()
    pkg = config.source.db('closed').packages().package('app')
    return config, pkg


@pytest.mark.parametrize('key', [
    'multi_tenant', 'default_subtable', 'ext_mypkg', 'totalizer_total',
    'hierarchical_caption_field', 'group_b_address', 'x_foo',
])
def test_table_attribute_outside_the_grammar_names_attribute_and_element(key):
    _, pkg = package()
    with pytest.raises(ValueError, match=f"Element 'table' does not accept '{key}'"):
        pkg.table('customer', pkey='id', **{key: True})


@pytest.mark.parametrize('key', ['x_foo', 'cell_format', 'template_name', 'batch_assign_tags', 'atc_x'])
def test_column_attribute_outside_the_grammar_names_attribute_and_element(key):
    _, pkg = package()
    table = pkg.table('customer', pkey='id')
    with pytest.raises(ValueError, match=f"Element 'column' does not accept '{key}'"):
        table.column('id', dtype='L', **{key: 'value'})


def test_ignore_tenant_on_a_relation_is_outside_the_grammar():
    _, pkg = package()
    pkg.table('customer', pkey='id').column('id', dtype='L')
    column = pkg.table('invoice', pkey='id').column('customer_id', dtype='L')
    with pytest.raises(ValueError, match="Element 'relation' does not accept 'ignore_tenant'"):
        column.relation('app.customer.id', ignore_tenant=True)


@pytest.mark.parametrize('call', ['subtable', 'tenant'])
def test_subtable_and_tenant_are_not_in_the_grammar(call):
    _, pkg = package()
    table = pkg.table('customer', pkey='id')
    target = table.options() if call == 'tenant' else table
    with pytest.raises(AttributeError, match=f"'{call}'"):
        getattr(target, call)()


def test_a_key_the_expansion_generates_still_raises_when_written_by_hand():
    config, pkg = package()
    table = pkg.table('customer', pkey='id')
    table.options().sys_fields()
    table.column('code', dtype='T')
    table.attr['group_zzz'] = 'System'
    with pytest.raises(ValueError, match="unknown attribute 'group_zzz' on <table>"):
        config.render(mode='objects_tree')


def test_option_declared_by_a_mixed_in_grammar_is_accepted():
    from genro_builders.builder import element
    from asqueel.option_elements import BehaviorOptionElements

    class FoobarOptions(BehaviorOptionElements):
        @element(parent_tags='options', sub_tags='', node_label='foobar')
        def foobar(self, *, level: int = 1, enabled: bool = True):
            ...

    class Config(FoobarOptions, SqlDatabaseConfig):
        pass

    config = Config()
    table = config.source.db('closed').packages().package('app').table('customer', pkey='id')
    table.column('id', dtype='L')
    assert 'foobar' in config.table_options
    assert table.options().foobar(level=2).get_attr('level') == 2
    with pytest.raises(ValueError, match="Element 'foobar' does not accept 'colour'"):
        table.options().foobar(colour='red')


def database(tmp_path, table_class=None):
    class Config(SqlDatabaseConfig):
        def main(self, root):
            db = root.db(implementation='sqlite')
            db.connection(name=str(tmp_path / 'closed.db'))
            table = db.schemas().schema('main').tables().table(
                'item', pkey='id', **({'x_table_class': table_class} if table_class else {}))
            table.columns().column('id', dtype='I')
    return AsqueelDb(Config)


@pytest.mark.parametrize('method', ['trigger_onInserted_mypkg', 'formulaColumn_foo'])
def test_table_class_with_a_legacy_method_names_it(tmp_path, method):
    table_class = type('Item', (SqlTable,), {method: lambda self, *args, **kwargs: None})
    with pytest.raises(UnsupportedFeatureError, match=f"table method '{method}' is not available"):
        database(tmp_path, table_class)


@pytest.mark.parametrize('key', ['sql_comment', 'sql_details', 'env_main_item_condition_active'])
def test_legacy_environment_keys_raise_at_execution(tmp_path, key):
    db = database(tmp_path)
    try:
        db.execute('CREATE TABLE item (id INTEGER PRIMARY KEY)')
        db.updateEnv(**{key: 'value'})
        with pytest.raises(UnsupportedFeatureError, match=f"environment key '{key}' is not available"):
            db.table('main.item').query().fetch()
    finally:
        db.close()


def test_subtable_query_option_names_the_option(tmp_path):
    db = database(tmp_path)
    try:
        with pytest.raises(UnsupportedFeatureError, match='subtable'):
            db.table('main.item').query(subtable='*')
    finally:
        db.close()
