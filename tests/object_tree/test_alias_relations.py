"""Alias relation inheritance is finalized on the model, before compilation."""
from uuid import uuid4

import pytest

from asqueel import AsqueelDb, SqlDatabaseConfig, SqlMigrationRenderer
from asqueel.compiler import PostgresCompiler
from tests.native_support import postgres_dsn


def source(*, implementation='postgresql', schema='public', conninfo=None, explicit=False):
    config = SqlDatabaseConfig()
    root = config.source.db('aliases', implementation=implementation, **({'conninfo': conninfo} if conninfo else {}))
    package = root.packages().package('app', sqlschema=schema, sqlprefix=False)
    # Declare aliases before their targets to exercise finalize, not source order.
    row = package.table('invoice_row', pkey='id')
    row.column('id', 'L')
    row.column('invoice_id', 'L').relation('app.invoice.id')
    row.aliasColumn('customer_copy', '$customer_id')
    alias = row.aliasColumn('customer_id', '@invoice_id.customer_id')
    if explicit:
        alias.relation('app.other_customer.id')
    row.aliasColumn('customer_label', '@invoice_id.@customer_id.name')
    invoice = package.table('invoice', pkey='id')
    invoice.column('id', 'L')
    invoice.column('customer_id', 'L').relation('app.customer.id', inverse='invoices', on_delete='cascade')
    for name in ('customer', 'other_customer'):
        table = package.table(name, pkey='id')
        table.column('id', 'L')
        table.column('name', 'T')
    return config, row


def test_inherited_relation_is_weak_and_does_not_mutate_source_or_target():
    config, _ = source()
    before = config.source.to_xml()
    model = config.render(mode='objects_tree')
    table = model.table('app.invoice_row')
    for name in ('customer_id', 'customer_copy'):
        attrs = table.relations.get_node('@' + name).attr['joiner']
        assert attrs['mode'] == 'O' and attrs['virtual']
        assert table.relations.get_node('@' + name).attr['dtype'] == 'L'
        assert attrs['one_relation'] == 'app.customer.id'
        assert attrs['many_relation'] == 'app.invoice_row.' + name
        assert not attrs['foreignkey']
        # An alias does not duplicate the source column's inverse/action contract.
        assert attrs['private_relation'] and attrs.get('onDelete') is None
    assert table.relations.get_node('@customer_label') is None
    original = model.table('app.invoice').relations.get_node('@customer_id').attr['joiner']
    assert original['relation_name'] == 'invoices' and original['onDelete'] == 'cascade'
    assert original['foreignkey']
    assert config.source.to_xml() == before
    assert config.render(mode='objects_tree').relations.to_xml() == model.relations.to_xml()
    migration = SqlMigrationRenderer(config).render()['root']['schemas']['public']['tables']
    assert len(migration['invoice_row']['relations']) == 1  # only invoice_id
    assert 'customer_id' not in migration['invoice_row']['columns']


def test_explicit_relation_wins_and_is_inherited_by_the_next_alias():
    config, _ = source(explicit=True)
    model = config.render(mode='objects_tree')
    for name in ('customer_id', 'customer_copy'):
        attrs = model.table('app.invoice_row').relations.get_node('@' + name).attr['joiner']
        assert attrs['one_relation'] == 'app.other_customer.id'
        assert not attrs['foreignkey']
    sql = PostgresCompiler(model).select('app.invoice_row', '@customer_copy.name').sql
    assert '"other_customer"' in sql


def test_alias_cycle_does_not_recurse_during_inheritance():
    config, row = source()
    row.aliasColumn('cycle_a', '$cycle_b')
    row.aliasColumn('cycle_b', '$cycle_a')
    model = config.render(mode='objects_tree')
    assert model.table('app.invoice_row').relations.get_node('@cycle_a') is None
    with pytest.raises(ValueError, match='Cyclic'):
        PostgresCompiler(model).select('app.invoice_row', '$cycle_a')


@pytest.fixture(params=[('sqlite', False), ('sqlite', True),
                        pytest.param(('postgresql', False), marks=pytest.mark.postgresql),
                        pytest.param(('postgresql', True), marks=pytest.mark.postgresql)])
def database(request):
    backend, explicit = request.param
    schema = 'main' if backend == 'sqlite' else 'alias_rel_' + uuid4().hex
    config, _ = source(implementation=backend, schema=schema,
                       conninfo=':memory:' if backend == 'sqlite' else postgres_dsn(), explicit=explicit)
    db = AsqueelDb(config)
    prefix = f'"{schema}".'
    created = False
    try:
        if backend == 'postgresql':
            db.execute(f'CREATE SCHEMA "{schema}"')
            created = True
        for name, fields in [('customer', 'id integer primary key, name text'),
                             ('other_customer', 'id integer primary key, name text'),
                             ('invoice', 'id integer primary key, customer_id integer'),
                             ('invoice_row', 'id integer primary key, invoice_id integer')]:
            db.execute(f'CREATE TABLE {prefix}{name} ({fields})')
        db.execute(f"INSERT INTO {prefix}customer VALUES (1, 'Ada'), (2, 'Grace')")
        db.execute(f"INSERT INTO {prefix}other_customer VALUES (1, 'Other Ada'), (2, 'Other Grace')")
        db.execute(f'INSERT INTO {prefix}invoice VALUES (10, 1), (11, 2), (12, NULL)')
        db.execute(f'INSERT INTO {prefix}invoice_row VALUES (100, 10), (101, 11), (102, 12), (103, NULL)')
        db.commit()
        yield db, explicit
    finally:
        db.rollback()
        if created:
            db.execute(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE')
            db.commit()
        db.close()


def test_inherited_relation_fetch_and_reuse_on_both_dialects(database):
    database, explicit = database
    ada, grace = ('Other Ada', 'Other Grace') if explicit else ('Ada', 'Grace')
    query = database.table('app.invoice_row').query(
        '$id, @customer_id.name AS name, @customer_id.name AS repeated', order_by='$id')
    compiled = query.compiled
    assert compiled.sql.count('LEFT JOIN') == 2
    assert query.compiled == compiled
    assert compiled.params == {}
    assert [(r['id'], r['name'], r['repeated']) for r in query.fetch()] == [
        (100, ada, ada), (101, grace, grace), (102, None, None), (103, None, None)]
    filtered = database.table('app.invoice_row').query(
        '$id', where='@customer_copy.name=:name', name=grace).fetch()
    assert [r['id'] for r in filtered] == [101]


def test_alias_path_can_traverse_another_inherited_relation():
    config, row = source()
    package = config.source.get_node('db.packages.app')
    customer = package.table('customer')
    customer.column('manager_id', 'L').relation('app.customer.id')
    row.aliasColumn('manager_id', '@customer_id.manager_id')
    model = config.render(mode='objects_tree')
    joiner = model.table('app.invoice_row').relations.get_node('@manager_id').attr['joiner']
    assert joiner['one_relation'] == 'app.customer.id'
    assert not joiner['foreignkey']
    sql = PostgresCompiler(model).select('app.invoice_row', '@manager_id.name').sql
    assert sql.count('LEFT JOIN') == 3


def test_physical_fk_on_alias_is_rejected():
    config, row = source()
    with pytest.raises(ValueError, match='foreign_key'):
        row.aliasColumn('other_id', '@invoice_id.customer_id').relation('app.customer.id', foreign_key=True)
