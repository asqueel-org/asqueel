"""74 native models against independent legacy structural captures."""
import json
from pathlib import Path

import pytest

from examples.test_invoice_pg import source

ROOT = Path(__file__).resolve().parents[2]
LEGACY = json.loads((ROOT / 'tests/oracles/test_invoice_pg/model.json').read_text())['children']
RELATIONS = json.loads((ROOT / 'docs/design/evidence/object-tree/legacy.json').read_text())
TABLES = [f'{p}.{t}' for p, pkg in LEGACY.items()
          for t in pkg['children']['tables']['children'] if (p, t) != ('sys', 'locked_record')]
# Those two legacy joinColumns were deliberately replaced by GEP declarations.
GEP_REPLACEMENTS = {'invc.invoice.@discount_tier_id', 'invc.discount_tier.@invoices_in_tier',
                    'invc.invoice_row.@customer_id', 'invc.customer.@invoice_rows_by_customer'}
# Approved alias inheritance adds weak edges; the original legacy oracle stays unchanged.
INHERITED_RELATIONS = {
    'invc.invoice.@customer_state': ('invc.invoice.customer_state', 'invc.state.code', 'O'),
    'invc.state.@invc_invoice_customer_state': ('invc.invoice.customer_state', 'invc.state.code', 'M'),
    'invc.invoice_row.@customer_id': ('invc.invoice_row.customer_id', 'invc.customer.id', 'O'),
    'invc.customer.@invc_invoice_row_customer_id': ('invc.invoice_row.customer_id', 'invc.customer.id', 'M'),
}


@pytest.fixture(scope='module')
def model():
    return source().render(mode='objects_tree')


@pytest.mark.parametrize('key', TABLES)
def test_native_table_hierarchy_and_fields_match_legacy(model, key):
    table = model.table(key)
    pkg, name = key.split('.')
    legacy = LEGACY[pkg]['children']['tables']['children'][name]
    sections = legacy['children']
    columns = sections['columns']['children']
    virtuals = sections.get('virtual_columns', {}).get('children', {})
    composites = {k for k, v in virtuals.items() if v['attributes'].get('composed_of')}
    deferred = ({'__protected_by_syscode', '__invalid_by_duplicate_sysrecord'}
                if key in {'adm.htag', 'adm.language', 'adm.xgroup'} else set())
    assert set(table.columns) == columns.keys()
    assert set(table.virtual_columns) == virtuals.keys() - composites - deferred
    assert set(table.composites) == composites
    assert table.pkg is model.package(pkg)
    assert table.parent is table.pkg.tables
    assert table.pkey == legacy['attributes']['pkey']
    for field in [*table.columns.values(), *table.virtual_columns.values()]:
        expected = (columns if field.name in columns else virtuals)[field.name]['attributes']
        assert field.parent.parent is table
        assert field.root is model.obj
        if field.tag != 'aliasColumn':
            assert field.dtype == expected['dtype']
            if 'size' in expected:
                assert field.attributes.get('size') == str(expected['size'])


def test_global_registry_matches_all_ordinary_legacy_relations(model):
    actual = {f'{p.label}.{t.label}.{r.label}': dict(r.attr)
              for p in model.relations for t in p.value for r in t.value}
    expected = {k: v for k, v in RELATIONS['relations'].items() if k not in GEP_REPLACEMENTS}
    assert set(actual) - set(expected) == set(INHERITED_RELATIONS)
    for path, (many, one, mode) in INHERITED_RELATIONS.items():
        joiner = actual.pop(path)
        assert (joiner['many_relation'], joiner['one_relation'], joiner['mode']) == (many, one, mode)
        assert joiner['virtual'] and joiner['private_relation']
        assert not joiner.get('foreignkey') and joiner.get('onDelete') is None
    assert len(actual) == 144
    assert actual == expected


@pytest.mark.parametrize('key', TABLES)
def test_relation_views_keep_legacy_fields_and_navigation(model, key):
    expected = [name for name in RELATIONS['view_keys'][key] if f'{key}.{name}' not in GEP_REPLACEMENTS]
    table = model.table(key)
    # Source authors may reorder declarations; fields precede their own link,
    # followed by virtual links and incoming relations, as in the legacy loop.
    actual = table.relations.keys()
    inherited = {path.rsplit('.', 1)[1] for path in INHERITED_RELATIONS if path.rsplit('.', 1)[0] == key}
    assert set(actual) == set(expected) | inherited
    for name in actual:
        if name.startswith('@'):
            node = table.relations.get_node(name)
            assert node.resolver._model is model
            assert node.attr['joiner'] == model.relations.get_node(f'{key}.{name}').attr
            joiner = node.attr['joiner']
            if joiner['mode'] == 'O':
                assert node.attr['dtype'] == model.column(joiner['many_relation']).dtype
            target = joiner['one_relation'] if joiner['mode'] == 'O' else joiner['many_relation']
            remote = model.table(target)
            field = next(iter(remote.columns))
            assert table.column(f'{name}.{field}') is remote.column(field)
        else:
            assert table.relations.get_node(name).attr['dtype'] == table.column(name).dtype


@pytest.mark.parametrize('table_name,column_name', [
    ('invc.customer', 'last_invoice_id'),
    ('invc.invoice', 'first_product_id'),
])
def test_virtual_relation_keeps_its_own_metadata_and_parentpath(model, table_name, column_name):
    table = model.table(table_name)
    column = table.virtual_columns[column_name]
    last_physical = list(table.columns.values())[-1]
    node = table.newRelationResolver(cacheTime=-1)().get_node(f'@{column_name}')

    # The legacy virtual loop reused the last physical column for both values.
    assert column.attributes['name_long'] != last_physical.attributes.get('name_long')
    assert node.attr['name_long'] == column.attributes['name_long']
    assert all(node.attr[key] == value for key, value in column.attributes.items())
    assert len(node.resolver.parentpath) == 1
    assert node.resolver.parentpath[0] is column

    joiner = node.attr['joiner']
    assert joiner['many_relation'] == column.fullname
    target = model.table(joiner['one_relation'])
    assert node.value.tbl_name == target.name
    assert node.value.pkg_name == target.pkg.name
    assert target.pkey in node.value


def test_declared_options_and_gep_relations_are_retained(model):
    assert len(model.tables) == 74
    assert sum(len(t.columns) for t in model.tables.values()) == 789
    assert sum(len(t.virtual_columns) for t in model.tables.values()) == 526
    declared = source()
    for path, node in declared.source.query('#p,#n', deep=True):
        if node.node_tag not in {'options', 'virtualRelation', 'subtable'}:
            continue
        obj = (model.obj[path.removeprefix('db.packages.')] if path.startswith('db.packages.')
               else model.db[path.removeprefix('db.')])
        assert obj is not None
        for name, value in node.attr.items():
            if name != '_meta':
                assert obj.attributes[name] == value
    invoice = model.table('invc.invoice')
    virtual = [child for child in invoice.values() if child.tag == 'virtualRelation']
    assert len(virtual) == 1
    assert 'var_total' in virtual[0].attributes
    assert invoice.relations.get_node('@discount_tier_id') is None
