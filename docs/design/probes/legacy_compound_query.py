"""Audit isolato del branch GenroPy compound_query; nessun import del core.

python3 docs/design/probes/legacy_compound_query.py --legacy /path/to/genropy
Aggiungere --postgres per confrontare su PostgreSQL i SQL generati.
Richiede git e, solo con --postgres, psql. Connessione: GNR_TEST_PG_*.

Estrae con AST i metodi originali a un commit fisso. Sostituisce solo la
costruzione delle query foglia e la compilazione modello -> SELECT con una
fixture minima. Cache, composizione e mangling sono codice legacy originale.
Non equivale a eseguire l'intera suite o l'intero compilatore GenroPy.
"""

import argparse
import ast
from collections import Counter
import json
import os
from pathlib import Path
import re
import subprocess
from types import SimpleNamespace


REV = '4c075f7adac55c05f2dad555b2b1277449388944'
QUERY_PATH = 'gnrpy/gnr/sql/gnrsqldata/query.py'
COMPILER_PATH = 'gnrpy/gnr/sql/gnrsqldata/compiler.py'
OPERATORS = ('UNION', 'UNION ALL', 'INTERSECT', 'EXCEPT')


def original_class(repo, path, name, methods=None):
    source = subprocess.check_output(
        ['git', '-C', str(repo), 'show', f'{REV}:{path}'], text=True)
    cls = next(n for n in ast.parse(source).body
               if isinstance(n, ast.ClassDef) and n.name == name)
    if methods is not None:
        cls.body = [n for n in cls.body
                    if (isinstance(n, ast.FunctionDef) and n.name in methods)
                    or (isinstance(n, ast.Assign) and any(
                        isinstance(t, ast.Name) and t.id in methods
                        for t in n.targets))]
    return cls


