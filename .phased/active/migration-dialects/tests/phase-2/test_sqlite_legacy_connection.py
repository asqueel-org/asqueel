# Copyright 2025 Softwell S.r.l. - SPDX-License-Identifier: Apache-2.0
"""Macro 7 phase 2 contract — the SQLite connection as GenroPy legacy.

Legacy reference: ``gnrpy/gnr/sql/adapters/gnrsqlite.py`` on ``origin/develop``
(``connect``: the folder is created when missing; ``_attach``: each schema is
``<schema>.db`` in the database folder; ``revTypesDict``: the declared types).
Decided for asqueel (A8.8): foreign keys on by default, switched off by the
connection option ``foreignKeys``. ``vacuum()`` covers every attached schema.
Requires asqueel-migration 0.3.
"""
from __future__ import annotations

import sqlite3

import pytest

from asqueel import AsqueelDb, SqlDatabaseConfig


def _recipe(path, options=None):
    class Recipe(SqlDatabaseConfig):
        def main(self, root):
            db = root.db()
            db.connection(name=str(path), implementation='sqlite', options=options)
            tables = db.schemas().schema('app').tables()
            tables.table('customer', pkey='id').columns().column('id', dtype='L')
            invoice = tables.table('invoice', pkey='id').columns()
            invoice.column('id', dtype='L')
            invoice.column('customer_id', dtype='L').relation(to='app.customer.id', foreign_key=True)
            item = tables.table('item', pkey='id').columns()
            item.column('id', dtype='L')
            item.column('name', dtype='A', size='0:20')
            item.column('code', dtype='C', size='3')
            item.column('stamp', dtype='DH')
            item.column('at', dtype='H')
            item.column('note', dtype='T')
    return Recipe


def _rows(db, statement):
    cursor = db.execute(statement)
    try:
        return [tuple(row) for row in cursor.fetchall()]
    finally:
        cursor.close()


def _migrated(path, options=None):
    db = AsqueelDb(_recipe(path, options))
    db.migrate()
    return db


def test_each_schema_is_a_schema_named_file_in_the_database_folder(tmp_path):
    db = _migrated(tmp_path / 'sample.db')
    try:
        db.table('app.customer').insert({'id': 1})
        db.commit()
    finally:
        db.closeConnection()
    assert (tmp_path / 'sample.db').exists()
    assert (tmp_path / 'app.db').exists()
    assert not (tmp_path / 'sample_app.db').exists()
    connection = sqlite3.connect(tmp_path / 'app.db')
    try:
        assert connection.execute('SELECT id FROM customer').fetchall() == [(1,)]
    finally:
        connection.close()


def test_a_missing_database_folder_is_created(tmp_path):
    path = tmp_path / 'data' / 'nested' / 'sample.db'
    db = _migrated(path)
    try:
        db.table('app.customer').insert({'id': 1})
        db.commit()
    finally:
        db.closeConnection()
    assert (path.parent / 'app.db').exists()


def test_foreign_keys_are_on_by_default(tmp_path):
    db = _migrated(tmp_path / 'sample.db')
    try:
        assert _rows(db, 'PRAGMA foreign_keys') == [(1,)]
        with pytest.raises(Exception, match='FOREIGN KEY'):
            db.table('app.invoice').insert({'id': 1, 'customer_id': 99})
            db.commit()
    finally:
        db.closeConnection()


def test_the_foreign_keys_connection_option_switches_them_off(tmp_path):
    path = tmp_path / 'sample.db'
    _migrated(path).closeConnection()
    db = AsqueelDb(_recipe(path, options={'foreignKeys': False}))
    try:
        assert _rows(db, 'PRAGMA foreign_keys') == [(0,)]
        db.table('app.invoice').insert({'id': 1, 'customer_id': 99})
        db.commit()
        assert _rows(db, 'SELECT customer_id FROM app.invoice') == [(99,)]
    finally:
        db.closeConnection()


def test_the_foreign_keys_option_is_refused_on_postgresql_before_connecting():
    class WithOption(SqlDatabaseConfig):
        def main(self, root):
            db = root.db(implementation='postgres')
            db.connection(name='unused', implementation='postgres', options={'foreignKeys': False})
            db.schemas().schema('app').tables().table('t', pkey='id').columns().column('id', dtype='L')

    db = None
    try:
        with pytest.raises(ValueError, match='foreignKeys'):
            db = AsqueelDb(WithOption)
            db.execute('SELECT 1').close()
    finally:
        if db is not None:
            db.closeConnection()


def test_vacuum_rebuilds_every_attached_schema(tmp_path):
    db = _migrated(tmp_path / 'sample.db')
    try:
        for index in range(2000):
            db.table('app.item').insert({'id': index, 'note': 'x' * 200})
        db.commit()
        db.execute('DELETE FROM app.item').close()
        db.commit()
        assert _rows(db, 'PRAGMA app.freelist_count')[0][0] > 0
        db.commit()
        db.vacuum()
        assert _rows(db, 'PRAGMA app.freelist_count') == [(0,)]
    finally:
        db.closeConnection()


def test_declared_sql_types_are_the_legacy_ones(tmp_path):
    db = _migrated(tmp_path / 'sample.db')
    try:
        types = {row[1]: row[2].lower() for row in _rows(db, "PRAGMA app.table_info('item')")}
    finally:
        db.closeConnection()
    assert types['name'].startswith('character varying')
    assert types['code'].startswith('character') and not types['code'].startswith('character varying')
    assert types['stamp'] == 'timestamp'
    assert types['at'] == 'time'
    assert types['note'] == 'text'


def test_a_database_created_with_the_earlier_type_names_needs_no_migration(tmp_path):
    path = tmp_path / 'sample.db'
    sqlite3.connect(path).close()
    connection = sqlite3.connect(tmp_path / 'app.db')
    try:
        connection.executescript('''
            CREATE TABLE customer ("id" bigint NOT NULL, PRIMARY KEY ("id"));
            CREATE TABLE invoice ("id" bigint NOT NULL, "customer_id" bigint, PRIMARY KEY ("id"),
                FOREIGN KEY ("customer_id") REFERENCES "customer" ("id") ON UPDATE CASCADE);
            CREATE INDEX idx_invoice_customer ON invoice ("customer_id");
            CREATE TABLE item ("id" bigint NOT NULL, "name" varchar(20), "code" char(3),
                "stamp" timestamp without time zone, "at" time, "note" text, PRIMARY KEY ("id"));
        ''')
    finally:
        connection.close()
    db = AsqueelDb(_recipe(path))
    try:
        plan = db.migration_plan()
        assert 'item' not in plan.commands
    finally:
        db.closeConnection()
