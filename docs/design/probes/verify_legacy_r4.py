"""R4 integrated audit; reuse the frozen corpus and benchmark without core edits.

PostgreSQL uses session-local temporary tables, SQLite uses memory databases.
Historical corpus expectations are diagnostic only: the actual legacy result
is the comparison reference. No execution of the multi-statement probe.
"""
import argparse
import cProfile
import hashlib
import json
from pathlib import Path
import pstats
import sys

from compare_scanners import (
    benchmark, compile_case, connect, encode, execute, models, populate,
)
from scanner_corpus import CASES


ENGINES = ('legacy', 'current', 'tree')


def compare(dbs, dialect):
    connections = {}
    results = []
    try:
        for engine in ENGINES:
            conn = connections[engine] = connect(dialect, engine)
            populate(conn, dialect)
        for case in CASES:
            if dialect not in case['dialects']:
                continue
            entry = {'name': case['name'], 'dialect': dialect,
                     'request': case, 'engines': {}, 'comparisons': {}}
            for engine, db in zip(ENGINES, dbs):
                value = entry['engines'][engine] = {}
                stage = 'compile'
                try:
                    value.update(compile_case(db, engine, case))
                    value[stage] = 'ok'
                    if case['options'].get('execute', True):
                        stage = 'execute'
                        value.update(execute(connections[engine], dialect, engine, value))
                        value[stage] = 'ok'
                except Exception as exc:
                    value[stage] = 'error'
                    value['error'] = {'type': type(exc).__name__, 'message': str(exc)}
            old = entry['engines']['legacy']
            for engine in ENGINES[1:]:
                new = entry['engines'][engine]
                comparison = entry['comparisons'][engine] = {
                    'same_stage_outcome': (old.get('compile'), old.get('execute')) ==
                    (new.get('compile'), new.get('execute')),
                }
                if old.get('execute') == new.get('execute') == 'ok':
                    comparison.update({f'same_{key}': old[key] == new[key]
                                       for key in ('rows', 'columns', 'types')})
                if old.get('compile') == new.get('compile') == 'ok':
                    comparison['same_params'] = old['params'] == new['params']
            results.append(entry)
    finally:
        for conn in connections.values():
            conn.close()
    return results


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--benchmark', action='store_true')
    args = parser.parse_args()
    root = Path('/tmp/asqueel-formula-baseline')
    sys.path.insert(0, str(root / 'legacy/gnrpy'))
    sys.path.append(str(root / 'env/lib/python3.12/site-packages'))
    out = Path('docs/design/evidence/legacy-realignment-r4')
    results = []
    for dialect in ('sqlite', 'postgresql'):
        dbs = models(dialect, include_tree=True)
        try:
            results.extend(benchmark(dbs, dialect, True) if args.benchmark else compare(dbs, dialect))
            if args.benchmark:
                for name in ('common_select', 'repeated_100', 'case_20'):
                    size = 100 if name == 'repeated_100' else 20
                    case = next(c for c in CASES if c['name'] == 'physical').copy()
                    case.update(where='$id=:id', params={'id': 1, 'threshold': 15})
                    case['columns'] = (
                        '$id,$title,COALESCE($amount,0) AS amount'
                        if name == 'common_select' else ','.join(
                            (f'$amount AS c{i}' if name == 'repeated_100' else
                             f'CASE WHEN $amount>=:threshold THEN COALESCE($amount,0) ELSE 0 END AS c{i}')
                            for i in range(size)))
                    for engine, db in zip(ENGINES, dbs):
                        profile = cProfile.Profile()
                        profile.runcall(lambda: [compile_case(db, engine, case) for _ in range(100)])
                        with (out / f'profile-{dialect}-{name}-{engine}.txt').open('w') as stream:
                            pstats.Stats(profile, stream=stream).sort_stats('cumulative').print_stats(35)
        finally:
            for db in dbs[1:]:
                db.close()
    before = json.loads((out / 'code-before.json').read_text())
    after = {str(p): hashlib.sha256(p.read_bytes()).hexdigest()
             for directory in ('src', 'tests', 'examples') for p in Path(directory).rglob('*.py')}
    assert before == after, 'Source, tests or examples changed during R4'
    name = 'benchmark.json' if args.benchmark else 'integrated.json'
    (out / name).write_text(json.dumps(results, indent=2, ensure_ascii=False, default=encode) + '\n')
    print(json.dumps({'output': name, 'cases': len(results), 'code_unchanged': True}))


if __name__ == '__main__':
    main()
