"""Persist the inventory, per-test outcomes and native-column compilation probe."""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import xml.etree.ElementTree as ET


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--legacy', required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    inventory = json.loads((args.root / 'inventory.json').read_text())
    for label, item in inventory.items():
        for module in item['files']:
            path = module['path']
            selected = ((path.startswith('gnrpy/tests/sql/') and 'migration' not in path)
                        or path.startswith('projects/test_invoice/tests/'))
            module['baseline_selected'] = selected
            if selected:
                original = subprocess.check_output([
                    'git', '-C', args.legacy, 'show', item['commit'] + ':' + path])
                actual = (args.root / label / path).read_bytes()
                assert actual == original, (label, path, 'test source changed')
                module['sha256'] = hashlib.sha256(original).hexdigest()
            else:
                module['classification'] = 'supporting declaration/application test; outside compiler SQL baseline'
    (args.output / 'inventory.json').write_text(json.dumps(inventory, indent=2) + '\n')
    results = {}
    for path in sorted(args.root.glob('*.xml')):
        if not (path.stem.endswith(('-sql', '-project'))
                or path.stem in ['simplify-new', 'asqueel-tests']):
            continue
        cases = []
        for case in ET.parse(path).getroot().findall('.//testcase'):
            record = {'class': case.get('classname'), 'name': case.get('name'), 'status': 'passed'}
            for tag in ['failure', 'error', 'skipped']:
                outcome = case.find(tag)
                if outcome is not None:
                    record['status'] = ('xfail' if tag == 'skipped' and
                                        outcome.get('type') == 'pytest.xfail' else tag)
                    record['message'] = outcome.get('message')
                    break
            cases.append(record)
        counts = dict(Counter(c['status'] for c in cases))
        results[path.stem] = {'counts': counts, 'cases': cases}
        print(path.stem, counts)
    (args.output / 'results.json').write_text(json.dumps(
        {'date': '2026-10-14', 'baseline': results}, indent=2) + '\n')
    shutil.copyfile(args.root / 'asqueel-native-columns.json', args.output / 'native-columns.json')
    data = {label: json.loads((args.root / f'{label}-data.json').read_text())
            for label in ['v2', 'v3', 'v3_merged', 'v4']}
    (args.output / 'project-data.json').write_text(json.dumps(data, indent=2) + '\n')


if __name__ == '__main__':
    main()
