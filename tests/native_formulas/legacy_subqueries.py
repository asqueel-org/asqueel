"""Legacy select/exists/select_* tests on the unchanged native invoice model.

Source and hashes: legacy-subqueries-manifest.json. Original assertions and
historical SQLite skips retained; one scalar-read API adaptation is recorded.
Separate native tests verify EXISTS on SQLite without rewriting the legacy.
"""
import pytest


class TestFormulaSelect:

    def test_count_n_invoices_pg(self, db_pg):
        """customer.n_invoices matches actual invoice count."""
        row = db_pg.table('invc.customer').query(
            columns='$id, $n_invoices',
            where='$n_invoices > 0', limit=1
        ).fetch()[0]
        actual = db_pg.table('invc.invoice').query(
            columns='$id',
            where='$customer_id = :cid', cid=row['id']
        ).count()
        assert int(row['n_invoices']) == actual

    def test_count_n_invoices_sqlite(self, db_sqlite):
        row = db_sqlite.table('invc.customer').query(
            columns='$id, $n_invoices',
            where='$n_invoices > 0', limit=1
        ).fetch()[0]
        actual = db_sqlite.table('invc.invoice').query(
            columns='$id',
            where='$customer_id = :cid', cid=row['id']
        ).count()
        assert int(row['n_invoices']) == actual

    def test_sum_invoiced_total_pg(self, db_pg):
        row = db_pg.table('invc.customer').query(
            columns='$id, $invoiced_total',
            where='$invoiced_total > 0', limit=1
        ).fetch()[0]
        assert float(row['invoiced_total']) > 0

    def test_sum_invoiced_total_sqlite(self, db_sqlite):
        row = db_sqlite.table('invc.customer').query(
            columns='$id, $invoiced_total',
            where='$invoiced_total > 0', limit=1
        ).fetch()[0]
        assert float(row['invoiced_total']) > 0

    def test_last_invoice_id_pg(self, db_pg):
        """last_invoice_id returns a valid invoice id."""
        row = db_pg.table('invc.customer').query(
            columns='$id, $last_invoice_id',
            where='$last_invoice_id IS NOT NULL', limit=1
        ).fetch()[0]
        inv = db_pg.table('invc.invoice').query(
            columns='$id',
            where='$id = :iid', iid=row['last_invoice_id']
        ).fetch()
        assert len(inv) == 1

    def test_last_invoice_id_sqlite(self, db_sqlite):
        row = db_sqlite.table('invc.customer').query(
            columns='$id, $last_invoice_id',
            where='$last_invoice_id IS NOT NULL', limit=1
        ).fetch()[0]
        inv = db_sqlite.table('invc.invoice').query(
            columns='$id',
            where='$id = :iid', iid=row['last_invoice_id']
        ).fetch()
        assert len(inv) == 1

    def test_exists_has_invoices_pg(self, db_pg):
        """has_invoices=True only for customers with invoices."""
        row = db_pg.table('invc.customer').query(
            columns='$id, $has_invoices',
            where='$has_invoices = TRUE', limit=1
        ).fetch()[0]
        n = db_pg.table('invc.invoice').query(
            columns='$id',
            where='$customer_id = :cid', cid=row['id']
        ).count()
        assert n > 0

    def test_exists_has_invoices_sqlite(self, db_sqlite):
        """EXISTS formula not supported on SQLite."""
        pytest.skip('EXISTS formula not supported on SQLite')

    def test_row_count_pg(self, db_pg):
        """invoice.row_count matches actual row count."""
        row = db_pg.table('invc.invoice').query(
            columns='$id, $row_count',
            where='$row_count > 0', limit=1
        ).fetch()[0]
        actual = db_pg.table('invc.invoice_row').query(
            columns='$id',
            where='$invoice_id = :iid', iid=row['id']
        ).count()
        assert int(row['row_count']) == actual

    def test_row_count_sqlite(self, db_sqlite):
        row = db_sqlite.table('invc.invoice').query(
            columns='$id, $row_count',
            where='$row_count > 0', limit=1
        ).fetch()[0]
        actual = db_sqlite.table('invc.invoice_row').query(
            columns='$id',
            where='$invoice_id = :iid', iid=row['id']
        ).count()
        assert int(row['row_count']) == actual

    def test_total_sold_pg(self, db_pg):
        """product.total_sold matches SUM(quantity)."""
        row = db_pg.table('invc.product').query(
            columns='$id, $total_sold',
            where='$total_sold > 0', limit=1
        ).fetch()[0]
        assert float(row['total_sold']) > 0

    def test_total_sold_sqlite(self, db_sqlite):
        row = db_sqlite.table('invc.product').query(
            columns='$id, $total_sold',
            where='$total_sold > 0', limit=1
        ).fetch()[0]
        assert float(row['total_sold']) > 0


