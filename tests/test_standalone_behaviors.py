"""Standalone behaviors through the current public APIs, on both databases."""
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from threading import Barrier

import pytest

from asqueel.application_table import SqlTable
from tests.option_tables_support import IMPLEMENTATIONS, migrated_db, row


@pytest.fixture(params=IMPLEMENTATIONS)
def implementation(request):
    return request.param


def ranked(package):
    table = package.table('item', name_long='Item')
    table.options().sys_fields()
    table.options().auto_counter(scope=['scope', 'group_id'])
    table.column('scope')
    table.column('group_id', dtype='L')
    table.column('value', dtype='L', default=5)
    table.column('fixed', unmodifiable=True)
    table.column('system', default='internal', readOnly=True)


def hierarchy(package, linked=False, table_class=SqlTable):
    if linked:
        master = package.table('master', name_long='Master')
        master.options().sys_fields()
        master.column('code')
    table = package.table('item', name_long='Item', x_table_class=table_class)
    table.options().sys_fields()
    table.options().hierarchical('code', parent='owner_id', root_id=True,
                                 virtual_roots=True, linked_to='app.master' if linked else None)
    table.options().auto_counter(field='position')
    table.column('code')


def test_counter_scopes_defaults_column_rules_and_rollback(implementation, tmp_path):
    with migrated_db(implementation, tmp_path, ranked) as db:
        table = db.table('app.item')
        first = table.insert({'scope': 'a', 'fixed': 'immutable'})
        second = table.insert({'scope': 'a', 'value': None})
        assert (first['_row_count'], second['_row_count'], first['value'], first['system']) == (1, 2, 5, 'internal')
        assert row(table, second['id'])['value'] is None
        assert table.insert({'scope': 'b'})['_row_count'] == 1
        assert table.insert({'scope': 'a', 'group_id': 1})['_row_count'] == 1
        table.insert({'scope': 'a', '_row_count': 9})
        assert table.insert({'scope': 'a'})['_row_count'] == 10
        db.commit()
        table.update({'id': first['id'], 'value': 8})
        assert row(table, first['id'])['value'] == 8
        db.rollback()
        assert row(table, first['id'])['value'] == 5
        for field in ('fixed', 'system'):
            with pytest.raises(ValueError, match='unmodifiable'):
                table.update({'id': first['id'], field: 'changed'})
            db.rollback()
        with pytest.raises(ValueError, match='read-only'):
            table.insert({'system': 'caller'})
        db.rollback()
        table.sql_update({'id': first['id'], 'fixed': 'raw'})
        assert row(table, first['id'])['fixed'] == 'raw'


def test_custom_hierarchy_moves_inheritance_and_delete(implementation, tmp_path):
    with migrated_db(implementation, tmp_path, hierarchy) as db:
        table = db.table('app.item')
        root = table.insert({'code': 'root', '_virtual_node': True})
        child = table.insert({'code': 'child', 'owner_id': root['id']})
        leaf = table.insert({'code': 'leaf', 'owner_id': child['id']})
        assert leaf['root_id'] == root['id']
        table.update(dict(root, code='new', _virtual_node=False), old_record=root)
        assert row(table, leaf['id'])['hierarchical_code'] == 'new/child/leaf'
        assert row(table, leaf['id'])['_virtual_node'] is False
        destination = table.insert({'code': 'destination'})
        old = row(table, child['id'])
        table.update(dict(old, owner_id=destination['id']), old_record=old)
        assert row(table, leaf['id'])['root_id'] == destination['id']
        db.commit()
        table.delete(destination['id'])
        assert not table._behavior_rows(where='$id=:id', sqlparams={'id': leaf['id']})
        db.rollback()
        assert row(table, leaf['id'])['root_id'] == destination['id']


def test_hierarchy_rejects_invalid_keys_and_parents(implementation, tmp_path):
    with migrated_db(implementation, tmp_path, hierarchy) as db:
        table = db.table('app.item')
        root = table.insert({'code': 'root'})
        child = table.insert({'code': 'child', 'owner_id': root['id']})
        db.commit()
        for parent in (root['id'], child['id']):
            with pytest.raises(Exception, match='cannot be moved under itself'):
                table.update(dict(root, owner_id=parent), old_record=root)
            db.rollback()
        with pytest.raises(ValueError, match='Unknown hierarchical parent'):
            table.insert({'code': 'missing', 'owner_id': 'x' * 22})
        db.rollback()
        with pytest.raises(ValueError, match='unmodifiable'):
            table.update(dict(root, id='n' * 22), old_record=root)
        db.rollback()
        with pytest.raises(ValueError, match='cannot contain'):
            table.insert({'id': 'a/b', 'code': 'invalid'})


