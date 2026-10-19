"""Selection writes through the write cycle and the logical-deletion cascade as legacy (Macro 6, Phase 4)."""
from datetime import datetime

import pytest

from asqueel import SqlTable
from tests.option_tables_support import IMPLEMENTATIONS, migrated_db

TS = datetime(2026, 1, 1, 12, 0)


class Logged(SqlTable):
    def log(self, *event):
        self.db.currentEnv.setdefault('events', []).append(event)

    def trigger_onUpdating(self, record, old_record=None):
        self.log('onUpdating', self.fullname, record['id'], dict(old_record or {}).get('text'))

    def trigger_onDeleting(self, record):
        self.log('onDeleting', self.fullname, record['id'])


def declare(pkg):
    invoice = pkg.table('invoice', pkey='id', logicalDeletionField='__del_ts', x_table_class=Logged)
    invoice.column('id', size=':22')
    invoice.column('text')
    invoice.column('__del_ts', dtype='DH')
    line = pkg.table('line', pkey='id', logicalDeletionField='__del_ts', x_table_class=Logged)
    line.column('id', size=':22')
    line.column('text')
    line.column('__del_ts', dtype='DH')
    line.column('invoice_id', size=':22').relation('app.invoice.id', onDelete='cascade')
    note = pkg.table('note', pkey='id', logicalDeletionField='__del_ts', x_table_class=Logged)
    note.column('id', size=':22')
    note.column('__del_ts', dtype='DH')
    note.column('invoice_id', size=':22').relation('app.invoice.id', onDelete='setnull')
    tag = pkg.table('tag', pkey='id', x_table_class=Logged)
    tag.column('id', size=':22')
    tag.column('invoice_id', size=':22').relation('app.invoice.id', onDelete='cascade')


@pytest.fixture(params=IMPLEMENTATIONS)
def db(request, tmp_path):
    with migrated_db(request.param, tmp_path, declare) as db:
        db.table('app.invoice').insert({'id': 'o1', 'text': 'a'})
        db.table('app.invoice').insert({'id': 'o2', 'text': 'b'})
        db.table('app.invoice').insert({'id': 'o3', 'text': 'c'})
        db.table('app.line').insert({'id': 'l1', 'invoice_id': 'o1', 'text': 'x'})
        db.table('app.line').insert({'id': 'l2', 'invoice_id': 'o1', 'text': 'y'})
        db.table('app.note').insert({'id': 'n1', 'invoice_id': 'o1'})
        db.table('app.tag').insert({'id': 't1', 'invoice_id': 'o1'})
        db.commit()
        db.currentEnv.pop('events', None)
        yield db


def events(db):
    return db.currentEnv.pop('events', [])


def deleted(db, table):
    rows = db.table(table).query(columns='$id,$__del_ts', excludeLogicalDeleted=False, order_by='$id').fetch()
    return {row['id']: row['__del_ts'] for row in rows}


def test_query_update_writes_record_by_record_through_the_triggers(db):
    pkeys = db.table('app.invoice').query(where='$id IN :ids', ids=['o2', 'o3']).update({'text': 'z'})
    assert sorted(pkeys) == ['o2', 'o3']
    assert sorted(events(db)) == [('onUpdating', 'app.invoice', 'o2', 'b'), ('onUpdating', 'app.invoice', 'o3', 'c')]
    texts = db.table('app.invoice').query(columns='$id,$text', order_by='$id').fetchAsDict(key='id')
    assert [texts[key]['text'] for key in ('o1', 'o2', 'o3')] == ['a', 'z', 'z']


def test_query_update_takes_a_callable_updater(db):
    def updater(row):
        row['text'] = row['text'].upper()

    db.table('app.invoice').query(where='$id=:pk', pk='o2').update(updater)
    assert db.table('app.invoice').query(columns='$text', where='$id=:pk', pk='o2').fetchRecord()['text'] == 'B'


def test_query_delete_deletes_record_by_record_through_the_triggers(db):
    rows = db.table('app.invoice').query(where='$id=:pk', pk='o1').delete()
    assert [row['id'] for row in rows] == ['o1']
    log = events(db)
    assert ('onDeleting', 'app.invoice', 'o1') in log
    assert ('onDeleting', 'app.line', 'l1') in log and ('onDeleting', 'app.tag', 't1') in log
    assert db.table('app.line').query(columns='$id', excludeLogicalDeleted=False).fetch() == []


def test_sql_update_and_sql_delete_still_skip_the_triggers(db):
    assert db.table('app.invoice').query(where='$id=:pk', pk='o2').sql_update({'text': 'q'}) == 1
    assert db.table('app.invoice').query(where='$id=:pk', pk='o3').sql_delete() == 1
    assert events(db) == []


def test_logical_deletion_cascades_to_cascade_children_with_their_own_field(db):
    invoice = db.table('app.invoice')
    old = dict(invoice.query(columns='*', where='$id=:pk', pk='o1').fetchRecord())
    invoice.update({**old, '__del_ts': TS}, old_record=old)
    assert deleted(db, 'app.line') == {'l1': TS, 'l2': TS}
    assert deleted(db, 'app.note') == {'n1': None}
    assert db.table('app.tag').query(columns='$id').fetchPkeys() == ['t1']
    assert ('onUpdating', 'app.line', 'l1', 'x') in events(db)


def test_clearing_the_logical_deletion_restores_the_cascade_children(db):
    invoice = db.table('app.invoice')
    old = dict(invoice.query(columns='*', where='$id=:pk', pk='o1').fetchRecord())
    invoice.update({**old, '__del_ts': TS}, old_record=old)
    assert deleted(db, 'app.line') == {'l1': TS, 'l2': TS}
    invoice.update({**old, '__del_ts': None}, old_record={**old, '__del_ts': TS})
    assert deleted(db, 'app.line') == {'l1': None, 'l2': None}


def test_an_update_without_old_record_does_not_cascade(db):
    db.table('app.invoice').update({'id': 'o1', '__del_ts': TS})
    assert deleted(db, 'app.line') == {'l1': None, 'l2': None}
