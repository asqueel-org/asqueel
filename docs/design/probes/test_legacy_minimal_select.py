"""Compile-only ports of legacy physical-column queries plus clause contracts.

Run with a frozen GenroPy interpreter, not Asqueel's pytest environment.
Original runtime assertions remain in the legacy suite; these assert compilation.
"""
import json
import os
from pathlib import Path
import socket
from datetime import date
from decimal import Decimal

import pytest
from gnr.sql.gnrsql import GnrSqlDb


@pytest.fixture(params=['postgres', 'sqlite'])
def db(request, monkeypatch):
    def denied(*args, **kwargs):
        raise AssertionError('Compilation must not connect or execute')
    monkeypatch.setattr(GnrSqlDb, 'execute', denied)
    monkeypatch.setattr(socket.socket, 'connect', denied)
    monkeypatch.setattr(socket.socket, 'connect_ex', denied)
    monkeypatch.setattr('sqlite3.connect', denied)
    database = GnrSqlDb(implementation=request.param, dbname='unused')
    pkg = database.model.src.package('sales', sqlschema='main', sqlprefix=True)
    table = pkg.table('invoice', pkey='id')
    for name, dtype in [('id', 'L'), ('total', 'N'), ('issued', 'D')]:
        table.column(name, dtype=dtype)
    database.startup()
    return database


def test_physical_expression_where_order_limit(db):
    params = dict(threshold=Decimal('100.50'), day=date(2026, 10, 14), empty=None)
    query = db.table('sales.invoice').query(
        columns='$id AS code, COALESCE($total,0) AS amount, '
                'CASE WHEN $total >= :threshold THEN 1 ELSE 0 END AS category',
        where='$issued <= :day AND (:empty IS NULL OR $id = :empty)',
        order_by='$total DESC, $id', limit=3, offset=2,
        sqlparams=params, addPkeyColumn=False)
    sql = query.sqltext
    assert 'COALESCE(' in sql and 'CASE WHEN ' in sql
    assert 'LIMIT 3' in sql and 'OFFSET 2' in sql
    assert 'JOIN' not in sql
    assert query.sqlparams['threshold'] == params['threshold']
    assert query.sqlparams['day'] == params['day']
    assert query.sqlparams['empty'] is None
    assert isinstance(query.sqlparams['threshold'], Decimal)
    assert isinstance(query.sqlparams['day'], date)
    assert query.sqltext == sql
    directory = os.environ.get('ASQUEEL_SELECT_EVIDENCE')
    if directory:
        Path(directory, f'{db.implementation}.json').write_text(json.dumps({
            'sql': sql, 'params': query.sqlparams,
            'types': {key: type(value).__name__ for key, value in query.sqlparams.items()}
        }, indent=2, default=str) + '\n')


@pytest.mark.parametrize('columns,limit,names', [
    ('$account_name', 5, ['account_name']),
    ('$account_name, $email, $phone', 3, ['account_name', 'email', 'phone']),
])
def test_physical_columns_from_original_coverage(db, columns, limit, names):
    # test_compiler_coverage.TestPhysicalColumns: single/multiple_column_{pg,sqlite}.
    source = Path(__file__).resolve().parents[3] / 'tests/oracles/test_invoice_pg/source.xml'
    db.model.load(str(source))
    db.startup()
    query = db.table('invc.customer').query(
        columns=columns, limit=limit, addPkeyColumn=False,
        excludeDraft=False, excludeLogicalDeleted=False, ignorePartition=True)
    sql = query.sqltext
    assert f'LIMIT {limit}' in sql
    for name in names:
        assert f'"t0"."{name}"' in sql
    assert 'JOIN' not in sql
