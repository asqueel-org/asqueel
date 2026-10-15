"""Compare frozen Bag extraction algorithms and replay seven legacy helpers.

No model/driver is patched. The source test bodies come from the legacy
reference and run against each snapshot's original bagItemFormula helper.
PostgreSQL result tests are run separately using the original SQL fixtures.
"""
import argparse
import ast
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile
import xml.etree.ElementTree as ET

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--snapshots', type=Path, default=Path('/tmp/asqueel-formula-baseline'))
args = parser.parse_args()
base = args.snapshots
root = Path(__file__).resolve().parents[3]
out = root / 'docs/design/evidence/native-bag-items'
out.mkdir(parents=True, exist_ok=True)
inventory = json.loads((base / 'inventory.json').read_text())
source = (root / 'tests/native_compiler/test_legacy_bag_items.py').read_text()
cls = next(n for n in ast.parse(source).body if isinstance(n, ast.ClassDef))
tests = 'from gnr.sql.gnrsqlmodel import bagItemFormula\n\n' + ast.get_source_segment(source, cls) + '\n'
results = {}
with tempfile.TemporaryDirectory(prefix='bag-item-replay-') as directory:
    testfile = Path(directory) / 'test_bag_items.py'
    testfile.write_text(tests)
    for label, info in inventory.items():
        snapshot = base / label
        definitions, test_inventory = [], []
        for path in sorted(snapshot.rglob('*.py')):
            relative = path.relative_to(snapshot).as_posix()
            if 'gnrpy/gnr/sql/' not in relative and '/tests/' not in relative:
                continue
            code = path.read_text(errors='replace')
            if 'bagItem' not in code and 'bag_item' not in code:
                continue
            try:
                tree = ast.parse(code)
            except SyntaxError:
                continue
            for node in ast.walk(tree):
                if not isinstance(node, ast.FunctionDef):
                    continue
                segment = ast.get_source_segment(code, node)
                record = dict(path=relative, name=node.name, line=node.lineno,
                              sha256=hashlib.sha256(segment.encode()).hexdigest())
                if node.name in ('bagItemFormula', 'bagItemColumn', 'baseDtype'):
                    definitions.append(record)
                elif node.name.startswith('test') and any(k in segment for k in
                        ('bagItem', 'bag_item', 'detail_weight', 'detail_color', 'detail_price')):
                    test_inventory.append(record)
        env = dict(os.environ, PYTHONPATH=str(snapshot / 'gnrpy'))
        with (out / f'{label}-helpers.log').open('w') as log:
            run = subprocess.run([str(base / 'env/bin/python'), '-m', 'pytest', '-q',
                                  '-o', 'addopts=', '--junitxml=' + str(out / f'{label}-helpers.xml'),
                                  str(testfile)], env=env, stdout=log, stderr=subprocess.STDOUT)
        cases = []
        for case in ET.parse(out / f'{label}-helpers.xml').getroot().iter('testcase'):
            failure = next((case.find(t) for t in ('failure', 'error')
                            if case.find(t) is not None), None)
            cases.append(dict(name=case.get('name'), status='passed' if failure is None else 'failed',
                              **({'message': failure.get('message')} if failure is not None else {})))
        results[label] = dict(commit=info['commit'], algorithms=definitions,
                              historical_tests=test_inventory, replay=cases)
        print(label, 'helper tests', sum(c['status'] == 'passed' for c in cases), '/', len(cases), flush=True)
(out / 'legacy-comparison.json').write_text(json.dumps(results, indent=2) + '\n')
(out / 'replayed-helpers.py').write_text(tests)
