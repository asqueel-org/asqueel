"""Query terminals as legacy: fetch derivatives, cursors and fetchRecord (Macro 5, Phase 1)."""
import json
from collections import OrderedDict
from datetime import date

import pytest
from genro_bag import Bag

from asqueel import RecordMultipleRowsError, RecordNotFoundError
from asqueel.contracts import UnsupportedFeatureError
from tests.option_tables_support import IMPLEMENTATIONS, migrated_db

ROWS = [
    {'code': 'c', 'grp': 'x', 'since': date(2026, 3, 1)},
    {'code': 'a', 'grp': 'y', 'since': date(2026, 1, 1)},
    {'code': 'b', 'grp': 'x', 'since': date(2026, 2, 1)},
]


def declare(pkg):
    customer = pkg.table('customer', pkey='id', order_by='$code')
    customer.column('id', dtype='serial')
    customer.column('code')
    customer.column('grp')
    customer.column('since', dtype='D')


@pytest.fixture(params=IMPLEMENTATIONS)
def customers(request, tmp_path):
    with migrated_db(request.param, tmp_path, declare) as db:
        table = db.table('app.customer')
        table.sql_insert([dict(row) for row in ROWS])
        db.commit()
        yield table


def query(table, **kwargs):
    return table.query(columns='$id,$code,$grp,$since', **kwargs)


def test_fetch_pkeys_returns_the_primary_keys_in_query_order(customers):
    rows = query(customers).fetch()
    assert query(customers).fetchPkeys() == [row['id'] for row in rows]
    assert [row['code'] for row in rows] == ['a', 'b', 'c']


def test_fetch_as_dict_keys_rows_by_a_column(customers):
    result = query(customers).fetchAsDict(key='code')
    assert type(result) is dict
    assert sorted(result) == ['a', 'b', 'c']
    assert result['b']['grp'] == 'x'
    ordered = query(customers).fetchAsDict(key='code', ordered=True)
    assert type(ordered) is OrderedDict
    assert list(ordered) == ['a', 'b', 'c']
    pkeys = query(customers).fetchAsDict(key='code', pkeyOnly=True)
    assert pkeys['a'] == result['a']['id']


def test_fetch_as_dict_defaults_to_the_primary_key(customers):
    result = query(customers).fetchAsDict()
    assert sorted(result) == sorted(query(customers).fetchPkeys())


def test_fetch_as_bag_holds_one_node_per_row_with_the_row_as_attributes(customers):
    bag = query(customers).fetchAsBag(key='code')
    assert isinstance(bag, Bag)
    assert list(bag.keys()) == ['a', 'b', 'c']
    assert bag.getAttr('c', 'grp') == 'x'


def test_fetch_as_json_serialises_rows_and_dates_in_iso_format(customers):
    data = json.loads(query(customers).fetchAsJson())
    assert [row['code'] for row in data] == ['a', 'b', 'c']
    assert data[0]['since'] == '2026-01-01'


def test_fetch_grouped_lists_rows_per_key(customers):
    grouped = query(customers).fetchGrouped(key='grp')
    assert type(grouped) is dict
    assert [row['code'] for row in grouped['x']] == ['b', 'c']
    assert [row['code'] for row in grouped['y']] == ['a']
    ordered = query(customers).fetchGrouped(key='grp', ordered=True)
    assert type(ordered) is OrderedDict
    assert list(ordered) == ['y', 'x']
    bag = query(customers).fetchGrouped(key='grp', asBag=True)
    assert isinstance(bag, Bag)
    assert sorted(bag.keys()) == ['x', 'y']


def test_iterfetch_yields_chunks_of_rows(customers):
    chunks = list(query(customers).iterfetch(arraysize=2))
    assert [len(chunk) for chunk in chunks] == [2, 1]
    assert [row['code'] for chunk in chunks for row in chunk] == ['a', 'b', 'c']


def test_cursor_and_servercursor_execute_the_query(customers):
    for cursor in (query(customers).cursor(), query(customers).servercursor()):
        rows = cursor.fetchall()
        cursor.close()
        assert len(rows) == 3


def test_fetch_record_returns_the_single_row(customers):
    row = query(customers, where='$code=:code', code='b').fetchRecord()
    assert row['grp'] == 'x'


def test_fetch_record_without_rows_raises_or_returns_none(customers):
    with pytest.raises(RecordNotFoundError):
        query(customers, where='$code=:code', code='zz').fetchRecord()
    assert query(customers, where='$code=:code', code='zz').fetchRecord(ignoreMissing=True) is None


def test_fetch_record_with_several_rows_raises_despite_the_table_order_by(customers):
    with pytest.raises(RecordMultipleRowsError):
        query(customers, where='$grp=:grp', grp='x').fetchRecord()


def test_fetch_record_with_an_explicit_order_by_takes_the_first_row(customers):
    row = query(customers, where='$grp=:grp', grp='x', order_by='$code DESC').fetchRecord()
    assert row['code'] == 'c'


def test_fetch_record_with_for_update_reads_the_row(customers):
    row = query(customers, where='$code=:code', code='a', for_update=True).fetchRecord()
    assert row['code'] == 'a'
    customers.db.rollback()


def test_legacy_record_is_absent_from_this_release(customers):
    with pytest.raises(UnsupportedFeatureError, match='record is not available in this release'):
        customers.record(pkey=1)


def test_delete_rereads_the_row_through_the_query_terminal(customers):
    pkey = query(customers, where='$code=:code', code='a').fetchRecord()['id']
    customers.delete({'id': pkey})
    customers.db.commit()
    assert query(customers, where='$code=:code', code='a').fetchRecord(ignoreMissing=True) is None
