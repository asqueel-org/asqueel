"""Row policies survive recipe materialization and application table dispatch."""
from tests.unit_of_work import completed
from datetime import datetime, timezone
from uuid import uuid4

import psycopg
from psycopg import sql
import pytest

from asqueel import SqlDatabaseConfig, AsqueelDb
from tests.native_support import postgres_dsn

pytestmark = pytest.mark.postgresql


@pytest.fixture
def policy_database():
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
                (1, 10, NULL, NULL, 'ten'), (2, 11, false, NULL, 'eleven'),
                (3, 10, true, NULL, 'draft'),
                (4, 10, false, '2026-01-01T00:00:00Z', 'deleted'),
                (5, NULL, false, NULL, 'shared')''').format(sql.Identifier(schema)))

            class Recipe(SqlDatabaseConfig):
                def main(self, root):
                    columns = root.db('policy', implementation='postgres', conninfo=dsn).schemas().schema(
                        'app', sqlname=schema,
                    ).tables().table(
                        'item', pkey='id',
                        partition_organization='organization',
                        draftField='draft', logicalDeletionField='deleted_at',
                    ).columns()
                    for name, dtype in [('id', 'I'), ('organization', 'I'), ('draft', 'B'),
                                        ('deleted_at', 'DHZ'), ('label', 'T')]:
                        columns.column(name, dtype=dtype)

            db = AsqueelDb(Recipe)
            try:
                yield db, observer, schema
            finally:
                db.closeConnection()
        finally:
            observer.execute(sql.SQL('DROP SCHEMA {} CASCADE').format(sql.Identifier(schema)))


def test_application_partition_draft_deletion_and_scoped_writes(policy_database):
    db, observer, schema = policy_database
    item = db.table('app.item')
    query = item.query(order_by='$id')
    assert [r['id'] for r in query.fetch()] == [1, 2, 5]
    # The SQL text is the one of the first compilation: each scope builds its own query.
    with db.tempEnv(current_organization=10):
        assert [r['id'] for r in item.query(order_by='$id').fetch()] == [1]
        marked = item.query(order_by='$id', exclude_draft=False,
                            exclude_logical_deleted='mark').fetch()
        assert [r['id'] for r in marked] == [1, 3, 4]
        assert marked[2]['_isdeleted'] == datetime(2026, 1, 1, tzinfo=timezone.utc)
    with db.tempEnv(current_organization=10, allowed_organization=[]):
        assert [r['id'] for r in item.query(order_by='$id').fetch()] == [1]
    with db.tempEnv(allowed_organization=[10]):
        assert [r['id'] for r in item.query(order_by='$id').fetch()] == [1, 5]
    db.rollback()
    with db.tempEnv(current_organization=10), completed(db):
        item.insert({'id': 6, 'organization': 10, 'label': 'new'})
        assert item.query(where='$id=2').sql_update({'label': 'forbidden'}) == 0
        tombstone = datetime(2026, 9, 29, tzinfo=timezone.utc)
        assert item.update({'id': 6, 'deleted_at': tombstone})['deleted_at'] == tombstone
        assert item.query(where='$id=6').fetch() == []
        assert item.update({'id': 6, 'deleted_at': None})['deleted_at'] is None
        assert item.query(where='$id=6').fetch()[0]['label'] == 'new'
    persisted = observer.execute(sql.SQL(
        'SELECT organization, deleted_at, label FROM {}.item WHERE id=6'
    ).format(sql.Identifier(schema))).fetchone()
    assert persisted == (10, None, 'new')
    assert observer.execute(sql.SQL('SELECT label FROM {}.item WHERE id=2')
                            .format(sql.Identifier(schema))).fetchone() == ('eleven',)


def test_application_insert_fills_the_partition_field(policy_database):
    db, observer, schema = policy_database
    item = db.table('app.item')
    with db.tempEnv(current_organization=10), completed(db):
        assert item.insert({'id': 6, 'label': 'new'})['organization'] == 10
    persisted = observer.execute(sql.SQL('SELECT organization FROM {}.item WHERE id=6')
                                 .format(sql.Identifier(schema))).fetchone()
    assert persisted == (10,)
