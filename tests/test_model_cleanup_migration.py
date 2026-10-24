"""Model cleanup, Phase 5: the migration structure is rendered from the source by a RendererBase renderer."""
import importlib

from genro_builders.renderer import RendererBase
import pytest

import asqueel
from asqueel import AsqueelDb, SqlBuilder, SqlMigrationRenderer
from tests.model_cleanup_support import example_sources, golden, normalized


def physical_names(structure):
    return {schema: {table: list(item['columns']) for table, item in data['tables'].items()}
            for schema, data in structure['root']['schemas'].items()}


def sqlname_recipe():
    builder = SqlBuilder()
    table = (builder.source.db('x').packages().package('s', sqlschema='phys_s', sqlprefix=False)
             .tables().table('t', pkey='id', sqlname='phys_t'))
    columns = table.columns()
    columns.column('id', dtype='I')
    columns.column('name', dtype='A', size='0:20', sqlname='phys_name')
    return builder


def test_sqlname_is_always_applied():
    structure = sqlname_recipe().render(mode='migration')
    assert physical_names(structure) == {'phys_s': {'phys_t': ['id', 'phys_name']}}


def test_the_live_objects_agree_with_the_structure():
    table = AsqueelDb(sqlname_recipe()).model.table('s.t')
    assert (table.sqlschema, table.sqlname, table.columns['name'].sqlname) == ('phys_s', 'phys_t', 'phys_name')


@pytest.mark.parametrize('label', ['test_invoice_pg', 'two_schemas', 'sqlite'])
def test_the_examples_keep_their_migration_structure(label):
    db = AsqueelDb(example_sources()[label])
    try:
        assert normalized(db.config.builder.render(mode='migration')) == golden(label, 'migration')
    finally:
        db.closeConnection()


def test_the_migration_renderer_is_a_builders_renderer():
    assert RendererBase in SqlMigrationRenderer.__mro__
    assert type(SqlBuilder().get_renderer('migration')) is SqlMigrationRenderer


def test_the_projection_through_live_objects_is_gone():
    assert not hasattr(asqueel, 'to_physical_builder')
    for module in ('asqueel.projection', 'asqueel.object_tree_projection'):
        with pytest.raises(ModuleNotFoundError):
            importlib.import_module(module)
