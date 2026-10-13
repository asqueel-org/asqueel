"""GEP declarations survive translation without virtual inverse generation."""
import pytest

from asqueel import SqlDatabaseConfig, SqlMigrationRenderer
from asqueel.configuration import _copy_recipe, _owned_handler
from asqueel.model import resolve_model
from asqueel.model_codec import model_from_json, model_to_json


def source():
    b = SqlDatabaseConfig()
    pkg = b.source.db('example').packages().package('app')
    customer = pkg.table('customer', pkey='id')
    customer.column('id', 'L')
    invoice = pkg.table('invoice', pkey='id')
    invoice.column('id', 'L')
    invoice.column('customer_id', 'L').relation('app.customer.id', inverse='invoices')
    invoice.column('year', 'L')
    invoice.column('total', 'N')
    return b, customer, invoice


def test_gep_bindings_and_filtered_relations_are_preserved():
    b, customer, invoice = source()
    customer.virtualRelation('selected_invoices', relation='@invoices',
        condition='$total>:var_min AND $year=:ask_year', var_min='$id',
        ask={'title': 'Year', 'fields': [{'name': 'year', 'dtype': 'I'}]})
    with b.contribution('application'):
        customer.virtualRelation('selected_invoices', var_min='$id + 1')
    customer.virtualRelation('direct_invoices', table='app.invoice',
        condition='$customer_id=:var_customer', var_customer='$id')
    customer.virtualRelation('nested', relation='@direct_invoices',
        condition='$total>0')
    for builder in (b, _copy_recipe(b), _owned_handler(b).builder):
        assert builder.validate_source() == []
        model = model_from_json(model_to_json(resolve_model(builder)))
        attrs = model.table('app.customer').relations['selected_invoices'].attributes
        assert attrs['condition'] == '$total>:var_min AND $year=:ask_year'
        assert attrs['var_min'] == '$id + 1'
        assert attrs['ask'] == {'title': 'Year', 'fields': [{'name': 'year', 'dtype': 'I'}]}
        assert not {'order_by', 'limit', 'one_one'} & attrs.keys()
        assert model.table('app.customer').relations['nested'].target == 'app.invoice'
        # The ordinary inverse remains; no virtual relation appears on the target.
        assert model.table('app.customer').relations['invoices'].kind == 'inverse'
        assert not any(r.kind == 'virtual' for r in model.table('app.invoice').relations.values())
    physical = SqlMigrationRenderer(b).render()['root']['schemas']['public']['tables']
    assert not physical['app_customer']['relations']
    assert len(physical['app_invoice']['relations']) == 1


@pytest.mark.parametrize('key,value', [
    ('inverse', 'back'), ('source_parameters', {'a': '$id'}),
    ('parameters', {'a': 1}), ('reverse_name', 'back'),
    ('var_', '$id'), ('unapproved', True),
    ('limit', 1), ('limit', None), ('order_by', '$id DESC'), ('order_by', None),
    ('one_one', True), ('one_one', False),
])
def test_retired_or_unknown_virtual_relation_arguments_are_rejected(key, value):
    b, customer, _ = source()
    with pytest.raises(ValueError, match='unsupported attributes'):
        customer.virtualRelation('bad', relation='@invoices', **{key: value})
    node = customer.virtualRelation('imported', relation='@invoices')
    node.attr[key] = value
    with pytest.raises(ValueError, match='unsupported attributes'):
        b.validate_source()
    with pytest.raises(ValueError, match='unsupported attributes'):
        resolve_model(b)
