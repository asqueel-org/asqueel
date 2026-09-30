# Copyright 2025 Softwell S.r.l. - SPDX-License-Identifier: Apache-2.0
"""SQL-model grammar, native PostgreSQL compiler and synchronous runtime.

The source tree is the pivot for migration tooling and round-tripping:
:class:`SqlMigrationRenderer` projects it to normalized migration JSON,
:class:`SqlModelReader` reads that structure back, and
:class:`SqlPythonEmitter` emits an editable Python recipe.
"""

from __future__ import annotations

from importlib import import_module

from .builder import SqlBuilder
from .application import AsqueelDb, SqlDatabase
from .application_table import (
    SqlTable, SqlColumn, SqlRelation, SqlQuery, SqlRecord,
    RecordNotFoundError, RecordMultipleRowsError,
)
from .configuration import SqlDatabaseConfig, ConfigurationView, build_database
from .emitter import SqlPythonEmitter
from .renderer import SqlRenderer
from .compiler import PostgresCompiler, QueryCompiler
from .catalog_provider import CatalogProvider, PostgresCatalogProvider
from .dialects.postgres import PostgresDialect
from .drivers.psycopg import PsycopgDriver
from .contracts import (
    Column, CompiledQuery, QueryResult, Relation, ResolvedModel, ResultColumn,
    Table, UnsupportedFeatureError, EnvironmentMismatchError, PartitionScope, RowPolicies,
)
from .environment import SqlEnvironment
from .importers import ImportResult, inspect_postgres
from .model import resolve_model
from .projection import to_physical_builder
from .runtime import (
    DatabaseClosedError, Database, PostgresDatabase,
    TransactionStateError,
)
from .session import DeferredCommitError
from .triggers import TriggerStack, TriggerStackItem

__version__ = "0.2.0"

__all__ = [
    "AsqueelDb", "SqlDatabase", "SqlDatabaseConfig", "ConfigurationView", "build_database",
    "SqlTable", "SqlColumn", "SqlRelation", "SqlQuery", "SqlRecord",
    "RecordNotFoundError", "RecordMultipleRowsError",
    "SqlBuilder", "SqlPythonEmitter", "SqlRenderer",
    "Column", "CompiledQuery", "QueryResult", "Relation", "ResolvedModel",
    "ResultColumn", "Table", "UnsupportedFeatureError", "PostgresCompiler",
    "PostgresDatabase", "DatabaseClosedError",
    "TransactionStateError", "resolve_model", "ImportResult", "inspect_postgres",
    "to_physical_builder",
    "QueryCompiler", "PostgresDialect", "PsycopgDriver", "Database",
    "CatalogProvider", "PostgresCatalogProvider",
    "SqlEnvironment", "EnvironmentMismatchError", "PartitionScope", "RowPolicies",
    "TriggerStack", "TriggerStackItem",
    "DeferredCommitError",
]

_MIGRATION_EXTRA = (
    "asqueel-migration is required for {name}: install asqueel[migration]"
)

_MIGRATION_NAMES = {
    "SqlMigrationRenderer": ".migration",
    "SqlModelReader": ".reader",
}


def __getattr__(name: str):
    """Resolve the names that need an optional dependency, on first use."""
    module_name = _MIGRATION_NAMES.get(name)
    if module_name is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    try:
        module = import_module(module_name, __name__)
    except ModuleNotFoundError as error:
        if error.name != "asqueel_migration":
            raise
        raise ImportError(_MIGRATION_EXTRA.format(name=name)) from error
    return getattr(module, name)
