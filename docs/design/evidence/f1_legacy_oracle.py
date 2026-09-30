"""Run original legacy F1 methods against an isolated PostgreSQL schema.

No Genropy framework import: AST-extracted classes retain their method bodies.
The SQL audit decorator and deferred callback dispatcher are replaced with
no-ops. This verifies connections, execution rollback and TempEnv, not the app,
callbacks, locale parser, triggers, model/compiler or complete framework.
"""
import argparse
import ast
import hashlib
import json
import logging
from pathlib import Path
import re
import _thread
from datetime import date
from time import time
from types import SimpleNamespace
from uuid import uuid4

import psycopg


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('legacy_root', type=Path)
    parser.add_argument('--dsn', required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    ns = dict(GnrSqlDbBaseMixin=object, _thread=_thread, re=re, time=time,
              date=date, defaultLocale=lambda: 'en_GB', getUuid=lambda: uuid4().hex,
              MAIN_CONNECTION_NAME='_main_connection', sql_audit=lambda method: method,
              logger=logging.getLogger('f1_legacy'), GnrException=RuntimeError)
    source_hashes = {}
    for file, name in [('helpers', 'TempEnv'), ('env', 'EnvMixin'),
                       ('connections', 'ConnectionMixin'), ('execute', 'ExecuteMixin'),
                       ('transactions', 'TransactionMixin')]:
        path = args.legacy_root / 'gnrpy/gnr/sql/gnrsql' / (file + '.py')
        raw = path.read_bytes()
        source_hashes[str(path.relative_to(args.legacy_root))] = hashlib.sha256(raw).hexdigest()
        cls = next(n for n in ast.parse(raw).body if isinstance(n, ast.ClassDef) and n.name == name)
        module = ast.Module(body=[ast.ImportFrom(module='__future__',
                            names=[ast.alias(name='annotations')], level=0), cls], type_ignores=[])
        exec(compile(ast.fix_missing_locations(module), str(path), 'exec'), ns)

    class Connection(psycopg.Connection):
        pass

    class Legacy(ns['EnvMixin'], ns['ConnectionMixin'], ns['ExecuteMixin'], ns['TransactionMixin']):
        rootstore = '_main_db'
        implementation = 'postgres'
        multidomain = False
        debugger = None
        QUEUE_DEFER_TO_COMMIT = 'to_commit_defer_calls'
        QUEUE_DEFER_AFTER_COMMIT = 'after_commit_defer_calls'

        def __init__(self):
            self._currentEnv = {}
            self._connections = {}
            self.adapter = SimpleNamespace(connect=lambda store: Connection.connect(args.dsn),
                                           cursor=lambda conn: conn.cursor(),
                                           prepareSqlText=lambda sql, params: (sql, params))

        def _invoke_deferred_cbs(self, queue):
            pass  # Explicit boundary: callback semantics are F4, not this oracle.

    db = Legacy()
    schema = 'f1_legacy_' + uuid4().hex
    with psycopg.connect(args.dsn, autocommit=True) as observer:
        observer.execute(f'CREATE SCHEMA "{schema}"')
        observer.execute(f'CREATE TABLE "{schema}".item (id integer PRIMARY KEY)')
        try:
            db.currentEnv = {'user': 'original', 'items': []}
            with db.tempEnv(user='temporary', introduced=1):
                db.currentEnv['introduced'] = 2
                db.currentEnv['other'] = 'keep'
                db.currentEnv['items'].append(1)
            assert db.currentEnv == {'user': 'original', 'items': [1],
                                     'introduced': 2, 'other': 'keep'}
            environment_result = dict(db.currentEnv)
            main_pid = db.execute('SELECT pg_backend_pid()').fetchone()[0]
            db.execute(f'INSERT INTO "{schema}".item VALUES (1)')
            with db.tempEnv(connectionName='independent'):
                other_pid = db.execute('SELECT pg_backend_pid()').fetchone()[0]
                assert main_pid != other_pid
                assert db.execute(f'SELECT id FROM "{schema}".item').fetchall() == []
                db.execute(f'INSERT INTO "{schema}".item VALUES (2)')
                try:
                    db.execute(f'INSERT INTO "{schema}".item VALUES (2)')
                except psycopg.errors.UniqueViolation:
                    pass
                else:
                    raise AssertionError('Expected duplicate error')
                assert db.execute(f'SELECT id FROM "{schema}".item').fetchall() == []
                db.execute(f'INSERT INTO "{schema}".item VALUES (3)')
                db.commit()
                assert db.execute('SELECT pg_backend_pid()').fetchone()[0] == other_pid
                assert observer.execute(f'SELECT id FROM "{schema}".item').fetchall() == [(3,)]
            assert db.execute('SELECT pg_backend_pid()').fetchone()[0] == main_pid
            db.rollback()
            assert db.execute('SELECT pg_backend_pid()').fetchone()[0] == main_pid
            assert observer.execute(f'SELECT id FROM "{schema}".item').fetchall() == [(3,)]
            result = dict(source_sha256=source_hashes, environment_after_scope=environment_result,
                          distinct_connections=True, connection_retained_after_commit=True,
                          connection_retained_after_rollback=True, automatic_sql_rollback=True,
                          retry_without_manual_rollback=True, only_committed_rows=[3],
                          method='AST-extracted legacy methods; real PostgreSQL; app/deferred hooks excluded')
        finally:
            db.closeConnection()
            observer.execute(f'DROP SCHEMA "{schema}" CASCADE')
    args.output.write_text(json.dumps(result, indent=2) + '\n')
    print('Legacy F1 oracle passed; schema removed.')


if __name__ == '__main__':
    main()
