"""Grammar cleanup, Phase 2: the model starts only from packages; relation takes related_column and insensitive as legacy."""
import pytest

from asqueel import AsqueelDb, SqlDatabaseConfig
from asqueel.reader import SqlModelReader
from tests.model_cleanup_support import golden, normalized

LABELS = ['test_invoice_pg', 'two_schemas', 'sqlite']


def nodes(bag):
    for node in bag:
        yield node
        if hasattr(node.value, 'get_node'):
            yield from nodes(node.value)


def test_schemas_is_outside_the_grammar():
    config = SqlDatabaseConfig()
    with pytest.raises(AttributeError, match="'schemas'"):
        config.source.db('nos').schemas()


def test_schema_is_outside_the_grammar():
    config = SqlDatabaseConfig()
    with pytest.raises(AttributeError, match="'schema'"):
        config.source.db('nos').packages().schema('sales')


@pytest.mark.parametrize('label', LABELS)
def test_the_reader_builds_one_package_per_schema(label):
    structure = golden(label, 'migration')
    source = SqlModelReader(structure).to_builder().source
    tags = {node.node_tag for node in nodes(source)}
    assert 'schemas' not in tags and 'schema' not in tags
    packages = {node.label: node.attr for node in nodes(source) if node.node_tag == 'package'}
    assert set(packages) == set(structure['root']['schemas'])
    for name, attributes in packages.items():
        assert attributes.get('sqlschema') == name
        assert attributes.get('sqlprefix') is False


@pytest.mark.parametrize('label', LABELS)
def test_the_reader_round_trip_keeps_the_migration_structure(label):
    structure = golden(label, 'migration')
    assert normalized(SqlModelReader(structure).to_builder().render(mode='migration')) == structure


def related():
    config = SqlDatabaseConfig()
    root = config.source.db('rel', implementation='sqlite')
    root.connection('main', database=':memory:')
    pkg = root.packages().package('app', sqlschema='main', sqlprefix=False)
    customer = pkg.table('customer', pkey='id')
    customer.column('id', dtype='A', size='22')
    invoice = pkg.table('invoice', pkey='id')
    invoice.column('id', dtype='L')
    return config, invoice.column('customer_id', dtype='A', size='22')


def test_relation_takes_related_column_by_keyword():
    config, column = related()
    column.relation(related_column='app.customer.id', relation_name='invoices')
    attributes = AsqueelDb(config).model.relations.get_node('app.invoice.@customer_id').attr
    assert attributes['one_relation'] == 'app.customer.id'


def test_relation_refuses_to():
    _, column = related()
    with pytest.raises(ValueError, match="Element 'relation' does not accept 'to'"):
        column.relation(to='app.customer.id')


def test_insensitive_reaches_the_relation_tree():
    config, column = related()
    column.relation('app.customer.id', insensitive=True)
    attributes = AsqueelDb(config).model.relations.get_node('app.invoice.@customer_id').attr
    assert attributes['case_insensitive'] in (True, 'True')


def test_relation_refuses_case_insensitive():
    _, column = related()
    with pytest.raises(ValueError, match="Element 'relation' does not accept 'case_insensitive'"):
        column.relation('app.customer.id', case_insensitive=True)
