"""All-package native acceptance; independent legacy fixtures are expectations only."""
import builtins
import json
from pathlib import Path

from genro_bag import Bag
import psycopg
import pytest

from asqueel import SqlDatabaseConfig, SqlMigrationRenderer
from asqueel.configuration import build_database
from asqueel.model_codec import model_from_json, model_to_json
from asqueel.projection import to_physical_builder
from asqueel_migration import StructureValidator
from examples.test_invoice_pg import source
from tests.test_release_invoice_migration import prepared

ROOT = Path(__file__).resolve().parents[1]
ORACLE = ROOT / 'tests/oracles/test_invoice_pg'
LEGACY = json.loads((ORACLE / 'model.json').read_text())['children']
TABLES = sorted(f'{p}.{t}' for p, pkg in LEGACY.items()
                for t in pkg['children']['tables']['children'] if (p, t) != ('sys', 'locked_record'))


def physical(model):
    return SqlMigrationRenderer(to_physical_builder(model)).render()


def expected_physical():
    result = json.loads((ORACLE / 'physical.json').read_text())
    del result['root']['schemas']['sys']['tables']['sys_locked_record']
    return result


@pytest.fixture(scope='module')
def native_db():
    with pytest.MonkeyPatch.context() as patch:
        patch.setenv('INVC_STATE', 'NSW')
        db = build_database(source())
    yield db
    db.close()


@pytest.mark.parametrize('key', TABLES)
def test_every_native_table_matches_legacy_structure_and_declarations(native_db, key):
    table = native_db.model.table(key)
    package, name = key.split('.')
    expected = LEGACY[package]['children']['tables']['children'][name]
    sections = expected['children']
    columns = sections['columns']['children']
    virtuals = sections.get('virtual_columns', {}).get('children', {})
    composites = {k for k, v in virtuals.items() if v['attributes'].get('composed_of')}
    deferred = ({'__protected_by_syscode', '__invalid_by_duplicate_sysrecord'}
                if key in {'adm.htag', 'adm.language', 'adm.xgroup'} else set())
    assert {c.name for c in table.columns.values() if not c.is_virtual} == columns.keys()
    assert {c.name for c in table.columns.values() if c.is_virtual} == virtuals.keys() - composites - deferred
    assert table.pkey == (expected['attributes']['pkey'],)
    for column_name, column in table.columns.items():
        attrs = (virtuals if column.is_virtual else columns)[column_name]['attributes']
        # The legacy snapshot contains raw alias dtype defaults. Native aliases
        # inherit their actual target; verify the resolved identity separately.
        if column.kind != 'aliasColumn':
            assert column.dtype == attrs['dtype'], (key, column_name, 'dtype')
        else:
            assert column.alias_target is not None
            target = native_db.model.table(column.alias_target[0]).columns[column.alias_target[1]]
            # Explicit dtype overrides (task_saved_query etc.) are preserved.
            declared = source_alias_attributes(key, column_name)
            assert column.dtype == (declared.get('dtype') or target.dtype)
        if 'size' in attrs and column.kind != 'aliasColumn':
            assert column.attributes.get('size') == str(attrs['size'])
    for item in composites:
        assert any(d.name == item for section in table.declarations if section.kind == 'composites'
                   for d in section.children)
    subtables = sections.get('subtables', {}).get('children', {})
    assert {d.name for d in table.declarations if d.kind == 'subtable'} == subtables.keys()


@pytest.fixture(scope='module')
def legacy_source():
    return Bag((ORACLE / 'source.xml').read_text())


def source_alias_attributes(key, name):
    # Raw explicit overrides, without defaults inserted by legacy DbColumnObj.
    package, table = key.split('.')
    return _LEGACY_SOURCE.get_node(f'packages.{package}.tables.{table}.virtual_columns.{name}').attr


_LEGACY_SOURCE = Bag((ORACLE / 'source.xml').read_text())


