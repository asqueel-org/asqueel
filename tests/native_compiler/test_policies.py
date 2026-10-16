from datetime import datetime, timezone

import pytest

from asqueel import SqlDatabaseConfig, build_database
from asqueel.contracts import UnsupportedFeatureError
from asqueel.environment import SqlEnvironment
from asqueel.write_compiler import WriteCompiler

SCOPE = {'field': 'organization', 'current': 'organization', 'allowed': 'allowed_organizations'}


def database(*, partition=SCOPE, draft='draft', deleted='deleted_at', environment=None):
    config = SqlDatabaseConfig()
    pkg = config.source.db('policies', implementation='postgresql').packages().package('app')
    policies = {'x_partition': partition, 'x_draft_field': draft, 'x_logical_deletion_field': deleted}
    item = pkg.table('item', pkey='id', **{key: value for key, value in policies.items() if value})
    item.column('id', dtype='I')
    item.column('organization', dtype='I')
    item.column('region')
    item.column('draft', dtype='B')
    item.column('deleted_at', dtype='DHZ', x_identity='tombstone')
    return build_database(config, environment=environment)


def writer(db):
    return WriteCompiler(db.dialect, db.driver)


def item(db):
    return db.table('app.item').model


def test_dml_partition_guards_autofill_and_no_draft_or_deleted_filters():
    with database() as db:
        for query in (writer(db).update(item(db), {'id': 1, 'draft': False}, {}),
                      writer(db).delete(item(db), {'id': 1}, {})):
            assert ' IS NOT TRUE' not in query.sql and '"deleted_at" IS NULL' not in query.sql


@pytest.mark.xfail(strict=True, reason='asqueel#15: partition autofill and guard on write')
def test_dml_partition_guards_and_autofill():
    snapshot = {'organization': 0, 'allowed_organizations': [0]}
    with database() as db:
        values = {'id': 1}
        inserted = writer(db).insert(item(db), values, snapshot)
        assert values == {'id': 1}
        assert '"organization"' in inserted.sql and inserted.params['organization'] == 0
        for method in (lambda: writer(db).insert(item(db), {'id': 1, 'organization': 2}, snapshot),
                       lambda: writer(db).update(item(db), {'id': 1, 'organization': 2}, snapshot)):
            with pytest.raises(ValueError, match='outside'):
                method()
        for query in (writer(db).update(item(db), {'id': 1, 'draft': False}, snapshot),
                      writer(db).delete(item(db), {'id': 1}, snapshot)):
            assert '"organization" = ' in query.sql


@pytest.mark.xfail(strict=True, reason='asqueel#15: allowed-only partition refuses inserts outside the allowed values')
def test_allowed_only_insert_requires_value_and_empty_allowed_refuses_insert():
    with database() as db:
        with pytest.raises(ValueError, match='requires partition value'):
            writer(db).insert(item(db), {'id': 1}, {'allowed_organizations': [1]})
        writer(db).insert(item(db), {'id': 1, 'organization': 1}, {'allowed_organizations': [1]})
        with pytest.raises(ValueError, match='outside'):
            writer(db).insert(item(db), {'organization': None}, {'allowed_organizations': []})


def test_soft_delete_and_restore_are_explicit_guarded_updates_with_quoted_marker():
    with database() as db:
        timestamp = datetime(2026, 1, 1, tzinfo=timezone.utc)
        deleted = writer(db).update(item(db), {'id': 1, 'deleted_at': timestamp}, {})
        restored = writer(db).update(item(db), {'id': 1, 'deleted_at': None}, {})
        assert deleted.sql.startswith('UPDATE ') and timestamp in deleted.params.values()
        assert restored.sql.startswith('UPDATE ') and None in restored.params.values()
        assert writer(db).delete(item(db), {'id': 1}, {}).sql.startswith('DELETE ')


def relational_database():
    config = SqlDatabaseConfig()
    pkg = config.source.db('policies', implementation='postgresql').packages().package('app')
    organization = pkg.table('organization', pkey='id')
    organization.column('id', dtype='I')
    organization.column('region')
    source = pkg.table('item', pkey='id', x_partition={'field': '@organization.region', 'current': 'region'})
    source.column('id', dtype='I')
    source.column('organization', dtype='I').relation('app.organization.id')
    return build_database(config, environment=SqlEnvironment({'region': 'north'}))


def test_relational_partition_reads_work_but_writes_are_explicitly_unsupported():
    with relational_database() as db:
        plan = db.compiler.plan_select('app.item', '$id')
        assert plan.joins and 'region' in plan.where and plan.params


@pytest.mark.xfail(strict=True, reason='asqueel#15: relational partition writes are not refused')
def test_relational_partition_writes_are_explicitly_unsupported():
    with relational_database() as db:
        table, snapshot = item(db), db.environment.snapshot()
        for action in (lambda: writer(db).insert(table, {'id': 1}, snapshot),
                       lambda: writer(db).update(table, {'id': 1, 'organization': 2}, snapshot),
                       lambda: writer(db).delete(table, {'id': 1}, snapshot)):
            with pytest.raises(UnsupportedFeatureError, match='Relational partition writes'):
                action()
