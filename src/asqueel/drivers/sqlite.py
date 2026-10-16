"""SQLite stdlib driver. Every connection uses explicit transaction boundaries."""
from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
import re
import sqlite3

from ..contracts import CompiledQuery, QueryResult
from .result import query_result


class SqliteDriver:
    dialect = 'sqlite'
    binding = 'sqlite_named'

    def prepare_sql(self, sql, sqlargs, snapshot):
        from .sql import prepare_text
        return prepare_text(self, sql, sqlargs, snapshot)


    def validate(self, query):
        if not isinstance(query, CompiledQuery):
            raise TypeError('execute requires a CompiledQuery')
        if (query.dialect, query.binding) != (self.dialect, self.binding):
            raise ValueError('Query profile does not match sqlite/sqlite_named')

    def connect(self, conninfo='', *, dbname=None, schemas=(), **kwargs):
        if sqlite3.sqlite_version_info < (3, 35, 0):
            raise RuntimeError('SQLite 3.35 or later is required for RETURNING')
        if conninfo and dbname:
            raise ValueError('Supply a SQLite filename once')
        name = dbname or conninfo
        if not name:
            raise ValueError('SQLite requires a database filename or :memory:')
        allowed = {'timeout', 'cached_statements'}
        if set(kwargs) - allowed:
            raise ValueError(f'Unsupported SQLite options: {sorted(set(kwargs) - allowed)}')
        connection = sqlite3.connect(name, isolation_level=None, **kwargs)
        try:
            # gnrsqlite registers this function for its ~* -> REGEXP translation.
            connection.create_function('regexp', 2, self._regexp)
            connection.execute('PRAGMA foreign_keys = ON')
            for schema in schemas:
                if schema == 'main':
                    continue
                if not isinstance(schema, str) or not re.fullmatch(r'[A-Za-z_][A-Za-z0-9_]*', schema) or schema == 'temp':
                    raise ValueError('SQLite attached schema names must be simple identifiers other than temp')
                # Same file layout as asqueel_migration.SqliteDatabase.schema_files().
                path = ':memory:' if name == ':memory:' else str(Path(name).with_name(f'{Path(name).stem}_{schema}.db'))
                connection.execute(f'ATTACH DATABASE ? AS "{schema}"', (path,))
        except BaseException:
            connection.close()
            raise
        return connection

    @staticmethod
    def _regexp(expression, item):
        return re.compile(expression, re.U).match(item) is not None

    def execute(self, connection, query):
        self.validate(query)
        if not connection.in_transaction:
            connection.execute('BEGIN IMMEDIATE')
        elif query.for_update:
            if not query.lock_table or not query.lock_column:
                raise ValueError('A locked SQLite query requires a physical table and column')
            # Acquire the write reservation without changing rows or ending the transaction.
            connection.execute(f'UPDATE {query.lock_table} SET {query.lock_column}={query.lock_column} WHERE 0')
        params = {name: self._value(value) for name, value in query.params.items()}
        cursor = connection.execute(query.sql, params)
        try:
            names = [column[0] for column in cursor.description] if cursor.description is not None else None
            return query_result(query.columns, names, cursor)
        finally:
            cursor.close()

    def executemany(self, connection, query, params_seq):
        """One statement, one parameter mapping per execution; no result rows."""
        self.validate(query)
        if not connection.in_transaction:
            connection.execute('BEGIN IMMEDIATE')
        rows = [{name: self._value(value) for name, value in params.items()} for params in params_seq]
        cursor = connection.executemany(query.sql, rows)
        try:
            return QueryResult([], cursor.rowcount, ())
        finally:
            cursor.close()

    @staticmethod
    def _value(value):
        if isinstance(value, (date, datetime)):
            return value.isoformat()
        if isinstance(value, Decimal):
            return str(value)
        return value

    def commit(self, connection):
        connection.commit()

    def rollback(self, connection):
        connection.rollback()

    def close(self, connection):
        connection.close()