@pytest.mark.parametrize('key', TABLES)
def test_original_column_attributes_survive_native_translation(native_db, legacy_source, key):
    package, name = key.split('.')
    expected = legacy_source.get_node(f'packages.{package}.tables.{name}').value
    rename = {'readOnly': 'read_only', 'defaultFrom': 'default_from', 'py_method': 'method'}
    for field, column in native_db.model.table(key).columns.items():
        section = 'virtual_columns' if column.is_virtual else 'columns'
        attributes = dict(expected.get_node(f'{section}.{field}').attr)
        for key, value in attributes.items():
            if key in {'tag', 'dtype', 'size', 'virtual_column', 'composed_of', 'join_column',
                       'subquery', 'format', '_owner_package', 'virtual'}:
                continue
            if column.kind in ('subQueryColumn', 'bagItemColumn') and (
                    key in {'sql_formula', 'select'} or key.startswith(('var_', 'select_'))):
                continue  # These remain query/mode or bagcolumn/itempath, without SQL expansion.
            mapped = rename.get(key, key)
            if mapped in ('read_only', 'indexed', 'unique') and value == 'y':
                value = True
            if key.startswith('validate_'):
                actual = column.validations.get(key[9:])
            elif key == 'values':
                actual = column.validations.get('values')
            elif key in ('encrypted', 'subfields'):
                kind, attribute = ('encryption', 'mode') if key == 'encrypted' else ('dynamic_fields', 'source')
                actual = next(d.attributes[attribute] for d in column.declarations if d.kind == kind)
            elif key == 'batch_assign':
                actual = {'tags': column.attributes.get('batch_assign_tags')}
            else:
                actual = column.attributes.get(mapped, column.attributes.get('x_legacy_' + key))
            assert actual == value, (column.name, key)


def test_native_totals_options_relations_and_deferred_expressions(native_db):
    model = native_db.model
    assert {key: len(pkg.tables) for key, pkg in model.packages.items()} == {'sys': 16, 'adm': 40, 'invc': 18}
    assert sum(not c.is_virtual for t in model.tables.values() for c in t.columns.values()) == 789
    assert sum(c.is_virtual for t in model.tables.values() for c in t.columns.values()) == 526
    assert model.table('sys.task').relations['user_id'].target == 'adm.user'
    assert model.table('invc.invoice_row').relations['customer'].target == 'invc.customer'
    assert model.table('invc.invoice_row').columns['customer_id'].attributes['x_legacy_relation_relation_name'] == 'invoice_rows_by_customer'
    assert model.table('invc.invoice').relations['discount_tier_id'].target == 'invc.discount_tier'
    assert 'invoices_in_tier' not in model.table('invc.discount_tier').relations
    assert model.table('invc.customer').relations['last_invoice_id'].kind == 'weak'
    assert model.table('invc.price_year_note').columns['price_year_price'].alias_target == ('invc.price_year', 'unit_price')
    assert model.table('invc.invoice_row').columns['effective_price'].dtype == 'N'
    assert model.table('invc.product').columns['detail_price'].attributes['size'] == '14,2'
    assert model.table('adm.connection').columns['user_fullname'].attributes['static'] is True
    invoice = model.table('invc.invoice')
    assert invoice.columns['rows_json'].attributes['mode'] == 'json'
    assert invoice.columns['max_row_price'].attributes['query']['columns'] == 'MAX($unit_price)'
    assert invoice.options['numbering_inv_number'].attributes['parameters']['format'] == '$K$YY/$NNNNNN'
    assert invoice.options['partition_customer_state'].attributes['value'] == 'NSW'
    assert model.table('sys.error').options['retention'].attributes['days'] == 60
    assert model.table('adm.counter').options['tenant'].enabled
    assert model.table('invc.customer').columns['subtable_trade'].attributes['sql_formula'] == "$customer_type_code = 'TRD'"
    assert model_from_json(model_to_json(model)) == model


def test_native_json_matches_independent_oracle_and_saved_artifact(native_db):
    result = physical(native_db.model)
    assert StructureValidator().validate(result) == result
    assert result == expected_physical()
    assert result == json.loads((ROOT / 'artifacts/test_invoice_pg/native/migration.json').read_text())


