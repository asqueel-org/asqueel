# Copyright 2025 Softwell S.r.l. - SPDX-License-Identifier: Apache-2.0
"""Macro 7 phase 2 contract — the migration reads the model as GenroPy legacy.

Legacy reference: ``gnrsqlmigration/orm_extractor.py`` on ``origin/develop``:
``statement_converter`` (SQL action abbreviations), ``fill_json_relations_and_indexes``
(an index on every relation column, a deferred one on a non-pkey target),
``fill_json_column_index`` (``indexed={...}`` options). The migration options
``foreignKeys``, ``force`` and ``backup`` reach the migrator from
``migration_plan()``, ``migrate()`` and the CLI.
"""
from __future__ import annotations

from uuid import uuid4

import psycopg
import pytest
from psycopg import sql

from asqueel import AsqueelDb, MigrationError, SqlBuilder, SqlDatabaseConfig, SqlMigrationRenderer
from asqueel.cli import main
from tests.native_support import postgres_dsn


# ---------------------------------------------------------------------------
# Projection (no database)
# ---------------------------------------------------------------------------

def _table(recipe_body):
    class Recipe(SqlBuilder):
        def main(self, root):
            tables = root.db(name='d').schemas().schema(name='s').tables()
            target = tables.table(name='target', pkey='id')
            target_columns = target.columns()
            target_columns.column(name='id', dtype='L')
            target_columns.column(name='code', dtype='T')
            item = tables.table(name='item', pkey='id')
            columns = item.columns()
            columns.column(name='id', dtype='L')
            recipe_body(columns)

    model = Recipe()
    model.create()
    return SqlMigrationRenderer(model).render()['root']['schemas']['s']['tables']


def _indexes_on(table, columns):
    return [index for index in table['indexes'].values()
            if list(index['attributes']['columns']) == columns]


@pytest.mark.parametrize('declared, expected', [
    ('C', 'CASCADE'), ('c', 'CASCADE'), ('CASCADE', 'CASCADE'),
    ('R', 'RESTRICT'), ('restrict', 'RESTRICT'),
    ('SN', 'SET NULL'), ('SETNULL', 'SET NULL'), ('set null', 'SET NULL'), ('setnull', 'SET NULL'),
    ('SD', 'SET DEFAULT'), ('SETDEFAULT', 'SET DEFAULT'), ('Set Default', 'SET DEFAULT'),
])
def test_sql_actions_accept_the_legacy_abbreviations(declared, expected):
    def body(columns):
        columns.column(name='target_id', dtype='L').relation(
            to='s.target.id', foreign_key=True, onDelete_sql=declared, onUpdate_sql=declared)

    relation, = _table(body)['item']['relations'].values()
    assert relation['attributes']['on_delete'] == expected
    assert relation['attributes']['on_update'] == expected


@pytest.mark.parametrize('declared', ['N', 'no action', 'NO ACTION'])
def test_no_action_projects_no_action_clause(declared):
    def body(columns):
        columns.column(name='target_id', dtype='L').relation(
            to='s.target.id', foreign_key=True, onDelete_sql=declared, onUpdate_sql=declared)

    relation, = _table(body)['item']['relations'].values()
    assert relation['attributes'].get('on_delete') is None
    assert relation['attributes'].get('on_update') is None


def test_an_unknown_sql_action_is_refused():
    def body(columns):
        columns.column(name='target_id', dtype='L').relation(
            to='s.target.id', foreign_key=True, onDelete_sql='X')

    with pytest.raises(Exception, match="onDelete_sql 'X'"):
        _table(body)


def test_a_relation_without_foreign_key_is_indexed_and_projects_no_constraint():
    def body(columns):
        columns.column(name='target_id', dtype='L').relation(to='s.target.id')

    item = _table(body)['item']
    assert item['relations'] == {}
    assert len(_indexes_on(item, ['target_id'])) == 1


def test_indexed_false_on_a_relation_without_foreign_key_skips_the_index():
    def body(columns):
        columns.column(name='target_id', dtype='L').relation(to='s.target.id', indexed=False)

    assert _indexes_on(_table(body)['item'], ['target_id']) == []


def test_a_relation_to_a_non_pkey_target_column_indexes_the_target_column():
    def body(columns):
        columns.column(name='target_code', dtype='T').relation(to='s.target.code')

    tables = _table(body)
    assert len(_indexes_on(tables['item'], ['target_code'])) == 1
    assert len(_indexes_on(tables['target'], ['code'])) == 1


