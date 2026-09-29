# Copyright 2025 Softwell S.r.l. - SPDX-License-Identifier: Apache-2.0
"""SQL-model grammar, native PostgreSQL compiler and awaitable runtime.

The source tree is the pivot for migration tooling and round-tripping:
:class:`SqlMigrationRenderer` projects it to normalized migration JSON,
:class:`SqlModelReader` reads that structure back, and
:class:`SqlPythonEmitter` emits an editable Python recipe.
"""

from __future__ import annotations

from importlib import import_module

from .builder import SqlBuilder
from .emitter import SqlPythonEmitter
from .renderer import SqlRenderer
from .compiler import PostgresCompiler, QueryCompiler
from .catalog_provider import CatalogProvider, PostgresCatalogProvider
from .dialects.postgres import PostgresDialect
from .drivers.psycopg import PsycopgDriver
from .contracts import (
    Column, CompiledQuery, QueryResult, Relation, ResolvedModel, ResultColumn,
    Table, UnsupportedFeatureError,
)
from .importers import ImportResult, inspect_postgres
from .model import resolve_model
from .projection import to_physical_builder
from .runtime import (
    DatabaseClosedError, DatabaseSaturatedError, PostgresDatabase, ThreadedDatabase,
    TransactionStateError,
)

__version__ = "0.1.0"

__all__ = [
    "SqlBuilder", "SqlPythonEmitter", "SqlRenderer",
    "Column", "CompiledQuery", "QueryResult", "Relation", "ResolvedModel",
    "ResultColumn", "Table", "UnsupportedFeatureError", "PostgresCompiler",
    "PostgresDatabase", "DatabaseClosedError", "DatabaseSaturatedError",
    "TransactionStateError", "resolve_model", "ImportResult", "inspect_postgres",
    "to_physical_builder",
    "QueryCompiler", "PostgresDialect", "PsycopgDriver", "ThreadedDatabase",
    "CatalogProvider", "PostgresCatalogProvider",
]

_MIGRATION_EXTRA = (
    "genro-sqlmigration is required for {name}: install genro-sql[migration]"
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
        if error.name != "genro_sqlmigration":
            raise
        raise ImportError(_MIGRATION_EXTRA.format(name=name)) from error
    return getattr(module, name)
