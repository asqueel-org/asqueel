"""Consumer-backed composition probes: experimental grammars remain test-only."""
import pytest

from asqueel import AsqueelDb, SqlBuilder
from asqueel.catalog import SqlModelCatalog
from asqueel.validators import SqlModelValidationError


def build(cls):
    model = cls()
    model.create()
    return model


# Standalone recipe functions represent independent package contributions.
# They use one stable grammar; composition is explicit application code.
def customer_recipe(tables):
    table = tables.table('customer', pkey='id')
    columns = table.columns()
    columns.column('id', dtype='I')
    columns.column('label', dtype='T', sqlname='display_name')


def invoice_recipe(tables):
    table = tables.table('invoice', pkey='id', sqlname='documents')
    columns = table.columns()
    columns.column('id', dtype='I')
    columns.column('customer_id', dtype='I').relation('sales.customer.id')


class ModularModel(SqlBuilder):
    def main(self, root):
        schema = root.db('demo').packages().package('sales', sqlschema='public', sqlprefix=False)
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
        assert customer.columns['label'].fullname == 'sales.customer.label'
        assert resolved.table('sales.invoice').sqlname == 'documents'
        physical = resolved.db.config.builder
        physical.validate_model()
        rendered = physical.render(mode='migration')
        assert set(rendered['root']['schemas']['public']['tables']) == {'customer', 'documents'}
        assert 'display_name' in rendered['root']['schemas']['public']['tables']['customer']['columns']


def test_validator_still_checks_cross_module_relations():
    class MissingDependency(SqlBuilder):
        def main(self, root):
            tables = root.db('demo').packages().package('sales', sqlschema='sales', sqlprefix=False).tables()
            invoice_recipe(tables)
    with pytest.raises(SqlModelValidationError):
        build(MissingDependency).validate_model()
