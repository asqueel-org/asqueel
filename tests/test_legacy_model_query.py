"""GenroPy model and query behaviours: name::dtype, falsy limit/offset."""
import pytest

from asqueel import AsqueelDb, SqlBuilder, SqlDatabaseConfig, SqlMigrationRenderer
from asqueel.model import resolve_model
from tests.native_formulas.conftest import db_pg  # noqa: F401


def source():
    b = SqlDatabaseConfig()
    pkg = b.source.db('example', implementation='postgres').packages().package('sales')
    return b, pkg


def test_name_dtype_split_on_column_and_virtual_columns():
    b, pkg = source()
    t = pkg.table('invoice', pkey='id')
    t.column('id', 'L')
    t.column('n::N')
    t.formulaColumn('f::N', sql_formula='$n * 2')
    t.aliasColumn('a::N', relation_path='$n')
    t.column('data', 'X')
    t.pyColumn('p::N', py_method='calc')
    t.bagItemColumn('b::N', bagcolumn='$data', itempath='a')
    table = resolve_model(b).table('sales.invoice')
    assert table.columns['n'].dtype == 'N'
    for name in ('f', 'a', 'p', 'b'):
        assert table.virtual_columns[name].dtype == 'N'
    with pytest.raises(ValueError, match='column: dtype passed twice'):
        t.column('x::N', dtype='T')
    with pytest.raises(ValueError, match="column: 'a::b::c' must be 'name::dtype'"):
        t.column('a::b::c')


def sqlite_db(path):
    source = SqlDatabaseConfig()
    root = source.source.db('records', implementation='sqlite')
    root.connection('main', database=str(path))
    table = root.packages().package('app', sqlschema='main', sqlprefix=False).table('item', pkey='id')
    table.column('id', dtype='L')
    db = AsqueelDb(source)
    db.execute('CREATE TABLE item (id INTEGER PRIMARY KEY)')
    for key in (1, 2, 3):
        db.execute('INSERT INTO item VALUES (:id)', {'id': key})
    db.commit()
    return db


@pytest.mark.parametrize('value', [0, None, False])
def test_falsy_limit_and_offset_emit_no_clause_on_sqlite(tmp_path, value):
    db = sqlite_db(tmp_path / 'limit.sqlite')
    try:
        query = db.table('app.item').query('$id', limit=value, offset=value, order_by='$id')
        assert 'LIMIT' not in query.compiled.sql and 'OFFSET' not in query.compiled.sql
        assert [row['id'] for row in query.fetch()] == [1, 2, 3]
    finally:
        db.closeConnection()


@pytest.mark.postgresql
def test_falsy_limit_and_offset_emit_no_clause_on_postgres(db_pg):  # noqa: F811
    table = db_pg.table('invc.customer')
    every = table.query('$id', order_by='$id').fetch()
    query = table.query('$id', limit=0, offset=0, order_by='$id')
    assert 'LIMIT' not in query.compiled.sql and 'OFFSET' not in query.compiled.sql
    assert query.fetch() == every
    db_pg.rollback()


def test_relation_name_names_the_inverse_relation():
    b, pkg = source()
    invoice = pkg.table('invoice', pkey='id')
    invoice.column('id', 'L')
    invoice.column('customer_id', 'L').relation('customer.id', relation_name='invoices')
    pkg.table('customer', pkey='id').column('id', 'L')
    model = resolve_model(b)
    assert model.table('sales.customer').relations.get_node('@invoices').attr['joiner']['mode'] == 'M'
    forward = model.table('sales.invoice').relations.get_node('@customer_id').attr['joiner']
    assert forward['relation_name'] == 'invoices'
    assert forward['private_relation'] is False


def fk_attributes(builder, table):
    tables = SqlMigrationRenderer(builder).render()['root']['schemas']['public']['tables']
    return next(iter(tables[table]['relations'].values()))['attributes']


def test_sql_actions_reach_the_migration_foreign_key_in_a_package():
    b, pkg = source()
    invoice = pkg.table('invoice', pkey='id')
    invoice.column('id', 'L')
    invoice.column('customer_id', 'L').relation(
        'customer.id', onDelete='setnull', onDelete_sql='cascade', onUpdate_sql='setnull')
    pkg.table('customer', pkey='id').column('id', 'L')
    fk = fk_attributes(b, 'sales_invoice')
    assert fk['on_delete'] == 'CASCADE' and fk['on_update'] == 'SET NULL'
    assert fk['deferrable'] and fk['initially_deferred']
    joiner = resolve_model(b).table('sales.invoice').relations.get_node('@customer_id').attr['joiner']
    assert (joiner['onDelete'], joiner['onDelete_sql'], joiner['onUpdate_sql']) == ('setnull', 'cascade', 'setnull')


def test_sql_actions_reach_the_migration_foreign_key_outside_a_package():
    class Recipe(SqlBuilder):
        def main(self, root):
            tables = root.db(name='d').schemas().schema(name='public').tables()
            tables.table(name='customer', pkey='id').columns().column(name='id', dtype='L')
            invoice = tables.table(name='invoice', pkey='id').columns()
            invoice.column(name='id', dtype='L')
            invoice.column(name='customer_id', dtype='L').relation(
                'public.customer.id', foreign_key=True, onDelete_sql='SET NULL')
    b = Recipe()
    b.create()
    fk = fk_attributes(b, 'invoice')
    assert fk['on_delete'] == 'SET NULL' and fk['on_update'] == 'CASCADE'
    # The physical layer mirrors the database: deferral is never implied.
    assert 'deferrable' not in fk


@pytest.mark.parametrize('key,value', [('onDelete_sql', 'set_null'), ('onUpdate_sql', 'X'),
                                       ('onDelete', 'set_null')])
def test_action_names_outside_the_legacy_ones_raise(key, value):
    b, pkg = source()
    invoice = pkg.table('invoice', pkey='id')
    invoice.column('id', 'L')
    invoice.column('customer_id', 'L').relation('customer.id', **{key: value})
    pkg.table('customer', pkey='id').column('id', 'L')
    with pytest.raises(ValueError, match=f'invalid {key} {value!r}'):
        resolve_model(b)
