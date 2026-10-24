"""Run with ASQUEEL_TEST_DSN against a disposable PostgreSQL database."""
import uuid

import pytest

from tests.native_support import postgres_dsn

pytestmark = pytest.mark.postgresql


def test_composite_fk_is_applied_and_enforced_by_postgres_migration():
    import psycopg
    dsn = postgres_dsn()
    schema = 'fk_regression_' + uuid.uuid4().hex[:12]
    from asqueel import AsqueelDb, SqlDatabaseConfig

    class Config(SqlDatabaseConfig):
        def main(self, root):
            db = root.db('demo', implementation='postgres', conninfo=dsn)
            tables = db.packages().package('s', sqlschema=schema, sqlprefix=False).tables()
            parent = tables.table('parent', pkey='pk')
            columns = parent.columns()
            columns.column('x', dtype='I')
            columns.column('y', dtype='I')
            parent.composites().compositeColumn('pk', columns='x,y')
            child = tables.table('child', pkey='id')
            columns = child.columns()
            columns.column('id', dtype='I')
            columns.column('ax', dtype='I')
            columns.column('ay', dtype='I')
            child.composites().compositeColumn('pair', columns='ax,ay').relation(
                's.parent', foreign_key=True, onDelete_sql='cascade')

    db = AsqueelDb(Config)
    try:
        assert not db.migrate()['empty']
        db.table('s.parent').insert({'x': 1, 'y': 2})
        db.table('s.child').insert({'id': 1, 'ax': 1, 'ay': 2})
        db.commit()
        with pytest.raises(psycopg.errors.ForeignKeyViolation):
            db.table('s.child').insert({'id': 2, 'ax': 1, 'ay': 3})
        db.table('s.parent').delete({'x': 1, 'y': 2})
        db.commit()
        assert db.table('s.child').query().fetch() == []
    finally:
        try:
            db.rollback()
            db.execute(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE')
            db.commit()
        finally:
            db.closeConnection()
