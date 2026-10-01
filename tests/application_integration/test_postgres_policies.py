"""Row policies survive recipe materialization and application table dispatch."""
from tests.unit_of_work import completed
from datetime import datetime, timezone
from uuid import uuid4

import psycopg
from psycopg import sql
import pytest

from asqueel import SqlDatabaseConfig, build_database
from tests.native_support import postgres_dsn

pytestmark = pytest.mark.postgresql


def test_application_partition_draft_deletion_and_scoped_writes():
    dsn = postgres_dsn()
    schema = 'app_policies_' + uuid4().hex
    with psycopg.connect(dsn, autocommit=True) as observer:
        observer.execute(sql.SQL('CREATE SCHEMA {}').format(sql.Identifier(schema)))
        try:
            observer.execute(sql.SQL('''CREATE TABLE {}.item (
                id integer PRIMARY KEY, organization integer, draft boolean,
                deleted_at timestamptz, label text
            )''').format(sql.Identifier(schema)))
            observer.execute(sql.SQL('''INSERT INTO {}.item VALUES
                (1, 0, NULL, NULL, 'zero'), (2, 1, false, NULL, 'one'),
                (3, 0, true, NULL, 'draft'),
                (4, 0, false, '2026-01-01T00:00:00Z', 'deleted'),
                (5, NULL, false, NULL, 'shared')''').format(sql.Identifier(schema)))

            class Recipe(SqlDatabaseConfig):
                def main(self, root):
                    columns = root.db('policy', conninfo=dsn).schemas().schema(
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

            with build_database(Recipe) as db:
                item = db.table('item')
                query = item.query(order_by='$id')
                with pytest.raises(ValueError):
                    query.fetch()
                assert db.outcome == 'not_started'
                with db.temp_env(organization=0):
                    assert [r['id'] for r in query.fetch()] == [1]
                    marked = item.query(order_by='$id', exclude_draft=False,
                                        exclude_logical_deleted='mark').fetch()
                    assert [r['id'] for r in marked] == [1, 3, 4]
                    assert marked[2]['_isdeleted'] == datetime(2026, 1, 1, tzinfo=timezone.utc)
                with db.temp_env(organization=0, allowed_organizations=[]):
                    assert query.fetch() == []
                with db.temp_env(allowed_organizations=[0]):
                    assert [r['id'] for r in query.fetch()] == [1, 5]
                db.rollback()
                with db.temp_env(organization=0), completed(db):
                    inserted = item.insert({'id': 6, 'label': 'new'})
                    assert inserted.rows[0]['organization'] == 0
                    assert item.raw_update({'label': 'forbidden'}, where='$id=2').rowcount == 0
                    tombstone = datetime(2026, 9, 29, tzinfo=timezone.utc)
                    assert item.soft_delete(tombstone, '$id=6').rows[0]['deleted_at'] == tombstone
                    assert item.query(where='$id=6').fetch() == []
                    assert item.restore('$id=6').rows[0]['deleted_at'] is None
                    assert item.query(where='$id=6').fetch()[0]['label'] == 'new'
                persisted = observer.execute(sql.SQL(
                    'SELECT organization, deleted_at, label FROM {}.item WHERE id=6'
                ).format(sql.Identifier(schema))).fetchone()
                assert persisted == (0, None, 'new')
                assert observer.execute(sql.SQL('SELECT label FROM {}.item WHERE id=2')
                                        .format(sql.Identifier(schema))).fetchone() == ('one',)
        finally:
            observer.execute(sql.SQL('DROP SCHEMA {} CASCADE').format(sql.Identifier(schema)))
