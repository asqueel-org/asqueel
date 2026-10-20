"""Isolated replacement for historical project conftest, not product code.

Copy only into a disposable snapshot. Tests and model code stay unchanged.
Historical project fixtures target an existing personal PostgreSQL instance.
This fixture uses a private ephemeral server and the frozen reference CSVs.
It records omitted tables/columns; it is not the original data baseline.
"""
import csv
import json
import os
from pathlib import Path
from uuid import uuid4

import pytest
from testing.postgresql import Postgresql

from core.common import BaseGnrTest
from gnr.app.gnrapp import GnrApp
from gnr.core.gnrbag import Bag

TABLES = [
    ('invc', 'region'), ('invc', 'state'), ('invc', 'customer_type'),
    ('invc', 'vat_type'), ('invc', 'payment_type'), ('invc', 'postcode'),
    ('invc', 'product_type'), ('invc', 'product'), ('invc', 'customer'),
    ('invc', 'staff_role'), ('adm', 'user'), ('invc', 'staff'),
    ('invc', 'discount_tier'), ('invc', 'price_year'), ('invc', 'price_year_note'),
    ('invc', 'invoice'), ('invc', 'invoice_row'), ('invc', 'invoice_note'),
]


@pytest.fixture(scope='session')
def app():
    BaseGnrTest.setup_class()
    instance = None
    application = None
    try:
        # Never consult environment credentials or an existing server.
        # Postgresql owns a fresh data directory and chooses an unused port.
        instance = Postgresql()
        conf = instance.dsn()
        conf.pop('database', None)
        config = Bag()
        config.setItem('db', None, implementation='postgres',
                       dbname='formula_' + uuid4().hex, **conf)
        # custom_config exists in all inspected revisions; db_attrs does not.
        application = GnrApp('test_invoice', custom_config=config)
        db = application.db
        assert db.implementation == 'postgres'
        db.model.check(applyChanges=True)
        source = Path(os.environ['FORMULA_BASELINE_CSV'])
        manifest = []
        conn = db.adapter.connection()
        cursor = conn.cursor()
        for package, name in TABLES:
            path = source / (name + '.csv')
            try:
                table = db.table(package + '.' + name)
            except Exception as error:
                manifest.append({'table': package + '.' + name, 'omitted': str(error)})
                continue
            if not path.exists():
                manifest.append({'table': package + '.' + name, 'omitted': 'CSV absent'})
                continue
            with path.open() as stream:
                reader = csv.DictReader(stream)
                columns = [c for c in reader.fieldnames if c != 'pkey' and c in table.columns]
                rows = [{c: row[c] if row[c] != '' else None for c in columns} for row in reader]
                placeholders = ','.join('%%(%s)s' % c for c in columns)
                sql = 'INSERT INTO %s.%s_%s (%s) VALUES (%s)' % (
                    package, package, name, ','.join(columns), placeholders)
                cursor.executemany(sql, rows)
                manifest.append({'table': package + '.' + name, 'rows': len(rows),
                                 'omitted_columns': sorted(set(reader.fieldnames) - set(columns))})
        conn.commit()
        cursor.close()
        Path(os.environ['FORMULA_BASELINE_MANIFEST']).write_text(json.dumps(manifest, indent=2))
        yield application
    finally:
        if application is not None:
            application.db.closeConnection()
        if instance is not None:
            instance.stop()
        BaseGnrTest.teardown_class()


@pytest.fixture(scope='session')
def db(app):
    return app.db
