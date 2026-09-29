"""Alias columns retain declaration identity while resolving values at their owner."""
from dataclasses import replace

import pytest

from genro_sql.compiler import PostgresCompiler
from genro_sql.contracts import Column, Relation, ResolvedModel, Table, UnsupportedFeatureError


@pytest.fixture
def model():
    country = Table('country', schema='app', pkey=('id',), columns={
        'id': Column('id', 'L'),
        'name': Column('name', sql_name='country_name', ui={'label': 'Country', 'width': 20}),
    })
    customer = Table('customer', schema='app', pkey=('id',), columns={
        'id': Column('id', 'L'), 'country_id': Column('country_id', 'L'),
        'country': Column('country', relation_path='@country.name'),
        'code': Column('code', 'L', sql_name='numeric_code'),
        'double': Column('double', 'L', formula='$code * 2'),
    }, relations={'country': Relation('country', country.key, ('country_id',), ('id',))})
    invoice = Table('invoice', schema='app', pkey=('id',), columns={
        'id': Column('id', 'L'), 'customer_id': Column('customer_id', 'L'),
        'local_id': Column('local_id', relation_path='id'),
        'customer_code': Column('customer_code', relation_path='@customer.code', identity='stable-code'),
        'country_name': Column('country_name', relation_path='@customer.@country.name',
                               ui={'label': 'Invoice country'}, identity='stable-country'),
        'via_alias': Column('via_alias', relation_path='@customer.country'),
        'twice': Column('twice', relation_path='@customer.double'),
    }, relations={'customer': Relation('customer', customer.key, ('customer_id',), ('id',))})
    return ResolvedModel({table.key: table for table in (country, customer, invoice)})


def test_alias_metadata_and_all_clauses_reuse_joins(model):
    query = PostgresCompiler(model).select(
        'invoice', '$customer_code AS code, $country_name AS label, $via_alias',
        where='$customer_code=:code AND @customer.@country.name=:name',
        params={'code': 7, 'name': 'Italy'}, order_by='$country_name')
    assert query.sql.count('LEFT JOIN') == 2
    assert '"t1"."numeric_code" AS "code"' in query.sql
    assert '"t2"."country_name" AS "label"' in query.sql
    assert query.sql.endswith('ORDER BY "t2"."country_name"')
    assert query.columns[0].source == 'stable-code'
    assert query.columns[0].dtype == 'L'
    assert query.columns[1].source == 'stable-country'
    assert query.columns[1].ui == {'label': 'Invoice country', 'width': 20}
    assert query.columns[2].source == 'app.invoice.via_alias'


def test_formula_target_is_evaluated_in_related_table_scope(model):
    query = PostgresCompiler(model).select('invoice', '$twice')
    assert '("t1"."numeric_code" * 2) AS "twice"' in query.sql
    assert query.columns[0].dtype == 'L'


def test_legacy_and_native_paths_have_same_sql_and_default_alias(model):
    compiler = PostgresCompiler(model)
    legacy = compiler.select('invoice', '@customer.@country.name')
    native = compiler.select('invoice', '@customer.country.name')
    assert legacy == native
    assert legacy.columns[0].name == 'customer_country_name'


def test_multi_hop_tokens_in_literals_are_not_resolved(model):
    query = PostgresCompiler(model).select(
        'invoice', "'$fake @customer.@country.name' AS literal, $id",
        where='$id=:id /* @missing.@missing.field */', params={'id': 1})
    assert 'LEFT JOIN' not in query.sql
    assert "'$fake @customer.@country.name'" in query.sql


def test_wildcard_select_expands_aliases_but_dml_defaults_do_not(model):
    compiler = PostgresCompiler(model)
    assert 'country_name' in [c.name for c in compiler.select('invoice').columns]
    results = [compiler.insert('invoice', {'id': 1}),
               compiler.update('invoice', {'customer_id': 2}, '$id=:id', {'id': 1}),
               compiler.delete('invoice', '$id=:id', {'id': 1})]
    for query in results:
        assert [column.name for column in query.columns] == ['id', 'customer_id']
        assert 'JOIN' not in query.sql
    assert compiler.insert('invoice', {'id': 1}, returning='$local_id').columns[0].name == 'local_id'


