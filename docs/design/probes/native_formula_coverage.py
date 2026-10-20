"""Compile each native virtual column without I/O; not a result-equivalence test.

Run from the Asqueel repository with PYTHONPATH=src:. and --output FILE.
"""
import argparse
from collections import Counter
import json
import os
from pathlib import Path
from unittest.mock import patch

from asqueel import build_database
from asqueel.drivers.psycopg import PsycopgDriver
from asqueel.drivers.sqlite import SqliteDriver
from examples.test_invoice_pg import source


def forbidden(*args, **kwargs):
    raise AssertionError('Compilation attempted database I/O')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    results = []
    with patch.dict(os.environ, {'INVC_STATE': 'NSW'}), \
            patch.object(PsycopgDriver, 'connect', forbidden), \
            patch.object(PsycopgDriver, 'execute', forbidden), \
            patch.object(SqliteDriver, 'connect', forbidden), \
            patch.object(SqliteDriver, 'execute', forbidden), \
            build_database(source()) as db:
        for table in db.model.tables.values():
            for column in table.columns.values():
                if not column.is_virtual:
                    continue
                record = {'table': table.key, 'column': column.name, 'kind': column.kind}
                attrs = column.attributes
                if column.kind == 'formulaColumn':
                    record['formula_form'] = (
                        'select' if attrs.get('select') else
                        'exists' if attrs.get('exists') else
                        'method' if attrs.get('sql_formula') is True else 'sql')
                record['forms'] = sorted(k for k in attrs if k in (
                    'sql_formula', 'expression', 'select', 'exists', 'parameters', 'subqueries',
                    'handler', 'query', 'mode', 'py_method', 'method', 'static')
                    or k.startswith(('var_', 'select_')))
                try:
                    compiled = db.table(table.key).query(
                        columns='$' + column.name, excludeDraft=False,
                        excludeLogicalDeleted=False, ignorePartition=True).compiled
                    record.update(status='compiled', sql=compiled.sql,
                                  parameter_names=sorted(compiled.params))
                except Exception as error:
                    record.update(status='blocked', error=type(error).__name__, message=str(error))
                results.append(record)
    counts = Counter((r['kind'], r['status']) for r in results)
    summary = [{'kind': k, 'status': s, 'count': n} for (k, s), n in sorted(counts.items())]
    args.output.write_text(json.dumps({'summary': summary, 'columns': results}, indent=2) + '\n')
    print(json.dumps(summary, indent=2))


if __name__ == '__main__':
    main()
