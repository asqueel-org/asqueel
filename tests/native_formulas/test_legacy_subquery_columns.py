"""Legacy subQueryColumn assertions; scalar readColumns adapted to query.fetch."""

class TestSubQueryColumn:

    def test_rows_json_pg(self, db_pg):
        """mode='json': returns a list of dicts."""
        rows = db_pg.table('invc.invoice').query(columns='$id, $rows_json', where='$row_count > 0', limit=3).fetch()
        for r in rows:
            if r['rows_json']:
                data = r['rows_json']
                assert isinstance(data, list)
                assert len(data) > 0
                assert 'product_id' in data[0]

    def test_notes_xml_pg(self, db_pg):
        """mode='xml': returns XML-like string."""
        rows = db_pg.table('invc.invoice').query(columns='$id, $notes_xml', where='$notes_xml IS NOT NULL', limit=3).fetch()
        for r in rows:
            if r['notes_xml']:
                xml_str = str(r['notes_xml'])
                assert '<' in xml_str

    def test_max_row_price_pg(self, db_pg):
        """mode=None (plain): MAX(unit_price) is numeric."""
        rows = db_pg.table('invc.invoice').query(columns='$id, $max_row_price', where='$max_row_price IS NOT NULL', limit=5).fetch()
        for r in rows:
            assert float(r['max_row_price']) > 0

    def test_max_row_price_sqlite(self, db_sqlite):
        rows = db_sqlite.table('invc.invoice').query(columns='$id, $max_row_price', where='$max_row_price IS NOT NULL', limit=5).fetch()
        for r in rows:
            assert float(r['max_row_price']) > 0

    def test_notes_xml_distinct_pg(self, db_pg):
        """mode='xml' under SELECT DISTINCT: xml has no equality operator."""
        rows = db_pg.table('invc.invoice').query(columns='$id, $notes_xml', where='$notes_xml IS NOT NULL', distinct=True, limit=3).fetch()
        assert rows
        for r in rows:
            assert '<' in str(r['notes_xml'])

    def test_rows_json_distinct_pg(self, db_pg):
        """mode='json' under SELECT DISTINCT: still parsed to a list."""
        rows = db_pg.table('invc.invoice').query(columns='$id, $rows_json', where='$row_count > 0', distinct=True, limit=3).fetch()
        assert rows
        for r in rows:
            if r['rows_json']:
                data = r['rows_json']
                assert isinstance(data, list)
                assert 'product_id' in data[0]

    def test_max_row_price_cross_validate_pg(self, db_pg):
        """max_row_price matches direct MAX query."""
        row = db_pg.table('invc.invoice').query(columns='$id, $max_row_price', where='$max_row_price IS NOT NULL', limit=1).fetch()[0]
        mx = db_pg.table('invc.invoice_row').query(columns='MAX($unit_price) AS mx', where='$invoice_id = :iid', iid=row['id']).fetch()[0]['mx']
        assert abs(float(row['max_row_price']) - float(mx)) < 0.01
