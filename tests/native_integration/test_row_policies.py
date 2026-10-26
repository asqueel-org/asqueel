"""Policy acceptance against PostgreSQL through the public compiler/runtime."""
from datetime import datetime, timezone
from uuid import uuid4

import psycopg
from psycopg import sql
import pytest

from asqueel import AsqueelDb, SqlDatabaseConfig
from tests.native_support import postgres_dsn

pytestmark = pytest.mark.postgresql


@pytest.fixture
def policy_database():
    schema = 'policies_' + uuid4().hex
    dsn = postgres_dsn()
    with psycopg.connect(dsn, autocommit=True) as connection:
        connection.execute(sql.SQL('CREATE SCHEMA {}').format(sql.Identifier(schema)))
        try:
            connection.execute(sql.SQL('''CREATE TABLE {}.item (
                id integer PRIMARY KEY, organization integer, draft boolean,
                deleted_at timestamptz, label text
            )''').format(sql.Identifier(schema)))
            connection.execute(sql.SQL('''INSERT INTO {}.item VALUES
                (1, 10, NULL, NULL, 'ten'), (2, 11, false, NULL, 'eleven'),
                (3, 10, true, NULL, 'draft'),
                (4, 10, false, '2026-01-01T00:00:00Z', 'deleted'),
                (5, NULL, false, NULL, 'shared')''').format(sql.Identifier(schema)))
            builder = SqlDatabaseConfig()
            columns = builder.source.db('policy', implementation='postgres', conninfo=dsn).packages().package(
                'app', sqlschema=schema, sqlprefix=False
            ).tables().table(
                'item', pkey='id',
                partition_organization='organization',
                draftField='draft', logicalDeletionField='deleted_at',
            ).columns()
            for name, dtype in [('id', 'I'), ('organization', 'I'), ('draft', 'B'),
                                ('deleted_at', 'DHZ'), ('label', 'T')]:
                columns.column(name, dtype=dtype)
            shared = AsqueelDb(builder)
            try:
                yield shared.session()
            finally:
                shared.close()
        finally:
            connection.execute(sql.SQL('DROP SCHEMA {} CASCADE').format(sql.Identifier(schema)))


def test_scopes_defaults_mark_and_environment_reuse(policy_database):
    db = env = policy_database
    compiler = db.compiler

    def scenario():
        try:
            assert [r['id'] for r in db.execute(compiler.select('app.item', order_by='$id')).fetchall()] == [1, 2, 5]
            with env.tempEnv(current_organization=10):
                query = compiler.select('app.item', order_by='$id')
                assert [r['id'] for r in (db.execute(query)).fetchall()] == [1]
                marked = db.execute(compiler.select(
                    'app.item', exclude_draft=False, exclude_logical_deleted='mark',
                    order_by='$id',
                )).fetchall()
                assert [r['id'] for r in marked] == [1, 3, 4]
                assert marked[0]['_isdeleted'] is None
                assert marked[2]['_isdeleted'] == datetime(2026, 1, 1, tzinfo=timezone.utc)
            with env.tempEnv(current_organization=11):
                fresh = compiler.select('app.item', order_by='$id')
                assert db.execute(query).fetchall() == db.execute(fresh).fetchall()
            with env.tempEnv(allowed_organization=[]):
                assert len(db.execute(compiler.select('app.item')).fetchall()) == 3
            with env.tempEnv(allowed_organization=[10]):
                rows = (db.execute(compiler.select('app.item', order_by='$id'))).fetchall()
                assert [r['id'] for r in rows] == [1, 5]
            with env.tempEnv(current_organization=10, allowed_organization=[]):
                assert [r['id'] for r in db.execute(compiler.select('app.item')).fetchall()] == [1]
            with env.tempEnv(current_organization=None):
                assert len(db.execute(compiler.select('app.item')).fetchall()) == 3
            assert len((db.execute(compiler.select('app.item', ignore_partition=True))).fetchall()) == 3
        finally:
            db.closeConnection()
    scenario()


def test_writes_soft_delete_restore_and_scope_isolation(policy_database):
    db = env = policy_database
    model, compiler = db.model, db.compiler
    writer, table = db.write_compiler, model.table('app.item')

    def scenario():
        try:
            with env.tempEnv(current_organization=10):
                db.execute(writer.insert(table, {'id': 6, 'label': 'new', 'organization': 10}, env.environment_snapshot()))
                changed = db.execute(writer.update(table, {'id': 3, 'label': 'editable draft'}, env.environment_snapshot()))
                assert changed.rowcount == 1
                tombstone = datetime(2026, 9, 29, tzinfo=timezone.utc)
                db.execute(writer.update(table, {'id': 6, 'deleted_at': tombstone}, env.environment_snapshot()))
                assert not (db.execute(compiler.select('app.item', where='$id = 6'))).fetchall()
                db.execute(writer.update(table, {'id': 6, 'deleted_at': None}, env.environment_snapshot()))
                assert [r['id'] for r in db.execute(compiler.select('app.item', where='$id = 6')).fetchall()] == [6]
                assert db.execute(writer.delete(table, {'id': 6}, env.environment_snapshot())).rowcount == 1

            def read_scope(value):
                with env.tempEnv(current_organization=value):
                    return [r['id'] for r in (db.execute(compiler.select('app.item'))).fetchall()]

            assert [read_scope(10), read_scope(11)] == [[1], [2]]
            assert not env.currentEnv
        finally:
            db.closeConnection()
    scenario()


def test_writes_fill_and_guard_the_partition(policy_database):
    db = env = policy_database
    model, compiler = db.model, db.compiler
    writer, table = db.write_compiler, model.table('app.item')
    try:
        with env.tempEnv(current_organization=10):
            db.execute(writer.insert(table, {'id': 6, 'label': 'new'}, env.environment_snapshot()))
            stored = db.execute(compiler.select('app.item', '$organization', where='$id = 6', ignore_partition=True))
            assert stored.fetchall()[0]['organization'] == 10
            with pytest.raises(ValueError):
                writer.insert(table, {'id': 7, 'organization': 11}, env.environment_snapshot())
            assert db.execute(writer.update(table, {'id': 2, 'label': 'forbidden'}, env.environment_snapshot())).rowcount == 0
    finally:
        db.closeConnection()