def test_hierarchy_refreshes_paths_after_before_hooks(implementation, tmp_path):
    class Normalize(SqlTable):
        def trigger_onInserting(self, record):
            record['code'] = record['code'].upper()

        def trigger_onUpdating(self, record, old_record=None):
            record['code'] = record.get('code', old_record['code']).upper()

    with migrated_db(implementation, tmp_path, lambda p: hierarchy(p, table_class=Normalize)) as db:
        table = db.table('app.item')
        root = table.insert({'code': 'root'})
        leaf = table.insert({'code': 'leaf', 'owner_id': root['id']})
        assert leaf['hierarchical_code'] == 'ROOT/LEAF'
        table.update(dict(root, code='renamed'), old_record=root)
        assert row(table, leaf['id'])['hierarchical_code'] == 'RENAMED/LEAF'


def test_linked_roots_follow_master_and_rollback(implementation, tmp_path):
    with migrated_db(implementation, tmp_path, lambda p: hierarchy(p, linked=True)) as db:
        master = db.table('app.master')
        table = db.table('app.item')
        owner = master.insert({'code': 'master'})
        root = row(table, owner['root_item_id'])
        leaf = table.insert({'code': 'leaf', 'owner_id': root['id']})
        assert leaf['master_id'] == owner['id']
        master.update(dict(owner, code='changed'), old_record=owner)
        assert row(table, leaf['id'])['hierarchical_code'] == 'changed/leaf'
        db.commit()
        master.delete(owner['id'])
        assert table._behavior_rows() == []
        db.rollback()
        assert row(table, leaf['id'])['hierarchical_code'] == 'changed/leaf'


def relative(package):
    master = package.table('master', name_long='Master')
    master.options().sys_fields()
    extension = package.table('master_xtd', pkey='id', name_long='Extension')
    extension.column('id', size='22')
    extension.column('main_id', size='22').relation('app.master.id', deferred=True)
    detail = package.table('item', name_long='Detail')
    detail.options().sys_fields()
    detail.options().relative_index('master_id')
    detail.column('master_id', size='22').relation('app.master.id', deferred=True)


def test_relative_index_survives_deletion_and_rolls_back(implementation, tmp_path):
    with migrated_db(implementation, tmp_path, relative) as db:
        master = db.table('app.master').insert({})
        detail = db.table('app.item')
        first = detail.insert({'master_id': master['id']})
        detail.delete(first)
        second = detail.insert({'master_id': master['id']})
        assert second['_relidx'] == 2
        db.commit()
        assert detail.insert({'master_id': master['id']})['_relidx'] == 3
        db.rollback()
        assert detail.insert({'master_id': master['id']})['_relidx'] == 3


def generated(package, expression='value * 2'):
    table = package.table('item', name_long='Item')
    table.options().sys_fields()
    table.column('value', dtype='L')
    table.column('computed', dtype='L', sql_generatedExpression=expression)


def test_generated_columns_roundtrip_and_full_record_update(implementation, tmp_path):
    with migrated_db(implementation, tmp_path, generated) as db:
        table = db.table('app.item')
        item = table.insert({'value': 3})
        assert item['computed'] == 6
        old = row(table, item['id'])
        table.update(dict(old, value=4), old_record=old)
        assert row(table, item['id'])['computed'] == 8
        db.commit()
        assert db.migration_plan().empty
        for write in (table.insert, table.sql_insert, table.sql_update):
            with pytest.raises(ValueError, match='database-generated'):
                write({'id': item['id'], 'computed': 12})
            db.rollback()


@pytest.mark.parametrize('declare', [ranked, relative])
def test_concurrent_allocations_serialize(implementation, tmp_path, declare):
    with migrated_db(implementation, tmp_path, declare) as db:
        values = {'scope': 'a'} if declare is ranked else {'master_id': db.table('app.master').insert({})['id']}
        db.commit()
        barrier = Barrier(2)
        def insert_one():
            try:
                barrier.wait(timeout=10)
                item = db.table('app.item').insert(dict(values))
                db.commit()
                return item['_row_count' if declare is ranked else '_relidx']
            finally:
                db.closeConnection()
        with ThreadPoolExecutor(2) as pool:
            results = list(pool.map(lambda _: insert_one(), range(2)))
        assert sorted(results) == [1, 2]


