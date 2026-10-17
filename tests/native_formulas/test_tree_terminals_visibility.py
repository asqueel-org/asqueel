"""Fetch/count and transaction visibility on all 74 tables through the real facade."""
from datetime import datetime, timezone

import pytest

from tests.native_formulas.test_native_visibility import native_db as execution_db, KEYS  # noqa: F401
from tests.native_formulas.test_tree_terminals_legacy import live_database


@pytest.fixture(scope='module')
def native_db(execution_db):  # noqa: F811
    yield from live_database(execution_db)


@pytest.mark.parametrize('key', KEYS)
def test_native_default_visibility_and_explicit_overrides(native_db, key):
    db = native_db
    table = db.model.table(key)
    quote = db.adapter.adaptSqlName
    target = f'{quote(table.sqlschema)}.{quote(table.sqlname)}'
    draft = table.attributes.get('x_legacy_draftField')
    deleted = table.attributes.get('x_legacy_logicalDeletionField')
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
