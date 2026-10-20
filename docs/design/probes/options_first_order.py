"""Compare physical column order on all 74 native models; no database I/O.

Run from the repository with PYTHONPATH=src:../asqueel-migration/src:.
The legacy reference is the frozen expanded XML, never the current compiler.
"""
import json
from pathlib import Path
import xml.etree.ElementTree as ET

from asqueel.catalog import SqlModelCatalog
from asqueel.model_source import prepare_source
from examples.test_invoice_pg import source

ROOT = Path(__file__).resolve().parents[3]


def name(node):
    return node.attrib.get('_tag', node.tag)


def main():
    legacy = {}
    xml = ET.parse(ROOT / 'tests/oracles/test_invoice_pg/source.xml').getroot()
    for package in xml.find('packages'):
        for table in package.find('tables'):
            columns = table.find('columns')
            legacy[f'{name(package)}.{name(table)}'] = (
                [name(column) for column in columns] if columns is not None else [])
    config = source()
    before = config.source.to_json()
    original = SqlModelCatalog(config)
    prepared = SqlModelCatalog(prepare_source(config, options_first=True))
    model = config.render(mode='objects_tree')
    assert config.source.to_json() == before
    results = {}
    for key in prepared.tables:
        fullname = '.'.join(key)
        authored = [c for p, t, c in original.physical_columns if (p, t) == key]
        expanded = [c for p, t, c in prepared.physical_columns if (p, t) == key]
        actual = list(model.table(fullname).columns)
        expected = legacy[fullname]
        assert expanded == actual
        assert set(actual) == set(expected)
        results[fullname] = dict(authored=authored, expanded=expanded, legacy=expected,
                                 same_order=actual == expected)
    mismatches = [key for key, value in results.items() if not value['same_order']]
    report = dict(tables=len(results), source_unchanged=True,
                  expanded_order_preserved=len(results), identical_field_sets=len(results),
                  identical_order=len(results) - len(mismatches),
                  different_order=mismatches, models=results)
    destination = ROOT / 'docs/design/evidence/options-first/order.json'
    destination.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps({k: v for k, v in report.items() if k != 'models'}, indent=2))


if __name__ == '__main__':
    main()
