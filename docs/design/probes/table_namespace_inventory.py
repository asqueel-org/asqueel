"""Inventory effective legacy table namespaces, without evaluating properties.

Run with the frozen legacy PYTHONPATH/interpreter. Uses the existing sanitized
invoice capture: no SQL, network, instance credentials or startup services.
"""
import inspect
import json
from pathlib import Path
import runpy
from tempfile import TemporaryDirectory
from unittest.mock import patch

from gnr.sql.gnrsqlmodel.table import DbTableObj
from gnr.sql.gnrsqltable import SqlTable
from gnr.sql.gnrsqlmigration.orm_extractor import OrmExtractor
from gnr.app.gnrdbo import TableBase

ROOT = Path(__file__).resolve().parents[3]
LEGACY = Path(inspect.getfile(SqlTable)).resolve().parents[4]
OUTPUT = ROOT / 'docs/design/evidence/table-namespace/inventory.json'


def inventory(obj):
    cls = obj if isinstance(obj, type) else type(obj)
    names = set().union(*(set(vars(c)) for c in cls.__mro__))
    if not isinstance(obj, type):
        names.update(vars(obj))
    result = {}
    for name in sorted(names):
        if name.startswith('__') and name.endswith('__'):
            continue
        value = inspect.getattr_static(obj, name)
        owner = next((c.__name__ for c in cls.__mro__ if name in vars(c)), 'instance')
        if not isinstance(obj, type) and name in vars(obj):
            owner = 'instance'
        function = None
        if isinstance(value, property):
            kind, function = 'property', value.fget
        elif isinstance(value, (staticmethod, classmethod)):
            kind, function = 'method', value.__func__
        elif inspect.isroutine(value):
            kind, function = 'method', getattr(value, '__func__', value)
        else:
            kind = 'attribute'
        entry = {'kind': kind, 'owner': owner, 'public': not name.startswith('_')}
        if function is not None:
            try:
                filename = Path(inspect.getfile(function)).resolve()
                entry['file'] = str(filename.relative_to(LEGACY))
                entry['line'] = function.__code__.co_firstlineno
            except (TypeError, ValueError, AttributeError):
                pass
        result[name] = entry
    return result


def counts(members):
    return {kind: sum(e['public'] and e['kind'] == kind for e in members.values())
            for kind in ('method', 'property', 'attribute')}


result = {'reference': 'fa35e5adfa6ad1b269f3a22a9b12c4c1ee6513ea',
          'scope': 'Effective namespaces; public means not starting with underscore; properties are not evaluated',
          'base_operational': inventory(SqlTable), 'base_model': inventory(DbTableObj),
          'application_base': inventory(TableBase), 'tables': {}}
original = OrmExtractor.get_json_struct


def collect(extractor, *args, **kwargs):
    for pkg in extractor.db.packages.values():
        for model in pkg.tables.values():
            operational = inventory(model.dbtable)
            structure = inventory(model)
            common = sorted(k for k in operational.keys() & structure.keys()
                            if operational[k]['public'] and structure[k]['public'])
            combined = {**structure, **operational}
            result['tables'][model.fullname] = {
                'operational': operational, 'model': structure,
                'counts_operational': counts(operational), 'counts_model': counts(structure),
                'union_public_names': sum(e['public'] for e in combined.values()),
                'overlapping_public_names': common,
            }
    return original(extractor, *args, **kwargs)


with TemporaryDirectory(prefix='asqueel-table-inventory-') as output:
    with patch.object(OrmExtractor, 'get_json_struct', collect):
        runpy.run_path(str(ROOT / 'scripts/capture_legacy_invoice.py'))['capture'](LEGACY, Path(output))
# Store shared entries once. Each effective namespace is common + table delta.
for kind in ('operational', 'model'):
    namespaces = [table[kind] for table in result['tables'].values()]
    common = {name: entry for name, entry in namespaces[0].items()
              if all(namespace.get(name) == entry for namespace in namespaces[1:])}
    result['common_' + kind] = common
    for table in result['tables'].values():
        original_members = table.pop(kind)
        delta = {name: entry for name, entry in original_members.items() if name not in common}
        assert {**common, **delta} == original_members
        table[kind + '_delta'] = delta
OUTPUT.write_text(json.dumps(result, indent=2, ensure_ascii=False) + '\n')
print('Legacy root:', LEGACY)
for key in ('base_operational', 'base_model', 'application_base'):
    print(key, counts(result[key]))
print('Tables:', len(result['tables']))
for key in ('invc.invoice', 'invc.customer', 'invc.invoice_row', 'adm.user'):
    t = result['tables'][key]
    print(key, t['counts_operational'], t['counts_model'], 'union',t['union_public_names'],
          'overlap', len(t['overlapping_public_names']))
