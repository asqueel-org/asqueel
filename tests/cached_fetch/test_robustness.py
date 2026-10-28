"""Cached fetch under aliases, concurrent handles, cleanup races and calls outside the grammar."""
import threading

import pytest

from asqueel.cached_fetch import physical_name
from asqueel.errors import TransactionStateError
from tests.cached_fetch.test_fetch import declare, enable, fill
from tests.option_tables_support import IMPLEMENTATIONS, migrated_db

ROWS = 40


@pytest.fixture(params=IMPLEMENTATIONS)
def db(request, tmp_path):
    with migrated_db(request.param, tmp_path, declare, declare_db=enable) as db:
        fill(db, ROWS)
        db.table('app.item').query(columns='$id, $grp, $value').fetch(destinationName='u:s')
        yield db


def test_an_order_by_on_an_output_alias_numbers_as_fetch_orders(db):
    query = db.table('app.item').query(columns='$grp, count(*) AS tot, max($id) AS top', group_by='$grp',
                                       order_by='tot desc, top')
    expected = [row['grp'] for row in query.fetch()]
    assert query.fetch(destinationName='u:alias') == len(expected)
    rows = db.table('app.item').cached('u:alias').query(columns='grp').fetch()
    assert [row['grp'] for row in rows] == expected


@pytest.mark.parametrize('destinationName', [' u:x', 'u :x', '\tu:x'])
def test_an_owner_with_surrounding_spaces_raises(db, destinationName):
    with pytest.raises(ValueError, match='space'):
        db.table('app.item').query(columns='$id').fetch(destinationName=destinationName)


def test_a_long_owner_keeps_the_digest_within_63_bytes():
    owner = 'è' * 40
    first, second = physical_name('p', owner, 'a'), physical_name('p', owner, 'b')
    assert first != second
    assert len(first.encode('utf-8')) <= 63 and len(second.encode('utf-8')) <= 63


@pytest.mark.parametrize('call, argument', [('search', 5), ('search', ''), ('sort', ''), ('sort', 3)])
def test_sort_and_search_refuse_what_is_not_sql_text(db, call, argument):
    cached = db.table('app.item').cached('u:s')
    with pytest.raises(ValueError):
        getattr(cached, call)(argument)


def test_count_zero_raises(db):
    with pytest.raises(ValueError, match='count'):
        db.table('app.item').cached('u:s').query(count=0)


def test_a_table_left_without_its_catalog_row_is_replaced(db):
    db.table('_asql_._asql_cached_fetch').query(where="$id = 'u:s'").sql_delete()
    db.commit()
    assert db.table('app.item').query(columns='$id').fetch(destinationName='u:s') == ROWS


def test_two_handles_sort_and_search_the_same_fetch(db):
    first = db.table('app.item').cached('u:s')
    second = db.table('app.item').cached('u:s')
    assert first.search('north') < ROWS
    second.sort('id desc')
    assert second.row['search_seed'] == 'north'
    ids = [row['id'] for row in second.query(columns='id').fetch()]
    assert ids == sorted(ids, reverse=True) and len(ids) == first.search('north')


def test_star_returns_the_result_columns_only_when_sorted(db):
    cached = db.table('app.item').cached('u:s')
    cached.sort('value desc')
    rows = cached.query(start=0, count=1).fetch()
    assert '_sortidx' not in rows[0].keys()
    assert '_rowidx' in rows[0].keys()


def test_a_page_of_a_fetch_cleaned_up_meanwhile_raises_a_clear_error(db):
    cached = db.table('app.item').cached('u:s')
    cached.sort('value desc')
    page = cached.query(start=0, count=5)
    db.cleanup_cached_tables(owner='u')
    with pytest.raises(ValueError, match='removed or replaced'):
        page.fetch()


def test_cleanup_drops_only_the_rows_it_read(db):
    db.table('app.item').query(columns='$id').fetch(destinationName='v:s')
    db.cleanup_cached_tables(owner='u')
    catalog = db.table('_asql_._asql_cached_fetch').query(columns='$id').fetch()
    assert [row['id'] for row in catalog] == ['v:s']


def test_the_shared_database_refuses_the_cached_fetch(db):
    with pytest.raises(TransactionStateError):
        db.shared.table('app.item').query(columns='$id').fetch(destinationName='u:x')
    with pytest.raises(TransactionStateError):
        db.shared.cleanup_cached_tables(owner='u')


def test_an_open_session_of_the_reserved_name_raises(db):
    reserved = db.session('_asql_cached_fetch')
    try:
        with pytest.raises(TransactionStateError, match='reserved'):
            db.table('app.item').query(columns='$id').fetch(destinationName='u:x')
    finally:
        reserved.close()


def test_two_concurrent_creates_of_one_key_both_succeed(db):
    if db.implementation != 'postgres':
        pytest.skip('one SQLite file serializes its writers by itself')
    shared = db.shared
    errors = []

    def create():
        try:
            with shared.session() as session:
                session.table('app.item').query(columns='$id').fetch(destinationName='w:same')
        except Exception as error:
            errors.append(error)

    threads = [threading.Thread(target=create) for _ in range(4)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    assert errors == []
    assert db.table('app.item').cached('w:same').row['rowcount'] == ROWS
