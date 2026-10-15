"""Read-only SELECTs comparing psycopg2, Cursor and a proposed ClientCursor.

This probe does not change Asqueel's driver or connection configuration.
"""
from datetime import date
from decimal import Decimal
import json
from pathlib import Path
import sys

from compare_scanners import Capture, connect


def main():
    root = Path('/tmp/asqueel-formula-baseline')
    sys.path.insert(0, str(root / 'legacy/gnrpy'))
    sys.path.append(str(root / 'env/lib/python3.12/site-packages'))
    import psycopg
    from gnr.sql.gnrsql import GnrSqlDb
    from asqueel.drivers.psycopg import PsycopgDriver

    legacy = GnrSqlDb(implementation='postgres', dbname='unused')
    driver = PsycopgDriver()
    cases = [
        ('quoted_numeric_parameter', "SELECT ':id' AS value, :id::integer AS bound", {'id': 1}),
        ('ordinary_numeric_parameter', 'SELECT :id::integer AS value', {'id': 1}),
        ('escaped_literal', r"SELECT '\:id' AS value, :id::integer AS bound", {'id': 1}),
        ('ordinary_text_parameter', 'SELECT :text::text AS value', {'text': "O'Reilly"}),
        ('percent_escape', "SELECT '10%%' AS value, :id::integer AS bound", {'id': 1}),
        ('typed_parameters', 'SELECT :d::date, :amount::numeric, :flag::boolean',
         {'d': date(2026, 1, 2), 'amount': Decimal('12.50'), 'flag': True}),
        ('null_parameter', 'SELECT :value::integer', {'value': None}),
        ('repeated_parameter', 'SELECT :id::integer + :id::integer', {'id': 1}),
    ]
    results = []
    oldconn = connect('postgresql', 'legacy')
    newconn = connect('postgresql', 'tree')
    try:
        for name, sql, params in cases:
            capture = Capture()
            legacy.execute(sql, dict(params), cursor=capture)
            prepared = driver.prepare_sql(sql, params, {})
            entry = {'name': name, 'source_sql': sql, 'params': params,
                     'prepared_sql': prepared.sql, 'engines': {}}
            for engine, cursor, query, arguments in (
                ('psycopg2', oldconn.cursor(), capture.sql, capture.params),
                ('psycopg3_server', newconn.cursor(), prepared.sql, dict(prepared.params)),
                ('psycopg3_client_proposal', psycopg.ClientCursor(newconn), prepared.sql, dict(prepared.params)),
            ):
                with cursor:
                    cursor.execute(query, arguments)
                    rows = cursor.fetchall()
                    entry['engines'][engine] = {'rows': rows,
                                               'types': [[type(v).__name__ for v in row] for row in rows]}
            results.append(entry)
    finally:
        oldconn.close()
        newconn.close()
    assert all(r['engines']['psycopg2'] == r['engines']['psycopg3_client_proposal'] for r in results)
    assert results[0]['engines']['psycopg2']['rows'] == [('1', 1)]
    assert results[0]['engines']['psycopg3_server']['rows'] == [('$1', 1)]
    out = Path('docs/design/evidence/legacy-renderer-r4/postgres-binding.json')
    out.write_text(json.dumps(results, ensure_ascii=False, indent=2, default=str) + '\n')
    print('8 SELECT cases: proposed ClientCursor matches psycopg2; quoted parameter differs with server binding')


if __name__ == '__main__':
    main()
