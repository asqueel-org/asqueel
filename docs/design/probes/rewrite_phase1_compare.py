"""Freeze legacy SELECT contracts and observe the two existing Asqueel paths.

Never edits a compiler. SQL compilation cannot connect. SQLite execution uses
an in-memory database and ten existing, frozen CSV tables; the original
test runner separately exercises PostgreSQL with original fixtures.
"""
import argparse
from collections import Counter
from copy import deepcopy
import csv
from datetime import date, datetime
from decimal import Decimal
import hashlib
import json
from pathlib import Path
import re
import signal
import sqlite3
import sys
import time

from rewrite_phase1_cases import CASES, COMMON

ROOT = Path(__file__).resolve().parents[3]
SNAPSHOTS = Path('/tmp/asqueel-formula-baseline')
CSV_TABLES = ('region', 'state', 'vat_type', 'customer', 'product',
              'invoice', 'invoice_row', 'invoice_note', 'price_year', 'price_year_note')


def encode(value):
    if isinstance(value, (date, datetime, Decimal)):
        return {'type': type(value).__name__, 'value': str(value)}
    if isinstance(value, bytes):
        return {'type': 'bytes', 'value': value.hex()}
    raise TypeError(type(value).__name__)


def normalized(sql):
    # Only layout and the already documented base-table alias quoting.
    return ' '.join(re.sub(r'\bAS (t\d+(?:_t\d+)*)\b', r'AS "\1"', sql).split())


def deny(*args, **kwargs):
    raise AssertionError('Compilation attempted database I/O')


def compile_timeout(*args):
    raise TimeoutError('Probe compilation exceeded 10 seconds')


def databases(dialect, *, legacy_only=False):
    from gnr.sql.gnrsql import GnrSqlDb
    legacy = GnrSqlDb(implementation='postgres' if dialect == 'postgresql' else 'sqlite',
                      dbname='unused')
    legacy.model.load(str(ROOT/'tests/oracles/test_invoice_pg/source.xml'))
    legacy.startup()
    legacy.currentEnv['workdate'] = date(2026, 2, 1)
    legacy.adapter.connect = legacy.adapter.connection = deny
    result = {'legacy': legacy}
    if not legacy_only:
        from asqueel import SqlDatabase
        from asqueel.configuration import _owned_handler
        from examples.test_invoice_pg import source
        for engine in ('current', 'tree'):
            config = source()
            config.source.get_node('db').attr['implementation'] = dialect
            database = (config.render() if engine == 'current' else
                        SqlDatabase(model=config.render(mode='objects_tree'), config=_owned_handler(config)))
            database.currentEnv['workdate'] = date(2026, 2, 1)
            database.driver.connect = database.driver.execute = deny
            database.execute = deny
            result[engine] = database
    return result


def compile_case(database, engine, case):
    from compare_scanners import Capture
    params = deepcopy(case['params'])
    options = deepcopy(case['options'])
    if engine == 'legacy' and not case['defaults']:
        options['addPkeyColumn'] = False
    query = database.table(case['table']).query(columns=case['columns'], sqlparams=params, **options)
    if engine == 'legacy':
        compiled = query.compileQuery(count=case['count'])
        raw_sql = compiled.get_sqltext(database)
        again = query.compileQuery(count=case['count']).get_sqltext(database)
        capture = Capture()
        # The real legacy preparation runs on a recording cursor, never on a DB.
        database.execute(raw_sql, query.sqlparams, cursor=capture)
        sql = capture.sql
        # execute() adds an audit line; it is not emitted by the compiler.
        audit_omitted = sql.startswith('-- ') and '\n' in sql
        if audit_omitted:
            sql = sql.split('\n', 1)[1]
        return dict(sql=sql, params=capture.params, raw_sql=raw_sql,
                    execution_audit_omitted=audit_omitted,
                    clauses={key: getattr(compiled, key, None) for key in (
                        'columns', 'joins', 'where', 'group_by', 'having', 'order_by',
                        'distinct', 'relationDict', 'aliasDict', 'explodingColumns')},
                    stable=raw_sql == again, input_after=params)
    compiled = query._compile(database.compiler.count) if case['count'] else query.compiled
    again = query._compile(database.compiler.count) if case['count'] else query.compiled
    return dict(sql=compiled.sql, params=dict(compiled.params),
                result_columns=[c.name for c in compiled.columns],
                stable=compiled.sql == again.sql and dict(compiled.params) == dict(again.params),
                input_after=params)


