"""Task-local SQL environment with explicit, detached snapshots.

The environment is context, not an authorization mechanism. Scope values are
never exposed directly: defaults, scope entry and snapshots are copied.
"""
from __future__ import annotations

from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from contextvars import ContextVar
from copy import deepcopy
from types import MappingProxyType
from typing import Any


def _copy_values(values: Mapping[str, Any], operation: str) -> dict[str, Any]:
    try:
        return deepcopy(dict(values))
    except Exception as error:
        raise ValueError(
            f'Cannot copy SQL environment values during {operation}; '
            'values must support deepcopy'
        ) from error


class SqlEnvironment:
    """An isolated context variable holding the current SQL environment.

    ``temp_env`` overlays values until the scope exits. ``None`` is a value,
    not a deletion marker. Child tasks inherit the context at task creation;
    snapshots and subsequent scopes remain independent.
    """

    def __init__(self, defaults: Mapping[str, Any] | None = None):
        initial = _copy_values(defaults if defaults is not None else {}, 'initialization')
        self._values: ContextVar[dict[str, Any]] = ContextVar(
            f'sql_environment_{id(self):x}', default=initial)

    def snapshot(self) -> Mapping[str, Any]:
        """Return a detached copy with a read-only outer mapping.

        Nested mutable values may be edited by the consumer without modifying
        this environment or another snapshot. Driver/application values must
        provide a correct deepcopy implementation.
        """
        return MappingProxyType(_copy_values(self._values.get(), 'snapshot'))

    @property
    def current_env(self) -> Mapping[str, Any]:
        return self.snapshot()

    @property
    def currentEnv(self) -> Mapping[str, Any]:
        """Compatibility spelling of ``current_env`` (also a snapshot)."""
        return self.current_env

    @contextmanager
    def temp_env(self, **values: Any) -> Iterator[SqlEnvironment]:
        """Overlay values for the current context and restore them in finally."""
        merged = dict(self._values.get())
        merged.update(values)
        copied = _copy_values(merged, 'scope entry')
        token = self._values.set(copied)
        try:
            yield self
        finally:
            self._values.reset(token)

    def tempEnv(self, **values: Any):
        """Compatibility spelling of ``temp_env``."""
        return self.temp_env(**values)
