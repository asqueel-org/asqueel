"""Seed with the existing fixture; read through the hierarchy's own connection."""
import pytest

from asqueel import AsqueelDb, SqlDatabaseConfig
from asqueel.configuration import connection_settings
from tests.query_completion_support import Shop, shop as execution_shop  # noqa: F401


@pytest.fixture
def shop(execution_shop):  # noqa: F811
    execution = execution_shop
    config = SqlDatabaseConfig()
    implementation, conninfo, connect_kwargs = connection_settings(execution.db.config)
    root = config.source.db('tree_shop', implementation=implementation, conninfo=conninfo,
                            connect_kwargs=connect_kwargs)
    physical = execution.db.model.table('sales.invoice')
    package = root.packages().package('sales', sqlschema=physical.sqlschema, sqlprefix=False)
    customer = package.table('customer', pkey='id')
    customer.column('id', dtype='L')
    customer.column('name', dtype='T', notnull=True)
    invoice = package.table('invoice', pkey='id', logicalDeletionField='__del_ts')
    invoice.column('id', dtype='L')
    invoice.column('customer_id', dtype='L').relation('sales.customer.id')
    invoice.column('total', dtype='N', size='12,2', notnull=True)
    invoice.column('note', dtype='T')
    invoice.column('__del_ts', dtype='DH')
    invoice.formulaColumn('double_total', dtype='N', sql_formula='$total * 2')
    invoice.aliasColumn('client_name', relation_path='@customer_id.name')
    tree = AsqueelDb(config)
    try:
        tree.currentEnv.update(dict(execution.db.currentEnv))
        yield Shop(execution.backend, tree, execution.invoice_sql)
    finally:
        tree.closeConnection()
