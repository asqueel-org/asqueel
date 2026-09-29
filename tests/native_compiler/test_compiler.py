import pytest

from genro_sql.compiler import PostgresCompiler
from genro_sql.contracts import Column, Relation, ResolvedModel, Table, UnsupportedFeatureError


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


def test_projection_join_reuse_and_metadata(compiler):
    query = compiler.select('invoice', '$id, @customer.name AS customer, $quad',
                            where='@customer.name = :name', params={'name': "O'Reilly"},
                            order_by='@customer.name DESC', limit=0, offset=0)
    assert query.sql.count('LEFT JOIN') == 1
    assert '"Actual ""Schema"."app_customer"' in query.sql
    assert '"t1"."full%%name" AS "customer"' in query.sql
    assert '(("t0"."amount" * 2) * 2)' in query.sql
    assert query.sql.endswith('LIMIT 0 OFFSET 0')
    assert dict(query.params) == {'name': "O'Reilly"}
    assert query.columns[1].source == 'app.customer.name'
    assert query.columns[1].ui == {'label': 'Name'}


def test_scanner_preserves_sql_literals_comments_cast_and_percent(compiler):
    query = compiler.select('invoice',
        "$id, concat('$missing :no @n.x #X', $$:no $none$$, $tag$:no$tag$) AS text",
        where="$id = :id::integer AND '10%' LIKE :pattern /* :missing /* nested */ */",
        params={'id': 1, 'pattern': '10%'})
    assert "'$missing :no @n.x #X'" in query.sql
    assert '$$:no $none$$' in query.sql
    assert '$tag$:no$tag$' in query.sql
    assert "'10%%'" in query.sql
    assert '%(id)s::integer' in query.sql
    assert dict(query.params) == {'id': 1, 'pattern': '10%'}


def test_escape_string_and_quoted_alias(compiler):
    query = compiler.select('invoice', r'''E'a\'b :fake' AS "a""b", $id AS "50%"''')
    assert [c.name for c in query.columns] == ['a"b', '50%']
    assert 'AS "50%%"' in query.sql
    assert not query.params


def test_cast_as_is_not_projection_alias(compiler):
    query = compiler.select('invoice', 'CAST($id AS text) AS id_text')
    assert 'CAST("t0"."id" AS text)' in query.sql


def test_missing_parameters_and_duplicate_aliases(compiler):
    with pytest.raises(ValueError, match='Missing query parameter'):
        compiler.select('invoice', where='$id=:unknown')
    with pytest.raises(ValueError, match='Duplicate result alias'):
        compiler.select('invoice', '$id, $amount AS id')
    with pytest.raises(ValueError, match='explicit AS'):
        compiler.select('invoice', '$amount * 2')


@pytest.mark.parametrize('expression', ["$id; DELETE FROM x", '#SOMETHING($id)',
                                        '$unknown', '@missing.id', 'aggregateRows($id)'])
def test_unsupported_or_unknown_expressions_fail(compiler, expression):
    with pytest.raises(ValueError):
        compiler.select('invoice', where=expression)


@pytest.mark.parametrize('expression', ["'unclosed", '$tag$unclosed', '/* open'])
def test_unclosed_tokens_fail(compiler, expression):
    with pytest.raises(ValueError, match='Unclosed'):
        compiler.select('invoice', where=expression)


@pytest.mark.parametrize('value', [-1, True, 2.5, '1; DROP TABLE x'])
def test_pagination_validated(compiler, value):
    with pytest.raises(ValueError):
        compiler.select('invoice', limit=value)


def test_formula_cycles_fail():
    table = Table('t', columns={'a': Column('a', formula='$b'),
                               'b': Column('b', formula='$a')})
    with pytest.raises(ValueError, match='Cyclic formula'):
        PostgresCompiler(ResolvedModel({table.key: table})).select('t')


def test_insert_values_mapping_and_default_values(compiler):
    query = compiler.insert('customer', {'id': 1, 'name': "Robert'); DROP TABLE x;--"})
    assert '"full%%name"' in query.sql
    assert 'DROP TABLE' not in query.sql
    assert list(query.params.values()) == [1, "Robert'); DROP TABLE x;--"]
    assert query.columns[1].name == 'name'
    assert 'DEFAULT VALUES' in compiler.insert('customer', {}, returning=None).sql


def test_update_collision_returning_and_line_comment(compiler):
    query = compiler.update('invoice', {'amount': 4}, '$id=:__value_0 -- trailing',
                            params={'__value_0': 1}, returning='$id, $double')
    assert query.params['__value_0'] == 1
    assert query.params['___value_0'] == 4
    assert '-- trailing\n RETURNING' in query.sql
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


def test_removed_aggregate_rows_option_is_explicit(compiler):
    with pytest.raises(UnsupportedFeatureError, match='removed'):
        compiler.select('invoice', aggregateRows=True)
    with pytest.raises(UnsupportedFeatureError, match='Unsupported query options'):
        compiler.select('invoice', group_by='$id')


@pytest.mark.parametrize('name', ['display name', 'a-b', 'città', 'αριθμός', '50%', 'a"b'])
def test_quoted_logical_names_work_in_wildcards_predicates_and_returning(name):
    table = Table('t', columns={name: Column(name)})
    compiler = PostgresCompiler(ResolvedModel({table.key: table}))
    reference = '$"' + name.replace('"', '""') + '"'
    selected = compiler.select('t', where=reference + ' = :value', params={'value': 'x'},
                                order_by=reference)
    assert selected.columns[0].name == name
    assert selected.sql.count('"t0".') == 3
    assert '%(value)s' in selected.sql
    for query in [compiler.insert('t', {name: 'x'}),
                  compiler.update('t', {name: 'y'}, reference + '=:value', {'value': 'x'}),
                  compiler.delete('t', 'TRUE')]:
        assert query.columns[0].name == name


def test_literal_quoted_field_syntax_is_not_interpreted(compiler):
    query = compiler.select('invoice', ''''$"missing"' AS text, $$; $id :x$$ AS body''')
    assert ''''$"missing"' AS "text"''' in query.sql
    assert '$$; $id :x$$' in query.sql
    assert not query.params


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


def test_manual_relation_without_unique_target_rejected():
    target = Table('target', columns={'id': Column('id')})
    source = Table('source', columns={'id': Column('id')},
                   relations={'target': Relation('target', target.key, ('id',), ('id',))})
    compiler = PostgresCompiler(ResolvedModel({target.key: target, source.key: source}))
    with pytest.raises(UnsupportedFeatureError, match='unique key'):
        compiler.select('source', '@target.id')
    # A standalone table without a primary key remains queryable.
    assert compiler.select('target').columns[0].name == 'id'


@pytest.mark.parametrize('attributes', [
    {'constraints': ({'constraint_type': 'UNIQUE', 'columns': 'id'},)},
    {'constraints': ({'kind': 'u', 'columns': ['id']},)},
])
def test_manual_relation_accepts_normalized_unique_constraints(attributes):
    target = Table('target', columns={'id': Column('id')}, attributes=attributes)
    source = Table('source', columns={'id': Column('id')},
                   relations={'target': Relation('target', target.key, ('id',), ('id',))})
    compiler = PostgresCompiler(ResolvedModel({target.key: target, source.key: source}))
    assert 'LEFT JOIN' in compiler.select('source', '@target.id').sql


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
