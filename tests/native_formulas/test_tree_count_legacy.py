# ruff: noqa: F811
"""Eight unchanged legacy count bodies; fixture compiles tree SQL separately."""
from tests.native_formulas.test_tree_phase4_results import db_pg, db_sqlite  # noqa: F401

from tests.native_formulas.conftest import db_pg as execution_pg, db_sqlite as execution_sqlite  # noqa: F401

CUSTOMER_COUNT = 3200

class TestPhysicalColumns:

    def test_count_matches_expected_pg(self, db_pg):
        n = db_pg.table('invc.customer').query(columns='$id').count()
        assert n == CUSTOMER_COUNT

    def test_count_matches_expected_sqlite(self, db_sqlite):
        n = db_sqlite.table('invc.customer').query(columns='$id').count()
        assert n == CUSTOMER_COUNT

class TestDraftField:

    def test_draft_filter_count_pg(self, db_pg):
        """Default query excludes drafts, count must match."""
        default = db_pg.table('invc.customer').query().count()
        no_draft = db_pg.table('invc.customer').query(excludeDraft=False).count()
        assert default == no_draft == CUSTOMER_COUNT

    def test_draft_filter_count_sqlite(self, db_sqlite):
        default = db_sqlite.table('invc.customer').query().count()
        no_draft = db_sqlite.table('invc.customer').query(excludeDraft=False).count()
        assert default == no_draft == CUSTOMER_COUNT

class TestCompiledQueryOptions:

    def test_count_with_group_by_pg(self, db_pg):
        tbl = db_pg.table('invc.invoice')
        n = tbl.query(columns='$customer_id, SUM($total) AS sum_total', group_by='$customer_id').count()
        assert n > 1

    def test_count_with_group_by_sqlite(self, db_sqlite):
        tbl = db_sqlite.table('invc.invoice')
        n = tbl.query(columns='$customer_id, SUM($total) AS sum_total', group_by='$customer_id').count()
        assert n > 1

    def test_count_with_distinct_pg(self, db_pg):
        tbl = db_pg.table('invc.invoice')
        n = tbl.query(columns='$customer_id', distinct=True).count()
        assert n > 1

    def test_count_with_distinct_sqlite(self, db_sqlite):
        tbl = db_sqlite.table('invc.invoice')
        n = tbl.query(columns='$customer_id', distinct=True).count()
        assert n > 1
