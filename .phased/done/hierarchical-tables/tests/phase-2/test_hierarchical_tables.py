"""Hierarchical tables read and written as legacy develop (asqueel#30), on both dialects."""
import datetime

import pytest

from asqueel.contracts import UnsupportedFeatureError
from asqueel.errors import BusinessLogicException, RecordException
from tests.option_tables_support import IMPLEMENTATIONS, migrated_db, row


def category(package, columns: str | None = 'code', counter=False, **options):
    table = package.table('category', name_long='Category', name_plural='Categories')
    table.options().sys_fields()
    table.options().hierarchical(columns, **options)
    if counter:
        table.options().auto_counter()
    table.column('code')
    table.column('description')


@pytest.fixture(params=IMPLEMENTATIONS)
def implementation(request):
    return request.param


@pytest.fixture
def db(implementation, tmp_path):
    with migrated_db(implementation, tmp_path, category) as database:
        yield database


def insert(table, code, parent=None, **values):
    return table.insert(dict(values, code=code, parent_id=parent['id'] if parent else None))


def change(table, record, **values):
    old = row(table, record['id'])
    new = dict(old, **values)
    table.update(new, old_record=old)
    return new


def tree(table):
    """a > b > c, returned as records."""
    a = insert(table, 'a')
    b = insert(table, 'b', a)
    c = insert(table, 'c', b)
    return a, b, c


def test_insert_materializes_the_paths_of_the_pkey_and_of_the_fields(db):
    table = db.table('app.category')
    a, b, c = tree(table)
    assert [r['hierarchical_code'] for r in (a, b, c)] == ['a', 'a/b', 'a/b/c']
    assert c['hierarchical_pkey'] == '/'.join((a['id'], b['id'], c['id']))
    assert (a['_parent_h_code'], b['_parent_h_code'], c['_parent_h_code']) == (None, 'a', 'a/b')
    assert c['_parent_h_pkey'] == b['hierarchical_pkey']
    stored = row(table, c['id'], '$hierarchical_code,$hierarchical_pkey')
    assert stored == {'hierarchical_code': 'a/b/c', 'hierarchical_pkey': c['hierarchical_pkey']}


def test_hlevel_and_child_count_are_read_for_every_node(db):
    table = db.table('app.category')
    a, *_ = tree(table)
    insert(table, 'b2', a)
    levels = {r['code']: (r['hlevel'], r['child_count'])
              for r in table.query(columns='$code,$hlevel,$child_count').fetch()}
    assert levels == {'a': (1, 2), 'b': (2, 1), 'c': (3, 0), 'b2': (2, 0)}


def test_default_order_is_the_first_hierarchical_path(db):
    table = db.table('app.category')
    a = insert(table, 'z')
    insert(table, 'm', a)
    insert(table, 'b')
    assert [r['code'] for r in table.query(columns='$code').fetch()] == ['b', 'z', 'm']


def test_renaming_a_node_rewrites_the_paths_of_its_subtree(db):
    table = db.table('app.category')
    a, b, c = tree(table)
    change(table, a, code='x')
    assert row(table, b['id'], '$hierarchical_code,$_parent_h_code') == {
        'hierarchical_code': 'x/b', '_parent_h_code': 'x'}
    assert row(table, c['id'], '$hierarchical_code')['hierarchical_code'] == 'x/b/c'


def test_moving_a_node_rewrites_its_paths_and_those_of_its_subtree(db):
    table = db.table('app.category')
    a, _, c = tree(table)
    d = insert(table, 'd', c)
    change(table, c, parent_id=a['id'])
    assert row(table, c['id'], '$hierarchical_code,$hierarchical_pkey') == {
        'hierarchical_code': 'a/c', 'hierarchical_pkey': f"{a['id']}/{c['id']}"}
    assert row(table, d['id'], '$hierarchical_code')['hierarchical_code'] == 'a/c/d'


