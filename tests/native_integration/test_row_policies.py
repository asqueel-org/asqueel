"""Policy acceptance against PostgreSQL through the public compiler/runtime."""
from datetime import datetime, timezone
from uuid import uuid4

import psycopg
from psycopg import sql
import pytest

from genro_sql import (
    EnvironmentMismatchError, PostgresCompiler, PostgresDatabase,
    SqlBuilder, SqlEnvironment, resolve_model,
)
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

    def scenario():
        with PostgresDatabase(dsn, environment=env) as db:
            with env.temp_env(organization=0):
                inserted = db.execute(compiler.insert('app.item', {'id': 6, 'label': 'new'}))
                assert inserted.rows[0]['organization'] == 0
                with pytest.raises(ValueError):
                    compiler.insert('app.item', {'id': 7, 'organization': 1})
                assert (db.execute(compiler.update(
                    'app.item', {'label': 'forbidden'}, where='$id = 2',
                ))).rowcount == 0
                changed = db.execute(compiler.update(
                    'app.item', {'label': 'editable draft'}, where='$id = 3',
                ))
                assert changed.rowcount == 1
                tombstone = datetime(2026, 9, 29, tzinfo=timezone.utc)
                db.execute(compiler.soft_delete('app.item', value=tombstone, where='$id = 6'))
                assert not (db.execute(compiler.select('app.item', where='$id = 6'))).rows
                restored = db.execute(compiler.restore('app.item', where='$id = 6'))
                assert restored.rows[0]['deleted_at'] is None
                assert (db.execute(compiler.delete('app.item', where='$id = 6'))).rowcount == 1

            def read_scope(value):
                with env.temp_env(organization=value):
                    return [r['id'] for r in (db.execute(compiler.select('app.item'))).rows]

            assert [read_scope(0), read_scope(1)] == [[1], [2]]
            assert not env.current_env
    scenario()
