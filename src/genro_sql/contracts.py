"""Shared, driver-independent contracts of the native PostgreSQL profile.

Names are logical unless explicitly prefixed with ``sql_``. SQL expressions
are authored application code; values belong exclusively in query parameters.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from copy import deepcopy
from types import MappingProxyType
from typing import Any, Mapping


class UnsupportedFeatureError(ValueError):
    """The requested feature is outside the declared native profile."""


class EnvironmentMismatchError(ValueError):
    """A context-bound query cannot be reused in a different environment."""


@dataclass(frozen=True, init=False)
class EnvironmentBinding:
    keys: tuple[str, ...]
    _values: Mapping[str, Any] = field(repr=False)

    def __init__(self, keys: tuple[str, ...], values: Mapping[str, Any]):
        object.__setattr__(self, 'keys', tuple(keys))
        object.__setattr__(self, '_values', MappingProxyType(deepcopy(dict(values))))

    @property
    def values(self) -> Mapping[str, Any]:
        """A detached snapshot; nested edits cannot change the bound context."""
        return MappingProxyType(deepcopy(dict(self._values)))

    def validate(self, current: Mapping[str, Any]) -> None:
        actual = {key: current[key] for key in self.keys if key in current}
        if actual != dict(self._values):
            raise EnvironmentMismatchError(
                'Query environment changed; compile again in the current scope')


@dataclass(frozen=True)
class PartitionScope:
    field: str
    current: str
    allowed: str | None = None
    include_null: bool = True


@dataclass(frozen=True)
class RowPolicies:
    partitions: tuple[PartitionScope, ...] = ()
    draft_field: str | None = None
    logical_deletion_field: str | None = None


@dataclass(frozen=True)
class Column:
    name: str
    dtype: str = "T"
    sql_name: str | None = None
    formula: str | None = None
    ui: Mapping[str, Any] = field(default_factory=dict)
    identity: str | None = None
    attributes: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        object.__setattr__(self, "ui", MappingProxyType(dict(self.ui)))
        object.__setattr__(self, "attributes", MappingProxyType(dict(self.attributes)))

    @property
    def physical_name(self) -> str:
        return self.sql_name if self.sql_name is not None else self.name


@dataclass(frozen=True)
class Relation:
    name: str
    target: str
    columns: tuple[str, ...]
    target_columns: tuple[str, ...]


@dataclass(frozen=True)
class Table:
    name: str
    schema: str = "public"
    columns: Mapping[str, Column] = field(default_factory=dict)
    relations: Mapping[str, Relation] = field(default_factory=dict)
    pkey: tuple[str, ...] = ()
    sql_name: str | None = None
    sql_schema: str | None = None
    sql_prefix: str = ""
    identity: str | None = None
    attributes: Mapping[str, Any] = field(default_factory=dict)
    policies: RowPolicies = field(default_factory=RowPolicies)

    def __post_init__(self):
        for name in ("columns", "relations", "attributes"):
            object.__setattr__(self, name, MappingProxyType(dict(getattr(self, name))))

    @property
    def key(self) -> str:
        return f"{self.schema}.{self.name}"

    @property
    def physical_name(self) -> str:
        return self.sql_name if self.sql_name is not None else self.sql_prefix + self.name

    @property
    def physical_schema(self) -> str:
        return self.sql_schema if self.sql_schema is not None else self.schema


@dataclass(frozen=True)
class ResolvedModel:
    tables: Mapping[str, Table]
    name: str = "database"
    warnings: tuple[str, ...] = ()

    def __post_init__(self):
        object.__setattr__(self, "tables", MappingProxyType(dict(self.tables)))

    def table(self, name: str) -> Table:
        try:
            return self.tables[name]
        except KeyError:
            matches = [t for t in self.tables.values() if t.name == name]
            if len(matches) == 1:
                return matches[0]
            raise ValueError(f"Unknown or ambiguous table: {name!r}") from None


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
    dialect: str = 'postgresql'
    binding: str = 'psycopg_named'
    environment: EnvironmentBinding | None = None

    def __post_init__(self):
        object.__setattr__(self, "params", MappingProxyType(dict(self.params)))


@dataclass(frozen=True)
class QueryResult:
    rows: list[dict[str, Any]]
    rowcount: int
    columns: tuple[ResultColumn, ...] = ()
