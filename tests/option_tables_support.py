"""Tables declared with options, migrated from their declaration on SQLite or PostgreSQL."""
from contextlib import contextmanager
from uuid import uuid4

import psycopg
from psycopg.conninfo import make_conninfo
from psycopg import sql
import pytest

from asqueel import AsqueelDb, SqlDatabaseConfig
from tests.native_support import postgres_dsn

IMPLEMENTATIONS = ['sqlite', pytest.param('postgres', marks=pytest.mark.postgresql)]


@contextmanager
def migrated_db(implementation, tmp_path, declare=None, path=None, declare_db=None):
    """A SessionDb on an AsqueelDb whose package ``app`` is filled by ``declare(package)`` and migrated.

    ``path`` is the package folder whose ``model/<table>.py`` declare tables with their ``Table`` class.
    ``declare_db(db)`` declares on the root ``db`` node; on PostgreSQL it gets a database of its own,
    because db-level options add schemas with fixed names.
    """
    source = SqlDatabaseConfig()
    schema = database = None
    if implementation == 'sqlite':
        root = source.source.db('options', implementation='sqlite')
        root.connection('main', database=str(tmp_path / 'options.sqlite'))
        sqlschema = 'main'
    else:
        schema = sqlschema = 'opt_' + uuid4().hex[:12]
        conninfo = postgres_dsn()
        if declare_db is not None:
            database = schema
            with psycopg.connect(conninfo, autocommit=True) as conn:
                conn.execute(sql.SQL('CREATE DATABASE {}').format(sql.Identifier(database)))
            conninfo = make_conninfo(conninfo, dbname=database)
        root = source.source.db('options', implementation='postgres', conninfo=conninfo)
        with psycopg.connect(conninfo, autocommit=True) as conn:
            conn.execute(sql.SQL('CREATE SCHEMA {}').format(sql.Identifier(schema)))
    if declare_db is not None:
        declare_db(root)
    package = root.packages().package(
        'app', sqlschema=sqlschema, sqlprefix=False, **({} if path is None else {'path': path}))
    if declare is not None:
        declare(package)
    db = AsqueelDb(source).session()
    try:
        db.migrate()
        db.commit()
        yield db
    finally:
        db.shared.close()
        if database:
            with psycopg.connect(postgres_dsn(), autocommit=True) as conn:
                conn.execute(sql.SQL('DROP DATABASE {} WITH (FORCE)').format(sql.Identifier(database)))
        elif schema:
            with psycopg.connect(postgres_dsn(), autocommit=True) as conn:
                conn.execute(sql.SQL('DROP SCHEMA {} CASCADE').format(sql.Identifier(schema)))


def row(table, pkey, columns='*'):
    """One row read back from the database, as a dict."""
    rows = table.query(columns=columns, where='$id=:pk', pk=pkey).fetch()
    assert len(rows) == 1
    return dict(rows[0])
