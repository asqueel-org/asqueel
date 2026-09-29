"""Correlated formulas preserve scope, bind values, and visibility policies."""
from dataclasses import replace

import pytest

from genro_sql.compiler import PostgresCompiler
from genro_sql.contracts import Column, PartitionScope, Relation, ResolvedModel, RowPolicies
from genro_sql.contracts import Table, UnsupportedFeatureError
from genro_sql.environment import SqlEnvironment


def spec(**options):
    return {'table': 'app.item', 'where': '$owner_id=#THIS.id', 'columns': 'SUM($amount)', **options}


@pytest.fixture
def model():
    owner = Table('owner', schema='app', pkey=('id',), columns={
        'id': Column('id', 'L'), 'threshold': Column('threshold', 'N'),
        'total': Column('total', 'N', select=spec(), identity='stable-total', ui={'label': 'Total'}),
        'present': Column('present', 'B', exists=spec(columns='1')),
        'named': Column('named', 'N', formula='COALESCE(#low,0)+COALESCE(#high,0)',
                        subqueries={'low': spec(where='$owner_id=#THIS.id AND $amount>:threshold',
                                                params={'threshold': 1}),
                                    'high': spec(where='$owner_id=#THIS.id AND $amount>:threshold',
                                                 params={'threshold': 5})}),
    })
    item = Table('item', schema='app', pkey=('id',), columns={
        'id': Column('id', 'L'), 'owner_id': Column('owner_id', 'L'), 'amount': Column('amount', 'N')})
    wrapper = Table('wrapper', schema='app', columns={'id': Column('id', 'L'),
                    'owner_id': Column('owner_id', 'L')},
                    relations={'owner': Relation('owner', owner.key, ('owner_id',), ('id',))})
    return ResolvedModel({table.key: table for table in (owner, item, wrapper)})


def change_column(model, name, column, table='owner'):
    owner = model.table(table)
    owner = replace(owner, columns={**owner.columns, name: column})
    return replace(model, tables={**model.tables, owner.key: owner})


def test_scalar_and_exists_have_no_implicit_limit_and_preserve_metadata(model):
    query = PostgresCompiler(model).select('owner', '$total, $present')
    assert 'SUM("s1_t0"."amount") AS "__value_0"' in query.sql
    assert '"s1_t0"."owner_id"="t0"."id"' in query.sql
    assert 'EXISTS (SELECT 1 AS "__value_0"' in query.sql
    assert 'LIMIT' not in query.sql
    assert query.columns[0].source == 'stable-total'
    assert query.columns[0].dtype == 'N'
    assert query.columns[0].ui == {'label': 'Total'}


def test_named_subqueries_and_outer_bindings_do_not_collide(model):
    query = PostgresCompiler(model).select('owner', '$named',
                where='$threshold=:threshold AND $id=:s1_threshold',
                params={'threshold': 10, 's1_threshold': 9})
    assert len(query.params) == 4
    assert sorted(query.params.values()) == [1, 5, 9, 10]
    assert query.params['threshold'] == 10
    assert query.params['s1_threshold'] == 9
    assert query.params['_s1_threshold'] == 1
    assert query.params['s2_threshold'] == 5


def test_reached_formula_uses_owner_alias_in_outer_reference(model):
    query = PostgresCompiler(model).select('wrapper', '@owner.total')
    assert '"s1_t0"."owner_id"="t1"."id"' in query.sql
    assert query.sql.count('LEFT JOIN') == 1


def test_this_in_raw_sql_formula_and_nested_formula_is_owning_row(model):
    model = change_column(model, 'raw', Column('raw', formula='COALESCE(#THIS.threshold,0)'))
    query = PostgresCompiler(model).select('wrapper', '@owner.raw')
    assert 'COALESCE("t1"."threshold",0)' in query.sql
    with pytest.raises(UnsupportedFeatureError, match='#THIS requires'):
        PostgresCompiler(model).select('owner', '#THIS.id AS bad')


