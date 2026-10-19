"""Shared, driver-independent contracts of the native PostgreSQL profile.

Names are logical unless explicitly prefixed with ``sql_``. SQL expressions
are authored application code; values belong exclusively in query parameters.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from copy import deepcopy
from types import MappingProxyType
from typing import Any, Mapping
from genro_toolbox import NamedList
from .model_sections import FrozenMap, Schema, Package, Option, Declaration


class UnsupportedFeatureError(ValueError):
    """The requested feature is outside the declared native profile."""


def not_available(subject):
    """The error of a legacy feature absent from this release, naming what the user wrote."""
    return UnsupportedFeatureError(f'{subject} is not available in this release')


def refused_property(subject):  # wf:phase-2:new
    """A property whose read raises the error of a legacy feature absent from this release."""
    def refuse(self):
        raise not_available(subject)
    return property(refuse)


class UnusedQueryParameterWarning(UserWarning):  # wf:phase-2:new
    """A query keyword that the compiled query does not use; the query still runs."""


@dataclass(frozen=True)
class RowPolicies:
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
    relation_path: str | None = None
    alias_target: tuple[str, str] | None = None
    select: Mapping[str, Any] | None = None
    exists: Mapping[str, Any] | None = None
    subqueries: Mapping[str, Mapping[str, Any]] = field(default_factory=dict)
    kind: str = 'column'
    declarations: tuple[Declaration, ...] = ()

    @property
    def validations(self) -> dict[str, Any]:
        """Declared rules and transformations as a detached dictionary."""
        for declaration in self.declarations:
            if declaration.kind == 'validation':
                return deepcopy(dict(declaration.attributes))
        return {}

    @property
    def is_virtual(self) -> bool:
        return (self.kind != 'column' or self.formula is not None or self.relation_path is not None
                or self.select is not None or self.exists is not None
                or bool(self.subqueries))

    def __post_init__(self):
        object.__setattr__(self, "ui", FrozenMap(self.ui))
        object.__setattr__(self, "attributes", FrozenMap(self.attributes))
        for name in ('select', 'exists'):
            value = getattr(self, name)
            if value is not None:
                object.__setattr__(self, name, FrozenMap(value))
        object.__setattr__(self, 'subqueries', FrozenMap(self.subqueries))
        object.__setattr__(self, 'declarations', tuple(self.declarations))

    @property
    def physical_name(self) -> str:
        return self.sql_name if self.sql_name is not None else self.name


@dataclass(frozen=True)
class Relation:
    name: str
    target: str
    columns: tuple[str, ...]
    target_columns: tuple[str, ...]
    kind: str = "relation"
    attributes: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        object.__setattr__(self, "attributes", FrozenMap(self.attributes))


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
    options: Mapping[str, Option] = field(default_factory=dict)
    declarations: tuple[Declaration, ...] = ()
    package_name: str | None = None

    def __post_init__(self):
        for name in ("columns", "relations"):
            object.__setattr__(self, name, MappingProxyType(dict(getattr(self, name))))
        object.__setattr__(self, 'attributes', FrozenMap(self.attributes))
        object.__setattr__(self, 'options', FrozenMap(self.options))
        object.__setattr__(self, 'declarations', tuple(self.declarations))

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
    schemas: Mapping[str, Schema] = field(default_factory=dict)
    packages: Mapping[str, Package] = field(default_factory=dict)
    options: Mapping[str, Option] = field(default_factory=dict)
    attributes: Mapping[str, Any] = field(default_factory=dict)
    extensions: tuple[str, ...] = ()
    capabilities: tuple[str, ...] = ()

    def __post_init__(self):
        object.__setattr__(self, "tables", MappingProxyType(dict(self.tables)))
        for name in ('schemas', 'packages', 'options', 'attributes'):
            object.__setattr__(self, name, FrozenMap(getattr(self, name)))
        object.__setattr__(self, 'extensions', tuple(self.extensions))
        object.__setattr__(self, 'capabilities', tuple(self.capabilities))

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
    dialect: str = 'postgres'
    binding: str = 'psycopg_named'
    # Environment keys read into the :env_* parameters at every execution.
    environment_keys: tuple[str, ...] = ()
    # Original caller parameter names consumed before scoped SQL renaming.
    input_parameters: tuple[str, ...] = ()
    for_update: bool = False
    lock_table: str | None = None
    lock_column: str | None = None

    def __post_init__(self):
        object.__setattr__(self, "params", MappingProxyType(dict(self.params)))


@dataclass(frozen=True)
class QueryResult:
    rows: list[NamedList]
    rowcount: int
    columns: tuple[ResultColumn, ...] = ()
