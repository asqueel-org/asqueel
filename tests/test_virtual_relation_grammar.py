"""GEP declarations survive translation without virtual inverse generation."""
import pytest

from asqueel import SqlDatabaseConfig, SqlMigrationRenderer
from asqueel.configuration import _copy_recipe, _owned_handler
from asqueel.model import resolve_model


def source():
    b = SqlDatabaseConfig()
    pkg = b.source.db('example', implementation='postgres').packages().package('app')
    customer = pkg.table('customer', pkey='id')
    customer.column('id', 'L')
    invoice = pkg.table('invoice', pkey='id')
    invoice.column('id', 'L')
    invoice.column('customer_id', 'L').relation('app.customer.id', relation_name='invoices')
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
        model = resolve_model(builder)
        attrs = model.table('app.customer')['virtualrelation_selected_invoices'].attributes
        assert attrs['condition'] == '$total>:var_min AND $year=:ask_year'
        assert attrs['var_min'] == '$id + 1'
        assert attrs['ask'] == {'title': 'Year', 'fields': [{'name': 'year', 'dtype': 'I'}]}
        assert not {'order_by', 'limit', 'one_one'} & attrs.keys()
        assert model.table('app.customer')['virtualrelation_nested'].attributes['relation'] == '@direct_invoices'
        # The ordinary inverse remains; no virtual relation appears on the target.
        assert model.table('app.customer').relations.get_node('@invoices').attr['joiner']['mode'] == 'M'
        assert not any(r.tag == 'virtualRelation' for r in model.table('app.invoice').values())
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
    with pytest.raises(ValueError, match=f"Element 'virtualRelation' does not accept '{key}'"):
        customer.virtualRelation('bad', relation='@invoices', **{key: value})
    node = customer.virtualRelation('imported', relation='@invoices')
    node.attr[key] = value
    with pytest.raises(ValueError, match=f"Element 'virtualRelation' does not accept '{key}'"):
        b.validate_source()
    with pytest.raises(ValueError, match=f"Element 'virtualRelation' does not accept '{key}'"):
        resolve_model(b)


@pytest.mark.parametrize('condition', [None, '', '   '])
def test_direct_table_requires_condition_in_complete_source(condition):
    b, customer, _ = source()
    customer.virtualRelation('direct', table='app.invoice', condition=condition)
    with pytest.raises(ValueError, match='table.*requires.*condition'):
        b.validate_source()
    with pytest.raises(ValueError, match='table.*requires.*condition'):
        resolve_model(b)


def test_direct_condition_can_be_supplied_by_a_contribution():
    b, customer, _ = source()
    customer.virtualRelation('direct', table='app.invoice')
    with b.contribution('application'):
        customer.virtualRelation('direct', condition='$customer_id=:var_customer', var_customer='$id')
    assert b.validate_source() == []
    attrs = resolve_model(b).table('app.customer')['virtualrelation_direct'].attributes
    assert attrs['table'] == 'app.invoice'
    assert attrs['condition'] == '$customer_id=:var_customer'


def test_imported_direct_condition_cannot_be_removed():
    b, customer, _ = source()
    node = customer.virtualRelation('direct', table='app.invoice', condition='$total>0')
    node.attr.pop('condition')
    with pytest.raises(ValueError, match='table.*requires.*condition'):
        resolve_model(b)
