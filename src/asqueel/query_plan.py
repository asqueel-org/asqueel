"""Resolved query plans and structured SQL, before driver-specific binding.

Raw SQL text is trusted application code. Identifier and parameter nodes are
kept distinct so a driver never needs to reparse SQL to find placeholders.
"""
from __future__ import annotations

import re
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
    for_update: bool = False
    input_parameters: tuple[str, ...] = ()
    distinct: bool = False
    group_by: Fragment | None = None
    having: Fragment | None = None

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


_IDENT = r"[A-Za-z_][A-Za-z_0-9]*"
# One scan for both parameter forms: an optional IN / NOT IN keyword, which puts the
# parameter in collection position, then the parameter itself.
_PARAM = re.compile(r"(?i)(?:\b(?P<keyword>NOT\s+IN|IN)\s*)?:(?P<name>" + _IDENT + r")")
_COLLECTION_TYPES = (list, tuple, set, frozenset)


def _column_reference(fragment: Fragment) -> bool:
    parts = fragment.parts
    return (len(parts) == 3 and isinstance(parts[0], Identifier) and parts[1] == '.'
            and isinstance(parts[2], Identifier))


def parameter_use(uses, name, collection):
    """Record how a parameter is used; one name is a collection or a scalar, never both."""
    if uses.setdefault(name, collection) is not collection:
        raise ValueError(f'Parameter {name} is used both in IN position and as a scalar value')


def member_name(base, names):
    """A bound name for one collection member, unique against every name already in use."""
    index = 0
    while f'{base}_{index}' in names:
        index += 1
    name = f'{base}_{index}'
    names.add(name)
    return name


def expand_collection(name, value, negated, allocate, empty_form):
    """The SQL parts replacing ``IN :name`` with one binding per member.

    Shared by the compiler and by direct SQL preparation, so the two paths
    cannot diverge on accepted types, member naming or the empty form.
    """
    if not isinstance(value, _COLLECTION_TYPES):
        raise ValueError(f'Parameter {name} is in IN position and requires a list, tuple, set '
                         f'or frozenset, not {type(value).__name__}')
    members = list(value)
    if not members:
        return [empty_form(negated)]
    parts = ['NOT IN (' if negated else 'IN (']
    for index, member in enumerate(members):
        if index:
            parts.append(', ')
        parts.append(Parameter(allocate(member)))
    parts.append(')')
    return parts
