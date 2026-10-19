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
from .configuration import SqlDatabaseConfig, ConfigurationView, build_database
from .emitter import SqlPythonEmitter
from .renderer import SqlRenderer
from .compiler import PostgresCompiler, QueryCompiler
from .catalog_provider import CatalogProvider, PostgresCatalogProvider
from .contracts import (
    Column, CompiledQuery, Relation, ResolvedModel, ResultColumn,
    Table, UnsupportedFeatureError, UnusedQueryParameterWarning, RowPolicies,
)
from .environment import SqlEnvironment
from .importers import ImportResult, inspect_postgres
from .model_sections import Schema, Package, Option, Declaration
from .model_codec import model_to_json, model_from_json
from .model import resolve_model
from .projection import to_physical_builder
from .runtime import (
    Database, PostgresDatabase,
    TransactionStateError, session,
)
from .errors import DeferredCommitError, MigrationError
from .hosting import AsqueelDbMixin
from .triggers import TriggerStack, TriggerStackItem

__version__ = "0.6.0"

__all__ = [
    "Schema", "Package", "Option", "Declaration", "model_to_json", "model_from_json",
    "AsqueelDb", "AsqueelDbMixin", "SqlDatabase", "SqlDatabaseConfig", "ConfigurationView", "build_database",
    "SqlTable", "SqlQuery",
    "RecordNotFoundError", "RecordMultipleRowsError",
    "SqlBuilder", "SqlPythonEmitter", "SqlRenderer",
    "Column", "CompiledQuery", "Relation", "ResolvedModel",
    "ResultColumn", "Table", "UnsupportedFeatureError", "PostgresCompiler",
    "PostgresDatabase", "session",
    "TransactionStateError", "resolve_model", "ImportResult", "inspect_postgres",
    "to_physical_builder",
    "QueryCompiler", "Database",
    "CatalogProvider", "PostgresCatalogProvider",
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
