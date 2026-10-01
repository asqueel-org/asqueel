"""Legacy oracle for collection parameters, DISTINCT, GROUP BY/HAVING and count.

Plan 30, step 1; contract matrix in docs/design/31-query-contract-matrix.md.
No Genropy framework import: the legacy code below is extracted by AST from the
checkout given on the command line and executed with real PostgreSQL and SQLite.

Executed verbatim: the whole path of the ``executed-extracted`` entries, and
the execution path (parameter rewriting, SQL assembly, cursor, count) of the
``derived-from-source`` entries:

- ``gnrpostgres3.py``: ``RE_SQL_PARAMS``, ``SqlDbAdapter.adaptTupleListSet``,
  ``prepareSqlText`` and ``compileSql``; ``gnrdict_row`` and ``GnrDictCursor``.
- ``_gnrbaseadapter.py``: ``SqlDbAdapter.adaptTupleListSet``, ``compileSql`` and
  ``_selectForUpdate``.
- ``gnrsqlite.py``: ``SqlDbAdapter.prepareSqlText``, ``_booleanSubCb`` and
  ``_selectForUpdate``.
- ``gnrsql/``: ``TempEnv``, ``EnvMixin``, ``ConnectionMixin``, ``ExecuteMixin``
  and ``TransactionMixin`` (``db.execute``, ``tempEnv``, ``rollback``).
- ``gnrsqldata/query.py``: ``SqlQuery.cursor`` and ``SqlQuery.count``.

Stubs and limits, stated here and in document 31:

- ``SqlQueryCompiler.compiledQuery`` cannot run outside the framework (model,
  relation tree, Bag, macro expanders). For the compiled-query entries
  (``method: derived-from-source``) the SQL fragments it would produce are
  written by hand from the cited source lines and assembled by the extracted
  ``compileSql``. ``SqlQuery.compileQuery`` is replaced by a stub returning
  those fragments; ``count`` and ``cursor`` around it are the original code.
- The correlation of the subquery formula (``#THIS``) is written in its
  resolved form; the subquery alias follows ``compiler.py:416``.
- ``GnrNamedList`` is replaced by ``list`` (row access by position only); the
  psycopg and sqlite3 base cursors are subclassed only to record the SQL text
  and parameters actually sent to the driver.
- The SQLite connection is a plain ``sqlite3`` in-memory connection with the
  sqlite3 default cursor (``GnrSqliteCursor`` only logs and re-wraps ``str``
  values); the legacy ``connect`` options and ``regexp`` function are not used.
- ``sql_audit``, the deferred-callback dispatcher and ``table().use_dbstores``
  are no-ops. No application, trigger, package, store or locale code runs.

Run with a disposable PostgreSQL database; the script creates and drops only
its own randomly named schema there. The output is deterministic: the schema
name is written as ``<schema>`` and an error message is recorded as its first
line.
"""
import argparse
import ast
import hashlib
import json
import logging
import re
import sqlite3
import subprocess
import _thread
from collections.abc import Mapping
from datetime import date
from pathlib import Path
from time import time
from types import SimpleNamespace
from uuid import uuid4

import psycopg
from psycopg import sql as psycopg_sql
from psycopg.rows import no_result

LEGACY_REVISION = 'fa35e5adfa6ad1b269f3a22a9b12c4c1ee6513ea'
PG3 = 'gnrpy/gnr/sql/adapters/gnrpostgres3.py'
BASE = 'gnrpy/gnr/sql/adapters/_gnrbaseadapter.py'
SQLITE = 'gnrpy/gnr/sql/adapters/gnrsqlite.py'
EXECUTE = 'gnrpy/gnr/sql/gnrsql/execute.py'
COMPILER = 'gnrpy/gnr/sql/gnrsqldata/compiler.py'
QUERY = 'gnrpy/gnr/sql/gnrsqldata/query.py'

CUSTOMERS = [(1, 'Ada'), (2, 'Grace'), (3, 'Linus')]
# Invoice 13 has no customer; invoice 14 is logically deleted; 11 and 15 share
# a total, 14 repeats it among the deleted rows.
INVOICES = [
    (10, 1, '125.00', 'First order', None),
    (11, 2, '40.00', None, None),
    (12, 1, '15.50', 'Second order', None),
    (13, None, '7.00', 'No customer', None),
    (14, 2, '40.00', 'Deleted', '2026-01-01 00:00:00'),
    (15, 3, '40.00', None, None),
]
PG_DDL = (
    'CREATE TABLE "{schema}".customer (id bigint PRIMARY KEY, name text NOT NULL)',
    'CREATE TABLE "{schema}".invoice (id bigint PRIMARY KEY, customer_id bigint, '
    'total numeric(12,2) NOT NULL, note text, __del_ts timestamp)',
)
SQLITE_DDL = (
    'CREATE TABLE customer (id INTEGER PRIMARY KEY, name TEXT NOT NULL)',
    'CREATE TABLE invoice (id INTEGER PRIMARY KEY, customer_id INTEGER, '
    'total NUMERIC NOT NULL, note TEXT, __del_ts TIMESTAMP)',
)