def native_cases(database):
    result = []
    for pkg in database.model.obj.values():
        for table in pkg.tables.values():
            if table.fullname == 'sys.locked_record':
                continue
            columns = ','.join('$'+name for name in table.columns.keys())
            result.append(dict(name='physical:'+table.fullname, table=table.fullname,
                               columns=columns, params={}, count=False, defaults=False,
                               options=dict(COMMON, order_by=columns.split(',')[0], limit=3),
                               origin='native source: all declared physical columns'))
            for node in table.relations:
                if not node.label.startswith('@'):
                    continue
                joiner = node.attr['joiner']
                # The four replaced joinColumns belong to the documented GEP divergence.
                if table.fullname+'.'+node.label in {
                    'invc.invoice.@discount_tier_id', 'invc.discount_tier.@invoices_in_tier',
                    'invc.invoice_row.@customer_id', 'invc.customer.@invoice_rows_by_customer',
                }:
                    continue
                target = database.model.table(joiner['one_relation'] if joiner['mode'] == 'O'
                                              else joiner['many_relation'])
                field = next(iter(target.columns.keys()))
                result.append(dict(name='relation:'+table.fullname+'.'+node.label,
                    table=table.fullname, columns=f'${table.pkey},{node.label}.{field}',
                    params={}, count=False, defaults=False,
                    options=dict(COMMON, order_by='$'+table.pkey, limit=3),
                    origin='native declared relation: '+table.fullname+'.'+node.label,
                    joiner=dict(joiner)))
    return result


def populate(database):
    from gnr.sql.adapters.gnrsqlite import GnrSqliteConnection
    connection = sqlite3.connect(':memory:', factory=GnrSqliteConnection)
    connection.execute("ATTACH DATABASE ':memory:' AS invc")
    types = {'N': 'NUMERIC', 'R': 'REAL', 'I': 'INTEGER', 'L': 'INTEGER', 'B': 'BOOLEAN'}
    for name in CSV_TABLES:
        table = database.model.table('invc.'+name)
        columns = ','.join(f'{column.sqlname} {types.get(column.dtype, "TEXT")}'
                          for column in table.columns.values())
        connection.execute(f'CREATE TABLE {table.sqlfullname} ({columns})')
        csv_path = ROOT/'tests/native_formulas/data'/f'{name}.csv'
        if not csv_path.exists():
            csv_path = SNAPSHOTS/'legacy/projects/test_invoice/data/export'/f'{name}.csv'
        with csv_path.open() as stream:
            reader = csv.DictReader(stream)
            names = [n for n in reader.fieldnames if n != 'pkey']
            fields = ','.join(table.column(n).sqlname for n in names)
            placeholders = ','.join('?' for n in names)
            for row in reader:
                values = [None if row[n] == '' else row[n] for n in names]
                values = [v.lower() in ('true', 't', '1') if v is not None
                          and table.column(n).dtype == 'B' else v for n, v in zip(names, values)]
                connection.execute(f'INSERT INTO {table.sqlfullname} ({fields}) VALUES ({placeholders})', values)
    return connection


