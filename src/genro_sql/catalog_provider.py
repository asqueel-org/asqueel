"""Read-only structural catalog providers, separate from data SQL dialects.

A future sqlmigration provider must preserve the importer's fidelity checks;
the existing normalized migration structure alone is not a complete catalog.
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Any, Mapping, Protocol, Sequence

if TYPE_CHECKING:
    from .importers import ImportResult


class CatalogProvider(Protocol):
    dialect: str

    def inspect(self, connection: Any, schemas: Sequence[str], *,
                ui: Mapping[str, Mapping[str, Any]] | None = None) -> ImportResult: ...


class PostgresCatalogProvider:
    """Inspect PostgreSQL catalogs without owning connection or transaction."""

    dialect = 'postgresql'

    def inspect(self, connection: Any, schemas: Sequence[str], *,
                ui: Mapping[str, Mapping[str, Any]] | None = None) -> ImportResult:
        from .importers import _inspect_postgres

        return _inspect_postgres(connection, schemas, ui=ui)