# Fragments as compiledQuery renders them for the oracle model (invoice: pkey
# id, logicalDeletionField __del_ts; customer: pkey id).
NOT_DELETED = '"t0"."__del_ts" IS NULL'
ID_COLUMNS = '"t0"."id" AS "id",\n"t0"."id" AS "pkey"'
SRC_WHERE = f'{COMPILER}:990'
SRC_DELETED = f'{COMPILER}:981'
SRC_PKEY = f'{COMPILER}:947'
SRC_AGGREGATE = f'{COMPILER}:902'
SRC_EXPAND_PG = f'{PG3}:74'
SRC_EXPAND_SQLITE = f'{BASE}:208'
SRC_PREPARE = f'{EXECUTE}:121'


def where_visible(condition=None):
    """compiler.py:990 wraps each chunk; :981 adds the logical deletion chunk."""
    chunks = [condition, NOT_DELETED]
    return ' AND '.join(f'({chunk})' for chunk in chunks if chunk)


def extract(root, relpath, hashes, lines, *, cls=None, names=()):
    """Return AST nodes of top-level ``names``, or of ``cls`` methods ``names``."""
    raw = (root / relpath).read_bytes()
    hashes[relpath] = hashlib.sha256(raw).hexdigest()
    body = ast.parse(raw).body
    if cls is not None:
        node = next(n for n in body if isinstance(n, ast.ClassDef) and n.name == cls)
        methods = [n for n in node.body if isinstance(n, ast.FunctionDef) and n.name in names]
        assert sorted(m.name for m in methods) == sorted(names), (relpath, cls, names)
        for method in methods:
            lines.append(f'{relpath}:{method.lineno} {cls}.{method.name}')
        return ast.ClassDef(name=cls, bases=[], keywords=[], body=methods, decorator_list=[])
    found = []
    for node in body:
        if isinstance(node, (ast.ClassDef, ast.FunctionDef)) and node.name in names:
            found.append(node)
            lines.append(f'{relpath}:{node.lineno} {node.name}')
        elif isinstance(node, ast.Assign) and any(
                isinstance(t, ast.Name) and t.id in names for t in node.targets):
            found.append(node)
            lines.append(f'{relpath}:{node.lineno} {node.targets[0].id}')
    assert len(found) == len(names), (relpath, names)
    return found


def run_nodes(nodes, relpath, ns):
    module = ast.Module(body=[ast.ImportFrom(module='__future__',
                        names=[ast.alias(name='annotations')], level=0), *nodes],
                        type_ignores=[])
    exec(compile(ast.fix_missing_locations(module), relpath, 'exec'), ns)
    return ns


def check_legacy(root):
    head = subprocess.run(['git', '-C', str(root), 'rev-parse', 'HEAD'], check=True,
                          capture_output=True, text=True).stdout.strip()
    if head != LEGACY_REVISION:
        raise SystemExit(f'Legacy checkout is at {head}, expected {LEGACY_REVISION}')
    dirty = subprocess.run(['git', '-C', str(root), 'status', '--porcelain', '--',
                            'gnrpy/gnr/sql'], check=True, capture_output=True,
                           text=True).stdout.strip()
    if dirty:
        raise SystemExit(f'Legacy gnrpy/gnr/sql has local changes:\n{dirty}')


