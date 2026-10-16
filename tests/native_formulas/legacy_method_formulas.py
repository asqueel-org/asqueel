"""Unchanged method-formula tests from the frozen legacy compiler corpus."""

class TestSqlFormulaTrueDelegate:
    """GAP 3c — sql_formula=True delegate (compiler.py:396).

    When a formulaColumn has sql_formula=True (boolean, not a string),
    the compiler calls sql_formula_<fieldname>(attr) on the table object
    to generate the SQL formula dynamically.

    sysFields registers __protecting_reasons and __invalid_reasons with
    sql_formula=True; the methods sql_formula___protecting_reasons and
    sql_formula___invalid_reasons on TableBase build the formula at
    compile time based on the table's protection/validation columns.
    """

    def test_protecting_reasons_pg(self, db_pg):
        """sql_formula=True resolves via sql_formula___protecting_reasons on PG."""
        tbl = db_pg.table('invc.customer')
        rows = tbl.query(
            columns='$id, $__protecting_reasons',
            limit=3
        ).fetch()
        assert len(rows) == 3

    def test_protecting_reasons_sqlite(self, db_sqlite):
        """sql_formula=True resolves via sql_formula___protecting_reasons on SQLite."""
        tbl = db_sqlite.table('invc.customer')
        rows = tbl.query(
            columns='$id, $__protecting_reasons',
            limit=3
        ).fetch()
        assert len(rows) == 3
