"""Check macro predicates on real databases against the existing invoice corpus."""
from datetime import date

import pytest

from tests.query_completion_support import shop as _shop

shop = _shop


@pytest.mark.parametrize('low, high, expected', [
    (None, None, [10, 11, 12, 13, 15]),
    (None, 40, [11, 12, 13, 15]),
    (40, None, [10, 11, 15]),
    (40, 40, [11, 15]),
    (50, 40, []),
])
def test_inclusive_range_with_nullable_bound_parameters(shop, low, high, expected):
    query = shop.query(columns='$id', where='#IN_RANGE($total,:low,:high)',
                       low=low, high=high, order_by='$id')
    compiled = query.compiled
    assert [row['id'] for row in shop.db.execute(compiled).rows] == expected


@pytest.mark.parametrize('low, high, expected', [(None, None, True), (0, None, False),
                                                (None, 10, False), (0, 10, False)])
def test_null_value_range_retains_sql_unknown_in_where(shop, low, high, expected):
    # CAST is authored SQL outside the macro's legacy simple-operand grammar.
    where = '#IN_RANGE(NULL,low_bound,high_bound)'
    query = shop.db.compiler.select('sales.invoice', '$id', where=where,
                                    exclude_logical_deleted=False)
    # Isolate the predicate in SQL with typed bounds; NULL/UNKNOWN is excluded
    # by WHERE, except when both bounds are absent.
    predicate = query.sql.split('\nWHERE ', 1)[1]
    sql = ('SELECT 1 AS found FROM '
           '(SELECT CAST(:low AS numeric) AS low_bound, '
           'CAST(:high AS numeric) AS high_bound) AS bounds WHERE ' + predicate)
    assert bool(shop.db.execute(sql, {'low': low, 'high': high}).rows) is expected


@pytest.mark.parametrize('period, expected', [('2026', [14]), ('2025', []),
                                            ('2026-01-01', [14]),
                                            ('', [10, 11, 12, 13, 14, 15])])
def test_period_bound_dates_execute_on_a_date_column(shop, period, expected):
    # A physical bare identifier is part of the legacy PERIOD grammar. Extend
    # only this disposable table, keeping the shared fixture model untouched.
    shop.db.execute(f'ALTER TABLE {shop.invoice_sql} ADD COLUMN issued DATE')
    shop.db.execute(f'UPDATE {shop.invoice_sql} SET issued=:day WHERE id=14',
                    {'day': date(2026, 1, 1)})
    shop.db.currentEnv['locale'] = 'en'
    query = shop.query(columns='$id', where='#PERIOD(issued,:period)',
                       period=period, excludeLogicalDeleted=False, order_by='$id')
    compiled = query.compiled
    assert [row['id'] for row in shop.db.execute(compiled).rows] == expected
