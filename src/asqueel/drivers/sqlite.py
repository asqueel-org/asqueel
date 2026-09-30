"""SQLite stdlib driver. Every connection uses explicit transaction boundaries."""
from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
import re
import sqlite3

from ..contracts import CompiledQuery, QueryResult, ResultColumn
from ..query_plan import Parameter, SqlStatement


class SqliteDriver:
    dialect = 'sqlite'
    binding = 'sqlite_named'

    def prepare_sql(self, sql, sqlargs, snapshot):
        from .sql import prepare_text
        return prepare_text(self, sql, sqlargs, snapshot)

    def prepare(self, statement):
        if not isinstance(statement, SqlStatement):
            raise TypeError('prepare requires a SqlStatement')
        if statement.dialect != self.dialect:
            raise ValueError(f'Unsupported SQL dialect: {statement.dialect!r}')
        parts, params = [], {}
        for part in statement.parts:
            if isinstance(part, str):
                parts.append(part)
            elif isinstance(part, Parameter):
                if not isinstance(part.name, str) or not re.fullmatch(r'[A-Za-z_][A-Za-z0-9_]*', part.name):
                    raise ValueError('Invalid parameter name')
                if part.name not in statement.params:
                    raise ValueError(f'Missing parameter: {part.name}')
                parts.append(':' + part.name)
                params[part.name] = statement.params[part.name]
            else:
                raise TypeError('Unsupported SQL statement part')
        return CompiledQuery(''.join(parts), params, statement.columns,
                             dialect=self.dialect, binding=self.binding,
                             environment=statement.environment)

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

    def execute(self, connection, query):
        self.validate(query)
        if not connection.in_transaction:
            connection.execute('BEGIN IMMEDIATE')
        params = {name: self._value(value) for name, value in query.params.items()}
        cursor = connection.execute(query.sql, params)
        try:
            columns, rows = query.columns, []
            if cursor.description is not None:
                names = [column[0] for column in cursor.description]
                if len(set(names)) != len(names):
                    raise ValueError('Result columns must have unique names; use explicit aliases')
                if columns and [column.name for column in columns] != names:
                    raise ValueError('Compiled result columns do not match cursor column names and order')
                rows = [dict(zip(names, row, strict=True)) for row in cursor.fetchall()]
                if not columns:
                    columns = tuple(ResultColumn(name) for name in names)
            elif columns:
                raise ValueError('Compiled result columns supplied for a statement without a result set')
            return QueryResult(rows, cursor.rowcount, columns)
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
