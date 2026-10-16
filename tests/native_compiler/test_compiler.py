import pytest

from asqueel.compiler import PostgresCompiler
from asqueel.contracts import Column, Relation, ResolvedModel, Table, UnsupportedFeatureError


@pytest.fixture
def compiler():
    customer = Table('customer', schema='app', sql_schema='Actual "Schema',
                     sql_prefix='app_', columns={
                         'id': Column('id', 'L'),
                         'name': Column('name', sql_name='full%name', ui={'label': 'Name'}),
                     }, pkey=('id',))
    invoice = Table('invoice', schema='app', sql_schema='Actual "Schema',
                    sql_name='Order', columns={
                        'id': Column('id', 'L'),
                        'customer_id': Column('customer_id', 'L'),
                        'amount': Column('amount', 'N'),
                        'double': Column('double', 'N', formula='$amount * 2'),
                        'quad': Column('quad', 'N', formula='$double * 2'),
                    }, relations={'customer': Relation('customer', 'app.customer',
                                                       ('customer_id',), ('id',))})
    return PostgresCompiler(ResolvedModel({invoice.key: invoice, customer.key: customer}))


def test_insert_values_mapping_and_default_values(compiler):
    query = compiler.insert('customer', {'id': 1, 'name': "Robert'); DROP TABLE x;--"})
    assert '"full%%name"' in query.sql
    assert 'DROP TABLE' not in query.sql
    assert list(query.params.values()) == [1, "Robert'); DROP TABLE x;--"]
    assert query.columns[1].name == 'name'
    assert 'DEFAULT VALUES' in compiler.insert('customer', {}, returning=None).sql


def test_update_collision_returning_and_line_comment(compiler):
    query = compiler.update('invoice', {'amount': 4}, '$id=:__value_0 -- trailing',
                            sqlparams={'__value_0': 1}, returning='$id, $double')
    assert query.params['__value_0'] == 1
    assert query.params['___value_0'] == 4
    assert '-- trailing\n\nRETURNING' in query.sql
    assert 'AS "double"' in query.sql


@pytest.mark.parametrize('predicate', [None, '', ' ', '/* comment */', '-- comment'])
def test_writes_need_predicate(compiler, predicate):
    with pytest.raises(ValueError):
        compiler.delete('invoice', predicate)
    with pytest.raises(ValueError):
        compiler.update('invoice', {'amount': 1}, predicate)


def test_dml_rejects_formula_writes_and_relation_paths(compiler):
    with pytest.raises(ValueError, match='formula'):
        compiler.insert('invoice', {'double': 3})
    with pytest.raises(UnsupportedFeatureError, match='DML'):
        compiler.delete('invoice', '@customer.id=:id', {'id': 1})
    assert 'WHERE TRUE' in compiler.delete('invoice', 'TRUE', returning=None).sql


@pytest.mark.parametrize('name', ['display name', 'a-b', 'città', 'αριθμός', '50%', 'a"b'])
def test_quoted_logical_names_work_in_wildcards_predicates_and_returning(name):
    table = Table('t', columns={name: Column(name)})
    compiler = PostgresCompiler(ResolvedModel({table.key: table}))
    reference = '$"' + name.replace('"', '""') + '"'
    selected = compiler.select('t', where=reference + ' = :value', sqlparams={'value': 'x'},
                                order_by=reference)
    assert selected.columns[0].name == name
    assert selected.sql.count('"t0".') == 3
    assert '%(value)s' in selected.sql
    for query in [compiler.insert('t', {name: 'x'}),
                  compiler.update('t', {name: 'y'}, reference + '=:value', {'value': 'x'}),
                  compiler.delete('t', 'TRUE')]:
        assert query.columns[0].name == name


def test_returning_formula_that_requires_join_is_rejected():
    customer = Table('customer', columns={'id': Column('id')}, pkey=('id',))
    invoice = Table('invoice', columns={'id': Column('id'),
                                      'display': Column('display', formula='@customer.id')},
                    relations={'customer': Relation('customer', customer.key, ('id',), ('id',))})
    compiler = PostgresCompiler(ResolvedModel({customer.key: customer, invoice.key: invoice}))
    for action in [lambda: compiler.insert('invoice', {'id': 1}, returning='$display'),
                   lambda: compiler.update('invoice', {'id': 1}, 'TRUE', returning='$display'),
                   lambda: compiler.delete('invoice', 'TRUE', returning='$display')]:
        with pytest.raises(UnsupportedFeatureError, match='DML'):
            action()
    assert compiler.insert('invoice', {'id': 1}, returning='$id').columns[0].name == 'id'
    assert [c.name for c in compiler.insert('invoice', {'id': 1}).columns] == ['id']


def test_result_source_preserves_stable_identity_across_alias_and_physical_names():
    customer = Table('customer', schema='app', sql_name='renamed_customer', columns={
        'id': Column('id', identity='stable:customer:id'),
        'name': Column('name', sql_name='renamed_name', identity='stable:customer:name',
                       ui={'label': 'Customer'}),
    }, pkey=('id',))
    invoice = Table('invoice', columns={'customer_id': Column('customer_id')}, relations={
        'customer': Relation('customer', customer.key, ('customer_id',), ('id',))})
    compiler = PostgresCompiler(ResolvedModel({customer.key: customer, invoice.key: invoice}))
    direct = compiler.select('customer', '$name AS display')
    related = compiler.select('invoice', '@customer.name AS display')
    written = compiler.insert('customer', {'id': 1, 'name': 'Alice'}, returning='$name AS display')
    for query in (direct, related, written):
        assert query.columns[0].source == 'stable:customer:name'
        assert query.columns[0].name == 'display'
        assert query.columns[0].ui == {'label': 'Customer'}
    assert compiler.select('invoice').columns[0].source == 'public.invoice.customer_id'
