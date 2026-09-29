import pytest

from genro_sql import SqlBuilder
from genro_sql.contracts import UnsupportedFeatureError
from genro_sql.model import resolve_model
from genro_sql.importers import inspect_postgres


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
    from genro_sql.projection import to_physical_builder
    from genro_sql.catalog import SqlModelCatalog
    model = resolve_model(example())
    physical = SqlModelCatalog(to_physical_builder(model))
    assert set(physical.tables) == {('public', 'sales_customer'), ('public', 'invoices')}
    assert 'double' not in physical.tables[('public', 'invoices')]['columns']
