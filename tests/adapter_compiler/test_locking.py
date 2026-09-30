"""Row locking is an explicit plan capability restricted to the root table."""
from dataclasses import replace

import pytest

from asqueel.compiler import PostgresCompiler, QueryCompiler
from asqueel.contracts import Column, Relation, ResolvedModel, Table, UnsupportedFeatureError
from asqueel.dialects.postgres import PostgresDialect
from asqueel.drivers.psycopg import PsycopgDriver
from asqueel.query_plan import TableRef


@pytest.fixture
def compiler():
    customer = Table('customer', schema='app', pkey=('id',),
                     columns={'id': Column('id'), 'name': Column('name')})
    invoice = Table('invoice', schema='app', pkey=('id',), columns={
        'id': Column('id'), 'customer_id': Column('customer_id')},
        relations={'customer': Relation('customer', customer.key, ('customer_id',), ('id',))})
    return PostgresCompiler(ResolvedModel({customer.key: customer, invoice.key: invoice}))


def test_select_defaults_do_not_lock(compiler):
    assert compiler.plan_select('invoice').for_update is False
    assert 'FOR UPDATE' not in compiler.select('invoice').sql


def test_lock_is_structural_and_follows_pagination(compiler):
    plan = compiler.plan_select('invoice', '$id, @customer.name', where='$id=:id',
                                params={'id': 3}, order_by='$id', limit=5, offset=2,
                                for_update=True)
    assert plan.for_update is True
    query = compiler.compile_plan(plan)
    assert ' LEFT JOIN ' in query.sql
    assert query.sql.endswith(' ORDER BY "t0"."id" LIMIT 5 OFFSET 2 FOR UPDATE OF "t0"')
    assert query.sql.count('FOR UPDATE OF') == 1
    assert dict(query.params) == {'id': 3}
    assert compiler.select('invoice', for_update=True).sql.endswith(' FOR UPDATE OF "t0"')


@pytest.mark.parametrize('value', [None, 0, 1, 'true', [], {}])
def test_compiler_rejects_non_boolean_lock_options(compiler, value):
    with pytest.raises(ValueError, match='for_update must be a boolean'):
        compiler.plan_select('invoice', for_update=value)
    with pytest.raises(ValueError, match='for_update must be a boolean'):
        compiler.select('invoice', for_update=value)


@pytest.mark.parametrize('value', [None, 0, 1, 'true'])
def test_renderer_revalidates_manually_constructed_plan(compiler, value):
    with pytest.raises(ValueError, match='for_update must be a boolean'):
        PostgresDialect().render(replace(compiler.plan_select('invoice'), for_update=value))


@pytest.mark.parametrize('operation', ['insert', 'update', 'delete'])
def test_non_select_lock_is_rejected(compiler, operation):
    plans = {
        'insert': compiler.plan_insert('invoice', {'id': 1}),
        'update': compiler.plan_update('invoice', {'id': 1}, 'TRUE'),
        'delete': compiler.plan_delete('invoice', 'TRUE'),
    }
    with pytest.raises(UnsupportedFeatureError, match='only supported for SELECT'):
        compiler.compile_plan(replace(plans[operation], for_update=True))


def test_lock_capability_cannot_be_silently_ignored(compiler):
    dialect = PostgresDialect(capabilities=PostgresDialect.capabilities - {'for_update'})
    limited = QueryCompiler(compiler.model, dialect, PsycopgDriver())
    assert 'FOR UPDATE' not in limited.select('invoice').sql
    with pytest.raises(UnsupportedFeatureError, match='unsupported capability for_update'):
        limited.select('invoice', for_update=True)


def test_manual_root_alias_is_quoted_for_lock_target(compiler):
    plan = compiler.plan_select('invoice', '1 AS one', for_update=True)
    plan = replace(plan, table=TableRef('app', 'invoice', 'root"%'))
    query = compiler.compile_plan(plan)
    assert query.sql.endswith(' FOR UPDATE OF "root""%%"')


def test_trailing_comment_cannot_swallow_lock(compiler):
    query = compiler.select('invoice', where='$id=:id -- user comment',
                            params={'id': 1}, for_update=True)
    assert '-- user comment\n FOR UPDATE OF "t0"' in query.sql
