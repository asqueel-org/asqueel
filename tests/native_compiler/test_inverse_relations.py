"""Inverse traversal uses the existing join tree and parameter allocator."""
from dataclasses import replace

import pytest

from asqueel import PostgresCompiler, SqlDatabaseConfig, build_database
from asqueel.contracts import Column, Relation, ResolvedModel, Table
from asqueel.drivers.psycopg import PsycopgDriver
from asqueel.drivers.sqlite import SqliteDriver


@pytest.fixture(params=['postgresql', 'sqlite'])
def db(request, monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail('Inverse compilation attempted database I/O')

    for driver in (PsycopgDriver, SqliteDriver):
        monkeypatch.setattr(driver, 'connect', forbidden)
        monkeypatch.setattr(driver, 'execute', forbidden)
    config = SqlDatabaseConfig()
    pkg = config.source.db('inverses', implementation=request.param).packages().package('app')
    owner = pkg.table('owner', pkey='id')
    owner.column('id', dtype='L')
    owner.column('parent_id', dtype='L').relation('app.owner.id', inverse='children')
    owner.formulaColumn('child_count', select=dict(
        table='app.owner', columns='COUNT(*)', where='@children.parent_id=#THIS.id'))
    owner.formulaColumn('filtered_count', select=dict(
        table='app.owner', columns='COUNT(*)',
        where='@children.parent_id=#THIS.id AND @children.id>:minimum', sqlparams={'minimum': 5}))
    owner.aliasColumn('child_alias', '@children.id')
    line = pkg.table('line', pkey='id')
    line.column('id', dtype='L')
    line.column('owner_id', dtype='L').relation('app.owner.id', back_reference='lines')
    line.column('other_id', dtype='L').relation('app.owner.id', inverse='other_lines')
    line.column('amount', dtype='N')
    line.formulaColumn('scaled', '$amount * :factor', var_factor=3)
    with build_database(config) as database:
        yield database


def test_inverse_reuses_the_join_across_clauses_and_aliases(db):
    plan = db.compiler.plan_select('owner', '$id,@children.id AS child,$child_alias',
                                  where='@children.id>:minimum', sqlparams={'minimum': 2},
                                  order_by='@children.id')
    assert len(plan.joins) == 1
    sql = db.compiler.compile_plan(plan).sql
    assert '"t0"."id" = "t1"."parent_id"' in sql
    assert 'LEFT JOIN' in sql
    assert 'DISTINCT' not in sql


def test_inverse_then_forward_and_separate_inverse_paths(db):
    plan = db.compiler.plan_select('owner',
        '@lines.other_id.id AS other,@lines.amount AS amount,@other_lines.amount AS other_amount')
    assert len(plan.joins) == 3
    sql = db.compiler.compile_plan(plan).sql
    assert '"t0"."id" = "t1"."owner_id"' in sql
    assert '"t1"."other_id" = "t2"."id"' in sql
    assert '"t0"."id" = "t3"."other_id"' in sql


def test_correlated_inverse_stays_inside_the_child_select(db):
    plan = db.compiler.plan_select('owner', '$id,$child_count')
    assert len(plan.joins) == 0
    compiled = db.compiler.compile_plan(plan)
    assert compiled.sql.count('LEFT JOIN') == 1
    assert '"s1_t0"."id" = "s1_t1"."parent_id"' in compiled.sql
    assert '"s1_t1"."parent_id"="t0"."id"' in compiled.sql
    assert 'COUNT(*)' in compiled.sql


def test_outer_and_inner_joins_and_formula_locals_have_separate_scopes(db):
    query = db.table('owner').query(
        '@lines.scaled AS amount,@other_lines.scaled AS other,$filtered_count',
        where='@lines.id>:minimum AND $id>:factor', minimum=19, factor=23)
    first = query.compiled
    assert first.sql.count('LEFT JOIN') == 3
    assert sorted(first.params.values()) == [3, 3, 5, 19, 23]
    assert query.compiled.sql == first.sql
    assert dict(query.compiled.params) == dict(first.params)
    assert db.currentEnv == {}


def test_explicit_grouping_and_having_share_the_inverse_join(db):
    plan = db.compiler.plan_select('owner', '$id,COUNT(@lines.id) AS n', group_by='$id',
                                  having='COUNT(@lines.id)>:minimum', sqlparams={'minimum': 1},
                                  order_by='n DESC')
    assert len(plan.joins) == 1
    compiled = db.compiler.compile_plan(plan)
    assert 'GROUP BY' in compiled.sql and 'HAVING' in compiled.sql
    assert dict(compiled.params) == {'minimum': 1}


def test_inverse_on_compound_key_keeps_every_pair():
    owner = Table('owner', columns={name: Column(name) for name in ('tenant', 'id')},
                  pkey=('tenant', 'id'), relations={
                      'lines': Relation('lines', 'public.line', ('tenant', 'id'),
                                        ('tenant_id', 'owner_id'), kind='inverse')})
    line = Table('line', columns={name: Column(name) for name in ('tenant_id', 'owner_id', 'amount')})
    compiler = PostgresCompiler(ResolvedModel({owner.key: owner, line.key: line}))
    sql = compiler.select('owner', '@lines.amount AS amount').sql
    assert '"t0"."tenant" = "t1"."tenant_id" AND "t0"."id" = "t1"."owner_id"' in sql


@pytest.mark.parametrize('failure', ['source_not_unique', 'missing_target_key', 'wrong_arity', 'virtual_relation'])
def test_invalid_inverse_and_virtual_relations_are_still_rejected(failure):
    relation = Relation('children', 'public.child', ('id',), ('parent_id',), kind='inverse')
    owner = Table('owner', columns={'id': Column('id')}, pkey=('id',))
    child = Table('child', columns={'id': Column('id'), 'parent_id': Column('parent_id')})
    if failure == 'source_not_unique':
        owner = replace(owner, pkey=())
        message = 'source must have a unique key'
    elif failure == 'missing_target_key':
        relation = replace(relation, target_columns=('missing',))
        message = 'Unknown join columns'
    elif failure == 'wrong_arity':
        relation = replace(relation, target_columns=('id', 'parent_id'))
        message = 'Invalid join columns'
    else:
        relation = replace(relation, kind='virtual')
        message = 'virtual navigation'
    owner = replace(owner, relations={'children': relation})
    compiler = PostgresCompiler(ResolvedModel({owner.key: owner, child.key: child}))
    with pytest.raises(ValueError, match=message):
        compiler.select('owner', '@children.id AS child')


def test_inverse_does_not_enable_joined_dml(db):
    with pytest.raises(ValueError, match='DML'):
        db.compiler.update('owner', {'parent_id': 1}, '@children.id=:child', sqlparams={'child': 2})
