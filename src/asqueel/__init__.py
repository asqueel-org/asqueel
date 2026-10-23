# Copyright 2025 Softwell S.r.l. - SPDX-License-Identifier: Apache-2.0
"""SQL-model grammar, native PostgreSQL compiler and synchronous runtime.

The source tree is the pivot for migration tooling and round-tripping:
:class:`SqlMigrationRenderer` projects it to normalized migration JSON,
:class:`SqlModelReader` reads that structure back, and
:class:`SqlPythonEmitter` renders an editable Python recipe (`recipe.render(mode='python')`).
"""

from __future__ import annotations

from importlib import import_module

from .builder import SqlBuilder
from .application import AsqueelDb
from .application_table import (
    SqlTable, SqlQuery,
    RecordNotFoundError, RecordMultipleRowsError,
)
from .configuration import SqlDatabaseConfig
from .emitter import SqlPythonEmitter
from .compiler import QueryCompiler
from .contracts import (
    CompiledQuery, ResultColumn,
    UnsupportedFeatureError, UnusedQueryParameterWarning, RowPolicies,
)
from .object_tree import DbModel
from .runtime import (
    SqlCursor,
    TransactionStateError, session,
)
from .errors import DeferredCommitError, MigrationError
from .hosting import AsqueelDbMixin
from .triggers import TriggerStack, TriggerStackItem

__version__ = "0.7.0"

__all__ = [
    "AsqueelDb", "AsqueelDbMixin", "SqlDatabaseConfig",
    "SqlTable", "SqlQuery",
    "RecordNotFoundError", "RecordMultipleRowsError",
    "SqlBuilder", "SqlPythonEmitter",
    "CompiledQuery",
    "ResultColumn", "UnsupportedFeatureError",
    "SqlCursor", "session",
    "TransactionStateError", "DbModel",
    "QueryCompiler",
    "UnusedQueryParameterWarning", "RowPolicies",
    "TriggerStack", "TriggerStackItem",
    "DeferredCommitError", "MigrationError",
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
