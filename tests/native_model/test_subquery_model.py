from dataclasses import replace

import pytest

from genro_sql import SqlBuilder, resolve_model
from genro_sql.contracts import UnsupportedFeatureError
from genro_sql.validators import SqlModelValidationError


def declaration(**attributes):
    builder = SqlBuilder()
    tables = builder.source.db('demo').schemas().schema('sales').tables()
    table = tables.table('customer', pkey='id')
    table.columns().column('id', dtype='I')
    virtuals = table.virtual_columns()
    virtuals.formulaColumn('value', **attributes)
    return builder, virtuals


def spec(**options):
    return dict(table='sales.invoice', where='$customer_id=#THIS.id', **options)


@pytest.mark.parametrize('kind', ['select', 'exists'])
def test_structured_formula_is_snapshotted_and_virtual(kind):
    definition = spec(columns='count(*)', params={'states': ['new']})
    builder, _ = declaration(**{kind: definition})
    column = resolve_model(builder).table('customer').columns['value']
    assert column.is_virtual and column.formula is None
    assert getattr(column, kind)['table'] == 'sales.invoice'
    definition['table'] = 'changed'
    definition['params']['states'].append('changed')
    assert getattr(column, kind)['params'] == {'states': ['new']}
    assert column.attributes[kind]['params'] == {'states': ['new']}
    with pytest.raises(TypeError):
        getattr(column, kind)['table'] = 'changed'
    assert getattr(replace(column, name='copy'), kind)['params'] == {'states': ['new']}


def test_named_subqueries_and_alias_lineage_do_not_copy_operational_definition():
    builder, virtuals = declaration(sql_formula='COALESCE(#total, 0)',
                                   select_total=spec(columns='sum($amount)'), dtype='N')
    virtuals.aliasColumn('alias', relation_path='value')
    model = resolve_model(builder)
    column = model.table('customer').columns['value']
    assert column.subqueries['total']['columns'] == 'sum($amount)'
    with pytest.raises(TypeError):
        column.subqueries['total']['columns'] = 'other'
    assert replace(column).subqueries['total']['table'] == 'sales.invoice'
    alias = model.table('customer').columns['alias']
    assert alias.alias_target == ('sales.customer', 'value')
    assert alias.dtype == 'N'
    assert alias.select is alias.exists is None and not alias.subqueries
    assert 'select_total' not in alias.attributes


@pytest.mark.parametrize('attributes, error, message', [
    ({'select': 'callback_name'}, UnsupportedFeatureError, 'callbacks'),
    ({'sql_formula': True}, UnsupportedFeatureError, 'callbacks'),
    ({'select': {}}, ValueError, 'nonempty table'),
    ({'select': {'table': 'sales.invoice'}}, ValueError, 'nonempty where'),
    ({'select': spec(), 'exists': spec()}, ValueError, 'exactly one'),
    ({'sql_formula': '1', 'select': spec()}, ValueError, 'exactly one'),
    ({'select': spec(), 'select_extra': spec()}, ValueError, 'require sql_formula'),
    ({'sql_formula': '1', 'select_extra': spec()}, ValueError, 'unused named subquery'),
    ({'sql_formula': '#extra', 'select_extra': 'callback'}, UnsupportedFeatureError, 'callbacks'),
])
def test_invalid_formula_contract_fails_early(attributes, error, message):
    builder, _ = declaration(**attributes)
    with pytest.raises(error, match=message):
        resolve_model(builder)


def test_select_prefix_exception_is_only_for_formula_columns_and_valid_names():
    builder, _ = declaration(sql_formula='1', selectoops={})
    with pytest.raises(SqlModelValidationError, match='selectoops'):
        builder.validate_model()
    builder, _ = declaration(sql_formula='1')
    builder.source.get_node('db.schemas.sales.tables.customer.columns.id').attr['select_other'] = spec()
    with pytest.raises(SqlModelValidationError, match='select_other'):
        builder.validate_model()
