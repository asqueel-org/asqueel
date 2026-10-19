"""Actual hierarchical fetch/count terminals on both supported drivers."""
import pytest
from genro_toolbox import NamedList

from asqueel import UnsupportedFeatureError
from tests.tree_execution_support import shop, execution_shop  # noqa: F401
from tests.adapter_integration.test_named_list_rows import (
    test_fetch_has_named_positional_mutable_rows as test_fetch_has_named_positional_mutable_rows,
    test_dynamic_column_uses_shared_legacy_index_only_within_result as test_dynamic_column_uses_shared_legacy_index_only_within_result,
    test_raw_compiled_and_empty_result_metadata as test_raw_compiled_and_empty_result_metadata,
    test_duplicate_names_rejected_consistently as test_duplicate_names_rejected_consistently,
)
from tests.read_path.count_cases import (
    test_count_uses_the_current_environment as original_environment,
    test_count_does_not_commit as original_transaction,
)


def test_count_environment_and_transaction(shop):  # noqa: F811
    original_environment(shop, None)
    original_transaction(shop, None)


@pytest.mark.parametrize('options,expected', [
    ({}, 5), ({'where': '$id<0'}, 0),
    ({'columns': '$total', 'distinct': True}, 4),
    ({'columns': '$total', 'distinct': True, 'where': '$id<0'}, 0),
    ({'columns': '$customer_id,SUM($total) AS amount', 'group_by': '$customer_id'}, 4),
    ({'columns': '$customer_id,SUM($total) AS amount', 'group_by': '$customer_id',
      'having': 'SUM($total)>=:minimum', 'minimum': 40}, 3),
    ({'columns': '$customer_id', 'group_by': '$customer_id', 'where': '$id<0'}, 0),
    ({'columns': 'SUM($total) AS amount'}, 5),
    ({'limit': 2}, 5), ({'limit': 2, 'offset': 1}, 0),
    ({'columns': '$total', 'distinct': True, 'limit': 2}, 2),
    ({'excludeLogicalDeleted': 'mark'}, 6),
])
def test_count_returns_legacy_integer(shop, options, expected):  # noqa: F811
    value = shop.query(**options).count()
    assert type(value) is int and value == expected


def test_reuse_fetch_count_current_environment_and_no_cache(shop):  # noqa: F811
    query = shop.query(columns='$id,@customer_id.name AS customer_name,$double_total',
                      where='$customer_id=:env_customer', order_by='$id DESC')
    for customer, ids in [(1, [12, 10]), (2, [11]), (1, [12, 10])]:
        with shop.db.temp_env(customer=customer):
            before = query.compiled
            rows = query.fetch()
            assert [row['id'] for row in rows] == ids
            assert all(type(row) is NamedList for row in rows)
            assert query.count() == len(ids)
            rows[0]['customer_name'] = 'local only'
            assert query.fetch()[0]['customer_name'] != 'local only'
            after = query.compiled
            assert (after.sql,dict(after.params)) == (before.sql,dict(before.params))


@pytest.mark.parametrize('terminal', ['fetch', 'count'])
def test_many_operations_fail_before_execution(shop, terminal, monkeypatch):  # noqa: F811
    def forbidden(*args, **kwargs):
        pytest.fail('Unsupported many operation reached execution')
    monkeypatch.setattr(shop.db, 'execute', forbidden)
    query = shop.db.table('sales.customer').query('@sales_invoice_customer_id.sum($total)')
    with pytest.raises(UnsupportedFeatureError):
        getattr(query, terminal)()



def test_fetch_shares_transaction_and_each_terminal_executes_once(shop, monkeypatch):  # noqa: F811
    shop.db.execute(f'INSERT INTO {shop.invoice_sql} (id, customer_id, total) '
                    'VALUES (:id, :customer, :total)', {'id': 16, 'customer': 3, 'total': 1})
    calls = []
    execute = shop.db.adapter.execute

    def recording(connection, compiled, cursorname=None):
        calls.append((connection, compiled.sql))
        return execute(connection, compiled, cursorname)

    monkeypatch.setattr(shop.db.adapter, 'execute', recording)
    query = shop.query(columns='$id', where='$id=16')
    assert query.fetch()[0]['id'] == 16
    assert len(calls) == 1
    assert query.count() == 1
    assert len(calls) == 2
    assert calls[0][0] is calls[1][0]
    shop.db.rollback()
    assert query.fetch() == []
    assert query.count() == 0
