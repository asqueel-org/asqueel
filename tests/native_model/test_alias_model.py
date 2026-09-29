import pytest

from genro_sql import SqlBuilder, resolve_model
from genro_sql.contracts import Column, Table
from genro_sql.model import _unique_target


def recipe():
    builder = SqlBuilder()
    tables = builder.source.db('demo').schemas().schema('sales').tables()
    nation = tables.table('nation', pkey='id')
    nc = nation.columns()
    nc.column('id', dtype='I')
    nc.column('name', dtype='A', size=':40', name_long='Nation', notnull=True,
              x_identity='nation-name', x_sql_name='nation_name',
              x_ui={'label': 'Nation', 'width': 40})
    nation.virtual_columns().formulaColumn('label', sql_formula='upper($name)', dtype='A',
                                            x_ui={'format': 'uppercase'})
    customer = tables.table('customer', pkey='id')
    cc = customer.columns()
    cc.column('id', dtype='I')
    cc.column('nation_id', dtype='I').relation('sales.nation.id')
    aliases = customer.virtual_columns()
    aliases.aliasColumn('nation', relation_path='@nation_id.name', name_long=None, dtype=None,
                        x_identity='customer-nation', x_ui={'label': 'Customer nation'})
    aliases.aliasColumn('label', relation_path='@nation_id.label')
    aliases.aliasColumn('local', relation_path='$nation')
    invoice = tables.table('invoice', pkey='id')
    ic = invoice.columns()
    ic.column('id', dtype='I')
    ic.column('customer_id', dtype='I').relation('sales.customer.id')
    ia = invoice.virtual_columns()
    ia.aliasColumn('nation', relation_path='@customer_id.@nation_id.name')
    ia.aliasColumn('nation2', relation_path='@customer_id.nation_id.name')
    ia.aliasColumn('chain', relation_path='@customer_id.local')
    return builder, aliases


def test_alias_inherits_target_and_overrides_ui_without_copying_physical_identity():
    builder, _ = recipe()
    model = resolve_model(builder, ui={'nation-name': {'width': 50},
                                      'sales.customer.nation': {'widget': 'label'},
                                      'customer-nation': {'label': 'Final label'}})
    alias = model.table('customer').columns['nation']
    assert alias.dtype == 'A'
    assert alias.attributes['size'] == ':40'
    assert alias.attributes['name_long'] == 'Nation'
    assert alias.attributes['notnull'] is True  # Metadata, not a LEFT JOIN result guarantee.
    assert alias.ui == {'label': 'Final label', 'width': 50, 'widget': 'label'}
    assert alias.identity == 'customer-nation'
    assert alias.attributes['x_identity'] == 'customer-nation'
    assert alias.alias_target == ('sales.nation', 'name')
    assert alias.is_virtual and alias.formula is None
    assert alias.sql_name is None and alias.physical_name == 'nation'
    assert 'x_sql_name' not in alias.attributes
    assert alias.attributes['provenance']['path'].endswith('customer.virtual_columns.nation')


def test_multihop_alias_chains_and_formula_targets_keep_immediate_lineage():
    builder, _ = recipe()
    model = resolve_model(builder)
    invoice = model.table('invoice')
    assert invoice.columns['nation'].alias_target == ('sales.nation', 'name')
    assert invoice.columns['nation2'].alias_target == ('sales.nation', 'name')
    chain = invoice.columns['chain']
    assert chain.alias_target == ('sales.customer', 'local')
    assert chain.dtype == 'A' and chain.attributes['size'] == ':40'
    assert chain.identity == 'sales.invoice.chain'
    assert 'x_identity' not in chain.attributes
    formula_alias = model.table('customer').columns['label']
    assert formula_alias.alias_target == ('sales.nation', 'label')
    assert formula_alias.formula is None and formula_alias.is_virtual
    assert formula_alias.ui == {'format': 'uppercase'}


def test_alias_explicit_dtype_and_none_metadata_do_not_erase_target():
    builder, aliases = recipe()
    aliases.aliasColumn('numeric', relation_path='@nation_id.name', dtype='N', name_long='Numeric')
    alias = resolve_model(builder).table('customer').columns['numeric']
    assert alias.dtype == 'N' and alias.attributes['dtype'] == 'N'
    assert alias.attributes['name_long'] == 'Numeric'


@pytest.mark.parametrize('path,message', [('@missing.name', 'unknown alias relation'),
                                         ('@nation_id.missing', 'Unknown alias target'),
                                         ('@nation_id..name', 'invalid alias path'),
                                         ('', 'relation_path')])
def test_bad_alias_targets_fail_during_model_resolution(path, message):
    builder, aliases = recipe()
    with pytest.raises(ValueError, match=message):
        aliases.aliasColumn('bad', relation_path=path)
        resolve_model(builder)


def test_local_alias_cycle_is_reported_with_names():
    builder, aliases = recipe()
    aliases.aliasColumn('first', relation_path='second')
    aliases.aliasColumn('second', relation_path='$first')
    with pytest.raises(ValueError, match=r'Cyclic alias: .*first.*second.*first'):
        resolve_model(builder)


def test_alias_is_never_a_physical_unique_target_even_with_inherited_unique():
    alias = Column('alias', attributes={'unique': True}, relation_path='id')
    table = Table('t', columns={'alias': alias}, pkey=('alias',))
    assert not _unique_target(table, ('alias',))


def test_alias_is_excluded_from_physical_name_collision_check():
    builder, aliases = recipe()
    aliases.aliasColumn('physical_collision', relation_path='@nation_id.name', x_sql_name='id')
    alias = resolve_model(builder).table('customer').columns['physical_collision']
    assert alias.sql_name is None


def test_manual_alias_normalization_keeps_ui_and_rejects_ambiguous_kind():
    from genro_sql.model import _resolve_aliases
    table = Table('t', columns={
        'id': Column('id', dtype='I', ui={'label': 'Id', 'width': 10}),
        'alias': Column('alias', relation_path='id', ui={'label': 'Alias'}),
    })
    alias = _resolve_aliases({'public.t': table})['public.t'].columns['alias']
    assert alias.dtype == 'I'
    assert alias.ui == {'label': 'Alias', 'width': 10}
    assert alias.identity == 'public.t.alias'
    assert alias.attributes['provenance'] == {'kind': 'manual', 'path': 'public.t.alias'}
    ambiguous = Table('t', columns={
        'alias': Column('alias', formula='1', relation_path='id'),
    })
    with pytest.raises(ValueError, match='both alias and formula'):
        _resolve_aliases({'public.t': ambiguous})


def test_alias_physical_policies_are_rejected():
    builder, _ = recipe()
    table = builder.source.get_node('db.schemas.sales.tables.customer')
    table.attr['x_partition'] = {'field': 'nation', 'current': 'nation'}
    with pytest.raises(ValueError, match='physical column'):
        resolve_model(builder)