def test_indexed_dict_carries_the_legacy_index_options():
    def body(columns):
        columns.column(name='code', dtype='T', indexed=dict(
            method='btree', where='code IS NOT NULL', sorting='DESC', with_fillfactor=70))

    index, = _indexes_on(_table(body)['item'], ['code'])
    attributes = index['attributes']
    assert attributes['columns'] == {'code': 'DESC'}
    assert attributes['method'] == 'btree'
    assert attributes['where'] == 'code IS NOT NULL'
    assert attributes['with_options'] == {'fillfactor': 70}


def test_indexed_dict_with_unique_makes_the_column_unique_and_no_index():
    def body(columns):
        columns.column(name='code', dtype='T', indexed=dict(unique=True))

    item = _table(body)['item']
    assert item['columns']['code']['attributes'].get('unique') is True
    assert _indexes_on(item, ['code']) == []


def test_indexed_dict_with_unique_and_where_is_a_partial_unique_index():
    def body(columns):
        columns.column(name='code', dtype='T', indexed=dict(unique=True, where='code IS NOT NULL'))

    item = _table(body)['item']
    index, = _indexes_on(item, ['code'])
    assert index['attributes'].get('unique') is True
    assert index['attributes']['where'] == 'code IS NOT NULL'
    assert not item['columns']['code']['attributes'].get('unique')


def test_indexed_dict_on_a_relation_column_gives_one_index_with_its_options():
    def body(columns):
        columns.column(name='target_id', dtype='L', indexed=dict(sorting='DESC')).relation(
            to='s.target.id', foreign_key=True)

    index, = _indexes_on(_table(body)['item'], ['target_id'])
    assert index['attributes']['columns'] == {'target_id': 'DESC'}


def test_indexed_dict_with_an_unknown_option_is_refused():
    def body(columns):
        columns.column(name='code', dtype='T', indexed=dict(colour='red'))

    with pytest.raises(Exception, match='colour'):
        _table(body)


# ---------------------------------------------------------------------------
# foreignKeys=False (SQLite)
# ---------------------------------------------------------------------------

def _sqlite_recipe(path):
    class Recipe(SqlDatabaseConfig):
        def main(self, root):
            db = root.db()
            db.connection(name=str(path), implementation='sqlite')
            tables = db.schemas().schema('app').tables()
            customer = tables.table('customer', pkey='id').columns()
            customer.column('id', dtype='L')
            invoice = tables.table('invoice', pkey='id').columns()
            invoice.column('id', dtype='L')
            invoice.column('customer_id', dtype='L').relation(to='app.customer.id', foreign_key=True)
    return Recipe


def _rows(db, statement):
    cursor = db.execute(statement)
    try:
        return [tuple(row) for row in cursor.fetchall()]
    finally:
        cursor.close()


def test_foreign_keys_false_migrates_without_constraints_and_keeps_the_relation_index(tmp_path):
    db = AsqueelDb(_sqlite_recipe(tmp_path / 'sample.db'))
    try:
        plan = db.migration_plan(foreignKeys=False)
        assert 'REFERENCES' not in plan.commands
        db.migrate(foreignKeys=False)
        assert _rows(db, "PRAGMA app.foreign_key_list('invoice')") == []
        indexed_columns = [
            column
            for index in _rows(db, "PRAGMA app.index_list('invoice')")
            for column in [info[2] for info in _rows(db, f"PRAGMA app.index_info('{index[1]}')")]
        ]
        assert 'customer_id' in indexed_columns
        assert db.migration_plan(foreignKeys=False).empty
    finally:
        db.closeConnection()


def test_foreign_keys_default_creates_the_constraint(tmp_path):
    db = AsqueelDb(_sqlite_recipe(tmp_path / 'sample.db'))
    try:
        db.migrate()
        assert [row[2] for row in _rows(db, "PRAGMA app.foreign_key_list('invoice')")] == ['customer']
    finally:
        db.closeConnection()


def test_cli_no_foreign_keys_option(tmp_path, capsys):
    path = tmp_path / 'cli.db'
    source = tmp_path / 'recipe.py'
    source.write_text(
        'from asqueel import SqlDatabaseConfig\n\n'
        'class Recipe(SqlDatabaseConfig):\n'
        '    def main(self, root):\n'
        '        db = root.db()\n'
        f'        db.connection(name={str(path)!r}, implementation="sqlite")\n'
        '        tables = db.schemas().schema("app").tables()\n'
        '        tables.table("customer", pkey="id").columns().column("id", dtype="L")\n'
        '        invoice = tables.table("invoice", pkey="id").columns()\n'
        '        invoice.column("id", dtype="L")\n'
        '        invoice.column("customer_id", dtype="L").relation(to="app.customer.id", foreign_key=True)\n'
    )
    assert main(['db', 'plan', str(source), '--no-foreign-keys']) == 0
    assert 'REFERENCES' not in capsys.readouterr().out


