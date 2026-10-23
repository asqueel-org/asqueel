"""Boundary regression: a line comment in a sql_value cannot comment out the UPDATE key guard."""
import uuid

import pytest

from asqueel import AsqueelDb, SqlDatabaseConfig
from tests.native_support import postgres_dsn

pytestmark = pytest.mark.postgresql


def test_manual_assignment_line_comment_cannot_remove_update_guard():
    name = 'adapter_comment_' + uuid.uuid4().hex[:12]
    source = SqlDatabaseConfig()
    pkg = source.source.db('adapter', implementation='postgres', conninfo=postgres_dsn()).packages().package(
        'adapter', sqlschema='pg_temp', sqlprefix=False)
    table = pkg.table(name, pkey='id')
    table.column('id', dtype='I')
    table.column('value', dtype='I', sql_value='99 -- trailing comment')
    db = AsqueelDb(source)
    try:
        db.execute(f'CREATE TEMP TABLE "{name}" (id integer PRIMARY KEY, value integer)')
        db.execute(f'INSERT INTO "{name}" VALUES (1, 10)')
        model = db.table(f'adapter.{name}').model
        result = db.execute(db.write_compiler.update(model, {'id': 0}, db.environment_snapshot()))
        assert result.rowcount == 0
        assert [tuple(row) for row in db.execute(f'SELECT id, value FROM "{name}"').fetchall()] == [(1, 10)]
        db.rollback()
    finally:
        db.closeConnection()
