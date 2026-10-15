"""Ported legacy inverse-navigation assertions; explicit output aliases only.

These assertions do not certify the legacy runtime aggregation of child values.
"""

class TestRelationNavigation:

    def test_one_to_many_pg(self, db_pg):
        """customer.@invoices.inv_number one-to-many."""
        rows = db_pg.table('invc.customer').query(columns='$account_name, @invoices.inv_number', where='$has_invoices = TRUE', limit=5).fetch()
        assert len(rows) > 0

    def test_one_to_many_sqlite(self, db_sqlite):
        rows = db_sqlite.table('invc.customer').query(columns='$account_name, @invoices.inv_number', where='$n_invoices > 0', limit=5).fetch()
        assert len(rows) > 0

class TestExplodingFastPath:

    def test_exploding_fast_path_pg(self, db_pg):
        """Two columns from @rows trigger exploding fast path on PG."""
        tbl = db_pg.table('invc.invoice')
        rows = tbl.query(columns='$id, @rows.quantity AS _rows_quantity, @rows.unit_price AS _rows_unit_price', limit=3).fetch()
        assert len(rows) == 3
        for r in rows:
            assert r['_rows_quantity'] is not None
            assert r['_rows_unit_price'] is not None

    def test_exploding_fast_path_sqlite(self, db_sqlite):
        """Two columns from @rows trigger exploding fast path on SQLite."""
        tbl = db_sqlite.table('invc.invoice')
        rows = tbl.query(columns='$id, @rows.quantity AS _rows_quantity, @rows.unit_price AS _rows_unit_price', limit=3).fetch()
        assert len(rows) == 3
        for r in rows:
            assert r['_rows_quantity'] is not None
            assert r['_rows_unit_price'] is not None
