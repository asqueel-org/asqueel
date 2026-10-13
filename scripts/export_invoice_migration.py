"""Export native test_invoice_pg objects and migration JSON, without GenroPy.

Run from the repository with its dependencies installed:
    PYTHONPATH=.:src:../asqueel-migration/src python scripts/export_invoice_migration.py

The independent legacy snapshots are test expectations only. Historical bridge
artifacts remain in artifacts/test_invoice_pg; native outputs are in native/.
"""
from pathlib import Path
import json

from asqueel import SqlMigrationRenderer
from asqueel.configuration import build_database
from asqueel.model_codec import model_to_json
from asqueel.projection import to_physical_builder
from examples.test_invoice_pg import source


def main():
    root = Path(__file__).resolve().parents[1]
    db = build_database(source())
    try:
        # Projection reads the completed objects. It never renders source again.
        structure = SqlMigrationRenderer(to_physical_builder(db.model)).render()
        destination = root / 'artifacts/test_invoice_pg/native'
        destination.mkdir(parents=True, exist_ok=True)
        (destination / 'migration.json').write_text(json.dumps(structure, ensure_ascii=False, indent=2) + '\n')
        (destination / 'model.json').write_text(model_to_json(db.model))
        print(f'{len(db.model.tables)} native tables; migration.json and model.json written to {destination}')
    finally:
        db.close()


if __name__ == '__main__':
    main()
