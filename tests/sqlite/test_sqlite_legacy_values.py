"""SQLite values and transactions as legacy gnrsqlite."""
import sqlite3
from datetime import date, datetime, time, timezone
from decimal import Decimal

import pytest

from asqueel import AsqueelDb, SqlDatabaseConfig


def recipe(path):
    class Recipe(SqlDatabaseConfig):
        def main(self, root):
            db = root.db()
            db.connection(name=str(path), implementation='sqlite', options={'timeout': 0.1})
            columns = db.schemas().schema('app').tables().table('item', pkey='id').columns()
            for name, dtype in (('id', 'I'), ('day', 'D'), ('moment', 'DH'), ('stamp', 'DHZ'),
                                ('hour', 'H'), ('amount', 'N'), ('flag', 'B')):
                columns.column(name, dtype=dtype)
    return Recipe


@pytest.fixture
def database(tmp_path):
    path = tmp_path / 'values.db'
    db = AsqueelDb(recipe(path))
    # Declared types as asqueel-migration's SQLite writer emits them (legacy revTypesDict).
    db.execute('CREATE TABLE app.item (id integer PRIMARY KEY, day date, '
               'moment timestamp, stamp timestamp with time zone, '
               'hour time, amount numeric(10,2), flag boolean)')
    db.commit()
    try:
        yield db, path.with_name('app.db')
    finally:
        db.closeConnection()


def test_values_come_back_converted_to_the_dtype(database):
    db, _ = database
    record = {'id': 1, 'day': date(2026, 10, 18), 'moment': datetime(2026, 10, 18, 9, 30, 15, 250),
              'stamp': datetime(2026, 10, 18, 9, 30, tzinfo=timezone.utc), 'hour': time(9, 30, 5),
              'amount': Decimal('12.50'), 'flag': True}
    db.table('app.item').sql_insert(record)
    db.commit()
    row = db.table('app.item').query(where='$id = :id', id=1).fetch()[0]
    assert {name: row[name] for name in record} == record
    assert [type(row[name]) for name in ('day', 'moment', 'hour', 'amount', 'flag')] == [
        date, datetime, time, Decimal, bool]


def test_read_in_open_unit_of_work_does_not_block_another_writer(database):
    db, path = database
    db.table('app.item').query().fetch()
    # As legacy: the unit of work is open, the read holds no SQLite lock.
    assert db._connection_state['pending']
    assert not db._connection_state['connection'].in_transaction
    other = sqlite3.connect(path, isolation_level=None, timeout=0.05)
    try:
        other.execute('INSERT INTO item (id) VALUES (2)')
    finally:
        other.close()
    db.rollback()


def test_for_update_blocks_another_writer(database):
    db, path = database
    db.table('app.item').query(for_update=True).fetch()
    other = sqlite3.connect(path, isolation_level=None, timeout=0.05)
    try:
        with pytest.raises(sqlite3.OperationalError, match='locked'):
            other.execute('INSERT INTO item (id) VALUES (2)')
        db.rollback()
        other.execute('INSERT INTO item (id) VALUES (2)')
    finally:
        other.close()
