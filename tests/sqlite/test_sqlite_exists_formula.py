"""Formula subqueries compile to SQL that SQLite executes."""
from asqueel import AsqueelDb, SqlDatabaseConfig


def recipe(path):
    class Recipe(SqlDatabaseConfig):
        def main(self, root):
            db = root.db()
            db.connection(name=str(path), implementation='sqlite')
            tables = db.packages().package('app', sqlschema='app', sqlprefix=False).tables()
            invoice = tables.table('invoice', pkey='id')
            invoice.columns().column('id', dtype='L')
            invoice.virtual_columns().formulaColumn('has_lines', dtype='B', exists=dict(
                table='app.line', where='$invoice_id=#THIS.id',
            ))
            line = tables.table('line', pkey='id').columns()
            line.column('id', dtype='L')
            line.column('invoice_id', dtype='L').relation('app.invoice.id')
    return Recipe


def test_an_exists_formula_runs_on_sqlite(tmp_path):
    db = AsqueelDb(recipe(tmp_path / 'sample.db')).session()
    try:
        db.migrate()
        db.table('app.invoice').insert({'id': 1})
        db.table('app.invoice').insert({'id': 2})
        db.table('app.line').insert({'id': 10, 'invoice_id': 1})
        db.commit()
        rows = db.table('app.invoice').query(columns='$id, $has_lines', order_by='$id').fetch()
        assert [(row['id'], bool(row['has_lines'])) for row in rows] == [(1, True), (2, False)]
        db.rollback()
    finally:
        db.shared.close()
