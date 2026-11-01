"""Full physical comparison with the independent legacy oracle and native path."""
import builtins
import json
from pathlib import Path

import pytest

from asqueel import AsqueelDb, SqlDatabaseConfig
from asqueel_migration import SqlMigrator, StructureValidator
from examples.test_invoice_pg import source
from tests.object_tree.test_invoice import TABLES

ROOT = Path(__file__).resolve().parents[2]
LEGACY = json.loads((ROOT / 'tests/oracles/test_invoice_pg/physical.json').read_text())
del LEGACY['root']['schemas']['sys']['tables']['sys_locked_record']
SAVED = json.loads((ROOT / 'artifacts/test_invoice_pg/native/migration.json').read_text())


def physical(model):
    return model.db.config.builder.render(mode='migration')


def prepared(database, structure):
    migrator = SqlMigrator(database, removeDisabled=True)
    migrator.ormStructure = structure
    migrator.prepareMigrationCommands()
    assert not migrator.warnings, migrator.warnings
    return migrator


@pytest.fixture(scope='module')
def tree():
    return AsqueelDb(source()).model


@pytest.fixture(scope='module')
def structure(tree):
    return physical(tree)


@pytest.mark.parametrize('key', TABLES)
def test_every_table_matches_legacy_and_native_artifact(tree, structure, key):
    table = tree.table(key)
    actual = structure['root']['schemas'][table.sqlschema]['tables'][table.sqlname]
    assert actual == LEGACY['root']['schemas'][table.sqlschema]['tables'][table.sqlname]
    assert actual == SAVED['root']['schemas'][table.sqlschema]['tables'][table.sqlname]


def test_whole_json_is_identical_to_both_references_and_current_renderer(tree, structure):
    assert StructureValidator().validate(structure) == structure
    assert structure == LEGACY == SAVED
    old = AsqueelDb(source())
    try:
        assert structure == physical(old.model)
    finally:
        old.closeConnection()
    counts = {}
    for package, schema in structure['root']['schemas'].items():
        tables = list(schema['tables'].values())
        counts[package] = [len(tables)] + [sum(len(t[k]) for t in tables)
                                          for k in ('columns', 'relations', 'indexes')]
    assert counts == {'sys': [16, 188, 7, 56], 'adm': [40, 412, 32, 150], 'invc': [18, 189, 19, 76]}


def test_projection_uses_only_objects_and_does_not_mutate_them(monkeypatch):
    import asqueel.application as application
    from copy import deepcopy

    def forbidden(*args, **kwargs):
        pytest.fail('Projection must use completed objects without compiler or I/O')
    original_open, original_read = builtins.open, Path.read_text
    def guard(path):
        if isinstance(path, (str, Path)) and 'oracles/test_invoice_pg' in str(path):
            forbidden()
    def checked_open(path, *args, **kwargs):
        guard(path)
        return original_open(path, *args, **kwargs)
    def checked_read(path, *args, **kwargs):
        guard(path)
        return original_read(path, *args, **kwargs)
    monkeypatch.setattr(builtins, 'open', checked_open)
    monkeypatch.setattr(Path, 'read_text', checked_read)
    monkeypatch.setattr(application, 'QueryCompiler', forbidden)
    monkeypatch.setattr('psycopg.connect', forbidden)
    monkeypatch.setattr('sqlite3.connect', forbidden)
    recipe = source()
    before = recipe.source.to_json()
    db = AsqueelDb(recipe)
    model = db.model
    assert recipe.source.to_json() == before
    attrs = {key: deepcopy(t.attributes) for key, t in model.tables.items()}
    cols = {c.fullname: deepcopy(c.attributes) for t in model.tables.values() for c in t.columns.values()}
    joiners = model.relations.to_json()
    baseline = physical(model)
    assert baseline == SAVED
    assert attrs == {key: t.attributes for key, t in model.tables.items()}
    assert cols == {c.fullname: c.attributes for t in model.tables.values() for c in t.columns.values()}
    assert model.relations.to_json() == joiners
    # The tables come from the package folders: the recipe holds the packages only.
    recipe.source.get_node('db.packages.invc').attr['sqlschema'] = 'other'
    model.src = None
    assert physical(model) == baseline
    try:
        assert physical(db.model) == baseline
        db.config.builder.source.get_node('db.packages.invc.tables.customer.columns.account_name').attr['size'] = ':121'
        changed = physical(model)
        assert changed['root']['schemas']['invc']['tables']['invc_customer']['columns']['account_name']['attributes']['size'] == '0:121'
        assert baseline == SAVED
    finally:
        db.closeConnection()


def test_physical_names_composite_keys_constraints_and_extensions():
    recipe = SqlDatabaseConfig()
    root = recipe.source.db('mapped')
    root.extensions().extension('pg_trgm')
    packages = root.packages()
    packages.package('other', sqlschema='extra')
    pkg = packages.package('app', sqlschema='storage', sqlprefix='prefix')
    owner = pkg.table('owner', pkey='key', sqlname='owners')
    owner.column('a', dtype='L', sqlname='first')
    owner.column('b', dtype='L', sqlname='second')
    owner.compositeColumn('key', columns='a,b')
    item = pkg.table('item', pkey='id', sqlschema='extra')
    item.column('id', dtype='L')
    item.column('a', dtype='L', sqlname='first')
    item.column('b', dtype='L', sqlname='second')
    item.compositeColumn('ref', columns='a,b', unique=True).relation(
        'app.owner.key', foreign_key=True, deferred=True, onDelete_sql='cascade')
    item.index(name='descending', columns={'b': 'DESC'})
    model = AsqueelDb(recipe).model
    result = physical(model)
    assert result['root']['extensions']['pg_trgm']
    assert result['root']['schemas']['storage']['tables']['owners']['attributes']['pkeys'] == 'first,second'
    table = result['root']['schemas']['extra']['tables']['prefix_item']
    fk = next(iter(table['relations'].values()))['attributes']
    assert fk['related_schema'] == 'storage'
    assert fk['related_columns'] == ['first', 'second']
    assert fk['on_delete'] == 'CASCADE'
    assert fk['deferrable'] and fk['initially_deferred']
    old = AsqueelDb(recipe)
    try:
        assert result == physical(old.model)
    finally:
        old.closeConnection()


@pytest.mark.postgresql
def test_hierarchical_json_apply_introspect_rediff_and_evolution(pg_database, structure):
    first = prepared(pg_database, structure)
    assert first.getChanges()
    first.applyChanges()
    assert prepared(pg_database, structure).getChanges() == ''
    actual = pg_database.get_json_struct()['root']['schemas']
    assert sum(len(schema['tables']) for schema in actual.values()) == 74
    assert sum(len(t['columns']) for s in actual.values() for t in s['tables'].values()) == 789
    recipe = source()
    with recipe.contribution('hierarchical-migration-check'):
        customer = recipe.source.get_node('db.packages.invc').table('customer')
        customer.options().fullUpd()
        customer.column('probe_product', size='22').relation('invc.product.id', onDelete_sql='setnull')
        customer.column('probe_code', size=':20', unique=True)
        customer.index(name='probe_account', columns='account_name')
        customer.column('account_name', size=':120')
    evolved = physical(AsqueelDb(recipe).model)
    migration = prepared(pg_database, evolved)
    changes = migration.getChanges()
    assert all(name in changes for name in ('__full_mod_ts', 'probe_product', 'probe_code', 'probe_account'))
    migration.applyChanges()
    assert prepared(pg_database, evolved).getChanges() == ''