def load_legacy(root):
    hashes, lines = {}, []
    logger = logging.getLogger('query_legacy_oracle')
    logger.addHandler(logging.NullHandler())
    logger.propagate = False

    class RecordingPgCursor(psycopg.Cursor):
        """Records the text and parameters handed to the psycopg driver."""

        def execute(self, query, params=None, **kwargs):
            self.sent = (query, params)
            return super().execute(query, params, **kwargs)

    pg_ns = run_nodes(extract(root, PG3, hashes, lines,
                              names=('RE_SQL_PARAMS', 'gnrdict_row', 'GnrDictCursor')),
                      PG3, dict(re=re, Cursor=RecordingPgCursor, Mapping=Mapping,
                                sql=psycopg_sql, no_result=no_result,
                                GnrNamedList=lambda index, values: list(values)))
    run_nodes([extract(root, PG3, hashes, lines, cls='SqlDbAdapter',
                       names=('adaptTupleListSet', 'prepareSqlText', 'compileSql'))],
              PG3, pg_ns)
    base_ns = run_nodes([extract(root, BASE, hashes, lines, cls='SqlDbAdapter',
                                 names=('adaptTupleListSet', 'compileSql', '_selectForUpdate'))],
                        BASE, dict(re=re))
    sqlite_ns = run_nodes([extract(root, SQLITE, hashes, lines, cls='SqlDbAdapter',
                                   names=('prepareSqlText', '_booleanSubCb', '_selectForUpdate'))],
                          SQLITE, dict(re=re))
    db_ns = dict(GnrSqlDbBaseMixin=object, _thread=_thread, re=re, time=time, date=date,
                 getUuid=lambda: uuid4().hex, MAIN_CONNECTION_NAME='_main_connection',
                 sql_audit=lambda method: method, logger=logger, GnrException=RuntimeError,
                 defaultLocale=lambda: 'en_GB')
    for file, name in [('helpers', 'TempEnv'), ('env', 'EnvMixin'),
                       ('connections', 'ConnectionMixin'), ('execute', 'ExecuteMixin'),
                       ('transactions', 'TransactionMixin')]:
        relpath = f'gnrpy/gnr/sql/gnrsql/{file}.py'
        run_nodes(extract(root, relpath, hashes, lines, names=(name,)), relpath, db_ns)
    query_ns = run_nodes([extract(root, QUERY, hashes, lines, cls='SqlQuery',
                                  names=('cursor', 'count'))], QUERY, {})
    return SimpleNamespace(
        pg_adapter=type('LegacyPostgresAdapter',
                        (pg_ns['SqlDbAdapter'], base_ns['SqlDbAdapter']), {}),
        sqlite_adapter=type('LegacySqliteAdapter',
                            (sqlite_ns['SqlDbAdapter'], base_ns['SqlDbAdapter']), {}),
        cursor_class=pg_ns['GnrDictCursor'], db_ns=db_ns,
        query_class=query_ns['SqlQuery'], hashes=hashes, lines=lines)


def legacy_db(legacy, implementation, adapter):
    ns = legacy.db_ns

    class Legacy(ns['EnvMixin'], ns['ConnectionMixin'], ns['ExecuteMixin'],
                 ns['TransactionMixin']):
        rootstore = '_main_db'
        multidomain = False
        debugger = None
        QUEUE_DEFER_TO_COMMIT = 'to_commit_defer_calls'
        QUEUE_DEFER_AFTER_COMMIT = 'after_commit_defer_calls'

        def __init__(self):
            self.implementation = implementation
            self._currentEnv = {}
            self._connections = {}
            self.adapter = adapter

        def table(self, name):
            return SimpleNamespace(use_dbstores=lambda **kwargs: None)

        def _invoke_deferred_cbs(self, queue):
            pass  # Explicit boundary: callbacks are not part of this oracle.

    return Legacy()


class Backend:
    def __init__(self, legacy, name, schema, dsn=None):
        self.name = name
        self.suffix = 'pg' if name == 'postgresql' else 'sqlite'
        self.schema = schema
        self.legacy = legacy
        if name == 'postgresql':
            cursor_class = legacy.cursor_class

            class Connection(psycopg.Connection):
                pass

            def connect(storename=None):
                conn = Connection.connect(dsn)
                conn.cursor_factory = cursor_class  # as gnrpostgres3.connect
                return conn

            adapter = legacy.pg_adapter()
            adapter.connect = connect
            adapter.cursor = lambda connection: connection.cursor()
        else:
            class Connection(sqlite3.Connection):
                pass

            class RecordingSqliteCursor(sqlite3.Cursor):
                def execute(self, query, params=()):
                    self.sent = (query, dict(params) if isinstance(params, Mapping) else params)
                    return super().execute(query, params)

            adapter = legacy.sqlite_adapter()
            adapter.connect = lambda storename=None: sqlite3.connect(':memory:', factory=Connection)
            adapter.cursor = lambda connection: connection.cursor(RecordingSqliteCursor)
        make_cursor = adapter.cursor

        def cursor(connection):
            self.last_cursor = make_cursor(connection)
            return self.last_cursor

        adapter.cursor = cursor
        self.last_cursor = None
        self.adapter = adapter
        self.db = legacy_db(legacy, 'postgres' if name == 'postgresql' else 'sqlite', adapter)

    def table(self, name):
        # sqlfullname: gnrsqlmodel/table.py:181 with adaptSqlName '"%s"'
        # (_gnrbasepostgresadapter.py:237, gnrsqlite.py:131).
        return f'"{self.schema or "main"}"."{name}"'

    def select_sql(self, table='invoice', alias='t0', **fragments):
        values = dict(columns='', distinct='', joins=[], where=None, group_by=None,
                      having=None, order_by=None, limit=None, offset=None, for_update=False)
        values.update(fragments)
        return self.adapter.compileSql(maintable=self.table(table), maintable_as=alias, **values)

    def query(self, sqltext, sqlparams):
        """An object with the original SqlQuery.cursor/count and a stub compileQuery."""
        query = object.__new__(self.legacy.query_class)
        query.db = self.db
        query.sqlparams = dict(sqlparams)
        query.storename = None
        query.dbtable = SimpleNamespace(dbImplementation=self.db.implementation,
                                        fullname='sales.invoice')
        query.sqltext = sqltext
        query.compileQuery = lambda count=False: SimpleNamespace(get_sqltext=lambda db: sqltext)
        return query