def test_concurrent_opposing_moves_cannot_create_cycle(implementation, tmp_path):
    with migrated_db(implementation, tmp_path, hierarchy) as db:
        table = db.table('app.item')
        a, b = table.insert({'code': 'a'}), table.insert({'code': 'b'})
        db.commit()
        barrier = Barrier(2)
        def move(pair):
            child, parent = pair
            try:
                barrier.wait(timeout=10)
                db.table('app.item').update(dict(child, owner_id=parent['id']), old_record=deepcopy(child))
                db.commit()
                return True
            except Exception as error:
                db.rollback()
                assert 'cannot be moved under itself' in str(error)
                return False
            finally:
                db.closeConnection()
        with ThreadPoolExecutor(2) as pool:
            results = list(pool.map(move, [(a, b), (b, a)]))
        assert sorted(results) == [False, True]


def partitioned(package):
    table = package.table('item', name_long='Item', partition_organization='organization')
    table.options().sys_fields()
    table.column('organization', dtype='L')
    table.column('value', dtype='L')


def test_partition_autofill_raw_guards_and_explicit_bypass(implementation, tmp_path):
    with migrated_db(implementation, tmp_path, partitioned) as db:
        table = db.table('app.item')
        other = table.insert({'organization': 2, 'value': 10})
        db.commit()
        with db.tempEnv(current_organization=1):
            own = table.insert({'value': 1})
            assert own['organization'] == 1
            raw = table.sql_insert({'value': 2})
            assert table._reread(raw['id'])['organization'] == 1
            table.sql_update({'id': other['id'], 'value': 99})
            table.sql_delete({'id': other['id']})
            assert table._reread(other['id'])['value'] == 10
            assert table.query(ignorePartition=True).sql_update({'value': 3}) == 2
            assert table._reread(other['id'])['value'] == 10
            table.sql_update({'id': other['id'], 'value': 11}, ignore_partition=True)
            assert table._reread(other['id'])['value'] == 11
            db.commit()
            with pytest.raises(ValueError, match='outside'):
                table.update({'id': own['id'], 'organization': 2})
            db.rollback()
            with pytest.raises(ValueError, match='outside'):
                table.sql_insert({'organization': 2})
            db.rollback()
        with db.tempEnv(allowed_organization=[]):
            table.sql_delete({'id': own['id']})
            assert table._reread(own['id']) is not None
            with pytest.raises(ValueError, match='outside'):
                table.insert({'organization': None})
            db.rollback()


@pytest.mark.parametrize('expression', ['value * 3', 'value +'])
def test_generated_expression_changes_require_explicit_migration(implementation, tmp_path, expression):
    from asqueel.errors import MigrationError
    with migrated_db(implementation, tmp_path, generated) as db:
        table = db.table('app.item')
        table.insert({'value': 4})
        db.commit()
        # Change the desired source, keeping the real database and its data.
        db.config.builder.source.get_node('db.packages.app.tables.item.columns.computed').attr[
            'sql_generatedExpression'] = expression
        plan = db.migration_plan()
        assert not plan.empty and plan.skipped
        with pytest.raises(MigrationError, match='explicit migration required'):
            db.migrate()
        assert table.query('$computed').fetch()[0]['computed'] == 8


def test_sqlite_generated_expression_parser_preserves_literals_and_comments():
    from asqueel.sqlite_migration import generated_expressions
    expression = "coalesce(\"odd,name\", ') AS (') || '/*text*/'"
    sql = f'CREATE TABLE x ("odd,name" TEXT, result TEXT AS ({expression}) STORED /* AS (bad) */)'
    assert generated_expressions(sql) == {'result': expression}


def test_generated_columns_on_sqlite_memory():
    from asqueel import AsqueelDb, SqlDatabaseConfig
    source = SqlDatabaseConfig()
    root = source.source.db('memory', implementation='sqlite')
    root.connection('main', database=':memory:')
    generated(root.packages().package('app', sqlschema='main', sqlprefix=False))
    db = AsqueelDb(source)
    try:
        db.migrate()
        assert db.table('app.item').insert({'value': 3})['computed'] == 6
        db.commit()
        assert db.migration_plan().empty
    finally:
        db.closeConnection()


def test_partition_refuses_cross_scope_before_hooks(implementation, tmp_path):
    calls = []
    class Observed(SqlTable):
        def trigger_onUpdating(self, record, old_record=None):
            calls.append('update')
        def trigger_onDeleting(self, record):
            calls.append('delete')
    def declare(package):
        partitioned(package)
    with migrated_db(implementation, tmp_path, declare) as db:
        table = db.table('app.item')
        item = table.insert({'organization': 2, 'value': 1})
        db.commit()
        table.trigger_onUpdating = Observed.trigger_onUpdating.__get__(table)
        table.trigger_onDeleting = Observed.trigger_onDeleting.__get__(table)
        with db.tempEnv(current_organization=1):
            for operation in (lambda: table.update({'id': item['id'], 'value': 2}), lambda: table.delete(item)):
                with pytest.raises(ValueError, match='outside'):
                    operation()
                db.rollback()
        assert calls == []


