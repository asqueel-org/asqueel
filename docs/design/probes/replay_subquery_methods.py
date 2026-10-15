"""Replay new regression contracts on frozen legacy compilers, without DB I/O.

No historical dedicated subquery_* tests were found. This probe extracts the
shared contract bodies from the native tests and records each original compiler's
behavior; it neither patches legacy code nor claims these are historical tests.
"""

import argparse
import ast
import hashlib
import json
import os
import subprocess
import tempfile
from pathlib import Path
import xml.etree.ElementTree as ET

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--snapshots', type=Path, default=Path('/tmp/asqueel-formula-baseline'))
args = parser.parse_args()
root = Path(__file__).resolve().parents[3]
base = args.snapshots
out = root / 'docs/design/evidence/native-subquery-methods'
out.mkdir(parents=True, exist_ok=True)
source = root / 'tests/native_compiler/test_subquery_methods.py'
code = source.read_text()
nodes = ast.parse(code).body
shared = 'from types import MethodType\nimport pytest\n\n' + '\n\n'.join(
    ast.get_source_segment(code, n)
    for n in nodes
    if isinstance(n, (ast.FunctionDef, ast.ClassDef))
    and n.name in ('declare', 'install', 'TestLegacySubqueryMethodContract')
)
fixture = """
@pytest.fixture
def db():
    from gnr.sql.gnrsql import GnrSqlDb
    db=GnrSqlDb(implementation='sqlite',dbname=':memory:')
    declare(db.model.src.package('app'))
    db.startup()
    db.method_calls=install(db)
    yield db
    db.closeConnection()
"""
inventory = json.loads((root / 'docs/design/evidence/formula-baseline/inventory.json').read_text())
results = {}
with tempfile.TemporaryDirectory(prefix='subquery-method-replay-') as d:
    testfile = Path(d) / 'test_contract.py'
    testfile.write_text(shared + fixture)
    for label, info in inventory.items():
        compiler = base / label / 'gnrpy/gnr/sql/gnrsqldata/compiler.py'
        tree = ast.parse(compiler.read_text())
        dispatch = []
        for n in ast.walk(tree):
            if isinstance(n, ast.FunctionDef) and any(
                isinstance(x, ast.Constant)
                and isinstance(x.value, str)
                and 'subquery_%s' in x.value
                for x in ast.walk(n)
            ):
                dispatch.append(
                    dict(
                        name=n.name,
                        line=n.lineno,
                        ast_sha256=hashlib.sha256(
                            ast.dump(n, include_attributes=False).encode()
                        ).hexdigest(),
                    )
                )
        env = dict(os.environ, PYTHONPATH=str(base / label / 'gnrpy'))
        with (out / f'{label}.log').open('w') as log:
            run = subprocess.run(
                [
                    str(base / 'env/bin/python'),
                    '-m',
                    'pytest',
                    '-q',
                    '-o',
                    'addopts=',
                    f'--junitxml={out}/{label}.xml',
                    str(testfile),
                ],
                env=env,
                stdout=log,
                stderr=subprocess.STDOUT,
            )
        cases = []
        for c in ET.parse(out / f'{label}.xml').getroot().iter('testcase'):
            error = next((c.find(t) for t in ('failure', 'error') if c.find(t) is not None), None)
            cases.append(
                dict(
                    test=c.get('name'),
                    status='failed' if error is not None else 'passed',
                    **({'message': error.get('message')} if error is not None else {}),
                )
            )
        results[label] = dict(commit=info['commit'], dispatch=dispatch, tests=cases)
        print(label, run.returncode, flush=True)
(out / 'legacy-comparison.json').write_text(json.dumps(results, indent=2) + '\n')
(out / 'replayed-contract.py').write_text(shared + fixture)
