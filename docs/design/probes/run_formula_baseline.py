"""Run unchanged tests in disposable snapshots produced by formula_census.py.

The project suite replaces only its personal-instance fixture. The SQL suite
uses the original fixtures. Historical dependencies must already be installed.
Run with --root DIR --labels legacy next --suite sql (or project).
"""
import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--labels', nargs='+', required=True)
    parser.add_argument('--suite', choices=['sql', 'project'], required=True)
    args = parser.parse_args()
    inventory = json.loads((args.root / 'inventory.json').read_text())
    for label in args.labels:
        root = args.root / label
        files = [f['path'] for f in inventory[label]['files']
                 if f['path'].startswith('gnrpy/tests/sql/') and 'migration' not in f['path']]
        if args.suite == 'project':
            fixture = root / 'projects/test_invoice/tests/conftest.py'
            original = fixture.with_suffix('.original.py')
            if not original.exists():
                shutil.copyfile(fixture, original)
            shutil.copyfile(Path(__file__).with_name('legacy_formula_project_fixture.py'), fixture)
            files = ['projects/test_invoice/tests']
        env = dict(os.environ, PYTHONPATH=f'{root}/gnrpy:{root}/gnrpy/tests',
                   FORMULA_BASELINE_CSV=str(args.root / 'legacy/projects/test_invoice/data/export'),
                   FORMULA_BASELINE_MANIFEST=str(args.root / f'{label}-data.json'))
        for key in ['GNR_TEST_PG_PASSWORD', 'GITHUB_WORKFLOW', 'GENRO_GNRFOLDER']:
            env.pop(key, None)
        stem = args.root / f'{label}-{args.suite}'
        command = [str(args.root / 'env/bin/python'), '-m', 'pytest', '-q', '-ra',
                   '-o', 'addopts=', '--junitxml=' + str(stem.with_suffix('.xml')), *files]
        with stem.with_suffix('.log').open('w') as output:
            run = subprocess.run(command, cwd=root, env=env,
                                 stdout=output, stderr=subprocess.STDOUT)
        print(label, args.suite, 'exit', run.returncode, flush=True)


if __name__ == '__main__':
    main()
