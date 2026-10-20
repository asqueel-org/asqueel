"""Run with the frozen legacy interpreter; no SQL, sockets or Asqueel imports."""
from pathlib import Path
import socket

import pytest
from gnr.sql.gnrsql import GnrSqlDb
from gnr.sql.gnrsqltable import SqlTable


@pytest.fixture
def db(monkeypatch):
    def denied(*args, **kwargs):
        raise AssertionError('Binding probe must not connect or execute SQL')
    monkeypatch.setattr(GnrSqlDb, 'execute', denied)
    monkeypatch.setattr(socket.socket, 'connect', denied)
    monkeypatch.setattr(socket.socket, 'connect_ex', denied)
    database = GnrSqlDb(implementation='postgres', dbname='unused', debug=True)
    source = Path(__file__).resolve().parents[3] / 'tests/oracles/test_invoice_pg/source.xml'
    database.model.load(str(source))
    return database


def test_legacy_table_model_and_column_identity(db):
    db.startup()
    count = 0
    for pkg in db.model.obj.values():
        for model in pkg.tables.values():
            table = db.table(model.fullname)
            assert table is model.dbtable
            assert table.model is model
            assert table.db is model.db is db
            assert table.pkg is model.pkg
            assert table.columns is model.columns
            assert table.relations is model.relations
            for name in model.columns:
                assert table.column(name) is model.column(name)
            count += 1
    assert count == 75


def test_legacy_relational_column_is_the_target_object(db):
    db.startup()
    invoice = db.table('invc.invoice')
    customer = db.table('invc.customer')
    assert invoice.column('@customer_id.id') is customer.column('id')


def test_legacy_operational_table_is_created_before_columns(db, monkeypatch):
    original = SqlTable.__init__
    seen = []
    def init(self, model):
        assert not model.columns
        seen.append(model.fullname)
        original(self, model)
    monkeypatch.setattr(SqlTable, '__init__', init)
    db.startup()
    assert len(seen) == 75
