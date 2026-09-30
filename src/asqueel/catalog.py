# Copyright 2025 Softwell S.r.l. - SPDX-License-Identifier: Apache-2.0
"""Ordered internal catalog of a built SQL model."""

from __future__ import annotations

from collections import defaultdict
from typing import Any


_VIRTUAL_COLUMN_TAGS = frozenset({
    "aliasColumn", "formulaColumn", "subQueryColumn", "pyColumn",
})
_COLLECTION_TAGS = frozenset({
    "schemas", "extensions", "tables", "columns", "virtual_columns",
    "composites", "constraints", "indexes",
})


class SqlModelCatalog:
    """Index model nodes once while preserving source order."""

    def __init__(self, builder) -> None:
        self.builder = builder
        self.database = None
        self.db_name = None
        self.nodes: list[tuple[str, Any]] = []
        self.schemas: dict[str, Any] = {}
        self.extensions: dict[str, Any] = {}
        self.tables: dict[tuple[str, str], dict[str, Any]] = {}
        self.physical_columns: dict[tuple[str, str, str], Any] = {}
        self.virtual_columns: dict[tuple[str, str, str], Any] = {}
        self.composites: dict[tuple[str, str, str], Any] = {}
        self.constraints: dict[tuple[str, str, str], Any] = {}
        self.indexes: dict[tuple[str, str, str], Any] = {}
        self.relations: list[tuple[str, Any]] = []
        self.relations_by_owner: dict[tuple[str, str, str], list[Any]] = defaultdict(list)
        self._children: dict[int, list[Any]] = defaultdict(list)
        self._paths: dict[int, str] = {}
        self._table_keys: dict[int, tuple[str, str]] = {}
        self._collect()

    def children(self, node) -> list[Any]:
        return list(self._children.get(id(node), ()))

    def path(self, node) -> str:
        return self._paths[id(node)]

    def table_key(self, node) -> tuple[str, str] | None:
        return self._table_keys.get(id(node))

    @staticmethod
    def _ancestor(node, tag: str):
        current = getattr(node, "parent_node", None)
        while current is not None:
            if current.node_tag == tag:
                return current
            current = getattr(current, "parent_node", None)
        return None

    def _collect(self) -> None:
        for path, node in self.builder.source.query("#p,#n", deep=True, iter=True):
            self.nodes.append((path, node))
            self._paths[id(node)] = path
            parent = getattr(node, "parent_node", None)
            if parent is not None:
                self._children[id(parent)].append(node)

            tag = node.node_tag
            if tag == "db":
                self.database = node
                self.db_name = node.get_attr("name")
                continue
            if tag == "schema":
                self.schemas[node.get_attr("name")] = node
                continue
            if tag == "extension":
                self.extensions[node.get_attr("name")] = node
                continue

            schema = self._ancestor(node, "schema")
            if schema is None:
                continue
            schema_name = schema.get_attr("name")
            if tag == "table":
                table_name = node.get_attr("name")
                self._table_keys[id(node)] = (schema_name, table_name)
                self.tables[(schema_name, table_name)] = {
                    "node": node,
                    "path": path,
                    "schema_name": schema_name,
                    "name": table_name,
                    "columns": {},
                    "virtual_columns": {},
                    "composites": {},
                    "family": {},
                    "constraints": [],
                    "indexes": [],
                    "relations": [],
                }
                continue

            table_node = self._ancestor(node, "table")
            if table_node is None:
                continue
            table_name = table_node.get_attr("name")
            table = self.tables.get((schema_name, table_name))
            if table is None:
                continue
            self._table_keys[id(node)] = (schema_name, table_name)
            if tag in _COLLECTION_TAGS:
                continue
            if tag == "relation":
                owner = getattr(node, "parent_node", None)
                owner_name = owner.get_attr("name") if owner is not None else None
                table["relations"].append((path, owner_name, node))
                self.relations.append((path, node))
                if owner_name is not None:
                    self.relations_by_owner[
                        (schema_name, table_name, owner_name)
                    ].append(node)
                continue
            name = node.get_attr("name")
            if tag == "constraint":
                table["constraints"].append((path, node))
                self.constraints[(schema_name, table_name, name)] = node
            elif tag == "index":
                table["indexes"].append((path, node))
                self.indexes[(schema_name, table_name, name)] = node
            else:
                table["family"][name] = node
                key = (schema_name, table_name, name)
                if node._get_meta("projects_column"):
                    table["columns"][name] = node
                    self.physical_columns[key] = node
                elif tag == "compositeColumn":
                    table["composites"][name] = node
                    self.composites[key] = node
                elif tag in _VIRTUAL_COLUMN_TAGS:
                    table["virtual_columns"][name] = node
                    self.virtual_columns[key] = node


__all__ = ["SqlModelCatalog"]
