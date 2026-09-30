from genro_builders.builder import element
import pytest

from asqueel.configuration import ConfigurationView, SqlDatabaseConfig, build_database
from asqueel.elements import ColumnElements, SchemaElements, TableElements


class Recipe(SqlDatabaseConfig):
    def main(self, root):
        table = root.db('demo').schemas().schema('sales').tables().table('customer', pkey='id')
        table.columns().column('id', dtype='I')


class Overlay(SqlDatabaseConfig):
    def main(self, root):
        root.db('demo', conninfo='dbname=overlay')


def test_layering_owns_instances_and_preserves_parent_tree():
    parent = Recipe()
    parent.create()
    overlay = Overlay()
    overlay.create()
    first = build_database(overlay, parents=[parent])
    second = build_database(parent)
    assert first.config('conninfo') == 'dbname=overlay'
    assert second.config('conninfo') == ''
    assert parent.source.get_item('db?conninfo') is None
    assert overlay.source.get_node('db.schemas') is None
    assert first.model.table('customer').pkey == ('id',)
    assert first.model is not second.model
    assert first.table('customer') is not second.table('customer')
    first.close()
    second.close()


def test_direct_object_render_uses_defaults_without_connecting(monkeypatch):
    import psycopg
    def forbidden(*args, **kwargs):
        raise AssertionError('object materialization must not connect')
    monkeypatch.setattr(psycopg, 'connect', forbidden)
    recipe = Recipe()
    recipe.create()
    database = recipe.render()
    assert database.config('implementation') == 'postgresql'
    assert database.config('conninfo') == ''
    assert database.table('customer') is database.table('sales.customer')
    with pytest.raises(TypeError, match='object'):
        recipe.render(target=False)
    database.close()


def test_scoped_configuration_defaults_and_missing_values():
    database = build_database(Recipe)
    view = ConfigurationView(database.config, 'schemas.sales.tables.customer')
    assert view('pkey') == 'id'
    assert view.scope('columns.id')('dtype') == 'I'
    assert view('missing', default=False) is False
    with pytest.raises(KeyError):
        view('missing')
    database.close()


class MountedColumns(TableElements, ColumnElements):
    @element(parent_tags='columns', _meta={'projects_column': True})
    def column(self, name: str, dtype: str = 'I', ui_hint: str = 'mounted default'):
        ...


class TableConfig:
    grammar = MountedColumns


class MountedSchema(SchemaElements):
    @element(parent_tags='tables', _meta={'subbuilder': 'x_config:grammar'})
    def table(self, name: str, pkey: str | None = None, x_config=None, **extra):
        ...


class SchemaConfig:
    grammar = MountedSchema


class MountedRecipe(SqlDatabaseConfig):
    @element(parent_tags='schemas', _meta={'subbuilder': 'x_config:grammar'})
    def schema(self, name: str, x_config=None, **extra):
        ...

    def main(self, root):
        schema = root.db('demo').schemas().schema(name='sales', x_config=SchemaConfig)
        table = schema.tables().table(name='customer', pkey='id', x_config=TableConfig)
        columns = table.columns()
        columns.column(name='id', dtype='I', ui_hint='explicit')
        columns.column(name='label')


def test_mounted_grammar_validation_and_signature_default():
    database = build_database(MountedRecipe)
    view = ConfigurationView(database.config, 'schemas.sales.tables.customer.columns')
    assert view('id.ui_hint') == 'explicit'
    assert view('label.ui_hint') == 'mounted default'
    assert database.config.builder.source.get_item(
        'db.schemas.sales.tables.customer.columns.label?dtype') is None
    assert database.model.table('customer').columns['label'].dtype == 'I'
    database.close()


def test_repeated_render_does_not_copy_live_products_or_reuse_context():
    recipe = Recipe()
    recipe.create()
    first = recipe.render()
    second = recipe.render()
    third = build_database(recipe)
    assert first is not second and second is not third
    assert first.table('customer') is not second.table('customer')
    assert recipe.materialized['objects'] == [second]
    for database in (first, second, third):
        database.close()


def test_logical_relation_defaults_remain_nonphysical_and_alias_config_inherits():
    class LogicalRecipe(SqlDatabaseConfig):
        def main(self, root):
            tables = root.db('demo').schemas().schema('app').tables()
            target = tables.table('target', pkey='id').columns()
            target.column('id', dtype='I')
            target.column('label', dtype='A', size='30', name_long='Original')
            source = tables.table('source', pkey='id')
            columns = source.columns()
            columns.column('id', dtype='I')
            columns.column('target_id', dtype='I').relation('app.target.id', x_name='target')
            source.virtual_columns().aliasColumn(
                'label', relation_path='@target.label', name_long='Local')

    with build_database(LogicalRecipe) as db:
        alias = db.table('source').column('label')
        target = db.table('target').column('label')
        assert alias.originalColumn is target
        assert alias.relation_path == '@target.label'
        assert alias.config('dtype') == 'A'
        assert alias.config('size') == '30'
        assert alias.config('name_long') == 'Local'
        assert alias.config('missing', default=False) is False
        assert alias.config.scope('missing')('value', default=0) == 0
        assert alias.model.dtype == 'A'
        assert 'LEFT JOIN' in db.table('source').query(columns='$label').sqltext
