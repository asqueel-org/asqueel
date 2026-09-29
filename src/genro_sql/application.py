"""Application database: one configuration, model, live graph and session."""
from __future__ import annotations

from contextlib import contextmanager
from types import MappingProxyType
from typing import Any

from .application_table import SqlTable
from .compiler import QueryCompiler
from .contracts import CompiledQuery, QueryResult, ResolvedModel, UnsupportedFeatureError
from .dialects.postgres import PostgresDialect
from .drivers.psycopg import PsycopgDriver
from .environment import SqlEnvironment
from .runtime import TransactionStateError
from .session import Session


class SqlDatabase:
    """A synchronous application database constructed from a configuration.

    Use ``build_database(recipe)`` or a configuration's object renderer to
    construct this class. Table operations share a lazy session until explicit
    commit/rollback. Closing rolls back pending work; it never commits it.
    """

    def __init__(self, *, model: ResolvedModel, config, driver=None, dialect=None,
                 environment: SqlEnvironment | None = None):
        self._ready = False
        self._write_depth = 0
        self.config = config
        self.model = model
        implementation = config('implementation', default='postgresql')
        if implementation != 'postgresql':
            raise UnsupportedFeatureError(f'Unsupported database implementation: {implementation!r}')
        self.driver = driver if driver is not None else PsycopgDriver()
        self.dialect = dialect if dialect is not None else PostgresDialect()
        if self.dialect.name != implementation:
            raise ValueError('Configured implementation does not match the data dialect')
        self.environment = environment if environment is not None else SqlEnvironment()
        self.compiler = QueryCompiler(model, self.dialect, self.driver, environment=self.environment)
        self._session = Session(
            driver=self.driver,
            conninfo=config('conninfo', default=''),
            connect_kwargs=config('connect_kwargs', default=None),
            environment=self.environment,
        )
        self._tables: dict[str, SqlTable] = {}
        for descriptor in model.tables.values():
            table_class = descriptor.attributes.get('x_table_class', SqlTable)
            if not isinstance(table_class, type) or not issubclass(table_class, SqlTable):
                raise TypeError(f'{descriptor.key}: x_table_class must be a SqlTable subclass')
            self._tables[descriptor.key] = table_class(self, descriptor)
        self._ready = True

    def _check_open(self) -> None:
        if not self._ready:
            raise TransactionStateError('Database object graph is not ready')
        self._session._check_open()

    @property
    def tables(self):
        self._check_open()
        return MappingProxyType(self._tables)

    def table(self, name: str) -> SqlTable:
        """Return the registered operational table, preserving object identity."""
        self._check_open()
        return self._tables[self.model.table(name).key]

    @property
    def current_env(self):
        self._check_open()
        return self.environment.current_env

    @property
    def currentEnv(self):
        return self.current_env

    def temp_env(self, **values: Any):
        self._check_open()
        return self.environment.temp_env(**values)

    def tempEnv(self, **values: Any):
        return self.temp_env(**values)

    @property
    def outcome(self) -> str:
        """Most recent session transaction outcome, including uncertain commit."""
        return self._session.outcome

    def execute(self, query: CompiledQuery) -> QueryResult:
        """Execute a compiled statement in this DB's shared unit of work."""
        self._check_open()
        return self._session.execute(query)

    def _check_boundary(self) -> None:
        self._check_open()
        if self._write_depth:
            raise TransactionStateError('Cannot finish a transaction inside a table write or hook')

    def commit(self) -> None:
        self._check_boundary()
        self._session.commit()

    def rollback(self) -> None:
        self._check_boundary()
        self._session.rollback()

    @contextmanager
    def transaction(self):
        """Group table operations atomically; enter with no pending transaction."""
        self._check_boundary()
        with self._session.transaction():
            yield self

    @contextmanager
    def _write_operation(self):
        self._check_open()
        self._session._check_usable()
        self._write_depth += 1
        try:
            yield
        except BaseException:
            self._session.mark_failed()
            raise
        finally:
            self._write_depth -= 1

    def close(self) -> None:
        if self._write_depth:
            raise TransactionStateError('Cannot close the database inside a table write or hook')
        self._session.close()

    def __enter__(self) -> SqlDatabase:
        self._check_open()
        return self

    def __exit__(self, *exc: Any) -> None:
        self.close()
