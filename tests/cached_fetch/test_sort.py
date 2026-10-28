"""cached(...).sort(...): the sort table of a cached fetch."""
import pytest

from asqueel import AsqueelDb
from tests.cached_fetch.test_fetch import declare, enable, fill
from tests.option_tables_support import IMPLEMENTATIONS, migrated_db

ROWS = 95


@pytest.fixture(params=IMPLEMENTATIONS)
def db(request, tmp_path):
    with migrated_db(request.param, tmp_path, declare, declare_db=enable) as db:
        fill(db, ROWS)
        db.table('app.item').query(columns='$id, $grp, $value').fetch(destinationName='u:s')
        yield db


def expected_order(db, order_by):
    """The ids of the source rows in ``order_by`` order, ties by id (the original numbering)."""
    return [row['id'] for row in db.table('app.item').query(columns='$id', order_by=f'{order_by}, $id').fetch()]


def page_ids(cached, start, count=30):
    return [row['id'] for row in cached.query(columns='id', start=start, count=count).fetch()]


def result_rows(db):
    sqltable = db.table('app.item').cached('u:s').row['sqltable']
    return [tuple(row) for row in db.execute(f'SELECT * FROM _asql_."{sqltable}" ORDER BY _rowidx').fetchall()]


def table_exists(db, name):
    if db.implementation == 'postgres':
        sql = "SELECT count(*) FROM pg_tables WHERE schemaname = '_asql_' AND tablename = :name"
    else:
        sql = "SELECT count(*) FROM _asql_.sqlite_master WHERE type = 'table' AND name = :name"
    return db.execute(sql, {'name': name}).fetchall()[0][0] == 1


def test_sort_by_two_columns_orders_every_page_with_ties_by_rowidx(db):
    cached = db.table('app.item').cached('u:s')
    assert cached.sort('value desc, grp') is None
    expected = expected_order(db, '$value desc, $grp')
    for start in (0, 40, 90):
        assert page_ids(cached, start) == expected[start:start + 30]
    rows = cached.query(columns='id, _sortidx', start=40, count=5).fetch()
    assert [row['_sortidx'] for row in rows] == [40, 41, 42, 43, 44]


def test_a_second_sort_replaces_the_first(db):
    cached = db.table('app.item').cached('u:s')
    cached.sort('value desc')
    first = cached.row['sort_sqltable']
    cached.sort('grp desc')
    assert page_ids(cached, 0, ROWS) == expected_order(db, '$grp desc')
    assert cached.row['sort_sqltable'] == first and table_exists(db, first)
    catalog = db.table('_asql_._asql_cached_fetch').query(columns='$sort_order_by', where="$id = 'u:s'").fetch()
    assert catalog[0]['sort_order_by'] == 'grp desc'


def test_sort_none_restores_the_original_order_and_drops_the_sort_table(db):
    cached = db.table('app.item').cached('u:s')
    cached.sort('value desc')
    sort_sqltable = cached.row['sort_sqltable']
    assert table_exists(db, sort_sqltable)
    cached.sort(None)
    assert page_ids(cached, 0, ROWS) == list(range(ROWS))
    assert not table_exists(db, sort_sqltable)
    catalog = db.table('_asql_._asql_cached_fetch').query(
        columns='$sort_sqltable, $sort_order_by', where="$id = 'u:s'").fetch()
    assert dict(catalog[0]) == {'sort_sqltable': None, 'sort_order_by': None}


def test_sorting_leaves_the_result_table_unchanged(db):
    before = result_rows(db)
    db.table('app.item').cached('u:s').sort('value desc, grp')
    assert result_rows(db) == before


def test_a_sort_is_seen_by_another_process(db):
    db.table('app.item').cached('u:s').sort('grp, value desc')
    other = AsqueelDb(db.shared.config.builder).session()
    try:
        assert page_ids(other.table('app.item').cached('u:s'), 0, ROWS) == expected_order(db, '$grp, $value desc')
    finally:
        other.shared.close()


def test_a_new_fetch_on_the_name_drops_its_sort(db):
    cached = db.table('app.item').cached('u:s')
    cached.sort('value desc')
    db.table('app.item').query(columns='$id, $grp, $value').fetch(destinationName='u:s')
    assert not table_exists(db, cached.row['sort_sqltable'])
    assert page_ids(db.table('app.item').cached('u:s'), 0, ROWS) == list(range(ROWS))
