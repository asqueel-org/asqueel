"""R1 SELECT evidence on the real legacy compiler and the hierarchical compiler.

Compile all 74 native models on both dialects without I/O; execute the focused
expression cases only on SQLite in memory. PostgreSQL timing is compile-only.
"""
import argparse
import json
from pathlib import Path
import re
import sys


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--benchmark', action='store_true')
    parser.add_argument('--output-directory', type=Path,
                        default=Path('docs/design/evidence/legacy-realignment-r1'))
    args = parser.parse_args()
    sys.path.insert(0, '/tmp/asqueel-formula-baseline/legacy/gnrpy')
    sys.path.append('/tmp/asqueel-formula-baseline/env/lib/python3.12/site-packages')
    from gnr.sql.gnrsql import GnrSqlDb
    from asqueel import SqlDatabase
    from asqueel.configuration import _owned_handler
    from examples.test_invoice_pg import source
    from scanner_corpus import CASES
    from compare_scanners import (models, compile_case, connect, populate,
                                  execute, deny, benchmark, encode)

    out = args.output_directory
    out.mkdir(parents=True, exist_ok=True)
    native, expression_results, benchmarks = [], [], []
    for dialect, legacy_dialect in [('sqlite', 'sqlite'), ('postgresql', 'postgres')]:
        legacy = GnrSqlDb(implementation=legacy_dialect, dbname='unused')
        legacy.model.load('tests/oracles/test_invoice_pg/source.xml')
        legacy.startup()
        legacy.adapter.connect = legacy.adapter.connection = deny
        config = source()
        config.source.get_node('db').attr['implementation'] = dialect
        with SqlDatabase(model=config.render(mode='objects_tree'), config=_owned_handler(config)) as db:
            db.driver.connect = deny
            for package in db.model.packages.values():
                for table in package.tables.values():
                    columns = ','.join('$' + name for name in table.columns)
                    options = dict(columns=columns, order_by=columns.split(',')[0], limit=3,
                                   excludeDraft=False, excludeLogicalDeleted=False, ignorePartition=True)
                    old = legacy.table(table.fullname).query(**options, addPkeyColumn=False).sqltext
                    new = db.table(table.fullname).query(**options).compiled

                    def normalize(sql):
                        return ' '.join(re.sub(r'\bAS t0\b', 'AS "t0"', sql).split())

                    native.append(dict(dialect=dialect, table=table.fullname,
                                       legacy_sql=old, hierarchical_sql=new.sql,
                                       same_sql=normalize(old) == normalize(new.sql),
                                       columns=[col.name for col in new.columns],
                                       expected_columns=list(table.columns)))

        legacy, previous, tree = dbs = models(dialect, include_tree=True)
        selected = {
            'physical', 'sqlparams_year', 'case', 'coalesce', 'cast', 'alias_lower',
            'expression_no_alias', 'duplicate_alias', 'literal_comma', 'literal_as',
            'literal_field', 'literal_dollars', 'literal_quotes', 'literal_semicolon',
            'bound_quote', 'repeated_bind', 'prefix_params', 'null_binding',
            'numeric_binding', 'quoted_alias', 'escaped_alias', 'cast_colon',
            'adjacent_field_operator', 'comment_known_field',
        }
        try:
            for case in CASES:
                if case['name'] not in selected or dialect not in case['dialects']:
                    continue
                record = dict(name=case['name'], dialect=dialect, engines={})
                for engine, database in [('legacy', legacy), ('tree', tree)]:
                    compiled = compile_case(database, engine, case)
                    record['engines'][engine] = compiled
                    if dialect == 'sqlite':
                        connection = connect(dialect, engine)
                        try:
                            populate(connection, dialect)
                            record['engines'][engine].update(execute(connection, dialect, engine, compiled))
                        finally:
                            connection.close()
                if dialect == 'sqlite':
                    old, new = record['engines']['legacy'], record['engines']['tree']
                    record['same_rows_columns'] = old['rows'] == new['rows'] and old['columns'] == new['columns']
                expression_results.append(record)
            if args.benchmark:
                benchmarks.extend(benchmark(dbs, dialect, dialect == 'sqlite'))
        finally:
            previous.close()
            tree.close()
    (out/'native-selects.json').write_text(json.dumps(native, ensure_ascii=False, indent=2) + '\n')
    (out/'select-cases.json').write_text(json.dumps(expression_results, ensure_ascii=False,
                                                 default=encode, indent=2) + '\n')
    if args.benchmark:
        (out/'benchmark.json').write_text(json.dumps(benchmarks, indent=2) + '\n')
    summary = dict(native_queries=len(native),
                   native_mismatches=[f"{r['dialect']}:{r['table']}" for r in native
                                      if not r['same_sql'] or r['columns'] != r['expected_columns']],
                   expression_cases=len(expression_results),
                   sqlite_executed=sum(r['dialect'] == 'sqlite' for r in expression_results),
                   sqlite_mismatches=[r['name'] for r in expression_results
                                      if r.get('same_rows_columns') is False],
                   benchmark_workloads=len(benchmarks))
    (out/'select-summary.json').write_text(json.dumps(summary, indent=2) + '\n')
    print(json.dumps(summary))
    assert not summary['native_mismatches'] and not summary['sqlite_mismatches']


if __name__ == '__main__':
    main()
