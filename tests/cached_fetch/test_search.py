"""cached(...).search(...): the search seed of a cached fetch."""
import datetime

import pytest

from asqueel import AsqueelDb
from tests.cached_fetch.test_fetch import enable
from tests.option_tables_support import IMPLEMENTATIONS, migrated_db

ROWS = [
    (0, 'Red apple', 'fresh fruit', 'X1', 10, datetime.date(2026, 1, 1)),
    (1, 'Green apple', 'sour', 'X2', 20, datetime.date(2026, 1, 2)),
    (2, 'Banana', 'yellow FRUIT', 'Y1', 30, datetime.date(2026, 1, 3)),
    (3, 'Cherry', None, 'Y2', 40, datetime.date(2026, 1, 4)),
    (4, '100% juice', 'apple_mix', 'Z1', 50, datetime.date(2026, 1, 5)),
    (5, '100 juice', 'applexmix', 'Z2', 60, datetime.date(2026, 1, 6)),
    (6, 'Apple pie', 'baked fruit', 'Z3', 70, datetime.date(2026, 1, 7)),
]


def declare(pkg):
    item = pkg.table('item', pkey='id')
    item.column('id', dtype='L')
    item.column('name', dtype='A')
    item.column('note', dtype='T')
    item.column('code', dtype='C', size='2')
    item.column('value', dtype='L')
    item.column('day', dtype='D')


@pytest.fixture(params=IMPLEMENTATIONS)
def db(request, tmp_path):
    with migrated_db(request.param, tmp_path, declare, declare_db=enable) as db:
        table = db.table('app.item')
        for row in ROWS:
            table.insert(dict(zip(('id', 'name', 'note', 'code', 'value', 'day'), row)))
        db.commit()
        table.query(columns='$id, $name, $note, $code, $value, $day').fetch(destinationName='u:q')
        yield db


def ids(cached, **kwargs):
    return [row['id'] for row in cached.query(columns='id, _sortidx', **kwargs).fetch()]


def test_a_two_token_seed_keeps_rows_matching_both_tokens_renumbered_from_zero(db):
    cached = db.table('app.item').cached('u:q')
    assert cached.search('apple fruit') == 2
    rows = cached.query(columns='id, _sortidx', start=0, count=10).fetch()
    assert [(row['id'], row['_sortidx']) for row in rows] == [(0, 0), (6, 1)]
    assert ids(cached, start=1, count=5) == [6]


def test_the_match_is_case_insensitive(db):
    cached = db.table('app.item').cached('u:q')
    assert cached.search('APPLE') == 5
    assert ids(cached) == [0, 1, 4, 5, 6]
    assert cached.search('fruit') == 3
    assert ids(cached) == [0, 2, 6]


def test_percent_and_underscore_in_the_seed_match_literally(db):
    cached = db.table('app.item').cached('u:q')
    assert cached.search('100%') == 1
    assert ids(cached) == [4]
    assert cached.search('apple_mix') == 1
    assert ids(cached) == [4]


def test_a_search_keeps_the_active_sort_and_a_sort_keeps_the_active_seed(db):
    cached = db.table('app.item').cached('u:q')
    cached.sort('value desc')
    assert cached.search('apple') == 5
    assert ids(cached) == [6, 5, 4, 1, 0]
    assert cached.sort('id % 2 desc, id') is None
    assert ids(cached) == [1, 5, 0, 4, 6]
    assert cached.sort(None) is None
    assert ids(cached) == [0, 1, 4, 5, 6]
    other = AsqueelDb(db.shared.config.builder).session()
    try:
        assert [row['id'] for row in other.table('app.item').cached('u:q').query(columns='id').fetch()] == [0, 1, 4, 5, 6]
    finally:
        other.shared.close()


def test_search_none_restores_the_unfiltered_sort_and_returns_the_full_count(db):
    cached = db.table('app.item').cached('u:q')
    cached.sort('value desc')
    cached.search('apple')
    assert cached.search(None) == len(ROWS)
    assert ids(cached) == [6, 5, 4, 3, 2, 1, 0]
    catalog = db.table('_asql_._asql_cached_fetch').query(
        columns='$sort_order_by, $search_seed', where="$id = 'u:q'").fetch()
    assert dict(catalog[0]) == {'sort_order_by': 'value desc', 'search_seed': None}


def test_search_none_without_a_sort_restores_the_original_numbering(db):
    cached = db.table('app.item').cached('u:q')
    cached.search('apple')
    assert cached.search(None) == len(ROWS)
    assert cached.row['sort_sqltable'] is None
    assert [row['id'] for row in cached.query(columns='id').fetch()] == list(range(len(ROWS)))


def test_non_text_columns_are_not_searched(db):
    cached = db.table('app.item').cached('u:q')
    assert cached.search('70') == 0
    assert cached.search('2026') == 0


def test_a_seed_without_tokens_raises(db):
    with pytest.raises(ValueError, match='at least one token'):
        db.table('app.item').cached('u:q').search('   ')