class TestCaseWhen:

    def test_customer_rank_pg(self, db_pg):
        """customer.customer_rank uses n_invoices (COUNT subquery)."""
        rows = db_pg.table('invc.customer').query(
            columns='$n_invoices, $customer_rank', limit=20
        ).fetch()
        valid = {'Inactive', 'Occasional', 'Regular'}
        for r in rows:
            assert r['customer_rank'] in valid

    def test_customer_rank_sqlite(self, db_sqlite):
        rows = db_sqlite.table('invc.customer').query(
            columns='$n_invoices, $customer_rank', limit=20
        ).fetch()
        valid = {'Inactive', 'Occasional', 'Regular'}
        for r in rows:
            assert r['customer_rank'] in valid


class TestFilterAggregation:

    def test_priced_rows_pct_pg(self, db_pg):
        """priced_rows_pct is between 0 and 100."""
        rows = db_pg.table('invc.invoice').query(
            columns='$id, $priced_rows_pct',
            where='$priced_rows_pct IS NOT NULL', limit=10
        ).fetch()
        for r in rows:
            pct = float(r['priced_rows_pct'])
            assert 0 <= pct <= 100

    def test_priced_rows_pct_sqlite(self, db_sqlite):
        rows = db_sqlite.table('invc.invoice').query(
            columns='$id, $priced_rows_pct',
            where='$priced_rows_pct IS NOT NULL', limit=10
        ).fetch()
        for r in rows:
            pct = float(r['priced_rows_pct'])
            assert 0 <= pct <= 100


class TestBooleanFormulas:

    def test_is_active_valuable_pg(self, db_pg):
        """is_active_valuable = has_invoices AND n_invoices >= 3."""
        rows = db_pg.table('invc.customer').query(
            columns='$has_invoices, $n_invoices, $is_active_valuable',
            where='$is_active_valuable = TRUE', limit=5
        ).fetch()
        for r in rows:
            assert r['has_invoices'] is True
            assert int(r['n_invoices']) >= 3

    def test_is_active_valuable_sqlite(self, db_sqlite):
        """is_active_valuable references has_invoices (EXISTS)."""
        pytest.skip('EXISTS formula not supported on SQLite')


class TestNamedSubQuery:

    def test_priority_note_pg(self, db_pg):
        """COALESCE(#top_note, 'No notes')."""
        rows = db_pg.table('invc.invoice').query(
            columns='$inv_number, $priority_note', limit=10
        ).fetch()
        for r in rows:
            assert r['priority_note'] is not None

    def test_priority_note_sqlite(self, db_sqlite):
        rows = db_sqlite.table('invc.invoice').query(
            columns='$inv_number, $priority_note', limit=10
        ).fetch()
        for r in rows:
            assert r['priority_note'] is not None

    def test_smart_row_count_pg(self, db_pg):
        """CASE with two named selects (#high_rows, #all_rows)."""
        rows = db_pg.table('invc.invoice').query(
            columns='$inv_number, $total, $smart_row_count',
            where='$smart_row_count IS NOT NULL', limit=10
        ).fetch()
        for r in rows:
            assert int(r['smart_row_count']) >= 0

    def test_smart_row_count_sqlite(self, db_sqlite):
        rows = db_sqlite.table('invc.invoice').query(
            columns='$inv_number, $total, $smart_row_count',
            where='$smart_row_count IS NOT NULL', limit=10
        ).fetch()
        for r in rows:
            assert int(r['smart_row_count']) >= 0


class TestNullif:

    def test_avg_invoice_value_pg(self, db_pg):
        """invoiced_total / NULLIF(n_invoices, 0)."""
        rows = db_pg.table('invc.customer').query(
            columns=(
                '$invoiced_total, $n_invoices, $avg_invoice_value'
            ),
            where='$n_invoices > 0', limit=5
        ).fetch()
        for r in rows:
            expected = (
                float(r['invoiced_total'])
                / float(r['n_invoices'])
            )
            assert (abs(float(r['avg_invoice_value']) - expected)
                    < 0.01)

    def test_avg_invoice_value_sqlite(self, db_sqlite):
        rows = db_sqlite.table('invc.customer').query(
            columns=(
                '$invoiced_total, $n_invoices, $avg_invoice_value'
            ),
            where='$n_invoices > 0', limit=5
        ).fetch()
        for r in rows:
            expected = (
                float(r['invoiced_total'])
                / float(r['n_invoices'])
            )
            assert (abs(float(r['avg_invoice_value']) - expected)
                    < 0.01)


class TestExistsOr:

    def test_has_activity_pg(self, db_pg):
        rows = db_pg.table('invc.customer').query(
            columns='$account_name, $has_activity',
            where='$has_activity = TRUE', limit=5
        ).fetch()
        assert len(rows) > 0

    def test_has_activity_sqlite(self, db_sqlite):
        """has_activity uses EXISTS, not supported on SQLite."""
        pytest.skip('EXISTS formula not supported on SQLite')


