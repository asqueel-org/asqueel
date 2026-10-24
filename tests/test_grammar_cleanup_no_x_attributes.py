"""Grammar cleanup, Phase 3: no x_* parameter in the grammar, no x_* attribute in the source or the live model; Table comes from the package layout."""
import importlib
import inspect
import textwrap

import pytest

from asqueel import AsqueelDb, SqlDatabaseConfig
from tests.model_cleanup_support import example_sources, objects_dump

LABELS = ['test_invoice_pg', 'two_schemas', 'sqlite']


def nodes(bag):
    for node in bag:
        yield node
        if hasattr(node.value, 'get_node'):
            yield from nodes(node.value)


def package():
    config = SqlDatabaseConfig()
    root = config.source.db('nox', implementation='sqlite')
    root.connection('main', database=':memory:')
    return config, root.packages().package('app', sqlschema='main', sqlprefix=False)


@pytest.mark.parametrize('key', ['x_table_class', 'x_expanded_legacy', 'x_logical_pkey'])
def test_the_table_has_no_x_parameter(key):
    _, pkg = package()
    with pytest.raises(ValueError, match=f"Element 'table' does not accept '{key}'"):
        pkg.table('item', pkey='id', **{key: True})


@pytest.mark.parametrize('key', ['x_identity', 'x_generation'])
def test_the_column_has_no_x_parameter(key):
    _, pkg = package()
    item = pkg.table('item', pkey='id')
    with pytest.raises(ValueError, match=f"Element 'column' does not accept '{key}'"):
        item.column('id', dtype='L', **{key: 'value'})


@pytest.mark.parametrize('key', ['x_weak', 'x_canonical', 'x_name'])
def test_the_relation_has_no_x_parameter(key):
    _, pkg = package()
    pkg.table('customer', pkey='id').column('id', dtype='L')
    column = pkg.table('invoice', pkey='id').column('customer_id', dtype='L')
    with pytest.raises(ValueError, match=f"Element 'relation' does not accept '{key}'"):
        column.relation('app.customer.id', **{key: True})


@pytest.mark.parametrize('label', LABELS)
def test_the_examples_keep_no_x_attribute_in_the_source(label):
    db = AsqueelDb(example_sources()[label])
    try:
        db.model
        found = [(node.node_tag, node.label, key) for node in nodes(db.config.builder.source)
                 for key in node.attr if key.startswith('x_')]
        assert found == []
    finally:
        db.closeConnection()


@pytest.mark.parametrize('label', LABELS)
def test_the_examples_keep_no_x_attribute_in_the_live_model(label):
    db = AsqueelDb(example_sources()[label])
    try:
        dump = objects_dump(db)
    finally:
        db.closeConnection()
    found = []
    for name, table in dump['tables'].items():
        found += [(name, key) for key in table['attributes'] if key.startswith('x_')]
        for group in ('columns', 'virtual_columns'):
            for column, data in table[group].items():
                found += [(f'{name}.{column}', key) for key in data['attributes'] if key.startswith('x_')]
    assert found == []


@pytest.mark.parametrize('label', LABELS)
def test_the_examples_keep_no_python_class_in_the_source(label):
    db = AsqueelDb(example_sources()[label])
    try:
        db.model
        found = [(node.label, key) for node in nodes(db.config.builder.source)
                 for key, value in node.attr.items() if inspect.isclass(value)]
        assert found == []
    finally:
        db.closeConnection()


MAIN = '''
class Package:
    def config_attributes(self):
        return dict(name_long='Sales')
'''

CUSTOMER = '''
class Table:
    def config_db(self, pkg):
        tbl = pkg.table('customer', pkey='id')
        tbl.column('id', dtype='serial')
        tbl.column('name')

    def trigger_onInserting(self, record):
        record['name'] = record['name'].upper()
'''


def layout_database(tmp_path):
    folder = tmp_path / 'sales'
    (folder / 'model').mkdir(parents=True)
    (folder / 'main.py').write_text(textwrap.dedent(MAIN))
    (folder / 'model' / 'customer.py').write_text(textwrap.dedent(CUSTOMER))
    config = SqlDatabaseConfig()
    root = config.source.db('layout', implementation='sqlite')
    root.connection('main', database=str(tmp_path / 'layout.sqlite'))
    root.packages().package('sales', path=str(folder))
    return folder, AsqueelDb(config)


def test_the_package_keeps_its_path_in_the_source(tmp_path):
    folder, db = layout_database(tmp_path)
    try:
        db.model
        packages = [node for node in nodes(db.config.builder.source) if node.node_tag == 'package']
        assert [node.attr.get('path') for node in packages] == [str(folder)]
    finally:
        db.closeConnection()


def test_the_table_class_comes_from_the_layout_module(tmp_path):
    _, db = layout_database(tmp_path)
    try:
        db.migrate()
        db.commit()
        customer = db.table('sales.customer')
        assert customer.insert({'name': 'acme'})['name'] == 'ACME'
        assert type(customer).__name__ == 'customer'
    finally:
        db.closeConnection()


def test_a_composite_pkey_stays_logical_on_the_live_table():
    config, pkg = package()
    doc = pkg.table('doc', pkey='identity')
    doc.column('code')
    doc.column('year', dtype='L')
    doc.compositeColumn('identity', columns='code,year')
    live = AsqueelDb(config).model.table('app.doc')
    assert (live.pkey, list(live.pkeys)) == ('identity', ['code', 'year'])


def test_the_legacy_xml_loader_is_gone():
    with pytest.raises(ModuleNotFoundError):
        importlib.import_module('asqueel.legacy_source')
