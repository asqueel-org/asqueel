"""Policy acceptance against PostgreSQL through the public compiler/runtime."""
from datetime import datetime, timezone
from uuid import uuid4

import psycopg
from psycopg import sql
import pytest

from asqueel import (
    EnvironmentMismatchError, PostgresCompiler, PostgresDatabase,
    SqlBuilder, SqlEnvironment, resolve_model,
)
from asqueel.adapters.postgres import SqlDbAdapter as PostgresAdapter
from asqueel.write_compiler import WriteCompiler
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
                (1, 0, NULL, NULL, 'zero'), (2, 1, false, NULL, 'one'),
                (3, 0, true, NULL, 'draft'),
                (4, 0, false, '2026-01-01T00:00:00Z', 'deleted'),
                (5, NULL, false, NULL, 'shared')''').format(sql.Identifier(schema)))
            builder = SqlBuilder()
            columns = builder.source.db('policy').schemas().schema(
                'app', x_sql_schema=schema,
            ).tables().table(
                'item', pkey='id',
                x_partition={'field': 'organization', 'current': 'organization',
                             'allowed': 'allowed_organizations'},
                x_draft_field='draft', x_logical_deletion_field='deleted_at',
            ).columns()
            for name, dtype in [('id', 'I'), ('organization', 'I'), ('draft', 'B'),
                                ('deleted_at', 'DHZ'), ('label', 'T')]:
                columns.column(name, dtype=dtype)
            yield dsn, resolve_model(builder)
        finally:
            connection.execute(sql.SQL('DROP SCHEMA {} CASCADE').format(sql.Identifier(schema)))


def test_scopes_defaults_mark_and_environment_reuse(policy_database):
    dsn, model = policy_database
    env = SqlEnvironment()
    compiler = PostgresCompiler(model, environment=env)

    def scenario():
        with PostgresDatabase(dsn, environment=env) as db:
            with pytest.raises(ValueError):
                compiler.select('app.item')
            with env.temp_env(organization=0):
                query = compiler.select('app.item', order_by='$id')
                assert [r['id'] for r in (db.execute(query)).rows] == [1]
                marked = db.execute(compiler.select(
                    'app.item', exclude_draft=False, exclude_logical_deleted='mark',
                    order_by='$id',
                ))
                assert [r['id'] for r in marked.rows] == [1, 3, 4]
                assert marked.rows[0]['_isdeleted'] is None
                assert marked.rows[2]['_isdeleted'] == datetime(2026, 1, 1, tzinfo=timezone.utc)
            with env.temp_env(organization=1):
                with pytest.raises(EnvironmentMismatchError):
                    db.execute(query)
            with env.temp_env(allowed_organizations=[]):
                assert not (db.execute(compiler.select('app.item'))).rows
            with env.temp_env(allowed_organizations=[0]):
                rows = (db.execute(compiler.select('app.item', order_by='$id'))).rows
                assert [r['id'] for r in rows] == [1, 5]
            with env.temp_env(organization=0, allowed_organizations=[]):
                assert not (db.execute(compiler.select('app.item'))).rows
            with env.temp_env(organization=None):
                assert [r['id'] for r in (db.execute(compiler.select('app.item'))).rows] == [5]
            assert len((db.execute(compiler.select('app.item', ignore_partition=True))).rows) == 3
    scenario()


def test_writes_soft_delete_restore_and_scope_isolation(policy_database):
    dsn, model = policy_database
    env = SqlEnvironment()
    compiler = PostgresCompiler(model, environment=env)
    writer, table = WriteCompiler(PostgresAdapter(None)), model.table('app.item')

    def scenario():
        with PostgresDatabase(dsn, environment=env) as db:
            with env.temp_env(organization=0):
                db.execute(writer.insert(table, {'id': 6, 'label': 'new', 'organization': 0}, env.snapshot()))
                changed = db.execute(writer.update(table, {'id': 3, 'label': 'editable draft'}, env.snapshot()))
                assert changed.rowcount == 1
                tombstone = datetime(2026, 9, 29, tzinfo=timezone.utc)
                db.execute(writer.update(table, {'id': 6, 'deleted_at': tombstone}, env.snapshot()))
                assert not (db.execute(compiler.select('app.item', where='$id = 6'))).rows
                db.execute(writer.update(table, {'id': 6, 'deleted_at': None}, env.snapshot()))
                assert [r['id'] for r in db.execute(compiler.select('app.item', where='$id = 6')).rows] == [6]
                assert db.execute(writer.delete(table, {'id': 6}, env.snapshot())).rowcount == 1

            def read_scope(value):
                with env.temp_env(organization=value):
                    return [r['id'] for r in (db.execute(compiler.select('app.item'))).rows]

            assert [read_scope(0), read_scope(1)] == [[1], [2]]
            assert not env.current_env
    scenario()


@pytest.mark.xfail(strict=True, reason='asqueel#15: partition autofill and guard on write')
def test_writes_fill_and_guard_the_partition(policy_database):
    dsn, model = policy_database
    env = SqlEnvironment()
    compiler = PostgresCompiler(model, environment=env)
    writer, table = WriteCompiler(PostgresAdapter(None)), model.table('app.item')
    with PostgresDatabase(dsn, environment=env) as db:
        with env.temp_env(organization=0):
            db.execute(writer.insert(table, {'id': 6, 'label': 'new'}, env.snapshot()))
            stored = db.execute(compiler.select('app.item', '$organization', where='$id = 6', ignore_partition=True))
            assert stored.rows[0]['organization'] == 0
            with pytest.raises(ValueError):
                writer.insert(table, {'id': 7, 'organization': 1}, env.snapshot())
            assert db.execute(writer.update(table, {'id': 2, 'label': 'forbidden'}, env.snapshot())).rowcount == 0
