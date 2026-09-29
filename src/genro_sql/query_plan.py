"""Resolved query plans and structured SQL, before driver-specific binding.

Raw SQL text is trusted application code. Identifier and parameter nodes are
kept distinct so a driver never needs to reparse SQL to find placeholders.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Any, Mapping, TypeAlias

from .contracts import EnvironmentBinding, ResultColumn


@dataclass(frozen=True)
class Identifier:
    name: str


@dataclass(frozen=True)
class Parameter:
    name: str


SqlPart: TypeAlias = str | Identifier | Parameter


@dataclass(frozen=True)
class Fragment:
    parts: tuple[SqlPart, ...] = ()


def concat(*items: str | SqlPart | Fragment) -> Fragment:
    parts: list[SqlPart] = []
    for item in items:
        if isinstance(item, Fragment):
            parts.extend(item.parts)
        else:
            parts.append(item)
    return Fragment(tuple(parts))


def separated(items, separator: str = ', ') -> Fragment:
    parts: list[SqlPart] = []
    for index, item in enumerate(items):
        if index:
            parts.append(separator)
        parts.extend(concat(item).parts)
    return Fragment(tuple(parts))


@dataclass(frozen=True)
class TableRef:
    schema: str
    name: str
    alias: str = 't0'


@dataclass(frozen=True)
class Projection:
    expression: Fragment
    alias: str
    column: ResultColumn


@dataclass(frozen=True)
class Join:
    table: TableRef
    condition: Fragment
    kind: str = 'left'


@dataclass(frozen=True)
class Assignment:
    column: str
    value: Fragment


@dataclass(frozen=True)
class QueryPlan:
    operation: str
    table: TableRef
    projections: tuple[Projection, ...] = ()
    joins: tuple[Join, ...] = ()
    where: Fragment | None = None
    order_by: Fragment | None = None
    limit: int | None = None
    offset: int | None = None
    assignments: tuple[Assignment, ...] = ()
    params: Mapping[str, Any] = field(default_factory=dict)
    dialect: str = 'postgresql'
    environment: EnvironmentBinding | None = None

    def __post_init__(self):
        object.__setattr__(self, 'params', MappingProxyType(dict(self.params)))


@dataclass(frozen=True)
class SqlStatement:
    # Identifiers are already quoted by the dialect at this boundary.
    parts: tuple[str | Parameter, ...]
    params: Mapping[str, Any] = field(default_factory=dict)
    columns: tuple[ResultColumn, ...] = ()
    dialect: str = 'postgresql'
    environment: EnvironmentBinding | None = None

    def __post_init__(self):
        object.__setattr__(self, 'params', MappingProxyType(dict(self.params)))
