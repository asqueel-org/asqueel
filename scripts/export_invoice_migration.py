"""Export native test_invoice_pg objects and migration JSON, without GenroPy.

Run from the repository with its dependencies installed:
    PYTHONPATH=.:src:../asqueel-migration/src python scripts/export_invoice_migration.py

The independent legacy snapshots are test expectations only. Historical bridge
artifacts remain in artifacts/test_invoice_pg; native outputs are in native/.
"""
from pathlib import Path
import json

from asqueel import AsqueelDb
from examples.test_invoice_pg import source


def main():
    root = Path(__file__).resolve().parents[1]
    db = AsqueelDb(source())
    try:
        structure = db.config.builder.render(mode='migration')
        destination = root / 'artifacts/test_invoice_pg/native'
        destination.mkdir(parents=True, exist_ok=True)
        (destination / 'migration.json').write_text(json.dumps(structure, ensure_ascii=False, indent=2) + '\n')
        print(f'{len(db.model.tables)} native tables; migration.json written to {destination}')
    finally:
        db.closeConnection()


if __name__ == '__main__':
    main()