def clean(value, schema):
    if schema is None:
        return value
    if isinstance(value, str):
        return value.replace(schema, '<schema>')
    if isinstance(value, (list, tuple)):
        return [clean(v, schema) for v in value]
    if isinstance(value, dict):
        return {k: clean(v, schema) for k, v in value.items()}
    if isinstance(value, (int, float)) or value is None:
        return value
    return str(value)


def run_entry(backend, spec):
    """Run one entry; ``spec['terminal']`` is fetch, count or execute (direct SQL)."""
    terminal = spec['terminal']
    sqltext = spec['legacy_sql'](backend)
    params = spec.get('params', {})
    entry = {'id': f"legacy_{spec['case']}_{backend.suffix}", 'backend': backend.name,
             'row': spec['row'], 'method': spec['method'], 'source': spec['source']}
    if spec.get('derivation'):
        entry['derivation'] = spec['derivation']
    entry['input'] = spec['input']
    entry['terminal'] = terminal
    entry['legacy_sql'] = sqltext
    backend.last_cursor = None
    entry['params'] = {k: sorted(v) if isinstance(v, set) else
                       list(v) if isinstance(v, tuple) else v for k, v in params.items()}
    try:
        if terminal == 'count':
            entry['result'] = backend.query(sqltext, params).count()
        elif terminal == 'fetch':
            cursor = backend.query(sqltext, params).cursor()
            entry['columns'] = [d[0] for d in cursor.description]
            entry['result'] = cursor.fetchall()
        else:
            cursor = backend.db.execute(sqltext, dict(params))
            entry['columns'] = [d[0] for d in cursor.description]
            entry['result'] = cursor.fetchall()
        entry['status'] = 'returned'
    except Exception as error:
        entry['status'] = 'error'
        entry['error_type'] = type(error).__name__
        entry['error'] = str(error).split('\n', 1)[0]
    finally:
        backend.db.rollback()
    sent_sql, sent_params = getattr(backend.last_cursor, 'sent', (None, None))
    entry['sent_sql'] = sent_sql
    entry['sent_params'] = dict(sent_params) if isinstance(sent_params, Mapping) else sent_params
    return clean(entry, backend.schema)


