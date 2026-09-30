"""Inventory source definitions, not pytest collection or execution results."""
import argparse
import ast
import hashlib
import json
import subprocess
from pathlib import Path


def catalog(root):
    paths = sorted((root / 'gnrpy/tests/sql').glob('*.py'))
    paths.append(root / 'gnrpy/tests/app/test_gnrsqlappdb.py')
    files = []
    for path in paths:
        raw = path.read_bytes()
        tree = ast.parse(raw)
        tests, classes = [], []

        def walk(node, parent=''):
            body = getattr(node, 'body', [])
            for index, item in enumerate(body):
                if isinstance(item, ast.ClassDef):
                    classes.append(dict(name=parent + item.name,
                                        bases=[ast.unparse(b) for b in item.bases],
                                        decorators=[ast.unparse(d) for d in item.decorator_list]))
                    walk(item, parent + item.name + '.')
                elif isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)) and item.name.startswith('test'):
                    overwritten = any(isinstance(later, (ast.FunctionDef, ast.AsyncFunctionDef))
                                      and later.name == item.name for later in body[index + 1:])
                    tests.append(dict(name=parent + item.name, line=item.lineno,
                                      end_line=item.end_lineno, overwritten=overwritten,
                                      decorators=[ast.unparse(d) for d in item.decorator_list]))
        walk(tree)
        files.append(dict(path=str(path.relative_to(root)), sha256=hashlib.sha256(raw).hexdigest(),
                          lines=len(raw.splitlines()), classes=classes, tests=tests))
    revision = subprocess.check_output(['git', '-C', str(root), 'rev-parse', 'HEAD'], text=True).strip()
    return dict(legacy_commit=revision, scope='gnrpy/tests/sql/*.py + app/test_gnrsqlappdb.py',
                file_count=len(files), source_test_definitions=sum(len(f['tests']) for f in files), files=files)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('legacy_root', type=Path)
    parser.add_argument('--output-dir', type=Path, default=Path(__file__).resolve().parent)
    args = parser.parse_args()
    result = catalog(args.legacy_root.resolve())
    args.output_dir.mkdir(parents=True, exist_ok=True)
    (args.output_dir / 'legacy-sql-tests.json').write_text(json.dumps(result, indent=2) + '\n')
    base = 'https://github.com/genropy/genropy/blob/' + result['legacy_commit'] + '/'
    lines = ['# Legacy SQL test source index', '',
             'Generated from source; not a pytest collection or execution report.', '',
             f"{result['file_count']} files; {result['source_test_definitions']} test definitions.", '',
             'Hashes, class bases and class/function decorators are in `legacy-sql-tests.json`.', '',
             'Base-class inheritance, parametrization, collection rules and skips change the executable count.', '']
    for item in result['files']:
        lines += [f"## {item['path']}", '', f"{len(item['tests'])} definitions; {item['lines']} source lines.", '']
        for test in item['tests']:
            flag = ' — OVERWRITTEN by a later definition' if test['overwritten'] else ''
            lines.append(f"- [{test['name']}]({base}{item['path']}#L{test['line']}){flag}")
        lines.append('')
    (args.output_dir / 'legacy-sql-tests-index.md').write_text('\n'.join(lines))
    print(f"{result['file_count']} files, {result['source_test_definitions']} source definitions")
    print('Overwritten:', [(f['path'], t['name'], t['line']) for f in result['files'] for t in f['tests'] if t['overwritten']])


if __name__ == '__main__':
    main()
