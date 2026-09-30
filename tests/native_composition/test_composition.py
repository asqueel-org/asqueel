"""Consumer-backed composition probes: experimental grammars remain test-only."""
import pytest
from genro_builders.builder import element

from asqueel import SqlBuilder, SqlMigrationRenderer, SqlPythonEmitter
from asqueel.catalog import SqlModelCatalog
from asqueel.elements import ColumnElements, SchemaElements, TableElements
from asqueel.model import resolve_model
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
        columns.column(name='label', dtype='T', x_ui={'label': 'Customer'})


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
    rendered = SqlMigrationRenderer(model).render()
    assert rendered['root']['schemas']['sales']['tables']['customer']['attributes']['pkeys'] == 'id'
    assert resolve_model(model).table('customer').columns['label'].ui == {'label': 'Customer'}


def test_dynamic_mount_class_configuration_is_not_emittable_python():
    # This is a characterized limitation, not a supported round-trip.
    source = SqlPythonEmitter(build(MountedModel)).emit()
    with pytest.raises(SyntaxError):
        compile(source, '<mounted-model>', 'exec')


# Standalone recipe functions represent independent package contributions.
# They use one stable grammar; composition is explicit application code.
def customer_recipe(tables):
    table = tables.table('customer', pkey='id')
    columns = table.columns()
    columns.column('id', dtype='I')
    columns.column('label', dtype='T', x_sql_name='display_name',
                   x_identity='customer-label', x_ui={'label': 'Customer', 'format': 'text'})


def invoice_recipe(tables):
    table = tables.table('invoice', pkey='id', x_sql_name='documents')
    columns = table.columns()
    columns.column('id', dtype='I')
    columns.column('customer_id', dtype='I').relation('sales.customer.id')


class ModularModel(SqlBuilder):
    def main(self, root):
        schema = root.db('demo').schemas().schema('sales', x_sql_schema='public', x_sql_prefix=True)
        tables = schema.tables()
        customer_recipe(tables)
        invoice_recipe(tables)


def test_modular_recipes_emit_rebuild_and_keep_all_consumer_contracts():
    from asqueel.projection import to_physical_builder

    model = build(ModularModel)
    model.validate_model()
    source = SqlPythonEmitter(model).emit(class_name='Rebuilt')
    namespace = {}
    exec(compile(source, '<modular-model>', 'exec'), namespace)
    rebuilt = build(namespace['Rebuilt'])
    rebuilt.validate_model()
    assert SqlMigrationRenderer(model).render() == SqlMigrationRenderer(rebuilt).render()
    overlay = {'customer-label': {'label': 'Customer override'}}
    for recipe in (model, rebuilt):
        catalog = SqlModelCatalog(recipe)
        assert set(catalog.tables) == {('sales', 'customer'), ('sales', 'invoice')}
        assert len(catalog.relations) == 1
        resolved = resolve_model(recipe, ui=overlay)
        customer = resolved.table('customer')
        assert customer.physical_schema == 'public'
        assert customer.physical_name == 'sales_customer'
        assert customer.columns['label'].physical_name == 'display_name'
        assert customer.columns['label'].ui == {'label': 'Customer override', 'format': 'text'}
        assert resolved.table('invoice').physical_name == 'documents'
        physical = to_physical_builder(resolved)
        physical.validate_model()
        rendered = SqlMigrationRenderer(physical).render()
        assert set(rendered['root']['schemas']['public']['tables']) == {'sales_customer', 'documents'}
        assert 'display_name' in rendered['root']['schemas']['public']['tables']['sales_customer']['columns']


def test_ui_overlay_does_not_change_physical_projection():
    from asqueel.projection import to_physical_builder

    model = build(ModularModel)
    base = resolve_model(model)
    changed = resolve_model(model, ui={'customer-label': {'label': 'Translated', 'widget': 'textbox'}})
    assert SqlMigrationRenderer(to_physical_builder(base)).render() == SqlMigrationRenderer(to_physical_builder(changed)).render()


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


def test_indirect_mounted_grammar_override_is_not_resolved_by_builders():
    class CustomTableGrammar(TableGrammar):
        @element(parent_tags='columns', _meta={'projects_column': True})
        def column(self, name: str, dtype: str, domain_hint: str = ''):
            ...

    class CustomTableConfig:
        grammar = CustomTableGrammar

    class CustomMountedModel(MountedModel):
        def main(self, root):
            schema = root.db('demo').schemas().schema(name='sales', x_config=SchemaConfig)
            table = schema.tables().table(name='customer', pkey='id', x_config=CustomTableConfig)
            table.columns().column(name='id', dtype='I', domain_hint='local grammar field')

    model = build(CustomMountedModel)
    # The mounted subclass's indirect grammar override is not retained by
    # Builders 0.27 node ownership; the node resolves the base column signature.
    with pytest.raises(SqlModelValidationError, match="unknown attribute 'domain_hint'"):
        model.validate_model()