# ---------------------------------------------------------------------------
# force / backup (PostgreSQL: SQLite cannot alter a column type)
# ---------------------------------------------------------------------------

def _pg_recipe(dsn, schema, dtype):
    class Recipe(SqlDatabaseConfig):
        def main(self, root):
            columns = root.db(implementation='postgres', conninfo=dsn).schemas().schema(schema).tables().table(
                'event', pkey='id').columns()
            columns.column('id', dtype='L')
            columns.column('happened', dtype=dtype)
    return Recipe


@pytest.fixture
def pg_schema():
    dsn = postgres_dsn()
    schema = 'm7_' + uuid4().hex[:12]
    with psycopg.connect(dsn, autocommit=True) as connection:
        try:
            yield dsn, schema, connection
        finally:
            connection.execute(sql.SQL('DROP SCHEMA IF EXISTS {} CASCADE').format(sql.Identifier(schema)))


def _filled(dsn, schema, values):
    runtime = AsqueelDb(_pg_recipe(dsn, schema, 'T'))
    try:
        runtime.migrate()
        for index, value in enumerate(values, 1):
            runtime.table(f'{schema}.event').insert({'id': index, 'happened': value})
        runtime.commit()
    finally:
        runtime.closeConnection()


def _columns(connection, schema):
    return sorted(row[0] for row in connection.execute(
        'SELECT column_name FROM information_schema.columns WHERE table_schema=%s AND table_name=%s',
        (schema, 'event')))


@pytest.mark.postgresql
def test_a_conversion_on_a_filled_column_without_force_is_refused(pg_schema):
    dsn, schema, _ = pg_schema
    _filled(dsn, schema, ['2026-01-02', 'not a date'])
    runtime = AsqueelDb(_pg_recipe(dsn, schema, 'DH'))
    try:
        with pytest.raises(MigrationError, match='force'):
            runtime.migrate()
    finally:
        runtime.closeConnection()


@pytest.mark.postgresql
def test_force_converts_and_non_matching_values_become_null(pg_schema):
    dsn, schema, connection = pg_schema
    _filled(dsn, schema, ['2026-01-02', 'not a date'])
    runtime = AsqueelDb(_pg_recipe(dsn, schema, 'DH'))
    try:
        runtime.migrate(force=True)
        assert runtime.migration_plan().empty
    finally:
        runtime.closeConnection()
    rows = connection.execute(sql.SQL('SELECT id, happened IS NULL FROM {}.event ORDER BY id').format(
        sql.Identifier(schema))).fetchall()
    assert rows == [(1, False), (2, True)]
    assert _columns(connection, schema) == ['happened', 'id']


@pytest.mark.postgresql
def test_backup_keeps_the_backup_column_and_warns_when_values_are_lost(pg_schema):
    dsn, schema, connection = pg_schema
    _filled(dsn, schema, ['2026-01-02', 'not a date'])
    runtime = AsqueelDb(_pg_recipe(dsn, schema, 'DH'))
    try:
        plan = runtime.migrate(backup=True)
    finally:
        runtime.closeConnection()
    assert _columns(connection, schema) == ['happened', 'happened__T', 'id']
    assert any('happened__T' in warning for warning in plan.warnings)


@pytest.mark.postgresql
def test_backup_drops_the_backup_column_when_nothing_is_lost(pg_schema):
    dsn, schema, connection = pg_schema
    _filled(dsn, schema, ['2026-01-02', '2026-03-04'])
    runtime = AsqueelDb(_pg_recipe(dsn, schema, 'DH'))
    try:
        plan = runtime.migrate(backup=True)
    finally:
        runtime.closeConnection()
    assert _columns(connection, schema) == ['happened', 'id']
    assert not any('happened__T' in warning for warning in plan.warnings)


# ---------------------------------------------------------------------------
# Kept as they are (A7.3)
# ---------------------------------------------------------------------------

def test_migrate_still_refuses_skipped_changes_before_any_ddl(tmp_path):
    path = tmp_path / 'sample.db'

    def recipe(dtype):
        class Recipe(SqlDatabaseConfig):
            def main(self, root):
                db = root.db()
                db.connection(name=str(path), implementation='sqlite')
                columns = db.schemas().schema('app').tables().table('item', pkey='id').columns()
                columns.column('id', dtype='L')
                columns.column('name', dtype=dtype)
        return Recipe

    first = AsqueelDb(recipe('T'))
    try:
        first.migrate()
    finally:
        first.closeConnection()
    changed = AsqueelDb(recipe('L'))
    try:
        with pytest.raises(MigrationError, match='cannot apply'):
            changed.migrate(force=True)
    finally:
        changed.closeConnection()
