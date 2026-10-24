# Copyright 2025 Softwell S.r.l. - SPDX-License-Identifier: Apache-2.0
"""Relation indexes and migration options on the configured-database path.

``AsqueelDb`` projects the model through the object tree, not through a built
``SqlBuilder``: the legacy index rules must hold there too. Also the edges of
``migrate(backup=True)`` and the errors raised while applying.
"""
from __future__ import annotations

from uuid import uuid4

import psycopg
import pytest
from psycopg import sql

from asqueel import AsqueelDb, MigrationError, SqlBuilder, SqlDatabaseConfig
from asqueel.contracts import UnsupportedFeatureError
from tests.native_support import postgres_dsn


def _index_lines(recipe):
    db = AsqueelDb(recipe)
    try:
        return [line for line in db.migration_plan()['sql'].splitlines() if 'INDEX' in line]
    finally:
        db.closeConnection()


def test_relations_without_foreign_key_are_indexed_on_the_configured_path(tmp_path):
    class Recipe(SqlDatabaseConfig):
        def main(self, root):
            db = root.db()
            db.connection(name=str(tmp_path / 'sample.db'), implementation='sqlite')
            tables = db.packages().package('app', sqlschema='app', sqlprefix=False).tables()
            customer = tables.table('customer', pkey='id').columns()
            customer.column('id', dtype='L')
            customer.column('code', dtype='T')
            invoice = tables.table('invoice', pkey='id').columns()
            invoice.column('id', dtype='L')
            invoice.column('customer_code', dtype='T').relation(related_column='app.customer.code')
            invoice.column('customer_id', dtype='L').relation(related_column='app.customer.id')
            invoice.column('other_id', dtype='L').relation(related_column='app.customer.id', indexed=False)

    lines = _index_lines(Recipe)
    assert any('"customer" ("code")' in line for line in lines)
    assert any('"invoice" ("customer_code")' in line for line in lines)
    assert any('"invoice" ("customer_id")' in line for line in lines)
    assert not any('other_id' in line for line in lines)


def test_a_relation_on_a_pkey_member_gets_no_index_on_either_path(tmp_path):
    class Recipe(SqlDatabaseConfig):
        def main(self, root):
            db = root.db()
            db.connection(name=str(tmp_path / 'sample.db'), implementation='sqlite')
            tables = db.packages().package('app', sqlschema='app', sqlprefix=False).tables()
            tables.table('customer', pkey='id').columns().column('id', dtype='L')
            row_table = tables.table('row', pkey='row_key')
            row_table.composites().compositeColumn('row_key', columns='customer_id,line')
            row = row_table.columns()
            row.column('customer_id', dtype='L').relation(related_column='app.customer.id', foreign_key=True)
            row.column('line', dtype='L')

    assert not any('("customer_id")' in line for line in _index_lines(Recipe))

    class Built(SqlBuilder):
        def main(self, root):
            tables = root.db(name='d').packages().package(name='s', sqlschema='s', sqlprefix=False).tables()
            tables.table(name='customer', pkey='id').columns().column(name='id', dtype='L')
            row_table = tables.table(name='row', pkey='row_key')
            row_table.composites().compositeColumn(name='row_key', columns='customer_id,line')
            row = row_table.columns()
            row.column(name='customer_id', dtype='L').relation(related_column='s.customer.id', foreign_key=True)
            row.column(name='line', dtype='L')

    model = Built()
    model.create()
    indexes = model.render(mode='migration')['root']['schemas']['s']['tables']['row']['indexes']
    assert [list(index['attributes']['columns']) for index in indexes.values()] == []


def _render(body):
    class Recipe(SqlBuilder):
        def main(self, root):
            tables = root.db(name='d').packages().package(name='s', sqlschema='s', sqlprefix=False).tables()
            target = tables.table(name='target', pkey='id')
            target.columns().column(name='id', dtype='L')
            target.columns().column(name='code', dtype='T')
            item = tables.table(name='item', pkey='id')
            item.columns().column(name='id', dtype='L')
            body(target, item)

    model = Recipe()
    model.create()
    return model.render(mode='migration')


def test_indexed_options_and_an_explicit_index_on_the_same_column_are_refused():
    def body(target, item):
        item.columns().column(name='code', dtype='T', indexed=dict(method='hash'))
        item.indexes().index(columns='code', where='code IS NOT NULL')

    with pytest.raises(UnsupportedFeatureError, match='conflicts with the explicit index'):
        _render(body)


def test_a_partial_explicit_index_cannot_replace_a_relation_target_index():
    def body(target, item):
        target.indexes().index(columns='code', where='code IS NOT NULL')
        item.columns().column(name='target_code', dtype='T').relation(related_column='s.target.code')

    with pytest.raises(UnsupportedFeatureError, match='does not cover required full index'):
        _render(body)


@pytest.fixture
def pg_schema():
    dsn = postgres_dsn()
    schema = 'm7qc_' + uuid4().hex[:12]
    with psycopg.connect(dsn, autocommit=True) as connection:
        try:
            yield dsn, schema, connection
        finally:
            connection.execute(sql.SQL('DROP SCHEMA IF EXISTS {} CASCADE').format(sql.Identifier(schema)))


def _pg_recipe(dsn, schema, dtype, notnull=False):
    class Recipe(SqlDatabaseConfig):
        def main(self, root):
            columns = root.db(implementation='postgres', conninfo=dsn).packages().package(schema, sqlschema=schema, sqlprefix=False).tables().table(
                'event', pkey='id').columns()
            columns.column('id', dtype='L')
            columns.column('happened', dtype=dtype, notnull=notnull)
    return Recipe


def _filled(dsn, schema, values):
    runtime = AsqueelDb(_pg_recipe(dsn, schema, 'T'))
    try:
        runtime.migrate()
        for index, value in enumerate(values, 1):
            runtime.table(f'{schema}.event').insert({'id': index, 'happened': value})
        runtime.commit()
    finally:
        runtime.closeConnection()


@pytest.mark.postgresql
def test_backup_with_removals_keeps_the_backup_column_and_returns_the_warning(pg_schema):
    dsn, schema, connection = pg_schema
    _filled(dsn, schema, ['2026-01-02', 'not a date'])
    runtime = AsqueelDb(_pg_recipe(dsn, schema, 'DH'))
    try:
        plan = runtime.migrate(backup=True, allow_removals=True)
    finally:
        runtime.closeConnection()
    columns = sorted(row[0] for row in connection.execute(
        'SELECT column_name FROM information_schema.columns WHERE table_schema=%s', (schema,)))
    assert columns == ['happened', 'happened__T', 'id']
    assert any('1 value(s) not converted' in warning and 'happened__T' in warning for warning in plan['warnings'])


@pytest.mark.postgresql
def test_an_error_while_applying_is_a_migration_error(pg_schema):
    dsn, schema, _ = pg_schema
    _filled(dsn, schema, [None])
    runtime = AsqueelDb(_pg_recipe(dsn, schema, 'T', notnull=True))
    try:
        with pytest.raises(MigrationError):
            runtime.migrate()
    finally:
        runtime.closeConnection()
