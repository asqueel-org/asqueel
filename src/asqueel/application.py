"""Configured database graph using the shared execution and write lifecycle."""
from __future__ import annotations

from types import MappingProxyType
from typing import Any

from .application_table import SqlTable
from .compiler import QueryCompiler
from .configuration import SqlDatabaseConfig
from .contracts import UnsupportedFeatureError
from .environment import ApplicationEnvironment, SqlEnvironment
from .runtime import Database
from .object_tree import DbModel
from .writes import WriteMixin


class SqlDatabase(WriteMixin, Database):
    """A model and table graph over thread-local named connections."""

    def __init__(self, *, model: DbModel, config, driver=None, dialect=None,
                 environment: SqlEnvironment | None = None):
        if not isinstance(model, DbModel):
            raise TypeError('SqlDatabase requires a hierarchical DbModel')
        if model._operational_db is not None:
            raise ValueError('Hierarchical model is already bound to a database')
        self.config = config
        self.model = model
        from .configuration import connection_settings
        implementation, conninfo, kwargs = connection_settings(config)
        if implementation != model.implementation:
            raise ValueError('Configured implementation does not match the hierarchical model')
        default_driver: Any
        if implementation == 'postgresql':
            from .dialects.postgres import PostgresDialect
            from .drivers.psycopg import PsycopgDriver
            default_dialect, default_driver = PostgresDialect, PsycopgDriver
        elif implementation == 'sqlite':
            from .dialects.sqlite import SqliteDialect
            from .drivers.sqlite import SqliteDriver
            default_dialect, default_driver = SqliteDialect, SqliteDriver
        else:
            raise UnsupportedFeatureError(f'Unsupported database implementation: {implementation!r}')
        driver = driver if driver is not None else default_driver()
        self.dialect = dialect if dialect is not None else default_dialect()
        if self.dialect.name != implementation or driver.dialect != implementation:
            raise ValueError('Configured implementation does not match the data dialect/driver')
        super().__init__(conninfo, driver=driver, connect_kwargs=kwargs, environment=ApplicationEnvironment(environment))
        self._ready = False
        self._compiler = None
        model._bind_db(self)
        self._ready = True

    @property
    def compiler(self):
        if self._compiler is None:
            self._compiler = QueryCompiler(self.model, self.dialect, self.driver,
                                           environment=self.environment, _db=self)
        return self._compiler

    @property
    def tables(self):
        self._check_open()
        return MappingProxyType({name: table.dbtable for name, table in self.model.tables.items()})

    def table(self, name: str) -> SqlTable:
        """Return the registered operational table, preserving object identity."""
        self._check_open()
        table: SqlTable = self.model.table(name).dbtable
        return table

    def package(self, name: str):
        self._check_open()
        return self.model.packages[name]

    def schema(self, name: str):
        self._check_open()
        raise UnsupportedFeatureError('SQL schemas are derived from packages')

    def _write_table(self, table):
        if isinstance(self.model, DbModel):
            raise UnsupportedFeatureError('Writes on the hierarchical model are not connected yet')
        return super()._write_table(table)

    def _connection_settings(self):
        from .configuration import connection_settings
        implementation, conninfo, kwargs = connection_settings(self.config, self.currentConnectionName)
        if implementation != self.dialect.name:
            raise ValueError('Configured implementation changed after database construction')
        kwargs = dict(kwargs or {})
        if implementation == 'sqlite':
            kwargs['schemas'] = sorted({table.sqlschema for table in self.model.tables.values()})
        return conninfo, kwargs


class AsqueelDb(SqlDatabase):
    """Load a configured database by registered name, recipe, folder, file or mounted node.

    Construction validates the model without connecting. Use table(), commit(),
    rollback() and close() directly on this long-lived database object.

    ``grammar`` is the configuration grammar a host document mounts to declare
    Asqueel databases in its own configuration: an element carrying
    ``_meta={"subbuilder": "db_class:grammar"}`` with ``db_class=AsqueelDb``.
    The database is written under that element starting from ``db()``, and
    ``AsqueelDb(node)`` builds it from the resulting ``db`` node.
    """

    grammar = SqlDatabaseConfig

    def migration_plan(self, *, allow_removals=False):
        """The DDL that would bring the live database to this model; changes nothing.

        Needs ``asqueel[migration]``. Returns a :class:`~asqueel.migration.MigrationPlan`.
        """
        # asqueel-migration is an optional extra: import it only when migrating.
        from .migration import migration_plan
        return migration_plan(self, allow_removals=allow_removals)

    def migrate(self, *, allow_removals=False):
        """Bring the live database to this model and return the applied plan.

        Needs ``asqueel[migration]``. Raises :class:`~asqueel.migration.MigrationError`
        before any DDL when the backend cannot apply a change, and after applying
        when differences remain.
        """
        from .migration import migrate
        return migrate(self, allow_removals=allow_removals)

    def __init__(self, source, *, parents=None, driver=None, dialect=None, environment=None):
        from .configuration import _owned_handler
        from .object_tree_renderer import render_model

        config = _owned_handler(source, parents)
        model = render_model(config)
        super().__init__(model=model, config=config, driver=driver,
                         dialect=dialect, environment=environment)