class TestPostgresOnly:

    def test_invoice_numbers_pg(self, db_pg):
        """array_to_string(ARRAY(#inv_nums), ', ')."""
        rows = db_pg.table('invc.customer').query(
            columns='$account_name, $invoice_numbers',
            where='$n_invoices > 0', limit=5
        ).fetch()
        for r in rows:
            assert isinstance(r['invoice_numbers'], str)

    def test_all_notes_string_agg_pg(self, db_pg):
        """STRING_AGG returns concatenated notes."""
        rows = db_pg.table('invc.invoice').query(
            columns='$inv_number, $all_notes',
            where='$all_notes IS NOT NULL', limit=5
        ).fetch()
        for r in rows:
            assert isinstance(r['all_notes'], str)
            assert len(r['all_notes']) > 0


class TestWhereOrderBy:

    def test_where_exists_pg(self, db_pg):
        """has_invoices=TRUE count matches distinct customers."""
        n_with = db_pg.table('invc.customer').query(
            columns='$id',
            where='$has_invoices = TRUE'
        ).count()
        all_inv = db_pg.table('invc.invoice').query(
            columns='$customer_id'
        ).fetch()
        n_distinct = len(set(r['customer_id'] for r in all_inv))
        assert n_with == n_distinct

    def test_where_exists_sqlite(self, db_sqlite):
        """EXISTS formula not supported on SQLite."""
        pytest.skip('EXISTS formula not supported on SQLite')


class TestCombinedQueries:

    def test_customer_full_pg(self, db_pg):
        """Customer with count, sum, bool, alias, formula."""
        rows = db_pg.table('invc.customer').query(
            columns=('$account_name, $n_invoices, $invoiced_total,'
                     ' $has_invoices, $customer_rank, $state_name,'
                     ' $display_name, $contact_info'),
            where='$n_invoices > 0',
            order_by='$n_invoices DESC',
            limit=10
        ).fetch()
        assert len(rows) == 10
        for r in rows:
            assert int(r['n_invoices']) > 0
            assert r['customer_rank'] in {
                'Occasional', 'Regular'
            }

    def test_customer_full_sqlite(self, db_sqlite):
        """has_invoices uses EXISTS, not supported on SQLite."""
        rows = db_sqlite.table('invc.customer').query(
            columns=('$account_name, $n_invoices, $invoiced_total,'
                     ' $customer_rank, $state_name,'
                     ' $display_name, $contact_info'),
            where='$n_invoices > 0',
            order_by='$n_invoices DESC',
            limit=10
        ).fetch()
        assert len(rows) == 10

    def test_invoice_full_pg(self, db_pg):
        """Invoice with all cross-db VCs."""
        rows = db_pg.table('invc.invoice').query(
            columns=('$inv_number, $customer_name, $row_count,'
                     ' $value_category, $display_total,'
                     ' $invoice_status, $status_label,'
                     ' $priority_note, $number_series,'
                     ' $smart_row_count'),
            where='$row_count > 0',
            order_by='$display_total DESC',
            limit=10
        ).fetch()
        assert len(rows) == 10

    def test_invoice_full_sqlite(self, db_sqlite):
        rows = db_sqlite.table('invc.invoice').query(
            columns=('$inv_number, $customer_name, $row_count,'
                     ' $value_category, $display_total,'
                     ' $invoice_status, $status_label,'
                     ' $priority_note, $number_series,'
                     ' $smart_row_count'),
            where='$row_count > 0',
            order_by='$display_total DESC',
            limit=10
        ).fetch()
        assert len(rows) == 10


class TestExistsDict:

    def test_has_expensive_rows_pg(self, db_pg):
        rows = db_pg.table('invc.invoice').query(
            columns='$inv_number, $has_expensive_rows',
            limit=10
        ).fetch()
        assert len(rows) == 10
        for r in rows:
            assert r['has_expensive_rows'] in (True, False)

    @pytest.mark.skipif(True, reason='EXISTS not supported on SQLite')
    def test_has_expensive_rows_sqlite(self, db_sqlite):
        rows = db_sqlite.table('invc.invoice').query(
            columns='$inv_number, $has_expensive_rows',
            limit=10
        ).fetch()
        assert len(rows) == 10

    def test_has_expensive_rows_where_pg(self, db_pg):
        rows = db_pg.table('invc.invoice').query(
            columns='$id AS pkey, $inv_number, $total',
            where='$has_expensive_rows IS TRUE',
            limit=5
        ).fetch()
        for r in rows:
            max_price = db_pg.table('invc.invoice_row').query(
                columns='MAX($unit_price) AS value',
                where='$invoice_id=:iid', iid=r['pkey']
            ).fetch()[0]['value']
            assert max_price is not None and float(max_price) > 100


class TestGroupByHaving:

    def test_duplicate_products_pg(self, db_pg):
        rows = db_pg.table('invc.invoice').query(
            columns='$inv_number, $duplicate_products',
            limit=20
        ).fetch()
        assert len(rows) == 20
        for r in rows:
            assert r['duplicate_products'] is not None
            assert int(r['duplicate_products']) >= 0

    def test_duplicate_products_sqlite(self, db_sqlite):
        rows = db_sqlite.table('invc.invoice').query(
            columns='$inv_number, $duplicate_products',
            limit=20
        ).fetch()
        assert len(rows) == 20
        for r in rows:
            assert int(r['duplicate_products']) >= 0
