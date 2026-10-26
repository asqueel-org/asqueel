"""Real locking and atomic update/delete lifecycle through application handles."""
from tests.unit_of_work import completed
from datetime import datetime, timezone
from uuid import uuid4

import psycopg
from psycopg import sql
import pytest

from asqueel import (
    RecordMultipleRowsError, RecordNotFoundError, SqlDatabaseConfig,
    AsqueelDb,
)
from tests.native_support import postgres_dsn
from tests.package_layout_support import write_layout

pytestmark = pytest.mark.postgresql


ITEM = '''
from copy import deepcopy


class Table:
    def config_db(self, pkg):
        item = pkg.table(
            'item', pkey='pk',
            partition_org='org',
            draftField='draft', logicalDeletionField='deleted_at')
        columns = item.columns()
        for name, dtype in [('org', 'I'), ('id', 'I'), ('name', 'T'),
                            ('draft', 'B'), ('deleted_at', 'DHZ')]:
            columns.column(name, dtype=dtype)
        item.composites().compositeColumn('pk', columns='org,id')

    def trigger_onUpdating(self, record, old_record=None):
        self.events.append(('updating', deepcopy(record), deepcopy(old_record)))
        old_record['name'] = 'damaged hook argument'
        record['name'] = record['name'].strip()
        if getattr(self, 'replace_key', None) is not None:
            record['id'] = self.replace_key
        self.db.table('app.audit').insert({'event': 'updating'})
        if getattr(self, 'probe_lock', None):
            self.probe_lock()

    def trigger_onUpdated(self, record, old_record=None):
        self.events.append(('updated', deepcopy(record), deepcopy(old_record)))
        self.db.table('app.audit').insert({'event': 'updated'})
        if getattr(self, 'fail', False):
            raise ValueError('update hook failure')

    def trigger_onDeleting(self, record):
        self.events.append(('deleting', deepcopy(record)))
        record['name'] = 'damaged hook argument'
        self.db.table('app.audit').insert({'event': 'deleting'})

    def trigger_onDeleted(self, record):
        self.events.append(('deleted', deepcopy(record)))
        self.db.table('app.audit').insert({'event': 'deleted'})
        if getattr(self, 'fail', False):
            raise ValueError('delete hook failure')
'''


@pytest.fixture
def hooked_database(tmp_path):
    dsn = postgres_dsn()
    path = write_layout(tmp_path / 'app', item=ITEM)
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
                    tables = root.db('hooks', implementation='postgres', conninfo=dsn).packages().package(
                        'app', sqlschema=schema, sqlprefix=False, path=path).tables()
                    audit = tables.table('audit', pkey='id').columns()
                    audit.column('id', dtype='serial')
                    audit.column('event', dtype='T')

            db = AsqueelDb(Recipe).session()
            try:
                with db.tempEnv(current_org=0):
                    db.table('app.item').events = []
                    yield db, observer, schema
            finally:
                db.closeConnection()
                db.shared.close()
        finally:
            observer.execute(sql.SQL('DROP SCHEMA {} CASCADE').format(sql.Identifier(schema)))


def stored(id=0, name='original', draft=True):
    """The row of partition 0 as the fixture stores it, passed by the caller as old_record."""
    return {'org': 0, 'id': id, 'name': name, 'draft': draft, 'deleted_at': None}


def persisted(observer, schema):
    return observer.execute(sql.SQL('SELECT org,id,name FROM {}.item ORDER BY org,id')
                            .format(sql.Identifier(schema))).fetchall()


def audit_events(observer, schema):
    return observer.execute(sql.SQL('SELECT event FROM {}.audit ORDER BY id')
                            .format(sql.Identifier(schema))).fetchall()


def test_full_records_old_snapshot_composite_zero_key_and_atomic_hooks(hooked_database):
    db, observer, schema = hooked_database
    table = db.table('app.item')
    old = stored()
    record = {'org': 0, 'id': 0, 'name': ' changed '}
    assert table.update(record, old_record=old) is record
    assert record['name'] == 'changed'
    before, after = table.events
    assert before[2]['name'] == 'original'
    assert after[2]['name'] == old['name'] == 'damaged hook argument'  # the caller's old_record
    assert after[1]['name'] == 'changed'
    assert persisted(observer, schema)[0] == (0, 0, 'original')
    assert audit_events(observer, schema) == []
    db.commit()
    assert persisted(observer, schema)[0] == (0, 0, 'changed')
    assert audit_events(observer, schema) == [('updating',), ('updated',)]
    table.delete(stored(name='changed'))
    assert table.events[-2][1]['name'] == 'changed'
    assert table.events[-1][1]['name'] == 'damaged hook argument'
    db.commit()
    assert persisted(observer, schema) == [(0, 1, 'second'), (1, 0, 'other partition')]
    assert audit_events(observer, schema)[-2:] == [('deleting',), ('deleted',)]


def test_fetch_record_with_lock_includes_the_draft_row(hooked_database):
    db, observer, schema = hooked_database
    old = db.table('app.item').query(where='$org=0 AND $id=0', for_update=True,
                                     exclude_draft=False).fetchRecord()
    assert old['draft'] is True


