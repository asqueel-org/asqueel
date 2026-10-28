"""Cached fetch: a query materialized server side by ``owner:name`` and read by pages.

The result tables live in schema ``_asql_`` and are recorded in the catalog
table ``_asql_cached_fetch``; both exist when the model declares the db-level
option ``cachedFetch``. Every write runs on the separate session
``_asql_cached_fetch`` and is committed there: the caller's session is never
committed.
"""
from __future__ import annotations

import hashlib
import re
from dataclasses import replace
from datetime import datetime, timezone

from .common import split_names
from .contracts import UnsupportedFeatureError
from .environment import environment_arguments
from .errors import TransactionStateError

SCHEMA = '_asql_'
CATALOG = '_asql_._asql_cached_fetch'
SESSION = '_asql_cached_fetch'
_MAX_NAME_BYTES = 63
_NEGATED_OWNERS = re.compile(r'^\s*!\s*\((?P<owners>.*)\)\s*$')


def split_destination(destination_name):
    """``(owner, name)`` of ``'owner:name'``, split at the first ``:``."""
    if not isinstance(destination_name, str) or ':' not in destination_name:
        raise ValueError(f"destination_name must be 'owner:name', not {destination_name!r}")
    owner, name = destination_name.split(':', 1)
    if not owner or not name:
        raise ValueError(f"destination_name {destination_name!r} needs an owner and a name")
    if any(char in owner for char in ',()') or owner.startswith('!') or owner != owner.strip():
        raise ValueError(f"destination_name {destination_name!r}: an owner may not contain ',', '(', ')', "
                         "start with '!' nor start or end with a space")
    return owner, name


def _safe(text):
    return ''.join(char if char.isalnum() or char == '_' else '_' for char in text)


def physical_name(prefix, owner, name):
    """``<prefix><owner>_<name>``; beyond 63 bytes the name becomes the first 12 hex of its SHA-256.

    When the owner part alone is too long it is cut, by bytes, never the digest.
    """
    safe = _safe(f'{prefix}{owner}_{name}')
    if len(safe.encode('utf-8')) <= _MAX_NAME_BYTES:
        return safe
    digest = hashlib.sha256(name.encode('utf-8')).hexdigest()[:12]
    head = _safe(f'{prefix}{owner}_').encode('utf-8')[:_MAX_NAME_BYTES - len(digest)]
    return head.decode('utf-8', 'ignore') + digest


def check_enabled(db):
    """Raise unless the model declares ``cachedFetch`` and the backend supports it."""
    if 'cached_fetch' not in db.adapter.capabilities:
        raise UnsupportedFeatureError(f'{db.adapter.dialect}: cached fetch is not available')
    if db.model.table(CATALOG) is None:
        raise UnsupportedFeatureError('cached fetch needs the db-level option cachedFetch()')


def _catalog_row(db, key):
    rows = db.table(CATALOG).query(where='$id = :key', key=key).fetch()
    return dict(rows[0]) if rows else None


def _locked_row(session, key):
    """The catalog row of ``key``, read under the lock that serializes the writers of ``key``.

    On SQLite the locked read begins the transaction (``BEGIN IMMEDIATE``), so
    the DDL that follows joins it.
    """
    lock = session.adapter.cached_fetch_lock()
    if lock is not None:
        session.execute(lock, {'key': key}).close()
    rows = session.table(CATALOG).query(where='$id = :key', key=key, for_update=True).fetch()
    return dict(rows[0]) if rows else None


def _columns(session, sqltable):
    """``[(name, is_text)]`` of a cached table, as the database reports them."""
    cursor = session.execute(session.adapter.table_columns_sql(), {'schema': SCHEMA, 'table': sqltable})
    rows = cursor.fetchall()
    cursor.close()
    return [(row[0], bool(row[1])) for row in rows]


def _separate_session(db):
    """The separate session on the target of ``db``; reads use it too, closed after each one.

    On PostgreSQL a read in the caller's open transaction would keep a lock
    on the cached table that a later replacement in the same call waits for.
    The shared AsqueelDb has no ``currentEnv`` of a call, and an open session
    of that name would be committed and closed by the cached fetch: both raise.
    """
    if db is db.shared:
        raise TransactionStateError('The shared AsqueelDb holds no connection; use db.session()')
    current = db.shared._current_session.get()
    if current is not None and not current._closed:
        found = current._call_sessions.get(SESSION)
        if found is not None and not found._closed:
            raise TransactionStateError(f'session {SESSION!r} is reserved to the cached fetch')
    return db.session(SESSION, target=db._target)


def _qualified(db, table):
    return f'{db.adapter.adaptSqlName(SCHEMA)}.{db.adapter.adaptSqlName(table)}'


def _drop(session, *tables):
    for table in tables:
        session.execute(f'DROP TABLE IF EXISTS {_qualified(session, table)}').close()