def test_native_production_and_projection_do_not_read_oracles_or_reexpand(monkeypatch):
    import asqueel.configuration as configuration
    import asqueel.model_expansion as expansion
    import asqueel.legacy_source as bridge
    import asqueel.model as model_module
    original_open = builtins.open
    original_read = Path.read_text
    def guard(path):
        if isinstance(path, (str, Path)) and 'oracles/test_invoice_pg' in str(path):
            pytest.fail('Production must not read legacy snapshots')
    def checked_open(file, *args, **kwargs):
        guard(file)
        return original_open(file, *args, **kwargs)
    def checked_read(path, *args, **kwargs):
        guard(path)
        return original_read(path, *args, **kwargs)
    def forbidden(*args, **kwargs):
        pytest.fail('Projection must use only completed objects')
    monkeypatch.setattr(builtins, 'open', checked_open)
    monkeypatch.setattr(Path, 'read_text', checked_read)
    monkeypatch.setattr(bridge, 'from_expanded_legacy_xml', forbidden)
    monkeypatch.setattr(psycopg, 'connect', forbidden)
    monkeypatch.setattr(model_module, '_formula_definition', forbidden)
    config = source()
    before = config.source.to_json()
    db = build_database(config)
    try:
        assert config.source.to_json() == before
        baseline = physical(db.model)
        monkeypatch.setattr(expansion, 'expand_options', forbidden)
        monkeypatch.setattr(model_module, 'resolve_model', forbidden)
        monkeypatch.setattr(configuration, '_effective_model_builder', forbidden)
        config.source.get_node('db.packages.invc.tables.customer.columns.account_name').attr['size'] = ':999'
        assert physical(db.model) == baseline
        assert physical(model_from_json(model_to_json(db.model))) == baseline
    finally:
        db.close()


@pytest.mark.parametrize('target', ['missing.id', 'target.missing'])
def test_scalar_weak_relation_checks_target_without_parsing_its_formula(target):
    config = SqlDatabaseConfig()
    pkg = config.source.db('weak').packages().package('app')
    pkg.table('target', pkey='id').column('id', dtype='L')
    pkg.table('item').formulaColumn('calculated', sql_formula='arbitrary_legacy_sql(#PREF(x,1))').weak_relation(target)
    with pytest.raises(ValueError, match='relation target'):
        build_database(config)


@pytest.mark.postgresql
def test_native_invoice_apply_introspect_rediff_and_evolution(pg_database, native_db):
    desired = physical(native_db.model)
    first = prepared(pg_database, desired)
    assert first.getChanges()
    first.applyChanges()
    assert prepared(pg_database, desired).getChanges() == ''
    actual = pg_database.get_json_struct()['root']['schemas']
    assert sum(len(s['tables']) for s in actual.values()) == 74
    assert sum(len(t['columns']) for s in actual.values() for t in s['tables'].values()) == 789
    with psycopg.connect(**pg_database.connection_params(), autocommit=True) as conn:
        conn.execute('CREATE VIEW invc.native_unmanaged AS SELECT id FROM invc.invc_customer')
    updated = source()
    with updated.contribution('migration-check'):
        table = updated.source.get_node('db.packages.invc.tables.customer')
        table.options().full_update()
        table.column('probe_product', size='22').relation('invc.product.id', on_delete_sql='set_null')
        table.column('probe_code', size=':20', unique=True)
        table.index('probe_account', columns='account_name')
        table.column('account_name', size=':120')
    db = build_database(updated)
    try:
        evolved = physical(db.model)
    finally:
        db.close()
    plan = prepared(pg_database, evolved)
    changes = plan.getChanges()
    assert all(name in changes for name in ('__full_mod_ts', 'probe_product', 'probe_code', 'probe_account'))
    plan.applyChanges()
    assert not prepared(pg_database, evolved).getChanges()
    with psycopg.connect(**pg_database.connection_params(), autocommit=True) as conn:
        assert conn.execute("SELECT to_regclass('invc.native_unmanaged')").fetchone() == ('invc.native_unmanaged',)
    # Change a real option after the first object graph was built.
    assert '__full_mod_ts' not in native_db.table('invc.customer').columns
    assert '__full_mod_ts' in evolved['root']['schemas']['invc']['tables']['invc_customer']['columns']
