"""sysFields columns are written by their legacy field triggers (asqueel#29)."""
from datetime import timezone

import pytest

from asqueel.contracts import UnsupportedFeatureError
from tests.option_tables_support import IMPLEMENTATIONS, migrated_db, row


def note(package):
    table = package.table('note', name_long='Note')
    table.options().sysFields()
    table.column('title')


@pytest.fixture(params=IMPLEMENTATIONS)
def db(request, tmp_path):
    with migrated_db(request.param, tmp_path, note) as database:
        yield database


def test_triggers_are_column_attributes_not_legacy_data(db):
    columns = db.table('app.note').model.columns
    assert columns['__ins_ts'].attributes['onInserting'] == 'setTSNow'
    assert columns['__mod_ts'].attributes['onUpdating'] == 'setTSNow'
    assert columns['__mod_user'].attributes['onUpdating'] == 'setCurrentUser'
    assert not any(key.startswith('x_') for column in columns.values() for key in column.attributes)


def test_insert_fills_key_timestamps_and_users(db):
    db.currentEnv['user'] = 'ada'
    record = db.table('app.note').insert({'title': 'first'})
    assert len(record['id']) == 22
    assert record['__ins_ts'].tzinfo is not None
    assert record['__ins_ts'].utcoffset() == timezone.utc.utcoffset(None)
    assert record['__mod_ts'] is not None
    assert record['__ins_user'] == record['__mod_user'] == 'ada'
    stored = row(db.table('app.note'), record['id'], '$title,$__ins_ts,$__mod_ts,$__ins_user,$__mod_user')
    assert stored['title'] == 'first'
    assert stored['__ins_ts'] is not None and stored['__mod_ts'] is not None
    assert stored['__ins_user'] == stored['__mod_user'] == 'ada'


def test_update_moves_only_the_modification_columns(db):
    table = db.table('app.note')
    db.currentEnv['user'] = 'ada'
    record = table.insert({'title': 'first'})
    old = dict(record)
    db.currentEnv['user'] = 'bob'
    record = dict(old, title='second')
    table.update(record, old_record=old)
    assert record['__mod_user'] == 'bob'
    assert record['__mod_ts'] >= old['__mod_ts']
    stored = row(table, record['id'], '$title,$__ins_user,$__mod_user')
    assert stored == {'title': 'second', '__ins_user': 'ada', '__mod_user': 'bob'}


def test_user_is_none_without_user_in_the_environment(db):
    record = db.table('app.note').insert({'title': 'anonymous'})
    assert record['__ins_user'] is None and record['__mod_user'] is None


def test_options_not_executed_still_refuse_the_write(tmp_path):
    def hashed(package):
        table = package.table('hashed', name_long='Hashed')
        table.options().sysFields()
        table.options().fullUpd()
        table.column('title')

    with migrated_db('sqlite', tmp_path, hashed) as db:
        with pytest.raises(UnsupportedFeatureError, match='option fullUpd'):
            db.table('app.hashed').insert({'title': 'x'})
