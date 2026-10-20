"""Census of native read markers and star expansion, with database I/O forbidden."""
import argparse
from collections import Counter
import json
import os
from unittest.mock import patch
from pathlib import Path

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
            patch.object(SqliteDriver, 'execute', forbidden):
        for backend in ['postgresql', 'sqlite']:
            config = source()
            config.source['db'].attr['implementation'] = backend
            with build_database(config) as db:
                for key, table in db.model.tables.items():
                    name = next(n for n, c in table.columns.items() if not c.is_virtual)
                    query = db.table(key).query('$"' + name + '"').compiled
                    record = dict(backend=backend, table=key, draft=table.policies.draft_field,
                                  deleted=table.policies.logical_deletion_field,
                                  partition=[dict(o.attributes) for o in table.options.values()
                                             if o.name == 'partition' and o.enabled],
                                  explicit_sql=query.sql, parameters=dict(query.params), stars=[])
                    for bags in [False, True]:
                        star = dict(bagFields=bags)
                        try:
                            query = db.table(key).query(bagFields=bags).compiled
                            star.update(status='compiled', columns=[c.name for c in query.columns])
                        except Exception as error:
                            star.update(status='blocked', error=type(error).__name__, message=str(error))
                        record['stars'].append(star)
                    results.append(record)
    args.output.write_text(json.dumps(results, indent=2) + '\n')
    print(dict(Counter((r['backend'], s['bagFields'], s['status']) for r in results for s in r['stars'])))


if __name__ == '__main__':
    main()
