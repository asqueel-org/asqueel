"""Examples and dumps the model-cleanup contract tests compare against the files of model_cleanup_golden.

The golden files were written at release/consolidation f8b68f4, before the cleanup:
``<example>.objects.json`` is the live model, ``<example>.migration.json`` the
migration structure.
"""
import json
from pathlib import Path
import sys

from genro_bag import Bag

ROOT = Path(__file__).resolve().parents[1]
GOLDEN = Path(__file__).resolve().parent / 'model_cleanup_golden'


def example_sources():
    """Each example's database source, freshly built: label -> source accepted by AsqueelDb."""
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    from examples.test_invoice_pg import source as invoice
    return {
        'test_invoice_pg': invoice(),
        'two_schemas': str(ROOT / 'examples/two_schemas/configure.py'),
        'sqlite': str(ROOT / 'examples/sqlite/configure.py'),
    }


def _plain(value):
    if isinstance(value, dict):
        return {str(key): _plain(item) for key, item in sorted(value.items(), key=lambda pair: str(pair[0]))}
    if isinstance(value, (list, tuple)):
        return [_plain(item) for item in value]
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return repr(value)


def _bag(bag):
    return {node.label: {'attr': _plain(dict(node.attr)),
                         'value': _bag(node.value) if isinstance(node.value, Bag) else None}
            for node in bag}


def objects_dump(db):
    """Tables, columns, virtual columns (dynamic ones included), composites, indexes and relations of db.model."""
    tables = {}
    for name, table in sorted(db.model.tables.items()):
        virtual = {**dict(table.virtual_columns), **dict(table.dynamic_columns)}
        tables[name] = {
            'sqlname': table.sqlname, 'sqlschema': table.sqlschema,
            'pkey': table.pkey, 'pkeys': _plain(table.pkeys),
            'attributes': _plain(dict(table.attributes)),
            'columns': {key: {'sqlname': column.sqlname, 'dtype': column.dtype,
                              'attributes': _plain(dict(column.attributes))}
                        for key, column in table.columns.items()},
            'virtual_columns': {key: {'tag': column.tag, 'attributes': _plain(dict(column.attributes))}
                                for key, column in sorted(virtual.items())},
            'composites': sorted(table.composites.keys()),
            'indexes': sorted(table.indexes.keys()),
        }
    return {'implementation': db.implementation, 'tables': tables, 'relations': _bag(db.model.relations)}


def golden(label, kind):
    """The stored dump: kind is 'objects' or 'migration'."""
    return json.loads((GOLDEN / f'{label}.{kind}.json').read_text())


def normalized(data):
    """data as it reads back from a golden file."""
    return json.loads(json.dumps(data, sort_keys=True))