def collection_entries():
    """IN / NOT IN on a compiled query: where '$x IN :p' + order_by '$id'."""
    derivation = [f'{COMPILER}:990 where chunks wrapped and joined with the logical '
                  f'deletion chunk ({COMPILER}:981)',
                  f'{SRC_PKEY} pkey column appended (no aggregate)',
                  f'{COMPILER}:1011 $col output name; templateReplace renders "t0"."col"']

    def compiled(case, where, params, condition, extra_source=()):
        def legacy_sql(backend):
            return backend.select_sql(columns=ID_COLUMNS, where=where_visible(condition),
                                      order_by='"t0"."id"')
        return dict(case=case, row=None, terminal='fetch', method='derived-from-source',
                    derivation=derivation, legacy_sql=legacy_sql, params=params,
                    input={'columns': '$id', 'where': where, 'params': None, 'order_by': '$id'},
                    source=[SRC_PREPARE, SRC_EXPAND_PG, SRC_EXPAND_SQLITE, *extra_source])

    rows = [
        ('in_list', 'IN list', '$id IN :ids', {'ids': [10, 11]}, '"t0"."id" IN :ids'),
        ('not_in_list', 'NOT IN list', '$id NOT IN :ids', {'ids': [10, 11]},
         '"t0"."id" NOT IN :ids'),
        ('in_tuple', 'IN tuple', '$id IN :ids', {'ids': (10, 11)}, '"t0"."id" IN :ids'),
        ('in_set', 'IN set', '$id IN :ids', {'ids': {10, 11}}, '"t0"."id" IN :ids'),
        ('in_empty', 'IN empty collection', '$id IN :ids', {'ids': []}, '"t0"."id" IN :ids'),
        ('not_in_empty', 'NOT IN empty collection', '$id NOT IN :ids', {'ids': []},
         '"t0"."id" NOT IN :ids'),
        ('in_duplicates', 'IN duplicates', '$id IN :ids', {'ids': [10, 10, 11]},
         '"t0"."id" IN :ids'),
        ('in_none_member', 'IN None member', '$id IN :ids', {'ids': [10, None]},
         '"t0"."id" IN :ids'),
        ('not_in_none_member', 'NOT IN None member', '$id NOT IN :ids', {'ids': [10, None]},
         '"t0"."id" NOT IN :ids'),
        ('in_null_column', 'IN on a NULL column value', '$customer_id IN :ids',
         {'ids': [1, 2]}, '"t0"."customer_id" IN :ids'),
        ('not_in_null_column', 'NOT IN on a NULL column value', '$customer_id NOT IN :ids',
         {'ids': [1]}, '"t0"."customer_id" NOT IN :ids'),
        ('in_scalar_string', 'IN scalar string', '$note IN :notes',
         {'notes': 'First order'}, '"t0"."note" IN :notes'),
        ('same_param_twice', 'same parameter used twice',
         '$id IN :ids OR $customer_id IN :ids', {'ids': [1, 11]},
         '"t0"."id" IN :ids OR "t0"."customer_id" IN :ids'),
        ('same_param_in_and_any', 'same parameter in IN and scalar position',
         '$id IN :ids OR $id = ANY(:ids)', {'ids': [10, 11]},
         '"t0"."id" IN :ids OR "t0"."id" = ANY(:ids)'),
        ('two_collections', 'two collections in one query',
         '$id IN :ids AND $customer_id NOT IN :customers',
         {'ids': [10, 11, 12], 'customers': [2]},
         '"t0"."id" IN :ids AND "t0"."customer_id" NOT IN :customers'),
        ('two_collections_prefix', 'two collections in one query (name prefix)',
         '$id IN :ids AND $customer_id IN :ids2', {'ids': [10, 11, 12], 'ids2': [1]},
         '"t0"."id" IN :ids AND "t0"."customer_id" IN :ids2'),
    ]
    specs = []
    for case, row, where, params, condition in rows:
        spec = compiled(case, where, params, condition)
        spec['row'] = row
        specs.append(spec)
    return specs


def subquery_entries():
    """IN inside a named subquery formula on customer (no logical deletion)."""
    derivation = [f'{COMPILER}:416 subquery alias prefix <alias>_t (t0_t0)',
                  f'{COMPILER}:409 subquery wrapped in " ( %s ) "; {COMPILER}:439 formula '
                  'wrapped in "( %s )"',
                  f'{COMPILER}:1011 output name of COUNT(*) is colToAs -> COUNT___',
                  'sq_pars defaults: excludeLogicalDeleted=False, addPkeyColumn=False '
                  f'({COMPILER}:412-418)',
                  '#THIS correlation written in its resolved form "t0"."id"']

    def legacy_sql(backend):
        inner = backend.select_sql(
            alias='t0_t0', columns='COUNT(*) AS "COUNT___"',
            where='("t0_t0"."customer_id" = "t0"."id" AND "t0_t0"."id" IN :ids)')
        formula = '( %s )' % (' ( %s ) ' % inner)
        return backend.select_sql(
            table='customer',
            columns=f'"t0"."id" AS "id",\n{formula} AS "n_selected",\n"t0"."id" AS "pkey"',
            order_by='"t0"."id"')

    specs = []
    for case, row, ids in [('subquery_in_list', 'IN inside a named subquery', [10, 11, 14]),
                           ('subquery_in_empty', 'IN empty collection inside a named subquery',
                            [])]:
        specs.append(dict(case=case, row=row, terminal='fetch', method='derived-from-source',
                          derivation=derivation, legacy_sql=legacy_sql, params={'ids': ids},
                          input={'table': 'customer', 'columns': '$id, $n_selected',
                                 'formula': "n_selected: select=dict(table='sales.invoice', "
                                            "columns='COUNT(*)', where='$customer_id=#THIS.id "
                                            "AND $id IN :ids')", 'order_by': '$id'},
                          source=[f'{COMPILER}:409', f'{COMPILER}:439', SRC_PREPARE,
                                  SRC_EXPAND_PG, SRC_EXPAND_SQLITE]))
    return specs


