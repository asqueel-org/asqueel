"""PostgreSQL binding and synchronous execution using optional psycopg 3.

Formatting and profile checks are offline: the external driver is imported
only when connecting or executing. Raw CompiledQuery SQL is never rewritten.
"""
from __future__ import annotations

import re
from typing import Any

from ..contracts import CompiledQuery, QueryResult
from .result import query_result


_PARAMETER_NAME = re.compile(r'[A-Za-z_][A-Za-z0-9_]*\Z')


class PsycopgDriver:
    """Driver profile for PostgreSQL and psycopg named parameter bindings."""

    dialect = 'postgresql'
    binding = 'psycopg_named'

    def prepare_sql(self, sql, sqlargs, snapshot):
        from .sql import prepare_text
        return prepare_text(self, sql, sqlargs, snapshot)


    def validate(self, query: CompiledQuery) -> None:
        if not isinstance(query, CompiledQuery):
            raise TypeError('execute requires a CompiledQuery')
        if (query.dialect, query.binding) != (self.dialect, self.binding):
            raise ValueError(
                f'Query profile {query.dialect}/{query.binding} does not match '
                f'driver profile {self.dialect}/{self.binding}')

    def connect(self, conninfo: str, **kwargs: Any) -> Any:
        import psycopg

        if kwargs.get('autocommit'):
            raise ValueError('autocommit is incompatible with explicit transactions')
        return psycopg.connect(conninfo, **kwargs)

    def execute(self, connection: Any, query: CompiledQuery) -> QueryResult:
        self.validate(query)
        from psycopg.rows import tuple_row

        with connection.cursor(row_factory=tuple_row) as cursor:
            cursor.execute(query.sql, dict(query.params))
            names = [column.name for column in cursor.description] if cursor.description is not None else None
            return query_result(query.columns, names, cursor)

    def executemany(self, connection: Any, query: CompiledQuery, params_seq: Any) -> QueryResult:
        """One statement, one parameter mapping per execution; no result rows."""
        self.validate(query)
        with connection.cursor() as cursor:
            cursor.executemany(query.sql, [dict(params) for params in params_seq])
            return QueryResult([], cursor.rowcount, ())

    def commit(self, connection: Any) -> None:
        connection.commit()

    def rollback(self, connection: Any) -> None:
        connection.rollback()

    def close(self, connection: Any) -> None:
        connection.close()
