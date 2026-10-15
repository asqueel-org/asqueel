"""Offline structural oracle: run with the frozen GenroPy interpreter/PYTHONPATH.

Input is the independently captured legacy source, used only for tests.
Asqueel rendering never reads it. No connection or formula execution.
"""
import hashlib
import json
from pathlib import Path
from unittest.mock import patch

from gnr.sql.gnrsql import GnrSqlDb

ROOT = Path(__file__).resolve().parents[3]
SOURCE = ROOT / 'tests/oracles/test_invoice_pg/source.xml'
OUTPUT = ROOT / 'docs/design/evidence/object-tree/legacy.json'


def denied(*args, **kwargs):
    raise AssertionError('Structural capture must not execute SQL or connect')


with patch.object(GnrSqlDb, 'execute', denied), patch('socket.socket.connect', denied):
    db = GnrSqlDb(implementation='postgres', dbname='unused', debug=True)
    db.model.load(str(SOURCE))
    db.startup()
    relations = {f'{p.label}.{t.label}.{r.label}': dict(r.attr)
                 for p in db.model.relations for t in p.value for r in t.value}
    views = {f'{p.name}.{t.name}': list(t.relations.keys())
             for p in db.model.obj.values() for t in p.tables.values()}
    result = {
        'reference': 'fa35e5adfa6ad1b269f3a22a9b12c4c1ee6513ea',
        'source_sha256': hashlib.sha256(SOURCE.read_bytes()).hexdigest(),
        'relations': relations, 'view_keys': views,
    }
    OUTPUT.write_text(json.dumps(result, indent=2, ensure_ascii=False) + '\n')
print(f'{len(relations)} relation entries; {len(views)} table views; no I/O')
