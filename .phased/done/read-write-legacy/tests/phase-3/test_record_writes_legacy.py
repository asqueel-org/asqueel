"""Single-record writes as legacy: serialized composite keys, insertOrUpdate, Bag in X columns,
sql_insert assigning keys, delete reread, table lock and for_update modes (Macro 6, Phase 3)."""
from datetime import date

import pytest
from genro_bag import Bag

from asqueel import SqlTable
from asqueel.contracts import UnsupportedFeatureError
from tests.option_tables_support import IMPLEMENTATIONS, migrated_db


class Note(SqlTable):
    def trigger_onUpdating(self, record, old_record=None):
        self.db.currentEnv.setdefault('events', []).append(('onUpdating', dict(old_record or {}).get('text')))

    def trigger_onDeleting(self, record):
        self.db.currentEnv.setdefault('events', []).append(('onDeleting', dict(record)))


def declare(pkg):
    note = pkg.table('note', pkey='id', x_table_class=Note)
    note.column('id', size=':22')
    note.column('text')
    note.column('data', dtype='X')
    counter = pkg.table('counter', pkey='id')
    counter.column('id', dtype='L')
    counter.column('text')
    line = pkg.table('line', pkey='doc_pos')
    line.column('doc', dtype='L')
    line.column('pos', dtype='L')
    line.column('text')
    line.compositeColumn('doc_pos', columns='doc,pos')
    entry = pkg.table('entry', pkey='code_day')
    entry.column('code')
    entry.column('day', dtype='D')
    entry.compositeColumn('code_day', columns='code,day')


@pytest.fixture(params=IMPLEMENTATIONS)
def db(request, tmp_path):
    with migrated_db(request.param, tmp_path, declare) as db:
        yield db


def events(db):
    return db.currentEnv.pop('events', [])


def test_a_composite_key_is_assigned_in_the_serialized_form_read_by_the_composite_column(db):
    table = db.table('app.line')
    record = table.insert({'doc': 1, 'pos': 2, 'text': 'a'})
    assert record['doc_pos'] == '[1, 2]'
    assert table.query(columns='$doc_pos').fetchRecord()['doc_pos'] == '[1, 2]'


def test_a_composite_key_with_a_date_member_carries_its_type(db):
    table = db.table('app.entry')
    record = table.insert({'code': 'a', 'day': date(2026, 1, 1)})
    assert record['code_day'] == '["a", "2026-01-01::D"]'
    assert table.query(columns='$code_day').fetchRecord()['code_day'] == record['code_day']
    table.delete(record['code_day'])
    assert table.query(columns='$code').fetch() == []


def test_update_and_delete_take_the_serialized_composite_key(db):
    table = db.table('app.line')
    table.insert({'doc': 1, 'pos': 2, 'text': 'a'})
    table.update({'text': 'b'}, pkey='[1, 2]')
    assert table.query(columns='$text').fetchRecord()['text'] == 'b'
    table.delete('[1, 2]')
    assert table.query(columns='$doc').fetch() == []


def test_insert_or_update_inserts_a_missing_record_and_returns_it(db):
    table = db.table('app.note')
    record = {'id': 'n1', 'text': 'a'}
    assert table.insertOrUpdate(record) is record
    assert table.query(columns='$text').fetchRecord()['text'] == 'a'


def test_insert_or_update_updates_an_existing_record_with_its_old_values(db):
    table = db.table('app.note')
    table.insert({'id': 'n1', 'text': 'a'})
    events(db)
    record = {'id': 'n1', 'text': 'b'}
    assert table.insertOrUpdate(record) is record
    assert events(db) == [('onUpdating', 'a')]
    assert table.query(columns='$text').fetchRecord()['text'] == 'b'


def test_a_bag_in_an_x_column_is_written_as_xml_and_an_empty_bag_as_null(db):
    table = db.table('app.note')
    data = Bag()
    data['colour'] = 'red'
    table.insert({'id': 'n1', 'data': data})
    table.insert({'id': 'n2', 'data': Bag()})
    rows = table.query(columns='$id,$data', bagFields=True, order_by='$id').fetch()
    assert Bag.from_xml(rows[0]['data'])['colour'] == 'red'
    assert rows[1]['data'] is None


def test_sql_insert_assigns_the_missing_primary_keys(db):
    notes = [{'text': 'a'}, {'text': 'b'}]
    db.table('app.note').sql_insert(notes)
    assert all(len(note['id']) == 22 for note in notes)
    assert notes[0]['id'] != notes[1]['id']
    counters = [{'text': 'a'}, {'text': 'b'}]
    db.table('app.counter').sql_insert(counters)
    assert [counter['id'] for counter in counters] == [1, 2]
    single = db.table('app.counter').sql_insert({'text': 'c'})
    assert single['id'] == 3


def test_delete_rereads_a_string_key_and_takes_a_record_as_it_is(db):
    table = db.table('app.note')
    table.insert({'id': 'n1', 'text': 'a'})
    table.insert({'id': 'n2', 'text': 'b'})
    events(db)
    table.delete('n1')
    assert events(db) == [('onDeleting', {'id': 'n1', 'text': 'a', 'data': None})]
    table.delete({'id': 'n2'})
    assert events(db) == [('onDeleting', {'id': 'n2'})]
    assert table.query(columns='$id').fetch() == []


def test_table_lock_runs_inside_the_transaction(db):
    table = db.table('app.note')
    table.lock()
    table.lock(mode='SHARE', nowait=True)
    table.insert({'id': 'n1', 'text': 'a'})
    db.commit()
    assert table.query(columns='$id').fetchPkeys() == ['n1']


def test_for_update_refuses_a_mode_outside_nowait_and_skip_locked(db):
    with pytest.raises(ValueError, match='for_update'):
        db.table('app.note').query(columns='$id', for_update='FOR SHARE').sqltext


def test_for_update_modes_follow_the_dialect(db):
    table = db.table('app.note')
    if db.implementation == 'postgres':
        assert table.query(columns='$id', for_update='NOWAIT').sqltext.endswith('FOR UPDATE OF t0 NOWAIT')
        assert table.query(columns='$id', for_update='SKIP LOCKED').sqltext.endswith('FOR UPDATE OF t0 SKIP LOCKED')
    else:
        with pytest.raises(UnsupportedFeatureError, match='NOWAIT'):
            table.query(columns='$id', for_update='NOWAIT').fetch()