def test_moving_a_node_under_its_own_descendant_raises(db):
    table = db.table('app.category')
    a, _, c = tree(table)
    with pytest.raises(BusinessLogicException, match='cannot be moved under itself or one of its descendants'):
        change(table, a, parent_id=c['id'])


def test_update_without_old_record_raises(db):
    table = db.table('app.category')
    a, *_ = tree(table)
    with pytest.raises(RecordException, match='requires old_record'):
        table.update(dict(row(table, a['id']), description='no old record'))


def test_deleting_a_node_deletes_its_subtree(db):
    table = db.table('app.category')
    a, *_ = tree(table)
    other = insert(table, 'other')
    table.delete(row(table, a['id']))
    assert [r['id'] for r in table.query(columns='$id', excludeLogicalDeleted=False).fetch()] == [other['id']]


def test_a_child_of_a_logically_deleted_parent_gets_the_parent_path(db):
    table = db.table('app.category')
    a = insert(table, 'a')
    change(table, a, __del_ts=datetime.datetime.now(datetime.timezone.utc))
    child = insert(table, 'child', a)
    assert child['hierarchical_code'] == 'a/child'


def test_pkey_only_hierarchy(implementation, tmp_path):
    def declare(package):
        category(package, columns=None)

    with migrated_db(implementation, tmp_path, declare) as db:
        table = db.table('app.category')
        a = insert(table, 'a')
        b = insert(table, 'b', a)
        assert b['hierarchical_pkey'] == f"{a['id']}/{b['id']}"
        assert 'hierarchical_code' not in table.model.columns


def test_counter_numbers_siblings_and_orders_the_tree(implementation, tmp_path):
    def declare(package):
        category(package, counter=True)

    with migrated_db(implementation, tmp_path, declare) as db:
        table = db.table('app.category')
        first = insert(table, 'first')
        second = insert(table, 'second')
        child = insert(table, 'child', second)
        third = insert(table, 'third')
        assert [r['_row_count'] for r in (first, second, child, third)] == [1, 2, 1, 3]
        assert [r['_h_count'] for r in (first, second, child, third)] == ['01', '02', '0201', '03']
        assert child['_parent_h_count'] == '02'
        assert [r['code'] for r in table.query(columns='$code').fetch()] == ['first', 'second', 'child', 'third']


def test_root_id_is_the_first_key_of_the_path(implementation, tmp_path):
    def declare(package):
        category(package, root_id=True)

    with migrated_db(implementation, tmp_path, declare) as db:
        table = db.table('app.category')
        a, _, c = tree(table)
        assert row(table, c['id'], '$root_id')['root_id'] == a['id']
        assert row(table, a['id'], '$root_id')['root_id'] == a['id']


def test_virtual_roots_copy_the_flag_from_the_parent(implementation, tmp_path):
    def declare(package):
        category(package, virtual_roots=True)

    with migrated_db(implementation, tmp_path, declare) as db:
        table = db.table('app.category')
        root = insert(table, 'root', _virtual_node=True)
        child = insert(table, 'child', root, _virtual_node=False)
        assert child['_virtual_node'] is True
        assert row(table, child['id'], '$_virtual_node')['_virtual_node'] is True


@pytest.mark.parametrize('option,value', [('linked_to', 'app.master'), ('depth', 3)])
def test_deferred_hierarchical_options_raise_when_the_model_is_built(tmp_path, option, value):
    def declare(package):
        master = package.table('master', name_long='Master')
        master.options().sys_fields()
        category(package, **{option: value})

    with pytest.raises(UnsupportedFeatureError, match=f'hierarchical {option}'):
        with migrated_db('sqlite', tmp_path, declare):
            pass


def test_auto_counter_without_hierarchy_still_refuses_the_write(tmp_path):
    def declare(package):
        table = package.table('ranked', name_long='Ranked')
        table.options().sys_fields()
        table.options().auto_counter()
        table.column('title')

    with migrated_db('sqlite', tmp_path, declare) as db:
        with pytest.raises(UnsupportedFeatureError, match='option auto_counter'):
            db.table('app.ranked').insert({'title': 'x'})
