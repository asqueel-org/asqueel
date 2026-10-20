"""The same public row contract on every supported data dialect."""
from copy import deepcopy
import json

import pytest
from genro_toolbox import NamedList

from tests.query_completion_support import shop as _shop

shop = _shop


def test_fetch_has_named_positional_mutable_rows(shop):
    query = shop.query(columns='$id AS code,$note AS label', order_by='$id', limit=2)
    rows = query.fetch()
    assert type(rows) is list and all(type(r) is NamedList for r in rows)
    first, second = rows
    assert first._index is second._index
    assert first.keys() == ['code', 'label']
    assert first[0] == first['code'] == 10
    assert first[-1] == first['label'] == 'First order'
    assert first[:] == list(first) == [10, 'First order']
    assert 'code' in first and 10 not in first  # Membership refers to names, not values.
    assert first.get('missing', 'default') == 'default'
    assert second[1] is second['label'] is None
    first['label'] = 'edited'
    assert first[1] == 'edited'
    first[0] = 123
    assert first['code'] == 123
    first.update({'label': 'updated'})
    assert dict(first) == {'code': 123, 'label': 'updated'}
    assert first.values() == (123, 'updated')
    assert deepcopy(first) == first
    assert json.loads(json.dumps(first)) == [123, 'updated']
    assert json.loads(json.dumps(dict(first))) == {'code': 123, 'label': 'updated'}
    assert query.fetch()[0]['code'] == 10  # No write and no cached result.


def test_dynamic_column_uses_shared_legacy_index_only_within_result(shop):
    query = shop.query(columns='$id', order_by='$id', limit=2)
    rows = query.fetch()
    rows[0]['local'] = 'a'
    assert rows[0][1] == 'a'
    assert 'local' in rows[1] and rows[1]['local'] is None
    assert len(rows[1]) == 1  # The sibling value list is not silently grown.
    rows[1]['local'] = 'b'
    assert rows[1][1] == 'b' and rows[0]['local'] == 'a'
    again = query.fetch()
    assert 'local' not in again[0]
    assert again[0]._index is not rows[0]._index
    assert query.compiled.columns[0].name == 'id'


def test_raw_compiled_and_empty_result_metadata(shop):
    query = shop.query(columns='$note AS "Note value",$id AS "ID"', where='$id=11')
    for result in [query.execute(), shop.db.execute(query.compiled),
                   shop.db.execute('SELECT NULL AS "Note value", 11 AS "ID"')]:
        names = [column[0] for column in result.description]
        row = result.fetchall()[0]
        assert type(row) is NamedList
        assert row.keys() == ['Note value', 'ID']
        assert row[0] is None and row[1] == 11
        assert row['ID'] == 11
        assert names == row.keys()
    empty = shop.query(columns='$id AS code', where='1=0').execute()
    assert empty.fetchall() == []
    assert [column[0] for column in empty.description] == ['code']


def test_returning_dict_and_fetch_record_named_list_keep_their_declared_interfaces(shop):
    table = shop.db.table('sales.customer')
    values = {'id': 99, 'name': 'Test'}
    result = table.insert(values)
    assert result is values and type(result) is dict
    record = table.query(where='$id = :id', id=99).fetchRecord()
    assert type(record) is NamedList and record['name'] == 'Test'
    record['name'] = 'copied'
    assert table.query(where='$id = :id', id=99).fetchRecord()['name'] == 'Test'
    assert table.query(where='$id = :id', id=99).sql_update({'name': 'Saved'}) == 1
    assert table.query(where='$id = :id', id=99).fetchRecord()['name'] == 'Saved'


def test_duplicate_names_rejected_consistently(shop):
    with pytest.raises(ValueError, match='unique names'):
        shop.db.execute('SELECT 1 AS duplicate, 2 AS duplicate')
