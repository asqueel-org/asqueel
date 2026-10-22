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
    SqlTable, SqlQuery,
    RecordNotFoundError, RecordMultipleRowsError,
)
from .configuration import SqlDatabaseConfig, build_database
from .emitter import SqlPythonEmitter
from .renderer import SqlRenderer
from .compiler import PostgresCompiler, QueryCompiler
from .contracts import (
    CompiledQuery, ResultColumn,
    UnsupportedFeatureError, UnusedQueryParameterWarning, RowPolicies,
)
from .environment import SqlEnvironment
from .model import resolve_model
from .object_tree import DbModel
from .projection import to_physical_builder
from .runtime import (
    Database, PostgresDatabase, SqlCursor,
    TransactionStateError, session,
)
from .errors import DeferredCommitError, MigrationError
from .hosting import AsqueelDbMixin
from .triggers import TriggerStack, TriggerStackItem

__version__ = "0.7.0"

__all__ = [
    "AsqueelDb", "AsqueelDbMixin", "SqlDatabase", "SqlDatabaseConfig", "build_database",
    "SqlTable", "SqlQuery",
    "RecordNotFoundError", "RecordMultipleRowsError",
    "SqlBuilder", "SqlPythonEmitter", "SqlRenderer",
    "CompiledQuery",
    "ResultColumn", "UnsupportedFeatureError", "PostgresCompiler",
    "PostgresDatabase", "SqlCursor", "session",
    "TransactionStateError", "resolve_model", "DbModel",
    "to_physical_builder",
    "QueryCompiler", "Database",
    "SqlEnvironment", "UnusedQueryParameterWarning", "RowPolicies",
    "TriggerStack", "TriggerStackItem",
    "DeferredCommitError", "MigrationError",
]

_MIGRATION_EXTRA = (
    "asqueel-migration is required for {name}: install asqueel[migration]"
)

_MIGRATION_NAMES = {
    "SqlMigrationRenderer": ".migration",
    "MigrationPlan": ".migration",
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