@pytest.mark.parametrize('method', ['insert', 'update'])
def test_alias_assignments_cannot_write_physical_lookalike(model, method):
    compiler = PostgresCompiler(model)
    args = ({'local_id': 1},) if method == 'insert' else ({'local_id': 1}, 'TRUE')
    with pytest.raises(ValueError, match='Cannot write alias column'):
        getattr(compiler, method)('invoice', *args)


@pytest.mark.parametrize('method', ['insert', 'update', 'delete'])
def test_explicit_relational_alias_returning_rejected(model, method):
    compiler = PostgresCompiler(model)
    args = ({'id': 1},) if method == 'insert' else ({'id': 1}, 'TRUE') if method == 'update' else ('TRUE',)
    with pytest.raises(UnsupportedFeatureError, match='Relation paths'):
        getattr(compiler, method)('invoice', *args, returning='$country_name')


def test_mixed_alias_formula_cycle_reports_error():
    table = Table('cycle', columns={'a': Column('a', relation_path='b'),
                                    'b': Column('b', formula='$a + 1')})
    with pytest.raises(ValueError, match='Cyclic formula/alias'):
        PostgresCompiler(ResolvedModel({table.key: table})).select('cycle', '$a')


def test_local_alias_chain_and_quoted_target():
    table = Table('local', columns={'a name': Column('a name', 'L'),
                                    'a': Column('a', relation_path='a name'),
                                    'b': Column('b', relation_path='$a')})
    query = PostgresCompiler(ResolvedModel({table.key: table})).select('local', '$b')
    assert '"t0"."a name" AS "b"' in query.sql
    assert query.columns[0].dtype == 'L'


def test_alias_key_not_allowed_in_join(model):
    invoice = model.table('invoice')
    invoice = replace(invoice, relations={'customer': Relation('customer', 'app.customer', ('local_id',), ('id',))})
    model = replace(model, tables={**model.tables, invoice.key: invoice})
    with pytest.raises(ValueError, match='Virtual join keys'):
        PostgresCompiler(model).select('invoice', '@customer.code')


@pytest.mark.parametrize('kind', ['partition', 'draft', 'deleted'])
def test_alias_cannot_stand_in_for_physical_policy_field(model, kind):
    from genro_sql.contracts import PartitionScope, RowPolicies
    policy = (RowPolicies(partitions=(PartitionScope('local_id', 'current'),)) if kind == 'partition'
              else RowPolicies(draft_field='local_id') if kind == 'draft'
              else RowPolicies(logical_deletion_field='local_id'))
    invoice = replace(model.table('invoice'), policies=policy)
    model = replace(model, tables={**model.tables, invoice.key: invoice})
    with pytest.raises(ValueError, match='physical column'):
        PostgresCompiler(model)


def test_alias_cycle_has_explicit_diagnostic():
    table = Table('cycle', columns={'a': Column('a', relation_path='b'),
                                    'b': Column('b', relation_path='a')})
    with pytest.raises(ValueError, match='Cyclic alias'):
        PostgresCompiler(ResolvedModel({table.key: table}))


def test_mark_allows_alias_value_that_resolves_to_physical_column(model):
    from genro_sql.contracts import RowPolicies
    invoice = model.table('invoice')
    invoice = replace(invoice, columns={**invoice.columns, 'deleted': Column('deleted', 'DH')},
                      policies=RowPolicies(logical_deletion_field='deleted'))
    model = replace(model, tables={**model.tables, invoice.key: invoice})
    query = PostgresCompiler(model).select('invoice', '$country_name', exclude_logical_deleted='mark')
    assert [c.name for c in query.columns] == ['country_name', '_isdeleted']
