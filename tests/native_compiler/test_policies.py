from dataclasses import replace
from datetime import datetime, timezone

import pytest

from asqueel.compiler import PostgresCompiler
from asqueel.contracts import (
    Column, PartitionScope, Relation, ResolvedModel,
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
