"""Native physical/star/Bag compilation census, with all database I/O forbidden."""
from collections import Counter
import json
import os
from pathlib import Path
from unittest.mock import patch

from asqueel import SqlDatabase
from asqueel.configuration import _owned_handler
from asqueel.drivers.psycopg import PsycopgDriver
from asqueel.drivers.sqlite import SqliteDriver
from examples.test_invoice_pg import source


def forbidden(*args, **kwargs):
    raise AssertionError('Compilation attempted database I/O')


def main():
    results = []
    with patch.dict(os.environ, {'INVC_STATE': 'NSW'}), \
         patch.object(PsycopgDriver, 'connect', forbidden), \
         patch.object(PsycopgDriver, 'execute', forbidden), \
         patch.object(SqliteDriver, 'connect', forbidden), \
         patch.object(SqliteDriver, 'execute', forbidden):
        for backend in ('postgresql', 'sqlite'):
            config = source()
            config.source['db'].attr['implementation'] = backend
            with SqlDatabase(model=config.render(mode='objects_tree'), config=_owned_handler(config)) as db:
                for name, table in db.model.tables.items():
                    columns = ','.join('$' + n for n in table.columns)
                    queries = [('physical', columns, {})]
                    queries += [(f'star_{bags}', '*', {'bagFields': bags}) for bags in (False, True)]
                    queries += [('bag:' + c.name, '$' + c.name, {}) for c in table.virtual_columns.values() if c.tag == 'bagItemColumn']
                    for label, columns, options in queries:
                        record = dict(backend=backend, table=name, query=label)
                        try:
                            query = db.table(name).query(columns, **options).compiled
                            record.update(status='compiled', columns=[c.name for c in query.columns], sql=query.sql, params=dict(query.params))
                        except Exception as error:
                            record.update(status='blocked', error=type(error).__name__, message=str(error))
                        results.append(record)
    out = Path(__file__).parents[1] / 'evidence/legacy-rewrite-phase4/native-census.json'
    out.write_text(json.dumps(results, indent=2) + '\n')
    print(dict(Counter((r['backend'], r['query'].split(':')[0], r['status']) for r in results)))


if __name__ == '__main__':
    main()
