"""Controlled visibility on all 74 native tables, both engines, tree SELECTs."""
from datetime import datetime, timezone

import pytest

from examples.test_invoice_pg import source
from tests.native_formulas.test_native_visibility import native_db as execution_db, KEYS  # noqa: F401
from tests.native_formulas.tree_execution import TreeExecution
from tests.object_tree.test_phase4_options import tree_database


@pytest.fixture(scope='module')
def native_db(execution_db):  # noqa: F811
    executor = execution_db
    config = source()
    config.source['db'].attr['implementation'] = executor.adapter.dialect
    tree = tree_database(config)
    try:
        yield TreeExecution(tree, executor)
        assert not tree._connections
    finally:
        tree.closeConnection()


@pytest.mark.parametrize('key', KEYS)
def test_native_default_visibility_and_explicit_overrides(native_db, key):
    db = native_db
    table = db.tree.model.table(key)
    quote = db.adapter.adaptSqlName
    target = f'{quote(table.sqlschema)}.{quote(table.sqlname)}'
    draft = table.attributes.get('draftField')
    deleted = table.attributes.get('logicalDeletionField')
    tombstone = datetime(2026, 1, 1, tzinfo=timezone.utc)
    try:
        db.execute(f'DELETE FROM {target}')
        for is_draft, is_deleted in [(None, False), (False, False), (True, False), (False, True)]:
            values = {}
            if draft:
                values[draft] = is_draft
            if deleted:
                values[deleted] = tombstone if is_deleted else None
            if values:
                fields = ','.join(quote(table.columns[n].sqlname) for n in values)
                params = ','.join(':' + n for n in values)
                db.execute(f'INSERT INTO {target} ({fields}) VALUES ({params})', values)
            else:
                db.execute(f'INSERT INTO {target} DEFAULT VALUES')
        live = db.table(key)
        assert live.query('1 AS row').count() == 4 - bool(draft) - bool(deleted)
        assert live.query('1 AS row', excludeDraft=False).count() == 4 - bool(deleted)
        assert live.query('1 AS row', excludeLogicalDeleted=False).count() == 4 - bool(draft)
        assert live.query('1 AS row', excludeDraft=False, excludeLogicalDeleted=False).count() == 4
        if deleted:
            name = next(iter(table.columns))
            rows = live.query('$' + name, excludeLogicalDeleted='mark', excludeDraft=False).fetch()
            assert len(rows) == 4
            assert sum(row['_isdeleted'] is not None for row in rows) == 1
    finally:
        db.rollback()
