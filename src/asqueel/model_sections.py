"""Immutable semantic model sections, independent of Builders and connections."""
from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from copy import deepcopy


class FrozenMap(Mapping):
    """Recursively immutable values that can safely participate in deepcopy."""
    def __init__(self, values=()):
        self._values = {key: freeze(value) for key, value in dict(values).items()}

    def __getitem__(self, key):
        return self._values[key]

    def __iter__(self):
        return iter(self._values)

    def __len__(self):
        return len(self._values)

    def __deepcopy__(self, memo):
        return self

    def __eq__(self, other):
        return isinstance(other, Mapping) and dict(self) == dict(other)


class FrozenList(list):
    """Read-only list retaining list equality and driver array adaptation."""
    def _readonly(self, *args, **kwargs):
        raise TypeError('Model lists are immutable')

    __setitem__ = __delitem__ = __iadd__ = __imul__ = _readonly
    append = clear = extend = insert = pop = remove = reverse = sort = _readonly

    def __deepcopy__(self, memo):
        return self


def freeze(value):
    if isinstance(value, FrozenMap):
        return value
    if isinstance(value, Mapping):
        return FrozenMap(value)
    if isinstance(value, list):
        return FrozenList(freeze(item) for item in value)
    if isinstance(value, tuple):
        return tuple(freeze(item) for item in value)
    return deepcopy(value)


def thaw(value):
    """Give legacy formula methods an owned, mutable copy of model attributes."""
    if isinstance(value, Mapping):
        return {key: thaw(item) for key, item in value.items()}
    if isinstance(value, list):
        return [thaw(item) for item in value]
    if isinstance(value, tuple):
        return tuple(thaw(item) for item in value)
    return deepcopy(value)


@dataclass(frozen=True)
class Option:
    name: str
    attributes: Mapping = field(default_factory=dict)

    def __post_init__(self):
        object.__setattr__(self, 'attributes', FrozenMap(self.attributes))

    @property
    def enabled(self):
        return self.attributes.get('enabled', True)


@dataclass(frozen=True)
class Schema:
    name: str
    sqlname: str | None = None
    attributes: Mapping = field(default_factory=dict)
    options: Mapping = field(default_factory=dict)

    def __post_init__(self):
        object.__setattr__(self, 'attributes', FrozenMap(self.attributes))
        object.__setattr__(self, 'options', FrozenMap(self.options))

    @property
    def physical_name(self):
        return self.sqlname or self.name


@dataclass(frozen=True)
class Package:
    name: str
    sqlschema: str = 'public'
    sqlprefix: bool | str = True
    attributes: Mapping = field(default_factory=dict)
    options: Mapping = field(default_factory=dict)
    tables: tuple[str, ...] = ()

    def __post_init__(self):
        object.__setattr__(self, 'attributes', FrozenMap(self.attributes))
        object.__setattr__(self, 'options', FrozenMap(self.options))
        object.__setattr__(self, 'tables', tuple(self.tables))


@dataclass(frozen=True)
class Declaration:
    """A semantic child (group, virtual relation, rule), never a source Bag."""
    kind: str
    name: str
    attributes: Mapping = field(default_factory=dict)
    children: tuple[Declaration, ...] = ()

    def __post_init__(self):
        object.__setattr__(self, 'attributes', FrozenMap(self.attributes))
        object.__setattr__(self, 'children', tuple(self.children))
