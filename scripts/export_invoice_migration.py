"""Build the complete migration artifact from portable expanded legacy source.

Run with the project's environment: python scripts/export_invoice_migration.py.
The independent physical oracle is used by tests only, never by this producer.
"""
from pathlib import Path
import json

from asqueel import SqlMigrationRenderer
from asqueel.legacy_source import from_expanded_legacy_xml
from asqueel.model import resolve_model
from asqueel.model_codec import model_to_json


def main():
    root = Path(__file__).resolve().parents[1]
    source = root / 'tests/oracles/test_invoice_pg'
    profile = json.loads((source / 'adapter-profile.json').read_text())
    builder = from_expanded_legacy_xml((source / 'source.xml').read_text(), **profile)
    model = resolve_model(builder)
    structure = SqlMigrationRenderer(builder).render()
    destination = root / 'artifacts/test_invoice_pg'
    destination.mkdir(parents=True, exist_ok=True)
    (destination / 'migration.json').write_text(json.dumps(structure, ensure_ascii=False, indent=2) + '\n')
    (destination / 'model.json').write_text(model_to_json(model))
    print(f'{len(model.tables)} tables; migration.json and model.json written to {destination}')


if __name__ == '__main__':
    main()
