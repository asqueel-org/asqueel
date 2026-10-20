"""Legacy read-policy and star tests; partition value supplied at native render."""
CUSTOMER_COUNT = 3200
CUSTOMER_NSW_COUNT = 399
INVOICE_NSW_COUNT = 21


class TestPhysicalColumns:

    def test_star_expansion_pg(self, db_pg):
        rows = db_pg.table('invc.customer').query(columns='*', limit=1).fetch()
        assert len(rows) == 1
        r = rows[0]
        assert 'account_name' in r
        assert 'email' in r

    def test_star_expansion_sqlite(self, db_sqlite):
        rows = db_sqlite.table('invc.customer').query(columns='*', limit=1).fetch()
        assert len(rows) == 1
        r = rows[0]
        assert 'account_name' in r
        assert 'email' in r

class TestDraftField:

    def test_is_confirmed_pg(self, db_pg):
        rows = db_pg.table('invc.customer').query(columns='$account_name, $is_confirmed', limit=10).fetch()
        assert len(rows) == 10
        for r in rows:
            assert r['is_confirmed'] is True

    def test_is_confirmed_sqlite(self, db_sqlite):
        rows = db_sqlite.table('invc.customer').query(columns='$account_name, $is_confirmed', limit=10).fetch()
        assert len(rows) == 10
        for r in rows:
            assert bool(r['is_confirmed'])

    def test_draft_filter_count_pg(self, db_pg):
        """Default query excludes drafts, count must match."""
        default = db_pg.table('invc.customer').query().count()
        no_draft = db_pg.table('invc.customer').query(excludeDraft=False).count()
        assert default == no_draft == CUSTOMER_COUNT

    def test_draft_filter_count_sqlite(self, db_sqlite):
        default = db_sqlite.table('invc.customer').query().count()
        no_draft = db_sqlite.table('invc.customer').query(excludeDraft=False).count()
        assert default == no_draft == CUSTOMER_COUNT

class TestPartitionCurrentState:

    def test_customer_partition_nsw_pg(self, partition_pg):
        count = partition_pg.table('invc.customer').query().count()
        assert count == CUSTOMER_NSW_COUNT

    def test_customer_partition_nsw_sqlite(self, partition_sqlite):
        count = partition_sqlite.table('invc.customer').query().count()
        assert count == CUSTOMER_NSW_COUNT

    def test_invoice_partition_nsw_pg(self, partition_pg):
        count = partition_pg.table('invc.invoice').query().count()
        assert count == INVOICE_NSW_COUNT

    def test_invoice_partition_nsw_sqlite(self, partition_sqlite):
        count = partition_sqlite.table('invc.invoice').query().count()
        assert count == INVOICE_NSW_COUNT

    def test_partition_ignore_pg(self, partition_pg):
        """ignorePartition=True bypasses the filter."""
        count = partition_pg.table('invc.customer').query(ignorePartition=True).count()
        assert count == CUSTOMER_COUNT

    def test_partition_ignore_sqlite(self, partition_sqlite):
        count = partition_sqlite.table('invc.customer').query(ignorePartition=True).count()
        assert count == CUSTOMER_COUNT

class TestPartitionAllowedStates:

    def test_no_partition_full_count_pg(self, db_pg):
        """Without env vars, no partition filter — full count."""
        count = db_pg.table('invc.customer').query().count()
        assert count == CUSTOMER_COUNT

    def test_no_partition_full_count_sqlite(self, db_sqlite):
        count = db_sqlite.table('invc.customer').query().count()
        assert count == CUSTOMER_COUNT

class TestExcludeLogicalDeletedMark:

    def test_mark_adds_isdeleted_column_pg(self, db_pg):
        tbl = db_pg.table('invc.customer')
        rows = tbl.query(columns='$id, $account_name', excludeLogicalDeleted='mark').fetch()
        assert isinstance(rows, list)
        assert '_isdeleted' in rows[0]

    def test_mark_adds_isdeleted_column_sqlite(self, db_sqlite):
        tbl = db_sqlite.table('invc.customer')
        rows = tbl.query(columns='$id, $account_name', excludeLogicalDeleted='mark').fetch()
        assert isinstance(rows, list)
        assert '_isdeleted' in rows[0]