def direct_entries():
    """db.execute(sql, params): the same prepareSqlText runs on every SQL text."""
    specs = []
    for case, row, ids in [('direct_in_list', 'IN in direct SQL', [10, 11]),
                           ('direct_in_empty', 'IN empty collection in direct SQL', [])]:
        specs.append(dict(
            case=case, row=row, terminal='execute', method='executed-extracted',
            legacy_sql=lambda b: f'SELECT id FROM {b.table("invoice")} WHERE id IN :ids ORDER BY id',
            params={'ids': ids}, input={'sql': 'SELECT id FROM <invoice> WHERE id IN :ids '
                                               'ORDER BY id'},
            source=[SRC_PREPARE, SRC_EXPAND_PG, f'{PG3}:81', SRC_EXPAND_SQLITE]))
    return specs


def clause_entries():
    """DISTINCT, GROUP BY, HAVING, aggregate projection, interactions."""
    def spec(case, row, input_, fragments, source, derivation, params=None, terminal='fetch'):
        return dict(case=case, row=row, terminal=terminal, method='derived-from-source',
                    derivation=derivation, input=input_, params=params or {},
                    legacy_sql=lambda b: b.select_sql(**fragments), source=source)

    distinct_on = [f'{COMPILER}:899 distinct or \'\'', f'{SRC_AGGREGATE} aggregate = '
                   'bool(distinct or group_by): no pkey column', f'{COMPILER}:1057 DISTINCT']
    distinct_off = [f'{COMPILER}:899 distinct or \'\' -> \'\'', f'{SRC_PKEY} pkey column '
                    'appended', f'{COMPILER}:1058 auto DISTINCT only with exploding (to-many) joins']
    grouped = [f'{SRC_AGGREGATE} aggregate: no pkey column, no table order_by ({COMPILER}:910)',
               f'{COMPILER}:1018 explicit AS kept verbatim (alias not quoted)']
    total_cols = '"t0"."total" AS "total"'
    group_cols = '"t0"."customer_id" AS "customer_id",\nSUM("t0"."total") AS total_sum'
    having = 'SUM("t0"."total") >= :minimum'
    return [
        spec('distinct_true', 'distinct=True',
             {'columns': '$total', 'distinct': True, 'order_by': '$total'},
             dict(columns=total_cols, distinct='DISTINCT ', where=where_visible(),
                  order_by='"t0"."total"'),
             [f'{COMPILER}:899', f'{COMPILER}:1057'], distinct_on),
        spec('distinct_empty', "distinct=''",
             {'columns': '$total', 'distinct': '', 'order_by': '$total'},
             dict(columns=f'{total_cols},\n"t0"."id" AS "pkey"', where=where_visible(),
                  order_by='"t0"."total"'),
             [f'{COMPILER}:899', f'{COMPILER}:1058'], distinct_off),
        spec('distinct_none', 'distinct=None',
             {'columns': '$total', 'distinct': None, 'order_by': '$total'},
             dict(columns=f'{total_cols},\n"t0"."id" AS "pkey"', where=where_visible(),
                  order_by='"t0"."total"'),
             [f'{QUERY}:144', f'{COMPILER}:899', f'{COMPILER}:1058'], distinct_off),
        spec('distinct_order_by_outside_projection', 'DISTINCT with order_by outside the projection',
             {'columns': '$customer_id', 'distinct': True, 'order_by': '$total'},
             dict(columns='"t0"."customer_id" AS "customer_id"', distinct='DISTINCT ',
                  where=where_visible(), order_by='"t0"."total"'),
             [f'{COMPILER}:1057', f'{COMPILER}:1071'],
             distinct_on + [f'{COMPILER}:1071 hidden __ord_col_N added only for auto DISTINCT']),
        spec('group_by', 'GROUP BY',
             {'columns': '$customer_id, SUM($total) AS total_sum', 'group_by': '$customer_id',
              'order_by': '$customer_id'},
             dict(columns=group_cols, where=where_visible(), group_by='"t0"."customer_id"',
                  order_by='"t0"."customer_id"'),
             [SRC_AGGREGATE, f'{COMPILER}:1096'], grouped),
        spec('group_by_star', "group_by='*'",
             {'columns': 'SUM($total) AS total_sum, COUNT(*) AS n', 'group_by': '*'},
             dict(columns='SUM("t0"."total") AS total_sum,\nCOUNT(*) AS n', where=where_visible()),
             [f'{COMPILER}:906', SRC_AGGREGATE],
             grouped + [f'{COMPILER}:906 group_by \'*\' -> None after aggregate is set']),
        spec('having_params', 'HAVING with parameters',
             {'columns': '$customer_id, SUM($total) AS total_sum', 'group_by': '$customer_id',
              'having': 'SUM($total) >= :minimum', 'order_by': '$customer_id'},
             dict(columns=group_cols, where=where_visible(), group_by='"t0"."customer_id"',
                  having=having, order_by='"t0"."customer_id"'),
             [f'{COMPILER}:1097', SRC_PREPARE], grouped, params={'minimum': 40}),
        spec('aggregate_without_group_by', 'aggregate projection without GROUP BY',
             {'columns': 'SUM($total) AS total_sum'},
             dict(columns='SUM("t0"."total") AS total_sum,\n"t0"."id" AS "pkey"',
                  where=where_visible()),
             [SRC_PKEY, f'{COMPILER}:1004'],
             [f'{SRC_AGGREGATE} aggregate is False: no distinct, no group_by',
              f'{SRC_PKEY} pkey column appended before {COMPILER}:1004 detects SUM(']),
        spec('for_update_distinct', 'for_update with DISTINCT',
             {'columns': '$total', 'distinct': True, 'for_update': True},
             dict(columns=total_cols, distinct='DISTINCT ', where=where_visible(),
                  for_update=True),
             [f'{COMPILER}:1101', f'{BASE}:721', f'{SQLITE}:140'],
             distinct_on + [f'{BASE}:721 FOR UPDATE OF t0; {SQLITE}:140 renders nothing']),
        spec('for_update_group_by', 'for_update with GROUP BY',
             {'columns': '$customer_id, SUM($total) AS total_sum', 'group_by': '$customer_id',
              'for_update': True},
             dict(columns=group_cols, where=where_visible(), group_by='"t0"."customer_id"',
                  for_update=True),
             [f'{COMPILER}:1101', f'{BASE}:721', f'{SQLITE}:140'], grouped),
        spec('mark_aggregate', "exclude_logical_deleted='mark' with GROUP BY",
             {'columns': '$customer_id, SUM($total) AS total_sum', 'group_by': '$customer_id',
              'excludeLogicalDeleted': 'mark', 'order_by': '$customer_id'},
             dict(columns=group_cols, group_by='"t0"."customer_id"',
                  order_by='"t0"."customer_id"'),
             [f'{COMPILER}:981', f'{COMPILER}:983'],
             grouped + [f'{COMPILER}:981 no IS NULL chunk unless excludeLogicalDeleted is True',
                        f'{COMPILER}:983 _isdeleted column skipped when aggregate or count']),
    ]


