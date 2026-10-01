"""Phase 1 contract — IN / NOT IN collection parameters (document 31, R01–R14, D2/D3/D6/D7)."""
import re

import pytest

from tests import query_completion_support as support
from tests.query_completion_support import ALL_IDS, VISIBLE, flat, in_lists

shop = support.shop


def compiled(shop, where, params):
    return shop.query(columns='$id', where=where, sqlparams=params, order_by='$id').compiled


@pytest.mark.parametrize('ids', [[10, 11], (10, 11), {10, 11}, frozenset({10, 11})],
                         ids=['list', 'tuple', 'set', 'frozenset'])
def test_in_binds_one_placeholder_per_member(shop, ids):
    # R01, R03, R04 (D7)
    query = compiled(shop, '$id IN :ids', {'ids': ids})
    assert [len(group) for group in in_lists(query.sql)] == [2]
    assert sorted(query.params.values()) == [10, 11]
    assert shop.ids(where='$id IN :ids', sqlparams={'ids': ids}) == [10, 11]


def test_not_in_list(shop):
    # R02
    query = compiled(shop, '$id NOT IN :ids', {'ids': [10, 11]})
    assert re.search(r'(?i)\bNOT IN \(', flat(query.sql))
    assert shop.ids(where='$id NOT IN :ids', sqlparams={'ids': [10, 11]}) == [12, 13, 15]


def test_duplicates_are_bound_not_deduplicated(shop):
    # R07
    query = compiled(shop, '$id IN :ids', {'ids': [10, 10, 11]})
    assert [len(group) for group in in_lists(query.sql)] == [3]
    assert shop.ids(where='$id IN :ids', sqlparams={'ids': [10, 10, 11]}) == [10, 11]


def test_empty_in_is_false_without_empty_list(shop):
    # R05 and the operand-free empty form decided at planning
    query = compiled(shop, '$customer_id IN :ids', {'ids': []})
    text = flat(query.sql)
    assert not re.search(r'(?i)\bIN \(\s*\)', text)
    if shop.backend == 'postgresql':
        assert "= ANY('{}')" in text
    else:
        assert 'IN (SELECT 1 WHERE 0)' in text
    assert shop.ids(where='$customer_id IN :ids', sqlparams={'ids': []}) == []


def test_empty_not_in_is_true_including_null_column(shop):
    # R06, D3: invoice 13 has a NULL customer and is included
    query = compiled(shop, '$customer_id NOT IN :ids', {'ids': []})
    text = flat(query.sql)
    assert not re.search(r'(?i)\bIN \(\s*\)', text)
    if shop.backend == 'postgresql':
        assert "<> ALL('{}')" in text
    else:
        assert 'NOT IN (SELECT 1 WHERE 0)' in text
    assert shop.ids(where='$customer_id NOT IN :ids', sqlparams={'ids': []}) == VISIBLE


def test_none_member_follows_sql_three_valued_logic(shop):
    # R08, D6
    assert shop.ids(where='$id IN :ids', sqlparams={'ids': [10, None]}) == [10]
    assert shop.ids(where='$id NOT IN :ids', sqlparams={'ids': [10, None]}) == []


def test_null_column_satisfies_neither_in_nor_not_in(shop):
    # R09, D6
    assert shop.ids(where='$customer_id IN :ids', sqlparams={'ids': [1, 2]}) == [10, 11, 12]
    assert shop.ids(where='$customer_id NOT IN :ids', sqlparams={'ids': [1]}) == [11, 15]


@pytest.mark.parametrize('value', ['First order', b'First order', 10, {'a': 1}],
                         ids=['str', 'bytes', 'int', 'dict'])
def test_non_collection_in_position_is_rejected_before_execution(shop, value):
    # R10: no conversion of a string into a list of characters, no SQL sent
    with pytest.raises(ValueError, match='notes'):
        shop.query(columns='$id', where='$note IN :notes', sqlparams={'notes': value}).compiled


def test_same_collection_twice_in_position(shop):
    # R11
    where = '$id IN :ids OR $customer_id IN :ids'
    assert shop.ids(where=where, sqlparams={'ids': [1, 11]}) == [10, 11, 12]


def test_same_collection_in_and_scalar_position_is_rejected(shop):
    # R11: mixed IN and scalar use of one parameter
    with pytest.raises(ValueError, match='ids'):
        compiled(shop, '$id IN :ids OR $id = ANY(:ids)', {'ids': [10, 11]})


def test_two_collections_expand_independently(shop):
    # R12
    where = '$id IN :ids AND $customer_id NOT IN :customers'
    assert shop.ids(where=where, sqlparams={'ids': [10, 11, 12], 'customers': [2]}) == [10, 12]


def test_generated_names_do_not_collide_with_prefixed_parameters(shop):
    # R12: the legacy defect with :ids and :ids2 is not a requirement
    where = '$id IN :ids AND $customer_id NOT IN :ids2'
    query = compiled(shop, where, {'ids': [10, 11, 12], 'ids2': [2]})
    assert sorted(query.params.values()) == [2, 10, 11, 12]
    assert shop.ids(where=where, sqlparams={'ids': [10, 11, 12], 'ids2': [2]}) == [10, 12]


