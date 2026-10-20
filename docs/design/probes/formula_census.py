"""Inventory frozen legacy formula/compiler tests without importing GenroPy.

Usage: python formula_census.py --legacy REPO --output DIR
Snapshots and evidence are written outside the legacy working tree.
"""
import argparse
import ast
import hashlib
import io
import json
from pathlib import Path
import re
import subprocess
import tarfile

REFS = {
    'legacy': 'fa35e5adfa6ad1b269f3a22a9b12c4c1ee6513ea',
    'compound': '4c075f7adac55c05f2dad555b2b1277449388944',
    'v2': '68f35b99c440df3658d275f3403f10962a953be6',
    'v3': '67bba0e59183f6df2b3463064c9feb2c21be225e',
    'v3_merged': '19da337f4632cc69897c9373aa263dcb49abc293',
    'v4': '38d210c376abaa390619c2b16985318921d6dd1d',
    'simplify': '13b891883487e8948921eb6694e14f8e51bc464d',
    'next': '12cfdcce86337119591b6c8247e7166d831c08b9',
}
PATTERN = re.compile(
    r'formulaColumn|sql_formula|subQueryColumn|aliasColumn|bagItemColumn|pyColumn|'
    r'compositeColumn|#THIS|select_\w+|#IN_RANGE|#PERIOD|#PREF|#ENV')


def inventory(root):
    files = []
    for path in sorted(root.rglob('*.py')):
        relative = path.relative_to(root).as_posix()
        if '/tests/' not in relative or not (
                path.name.startswith('test_') or path.name.endswith('_test.py')):
            continue
        source = path.read_text(errors='replace')
        hits = sorted(set(PATTERN.findall(source)))
        if not hits and not any(word in path.name for word in ('compiler', 'subquery', 'query_test')):
            continue
        try:
            tree = ast.parse(source)
        except SyntaxError as error:
            files.append({'path': relative, 'parse_error': str(error)})
            continue
        tests = []

        def visit(node, parents=()):
            for child in ast.iter_child_nodes(node):
                if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)) and child.name.startswith('test'):
                    segment = ast.get_source_segment(source, child)
                    tests.append({'name': '::'.join((*parents, child.name)),
                                  'line': child.lineno,
                                  'sha256': hashlib.sha256(segment.encode()).hexdigest(),
                                  'hits': sorted(set(PATTERN.findall(segment))),
                                  'decorators': [ast.unparse(d) for d in child.decorator_list]})
                elif isinstance(child, ast.ClassDef):
                    visit(child, (*parents, child.name))
        visit(tree)
        files.append({'path': relative, 'sha256': hashlib.sha256(source.encode()).hexdigest(),
                      'hits': hits, 'tests': tests})
    return files


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--legacy', required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    report = {}
    for label, commit in REFS.items():
        root = args.output / label
        if not root.exists():
            archive = subprocess.check_output([
                'git', '-C', args.legacy, 'archive', commit,
                'gnrpy', 'projects/test_invoice', 'projects/gnrcore'])
            root.mkdir()
            with tarfile.open(fileobj=io.BytesIO(archive)) as tar:
                tar.extractall(root, filter='data')
        files = inventory(root)
        report[label] = {'commit': commit, 'files': files}
        print(label, 'modules', len(files), 'definitions', sum(len(f.get('tests', [])) for f in files))
    (args.output / 'inventory.json').write_text(json.dumps(report, indent=2) + '\n')


if __name__ == '__main__':
    main()
