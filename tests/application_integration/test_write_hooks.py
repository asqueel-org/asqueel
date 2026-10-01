"""Real locking and atomic update/delete lifecycle through application handles."""
from tests.unit_of_work import completed
from copy import deepcopy
from datetime import datetime, timezone
from uuid import uuid4

import psycopg
from psycopg import sql
import pytest

from asqueel import (
    RecordMultipleRowsError, RecordNotFoundError, SqlDatabaseConfig, SqlTable,
    build_database,
)
from tests.native_support import postgres_dsn

pytestmark = pytest.mark.postgresql


class HookedItem(SqlTable):
    def trigger_onUpdating(self, record, old_record=None):
        self.events.append(('updating', deepcopy(record), deepcopy(old_record)))
        old_record['name'] = 'damaged hook argument'
        record['name'] = record['name'].strip()
        if getattr(self, 'replace_key', None) is not None:
            record['id'] = self.replace_key
        self.db.table('audit').insert({'event': 'updating'})
        if getattr(self, 'probe_lock', None):
            self.probe_lock()

    def trigger_onUpdated(self, record, old_record=None):
        self.events.append(('updated', deepcopy(record), deepcopy(old_record)))
        self.db.table('audit').insert({'event': 'updated'})
        if getattr(self, 'fail', False):
            raise ValueError('update hook failure')

    def trigger_onDeleting(self, record):
        self.events.append(('deleting', deepcopy(record)))
        record['name'] = 'damaged hook argument'
        self.db.table('audit').insert({'event': 'deleting'})

    def trigger_onDeleted(self, record):
        self.events.append(('deleted', deepcopy(record)))
        self.db.table('audit').insert({'event': 'deleted'})
        if getattr(self, 'fail', False):
            raise ValueError('delete hook failure')


@pytest.fixture
def hooked_database():
    dsn = postgres_dsn()
    schema = 'write_hooks_' + uuid4().hex
    with psycopg.connect(dsn, autocommit=True) as observer:
        observer.execute(sql.SQL('CREATE SCHEMA {}').format(sql.Identifier(schema)))
        try:
            observer.execute(sql.SQL('''CREATE TABLE {}.item (
                org integer, id integer, name text, draft boolean,
                deleted_at timestamptz, PRIMARY KEY(org,id))''').format(sql.Identifier(schema)))
            observer.execute(sql.SQL('''INSERT INTO {}.item VALUES
                (0,0,'original',true,NULL),(0,1,'second',false,NULL),
                (1,0,'other partition',false,NULL)''').format(sql.Identifier(schema)))
            observer.execute(sql.SQL('CREATE TABLE {}.audit (id serial PRIMARY KEY, event text)')
                             .format(sql.Identifier(schema)))

            class Recipe(SqlDatabaseConfig):
                def main(self, root):
                    tables = root.db('hooks', conninfo=dsn).schemas().schema(
                        'app', x_sql_schema=schema).tables()
                    columns = tables.table(
                        'item', pkey='org,id', x_table_class=HookedItem,
                        x_partition={'field': 'org', 'current': 'org'},
                        x_draft_field='draft', x_logical_deletion_field='deleted_at',
                    ).columns()
                    for name, dtype in [('org', 'I'), ('id', 'I'), ('name', 'T'),
                                        ('draft', 'B'), ('deleted_at', 'DHZ')]:
                        columns.column(name, dtype=dtype)
                    audit = tables.table('audit', pkey='id').columns()
                    audit.column('id', dtype='I')
                    audit.column('event', dtype='T')

            with build_database(Recipe) as db, db.temp_env(org=0):
                db.table('item').events = []
                yield db, observer, schema
        finally:
            observer.execute(sql.SQL('DROP SCHEMA {} CASCADE').format(sql.Identifier(schema)))


def persisted(observer, schema):
    return observer.execute(sql.SQL('SELECT org,id,name FROM {}.item ORDER BY org,id')
                            .format(sql.Identifier(schema))).fetchall()


def audit_events(observer, schema):
    return observer.execute(sql.SQL('SELECT event FROM {}.audit ORDER BY id')
                            .format(sql.Identifier(schema))).fetchall()


def test_full_records_old_snapshot_composite_zero_key_and_atomic_hooks(hooked_database):
    db, observer, schema = hooked_database
    table = db.table('item')
    result = table.update({'org': 0, 'id': 0, 'name': ' changed '})
    assert result.rows[0]['name'] == 'changed'
    before, after = table.events
    assert before[1]['draft'] is True  # Write locking includes draft rows.
    assert before[2]['name'] == after[2]['name'] == 'original'
    assert after[1]['name'] == 'changed'
    assert persisted(observer, schema)[0] == (0, 0, 'original')
    assert audit_events(observer, schema) == []
    db.commit()
    assert persisted(observer, schema)[0] == (0, 0, 'changed')
    assert audit_events(observer, schema) == [('updating',), ('updated',)]
    table.delete({'org': 0, 'id': 0})
    assert table.events[-2][1]['name'] == 'changed'
    assert table.events[-1][1]['name'] == 'damaged hook argument'
    db.commit()
    assert persisted(observer, schema) == [(0, 1, 'second'), (1, 0, 'other partition')]
    assert audit_events(observer, schema)[-2:] == [('deleting',), ('deleted',)]


@pytest.mark.parametrize('operation', ['update', 'delete'])
def test_post_hook_failure_rolls_back_write_and_cross_table_effects(hooked_database, operation):
    db, observer, schema = hooked_database
    table = db.table('item')
    table.fail = True
    with pytest.raises(ValueError, match='hook failure'):
        with completed(db):
            if operation == 'update':
                table.update({'org': 0, 'id': 0, 'name': 'changed'})
            else:
                table.delete({'org': 0, 'id': 0})
    assert persisted(observer, schema)[0] == (0, 0, 'original')
    assert audit_events(observer, schema) == []


