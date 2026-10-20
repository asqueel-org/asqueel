"""R3 preparation oracle from original execute and adapter methods, no I/O.

PostgreSQL's psycopg3 collection expansion is tested separately against its
original method; final named placeholders come from the psycopg2 adapter regex.
The same composition is captured through the original execute method.
"""
import argparse
from copy import deepcopy
from datetime import date, datetime
from decimal import Decimal
import json
from pathlib import Path
import sys
from types import SimpleNamespace


CASES = [
    ('ordinary', 'SELECT :value AS value', {'value': 3}),
    ('repeat', 'SELECT :x+:x AS value', {'x': 2}),
    ('prefix', 'SELECT :x+:xx AS value', {'x': 2, 'xx': 3}),
    ('unicode', 'SELECT :soglia_è AS value', {'soglia_è': Decimal('12.50')}),
    ('missing', 'SELECT :missing AS value', {}),
    ('unused', 'SELECT :x AS value', {'x': 2, 'unused': 3}),
    ('null', 'SELECT :x AS value', {'x': None}),
    ('bytes', 'SELECT :x AS value', {'x': b'caf\xc3\xa8'}),
    ('date', 'SELECT :x AS value', {'x': date(2026, 10, 14)}),
    ('decimal', 'SELECT :x AS value', {'x': Decimal('1.25')}),
    ('escaped_field', 'SELECT :x AS value', {'x': r'\$id'}),
    ('escaped_relation', 'SELECT :x AS value', {'x': r'\@customer_id.name'}),
    ('escaped_bytes', 'SELECT :x AS value', {'x': b'\\$id'}),
    ('escaped_sql', r"SELECT '\:value' AS value", {}),
    ('percent', "SELECT '10%%' AS value", {}),
    ('percent_bound', "SELECT :x AS value, 8 %% 3 AS remainder", {'x': '10%'}),
    ('environment', 'SELECT :env_workdate AS value', {}),
    ('environment_missing', 'SELECT :env_absent AS value', {}),
    ('environment_override', 'SELECT :env_workdate AS value', {'env_workdate': date(2020, 1, 1)}),
    ('cast', 'SELECT :x::numeric AS value', {'x': 3}),
    ('cast_no_bind', 'SELECT t0.value::numeric AS value FROM t0', {}),
    ('regexp', 'SELECT value REGEXP :pattern AS value FROM t0', {'pattern': '^a'}),
    ('ilike', 'SELECT value ILIKE :pattern AS value FROM t0', {'pattern': 'a%'}),
    ('ilike_lower', 'SELECT value ilike :pattern AS value FROM t0', {'pattern': 'a%'}),
    ('sqlite_regex', 'SELECT value ~* :pattern AS value FROM t0', {'pattern': '^a'}),
    ('boolean', 'SELECT (t0.flag IS NOT TRUE) AS value FROM t0', {}),
    ('false', 'SELECT t0.flag IS FALSE AS value FROM t0', {}),
    ('literal_operator', "SELECT 'ILIKE REGEXP' AS value", {}),
    ('literal_binding', "SELECT ':x' AS value", {'x': 'text'}),
    ('list', 'SELECT "t0"."id" IN :ids AS value FROM t0', {'ids': [1, 2]}),
    ('tuple', 'SELECT "t0"."id" IN :ids AS value FROM t0', {'ids': (1, 2)}),
    ('set', 'SELECT "t0"."id" IN :ids AS value FROM t0', {'ids': {1, 2}}),
    ('one', 'SELECT "t0"."id" IN :ids AS value FROM t0', {'ids': [1]}),
    ('empty', 'SELECT "t0"."id" IN :ids AS value FROM t0', {'ids': []}),
    ('empty_not', 'SELECT "t0"."id" NOT IN :ids AS value FROM t0', {'ids': []}),
    ('null_member', 'SELECT "t0"."id" IN :ids AS value FROM t0', {'ids': [1, None]}),
    ('not_in', 'SELECT "t0"."id" NOT IN :ids AS value FROM t0', {'ids': [1, 2]}),
    ('collection_repeat', 'SELECT 1 IN :ids OR 2 IN :ids AS value', {'ids': [1, 2]}),
    ('collection_prefix', 'SELECT 1 IN :ids AND 3=:ids0 AS value', {'ids': [1, 2], 'ids0': 3}),
    ('collection_pg_collision', 'SELECT 1 IN :ids AND 3=:ids_0 AS value', {'ids': [1, 2], 'ids_0': 3}),
    ('collection_unused', 'SELECT 1 AS value', {'ids': [1, 2]}),
    ('collection_non_in', 'SELECT :ids AS value', {'ids': [1, 2]}),
    ('collection_shared_scalar', 'SELECT 1 IN :ids AND :ids IS NOT NULL AS value', {'ids': [1, 2]}),
]


