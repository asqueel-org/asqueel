"""formulaColumn as legacy, formulaColumn_<name>() dynamic columns, compositeColumn read as a value (Macro 5, Phase 3)."""
import pytest

from asqueel import AsqueelDb, SqlDatabaseConfig, SqlTable
from tests.option_tables_support import IMPLEMENTATIONS, migrated_db


class Customer(SqlTable):
    def formulaColumn_labels(self):
        return [dict(name='code_twice', sql_formula='$code || $code', dtype='T'),
                dict(name='scaled', sql_formula=f"$year * {self.db.currentEnv.get('factor', 1)}", dtype='L')]

    def formulaColumn_single(self):
        return dict(name='loud', sql_formula='upper($code)', dtype='T')


def declare(pkg):
    customer = pkg.table('customer', pkey='id', x_table_class=Customer)
    customer.column('id', dtype='serial')
    customer.column('code')
    customer.column('year', dtype='L')
    customer.formulaColumn('has_big', sql_formula='#big', dtype='B',
                           exists_big=dict(table='app.invoice', where='$customer_id=#THIS.id AND $amount > 100'))
    customer.formulaColumn('big_and_total', sql_formula='#big AND #total > 150', dtype='B',
                           exists_big=dict(table='app.invoice', where='$customer_id=#THIS.id AND $amount > 100'),
                           select_total=dict(table='app.invoice', columns='SUM($amount)',
                                             where='$customer_id=#THIS.id'))
    invoice = pkg.table('invoice', pkey='id')
    invoice.column('id', dtype='serial')
    invoice.column('customer_id', dtype='L').relation('app.customer.id', relation_name='invoices')
    invoice.column('amount', dtype='N')
    doc = pkg.table('doc', pkey='identity')
    doc.column('code')
    doc.column('year', dtype='L')
    doc.compositeColumn('identity', columns='code,year')


@pytest.fixture(params=IMPLEMENTATIONS)
def db(request, tmp_path):
    with migrated_db(request.param, tmp_path, declare) as db:
        customer = db.table('app.customer')
        customer.sql_insert([{'id': 1, 'code': 'a', 'year': 2025}, {'id': 2, 'code': 'b', 'year': 2026}])
        db.table('app.invoice').sql_insert([{'customer_id': 1, 'amount': 120}, {'customer_id': 1, 'amount': 50},
                                            {'customer_id': 2, 'amount': 30}])
        db.table('app.doc').sql_insert([{'code': 'A', 'year': 2026}, {'code': 'B', 'year': 2025}])
        db.commit()
        yield db


def values(db, table, columns, **kwargs):
    return [dict(row) for row in db.table(table).query(columns=columns, order_by='$id', **kwargs).fetch()]


def test_exists_named_subquery_becomes_an_exists_clause(db):
    rows = values(db, 'app.customer', '$id,$has_big')
    assert [row['has_big'] for row in rows] == [True, False]


def test_exists_and_select_named_subqueries_combine_in_one_formula(db):
    rows = values(db, 'app.customer', '$id,$big_and_total')
    assert [row['big_and_total'] for row in rows] == [True, False]


def test_dynamic_formula_columns_come_from_table_methods(db):
    rows = values(db, 'app.customer', '$id,$code_twice,$loud')
    assert [(row['code_twice'], row['loud']) for row in rows] == [('aa', 'A'), ('bb', 'B')]


def test_dynamic_formula_columns_are_evaluated_in_the_environment(db):
    with db.tempEnv(factor=3):
        rows = values(db, 'app.customer', '$id,$scaled')
    assert [row['scaled'] for row in rows] == [6075, 6078]


def test_composite_column_reads_as_the_legacy_string(db):
    rows = db.table('app.doc').query(columns='$identity', order_by='$code').fetch()
    assert [row['identity'] for row in rows] == ['["A", 2026]', '["B", 2025]']


def test_table_with_a_composite_primary_key_reads_all_its_columns(db):
    rows = db.table('app.doc').query(columns='*', where='$identity=:key', key='["B", 2025]').fetch()
    assert [(row['code'], row['year']) for row in rows] == [('B', 2025)]


def memory_package():
    config = SqlDatabaseConfig()
    root = config.source.db('formulas', implementation='sqlite')
    root.connection('main', database=':memory:')
    pkg = root.packages().package('app', sqlschema='main', sqlprefix=False)
    customer = pkg.table('customer', pkey='id')
    customer.column('id', dtype='L')
    customer.column('code')
    return config, customer


def compile_column(config, name):
    return AsqueelDb(config).table('app.customer').query(columns=f'${name}').compiled


def test_formula_column_dtype_defaults_to_a():
    config, customer = memory_package()
    customer.formulaColumn('label', sql_formula='$code')
    assert AsqueelDb(config).model.table('app.customer').column('label').dtype == 'A'


@pytest.mark.parametrize('key', ['expression', 'parameters'])
def test_expression_and_parameters_are_outside_the_grammar(key):
    _, customer = memory_package()
    with pytest.raises(ValueError, match=f"Element 'formulaColumn' does not accept '{key}'"):
        customer.formulaColumn('label', sql_formula='$code', **{key: {'x': 1} if key == 'parameters' else '$code'})


@pytest.mark.parametrize('key', ['select', 'exists'])
def test_sql_formula_together_with_select_or_exists_is_an_error(key):
    config, customer = memory_package()
    with pytest.raises(ValueError, match='sql_formula cannot be combined with select or exists'):
        customer.formulaColumn('label', sql_formula='$code',
                               **{key: dict(table='app.customer', columns='$code', where='$id=#THIS.id')})
        compile_column(config, 'label')


def test_select_and_exists_with_the_same_name_are_an_error():
    config, customer = memory_package()
    subquery = dict(table='app.customer', columns='$code', where='$id=#THIS.id')
    with pytest.raises(ValueError, match='select_twin and exists_twin'):
        customer.formulaColumn('label', sql_formula='#twin', dtype='B', select_twin=subquery, exists_twin=subquery)
        compile_column(config, 'label')
