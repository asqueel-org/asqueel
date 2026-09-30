from dataclasses import replace
from datetime import datetime, timezone

import pytest

from asqueel.compiler import PostgresCompiler
from asqueel.contracts import (
    Column, EnvironmentMismatchError, PartitionScope, Relation, ResolvedModel,
    RowPolicies, Table, UnsupportedFeatureError,
)
from asqueel.environment import SqlEnvironment
from asqueel.query_plan import Identifier, Parameter


def model(*, partitions=(), draft='draft', deleted='deleted_at', formulas=False):
    columns = {
        'id': Column('id', 'I'), 'organization': Column('organization', 'I'),
        'region': Column('region'), 'draft': Column('draft', 'B'),
        'deleted_at': Column('deleted_at', 'DHZ', identity='tombstone'),
    }
    if formulas:
        columns['doubled'] = Column('doubled', 'I', formula='$id * 2')
    table = Table('item', columns=columns, pkey=('id',),
                  policies=RowPolicies(tuple(partitions), draft, deleted))
    return ResolvedModel({table.key: table})


SCOPE = PartitionScope('organization', 'organization', 'allowed_organizations')


def test_default_filters_and_include_options():
    compiler = PostgresCompiler(model())
    query = compiler.select('item', '$id', where='$id=1 OR $id=2')
    assert 'WHERE ("t0"."id"=1 OR "t0"."id"=2) AND ' in query.sql
    assert '("t0"."draft" IS NOT TRUE)' in query.sql
    assert '("t0"."deleted_at" IS NULL)' in query.sql
    included = compiler.select('item', exclude_draft=False, exclude_logical_deleted=False)
    assert ' WHERE ' not in included.sql


def test_mark_preserves_actual_column_metadata_and_alias_collision():
    compiler = PostgresCompiler(model())
    marked = compiler.select('item', '$id', exclude_logical_deleted='mark')
    assert '"t0"."deleted_at" AS "_isdeleted"' in marked.sql
    assert marked.columns[-1].dtype == 'DHZ'
    assert marked.columns[-1].source == 'tombstone'
    assert '"deleted_at" IS NULL' not in marked.sql
    with pytest.raises(ValueError, match='reserved'):
        compiler.select('item', '$id AS _isdeleted', exclude_logical_deleted='mark')


@pytest.mark.parametrize('columns', ['COUNT(*) AS n', '$id + 1 AS x', '$doubled'])
def test_mark_rejects_opaque_aggregate_and_formula(columns):
    with pytest.raises(UnsupportedFeatureError, match='physical column projections'):
        PostgresCompiler(model(formulas=True)).select('item', columns, exclude_logical_deleted='mark')


@pytest.mark.parametrize('current', [0, False, '', None])
def test_current_falsy_is_present_and_missing_key_is_captured(current):
    env = SqlEnvironment({'organization': current})
    compiler = PostgresCompiler(model(partitions=[SCOPE]), environment=env)
    plan = compiler.plan_select('item', '$id')
    assert plan.environment.keys == ('allowed_organizations', 'organization')
    assert dict(plan.environment.values) == {'organization': current}
    query = compiler.compile_plan(plan)
    if current is None:
        assert '"organization" IS NULL' in query.sql
    else:
        assert current in query.params.values()
    with pytest.raises(EnvironmentMismatchError):
        plan.environment.validate({'organization': current, 'allowed_organizations': [current]})


def test_missing_partition_context_requires_explicit_bypass():
    compiler = PostgresCompiler(model(partitions=[SCOPE]))
    with pytest.raises(ValueError, match='Missing partition context'):
        compiler.select('item')
    assert compiler.select('item', ignore_partition=True).environment is None


def test_empty_allowed_intersection_and_null_membership():
    env = SqlEnvironment({'organization': 0, 'allowed_organizations': []})
    compiler = PostgresCompiler(model(partitions=[SCOPE]), environment=env)
    assert 'AND (FALSE)' in compiler.select('item').sql
    only_allowed = SqlEnvironment({'allowed_organizations': [2, 3]})
    compiler = PostgresCompiler(model(partitions=[SCOPE]), environment=only_allowed)
    query = compiler.select('item')
    assert ' IN (' in query.sql and ' OR "t0"."organization" IS NULL' in query.sql
    assert list(query.params.values()) == [2, 3]
    strict = replace(SCOPE, include_null=False)
    compiler = PostgresCompiler(model(partitions=[strict]), environment=only_allowed)
    assert '"organization" IS NULL' not in compiler.select('item').sql
    with only_allowed.temp_env(allowed_organizations=[None]):
        query = compiler.select('item')
        assert '"organization" IS NULL' in query.sql and ' IN (' not in query.sql


@pytest.mark.parametrize('allowed', ['abc', None, {'x': 1}, [[1]], [dict(x=1)]])
def test_allowed_requires_collection_of_scalars(allowed):
    env = SqlEnvironment({'allowed_organizations': allowed})
    with pytest.raises(ValueError):
        PostgresCompiler(model(partitions=[SCOPE]), environment=env).select('item')


