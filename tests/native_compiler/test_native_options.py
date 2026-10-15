"""Native options feed SELECT through the existing policy/binding machinery."""
import pytest
from genro_bag.resolvers import EnvResolver

from asqueel import SqlDatabaseConfig, build_database
from asqueel.drivers.psycopg import PsycopgDriver
from asqueel.drivers.sqlite import SqliteDriver


def source(backend='postgresql', *, value='NSW', required=False, enabled=True):
    config = SqlDatabaseConfig()
    pkg = config.source.db('options', implementation=backend).packages().package('sales')
    customer = pkg.table('customer')
    customer.options().sys_fields(draft=True)
    customer.column('state')
    customer.options().partition('state', field='state', value=value,
                                 required=required, enabled=enabled)
    invoice = pkg.table('invoice')
    invoice.options().sys_fields()
    invoice.column('customer_id').relation('sales.customer.id')
    invoice.aliasColumn('state', '@customer_id.state')
    invoice.options().partition('state', field='state', value=value,
                                required=required, enabled=enabled)
    invoice.formulaColumn('all_customers', select=dict(table='sales.customer',
        columns='COUNT(*)', where='TRUE'), dtype='L')
    invoice.formulaColumn('visible_customers', select=dict(table='sales.customer',
        columns='COUNT(*)', where='TRUE', excludeDraft=True,
        excludeLogicalDeleted=True, ignorePartition=False), dtype='L')
    return config


@pytest.fixture(params=['postgresql', 'sqlite'])
def backend(request, monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail('Compiling native options attempted database I/O')
    for driver in (PsycopgDriver, SqliteDriver):
        monkeypatch.setattr(driver, 'connect', forbidden)
        monkeypatch.setattr(driver, 'execute', forbidden)
    return request.param


def test_generated_markers_and_scalar_partition(backend):
    db = build_database(source(backend))
    table = db.table('sales.customer')
    query = table.query('$id', where='$state=:state OR $state IS NULL', state='VIC').compiled
    assert '"__is_draft" IS NOT TRUE' in query.sql
    assert '"__del_ts" IS NULL' in query.sql
    assert set(query.params.values()) == {'NSW', 'VIC'}
    assert ') AND (' in query.sql
    included = table.query('$id', excludeDraft=False, excludeLogicalDeleted=False,
                           ignorePartition=True).compiled
    assert ' WHERE ' not in included.sql
    assert not included.params


def test_partition_alias_reuses_join_without_filtering_joined_table(backend):
    db = build_database(source(backend))
    query = db.table('sales.invoice').query('$id,$state', order_by='$state').compiled
    assert query.sql.count('LEFT JOIN') == 1
    assert '"__is_draft" IS NOT TRUE' not in query.sql
    assert query.sql.count('"__del_ts" IS NULL') == 1
    assert list(query.params.values()) == ['NSW']


def test_child_defaults_and_overrides_keep_partition_bindings_isolated(backend):
    db = build_database(source(backend))
    table = db.table('sales.invoice')
    default = table.query('$all_customers').compiled
    assert '"__is_draft" IS NOT TRUE' not in default.sql
    assert list(default.params.values()) == ['NSW']  # root only
    query = table.query('$visible_customers').compiled
    assert '"__is_draft" IS NOT TRUE' in query.sql
    assert query.sql.count('"__del_ts" IS NULL') == 2
    assert list(query.params.values()) == ['NSW', 'NSW']
    assert len(query.params) == 2
    assert table.query('$visible_customers').compiled == query


@pytest.mark.parametrize('value', [0, False, '', 'NSW'])
def test_present_scalar_is_bound_even_when_falsy(backend, value):
    query = build_database(source(backend, value=value)).table('sales.customer').query('$id').compiled
    assert list(query.params.values()) == [value]


def test_optional_missing_and_disabled_partitions_do_not_filter(backend):
    for config in (source(backend, value=None), source(backend, required=True, enabled=False)):
        query = build_database(config).table('sales.customer').query('$id').compiled
        assert not query.params


def test_required_missing_is_explicit_and_can_be_bypassed(backend):
    table = build_database(source(backend, value=None, required=True)).table('sales.customer')
    with pytest.raises(ValueError, match='missing required partition'):
        table.query('$id').compiled
    assert not table.query('$id', ignorePartition=True).compiled.params


@pytest.mark.parametrize('value', [['NSW', 'VIC'], {'current': 'NSW'}])
def test_collection_partition_has_no_implicit_allowed_values_semantics(backend, value):
    table = build_database(source(backend, value=value)).table('sales.customer')
    with pytest.raises(ValueError, match='Partition values must be scalars'):
        table.query('$id').compiled


def test_existing_resolver_is_evaluated_by_render_not_compiler(backend, monkeypatch):
    monkeypatch.setenv('ASQUEEL_TEST_STATE', 'NSW')
    config = source(backend, value=EnvResolver('ASQUEEL_TEST_STATE'))
    db = build_database(config)
    monkeypatch.setenv('ASQUEEL_TEST_STATE', 'VIC')
    assert list(db.table('sales.customer').query('$id').compiled.params.values()) == ['NSW']
    assert list(build_database(config).table('sales.customer').query('$id').compiled.params.values()) == ['VIC']


def test_names_alone_do_not_create_filters(backend):
    config = SqlDatabaseConfig()
    table = config.source.db('plain', implementation=backend).packages().package('sales').table('plain')
    table.column('id')
    table.column('__is_draft', dtype='B')
    table.column('__del_ts', dtype='DHZ')
    assert ' WHERE ' not in build_database(config).table('sales.plain').query('$id').compiled.sql


def test_disabled_sys_fields_does_not_activate_read_markers(backend):
    config = source(backend, value=None)
    table = config.source['db'].packages().package('sales').table('customer', pkey='id')
    table.options().sys_fields(enabled=False)
    table.column('id')
    model = build_database(config).model.table('sales.customer')
    assert model.policies.draft_field is None
    assert model.policies.logical_deletion_field is None


def test_partition_value_never_becomes_sql_text(backend):
    value = "NSW'); DELETE FROM customer; --"
    table = build_database(source(backend, value=value)).table('sales.customer')
    query = table.query('$id').compiled
    assert value not in query.sql
    assert list(query.params.values()) == [value]