def execute(connection, result, *, count=False):
    deadline = time.monotonic() + 5
    connection.set_progress_handler(lambda: int(time.monotonic() > deadline), 10000)
    cursor = connection.cursor()
    cursor.execute(result['sql'], result['params'])
    rows = [list(row) for row in cursor.fetchall()]
    names = [c[0] for c in cursor.description]
    output = {'rows': rows, 'columns': names}
    if count:
        # Exactly the scalar extraction in legacy SqlQuery.count, without fetch aggregation.
        output['count'] = rows[0][0] if len(rows) == 1 and names[0] in ('gnr_row_count', 'count') else len(rows)
    return output


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-directory', type=Path, required=True)
    parser.add_argument('--label', default='legacy')
    parser.add_argument('--legacy-only', action='store_true')
    parser.add_argument('--execute-sqlite', action='store_true')
    parser.add_argument('--focused-only', action='store_true')
    parser.add_argument('--freeze-contracts', action='store_true')
    args = parser.parse_args()
    signal.signal(signal.SIGALRM, compile_timeout)
    sys.path.insert(0, str(SNAPSHOTS/args.label/'gnrpy'))
    sys.path.append(str(SNAPSHOTS/'env/lib/python3.12/site-packages'))
    sys.path.insert(0, str(ROOT))
    out = args.output_directory.resolve()
    out.mkdir(parents=True, exist_ok=True)
    observations = []
    for dialect in ('sqlite', 'postgresql'):
        dbs = databases(dialect, legacy_only=args.legacy_only)
        connection = populate(dbs['legacy']) if dialect == 'sqlite' and args.execute_sqlite else None
        try:
            for case in [*CASES, *([] if args.focused_only else native_cases(dbs['legacy']))]:
                entry = dict(dialect=dialect, case=case, engines={})
                for engine, database in dbs.items():
                    try:
                        signal.alarm(10)
                        result = compile_case(database, engine, case)
                        entry['engines'][engine] = dict(compile='ok', **result)
                    except Exception as exc:
                        entry['engines'][engine] = dict(compile='error', error_type=type(exc).__name__, error=str(exc))
                        continue
                    finally:
                        signal.alarm(0)
                    if connection is not None and case in CASES:
                        try:
                            result = execute(connection, result, count=case['count'])
                            entry['engines'][engine].update(execute='ok', **result)
                        except Exception as exc:
                            entry['engines'][engine].update(execute='error', execution_error=type(exc).__name__+': '+str(exc))
                legacy = entry['engines']['legacy']
                for engine in ('current', 'tree'):
                    if engine not in entry['engines']:
                        continue
                    other = entry['engines'][engine]
                    comparison = {}
                    if legacy['compile'] == other['compile'] == 'ok':
                        comparison['sql'] = normalized(legacy['sql']) == normalized(other['sql'])
                        # jc_kwargs is legacy execute bookkeeping, not an SQL binding.
                        comparison['params'] = {k: v for k, v in legacy['params'].items() if k != 'jc_kwargs'} == other['params']
                    if legacy.get('execute') == other.get('execute') == 'ok':
                        for key in ('rows', 'columns'):
                            comparison[key] = legacy[key] == other[key]
                        if case['count']:
                            comparison['count'] = legacy['count'] == other['count']
                    entry[engine+'_comparison'] = comparison
                observations.append(entry)
        finally:
            if connection:
                connection.close()
            for engine, database in dbs.items():
                if engine != 'legacy':
                    database.close()
    summary = {}
    for engine in observations[0]['engines']:
        values = [o['engines'][engine] for o in observations]
        summary[engine] = {'compile': dict(Counter(v['compile'] for v in values)),
                           'execute': dict(Counter(v.get('execute', 'not_run') for v in values)),
                           'unstable': sum(v.get('stable') is False for v in values)}
    artifact = dict(label=args.label, observations=observations, summary=summary,
                    source_sha256=hashlib.sha256((ROOT/'tests/oracles/test_invoice_pg/source.xml').read_bytes()).hexdigest())
    (out/(args.label+'-comparison.json')).write_text(json.dumps(artifact, indent=2, default=encode)+'\n')
    if args.freeze_contracts:
        if args.label != 'legacy':
            raise ValueError('Only the normative legacy snapshot can produce the oracle')
        focus = [entry for entry in observations if ':' not in entry['case']['name']]
        if any(entry['engines']['legacy']['compile'] != 'ok' for entry in focus):
            raise ValueError('A failed legacy compilation cannot become an expected SQL contract')
        oracle = dict(reference='fa35e5adfa6ad1b269f3a22a9b12c4c1ee6513ea',
                      source_sha256=artifact['source_sha256'],
                      cases=[dict(dialect=e['dialect'], request=e['case'],
                                  expected=e['engines']['legacy']) for e in focus])
        (ROOT/'tests/oracles/legacy_rewrite_phase1.json').write_text(
            json.dumps(oracle, indent=2, default=encode)+'\n')
    print(json.dumps(summary))


if __name__ == '__main__':
    main()