def test_collection_next_to_scalar_parameters(shop):
    where = '$id IN :ids AND $total >= :ids_0'
    assert shop.ids(where=where, sqlparams={'ids': [10, 11, 12], 'ids_0': 20}) == [10, 11]


def test_in_text_inside_literals_and_comments_is_not_rewritten(shop):
    where = "$note <> 'IN :ids' /* IN :ids */ AND $id IN :ids"
    query = compiled(shop, where, {'ids': [10]})
    assert "'IN :ids'" in query.sql and '/* IN :ids */' in query.sql
    assert shop.ids(where=where, sqlparams={'ids': [10]}) == [10]


def test_hostile_values_stay_parameters(shop):
    hostile = ["x'); DROP TABLE sales.invoice; --", 'First order']
    query = compiled(shop, '$note IN :notes', {'notes': hostile})
    assert 'DROP TABLE' not in query.sql
    assert shop.ids(where='$note IN :notes', sqlparams={'notes': hostile}) == [10]
    assert shop.ids() == VISIBLE


def test_environment_collection_and_reuse_after_environment_change(shop):
    query = shop.query(columns='$id', where='$customer_id IN :env_customers', order_by='$id')
    with shop.db.temp_env(customers=[1]):
        assert [row['id'] for row in query.fetch()] == [10, 12]
    with shop.db.temp_env(customers=[2, 3]):
        assert [row['id'] for row in query.fetch()] == [11, 15]
    with shop.db.temp_env(customers=[]):
        assert query.fetch() == []


def test_query_reuse_does_not_mutate_parameters(shop):
    query = shop.query(columns='$id', where='$id IN :ids', sqlparams={'ids': [10, 11]},
                       order_by='$id')
    first, second = query.compiled, query.compiled
    assert first.sql == second.sql and dict(first.params) == dict(second.params)
    assert query.fetch() == query.fetch() == [{'id': 10}, {'id': 11}]


def test_collection_inside_named_subquery(shop):
    # R13: the subquery does not exclude logically deleted rows (invoice 14)
    customers = shop.db.table('sales.customer')
    query = customers.query(columns='$id, $selected_invoices', sqlparams={'ids': [10, 11, 14]},
                            order_by='$id')
    assert [(row['id'], row['selected_invoices']) for row in query.fetch()] == [
        (1, 1), (2, 2), (3, 0)]
    empty = customers.query(columns='$id, $selected_invoices', sqlparams={'ids': []},
                            order_by='$id')
    assert [row['selected_invoices'] for row in empty.fetch()] == [0, 0, 0]


def test_postgres_any_with_a_list_still_binds_an_array(shop):
    if shop.backend != 'postgresql':
        pytest.skip('= ANY is PostgreSQL syntax')
    assert shop.ids(where='$id = ANY(:ids)', sqlparams={'ids': [10, 11]}) == [10, 11]
    assert shop.ids(where='$id = ANY(:ids)', sqlparams={'ids': []}) == []


def test_raw_update_and_delete_share_the_expression_path(shop):
    table = shop.db.table('sales.invoice')
    table.raw_update({'note': 'bulk'}, where='$id IN :ids', sqlparams={'ids': [10, 11]})
    notes = shop.query(columns='$id, $note', where='$note = :note', sqlparams={'note': 'bulk'},
                       order_by='$id').fetch()
    assert [row['id'] for row in notes] == [10, 11]
    table.raw_delete(where='$id IN :ids', sqlparams={'ids': [10, 11]})
    assert shop.ids() == [12, 13, 15]
    table.raw_delete(where='$id IN :ids', sqlparams={'ids': []})
    assert shop.ids() == [12, 13, 15]
    shop.db.rollback()


def test_direct_sql_expands_collections(shop):
    # R14, D2
    sql = 'SELECT id FROM {invoice} WHERE id IN :ids ORDER BY id'
    assert shop.direct_ids(sql, {'ids': [10, 11]}) == [10, 11]
    assert shop.direct_ids(sql, {'ids': (10, 10, 11)}) == [10, 11]
    assert shop.direct_ids(sql, {'ids': []}) == []
    not_in = 'SELECT id FROM {invoice} WHERE customer_id NOT IN :ids'
    assert shop.direct_ids(not_in, {'ids': []}) == ALL_IDS
    assert shop.direct_ids(not_in, {'ids': [1]}) == [11, 14, 15]


def test_direct_sql_keeps_literals_and_rejects_scalars(shop):
    literal = "SELECT id FROM {invoice} WHERE coalesce(note, '') <> 'IN :ids' AND id IN :ids"
    assert shop.direct_ids(literal, {'ids': [10, 12]}) == [10, 12]
    with pytest.raises(ValueError, match='ids'):
        shop.direct_ids('SELECT id FROM {invoice} WHERE id IN :ids', {'ids': 'abc'})
    with pytest.raises(ValueError, match='ids'):
        shop.direct_ids('SELECT id FROM {invoice} WHERE id IN :ids OR id = ANY(:ids)',
                        {'ids': [10]})