@pytest.mark.parametrize('operation', ['update', 'delete'])
def test_post_hook_failure_rolls_back_write_and_cross_table_effects(hooked_database, operation):
    db, observer, schema = hooked_database
    table = db.table('app.item')
    table.fail = True
    with pytest.raises(ValueError, match='hook failure'):
        with completed(db):
            if operation == 'update':
                table.update({'org': 0, 'id': 0, 'name': 'changed'}, old_record=stored())
            else:
                table.delete(stored())
    assert persisted(observer, schema)[0] == (0, 0, 'original')
    assert audit_events(observer, schema) == []


@pytest.mark.xfail(strict=True, reason='asqueel#17: hooked update/delete of exactly one locked record selected by a where')
@pytest.mark.parametrize('operation', ['update', 'delete'])
def test_exactly_one_locked_record_before_any_hook(hooked_database, operation):
    db, observer, schema = hooked_database
    table = db.table('app.item')
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
    table = db.table('app.item')
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
        old = dict(table.query(where='$org=0 AND $id=0', for_update=True, exclude_draft=False).fetchRecord())
        table.update(dict(old, name='locked'), old_record=old)
    assert attempted == [True]
    assert persisted(observer, schema)[0] == (0, 0, 'locked')


def test_soft_delete_restore_call_update_hooks_with_deleted_record_visible(hooked_database):
    db, observer, schema = hooked_database
    table = db.table('app.item')
    marker = datetime(2026, 9, 29, tzinfo=timezone.utc)
    deleted = dict(stored(1, 'second', draft=False), deleted_at=marker)
    with completed(db):
        table.update({'org': 0, 'id': 1, 'name': 'second', 'deleted_at': marker},
                     old_record=stored(1, 'second', draft=False))
        table.update({'org': 0, 'id': 1, 'name': 'second', 'deleted_at': None}, old_record=deleted)
    assert [event[0] for event in table.events] == ['updating', 'updated'] * 2
    assert table.events[2][2]['deleted_at'] == marker
    assert audit_events(observer, schema) == [('updating',), ('updated',)] * 2


def test_logically_deleted_record_is_hidden_until_restored(hooked_database):
    db, observer, schema = hooked_database
    table = db.table('app.item')
    marker = datetime(2026, 9, 29, tzinfo=timezone.utc)
    with completed(db):
        table.update({'org': 0, 'id': 1, 'name': 'second', 'deleted_at': marker},
                     old_record=stored(1, 'second', draft=False))
        assert table.query(where='$id=1').fetch() == []
        table.update({'org': 0, 'id': 1, 'name': 'second', 'deleted_at': None},
                     old_record=dict(stored(1, 'second', draft=False), deleted_at=marker))
        assert table.query(where='$id=1').fetch()[0]['deleted_at'] is None


def test_hook_key_change_uses_saved_old_key_and_raw_allows_batch_writes(hooked_database):
    db, observer, schema = hooked_database
    table = db.table('app.item')
    table.replace_key = 7
    with completed(db):
        result = table.update({'org': 0, 'id': 0, 'name': 'moved'}, old_record=stored())
        assert result['id'] == 7
        assert table.events[-1][2]['id'] == 0
        assert db.table('app.audit').query(where='true').sql_update({'event': 'batch'}) == 2
    assert (0, 7, 'moved') in persisted(observer, schema)
    assert (0, 0, 'original') not in persisted(observer, schema)
    assert audit_events(observer, schema) == [('batch',), ('batch',)]


def test_deferred_registered_in_hook_shares_commit_and_observer_visibility(hooked_database):
    db, observer, schema = hooked_database
    table = db.table('app.item')
    old = stored()
    events = []

    def before():
        assert db.currentEnv['onCommittingStep'] is True
        assert persisted(observer, schema)[0][2] == 'original'
        db.table('app.audit').insert({'event': 'deferred'})

    def after():
        events.append((db.currentEnv['onCommittingStep'], persisted(observer, schema)[0][2],
                       audit_events(observer, schema)))

    def updated(record, old_record=None):
        assert table.currentTrigger.event == 'update'
        assert table.currentTrigger.old_record is old
        db.deferToCommit(before)
        db.deferAfterCommit(after)

    table.trigger_onUpdated = updated
    table.update({'org': 0, 'id': 0, 'name': 'changed'}, old_record=old)
    assert events == []
    db.commit()
    assert events == [(True, 'changed', [('updating',), ('deferred',)])]
    assert 'onCommittingStep' not in db.currentEnv
    assert db.currentTrigger is None


def test_precommit_exception_rolls_back_real_writes_and_skips_after(hooked_database):
    db, observer, schema = hooked_database
    events = []

    def fail():
        db.table('app.audit').insert({'event': 'must rollback'})
        raise ValueError('pre-commit failure')

    with pytest.raises(ValueError, match='pre-commit failure'):
        with completed(db):
            db.table('app.item').update({'org': 0, 'id': 0, 'name': 'changed'}, old_record=stored())
            db.deferToCommit(fail)
            db.deferAfterCommit(lambda: events.append('after'))
    assert persisted(observer, schema)[0][2] == 'original'
    assert audit_events(observer, schema) == []
    assert events == []
    db.table('app.item').update({'org': 0, 'id': 0, 'name': 'recovered'}, old_record=stored())
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

    db.table('app.item').update({'org': 0, 'id': 0, 'name': 'changed'}, old_record=stored())
    db.deferToCommit(fail)
    db.deferAfterCommit(lambda: events.append('after'))
    with pytest.raises(TransactionStateError):
        db.commit()
    db.rollback()
    assert persisted(observer, schema)[0][2] == 'original'
    assert audit_events(observer, schema) == []
    assert events == []
