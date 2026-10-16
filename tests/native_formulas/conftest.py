"""Native package model, frozen legacy rows, private databases on both backends.

DDL here provisions only the tables used by the formula corpus. The tests
exercise the actual compiler/dialect/driver, not migration or write hooks.
"""
import csv
from datetime import date
from pathlib import Path
from uuid import uuid4

import pytest
import psycopg
from psycopg import sql
from psycopg.conninfo import make_conninfo

from asqueel import build_database
from examples.test_invoice_pg import source
from tests.native_support import postgres_dsn

TABLES = ('region', 'state', 'vat_type', 'customer', 'product',
          'invoice', 'invoice_row', 'invoice_note')
SQL_TYPES = {'N': 'NUMERIC', 'R': 'REAL', 'I': 'INTEGER', 'L': 'BIGINT',
             'B': 'BOOLEAN', 'D': 'DATE', 'DH': 'TIMESTAMP',
             'DHZ': 'TIMESTAMP WITH TIME ZONE', 'H': 'TIME'}


def database(backend, tmp_path, monkeypatch, *, dsn=None, state=None):
    # Generic legacy formula tests run without a current partition. Dedicated
    # partition fixtures resolve their value while rendering the native source.
    if state is None:
        monkeypatch.delenv('INVC_STATE', raising=False)
    else:
        monkeypatch.setenv('INVC_STATE', state)
    config = source()
    root = config.source['db']
    root.attr['implementation'] = backend
    root.connection(implementation=backend, **(
        {'dsn': dsn} if backend == 'postgresql'
        else {'database': str(tmp_path / 'formulas.db')}))
    # Preserve physical schema names too: authored SQL in the legacy model
    # refers directly to invc.invc_invoice_note. Isolation is per database.
    db = build_database(config)
    schemas = sorted({t.sqlschema for t in db.model.tables.values()})
    try:
        if backend == 'postgresql':
            for schema in schemas:
                db.execute(f'CREATE SCHEMA "{schema}"')
        for name in TABLES:
            table = db.model.table('invc.' + name)
            physical = [c for c in table.columns.values()]
            columns = ', '.join(f'"{c.sqlname}" {SQL_TYPES.get(c.dtype, "TEXT")}'
                                for c in physical)
            target = f'"{table.sqlschema}"."{table.sqlname}"'
            db.execute(f'CREATE TABLE {target} ({columns})')
            with (Path(__file__).parent / 'data' / (name + '.csv')).open() as stream:
                reader = csv.DictReader(stream)
                names = [n for n in reader.fieldnames if n != 'pkey']
                fields = ', '.join(f'"{table.columns[n].sqlname}"' for n in names)
                values = ', '.join(':' + n for n in names)
                for row in reader:
                    params = {n: None if row[n] == '' else row[n] for n in names}
                    for n in names:
                        if table.columns[n].dtype == 'B' and params[n] is not None:
                            params[n] = params[n].lower() in ('true', 't', '1')
                    db.execute(f'INSERT INTO {target} ({fields}) VALUES ({values})', params)
        db.commit()
        with db.tempEnv(workdate=date(2026, 2, 1)):
            yield db
    finally:
        db.rollback()
        db.close()


def pg_database(tmp_path_factory, *, state=None):
    with pytest.MonkeyPatch.context() as patch, \
            psycopg.connect(postgres_dsn(), autocommit=True) as admin:
        name = 'test_asqueel_formulas_' + uuid4().hex
        admin.execute(sql.SQL('CREATE DATABASE {}').format(sql.Identifier(name)))
        try:
            yield from database('postgresql', tmp_path_factory.mktemp('formula_pg'), patch,
                                dsn=make_conninfo(postgres_dsn(), dbname=name), state=state)
        finally:
            admin.execute(sql.SQL('DROP DATABASE {}').format(sql.Identifier(name)))


@pytest.fixture(scope='module')
def db_pg(tmp_path_factory):
    yield from pg_database(tmp_path_factory)


@pytest.fixture(scope='module')
def partition_pg(tmp_path_factory):
    yield from pg_database(tmp_path_factory, state='NSW')


@pytest.fixture(scope='module')
def partition_sqlite(tmp_path_factory):
    with pytest.MonkeyPatch.context() as patch:
        yield from database('sqlite', tmp_path_factory.mktemp('partition_sqlite'), patch, state='NSW')


@pytest.fixture(scope='module')
def db_sqlite(tmp_path_factory):
    with pytest.MonkeyPatch.context() as patch:
        yield from database('sqlite', tmp_path_factory.mktemp('formula_sqlite'), patch)
