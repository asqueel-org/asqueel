"""Relational partitions and multiple dimensions against real PostgreSQL."""
from uuid import uuid4

import psycopg
from psycopg import sql
import pytest

from genro_sql import PostgresCompiler, PostgresDatabase, SqlBuilder, SqlEnvironment, resolve_model
from tests.native_support import postgres_dsn

pytestmark = pytest.mark.postgresql


@pytest.fixture
def relational_database():
    schema = 'relational_policy_' + uuid4().hex
    dsn = postgres_dsn()
    with psycopg.connect(dsn, autocommit=True) as connection:
        connection.execute(sql.SQL('CREATE SCHEMA {}').format(sql.Identifier(schema)))
        try:
            connection.execute(sql.SQL('''CREATE TABLE {}.organization (
                id integer PRIMARY KEY, region integer, draft boolean, deleted_at timestamptz
            )''').format(sql.Identifier(schema)))
            connection.execute(sql.SQL('''CREATE TABLE {}.item (
                id integer PRIMARY KEY, organization_id integer REFERENCES {}.organization(id), enabled boolean
            )''').format(sql.Identifier(schema), sql.Identifier(schema)))
            connection.execute(sql.SQL('''INSERT INTO {}.organization VALUES
                (1,0,TRUE,'2026-01-01T00:00:00Z'),(2,1,FALSE,NULL),
                (3,NULL,FALSE,NULL),(4,0,FALSE,NULL)''').format(sql.Identifier(schema)))
            connection.execute(sql.SQL('''INSERT INTO {}.item VALUES
                (1,1,FALSE),(2,2,FALSE),(3,1,TRUE),(4,3,FALSE),(5,NULL,FALSE),
                (6,4,FALSE),(7,4,NULL),(8,NULL,NULL),(9,1,NULL)''').format(sql.Identifier(schema)))
            builder = SqlBuilder()
            tables = builder.source.db('relational_policy').schemas().schema(
                'app', x_sql_schema=schema).tables()
            organization = tables.table('organization', pkey='id', x_draft_field='draft',
                                        x_logical_deletion_field='deleted_at').columns()
            for name, dtype in [('id', 'I'), ('region', 'I'), ('draft', 'B'), ('deleted_at', 'DHZ')]:
                organization.column(name, dtype=dtype)
            item = tables.table('item', pkey='id', x_partitions=[
                {'field': '@organization.region', 'current': 'region', 'allowed': 'allowed_regions'},
                {'field': 'enabled', 'current': 'enabled', 'allowed': 'allowed_enabled'},
            ]).columns()
            item.column('id', dtype='I')
            item.column('organization_id', dtype='I').relation('app.organization.id', x_name='organization')
            item.column('enabled', dtype='B')
            yield dsn, resolve_model(builder)
        finally:
            connection.execute(sql.SQL('DROP SCHEMA {} CASCADE').format(sql.Identifier(schema)))


def test_related_partition_zero_and_false_intersect_without_target_visibility_filters(relational_database):
    dsn, model = relational_database
    environment = SqlEnvironment()
    compiler = PostgresCompiler(model, environment=environment)
    with PostgresDatabase(dsn, environment=environment) as database:
        with environment.temp_env(region=0, enabled=False):
            query = compiler.select('item', columns='$id,@organization.draft,@organization.deleted_at',
                                     where='$id=1 OR $id=2 OR $id=3 OR $id=6', order_by='$id')
            rows = database.execute(query).rows
            assert [row['id'] for row in rows] == [1, 6]
            # The target is draft+deleted, but its own root policies do not
            # silently change the semantics of a relation traversal.
            assert rows[0]['organization_draft'] is True
            assert rows[0]['organization_deleted_at'] is not None
            assert [row['id'] for row in database.execute(
                compiler.select('organization', columns='$id', order_by='$id')).rows] == [2, 3, 4]


def test_allowed_dimensions_include_nulls_and_empty_set_still_denies_all(relational_database):
    dsn, model = relational_database
    environment = SqlEnvironment()
    compiler = PostgresCompiler(model, environment=environment)
    with PostgresDatabase(dsn, environment=environment) as database:
        with environment.temp_env(allowed_regions=[0], allowed_enabled=[False]):
            rows = database.execute(compiler.select('item', columns='$id', order_by='$id')).rows
            # NULL on either dimension is included, also when LEFT JOIN found
            # no organization. Wrong non-NULL region/boolean stay excluded.
            assert [row['id'] for row in rows] == [1, 4, 5, 6, 7, 8, 9]
        with environment.temp_env(allowed_regions=[], allowed_enabled=[False]):
            assert database.execute(compiler.select('item', columns='$id')).rows == []
        with environment.temp_env(region=None, enabled=False):
            rows = database.execute(compiler.select('item', columns='$id', order_by='$id')).rows
            assert [row['id'] for row in rows] == [4, 5]
