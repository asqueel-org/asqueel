"""Export migration JSON from the native hierarchy, without legacy or compiler."""
import json
from pathlib import Path

from asqueel import SqlMigrationRenderer, to_physical_builder
from examples.test_invoice_pg import source


def main():
    model = source().render(mode='objects_tree')
    structure = SqlMigrationRenderer(to_physical_builder(model)).render()
    destination = Path(__file__).resolve().parents[1] / 'artifacts/test_invoice_pg/objects_tree/migration.json'
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(structure, ensure_ascii=False, indent=2) + '\n')
    print(f'{len(model.tables)} native tables; hierarchical migration JSON written to {destination}')


if __name__ == '__main__':
    main()
