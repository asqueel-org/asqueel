import pytest

from asqueel import SqlBuilder
from asqueel.contracts import UnsupportedFeatureError
from asqueel.model import resolve_model
from asqueel.importers import inspect_postgres


class Example(SqlBuilder):
    def main(self, root):
        schema = root.db('demo').schemas().schema('sales', x_sql_schema='public', x_sql_prefix=True)
        tables = schema.tables()
        customer = tables.table('customer', pkey='id')
        columns = customer.columns()
        columns.column('id', dtype='I')
        columns.column('label', dtype='T', x_identity='customer-label', x_ui={'label': 'Inline'})
        invoice = tables.table('invoice', pkey='id', x_sql_name='invoices')
        columns = invoice.columns()
        columns.column('id', dtype='I')
        columns.column('customer_id', dtype='I').relation('sales.customer.id')
        columns.column('total', dtype='N')
        invoice.virtual_columns().formulaColumn('double', sql_formula='$total * 2', dtype='N')


def example():
    model = Example()
    model.create()
    return model


def test_resolution_keeps_ui_mapping_formulas_and_provenance():
    model = resolve_model(example(), ui={'sales.customer.label': {'label': 'Path'},
                                        'customer-label': {'label': 'Identity'}})
    customer = model.table('customer')
    assert (customer.physical_schema, customer.physical_name) == ('public', 'sales_customer')
    assert customer.columns['label'].ui['label'] == 'Identity'
    assert customer.columns['label'].attributes['provenance']['kind'] == 'builder'
    invoice = model.table('invoice')
    assert invoice.physical_name == 'invoices'
    assert invoice.relations['customer_id'].target == 'sales.customer'
    assert invoice.columns['double'].formula == '$total * 2'


def test_ui_cannot_override_dtype():
    with pytest.raises(ValueError, match='semantics'):
        resolve_model(example(), ui={'customer-label': {'dtype': 'I'}})


def test_unsupported_virtual_fails_loudly():
    class Bad(SqlBuilder):
        def main(self, root):
            table = root.db('demo').schemas().schema('s').tables().table('t')
            table.columns().column('id', dtype='I')
            table.virtual_columns().pyColumn('calculated', py_method='calculate')
    model = Bad()
    model.create()
    with pytest.raises(UnsupportedFeatureError):
        resolve_model(model)


def test_import_requires_explicit_schema_sequence():
    with pytest.raises(ValueError):
        inspect_postgres(None, [])
    with pytest.raises(TypeError):
        inspect_postgres(None, 'public')


def test_duplicate_physical_mapping_is_rejected():
    class Collision(SqlBuilder):
        def main(self, root):
            tables = root.db('demo').schemas().schema('s').tables()
            tables.table('a', x_sql_name='same').columns().column('id', dtype='I')
            tables.table('b', x_sql_name='same').columns().column('id', dtype='I')
    model = Collision()
    model.create()
    with pytest.raises(ValueError, match='Duplicate physical table'):
        resolve_model(model)


def test_nonunique_relation_cannot_silently_explode_rows():
    class Nonunique(SqlBuilder):
        def main(self, root):
            tables = root.db('demo').schemas().schema('s').tables()
            tables.table('a').columns().column('code', dtype='I')
            tables.table('b').columns().column('ref', dtype='I').relation('s.a.code')
    model = Nonunique()
    model.create()
    with pytest.raises(UnsupportedFeatureError, match='unique key'):
        resolve_model(model)


def test_physical_projection_uses_resolved_naming():
    from asqueel.projection import to_physical_builder
    from asqueel.catalog import SqlModelCatalog
    model = resolve_model(example())
    physical = SqlModelCatalog(to_physical_builder(model))
    assert set(physical.tables) == {('public', 'sales_customer'), ('public', 'invoices')}
    assert 'double' not in physical.tables[('public', 'invoices')]['columns']


@pytest.mark.parametrize('alias', [None, 'parent'])
@pytest.mark.parametrize('foreign_key', [True, False])
def test_composite_relation_survives_physical_migration_projection(alias, foreign_key):
    from asqueel import SqlMigrationRenderer, to_physical_builder

    builder = SqlBuilder()
    tables = builder.source.db('demo').schemas().schema('s', x_sql_schema='physical').tables()
    parent = tables.table('parent', pkey='x,y', x_sql_name='parents')
    columns = parent.columns()
    columns.column('x', dtype='I', x_sql_name='px')
    columns.column('y', dtype='I', x_sql_name='py')
    child = tables.table('child', pkey='id')
    columns = child.columns()
    columns.column('id', dtype='I')
    columns.column('ax', dtype='I', x_sql_name='cx')
    columns.column('ay', dtype='I', x_sql_name='cy')
    kwargs = {'foreign_key': foreign_key}
    if foreign_key:
        kwargs['on_delete'] = 'CASCADE'
    if alias:
        kwargs['x_name'] = alias
    child.composites().compositeColumn('pair', columns='ax,ay').relation('s.parent', **kwargs)
    model = resolve_model(builder)
    assert model.table('s.child').relations[alias or 'pair'].columns == ('ax', 'ay')
    physical = to_physical_builder(model)
    projected = resolve_model(physical).table('physical.child')
    assert len(projected.relations) == int(foreign_key)
    if foreign_key:
        relation = next(iter(projected.relations.values()))
        assert relation.columns == ('cx', 'cy')
        assert relation.target_columns == ('px', 'py')
        assert relation.target == 'physical.parents'
    structure = SqlMigrationRenderer(physical).render()
    relations = structure['root']['schemas']['physical']['tables']['child']['relations']
    assert bool(relations) is foreign_key
