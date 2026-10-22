from genro_builders.builder import element
import pytest

from asqueel.configuration import SqlDatabaseConfig, build_database
from asqueel.elements import ColumnElements, SchemaElements, TableElements


class Recipe(SqlDatabaseConfig):
    def main(self, root):
        table = root.db('demo').schemas().schema('sales').tables().table('customer', pkey='id')
        table.columns().column('id', dtype='I')


class Overlay(SqlDatabaseConfig):
    def main(self, root):
        root.db('demo', implementation='postgres', conninfo='dbname=overlay')


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
    assert first.model.table('sales.customer').pkey == 'id'
    assert first.model is not second.model
    assert first.table('sales.customer') is not second.table('sales.customer')
    first.closeConnection()
    second.closeConnection()


def test_direct_object_render_uses_defaults_without_connecting(monkeypatch):
    import psycopg
    def forbidden(*args, **kwargs):
        raise AssertionError('object materialization must not connect')
    monkeypatch.setattr(psycopg, 'connect', forbidden)
    recipe = Recipe()
    recipe.create()
    database = recipe.render()
    assert database.config('implementation') == 'sqlite'
    assert database.config('conninfo') == ''
    assert database.table('sales.customer').model is database.model.table('sales.customer')
    with pytest.raises(TypeError, match='object'):
        recipe.render(target=False)
    database.closeConnection()


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
    assert database.config('schemas.sales.tables.customer.columns.id.ui_hint') == 'explicit'
    assert database.config('schemas.sales.tables.customer.columns.label.ui_hint') == 'mounted default'
    assert database.config.builder.source.get_item(
        'db.schemas.sales.tables.customer.columns.label?dtype') is None
    assert database.model.table('sales.customer').columns['label'].dtype == 'I'
    database.closeConnection()


def test_repeated_render_does_not_copy_live_products_or_reuse_context():
    recipe = Recipe()
    recipe.create()
    first = recipe.render()
    second = recipe.render()
    third = build_database(recipe)
    assert first is not second and second is not third
    assert first.table('sales.customer') is not second.table('sales.customer')
    assert recipe.materialized['objects'][0].tag == 'db'
    for database in (first, second, third):
        database.closeConnection()


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
                'label', relation_path='@target_id.label', name_long='Local')

    db = build_database(LogicalRecipe)
    try:
        alias = db.table('app.source').column('label')
        target = db.table('app.target').column('label')
        assert alias.originalColumn is target
        assert alias.relation_path == '@target_id.label'
        assert alias.attributes['dtype'] == 'A'
        assert alias.attributes['size'] == '30'
        assert alias.attributes['name_long'] == 'Local'
        assert alias.attributes.get('missing', False) is False
        assert alias.dtype == 'A'
        assert 'LEFT JOIN' in db.table('app.source').query(columns='$label').sqltext
    finally:
        db.closeConnection()


@pytest.mark.parametrize(('root_impl', 'connection_impl', 'expected'), [
    ('sqlite', None, 'sqlite'),
    ('postgres', None, 'postgres'),
    ('postgres', 'sqlite', 'sqlite'),
    ('sqlite', 'postgres', 'postgres'),
])
def test_connection_implementation_inherits_root_unless_explicit(root_impl, connection_impl, expected):
    from asqueel.configuration import connection_settings

    class Config(SqlDatabaseConfig):
        def main(self, root):
            db = root.db('demo', implementation=root_impl)
            options = {} if connection_impl is None else {'implementation': connection_impl}
            db.connection(name='app.db', **options)
            db.schemas().schema('s').tables().table('t', pkey='id').columns().column('id', dtype='I')

    db = build_database(Config)
    try:
        implementation, conninfo, options = connection_settings(db.config)
        assert implementation == db.adapter.dialect == expected
        assert conninfo == ''
        assert options == {'dbname': 'app.db'}
    finally:
        db.closeConnection()
