"""Shared, driver-independent contracts of the native PostgreSQL profile.

Names are logical unless explicitly prefixed with ``sql_``. SQL expressions
are authored application code; values belong exclusively in query parameters.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Any, Mapping


class UnsupportedFeatureError(ValueError):
    """The requested feature is outside the declared native profile."""


def not_available(subject):
    """The error of a legacy feature absent from this release, naming what the user wrote."""
    return UnsupportedFeatureError(f'{subject} is not available in this release')


def refused_property(subject):
    """A property whose read raises the error of a legacy feature absent from this release."""
    def refuse(self):
        raise not_available(subject)
    return property(refuse)


class UnusedQueryParameterWarning(UserWarning):
    """A query keyword that the compiled query does not use; the query still runs."""


@dataclass(frozen=True)
class RowPolicies:
    draft_field: str | None = None
    logical_deletion_field: str | None = None


@dataclass(frozen=True)
class ResultColumn:
    name: str
    dtype: str | None = None
    source: str | None = None
    ui: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class CompiledQuery:
    sql: str
    params: Mapping[str, Any] = field(default_factory=dict)
    columns: tuple[ResultColumn, ...] = ()
    # Existing positional constructors remain PostgreSQL/psycopg statements.
    dialect: str = 'postgres'
    binding: str = 'psycopg_named'
    # Environment keys read into the :env_* parameters at every execution.
    environment_keys: tuple[str, ...] = ()
    # Original caller parameter names consumed before scoped SQL renaming.
    input_parameters: tuple[str, ...] = ()
    for_update: bool | str = False
    lock_table: str | None = None
    lock_column: str | None = None
    # (field, separateCols) of the #BAG/#BAGCOLS columns, turned into Bags after fetch.
    evaluateBagColumns: tuple[tuple[str, bool], ...] = ()

    def __post_init__(self):
        object.__setattr__(self, "params", MappingProxyType(dict(self.params)))
