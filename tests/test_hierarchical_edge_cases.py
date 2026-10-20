"""Hierarchical writes outside the legacy full-record path, and the write gate message."""
import datetime

import pytest

from asqueel.contracts import UnsupportedFeatureError
from tests.option_tables_support import IMPLEMENTATIONS, migrated_db, row


def category(package, counter=False):
    table = package.table('category', name_long='Category', name_plural='Categories')
    table.options().sys_fields()
    table.options().hierarchical('code')
    if counter:
        table.options().auto_counter()
    table.column('code')
    table.column('description')


def ranked(package):
    category(package, counter=True)


@pytest.fixture(params=IMPLEMENTATIONS)
def implementation(request):
    return request.param


def test_a_partial_update_keeps_the_paths_of_the_node_and_its_children(implementation, tmp_path):
    with migrated_db(implementation, tmp_path, ranked) as db:
        table = db.table('app.category')
        a = table.insert({'code': 'a'})
        b = table.insert({'code': 'b', 'parent_id': a['id']})
        c = table.insert({'code': 'c', 'parent_id': b['id']})
        table.update({'id': b['id'], 'description': 'renamed'}, old_record=row(table, b['id']))
        assert row(table, b['id'], '$hierarchical_code,$hierarchical_pkey,$_h_count,$description') == {
            'hierarchical_code': 'a/b', 'hierarchical_pkey': f"{a['id']}/{b['id']}",
            '_h_count': '0101', 'description': 'renamed'}
        assert row(table, c['id'], '$hierarchical_code')['hierarchical_code'] == 'a/b/c'


def test_a_logically_deleted_sibling_keeps_its_position(implementation, tmp_path):
    with migrated_db(implementation, tmp_path, ranked) as db:
        table = db.table('app.category')
        table.insert({'code': 'first'})
        second = table.insert({'code': 'second'})
        old = row(table, second['id'])
        table.update(dict(old, __del_ts=datetime.datetime.now(datetime.timezone.utc)), old_record=old)
        third = table.insert({'code': 'third'})
        assert third['_row_count'] == 3


def test_a_stored_position_beyond_the_bound_does_not_block_other_changes(tmp_path):
    with migrated_db('sqlite', tmp_path, ranked) as db:
        table = db.table('app.category')
        legacy = table.insert({'code': 'legacy'})
        # A legacy database can hold a 1296th sibling: write it as the legacy did.
        table.sql_update({'id': legacy['id'], '_row_count': 1296, '_h_count': ''})
        old = row(table, legacy['id'])
        table.update(dict(old, description='still writable'), old_record=old)
        assert row(table, legacy['id'], '$description')['description'] == 'still writable'


def test_a_hierarchical_counter_can_use_a_custom_field(tmp_path):
    def declare(package):
        table = package.table('category', name_long='Category')
        table.options().sys_fields()
        table.options().hierarchical('code')
        table.options().auto_counter(field='pos')
        table.column('code')

    with migrated_db('sqlite', tmp_path, declare) as db:
        item = db.table('app.category').insert({'code': 'first'})
        assert (item['pos'], item['_h_count']) == (1, '01')


def test_the_refused_options_are_named_in_declaration_order(tmp_path):
    def declare(package):
        table = package.table('hashed', name_long='Hashed')
        table.options().sys_fields()
        table.options().record_hash()
        table.options().audit('lazy')
        table.column('title')

    with migrated_db('sqlite', tmp_path, declare) as db:
        with pytest.raises(UnsupportedFeatureError, match='option record_hash, option audit'):
            db.table('app.hashed').insert({'title': 'x'})
