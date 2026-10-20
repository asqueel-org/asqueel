"""Run selected, unchanged legacy tests and record their provenance.

The selection includes DISTINCT/exploding/count. It excludes table aliases,
pyColumn execution, #PREF, set operators and experimental query syntax.
Original fixtures provision their own disposable SQLite/PostgreSQL databases.
"""
import argparse
import ast
import hashlib
import json
import os
from pathlib import Path
import subprocess
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[3]
SNAPSHOTS = Path('/tmp/asqueel-formula-baseline')
TEST_FILE = 'gnrpy/tests/sql/test_compiler_coverage.py'
CLASSES = (
    'TestPhysicalColumns', 'TestAliasColumn', 'TestFormulaSelect', 'TestFormulaSql',
    'TestCaseWhen', 'TestCoalesce', 'TestFormulaChain', 'TestSubQueryColumn',
    'TestVarParameters', 'TestNamedSubQuery', 'TestRelationNavigation',
    'TestGroupBy', 'TestWhereOrderBy', 'TestGroupByHaving', 'TestEmbedFieldPars',
    'TestExplodingFastPath', 'TestDistinctExploding', 'TestCompiledQueryOptions',
    'TestExpandInRange', 'TestExpandPeriod', 'TestBagItemColumn',
    'TestCompositeColumnPg', 'TestCompositeColumnSqlite',
    'TestJoinColumn',  # Reference only: the native declarations use the agreed GEP mapping.
)


def definitions(path):
    if not path.exists():
        return {}
    return {f'{cls.name}::{node.name}': {
        'line': node.lineno,
        'ast_sha256': hashlib.sha256(ast.dump(node, include_attributes=False).encode()).hexdigest(),
    } for cls in ast.parse(path.read_text()).body if isinstance(cls, ast.ClassDef)
        and cls.name in CLASSES for node in cls.body
        if isinstance(node, ast.FunctionDef) and node.name.startswith('test_')}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-directory', type=Path, required=True)
    parser.add_argument('--inventory-only', action='store_true')
    args = parser.parse_args()
    out = args.output_directory.resolve()
    out.mkdir(parents=True, exist_ok=True)
    inventory = json.loads((ROOT/'docs/design/evidence/formula-baseline/inventory.json').read_text())
    originals = definitions(SNAPSHOTS/'legacy'/TEST_FILE)
    composite_file = 'gnrpy/tests/sql/test_composite_column.py'
    composites = definitions(SNAPSHOTS/'legacy'/composite_file)
    refs = {label: definitions(SNAPSHOTS/label/TEST_FILE) for label in inventory}
    manifest = {
        'reference': inventory['legacy']['commit'], 'source_file': TEST_FILE,
        'fixture': 'Original tests/sql/conftest.py, unchanged; original project CSVs',
        'tests': {name: {**value, 'references': {
            label: ('absent' if name not in tests else 'identical'
                    if tests[name]['ast_sha256'] == value['ast_sha256'] else 'different')
            for label, tests in refs.items()}} for name, value in originals.items()},
        'snapshots': {label: item['commit'] for label, item in inventory.items()},
        'composite_file': composite_file, 'composite_tests': composites,
    }
    (out/'original-tests.json').write_text(json.dumps(manifest, indent=2)+'\n')
    if args.inventory_only:
        print(f'{len(originals) + len(composites)} original tests inventoried')
        return
    root = SNAPSHOTS/'legacy'
    command = [str(SNAPSHOTS/'env/bin/python'), '-m', 'pytest', '-q', '-ra',
               '-o', 'addopts=', '--junitxml='+str(out/'original-tests.xml'),
               *[f'{TEST_FILE}::{name}' for name in originals],
               *[f'{composite_file}::{name}' for name in composites]]
    env = dict(os.environ, PYTHONPATH=f'{root}/gnrpy:{root}/gnrpy/tests')
    # The original fixture uses a private ephemeral server without shared credentials.
    for key in ('GNR_TEST_PG_PASSWORD', 'GITHUB_WORKFLOW', 'GENRO_GNRFOLDER'):
        env.pop(key, None)
    with (out/'original-tests.log').open('w') as stream:
        run = subprocess.run(command, cwd=root, env=env, stdout=stream, stderr=subprocess.STDOUT)
    suites = ET.parse(out/'original-tests.xml').getroot()
    result = {'returncode': run.returncode, 'selected': len(originals) + len(composites),
              **{key: sum(int(s.attrib.get(key, 0)) for s in suites.findall('testsuite'))
                 for key in ('tests', 'failures', 'errors', 'skipped')}}
    result['passed'] = result['tests'] - result['failures'] - result['errors'] - result['skipped']
    (out/'original-summary.json').write_text(json.dumps(result, indent=2)+'\n')
    print(json.dumps(result))
    raise SystemExit(run.returncode)


if __name__ == '__main__':
    main()
