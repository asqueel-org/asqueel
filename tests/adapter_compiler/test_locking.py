"""Row locking is an explicit plan capability restricted to the root table."""
from dataclasses import replace

import pytest

from asqueel.compiler import PostgresCompiler
from asqueel.contracts import Column, Relation, ResolvedModel, Table, UnsupportedFeatureError


@pytest.fixture
def compiler():
    customer = Table('customer', schema='app', pkey=('id',),
                     columns={'id': Column('id'), 'name': Column('name')})
    invoice = Table('invoice', schema='app', pkey=('id',), columns={
        'id': Column('id'), 'customer_id': Column('customer_id')},
        relations={'customer': Relation('customer', customer.key, ('customer_id',), ('id',))})
    return PostgresCompiler(ResolvedModel({customer.key: customer, invoice.key: invoice}))


@pytest.mark.parametrize('operation', ['insert', 'update', 'delete'])
def test_non_select_lock_is_rejected(compiler, operation):
    plans = {
        'insert': compiler.plan_insert('invoice', {'id': 1}),
        'update': compiler.plan_update('invoice', {'id': 1}, 'TRUE'),
        'delete': compiler.plan_delete('invoice', 'TRUE'),
    }
    with pytest.raises(UnsupportedFeatureError, match='only supported for SELECT'):
        compiler.compile_plan(replace(plans[operation], for_update=True))
