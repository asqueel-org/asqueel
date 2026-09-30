# Copyright 2025 Softwell S.r.l. - SPDX-License-Identifier: Apache-2.0
"""SqlBuilder — SQL model dialect for genro-builders.

Grammar only: the vocabulary lives in the four mixins of
:mod:`asqueel.elements`, rendering in :class:`SqlRenderer` exposed
via the ``renderer_sql`` property.
"""

from __future__ import annotations

from typing import cast

from genro_bag import BagNode

from genro_builders.builder import BuilderBase, SourceBag
from genro_builders.builder.base import SOURCE_ROOT

from .elements import ColumnElements, DbElements, SchemaElements, TableElements
from .renderer import SqlRenderer
from .validators import SqlModelValidator


class SqlSourceBag(SourceBag):
    """Source bag whose bracket access is name addressing over NODES.

    ``model.source["db.public.author"]`` returns the grammar node — its
    attributes, ``_meta`` flags and children — because the SQL model is a
    name-keyed catalog, not a value store: every consumer (renderer,
    validators, emitter) reads nodes. ``get_item``/``get`` keep the plain
    Bag value semantics. Sub-bags inherit this class automatically (the
    grammar spawns them as ``type(node.parent_bag)``), so the whole tree
    is addressed the same way.

    The override also reshapes every Bag form that reads through
    ``__getitem__``: the ``?attr`` path suffix and ``bag(path)`` return
    the node instead of value/attribute, an empty path returns the
    owning node, and the scoped ``query``/``digest`` form
    (``"where:what"``) is unsupported — scope with ``get_item(where)``
    or walk from a node's ``.value`` instead.
    """

    def __getitem__(self, path: str) -> BagNode | None:
        return cast(BagNode | None, self.get_node(path))


class SqlBuilder(DbElements, SchemaElements, TableElements, ColumnElements,
                 BuilderBase):
    """SQL model dialect builder.

    One dialect, one flat namespace: the grammar is split into mixins by
    containment level for readability. Mounted dialects preserve name paths,
    but root-signature validation and serialization of dynamic configuration
    are not yet compatible with every mount; see docs/native-composition.md.
    """

    _name = "sqlmodel"
    _default_render_mode = "sql"
    _name_label_tags = frozenset({
        "schema", "table", "column", "aliasColumn", "formulaColumn",
        "subQueryColumn", "pyColumn", "compositeColumn", "extension",
        "constraint", "index",
    })
    _positional_arguments = {
        **dict.fromkeys(_name_label_tags | {"db"}, "name"),
        "relation": "to",
    }

    def __init__(self, name: str | None = None) -> None:
        super().__init__(name)
        source = SqlSourceBag(builder=self)
        self._sourceroot[SOURCE_ROOT] = source
        self.source = source

    def main(self, root):
        pass

    def _validate_call_args(self, info, node_value, attr, node_tag=""):
        parameter = self._positional_arguments.get(node_tag)
        if parameter is not None and node_value is not None:
            if parameter in attr:
                raise ValueError(f"'{node_tag}': {parameter} passed twice")
            attr[parameter] = node_value
            node_value = None
        return super()._validate_call_args(info, node_value, attr, node_tag)

    def set_child(self, build_where, node_tag, node_value=None, node_label=None,
                  node_position=None, **attr):
        """Apply SQL path and namespace rules before framework insertion."""
        positional = self._positional_arguments.get(node_tag)
        if positional is not None and attr.get(positional) == node_value:
            node_value = None
        if node_tag == "db" and build_where.node("db") is not None:
            raise ValueError("a database is already present in this SQL model")
        name = attr.get("name")
        if node_tag in self._name_label_tags:
            if isinstance(name, str) and "." in name:
                raise ValueError(
                    f"'{node_tag}' name {name!r} contains the Bag path separator '.'",
                )
            if node_label is not None:
                raise ValueError(
                    f"'{node_tag}': node_label is fixed by its SQL name",
                )
        if node_label is not None and build_where.node(node_label) is not None:
            raise ValueError(
                f"duplicate {node_tag} name {name!r} in the same SQL namespace",
            )
        return super().set_child(
            build_where, node_tag, node_value, node_label=node_label,
            node_position=node_position, **attr,
        )

    def validate_model(self):
        """Run the domain validation on this model and return it.

        Convenience over ``SqlModelValidator().validate(self)``; raises
        :class:`~asqueel.validators.SqlModelValidationError`
        listing every violation.
        """
        return SqlModelValidator().validate(self)

    @property
    def renderer_sql(self) -> SqlRenderer:
        """Fresh ``SqlRenderer`` instance bound to this builder.

        Each access returns a new instance: the renderer is meant to be
        ephemeral, used for a single ``render`` call and discarded.

        Today ``SqlRenderer`` is a placeholder that renders nothing: DDL
        rendering is out of scope until its own slice lands. Database work
        goes through :class:`~asqueel.migration.SqlMigrationRenderer`.
        """
        return SqlRenderer(builder=self)