def test_nested_subqueries_allocate_distinct_scopes(model):
    model = change_column(model, 'nested', Column('nested', select={
        'table': 'app.owner', 'where': '$id=#THIS.owner_id', 'columns': '$threshold'}), table='item')
    model = change_column(model, 'nested_total', Column('nested_total', select=spec(columns='SUM($nested)')))
    query = PostgresCompiler(model).select('owner', '$nested_total')
    assert '"s2_t0"."id"="s1_t0"."owner_id"' in query.sql
    assert '"s1_t0"."owner_id"="t0"."id"' in query.sql


def test_subquery_cycles_share_recursion_guard_across_contexts(model):
    model = change_column(model, 'total', Column('total', select={
        'table': 'app.owner', 'columns': '$total', 'where': '$id=#THIS.id'}))
    with pytest.raises(ValueError, match='Cyclic formula/alias'):
        PostgresCompiler(model).select('owner', '$total')


def test_macros_and_this_in_literals_comments_stay_literal(model):
    model = change_column(model, 'literal', Column('literal', formula="concat('#total', $$#THIS.id$$) /* #total */"))
    query = PostgresCompiler(model).select('owner', '$literal')
    assert "concat('#total', $$#THIS.id$$) /* #total */" in query.sql
    assert 'app"."item' not in query.sql


def test_child_environment_dependencies_are_bound_to_root_snapshot(model):
    model = change_column(model, 'total', Column('total', select=spec(
        where='$owner_id=#THIS.id AND $amount>:env_threshold')))
    env = SqlEnvironment()
    with env.temp_env(threshold=7):
        query = PostgresCompiler(model, environment=env).select('owner', '$total')
    assert list(query.params.values()) == [7]
    assert query.environment.keys == ('threshold',)
    assert query.environment.values == {'threshold': 7}


def test_child_policy_defaults_are_partition_strict_but_include_draft_deleted(model):
    item = model.table('item')
    item = replace(item, columns={**item.columns, 'draft': Column('draft', 'B'),
                                   'deleted': Column('deleted', 'DH')},
                   policies=RowPolicies(partitions=(PartitionScope('owner_id', 'owner'),),
                                        draft_field='draft', logical_deletion_field='deleted'))
    model = replace(model, tables={**model.tables, item.key: item})
    env = SqlEnvironment()
    compiler = PostgresCompiler(model, environment=env)
    with pytest.raises(ValueError, match='Missing partition context'):
        compiler.select('owner', '$total')
    with env.temp_env(owner=0):
        query = compiler.select('owner', '$total')
    assert list(query.params.values()) == [0]
    assert 'IS NOT TRUE' not in query.sql and 'IS NULL' not in query.sql
    assert query.environment.keys == ('owner',)
    model = change_column(model, 'total', Column('total', select=spec(ignorePartition=True,
                              excludeDraft=True, excludeLogicalDeleted=True)))
    query = PostgresCompiler(model).select('owner', '$total')
    assert '"s1_t0"."draft" IS NOT TRUE' in query.sql
    assert '"s1_t0"."deleted" IS NULL' in query.sql


@pytest.mark.parametrize('options', [dict(group_by='$id'), dict(subtable='restricted'),
    dict(addPkeyColumn=True), dict(ignoreTableOrderBy=False), dict(ignore_partition=True, ignorePartition=True),
    dict(cast='numeric); DELETE FROM x;--'), dict(params=1), dict(params={'x': 1}, sqlparams={'x': 2})])
def test_unsupported_or_ambiguous_child_options_rejected(model, options):
    model = change_column(model, 'total', Column('total', select=spec(**options)))
    with pytest.raises(ValueError):
        PostgresCompiler(model).select('owner', '$total')


def test_scalar_subquery_requires_one_column(model):
    model = change_column(model, 'total', Column('total', select=spec(columns='$id,$amount')))
    with pytest.raises(ValueError, match='exactly one result column'):
        PostgresCompiler(model).select('owner', '$total')


