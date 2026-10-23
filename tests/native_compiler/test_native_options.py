"""The legacy partition_<field> table attribute feeds SELECT through the environment."""
import pytest

from asqueel import SqlDatabaseConfig, AsqueelDb
from asqueel.adapters.postgres import SqlDbAdapter as PostgresAdapter
from asqueel.adapters.sqlite import SqlDbAdapter as SqliteAdapter

STATE = {'current_state': 'NSW'}


def source(backend='postgres'):
    config = SqlDatabaseConfig()
    pkg = config.source.db('options', implementation=backend).packages().package('sales')
    customer = pkg.table('customer', partition_state='state')
    customer.options().sys_fields(draft=True)
    customer.column('state')
    invoice = pkg.table('invoice', partition_state='state')
    invoice.options().sys_fields()
    invoice.column('customer_id').relation('sales.customer.id')
    invoice.aliasColumn('state', '@customer_id.state')
    invoice.formulaColumn('all_customers', select=dict(table='sales.customer',
        columns='COUNT(*)', where='TRUE'), dtype='L')
    invoice.formulaColumn('visible_customers', select=dict(table='sales.customer',
        columns='COUNT(*)', where='TRUE', excludeDraft=True,
        excludeLogicalDeleted=True, ignorePartition=False), dtype='L')
    return config


@pytest.fixture(params=['postgres', 'sqlite'])
def backend(request, monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail('Compiling partitions attempted database I/O')
    for driver in (PostgresAdapter, SqliteAdapter):
        monkeypatch.setattr(driver, 'connect', forbidden)
        monkeypatch.setattr(driver, 'execute', forbidden)
    return request.param


def test_partition_alias_reuses_join_without_filtering_joined_table(backend):
    db = AsqueelDb(source(backend), environment=STATE)
    query = db.table('sales.invoice').query('$id,$state', order_by='$state').compiled
    assert query.sql.count('LEFT JOIN') == 1
    assert '"__is_draft" IS NOT TRUE' not in query.sql
    assert query.sql.count('"__del_ts" IS NULL') == 1
    assert list(query.params.values()) == ['NSW']


@pytest.mark.parametrize('value', [0, False, '', None])
def test_falsy_environment_values_do_not_filter(backend, value):
    environment = {'current_state': value, 'allowed_state': value}
    query = AsqueelDb(source(backend), environment=environment).table('sales.customer').query('$id').compiled
    assert not query.params


def test_partition_is_bypassed_explicitly(backend):
    table = AsqueelDb(source(backend), environment=STATE).table('sales.customer')
    assert list(table.query('$id').compiled.params.values()) == ['NSW']
    assert not table.query('$id', ignorePartition=True).compiled.params


def test_names_alone_do_not_create_filters(backend):
    config = SqlDatabaseConfig()
    table = config.source.db('plain', implementation=backend).packages().package('sales').table('plain')
    table.column('id')
    table.column('__is_draft', dtype='B')
    table.column('__del_ts', dtype='DHZ')
    assert ' WHERE ' not in AsqueelDb(config).table('sales.plain').query('$id').compiled.sql


def test_partition_value_never_becomes_sql_text(backend):
    value = "NSW'); DELETE FROM customer; --"
    environment = {'current_state': value}
    table = AsqueelDb(source(backend), environment=environment).table('sales.customer')
    query = table.query('$id').compiled
    assert value not in query.sql
    assert list(query.params.values()) == [value]
