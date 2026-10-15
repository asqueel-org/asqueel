"""Four unchanged legacy bagItemColumn result tests; native model/CSV fixtures."""

class TestBagItemColumn:

    def test_detail_weight_no_crash_pg(self, db_pg):
        """bagItemColumn doesn't crash (likely returns None)."""
        rows = db_pg.table('invc.product').query(
            columns='$description, $detail_weight', limit=5
        ).fetch()
        assert len(rows) == 5

    def test_detail_color_no_crash_pg(self, db_pg):
        rows = db_pg.table('invc.product').query(
            columns='$description, $detail_color', limit=5
        ).fetch()
        assert len(rows) == 5

    def test_bagitem_with_physical_pg(self, db_pg):
        """bagItemColumn alongside physical columns."""
        rows = db_pg.table('invc.product').query(
            columns='$code, $unit_price, $detail_weight, $detail_color',
            limit=5
        ).fetch()
        assert len(rows) == 5
        for r in rows:
            assert r['code'] is not None

    def test_bagitem_custom_dtype_pg(self, db_pg):
        """bagItemColumn with a package custom dtype compiles and runs (#22)."""
        rows = db_pg.table('invc.product').query(
            columns='$description, $detail_price', limit=5
        ).fetch()
        assert len(rows) == 5
