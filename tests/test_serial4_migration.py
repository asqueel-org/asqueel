"""SERIAL4 grammar and native migration compatibility across engine versions."""
from uuid import uuid4

import psycopg
from psycopg import sql
import pytest

from asqueel import AsqueelDb, SqlDatabaseConfig
from asqueel_migration.structures import DTYPE_CODES
from tests.native_support import postgres_dsn


def config(dsn, schema, dtype='serial4'):
    class Config(SqlDatabaseConfig):
        def main(self, root):
            root.db(implementation='postgres', conninfo=dsn).packages().package(schema, sqlschema=schema, sqlprefix=False).tables().table(
                'items', pkey='id',
            ).columns().column('id', dtype=dtype)
    return Config


def test_serial4_declaration_is_accepted_without_connecting():
    runtime = AsqueelDb(config('postgresql://localhost/unused', 'app'))
    runtime.closeConnection()


@pytest.mark.postgresql
@pytest.mark.skipif('serial4' not in DTYPE_CODES, reason='requires migration engine with serial4 support')
@pytest.mark.parametrize('existing', [False, True])
def test_native_serial4_keys_and_legacy_integer_adoption(existing):
    dsn = postgres_dsn()
    schema = 'serial4_' + uuid4().hex[:12]
    with psycopg.connect(dsn, autocommit=True) as conn:
        conn.execute(sql.SQL('CREATE SCHEMA {}').format(sql.Identifier(schema)))
        try:
            if existing:
                conn.execute(sql.SQL('CREATE TABLE {}.items (id SERIAL PRIMARY KEY)').format(sql.Identifier(schema)))
                conn.execute(sql.SQL('INSERT INTO {}.items DEFAULT VALUES').format(sql.Identifier(schema)))
                conn.execute("SELECT setval(pg_get_serial_sequence(%s, 'id'), 90, false)", (f'{schema}.items',))
            runtime = AsqueelDb(config(dsn, schema))
            try:
                plan = runtime.migration_plan()
                assert plan['empty'] is existing
                runtime.migrate()
                assert runtime.migration_plan()['empty']
            finally:
                runtime.closeConnection()
            assert conn.execute("SELECT data_type FROM information_schema.columns WHERE table_schema=%s AND table_name='items' AND column_name='id'", (schema,)).fetchone() == ('integer',)
            assert conn.execute(sql.SQL('INSERT INTO {}.items DEFAULT VALUES RETURNING id').format(sql.Identifier(schema))).fetchone() == ((90 if existing else 1),)
            for dtype in ('serial4', 'I'):
                runtime = AsqueelDb(config(dsn, schema, dtype))
                try:
                    assert runtime.migration_plan()['empty']
                    assert not runtime.migration_plan()['skipped']
                    runtime.migrate()
                finally:
                    runtime.closeConnection()
        finally:
            conn.execute(sql.SQL('DROP SCHEMA {} CASCADE').format(sql.Identifier(schema)))
