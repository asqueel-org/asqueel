"""Independent all-package acceptance tests for the migration milestone."""
import json
from pathlib import Path

import pytest
import psycopg
from asqueel import SqlMigrationRenderer, SqlModelReader, SqlPythonEmitter
from asqueel.legacy_source import from_expanded_legacy_xml
from asqueel.model import resolve_model
from asqueel.model_codec import model_from_json, model_to_json
from asqueel_migration import SqlMigrator, StructureValidator

SOURCE = Path(__file__).parent / 'oracles/test_invoice_pg'


def invoice_source():
    return from_expanded_legacy_xml((SOURCE / 'source.xml').read_text(),
                                   **json.loads((SOURCE / 'adapter-profile.json').read_text()))


def test_all_packages_match_the_independent_legacy_physical_oracle():
    builder = invoice_source()
    result = SqlMigrationRenderer(builder).render()
    assert result == json.loads((SOURCE / 'physical.json').read_text())
    artifact = Path(__file__).parents[1] / 'artifacts/test_invoice_pg/migration.json'
    assert result == json.loads(artifact.read_text())
    assert StructureValidator().validate(result) == result
    model = resolve_model(builder)
    assert {key: len(pkg.tables) for key, pkg in model.packages.items()} == {'sys': 17, 'adm': 40, 'invc': 18}
    assert sum(not col.is_virtual for table in model.tables.values() for col in table.columns.values()) == 796
    assert sum(col.is_virtual for table in model.tables.values() for col in table.columns.values()) == 532
    composites = [d for table in model.tables.values() for section in table.declarations
                  if section.kind == 'composites' for d in section.children]
    assert len(composites) == 2  # 534 legacy virtual declarations, including two composites.
    assert sum(len(t['relations']) for s in result['root']['schemas'].values() for t in s['tables'].values()) == 58
    assert model_from_json(model_to_json(model)) == model
    # A modified input must change the output: this is a producer, not an oracle replay.
    builder.source['db.packages.invc.tables.customer.columns.account_name'].attr['size'] = '0:120'
    changed = SqlMigrationRenderer(builder).render()
    assert changed != result
    assert changed['root']['schemas']['invc']['tables']['invc_customer']['columns']['account_name']['attributes']['size'] == '0:120'


def prepared(database, structure):
    migrator = SqlMigrator(database, removeDisabled=True)
    migrator.ormStructure = structure
    migrator.prepareMigrationCommands()
    assert not migrator.warnings, migrator.warnings
    return migrator


@pytest.mark.postgresql
def test_complete_invoice_apply_introspect_rediff_and_controlled_changes(pg_database):
    desired = SqlMigrationRenderer(invoice_source()).render()
    first = prepared(pg_database, desired)
    assert first.getChanges()
    first.applyChanges()
    second = prepared(pg_database, desired)
    assert second.getChanges() == '', second.getChanges()
    actual = pg_database.get_json_struct()
    assert sum(len(schema['tables']) for schema in actual['root']['schemas'].values()) == 75
    assert sum(len(table['columns']) for schema in actual['root']['schemas'].values()
               for table in schema['tables'].values()) == 796
    # Introspection -> builder -> emitter -> execution -> normalized JSON.
    reader = SqlModelReader(actual).to_builder()
    code = SqlPythonEmitter(reader).emit()
    namespace = {}
    exec(compile(code, '<invoice-physical-roundtrip>', 'exec'), namespace)
    rebuilt = namespace['build_model']() if 'build_model' in namespace else None
    if rebuilt is None:
        from asqueel import SqlBuilder
        classes = [cls for cls in namespace.values() if isinstance(cls, type)
                   and issubclass(cls, SqlBuilder) and cls is not SqlBuilder]
        assert len(classes) == 1
        rebuilt = classes[0]()
        rebuilt.create()
    assert not prepared(pg_database, SqlMigrationRenderer(rebuilt).render()).getChanges()
    with psycopg.connect(**pg_database.connection_params(), autocommit=True) as connection:
        connection.execute('CREATE VIEW invc.unmanaged_view AS SELECT id FROM invc.invc_customer')
        connection.execute("CREATE FUNCTION invc.unmanaged_trigger() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN RETURN NEW; END $$")
        connection.execute('CREATE TRIGGER unmanaged_trigger BEFORE INSERT ON invc.invc_customer FOR EACH ROW EXECUTE FUNCTION invc.unmanaged_trigger()')
    # Alter real source across column, UNIQUE, FK, and index boundaries.
    builder = invoice_source()
    with builder.contribution('migration-evolution'):
        customer = builder.source['db.packages.invc.tables.customer']
        customer.column('migration_probe', dtype='T', unique=True)
        customer.index('probe_lower', columns='account_name')
        customer.column('migration_product_id').relation('invc.product.id', on_delete_sql='set_null')
        builder.source['db.packages.invc.tables.customer.columns.account_name'].attr['size'] = '0:120'
    evolved = SqlMigrationRenderer(builder).render()
    plan = prepared(pg_database, evolved)
    changes = plan.getChanges()
    assert 'migration_probe' in changes and 'migration_product_id' in changes and 'probe_lower' in changes
    plan.applyChanges()
    assert not prepared(pg_database, evolved).getChanges()

    with psycopg.connect(**pg_database.connection_params(), autocommit=True) as connection:
        assert connection.execute("SELECT to_regclass('invc.unmanaged_view'), to_regprocedure('invc.unmanaged_trigger()')").fetchone() == ('invc.unmanaged_view', 'invc.unmanaged_trigger()')
        assert connection.execute("SELECT count(*) FROM pg_trigger WHERE tgname='unmanaged_trigger'").fetchone() == (1,)
