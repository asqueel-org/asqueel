"""Compare original legacy clause assembly and the R4 corpus after renderer alignment."""
import argparse
import ast
import hashlib
import json
from pathlib import Path
import sys
from types import SimpleNamespace

from compare_scanners import benchmark, encode, models
from verify_legacy_r4 import compare


OUT = Path('docs/design/evidence/legacy-renderer-r4')
ROOT = Path('/tmp/asqueel-formula-baseline')


def legacy_oracle():
    records = []
    clauses = [
        {}, {'where': '(id=:id)'},
        {'where': '(id=:id)', 'order_by': 'id', 'limit': 3, 'offset': 1},
        {'group_by': 'id', 'having': 'count(*)>1', 'order_by': 'id'},
        {'columns': '1 AS first,\n2 AS second'},
        {'columns': "'a,b' AS value"},
        {'columns': "' AS ' AS value"},
        {'columns': '1 -- existing corpus case'},
        {'where': '(id=:id -- existing corpus case)', 'order_by': 'id'},
        {'where': '(id=1 /* open)', 'order_by': 'id'},
        {'columns': "'unclosed AS value"},
        {'where': '/* existing corpus case */'},
    ]
    anchors = {}
    for branch in ('legacy', 'compound', 'v2', 'v3', 'v3_merged', 'v4', 'simplify', 'next'):
        path = ROOT / branch / 'gnrpy/gnr/sql/adapters/_gnrbaseadapter.py'
        tree = ast.parse(path.read_text())
        method = next(n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name == 'compileSql')
        namespace = {}
        exec(compile(ast.Module(body=[method], type_ignores=[]), str(path), 'exec'), namespace)
        anchors[branch] = {'file': str(path), 'line': method.lineno,
                           'ast_sha256': hashlib.sha256(ast.dump(method).encode()).hexdigest()}
        outcomes = []
        for options in clauses:
            kwargs = {'maintable': '"s"."t"', 'maintable_as': '"t0"', 'columns': 'id AS value', **options}
            outcomes.append({'arguments': kwargs, 'sql': namespace['compileSql'](SimpleNamespace(), **kwargs)})
        if not records:
            records = outcomes
        assert outcomes == records, branch
    Path('tests/oracles/legacy_renderer.json').write_text(json.dumps(records, indent=2) + '\n')
    (OUT / 'algorithm-anchors.json').write_text(json.dumps(anchors, indent=2) + '\n')
    print(f'{len(records)} assembly cases identical across {len(anchors)} original adapters')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--oracle', action='store_true')
    parser.add_argument('--benchmark', action='store_true')
    args = parser.parse_args()
    if args.oracle:
        legacy_oracle()
        return
    sys.path.insert(0, str(ROOT / 'legacy/gnrpy'))
    sys.path.append(str(ROOT / 'env/lib/python3.12/site-packages'))
    results = []
    for dialect in ('sqlite', 'postgresql'):
        dbs = models(dialect, include_tree=True)
        try:
            results.extend(benchmark(dbs, dialect, True) if args.benchmark else compare(dbs, dialect))
        finally:
            for db in dbs[1:]:
                db.close()
    name = 'benchmark.json' if args.benchmark else 'integrated.json'
    (OUT / name).write_text(json.dumps(results, indent=2, ensure_ascii=False, default=encode) + '\n')
    print(f'{len(results)} cases written to {OUT / name}')


if __name__ == '__main__':
    main()