def create(db, tablename, compiled, owner, name):
    """Materialize ``compiled`` (a numbered SELECT on ``tablename``) as ``owner:name``; return its row count.

    An existing ``owner:name`` is replaced; a concurrent writer of the same
    key waits for it. The work runs on the separate session, on the target
    of ``db``, and is committed there.
    """
    key = f'{owner}:{name}'
    sqltable = physical_name('p', owner, name)
    adapter = db.adapter
    params = {**compiled.params, **environment_arguments(compiled.environment_keys, db.environment_snapshot())}
    ctas = replace(compiled, sql=adapter.create_table_as(SCHEMA, sqltable, compiled.sql),
                   params=params, environment_keys=(), columns=(), evaluateBagColumns=())
    index = adapter.create_unique_index(SCHEMA, sqltable, '_rowidx')
    user = db.currentUser
    with _separate_session(db) as session:
        _locked_row(session, key)
        catalog = session.table(CATALOG)
        taken = catalog.query(columns='$id', where='$sqltable = :sqltable AND $id <> :key',
                              sqltable=sqltable, key=key).fetch()
        if taken:
            raise ValueError(f'cached fetch {key!r}: table {sqltable!r} already belongs to {taken[0]["id"]!r}')
        catalog.sql_delete({'id': key})
        # The computed names, not the catalog's: a table left without its row is replaced too.
        _drop(session, sqltable, physical_name('s', owner, name))
        session.execute(ctas).close()
        session.execute(index).close()
        cursor = session.execute(f'SELECT count(*) FROM {_qualified(session, sqltable)}')
        rowcount = cursor.fetchall()[0][0]
        cursor.close()
        catalog.sql_insert({
            'id': key, 'owner': owner, 'name': name, 'tablename': tablename, 'sqlschema': SCHEMA,
            'sqltable': sqltable, 'rowcount': rowcount, 'created': datetime.now(timezone.utc),
            'user': None if user is None else str(user),
        })
        session.commit()
    return rowcount


def cleanup(db, owner):
    """Drop the cached fetches of ``owner`` (or of every other owner, ``'!(...)'``): tables and catalog rows.

    Only the rows read under lock are deleted, so a fetch created meanwhile
    keeps its table and its row. The work runs on the separate session, on
    the target of ``db``, and is committed there.
    """
    if not isinstance(owner, str):
        raise ValueError(f"owner must be 'foo,bar' or '!(foo,bar)', not {owner!r}")
    match = _NEGATED_OWNERS.match(owner)
    text = match.group('owners') if match else owner
    owners = split_names(text)
    if not owners or any(char in text for char in '!()'):
        raise ValueError(f"owner must be 'foo,bar' or '!(foo,bar)', not {owner!r}")
    check_enabled(db)
    where = '$owner NOT IN :owners' if match else '$owner IN :owners'
    with _separate_session(db) as session:
        catalog = session.table(CATALOG)
        rows = catalog.query(columns='$id, $sqltable, $sort_sqltable', where=where, owners=owners,
                             for_update=True).fetch()
        if rows:
            catalog.query(where='$id IN :ids', ids=[row['id'] for row in rows]).sql_delete()
            _drop(session, *(table for row in rows for table in (row['sqltable'], row['sort_sqltable']) if table))
        session.commit()