def test_multiple_partitions_are_and_combined_and_parameter_names_do_not_collide():
    partitions = [SCOPE, PartitionScope('region', 'region')]
    env = SqlEnvironment({'organization': 0, 'region': 'north'})
    compiler = PostgresCompiler(model(partitions=partitions), environment=env)
    query = compiler.select('item', where='$id=:__policy_0', params={'__policy_0': 99})
    assert query.params['__policy_0'] == 99
    assert query.params['___policy_0'] == 0
    assert query.params['__policy_1'] == 'north'
    assert ') AND ("t0"."region" = ' in query.sql


def test_env_fallback_explicit_override_and_snapshot_once():
    class CountingEnvironment(SqlEnvironment):
        def __init__(self):
            super().__init__({'organization': 0, 'needle': 4})
            self.calls = 0

        def snapshot(self):
            self.calls += 1
            return super().snapshot()

    env = CountingEnvironment()
    compiler = PostgresCompiler(model(partitions=[SCOPE]), environment=env)
    plan = compiler.plan_select('item', where='$id=:env_needle')
    assert env.calls == 1
    assert plan.params['env_needle'] == 4
    assert 'needle' in plan.environment.keys
    other = compiler.plan_select('item', where='$id=:env_needle', params={'env_needle': 9})
    assert env.calls == 2
    assert other.params['env_needle'] == 9
    assert 'needle' not in other.environment.keys
    with pytest.raises(ValueError, match='Missing query parameter'):
        compiler.select('item', where='$id=:env_missing')


def test_dml_partition_guards_autofill_and_no_draft_or_deleted_filters():
    env = SqlEnvironment({'organization': 0, 'allowed_organizations': [0]})
    compiler = PostgresCompiler(model(partitions=[SCOPE]), environment=env)
    values = {'id': 1}
    plan = compiler.plan_insert('item', values)
    assert values == {'id': 1}
    assert [a.column for a in plan.assignments] == ['id', 'organization']
    assert [plan.params[a.value.parts[0].name] for a in plan.assignments] == [1, 0]
    for method in (lambda: compiler.insert('item', {'id': 1, 'organization': 2}),
                   lambda: compiler.update('item', {'organization': 2}, 'TRUE')):
        with pytest.raises(ValueError, match='outside'):
            method()
    for query in (compiler.update('item', {'draft': False}, '$id=:id', {'id': 1}),
                  compiler.delete('item', '$id=:id', {'id': 1})):
        assert '"organization" = ' in query.sql
        assert ' IS NOT TRUE' not in query.sql and '"deleted_at" IS NULL' not in query.sql
    assert compiler.insert('item', {'organization': 2}, ignore_partition=True).environment is None


def test_allowed_only_insert_requires_value_and_empty_allowed_refuses_insert():
    env = SqlEnvironment({'allowed_organizations': [1]})
    compiler = PostgresCompiler(model(partitions=[SCOPE]), environment=env)
    with pytest.raises(ValueError, match='requires partition value'):
        compiler.insert('item', {'id': 1})
    compiler.insert('item', {'id': 1, 'organization': 1})
    with env.temp_env(allowed_organizations=[]):
        with pytest.raises(ValueError, match='outside'):
            compiler.insert('item', {'organization': None})


def test_soft_delete_and_restore_are_explicit_guarded_updates_with_quoted_marker():
    env = SqlEnvironment({'organization': 0})
    compiler = PostgresCompiler(model(partitions=[SCOPE], deleted='$"deleted_at"'), environment=env)
    timestamp = datetime(2026, 1, 1, tzinfo=timezone.utc)
    deleted = compiler.soft_delete('item', timestamp, '$id=:id', {'id': 1})
    restored = compiler.restore('item', '$id=:id', {'id': 1})
    assert deleted.sql.startswith('UPDATE ') and timestamp in deleted.params.values()
    assert restored.sql.startswith('UPDATE ') and None in restored.params.values()
    assert compiler.delete('item', 'TRUE').sql.startswith('DELETE ')
    with pytest.raises(ValueError, match='non-None'):
        compiler.soft_delete('item', None, 'TRUE')


def test_relational_partition_reads_work_but_writes_are_explicitly_unsupported():
    target = Table('organization', columns={'id': Column('id', 'I'), 'region': Column('region')},
                   pkey=('id',), policies=RowPolicies(draft_field=None))
    source = next(iter(model(draft=None, deleted=None).tables.values()))
    source = replace(source, relations={'org': Relation('org', target.key, ('organization',), ('id',))},
                     policies=RowPolicies((PartitionScope('@org.region', 'region'),)))
    compiler = PostgresCompiler(ResolvedModel({source.key: source, target.key: target}),
                                environment=SqlEnvironment({'region': 'north'}))
    plan = compiler.plan_select('item', '$id')
    assert plan.joins and Identifier('region') in plan.where.parts
    assert any(isinstance(p, Parameter) for p in plan.where.parts)
    for action in (lambda: compiler.insert('item', {'id': 1}),
                   lambda: compiler.update('item', {'id': 1}, 'TRUE'),
                   lambda: compiler.delete('item', 'TRUE')):
        with pytest.raises(UnsupportedFeatureError, match='Relational partition writes'):
            action()
    assert compiler.delete('item', 'TRUE', ignore_partition=True)