def load_legacy(repo):
    methods = {'_get_sqltext', 'sqltext', '_get_compiled', 'compiled', 'test',
               '_next_mangler_key', '_compound', '__add__', '__or__',
               '__and__', '__sub__'}
    module = ast.Module(body=[
        original_class(repo, QUERY_PATH, 'SqlQuery', methods),
        original_class(repo, QUERY_PATH, 'SqlCompoundQuery'),
        original_class(repo, COMPILER_PATH, 'SqlQueryCompiler',
                       {'mangle', 'mangleParams'}),
    ], type_ignores=[])
    namespace = {'re': re}
    exec(compile(ast.fix_missing_locations(module), str(repo / QUERY_PATH), 'exec'),
         namespace)
    return namespace['SqlQuery'], namespace['SqlQueryCompiler']


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--legacy', required=True, type=Path)
    parser.add_argument('--postgres', action='store_true')
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    query_class, compiler_class = load_legacy(args.legacy)

    class Leaf(query_class):
        def __init__(self, db, sql='SELECT :n AS x', value=1):
            self.db = db
            self.dbtable = SimpleNamespace(fullname='audit.fixture')
            self.original_sql = sql
            self.sqlparams = {'n': value}
            self.mangler = None
            self._compiled = None

        def compileQuery(self):
            compiler = compiler_class()
            compiler.mangler = self.mangler
            compiler.sqlparams = self.sqlparams
            compiler.query_kw = dict(self.sqlparams)
            compiler.mainquery_kw = {}
            compiler.subquery_kw = {}
            sql = compiler.mangle(self.original_sql)
            compiler.mangleParams()
            return SimpleNamespace(get_sqltext=lambda db: sql)

    report = {'revision': REV, 'scope': 'Original composition/cache/mangler; '
              'synthetic leaf compiler; no GenroPy model or adapter execution',
              'reuse': {}, 'postgres': []}

    def db():
        return SimpleNamespace(currentEnv={})

    shared = db()
    q1, q2, q3 = [Leaf(shared, value=n) for n in (1, 2, 3)]
    first = q1 + q2
    assigned = q1.mangler
    second = q1 + q3
    assert q1.mangler != assigned
    first_sql, first_params = first.test()
    second_sql, second_params = second.test()
    report['reuse']['shared_leaf_mutated'] = {
        'first_prefix': assigned, 'prefix_after_second_composition': q1.mangler,
        'first_sql': first_sql, 'first_params': first_params,
        'second_sql': second_sql, 'second_params': second_params}
    assert first.compiled is q1.compiled
    assert first.compiled.get_sqltext(shared) != first.sqltext
    report['reuse']['compound_compiled_is_first_leaf'] = True

    shared = db()
    cached = Leaf(shared, value=1)
    before = cached.sqltext
    other = Leaf(shared, value=2)
    compound = cached + other
    sql, params = compound.test()
    assert cached.sqltext == before and ':n ' in sql and params['n'] == 2
    report['reuse']['precompiled_left_binding_overwritten'] = {
        'sql': sql, 'params': params, 'expected': [1, 2]}

    # Collect cases before optionally running PostgreSQL. Each tuple carries
    # generated SQL + kwargs and an explicitly parenthesized reference SQL.
    cases = [('precompiled_left', sql, params,
              '(SELECT 1 AS x) UNION (SELECT 2 AS x)')]
    shared = db()
    left, right = Leaf(shared, value=1), Leaf(shared, value=2)
    left.sqltext, right.sqltext
    sql, params = (left + right).test()
    cases.append(('both_precompiled', sql, params,
                  '(SELECT 1 AS x) UNION (SELECT 2 AS x)'))
    cases += [('reuse_first', first_sql, first_params,
               '(SELECT 1 AS x) UNION (SELECT 2 AS x)'),
              ('reuse_second', second_sql, second_params,
               '(SELECT 1 AS x) UNION (SELECT 3 AS x)')]
    shared = db()
    a, b, c = [Leaf(shared, value=n) for n in (1, 2, 3)]
    original = a + b
    old_sql, old_params = original.test()
    later = a + c
    later.test()
    assert original.test() == (old_sql, old_params)
    sql, params = later.test()
    cases.append(('reuse_after_compilation', sql, params,
                  '(SELECT 1 AS x) UNION (SELECT 3 AS x)'))
    shared = db()
    leaf = Leaf(shared, value=7)
    for op in OPERATORS:
        sql, params = leaf._compound(leaf, op).test()
        cases.append((f'self_{op}', sql, params,
                      f'(SELECT 7 AS x) {op} (SELECT 7 AS x)'))

    source_sql = [
        'SELECT x FROM (VALUES (1),(2),(2)) AS d(x) WHERE x <= :n',
        'SELECT x FROM (VALUES (2),(3)) AS d(x) WHERE x <= :n',
        'SELECT x FROM (VALUES (2)) AS d(x) WHERE x <= :n',
    ]
    reference = [s.replace(':n', '100') for s in source_sql]
    for outer in OPERATORS:
        for inner in OPERATORS:
            for side in ('left', 'right'):
                shared = db()
                a, b, c = [Leaf(shared, s, 100) for s in source_sql]
                if side == 'left':
                    result = a._compound(b, inner)._compound(c, outer)
                    expected = f'(({reference[0]}) {inner} ({reference[1]})) {outer} ({reference[2]})'
                else:
                    result = a._compound(b._compound(c, inner), outer)
                    expected = f'({reference[0]}) {outer} (({reference[1]}) {inner} ({reference[2]}))'
                sql, params = result.test()
                cases.append((f'{side}_{inner}_{outer}', sql, params, expected))

    for outer in OPERATORS:
        shared = db()
        a, b, c, d = [Leaf(shared, value=n) for n in (1, 2, 2, 3)]
        result = (a + b)._compound(c + d, outer)
        sql, params = result.test()
        expected = f'((SELECT 1 AS x) UNION (SELECT 2 AS x)) {outer} ((SELECT 2 AS x) UNION (SELECT 3 AS x))'
        cases.append((f'both_compound_{outer}', sql, params, expected))

    for suffix in ('ORDER BY x', 'LIMIT 1', 'ORDER BY x LIMIT 1 OFFSET 1'):
        shared = db()
        a = Leaf(shared, source_sql[0] + ' ' + suffix, 100)
        b = Leaf(shared, source_sql[1], 100)
        sql, params = (a + b).test()
        expected = f'({reference[0]} {suffix}) UNION ({reference[1]})'
        cases.append((f'left_clause_{suffix}', sql, params, expected))

    for suffix in ('ORDER BY x LIMIT 1', 'ORDER BY x LIMIT 1 OFFSET 1'):
        shared = db()
        a = Leaf(shared, source_sql[0], 100)
        b = Leaf(shared, source_sql[1] + ' ' + suffix, 100)
        sql, params = (a + b).test()
        expected = f'({reference[0]}) UNION ({reference[1]} {suffix})'
        cases.append((f'right_clause_{suffix}', sql, params, expected))

    if args.postgres:
        env = dict(os.environ)
        password = env.get('GNR_TEST_PG_PASSWORD')
        if password:
            env['PGPASSWORD'] = password
        command = ['psql', '-X', '-qAt', '--no-password', '-v', 'ON_ERROR_STOP=1',
                   '-v', 'VERBOSITY=verbose',
                   '-h', env.get('GNR_TEST_PG_HOST', '127.0.0.1'),
                   '-p', env.get('GNR_TEST_PG_PORT', '5432'),
                   '-U', env.get('GNR_TEST_PG_USER', 'postgres'), '-d', 'postgres']

        def execute(sql, params):
            # Fixture SQL has only :name integer bindings. Server-side PREPARE
            # validates the real PostgreSQL syntax and parameter association.
            names = list(dict.fromkeys(re.findall(r':(\w+)', sql)))
            if names:
                assert all(type(params[n]) is int for n in names)
                sql = re.sub(r':(\w+)', lambda m: f'${names.index(m[1]) + 1}', sql)
                types = ','.join('integer' for _ in names)
                values = ','.join(str(params[n]) for n in names)
                body = (f'PREPARE audit({types}) AS '
                        f'SELECT COALESCE(json_agg(x ORDER BY x),\'[]\'::json) FROM ({sql}) AS audit_rows; '
                        f'EXECUTE audit({values});')
            else:
                body = f"SELECT COALESCE(json_agg(x ORDER BY x),'[]'::json) FROM ({sql}) AS audit_rows;"
            run = subprocess.run(command, input='BEGIN READ ONLY; ' + body + ' ROLLBACK;',
                                 text=True, capture_output=True, env=env)
            if run.returncode:
                return {'error': run.stderr.strip()}
            return {'rows': json.loads(run.stdout.strip())}

        for name, sql, params, expected in cases:
            actual = execute(sql, params)
            wanted = execute(expected, {})
            assert 'rows' in wanted, (name, wanted)
            report['postgres'].append({
                'case': name, 'sql': sql, 'params': params, 'actual': actual,
                'reference_sql': expected, 'expected': wanted['rows'],
                'matches': actual.get('rows') == wanted['rows']})

        failures = {item['case'] for item in report['postgres'] if not item['matches']}
        expected_failures = {'precompiled_left', 'both_precompiled',
                             'left_UNION_INTERSECT', 'left_UNION ALL_INTERSECT',
                             'left_EXCEPT_INTERSECT'}
        expected_failures.update('left_clause_' + s for s in
                                 ('ORDER BY x', 'LIMIT 1', 'ORDER BY x LIMIT 1 OFFSET 1'))
        expected_failures.update('right_clause_' + s for s in
                                 ('ORDER BY x LIMIT 1', 'ORDER BY x LIMIT 1 OFFSET 1'))
        assert failures == expected_failures, failures
        report['summary'] = dict(Counter(
            'different' if not item['matches'] else 'matching'
            for item in report['postgres']))
    else:
        report['summary'] = {'structural_checks': 'passed',
                             'postgres_cases_prepared': len(cases),
                             'postgres_executed': False}
    serialized = json.dumps(report, indent=2) + '\n'
    if args.output:
        args.output.write_text(serialized)
    print(json.dumps(report['summary']))


if __name__ == '__main__':
    main()
