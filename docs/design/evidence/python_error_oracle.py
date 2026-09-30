"""Compare Python failures in legacy write/commit methods and native Asqueel.

Run twice against a disposable PostgreSQL service, with --legacy-root for the
legacy run. Original AST definitions and the real legacy Bag execute unchanged.
The adapter emits fixed fixture SQL; table validation/counters/related writes,
SQL auditing and app notifications are excluded. This is a core lifecycle
oracle, not a full Genropy application compatibility test.
"""
import argparse
import ast
from contextlib import contextmanager
from datetime import date
import hashlib
import json
import logging
from pathlib import Path
import re
import subprocess
import sys
import _thread
from time import time
from types import SimpleNamespace
from uuid import uuid4

import psycopg


HOOKS = {
    'insert': ('trigger_onInserting', 'trigger_onInserted'),
    'update': ('trigger_onUpdating', 'trigger_onUpdated'),
    'delete': ('trigger_onDeleting', 'trigger_onDeleted'),
}


def noop(*args, **kwargs):
    pass


def legacy_factory(root, dsn):
    sys.path.insert(0, str(root / 'gnrpy'))
    import gnr.core.gnrbag as bag_module
    from gnr.core.gnrbag import Bag
    assert Path(bag_module.__file__).resolve().is_relative_to(root.resolve())
    ns = dict(GnrSqlDbBaseMixin=object, _thread=_thread, re=re, time=time,
              date=date, defaultLocale=lambda: 'en_GB', getUuid=lambda: uuid4().hex,
              MAIN_CONNECTION_NAME='_main_connection', sql_audit=lambda fn: fn,
              logger=logging.getLogger('python_error_oracle'), GnrException=RuntimeError,
              GnrSqlException=RuntimeError, Bag=Bag)
    sources = {}
    for module_name, names in (
        ('helpers', {'TempEnv', 'TriggerStack', 'TriggerStackItem', 'in_triggerstack'}),
        ('env', {'EnvMixin'}), ('connections', {'ConnectionMixin'}),
        ('execute', {'ExecuteMixin'}), ('transactions', {'TransactionMixin'}),
        ('write', {'WriteMixin'}),
    ):
        path = root / 'gnrpy/gnr/sql/gnrsql' / (module_name + '.py')
        raw = path.read_bytes()
        sources[str(path.relative_to(root))] = hashlib.sha256(raw).hexdigest()
        nodes = [n for n in ast.parse(raw).body
                 if isinstance(n, (ast.ClassDef, ast.FunctionDef)) and n.name in names]
        assert len(nodes) == len(names)
        module = ast.Module(body=[ast.ImportFrom(module='__future__',
                            names=[ast.alias(name='annotations')], level=0), *nodes], type_ignores=[])
        exec(compile(ast.fix_missing_locations(module), str(path), 'exec'), ns)
    sources['gnrpy/gnr/core/gnrbag.py'] = hashlib.sha256(
        Path(bag_module.__file__).read_bytes()).hexdigest()

    class Connection(psycopg.Connection):
        pass

    class Legacy(ns['EnvMixin'], ns['ConnectionMixin'], ns['ExecuteMixin'],
                 ns['TransactionMixin'], ns['WriteMixin']):
        rootstore = '_main_db'
        implementation = 'postgres'
        multidomain = False
        debugger = None
        QUEUE_DEFER_TO_COMMIT = 'to_commit_defer_calls'
        QUEUE_DEFER_AFTER_COMMIT = 'after_commit_defer_calls'
        _onDbChange = staticmethod(noop)

        def __init__(self, schema):
            self._currentEnv = {}
            self._connections = {}
            self.adapter = SimpleNamespace(
                connect=lambda store: Connection.connect(dsn),
                cursor=lambda conn: conn.cursor(), prepareSqlText=lambda sql, params: (sql, params),
                insert=lambda table, record: self.execute(
                    f'INSERT INTO "{schema}".item VALUES (%(id)s, %(name)s)', record),
                update=lambda table, record, **kwargs: self.execute(
                    f'UPDATE "{schema}".item SET name=%(name)s WHERE id=%(id)s', record),
                delete=lambda table, record: self.execute(
                    f'DELETE FROM "{schema}".item WHERE id=%(id)s', record),
            )
            self.item = SimpleNamespace(fullname='app.item', attributes={}, draftField=None)
            for name in ('checkPkey', 'protect_validate', 'protect_update', 'protect_delete',
                         '_doFieldTriggers', '_doExternalPkgTriggers', 'trigger_assignCounters',
                         'trigger_releaseCounters', 'updateRelated', 'deleteRelated',
                         *(hook for pair in HOOKS.values() for hook in pair)):
                setattr(self.item, name, noop)

        def write(self, operation):
            record = {'id': 20 if operation == 'insert' else 10, 'name': 'changed'}
            if operation == 'update':
                self.update(self.item, record, old_record={'id': 10, 'name': 'original'})
            else:
                getattr(self, operation)(self.item, record)

        def stack_depth(self):
            return len(self.currentEnv.get('_trigger_stack', ()))

        close = ns['ConnectionMixin'].closeConnection

    return Legacy, {'commit': subprocess.check_output(
        ['git', '-C', str(root), 'rev-parse', 'HEAD'], text=True).strip(), 'sha256': sources}


