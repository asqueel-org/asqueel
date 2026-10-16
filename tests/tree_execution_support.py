"""Seed with the existing fixture; read through the hierarchy's own connection."""
import pytest

from asqueel import SqlDatabase, SqlDatabaseConfig
from tests.query_completion_support import Shop, shop as execution_shop  # noqa: F401


@pytest.fixture
def shop(execution_shop):  # noqa: F811
    execution = execution_shop
    config = SqlDatabaseConfig()
    root = config.source.db('tree_shop', implementation=execution.backend)
    physical = execution.db.model.table('sales.invoice')
    package = root.packages().package('sales', sqlschema=physical.sqlschema, sqlprefix=False)
    customer = package.table('customer', pkey='id')
    customer.column('id', dtype='L')
    customer.column('name', dtype='T', notnull=True)
    invoice = package.table('invoice', pkey='id', x_logical_deletion_field='__del_ts')
    invoice.column('id', dtype='L')
    invoice.column('customer_id', dtype='L').relation('sales.customer.id')
    invoice.column('total', dtype='N', size='12,2', notnull=True)
    invoice.column('note', dtype='T')
    invoice.column('__del_ts', dtype='DH')
    invoice.formulaColumn('double_total', dtype='N', sql_formula='$total * 2')
    invoice.aliasColumn('client_name', relation_path='@customer_id.name')
    with SqlDatabase(model=config.render(mode='objects_tree'), config=execution.db.config) as tree:
        tree.currentEnv.update(dict(execution.db.currentEnv))
        yield Shop(execution.backend, tree, execution.invoice_sql)
