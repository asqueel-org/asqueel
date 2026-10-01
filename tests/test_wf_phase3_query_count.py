"""Phase 3 contract — the SqlQuery.count() terminal (R23–R27, R30 count, R31, R32, D1)."""
import re

import pytest

from asqueel.contracts import UnsupportedFeatureError

from tests import query_completion_support as support
from tests.query_completion_support import flat

shop = support.shop


@pytest.fixture
def statements(shop, monkeypatch):
    """Every compiled statement count() sends through the database's own execute."""
    sent = []
    execute = shop.db.execute

    def recording(query, sqlargs=None):
        result = execute(query, sqlargs)
        sent.append((query, result))
        return result

    monkeypatch.setattr(shop.db, 'execute', recording)
    return sent


def counted(shop, statements, **options):
    statements.clear()
    value = shop.query(**options).count()
    assert type(value) is int
    assert len(statements) == 1
    query, result = statements[0]
    assert len(result.rows) == 1 and len(result.rows[0]) == 1
    return value, flat(query.sql)


def test_plain_count_has_no_projected_columns(shop, statements):
    # R23
    value, sql = counted(shop, statements, columns='$id, $note')
    assert value == 5
    assert re.match(r'(?i)SELECT count\(\*\)', sql)
    assert '"note"' not in sql


def test_count_respects_where_and_parameters(shop, statements):
    value, _ = counted(shop, statements, columns='$id', where='$customer_id = :customer',
                       sqlparams={'customer': 1})
    assert value == 2
    value, _ = counted(shop, statements, columns='$id', where='$id IN :ids',
                       sqlparams={'ids': [10, 11, 14]})
    assert value == 2


def test_distinct_count_counts_distinct_rows(shop, statements):
    # R24
    value, sql = counted(shop, statements, columns='$total', distinct=True)
    assert value == 4
    assert re.match(r'(?i)SELECT count\(\*\) AS "count" FROM \(SELECT DISTINCT ', sql)


def test_grouped_count_counts_surviving_groups(shop, statements):
    # R25
    value, sql = counted(shop, statements, columns='$customer_id, SUM($total) AS total_sum',
                         group_by='$customer_id', having='SUM($total) >= :minimum',
                         sqlparams={'minimum': 40})
    assert value == 3
    assert re.match(r'(?i)SELECT count\(\*\) AS "count" FROM \(SELECT ', sql) and 'HAVING' in sql
    value, _ = counted(shop, statements, columns='$customer_id, COUNT(*) AS n',
                       group_by='$customer_id')
    assert value == 4


def test_opaque_projection_is_counted_through_a_subquery(shop, statements):
    # decided at planning: count() == len(fetch()) for every admitted form
    value, sql = counted(shop, statements, columns='SUM($total) AS total_sum')
    assert value == 1 == len(shop.query(columns='SUM($total) AS total_sum').fetch())
    assert re.match(r'(?i)SELECT count\(\*\) AS "count" FROM \(SELECT ', sql)
    value, _ = counted(shop, statements, columns='$id, $double_total')
    assert value == 5


def test_relation_path_projection_counts_rows(shop, statements):
    value, _ = counted(shop, statements, columns='$id, @customer.name')
    assert value == 5


@pytest.mark.parametrize('options', [{'limit': 2}, {'offset': 2}, {'limit': 0, 'offset': 0},
                                     {'limit': 2, 'distinct': True, 'columns': '$total'}],
                         ids=['limit', 'offset', 'zero', 'distinct-limit'])
def test_count_with_limit_or_offset_is_rejected(shop, statements, options):
    # R26, R32, D1
    options.setdefault('columns', '$id')
    with pytest.raises(UnsupportedFeatureError, match=r'(?i)limit|offset'):
        shop.query(**options).count()
    assert statements == []


def test_empty_dataset_counts_zero(shop, statements):
    # R27
    assert counted(shop, statements, columns='$id', where='$id < 0')[0] == 0
    assert counted(shop, statements, columns='$customer_id, COUNT(*) AS n', where='$id < 0',
                   group_by='$customer_id')[0] == 0
    assert counted(shop, statements, columns='$total', where='$id < 0', distinct=True)[0] == 0


def test_count_follows_row_policies(shop, statements):
    # R30 count: mark keeps deleted rows visible, as fetch does
    assert counted(shop, statements, columns='$id')[0] == 5
    assert counted(shop, statements, columns='$id', exclude_logical_deleted='mark')[0] == 6
    assert counted(shop, statements, columns='$id', exclude_logical_deleted=False)[0] == 6


def test_count_drops_order_by(shop, statements):
    # R31
    value, sql = counted(shop, statements, columns='$id', order_by='$total')
    assert value == 5
    assert 'ORDER BY' not in sql.upper()
    value, sql = counted(shop, statements, columns='$total', distinct=True, order_by='$total')
    assert value == 4
    assert 'ORDER BY' not in sql.upper()


def test_count_ignores_for_update(shop, statements):
    # decided at planning: the lock is not applied to the count statement
    value, sql = counted(shop, statements, columns='$id', for_update=True)
    assert value == 5
    assert 'FOR UPDATE' not in sql.upper()


def test_count_does_not_mutate_the_query(shop, statements):
    query = shop.query(columns='$id', where='$id IN :ids', sqlparams={'ids': [10, 11, 12]},
                       order_by='$id DESC', limit=2)
    before = query.compiled
    with pytest.raises(UnsupportedFeatureError):
        query.count()
    unlimited = shop.query(columns='$id', where='$id IN :ids', sqlparams={'ids': [10, 11, 12]},
                           order_by='$id DESC')
    rows = unlimited.fetch()
    assert unlimited.count() == 3
    assert unlimited.fetch() == rows == [{'id': 12}, {'id': 11}, {'id': 10}]
    after = query.compiled
    assert (after.sql, dict(after.params)) == (before.sql, dict(before.params))
    assert [row['id'] for row in query.fetch()] == [12, 11]


def test_count_uses_the_current_environment(shop, statements):
    query = shop.query(columns='$id', where='$customer_id IN :env_customers')
    with shop.db.temp_env(customers=[1]):
        assert query.count() == 2
    with shop.db.temp_env(customers=[1, 2, 3]):
        assert query.count() == 4


def test_count_does_not_commit(shop, statements):
    shop.db.execute(f'INSERT INTO {shop.invoice_sql} (id, customer_id, total) '
                    'VALUES (:id, :customer, :total)', {'id': 16, 'customer': 3, 'total': 1})
    assert shop.query(columns='$id').count() == 6
    shop.db.rollback()
    assert shop.query(columns='$id').count() == 5
