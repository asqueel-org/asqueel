# Copyright 2025 Softwell S.r.l. - SPDX-License-Identifier: Apache-2.0
"""Domain validation of a complete SQL model tree.

The grammar (:mod:`genro_sql.elements`) enforces containment and
types at build time; it cannot know whether a name refers to something.
This module walks the finished tree and checks the referential rules —
pkey members, relation targets, composite members, constraint and index
columns, the ``x_`` rule of the semi-closed signatures (D2).

Every violation is accumulated and reported together, prefixed by the
node's readable path (``d.public.recipe.author_id``), so one run tells
the whole story instead of stopping at the first offence.
"""

from __future__ import annotations

from collections import Counter

from .catalog import SqlModelCatalog
from .common import split_names

_META_KEY = "_meta"


class SqlModelValidationError(ValueError):
    """Every domain violation found in one model, one per line.

    Args:
        errors: the violation messages, already path-prefixed.
    """

    def __init__(self, errors: list[str]) -> None:
        self.errors = list(errors)
        super().__init__(
            "invalid SQL model:\n" + "\n".join(f"  {e}" for e in self.errors),
        )


class SqlModelValidator:
    """Referential validation of a built :class:`SqlBuilder` tree."""

    def validate(self, builder):
        """Validate ``builder``'s source tree.

        Args:
            builder: a created :class:`~genro_sql.builder.SqlBuilder`.

        Returns:
            The same builder, so the call chains.

        Raises:
            SqlModelValidationError: with every violation found.
        """
        self.errors: list[str] = []
        self._catalog = SqlModelCatalog(builder)
        self._db_name = self._catalog.db_name
        self._tables = self._catalog.tables
        self._relations = self._catalog.relations
        self._resolved: dict[str, tuple] = {}
        self._relation_keys: dict[tuple[str, str, tuple[str, ...]], str] = {}
        self._check_attributes(builder)
        for table in self._tables.values():
            self._check_pkey(table)
            self._check_composites(table)
            self._check_constraints(table)
            self._check_indexes(table)
            self._check_structural_keys(table)
        for path, node in self._relations:
            self._check_relation(path, node)
        self._check_back_references()
        if self.errors:
            raise SqlModelValidationError(self.errors)
        return builder

    # -- helpers ---------------------------------------------------------

    def _readable(self, path: str) -> str:
        """Path with the ``db`` root label replaced by the database name."""
        parts = path.split(".")
        if parts and self._db_name:
            parts[0] = self._db_name
        return ".".join(parts)

    def _error(self, path: str, message: str) -> None:
        self.errors.append(f"{self._readable(path)}: {message}")

    _names = staticmethod(split_names)

    def _pkey_names(self, table: dict) -> list[str]:
        return self._names(table["node"].get_attr("pkey"))

    def _check_repeated_members(
        self, path: str, family: str, members: list[str],
    ) -> None:
        repeated = sorted(name for name, count in Counter(members).items() if count > 1)
        if repeated:
            self._error(
                path,
                f"{family} repeats member(s): {', '.join(repeated)}",
            )

    # -- checks ----------------------------------------------------------

    def _check_attributes(self, builder) -> None:
        """D2: any attribute outside the signature must start with ``x_``."""
        schema = type(builder)._class_schema
        for path, node in self._catalog.nodes:
            element = schema.get_node(node.node_tag)
            if element is None:
                continue
            declared = element.get_attr("declared_names") or set()
            for key in node.attr:
                if key == _META_KEY or key in declared or key.startswith("x_"):
                    continue
                self._error(
                    path,
                    f"unknown attribute '{key}' on <{node.node_tag}>: extras "
                    f"must start with 'x_'; declared attributes are "
                    f"{', '.join(sorted(declared))}",
                )

    def _check_pkey(self, table: dict) -> None:
        names = self._pkey_names(table)
        self._check_repeated_members(table["path"], "pkey", names)
        for name in names:
            if name not in table["columns"]:
                self._error(
                    table["path"],
                    f"pkey column '{name}' is not a physical column of the table",
                )

    def _check_composites(self, table: dict) -> None:
        for name, node in table["composites"].items():
            path = self._catalog.path(node)
            members = self._names(node.get_attr("columns"))
            self._check_repeated_members(path, "composite", members)
            if not members:
                self._error(path, "compositeColumn requires 'columns'")
            for member in members:
                if member not in table["columns"]:
                    self._error(
                        path,
                        f"composite member '{member}' is not a physical "
                        "column of the table",
                    )

    def _check_constraints(self, table: dict) -> None:
        for path, node in table["constraints"]:
            kind = node.get_attr("constraint_type")
            name = node.get_attr("name")
            if kind == "CHECK" and not node.get_attr("check_clause"):
                self._error(
                    path, f"constraint '{name}': CHECK requires a check_clause",
                )
            if kind == "UNIQUE" and not node.get_attr("columns"):
                self._error(
                    path, f"constraint '{name}': UNIQUE requires columns",
                )
            columns = self._names(node.get_attr("columns"))
            if kind == "UNIQUE":
                self._check_repeated_members(path, "UNIQUE constraint", columns)
            for column in columns:
                if column not in table["columns"]:
                    self._error(
                        path,
                        f"constraint column '{column}' is not a physical "
                        "column of the table",
                    )

    def _check_indexes(self, table: dict) -> None:
        for path, node in table["indexes"]:
            raw_columns = node.get_attr("columns")
            columns = self._names(raw_columns)
            if not columns:
                self._error(path, "index requires 'columns'")
            self._check_repeated_members(path, "index", columns)
            if not isinstance(raw_columns, (str, dict)):
                self._error(
                    path,
                    "index columns must be a comma-joined string or a dict",
                )
            if isinstance(raw_columns, dict):
                for column, order in raw_columns.items():
                    if order not in (None, "DESC"):
                        self._error(
                            path,
                            f"index order for '{column}' must be None or 'DESC'",
                        )
            for column in columns:
                if column not in table["columns"]:
                    self._error(
                        path,
                        f"index column '{column}' is not a physical column "
                        "of the table",
                    )

    def _check_structural_keys(self, table: dict) -> None:
        unique_keys: dict[tuple[str, ...], str] = {}
        for path, node in table["constraints"]:
            if node.get_attr("constraint_type") != "UNIQUE":
                continue
            columns = tuple(self._names(node.get_attr("columns")))
            if columns in unique_keys:
                self._error(
                    path,
                    "duplicate UNIQUE structural key for columns "
                    f"{', '.join(columns)}; already declared at "
                    f"{self._readable(unique_keys[columns])}",
                )
            elif columns:
                unique_keys[columns] = path
        for name, node in table["composites"].items():
            if not node.get_attr("unique"):
                continue
            path = self._catalog.path(node)
            columns = tuple(self._names(node.get_attr("columns")))
            if columns in unique_keys:
                self._error(
                    path,
                    "duplicate UNIQUE structural key for columns "
                    f"{', '.join(columns)}; already declared at "
                    f"{self._readable(unique_keys[columns])}",
                )
            elif columns:
                unique_keys[columns] = path

        index_keys: dict[tuple[str, ...], str] = {}
        for path, node in table["indexes"]:
            columns = tuple(self._names(node.get_attr("columns")))
            if columns in index_keys:
                self._error(
                    path,
                    "duplicate index structural key for columns "
                    f"{', '.join(columns)}; already declared at "
                    f"{self._readable(index_keys[columns])}",
                )
            elif columns:
                index_keys[columns] = path

    def _resolve_target(self, path: str, node):
        """Target table and columns of ``relation.to``, errors reported.

        A three-part target names a physical column, or the
        compositeColumn packing the target key.

        Returns:
            ``(table_key, column_names)`` or ``None`` when unresolvable.
        """
        to = node.get_attr("to")
        if not to:
            self._error(path, "relation requires 'to'")
            return None
        parts = [p.strip() for p in str(to).split(".")]
        if len(parts) not in (2, 3):
            self._error(
                path,
                f"relation target '{to}' must be 'schema.table' or "
                "'schema.table.column'",
            )
            return None
        table_key = (parts[0], parts[1])
        target = self._tables.get(table_key)
        if target is None:
            self._error(path, f"relation target table '{to}' does not exist")
            return None
        if len(parts) == 3:
            composite = target["composites"].get(parts[2])
            columns = (self._names(composite.get_attr("columns"))
                       if composite is not None else [parts[2]])
        else:
            columns = self._pkey_names(target)
        if not columns:
            self._error(
                path,
                f"relation target '{to}' resolves to no column: the target "
                "table declares no pkey",
            )
            return None
        for column in columns:
            if column not in target["columns"]:
                self._error(
                    path,
                    f"relation target column '{to}': '{column}' is not a "
                    "physical column of the target table",
                )
                return None
        return table_key, columns

    def _check_relation(self, path: str, node) -> None:
        if not node.get_attr("foreign_key"):
            physical = [
                name for name in (
                    "on_delete", "on_update", "deferred", "deferrable",
                    "initially_deferred",
                )
                if node.get_attr(name)
            ]
            if "indexed" in node.attr:
                physical.append("indexed")
            if physical:
                self._error(
                    path,
                    "foreign_key=False cannot declare physical option(s): "
                    + ", ".join(physical),
                )
        if (node.get_attr("initially_deferred")
                and not (node.get_attr("deferrable")
                         or node.get_attr("deferred"))):
            self._error(
                path,
                "initially_deferred requires deferrable=True or deferred=True",
            )
        table_key = self._catalog.table_key(node)
        owner = getattr(node, "parent_node", None)
        if owner is None or not owner._get_meta("projects_relation"):
            if node.get_attr("foreign_key"):
                self._error(
                    path,
                    "foreign_key is allowed only on a relation under a "
                    "column or a compositeColumn",
                )
            return
        if owner.node_tag == "compositeColumn":
            local = self._names(owner.get_attr("columns"))
        else:
            local = [owner.get_attr("name")]
        relation_key = (*table_key, tuple(local))
        previous = self._relation_keys.get(relation_key)
        if previous is not None:
            self._error(
                path,
                "at most one relation may use local columns "
                f"{', '.join(local)}; already declared at "
                f"{self._readable(previous)}",
            )
        else:
            self._relation_keys[relation_key] = path
        resolved = self._resolve_target(path, node)
        if resolved is None:
            return
        self._resolved[path] = resolved
        _target_key, target_columns = resolved
        if len(local) != len(target_columns):
            self._error(
                path,
                f"composite relation column counts differ: {len(local)} local "
                f"({', '.join(local)}) vs {len(target_columns)} target "
                f"({', '.join(target_columns)})",
            )

    def _check_back_references(self) -> None:
        seen: dict[tuple, str] = {}
        for path, node in self._relations:
            back_reference = node.get_attr("back_reference")
            if not back_reference:
                continue
            resolved = self._resolved.get(path)
            if resolved is None:
                continue
            key = (resolved[0], back_reference)
            if key in seen:
                self._error(
                    path,
                    f"back_reference '{back_reference}' on "
                    f"'{'.'.join(resolved[0])}' is already used by "
                    f"{self._readable(seen[key])}",
                )
            else:
                seen[key] = path


__all__ = ["SqlModelValidationError", "SqlModelValidator"]