def encode(value):
    if isinstance(value, dict):
        return {key: encode(item) for key, item in value.items()}
    if isinstance(value, list):
        return [encode(item) for item in value]
    if isinstance(value, (tuple, set, bytes, date, datetime, Decimal)):
        if isinstance(value, bytes):
            return {'type': 'bytes', 'value': value.hex()}
        if isinstance(value, (tuple, set)):
            return {'type': type(value).__name__, 'value': [encode(v) for v in value]}
        return {'type': type(value).__name__, 'value': str(value)}
    return value


def capture(function):
    try:
        return {'value': encode(function())}
    except Exception as error:
        return {'error': type(error).__name__}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--snapshot', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--write-oracle', type=Path)
    args = parser.parse_args()
    sys.path.insert(0, str(args.snapshot / 'gnrpy'))
    sys.path.append('/tmp/asqueel-formula-baseline/env/lib/python3.12/site-packages')
    from gnr.sql.gnrsql import GnrSqlDb
    from gnr.sql.adapters.gnrpostgres import RE_SQL_PARAMS
    from asqueel.drivers.psycopg import PsycopgDriver
    from asqueel.drivers.sqlite import SqliteDriver
    from asqueel.drivers.sql import postgres_collections

    pg3 = GnrSqlDb(implementation='postgres3', dbname='unused').adapter
    snapshot = {'workdate': date(2026, 10, 14)}
    records = []
    for dialect, driver in [('postgresql', PsycopgDriver()), ('sqlite', SqliteDriver())]:
        legacy = GnrSqlDb(implementation='postgres' if dialect == 'postgresql' else 'sqlite', dbname='unused')
        legacy.currentEnv.update(snapshot)
        def denied(*args, **kwargs):
            raise AssertionError('Preparation opened a connection')
        legacy.adapter.connect = legacy.adapter.connection = denied
        if dialect == 'postgresql':
            # Actual legacy psycopg3 expansion + actual psycopg2 named protocol.
            def prepare(sql, params):
                sql = pg3.adaptTupleListSet(sql, params)
                return RE_SQL_PARAMS.sub(r'%(\1)s\2', sql).replace('REGEXP', '~*'), params
            legacy.adapter.prepareSqlText = prepare
        for name, sql, params in CASES:
            def old():
                cursor = SimpleNamespace(connection=SimpleNamespace(committed=True))
                def execute(text, values):
                    cursor.sql, cursor.params = text.split('\n', 1)[1], dict(values)
                cursor.execute = execute
                legacy.execute(sql, deepcopy(params), cursor=cursor)
                return {'sql': cursor.sql, 'params': cursor.params}
            def new():
                result = driver.prepare_sql(sql, deepcopy(params), snapshot)
                return {'sql': result.sql, 'params': dict(result.params)}
            records.append(dict(kind='prepared', name=name, dialect=dialect, sql=sql,
                                params=encode(params), snapshot=encode(snapshot),
                                legacy=capture(old), current=capture(new)))
            if dialect == 'postgresql' and name.startswith(('collection', 'list', 'tuple', 'set', 'one', 'empty', 'null_member', 'not_in')):
                def collection(method):
                    values = deepcopy(params)
                    return {'sql': method(sql, values), 'params': values}
                records.append(dict(kind='pg3_collection', name=name, sql=sql, params=encode(params),
                                    legacy=capture(lambda: collection(pg3.adaptTupleListSet)),
                                    current=capture(lambda: collection(postgres_collections))))
    mismatches = [r for r in records if r['legacy'] != r['current']]
    report = dict(snapshot=str(args.snapshot), checks=len(records), mismatches=mismatches, records=records)
    args.output.write_text(json.dumps(report, indent=2, ensure_ascii=False)+'\n')
    if args.write_oracle:
        assert args.snapshot.name == 'legacy' and not mismatches
        args.write_oracle.write_text(json.dumps(dict(reference='fa35e5ad', records=[
            {k:v for k,v in record.items() if k != 'current'} for record in records]), indent=2, ensure_ascii=False)+'\n')
    print(json.dumps(dict(snapshot=args.snapshot.name, checks=len(records), mismatches=len(mismatches))))
    if mismatches:
        print(json.dumps(mismatches, indent=2, ensure_ascii=False))
    if args.snapshot.name == 'legacy' and mismatches:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