def count_entries():
    """SqlQuery.count (query.py:557) on the compileQuery(count=True) fragments."""
    count_cols = 'count(*) AS "gnr_row_count"'
    plain = [f'{COMPILER}:940 count mode: order_by dropped',
             f'{COMPILER}:946 columns = count(*) AS "gnr_row_count"',
             f'{COMPILER}:1099 limit/offset kept in count mode',
             f'{QUERY}:587 one gnr_row_count row -> its value, otherwise len(fetchall())']
    distinct = [f'{COMPILER}:943 count with distinct keeps the projection',
                f'{QUERY}:585 count = len(fetchall())']
    grouped = [f'{COMPILER}:942 count with group_by projects the group_by columns',
               f'{QUERY}:585 count = number of groups fetched']

    def spec(case, row, input_, fragments, derivation, params=None):
        return dict(case=case, row=row, terminal='count', method='derived-from-source',
                    derivation=derivation, input=input_, params=params or {},
                    legacy_sql=lambda b: b.select_sql(**fragments),
                    source=[f'{QUERY}:557', f'{COMPILER}:939'])

    group_fragments = dict(columns='"t0"."customer_id" AS "customer_id"',
                           where=where_visible(), group_by='"t0"."customer_id"',
                           having='SUM("t0"."total") >= :minimum')
    return [
        spec('count_plain', 'count: plain query', {'columns': '*'},
             dict(columns=count_cols, where=where_visible()), plain),
        spec('count_ordered', 'count: order_by', {'columns': '*', 'order_by': '$total'},
             dict(columns=count_cols, where=where_visible()), plain),
        spec('count_distinct', 'count: DISTINCT query', {'columns': '$total', 'distinct': True},
             dict(columns='"t0"."total" AS "total"', distinct='DISTINCT ',
                  where=where_visible()), distinct),
        spec('count_grouped_having', 'count: grouped query with HAVING',
             {'columns': '$customer_id, SUM($total) AS total_sum', 'group_by': '$customer_id',
              'having': 'SUM($total) >= :minimum'},
             group_fragments, grouped, params={'minimum': 40}),
        spec('count_limit', 'count: limit', {'columns': '*', 'limit': 2},
             dict(columns=count_cols, where=where_visible(), limit=2), plain),
        spec('count_limit_offset', 'count: limit and offset',
             {'columns': '*', 'limit': 2, 'offset': 2},
             dict(columns=count_cols, where=where_visible(), limit=2, offset=2), plain),
        spec('count_distinct_limit_offset', 'count: DISTINCT with limit and offset',
             {'columns': '$total', 'distinct': True, 'limit': 2, 'offset': 1},
             dict(columns='"t0"."total" AS "total"', distinct='DISTINCT ',
                  where=where_visible(), limit=2, offset=1), distinct),
        spec('count_grouped_limit', 'count: grouped query with limit',
             {'columns': '$customer_id, SUM($total) AS total_sum', 'group_by': '$customer_id',
              'having': 'SUM($total) >= :minimum', 'limit': 2},
             dict(group_fragments, limit=2), grouped, params={'minimum': 40}),
        spec('count_empty', 'count: empty dataset', {'columns': '*', 'where': '$id < 0'},
             dict(columns=count_cols, where=where_visible('"t0"."id" < 0')), plain),
        spec('count_grouped_empty', 'count: grouped query on an empty dataset',
             {'columns': '$customer_id', 'group_by': '$customer_id', 'where': '$id < 0'},
             dict(columns='"t0"."customer_id" AS "customer_id"',
                  where=where_visible('"t0"."id" < 0'), group_by='"t0"."customer_id"'), grouped),
        spec('count_mark', "count with exclude_logical_deleted='mark'",
             {'columns': '*', 'excludeLogicalDeleted': 'mark'},
             dict(columns=count_cols), plain + [f'{COMPILER}:981 no IS NULL chunk in mark mode']),
    ]


