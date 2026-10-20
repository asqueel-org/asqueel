"""Check native subquery results against physical rows on both dialects.

Legacy skips EXISTS on SQLite; keep those tests untouched and verify the
Asqueel capability separately. No implicit JOIN conversion is involved.
"""
from collections import Counter, defaultdict
from decimal import Decimal

import pytest


@pytest.fixture(params=['db_pg', 'db_sqlite'])
def db(request):
    return request.getfixturevalue(request.param)


def test_exists_matches_physical_rows_on_both_backends(db):
    expected = {row['invoice_id'] for row in db.table('invc.invoice_row').query(
        '$invoice_id', where='$unit_price>100').fetch()}
    rows = db.table('invc.invoice').query('$id,$has_expensive_rows').fetch()
    assert expected
    assert any(not row['has_expensive_rows'] for row in rows)
    assert {row['id'] for row in rows if row['has_expensive_rows']} == expected


def test_count_sum_and_empty_results_match_physical_invoice_rows(db):
    counts = Counter()
    sums = defaultdict(Decimal)
    for row in db.table('invc.invoice').query('$customer_id,$total').fetch():
        counts[row['customer_id']] += 1
        if row['total'] is not None:
            sums[row['customer_id']] += Decimal(str(row['total']))
    columns = '$id,$n_invoices,$invoiced_total'
    if db.adapter.dialect != 'sqlite':
        columns += ',$has_invoices'
    rows = db.table('invc.customer').query(columns).fetch()
    assert len({row['id'] for row in rows}) == len(rows)
    assert any(not row['n_invoices'] for row in rows)
    for row in rows:
        assert row['n_invoices'] == counts[row['id']]
        if 'has_invoices' in row:
            assert bool(row['has_invoices']) == bool(counts[row['id']])
        expected = sums.get(row['id'])
        if expected is None:
            assert row['invoiced_total'] is None
        else:
            assert abs(Decimal(str(row['invoiced_total'])) - expected) < Decimal('0.000001')