def test_subquery_sql_percent_is_escaped_once_after_child_render(model):
    model = change_column(model, 'literal', Column('literal', select=spec(columns="'50%'", cast='text')))
    query = PostgresCompiler(model).select('owner', '$literal')
    assert "'50%%'" in query.sql and '%%%%' not in query.sql
    assert 'CAST((SELECT' in query.sql


def test_dml_default_excludes_subqueries_and_explicit_request_rejected(model):
    compiler = PostgresCompiler(model)
    query = compiler.insert('owner', {'id': 1})
    assert [column.name for column in query.columns] == ['id', 'threshold']
    for column in ('$total', '$present', '$named'):
        with pytest.raises(UnsupportedFeatureError, match='Subquery columns'):
            compiler.insert('owner', {'id': 1}, returning=column)


def test_original_input_consumption_tracks_child_inheritance_not_local_overrides(model):
    model = change_column(model, 'inherited', Column('inherited', select=spec(
        where='$owner_id=#THIS.id AND $amount>:threshold')))
    compiler = PostgresCompiler(model)
    inherited = compiler.select('owner', '$inherited', params={'threshold': 4})
    assert inherited.input_parameters == ('threshold',)
    overridden = compiler.select('owner', '$named', params={'threshold': 4})
    assert overridden.input_parameters == ()
    both = compiler.select('owner', '$named', where='$threshold=:threshold', params={'threshold': 4})
    assert both.input_parameters == ('threshold',)


def test_snapshot_once_even_with_nested_subqueries(model):
    class CountingEnvironment(SqlEnvironment):
        calls = 0

        def snapshot(self):
            self.calls += 1
            return super().snapshot()

    env = CountingEnvironment({'threshold': 1})
    model = change_column(model, 'env_total', Column('env_total', select=spec(
        where='$owner_id=#THIS.id AND $amount>:env_threshold')))
    PostgresCompiler(model, environment=env).select('owner', '$env_total,$named')
    assert env.calls == 1


def test_this_relation_path_allocates_outer_join_not_inner_join(model):
    model = change_column(model, 'foreign_total', Column('foreign_total', select=spec(
        where='$owner_id=#THIS.@owner.id')), table='wrapper')
    query = PostgresCompiler(model).select('wrapper', '$foreign_total')
    assert '"s1_t0"."owner_id"="t1"."id"' in query.sql
    assert ') AS "foreign_total" FROM "app"."wrapper" AS "t0" LEFT JOIN ' in query.sql


def test_driver_formats_only_final_statement(model):
    from genro_sql.compiler import QueryCompiler
    from genro_sql.dialects.postgres import PostgresDialect
    from genro_sql.drivers.psycopg import PsycopgDriver

    class CountingFormatter(PsycopgDriver):
        calls = 0

        def prepare(self, statement):
            self.calls += 1
            return super().prepare(statement)

    driver = CountingFormatter()
    QueryCompiler(model, PostgresDialect(), driver).select('owner', '$named')
    assert driver.calls == 1


def test_exists_cast_rejected_instead_of_rendering_invalid_exists_cast(model):
    model = change_column(model, 'present', Column('present', exists=spec(cast='numeric')))
    with pytest.raises(UnsupportedFeatureError, match='not EXISTS'):
        PostgresCompiler(model).select('owner', '$present')


def test_default_returning_excludes_transitive_virtual_dependencies(model):
    model = change_column(model, 'plus', Column('plus', formula='$total + 1'))
    model = change_column(model, 'local', Column('local', formula='$id + 1'))
    compiler = PostgresCompiler(model)
    results = [compiler.insert('owner', {'id': 1}),
               compiler.update('owner', {'id': 1}, 'TRUE'), compiler.delete('owner', 'TRUE')]
    for result in results:
        assert [column.name for column in result.columns] == ['id', 'threshold']
    assert '("t0"."id" + 1) AS "local"' in compiler.insert('owner', {'id': 1}, returning='$local').sql
    with pytest.raises(UnsupportedFeatureError, match='Subquery columns'):
        compiler.insert('owner', {'id': 1}, returning='$plus')
