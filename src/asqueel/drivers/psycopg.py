"""PostgreSQL binding and synchronous execution using optional psycopg 3.

Formatting and profile checks are offline: the external driver is imported
only when connecting or executing. Raw CompiledQuery SQL is never rewritten.
"""
from __future__ import annotations

import re
from typing import Any

from ..contracts import CompiledQuery, QueryResult
from ..query_plan import Parameter, SqlStatement
from .result import query_result


_PARAMETER_NAME = re.compile(r'[A-Za-z_][A-Za-z0-9_]*\Z')


class PsycopgDriver:
    """Driver profile for PostgreSQL and psycopg named parameter bindings."""

    dialect = 'postgresql'
    binding = 'psycopg_named'

    def prepare_sql(self, sql, sqlargs, snapshot):
        from .sql import prepare_text
        return prepare_text(self, sql, sqlargs, snapshot)

    def prepare(self, statement: SqlStatement) -> CompiledQuery:
        if not isinstance(statement, SqlStatement):
            raise TypeError('prepare requires a SqlStatement')
        if statement.dialect != self.dialect:
            raise ValueError(f'Unsupported SQL dialect: {statement.dialect!r}')
        text = []
        params: dict[str, Any] = {}
        for part in statement.parts:
            if isinstance(part, str):
                text.append(part.replace('%', '%%'))
            elif isinstance(part, Parameter):
                if not isinstance(part.name, str) or not _PARAMETER_NAME.fullmatch(part.name):
                    raise ValueError(f'Invalid parameter name: {part.name!r}')
                if part.name not in statement.params:
                    raise ValueError(f'Missing parameter: {part.name}')
                text.append(f'%({part.name})s')
                params[part.name] = statement.params[part.name]
            else:
                raise TypeError(f'Unsupported SQL statement part: {type(part).__name__}')
        return CompiledQuery(''.join(text), params, statement.columns,
                             dialect=self.dialect, binding=self.binding,
                             environment=statement.environment)

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

    def commit(self, connection: Any) -> None:
        connection.commit()

    def rollback(self, connection: Any) -> None:
        connection.rollback()

    def close(self, connection: Any) -> None:
        connection.close()