@pytest.mark.parametrize('operation', ['update', 'delete'])
def test_exactly_one_locked_record_before_any_hook(hooked_database, operation):
    db, observer, schema = hooked_database
    table = db.table('item')
    for where, error in [('$id=99', RecordNotFoundError), ('$org=0', RecordMultipleRowsError),
                         ('$org=1', RecordNotFoundError)]:
        with pytest.raises(error):
            with completed(db):
                if operation == 'update':
                    table.update({'name': 'changed'}, where=where)
                else:
                    table.delete(where=where)
    assert table.events == []
    assert audit_events(observer, schema) == []


def test_pre_hook_holds_postgres_row_lock(hooked_database):
    db, observer, schema = hooked_database
    table = db.table('item')
    attempted = []

    def probe():
        with psycopg.connect(postgres_dsn(), autocommit=True) as contender:
            contender.execute("SET lock_timeout = '100ms'")
            with pytest.raises(psycopg.errors.LockNotAvailable):
                contender.execute(sql.SQL("UPDATE {}.item SET name='contender' WHERE org=0 AND id=0")
                                  .format(sql.Identifier(schema)))
            attempted.append(True)

    table.probe_lock = probe
    with completed(db):
        table.update({'org': 0, 'id': 0, 'name': 'locked'})
    assert attempted == [True]
    assert persisted(observer, schema)[0] == (0, 0, 'locked')


def test_soft_delete_restore_call_update_hooks_with_deleted_record_visible(hooked_database):
    db, observer, schema = hooked_database
    table = db.table('item')
    marker = datetime(2026, 9, 29, tzinfo=timezone.utc)
    with completed(db):
        table.soft_delete(marker, '$id=1')
        assert table.query(where='$id=1').fetch() == []
        table.restore('$id=1')
        assert table.query(where='$id=1').fetch()[0]['deleted_at'] is None
    assert [event[0] for event in table.events] == ['updating', 'updated'] * 2
    assert table.events[2][2]['deleted_at'] == marker
    assert audit_events(observer, schema) == [('updating',), ('updated',)] * 2


def test_hook_key_change_uses_saved_old_key_and_raw_allows_batch_writes(hooked_database):
    db, observer, schema = hooked_database
    table = db.table('item')
    table.replace_key = 7
    with completed(db):
        result = table.update({'org': 0, 'id': 0, 'name': 'moved'})
        assert result.rows[0]['id'] == 7
        assert table.events[-1][2]['id'] == 0
        assert db.table('audit').raw_update({'event': 'batch'}, where='true').rowcount == 2
    assert (0, 7, 'moved') in persisted(observer, schema)
    assert (0, 0, 'original') not in persisted(observer, schema)
    assert audit_events(observer, schema) == [('batch',), ('batch',)]


def test_deferred_registered_in_hook_shares_commit_and_observer_visibility(hooked_database):
    db, observer, schema = hooked_database
    table = db.table('item')
    events = []

    def before():
        assert db.currentEnv['onCommittingStep'] is True
        assert persisted(observer, schema)[0][2] == 'original'
        db.table('audit').insert({'event': 'deferred'})

    def after():
        events.append((db.currentEnv['onCommittingStep'], persisted(observer, schema)[0][2],
                       audit_events(observer, schema)))

    def updated(record, old_record=None):
        assert table.currentTrigger.event == 'update'
        assert table.currentTrigger.old_record['name'] == 'original'
        db.deferToCommit(before)
        db.deferAfterCommit(after)

    table.trigger_onUpdated = updated
    table.update({'org': 0, 'id': 0, 'name': 'changed'})
    assert events == []
    db.commit()
    assert events == [(True, 'changed', [('updating',), ('deferred',)])]
    assert 'onCommittingStep' not in db.currentEnv
    assert db.currentTrigger is None


def test_precommit_exception_rolls_back_real_writes_and_skips_after(hooked_database):
    db, observer, schema = hooked_database
    events = []

    def fail():
        db.table('audit').insert({'event': 'must rollback'})
        raise ValueError('pre-commit failure')

    with pytest.raises(ValueError, match='pre-commit failure'):
        with completed(db):
            db.table('item').update({'org': 0, 'id': 0, 'name': 'changed'})
            db.deferToCommit(fail)
            db.deferAfterCommit(lambda: events.append('after'))
    assert persisted(observer, schema)[0][2] == 'original'
    assert audit_events(observer, schema) == []
    assert events == []
    db.table('item').update({'org': 0, 'id': 0, 'name': 'recovered'})
    db.commit()
    assert persisted(observer, schema)[0][2] == 'recovered'


def test_caught_precommit_sql_failure_cannot_announce_commit(hooked_database):
    from asqueel import CompiledQuery, TransactionStateError
    db, observer, schema = hooked_database
    events = []

    def fail():
        try:
            db.execute(CompiledQuery('SELECT 1 / 0'))
        except psycopg.errors.DivisionByZero:
            pass

    db.table('item').update({'org': 0, 'id': 0, 'name': 'changed'})
    db.deferToCommit(fail)
    db.deferAfterCommit(lambda: events.append('after'))
    with pytest.raises(TransactionStateError):
        db.commit()
    db.rollback()
    assert persisted(observer, schema)[0][2] == 'original'
    assert audit_events(observer, schema) == []
    assert events == []
