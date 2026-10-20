"""Actual visibility on every native table, with controlled rows and no hooks."""
from datetime import datetime, timezone

import pytest

from examples.test_invoice_pg import source
from asqueel import build_database
from tests.native_formulas.conftest import SQL_TYPES, TABLES


# Collect native table identities without opening a database.
KEYS = tuple(build_database(source()).model.tables)


@pytest.fixture(scope='module', params=['db_pg', 'db_sqlite'])
def native_db(request):
    db = request.getfixturevalue(request.param)
    for table in db.model.tables.values():
        if table.fullname in {'invc.' + name for name in TABLES}:
            continue
        columns = ', '.join(f'"{c.sqlname}" {SQL_TYPES.get(c.dtype, "TEXT")}'
                            for c in table.columns.values())
        db.execute(f'CREATE TABLE "{table.sqlschema}"."{table.sqlname}" ({columns})')
    db.commit()
    return db


@pytest.mark.parametrize('key', KEYS)
def test_native_default_visibility_and_explicit_overrides(native_db, key):
    db = native_db
    table = db.model.table(key)
    quote = db.adapter.adaptSqlName
    target = f'{quote(table.sqlschema)}.{quote(table.sqlname)}'
    attrs = table.attributes
    draft = attrs.get('draftField')
    deleted = attrs.get('logicalDeletionField')
    tombstone = datetime(2026, 1, 1, tzinfo=timezone.utc)
    # Independent expected flags come from the render markers, not RowPolicies.
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
            name = next(n for n,c in table.columns.items())
            rows = live.query('$' + name, excludeLogicalDeleted='mark', excludeDraft=False).fetch()
            assert len(rows) == 4
            assert sum(row['_isdeleted'] is not None for row in rows) == 1
    finally:
        db.rollback()
