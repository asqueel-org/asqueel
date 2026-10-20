"""Configured database graph using the shared execution and write lifecycle."""
from __future__ import annotations

from types import MappingProxyType
from typing import Any

from .application_table import SqlTable
from .compiler import QueryCompiler
from .configuration import SqlDatabaseConfig, _owned_handler, connection_settings
from .contracts import UnsupportedFeatureError
from .errors import MigrationError, TransactionStateError
from .environment import ApplicationEnvironment, SqlEnvironment
from .runtime import Database
from .object_tree import DbModel
from .object_tree_renderer import render_model
from .write_compiler import WriteCompiler
from .db_write import WriteMixin


class SqlDatabase(WriteMixin, Database):
    """A model and table graph over thread-local named connections."""

    def __init__(self, *, model: DbModel, config, environment: SqlEnvironment | None = None):
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
        super().__init__(conninfo, implementation=implementation, connect_kwargs=kwargs,
                         environment=ApplicationEnvironment(environment))
        self._ready = False
        self._compilers: dict[Any, QueryCompiler] = {}
        self._write_compilers: dict[Any, WriteCompiler] = {}
        model._bind_db(self)
        self._ready = True

    @property
    def compiler(self):
        adapter = self.adapter
        if adapter not in self._compilers:
            self._compilers[adapter] = QueryCompiler(self.model, adapter,
                                                     environment=self.environment, _db=self)
        return self._compilers[adapter]

    @property
    def write_compiler(self):
        """Compiler of insert, update and delete statements, separate from queries."""
        adapter = self.adapter
        if adapter not in self._write_compilers:
            self._write_compilers[adapter] = WriteCompiler(adapter)
        return self._write_compilers[adapter]

    @property
    def tables(self):
        self._check_open()
        return MappingProxyType({name: table.dbtable for name, table in self.model.tables.items()})

    def table(self, name: str) -> SqlTable:
        """Return the registered operational table, preserving object identity."""
        self._check_open()
        found = self.model.table(name)
        if found is None:
            raise ValueError(f'Unknown package/schema {name.split(".")[0]!r}')
        table: SqlTable = found.dbtable
        return table

    def package(self, name: str):
        self._check_open()
        return self.model.packages[name]

    def schema(self, name: str):
        self._check_open()
        raise UnsupportedFeatureError('SQL schemas are derived from packages')

    def _connection_settings(self):
        from .configuration import connection_settings
        implementation, conninfo, kwargs = connection_settings(self.config, self.currentConnectionName)
        if implementation != self.model.implementation:
            raise ValueError('Configured implementation changed after database construction')
        kwargs = dict(kwargs or {})
        if self.implementation == 'sqlite':
            kwargs['schemas'] = sorted({table.sqlschema for table in self.model.tables.values()})
        return conninfo, kwargs


class AsqueelDb(SqlDatabase):
    """Load a configured database by registered name, recipe, folder, file or mounted node.

    Construction validates the model without connecting. Use table(), commit(),
    rollback() and closeConnection() directly on this long-lived database object.

    ``grammar`` is the configuration grammar a host document mounts to declare
    Asqueel databases in its own configuration: an element carrying
    ``_meta={"subbuilder": "db_class:grammar"}`` with ``db_class=AsqueelDb``.
    The database is written under that element starting from ``db()``, and
    ``AsqueelDb(node)`` builds it from the resulting ``db`` node.
    """

    grammar = SqlDatabaseConfig

    def migration_plan(self, *, allow_removals=False, foreignKeys=True, force=False, backup=False):
        """The DDL that would bring the live database to this model; changes nothing.

        Needs ``asqueel[migration]``. Returns a :class:`~asqueel.migration.MigrationPlan`.
        ``foreignKeys``, ``force`` and ``backup`` are the legacy migration options
        (:func:`asqueel.migration.migration_plan`).
        """
        # asqueel-migration is an optional extra: import it only when migrating.
        from .migration import migration_plan
        return migration_plan(self, allow_removals=allow_removals, foreignKeys=foreignKeys,
                              force=force, backup=backup)

    def migrate(self, *, allow_removals=False, foreignKeys=True, force=False, backup=False):
        """Bring the live database to this model and return the applied plan.

        Needs ``asqueel[migration]``. Raises :class:`~asqueel.migration.MigrationError`
        before any DDL when the backend cannot apply a change, and after applying
        when differences remain. The options are those of :meth:`migration_plan`.
        """
        from .migration import migrate
        return migrate(self, allow_removals=allow_removals, foreignKeys=foreignKeys,
                       force=force, backup=backup)

    def __init__(self, source, *, parents=None, environment=None):
        from .configuration import _owned_handler
        from .object_tree_renderer import render_model

        config = _owned_handler(source, parents)
        model = render_model(config)
        super().__init__(model=model, config=config, environment=environment)

    def reloadModel(self, source, *, parents=None):
        """Replace the model of an idle SQLite :memory: database, keeping its connection and rows.

        Does not migrate or reconnect: call migrate() afterwards, then take
        fresh tables and queries, because those of the previous model are
        invalidated. Requires exclusive use of this database (no concurrent
        threads), the same connection settings and the same SQL schemas.
        """
        self._check_idle()
        if len(self._connections) > 1:
            raise MigrationError('reloadModel requires a single main connection')
        old_settings = connection_settings(self.config)
        implementation, conninfo, kwargs = old_settings
        if implementation != 'sqlite' or ((kwargs or {}).get('dbname') or conninfo) != ':memory:':
            raise MigrationError('reloadModel is only supported for SQLite :memory: databases')
        config = _owned_handler(source, parents)
        if connection_settings(config) != old_settings:
            raise MigrationError('reloadModel cannot change connection settings')
        model = render_model(config)
        if {t.sqlschema for t in model.tables.values()} != {t.sqlschema for t in self.model.tables.values()}:
            raise MigrationError('reloadModel cannot change SQL schemas')
        old_model = self.model
        model._bind_db(self)
        self.config, self.model = config, model
        self._compilers.clear()
        self._write_compilers.clear()
        env = self.currentEnv
        for key in [key for key in env if key.startswith('_virtual_columns_')]:
            del env[key]
        old_model._operational_db = None

    def _check_idle(self):
        """Refuse to commit, roll back or bypass the unfinished work of a connection."""
        self._check_open()
        if not self.usingMainConnection() or self.adapter.dialect != 'sqlite':
            raise MigrationError('In-memory migration requires the main SQLite connection')
        for state in self._connections.values():
            self._check_connection_usable(state)
            self._check_connection_completion(state)
            deferred = any(self.currentEnv.get(self._deferred_key(state, key)) for key in (
                'to_commit_defer_calls', 'after_commit_defer_calls', '_pendingExceptions'))
            connection = state['connection']
            if (state['pending'] or state['write_depth'] or deferred
                    or (connection is not None and connection.in_transaction)):
                raise TransactionStateError(
                    'In-memory schema changes require no pending work; commit or rollback first')