def seed_postgres(observer, schema):
    observer.execute(f'CREATE SCHEMA "{schema}"')
    for ddl in PG_DDL:
        observer.execute(ddl.format(schema=schema))
    with observer.cursor() as cur:
        cur.executemany(f'INSERT INTO "{schema}".customer VALUES (%s, %s)', CUSTOMERS)
        cur.executemany(f'INSERT INTO "{schema}".invoice VALUES (%s, %s, %s, %s, %s)', INVOICES)


def seed_sqlite(db):
    conn = db.connection
    for ddl in SQLITE_DDL:
        conn.execute(ddl)
    conn.executemany('INSERT INTO customer VALUES (?, ?)', CUSTOMERS)
    conn.executemany('INSERT INTO invoice VALUES (?, ?, ?, ?, ?)',
                     [(i, c, float(t), n, d) for i, c, t, n, d in INVOICES])
    conn.commit()


def main():
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('legacy_root', type=Path)
    parser.add_argument('--dsn', required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    check_legacy(args.legacy_root)
    legacy = load_legacy(args.legacy_root)
    specs = collection_entries() + subquery_entries() + direct_entries() + clause_entries() \
        + count_entries()
    entries = []
    schema = 'query_legacy_' + uuid4().hex
    with psycopg.connect(args.dsn, autocommit=True) as observer:
        seed_postgres(observer, schema)
        server_version = observer.execute('SHOW server_version').fetchone()[0]
        try:
            pg = Backend(legacy, 'postgresql', schema, dsn=args.dsn)
            try:
                entries += [run_entry(pg, spec) for spec in specs]
            finally:
                pg.db.closeConnection()
        finally:
            observer.execute(f'DROP SCHEMA "{schema}" CASCADE')
    lite = Backend(legacy, 'sqlite', None)
    seed_sqlite(lite.db)
    try:
        entries += [run_entry(lite, spec) for spec in specs]
    finally:
        lite.db.closeConnection()
    ids = [e['id'] for e in entries]
    assert len(ids) == len(set(ids)), 'entry ids must be unique'
    result = {
        'generated_by': 'docs/design/evidence/query_legacy_oracle.py',
        'legacy': {'revision': LEGACY_REVISION, 'source_sha256': dict(sorted(legacy.hashes.items())),
                   'extracted': legacy.lines},
        'environment': {'psycopg': psycopg.__version__, 'postgresql': server_version,
                        'sqlite': sqlite3.sqlite_version},
        'dataset': {'customer': [list(r) for r in CUSTOMERS],
                    'invoice': [list(r) for r in INVOICES],
                    'columns': {'customer': ['id', 'name'],
                                'invoice': ['id', 'customer_id', 'total', 'note', '__del_ts']}},
        'entries': entries,
    }
    args.output.write_text(json.dumps(result, indent=2, default=str) + '\n')
    print(f'Legacy query oracle: {len(entries)} entries; schema removed.')


if __name__ == '__main__':
    main()
