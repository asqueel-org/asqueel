"""Independent all-package acceptance tests for the migration milestone."""
import json
from pathlib import Path

from asqueel.legacy_source import from_expanded_legacy_xml
from asqueel_migration import SqlMigrator

SOURCE = Path(__file__).parent / 'oracles/test_invoice_pg'


def invoice_source():
    return from_expanded_legacy_xml((SOURCE / 'source.xml').read_text(),
                                   **json.loads((SOURCE / 'adapter-profile.json').read_text()))


def prepared(database, structure):
    migrator = SqlMigrator(database, removeDisabled=True)
    migrator.ormStructure = structure
    migrator.prepareMigrationCommands()
    assert not migrator.warnings, migrator.warnings
    return migrator
