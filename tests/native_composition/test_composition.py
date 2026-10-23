"""Consumer-backed composition probes: experimental grammars remain test-only."""
import pytest
from genro_builders.builder import element

from asqueel import AsqueelDb, SqlBuilder
from asqueel.catalog import SqlModelCatalog
from asqueel.elements import ColumnElements, SchemaElements, TableElements
from asqueel.validators import SqlModelValidationError


class TableGrammar(TableElements, ColumnElements):
    pass


class TableConfig:
    grammar = TableGrammar


class SchemaGrammar(SchemaElements):
    @element(parent_tags='tables', _meta={'subbuilder': 'x_config:grammar'})
    def table(self, name: str, pkey: str | None = None, x_config=None, **extra):
        ...


class SchemaConfig:
    grammar = SchemaGrammar


class MountedModel(SqlBuilder):
    @element(parent_tags='schemas', _meta={'subbuilder': 'x_config:grammar'})
    def schema(self, name: str, x_config=None, **extra):
        ...

    def main(self, root):
        schema = root.db('demo').schemas().schema(name='sales', x_config=SchemaConfig)
        table = schema.tables().table(name='customer', pkey='id', x_config=TableConfig)
        columns = table.columns()
        columns.column(name='id', dtype='I')
        columns.column(name='label', dtype='T')


def build(cls):
    model = cls()
    model.create()
    return model


def test_nested_mount_preserves_named_paths_and_real_consumers():
    model = build(MountedModel)
    node = model.source.get_node('db.schemas.sales.tables.customer.columns.id')
    assert node is not None
    assert node._get_meta('projects_column')
    catalog = SqlModelCatalog(model)
    assert set(catalog.physical_columns) == {('sales', 'customer', 'id'), ('sales', 'customer', 'label')}
    model.validate_model()
    rendered = model.render(mode='migration')
    assert rendered['root']['schemas']['sales']['tables']['customer']['attributes']['pkeys'] == 'id'
    assert AsqueelDb(model).model.table('sales.customer').columns['label'].dtype == 'T'


def test_dynamic_mount_class_configuration_is_not_emittable_python():
    # This is a characterized limitation, not a supported round-trip.
    source = build(MountedModel).render(mode='python')
    with pytest.raises(SyntaxError):
        compile(source, '<mounted-model>', 'exec')


# Standalone recipe functions represent independent package contributions.
# They use one stable grammar; composition is explicit application code.
def customer_recipe(tables):
    table = tables.table('customer', pkey='id')
    columns = table.columns()
    columns.column('id', dtype='I')
    columns.column('label', dtype='T', sqlname='display_name',
                   x_identity='customer-label')


def invoice_recipe(tables):
    table = tables.table('invoice', pkey='id', sqlname='documents')
    columns = table.columns()
    columns.column('id', dtype='I')
    columns.column('customer_id', dtype='I').relation('sales.customer.id')


class ModularModel(SqlBuilder):
    def main(self, root):
        schema = root.db('demo').schemas().schema('sales', sqlname='public')
        tables = schema.tables()
        customer_recipe(tables)
        invoice_recipe(tables)


def test_modular_recipes_emit_rebuild_and_keep_all_consumer_contracts():

    model = build(ModularModel)
    model.validate_model()
    source = model.render(mode='python', class_name='Rebuilt')
    namespace = {}
    exec(compile(source, '<modular-model>', 'exec'), namespace)
    rebuilt = build(namespace['Rebuilt'])
    rebuilt.validate_model()
    assert model.render(mode='migration') == rebuilt.render(mode='migration')
    for recipe in (model, rebuilt):
        catalog = SqlModelCatalog(recipe)
        assert set(catalog.tables) == {('sales', 'customer'), ('sales', 'invoice')}
        assert len(catalog.relations) == 1
        resolved = AsqueelDb(recipe).model
        customer = resolved.table('sales.customer')
        assert customer.sqlschema == 'public'
        assert customer.sqlname == 'customer'
        assert customer.columns['label'].sqlname == 'display_name'
        assert customer.columns['label'].attributes['x_identity'] == 'customer-label'
        assert resolved.table('sales.invoice').sqlname == 'documents'
        physical = resolved.db.config.builder
        physical.validate_model()
        rendered = physical.render(mode='migration')
        assert set(rendered['root']['schemas']['public']['tables']) == {'customer', 'documents'}
        assert 'display_name' in rendered['root']['schemas']['public']['tables']['customer']['columns']


def test_duplicate_recipe_contribution_fails_explicitly():
    class Duplicate(SqlBuilder):
        def main(self, root):
            tables = root.db('demo').schemas().schema('sales').tables()
            customer_recipe(tables)
            customer_recipe(tables)
    with pytest.raises(ValueError, match='duplicate'):
        build(Duplicate)


def test_validator_still_checks_cross_module_relations():
    class MissingDependency(SqlBuilder):
        def main(self, root):
            tables = root.db('demo').schemas().schema('sales').tables()
            invoice_recipe(tables)
    with pytest.raises(SqlModelValidationError):
        build(MissingDependency).validate_model()


def test_indirect_mounted_grammar_preserves_its_declared_attribute():
    class CustomTableGrammar(TableGrammar):
        @element(parent_tags='columns', _meta={'projects_column': True})
        def column(self, name: str, dtype: str, domain_hint: str = ''):
            ...

    class CustomTableConfig:
        grammar = CustomTableGrammar

    class CustomMountedModel(SqlBuilder):
        # genro_builders: a second-level subclass loses MountedModel's schema override.
        @element(parent_tags='schemas', _meta={'subbuilder': 'x_config:grammar'})
        def schema(self, name: str, x_config=None, **extra):
            ...

        def main(self, root):
            schema = root.db('demo').schemas().schema(name='sales', x_config=SchemaConfig)
            table = schema.tables().table(name='customer', pkey='id', x_config=CustomTableConfig)
            table.columns().column(name='id', dtype='I', domain_hint='local grammar field')

    model = build(CustomMountedModel)
    # An attribute declared by the mounted grammar survives resolution.
    model.validate_model()
    assert AsqueelDb(model).model.table('sales.customer').columns['id'].attributes['domain_hint'] == 'local grammar field'
