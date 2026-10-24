from datetime import datetime, timezone

import pytest

from asqueel import SqlDatabaseConfig, AsqueelDb
from asqueel.write_compiler import WriteCompiler

def database(*, partition='organization', draft='draft', deleted='deleted_at', environment=None):
    config = SqlDatabaseConfig()
    pkg = config.source.db('policies', implementation='postgres').packages().package('app')
    policies = {'partition_organization': partition, 'draftField': draft, 'logicalDeletionField': deleted}
    item = pkg.table('item', pkey='id', **{key: value for key, value in policies.items() if value})
    item.column('id', dtype='I')
    item.column('organization', dtype='I')
    item.column('region')
    item.column('draft', dtype='B')
    item.column('deleted_at', dtype='DHZ')
    return AsqueelDb(config, environment=environment)


def writer(db):
    return WriteCompiler(db.adapter)


def item(db):
    return db.table('app.item').model


def test_dml_partition_guards_autofill_and_no_draft_or_deleted_filters():
    db = database()
    try:
        for query in (writer(db).update(item(db), {'id': 1, 'draft': False}, {}),
                      writer(db).delete(item(db), {'id': 1}, {})):
            assert ' IS NOT TRUE' not in query.sql and '"deleted_at" IS NULL' not in query.sql
    finally:
        db.closeConnection()


def test_dml_partition_guards_and_autofill():
    snapshot = {'current_organization': 0, 'allowed_organization': [0]}
    db = database()
    try:
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
    finally:
        db.closeConnection()


def test_allowed_only_insert_requires_value_and_empty_allowed_refuses_insert():
    db = database()
    try:
        with pytest.raises(ValueError, match='requires partition value'):
            writer(db).insert(item(db), {'id': 1}, {'allowed_organization': [1]})
        writer(db).insert(item(db), {'id': 1, 'organization': 1}, {'allowed_organization': [1]})
        with pytest.raises(ValueError, match='outside'):
            writer(db).insert(item(db), {'organization': None}, {'allowed_organization': []})
    finally:
        db.closeConnection()


def test_soft_delete_and_restore_are_explicit_guarded_updates_with_quoted_marker():
    db = database()
    try:
        timestamp = datetime(2026, 1, 1, tzinfo=timezone.utc)
        deleted = writer(db).update(item(db), {'id': 1, 'deleted_at': timestamp}, {})
        restored = writer(db).update(item(db), {'id': 1, 'deleted_at': None}, {})
        assert deleted.sql.startswith('UPDATE ') and timestamp in deleted.params.values()
        assert restored.sql.startswith('UPDATE ') and None in restored.params.values()
        assert writer(db).delete(item(db), {'id': 1}, {}).sql.startswith('DELETE ')
    finally:
        db.closeConnection()