class CachedFetch:
    """A cached fetch of a table, read by ``owner:name``; ``table.cached(...)`` builds it."""

    def __init__(self, table, destination_name):
        owner, name = split_destination(destination_name)
        self.table = table
        self.db = table.db
        check_enabled(self.db)
        self.key = f'{owner}:{name}'
        with _separate_session(self.db) as session:
            row = _catalog_row(session, self.key)
            if row is None:
                raise ValueError(f'cached fetch {self.key!r} does not exist')
            self.columns = _columns(session, row['sqltable'])
        if row['tablename'] != table.fullname:
            raise ValueError(f'cached fetch {self.key!r} was created from {row["tablename"]}, not {table.fullname}')
        self.row = row

    def sort(self, order_by):
        """Order the pages by ``order_by`` (plain SQL over the result columns), ties by ``_rowidx``.

        The sort table ``(_sortidx, _rowidx)`` replaces the previous one;
        ``sort(None)`` drops it and restores the original order, keeping the
        active search. The result table is never touched. The work runs on
        the separate session and is committed there.
        """
        if order_by is not None and (not isinstance(order_by, str) or not order_by.strip()):
            raise ValueError(f'sort needs SQL text, not {order_by!r}; sort(None) drops the sort')
        self._rebuild(sort_order_by=order_by)

    def search(self, seed):
        """Keep only the rows whose text columns hold every token of ``seed``; return the new total.

        The match is case-insensitive and ``%`` and ``_`` are literal. The
        active sort is kept; ``search(None)`` clears the filter and returns
        the unfiltered total.
        """
        if seed is not None and (not isinstance(seed, str) or not seed.split()):
            raise ValueError(f'a search seed needs at least one token, not {seed!r}; search(None) clears the search')
        return self._rebuild(search_seed=seed)

    def _search_clause(self, session, seed):
        """``(where, params)`` matching every token of ``seed`` on the text columns joined by a space."""
        columns = [name for name, is_text in self.columns if is_text]
        if not columns:
            raise ValueError(f'cached fetch {self.key!r} has no text column to search')
        adapter = session.adapter
        text = " || ' ' || ".join(f"COALESCE({adapter.adaptSqlName(column)}, '')" for column in columns)
        conditions, params = [], {}
        for position, token in enumerate(seed.split()):
            escaped = token.replace('\\', '\\\\').replace('%', '\\%').replace('_', '\\_')
            conditions.append(f"{text} ILIKE :__search_{position} ESCAPE '\\'")
            params[f'__search_{position}'] = f'%{escaped}%'
        return ' AND '.join(conditions), params

    def _rebuild(self, **change):
        """Apply ``change`` (sort and seed) to the current catalog row and rebuild its sort table; return the total.

        The sort table is dropped when neither a sort nor a seed is left.
        """
        owner, name = split_destination(self.key)
        sort_sqltable = physical_name('s', owner, name)
        adapter = self.db.adapter
        with _separate_session(self.db) as session:
            row = _locked_row(session, self.key)
            if row is None:
                raise ValueError(f'cached fetch {self.key!r} does not exist')
            row.update(change)
            order_by, seed = row['sort_order_by'], row['search_seed']
            row['sort_sqltable'] = sort_sqltable if order_by is not None or seed is not None else None
            self.columns = _columns(session, row['sqltable'])
            session.table(CATALOG).sql_update({'id': self.key, 'sort_sqltable': row['sort_sqltable'],
                                               'sort_order_by': order_by, 'search_seed': seed})
            _drop(session, sort_sqltable)
            total = row['rowcount']
            if row['sort_sqltable']:
                ordering = f'{order_by}, _rowidx' if order_by is not None else '_rowidx'
                select = (f'SELECT _rowidx, row_number() OVER (ORDER BY {ordering}) - 1 AS _sortidx '
                          f'FROM {_qualified(session, row["sqltable"])}')
                params = {}
                if seed is not None:
                    where, params = self._search_clause(session, seed)
                    select += f' WHERE {where}'
                session.execute(adapter.create_table_as(SCHEMA, sort_sqltable, select), params).close()
                session.execute(adapter.create_unique_index(SCHEMA, sort_sqltable, '_sortidx')).close()
                if seed is not None:
                    cursor = session.execute(f'SELECT count(*) FROM {_qualified(session, sort_sqltable)}')
                    total = cursor.fetchall()[0][0]
                    cursor.close()
            session.commit()
        self.row = row
        return total

    def query(self, columns='*', where=None, order_by=None, start=0, count=None, sqlparams=None, **bindings):
        """A page of the cached rows: ``count`` rows at most from ``start``, zero-based.

        ``columns``, ``where`` and ``order_by`` are plain SQL over the result
        columns; ``*`` is the result columns only. Without ``where`` and
        ``order_by`` the page is a range of the current numbering
        (``_rowidx``, or ``_sortidx`` when sorted); otherwise it is
        ``ORDER BY ... LIMIT ... OFFSET``.
        """
        for refused in ('limit', 'offset'):
            if refused in bindings:
                raise UnsupportedFeatureError(f'{refused}= is not available on a cached query; use start= and count=')
        if type(start) is not int or start < 0:
            raise ValueError('start must be a nonnegative integer')
        if count is not None and (type(count) is not int or count < 1):
            raise ValueError('count must be a positive integer')
        adapter = self.db.adapter
        params = {**(sqlparams or {}), **bindings}
        view = _qualified(self.db, self.row['sqltable'])
        index = '_rowidx'
        if self.row['sort_sqltable']:
            sort = _qualified(self.db, self.row['sort_sqltable'])
            view = f'(SELECT r.*, s._sortidx FROM {view} AS r JOIN {sort} AS s ON s._rowidx = r._rowidx)'
            index = '_sortidx'
            if columns.strip() == '*':
                columns = ', '.join(adapter.adaptSqlName(name) for name, _ in self.columns)
        if where is None and order_by is None:
            where = f'{index} >= :__cached_start'
            params['__cached_start'] = start
            if count is not None:
                where += f' AND {index} < :__cached_end'
                params['__cached_end'] = start + count
            sql = adapter.compileSql(view, columns, where=where, order_by=index, maintable_as='v')
        else:
            sql = adapter.compileSql(view, columns, where=where, order_by=order_by or index,
                                     limit=count, offset=start, maintable_as='v')
        return CachedQuery(self, sql, params)


class CachedQuery:
    """One page query over a cached fetch; ``fetch()`` executes it again at every call."""

    def __init__(self, cached, sqltext, sqlparams):
        self.cached = cached
        self.sqltext = sqltext
        self.sqlparams = sqlparams

    def fetch(self):
        """The rows of the page; a cached fetch removed or replaced meanwhile raises a clear error."""
        db = self.cached.db
        try:
            with _separate_session(db) as session:
                cursor = session.execute(self.sqltext, self.sqlparams)
                rows = cursor.fetchall()
                cursor.close()
        except Exception as error:
            with _separate_session(db) as session:
                row = _catalog_row(session, self.cached.key)
            if row is None or row['created'] != self.cached.row['created']:
                raise ValueError(f'cached fetch {self.cached.key!r} was removed or replaced; '
                                 'call cached() again') from error
            raise
        return rows