def native_factory(dsn):
    from asqueel import CompiledQuery, SqlDatabaseConfig, SqlTable, build_database

    item_class = type('OracleItem', (SqlTable,),
                      {hook: noop for pair in HOOKS.values() for hook in pair})

    class Native:
        def __init__(self, schema):
            class Recipe(SqlDatabaseConfig):
                def main(self, root):
                    columns = root.db('oracle', conninfo=dsn).schemas().schema(
                        'app', x_sql_schema=schema).tables().table(
                            'item', pkey='id', x_table_class=item_class).columns()
                    columns.column('id', dtype='I')
                    columns.column('name', dtype='T')
            self.db = build_database(Recipe)
            self.item = self.db.table('item')

        def __getattr__(self, name):
            return getattr(self.db, name)

        def execute(self, sql):
            return self.db.execute(CompiledQuery(sql))

        def write(self, operation):
            record = {'id': 20 if operation == 'insert' else 10, 'name': 'changed'}
            getattr(self.item, operation)(record)

        def stack_depth(self):
            return len(self.db._trigger_stack)

    return Native, {}


@contextmanager
def fixture(factory, dsn):
    schema = 'python_error_' + uuid4().hex
    with psycopg.connect(dsn, autocommit=True) as observer:
        observer.execute(f'CREATE SCHEMA "{schema}"')
        db = None
        try:
            observer.execute(f'CREATE TABLE "{schema}".item (id integer PRIMARY KEY, name text)')
            observer.execute(f'INSERT INTO "{schema}".item VALUES (10,\'original\')')
            observer.execute(f'CREATE TABLE "{schema}".audit (event text)')
            db = factory(schema)

            def visible():
                return dict(items=observer.execute(
                    f'SELECT id,name FROM "{schema}".item ORDER BY id').fetchall(),
                    audit=[r[0] for r in observer.execute(
                        f'SELECT event FROM "{schema}".audit ORDER BY event').fetchall()])

            def write_audit(event):
                assert event in ('earlier', 'hook', 'callback', 'recovered')
                db.execute(f'INSERT INTO "{schema}".audit VALUES (\'{event}\')')

            yield db, visible, write_audit
        finally:
            try:
                if db is not None:
                    db.close()
            finally:
                observer.execute(f'DROP SCHEMA "{schema}" CASCADE')


def scenarios(factory, dsn):
    results = {}
    for operation, hooks in HOOKS.items():
        for hook in hooks:
            for completion in ('rollback', 'commit'):
                with fixture(factory, dsn) as (db, visible, write):
                    trace = []
                    original = ValueError('hook failure')

                    def fail(*args, **kwargs):
                        write('hook')
                        raise original

                    setattr(db.item, hook, fail)
                    write('earlier')
                    db.deferToCommit(lambda: trace.append('before'))
                    db.deferAfterCommit(lambda: trace.append('after'))
                    try:
                        db.write(operation)
                    except ValueError as error:
                        assert error is original
                    else:
                        raise AssertionError('Hook did not raise')
                    result = {'visible_after_error': visible(), 'trigger_depth': db.stack_depth()}
                    try:
                        getattr(db, completion)()
                        result['completion_error'] = None
                    except Exception as error:
                        result['completion_error'] = type(error).__name__
                    result['visible_after_completion'] = visible()
                    result['callbacks'] = trace[:]
                    # Recovery uses connection closure: legacy rollback alone does
                    # not clear its deferred queues, unlike native rollback.
                    db.close()
                    results[f'{hook}/{completion}'] = result
    for queue in ('before', 'after'):
        for new_write in (False, True):
            with fixture(factory, dsn) as (db, visible, write):
                trace = []
                original = ValueError('callback failure')

                def fail():
                    if new_write:
                        write('callback')
                    raise original

                write('earlier')
                register = db.deferToCommit if queue == 'before' else db.deferAfterCommit
                register(fail)
                register(lambda: trace.append('later'))
                if queue == 'before':
                    db.deferAfterCommit(lambda: trace.append('after'))
                try:
                    db.commit()
                except ValueError as error:
                    assert error is original
                else:
                    raise AssertionError('Callback did not raise')
                result = {'visible_after_error': visible(), 'callbacks_after_error': trace[:]}
                try:
                    db.commit()
                    result['retry_error'] = None
                except Exception as error:
                    result['retry_error'] = type(error).__name__
                result['visible_after_retry'] = visible()
                result['callbacks_after_retry'] = trace[:]
                db.rollback()
                write('recovered')
                db.commit()
                result['visible_after_recovery'] = visible()
                result['callbacks_after_recovery'] = trace[:]
                results[f'{queue}/write={new_write}'] = result
    return results


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--legacy-root', type=Path)
    parser.add_argument('--dsn', required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    factory, source = (legacy_factory(args.legacy_root, args.dsn) if args.legacy_root
                       else native_factory(args.dsn))
    result = {'source': source, 'results': scenarios(factory, args.dsn)}
    args.output.write_text(json.dumps(result, indent=2) + '\n')
    print(f'{len(result["results"])} lifecycle scenarios recorded; disposable schemas removed.')


if __name__ == '__main__':
    main()