def test_after_hook_failure_rolls_back_descendant_paths(implementation, tmp_path):
    class Fail(SqlTable):
        def trigger_onUpdated(self, record, old_record=None):
            if record.get('code') == 'fail':
                raise RuntimeError('deliberate hook failure')
    with migrated_db(implementation, tmp_path, lambda p: hierarchy(p, table_class=Fail)) as db:
        table = db.table('app.item')
        root = table.insert({'code': 'root'})
        leaf = table.insert({'code': 'leaf', 'owner_id': root['id']})
        db.commit()
        with pytest.raises(RuntimeError, match='deliberate'):
            table.update(dict(root, code='fail'), old_record=root)
        db.rollback()
        assert row(table, leaf['id'])['hierarchical_code'] == 'root/leaf'


def test_linked_root_handles_partial_update_and_master_hook(implementation, tmp_path):
    with migrated_db(implementation, tmp_path, lambda p: hierarchy(p, linked=True)) as db:
        master = db.table('app.master')
        item = master.insert({'code': 'old'})
        def normalize(record, old_record=None):
            record['code'] = record['code'].upper()
        master.trigger_onUpdating = normalize
        master.update({'id': item['id'], 'code': 'new'})
        assert row(db.table('app.item'), item['root_item_id'])['hierarchical_code'] == 'NEW'


def test_delete_hook_cannot_redirect_subtree_cascade(implementation, tmp_path):
    with migrated_db(implementation, tmp_path, hierarchy) as db:
        table = db.table('app.item')
        one, two = table.insert({'code': 'one'}), table.insert({'code': 'two'})
        child = table.insert({'code': 'child', 'owner_id': one['id']})
        other = table.insert({'code': 'other', 'owner_id': two['id']})
        db.commit()
        def redirect(record):
            record['id'] = two['id']
        table.trigger_onDeleting = redirect
        table.delete(one['id'])
        assert table._reread(child['id']) is None
        assert table._reread(other['id']) is not None
        db.rollback()
        assert table._reread(child['id']) is not None


@pytest.mark.parametrize('serial', [True, False])
def test_linked_root_with_database_generated_master_key(implementation, tmp_path, serial):
    def declare(package):
        master = package.table('master', pkey='id')
        if serial:
            master.column('id', dtype='serial')
        else:
            master.options().sys_fields()
        master.column('code', sql_default="'from database'")
        tree = package.table('item')
        tree.options().sys_fields()
        tree.options().hierarchical('code', linked_to='app.master')
        tree.column('code')
    with migrated_db(implementation, tmp_path, declare) as db:
        master = db.table('app.master').insert({})
        root = row(db.table('app.item'), master['root_item_id'])
        assert root['master_id'] == master['id']
        assert root['hierarchical_code'] == 'from database'
        db.commit()
        db.table('app.master').delete(master)
        assert db.table('app.item')._behavior_rows() == []


@pytest.mark.parametrize('position', [-1, True, 1.5])
def test_hierarchy_rejects_invalid_counter_values(implementation, tmp_path, position):
    with migrated_db(implementation, tmp_path, hierarchy) as db:
        with pytest.raises(ValueError, match='nonnegative integer'):
            db.table('app.item').insert({'code': 'invalid', 'position': position})
        db.rollback()
        assert db.table('app.item')._behavior_rows() == []


def test_allowed_only_partition_filters_sql_updates_and_deletes(implementation, tmp_path):
    with migrated_db(implementation, tmp_path, partitioned) as db:
        table = db.table('app.item')
        permitted = table.insert({'organization': 1, 'value': 1})
        global_row = table.insert({'organization': None, 'value': 2})
        excluded = table.insert({'organization': 2, 'value': 3})
        db.commit()
        with db.tempEnv(allowed_organization=[1]):
            assert table.query(ignorePartition=True).sql_update({'value': 9}) == 2
            assert table._reread(permitted['id'])['value'] == 9
            assert table._reread(global_row['id'])['value'] == 9
            assert table._reread(excluded['id'])['value'] == 3
            assert table.query(ignorePartition=True).sql_delete() == 2
            assert table._reread(excluded['id']) is not None
        db.rollback()
        assert len(table._behavior_rows()) == 3
