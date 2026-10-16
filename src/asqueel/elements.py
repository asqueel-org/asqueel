# Copyright 2025 Softwell S.r.l. - SPDX-License-Identifier: Apache-2.0
"""SQL model grammar — explicit structural collections.

Four grammar mixins, one per containment level, composed into
:class:`~asqueel.builder.SqlBuilder`:

- :class:`DbElements` — ``db``, ``extension``
- :class:`SchemaElements` — ``schema``
- :class:`TableElements` — ``table`` and everything a table holds
- :class:`ColumnElements` — ``relation``

Hierarchy::

    db
    ├── schemas → schema → tables → table
    │   ├── columns → column → relation
    │   ├── virtual_columns → aliasColumn / formulaColumn /
    │   │   subQueryColumn / pyColumn
    │   ├── composites → compositeColumn → relation
    │   ├── constraints → constraint
    │   └── indexes → index
    └── extensions → extension

Two planes. The **physical** plane projects into the asqueel-migration
JSON (``structure-1.0``): ``db``/``schema``/``table``, physical ``column``
attributes, ``foreign_key`` relations, ``constraint``, ``index``. The
**semantic** plane (``name_*``, ``group``, ``caption_field``, …) travels as
node attributes the migration projection ignores; the compiler and the GUI
read it.

Signatures are **semi-closed**: every element declares its physical AND its
enumerated semantic parameters, typed, and accepts ``**extra`` on top. The
grammar takes any extra key; the domain validator requires it to start with
``x_``, so a typo (``dtypo=``) is a loud error naming the declared set
instead of a silently stored attribute.

Every repeated family has an author-visible fixed-label collection. Children
are keyed by name inside their own collection, so unrelated SQL namespaces do
not collide. A relation remains the singular child of the column or composite
that owns it; normalized JSON may project it under a table-level collection,
but that projection does not change the source grammar.

Projection flags ride on each element's ``_meta`` and are read from the node
(``node._get_meta("projects_column")``): the renderer and the validators
dispatch on them, never on tag strings.
"""

from __future__ import annotations

from typing import Literal

from genro_builders.builder import element

#: asqueel normalized type codes. Mirrors
#: ``asqueel_migration.structures.DTYPE_CODES`` plus the additive serial4
#: declaration on older engine versions — declared locally because
#: the grammar must not import the migration package (the dependency is
#: one-way). The renderer's golden test pins the compatibility boundary.
DTYPE = Literal[
    "A", "B", "C", "D", "DH", "DHZ", "DT", "H", "HZ", "I", "L", "M", "N",
    "O", "P", "R", "T", "TSV", "VEC", "X", "Z", "jsonb", "serial", "serial4",
]

#: Referential actions a foreign key may declare. ``NO ACTION`` is absent on
#: purpose: it is the SQL default and the migration structure strips it.
FK_ACTION = Literal["CASCADE", "SET NULL", "SET DEFAULT", "RESTRICT"]

#: Table constraint kinds. Single-column uniqueness is the ``unique`` column
#: attribute, not a constraint entity.
CONSTRAINT_TYPE = Literal["UNIQUE", "CHECK"]

_VIRTUAL_TAGS = "aliasColumn, formulaColumn, subQueryColumn, pyColumn, bagItemColumn"


class DbElements:
    """Database-level grammar: the root and its collections."""

    @element(sub_tags="schemas[:1], packages[:1], extensions[:1], options[:1]", node_label="db")
    def db(self, name: str, implementation: str = 'postgresql',
           name_long: str | None = None, name_short: str | None = None,
           comment: str | None = None, **extra):
        """Database root, one per model.

        Args:
            name: the database name — the JSON ``entity_name``.
        """
        ...

    @element(
        parent_tags="db",
        sub_tags="schema",
        collection_key="name",
        node_label="schemas",
    )
    def schemas(self):
        """Physical/legacy source collection, not a package configuration section.

        Package configurations infer schemas from package.sqlschema.
        This collection remains for physical migration input and older sources.
        """
        ...

    @element(
        parent_tags="db",
        sub_tags="extension",
        collection_key="name",
        node_label="extensions",
    )
    def extensions(self):
        """The explicit collection of database extensions."""
        ...

    @element(parent_tags="extensions", sub_tags="")
    def extension(self, name: str, name_long: str | None = None,
                  name_short: str | None = None, comment: str | None = None,
                  **extra):
        """A PostgreSQL extension.

        Rendered ``CREATE EXTENSION IF NOT EXISTS`` and never dropped.

        Args:
            name: the extension name (``pg_trgm``, ``unaccent``, …).
        """
        ...


class SchemaElements:
    """Schema-level grammar."""

    @element(parent_tags="schemas", sub_tags="tables[:1], options[:1]")
    def schema(self, name: str, comment: str | None = None,
               sqlname: str | None = None, name_long: str | None = None,
               name_short: str | None = None, **extra):
        """A physical database schema, separate from logical packages.

        Args:
            name: the schema name — physical, and this node's key.
            comment: semantic; source-only free description; structure-1.0
                schemas have no physical attribute slot.
        """
        ...

    @element(
        parent_tags="schema, package",
        sub_tags="table",
        collection_key="name",
        node_label="tables",
    )
    def tables(self):
        """The explicit collection of a schema's tables."""
        ...


class TableElements:
    """Table-level grammar: the table and everything it holds."""

    @element(
        parent_tags="tables",
        sub_tags=(
            "columns[:1], virtual_columns[:1], composites[:1], "
            "constraints[:1], indexes[:1], options[:1], colgroup, subtable, virtualRelation"
        ),
    )
    def table(self, name: str, pkey: str | None = None,
              comment: str | None = None,
              caption_field: str | None = None,
              name_long: str | None = None,
              name_plural: str | None = None,
              name_short: str | None = None, rowcaption: str | None = None,
              newrecord_caption: str | None = None, order_by: str | None = None,
              lookup: bool = False, tabletype: str | None = None,
              sqlname: str | None = None, sqlschema: str | None = None,
              pkey_columns: str | None = None,
              pkey_columns_joiner: str | None = None, **extra):
        """A table.

        Args:
            name: the table name — physical, and this node's key.
            pkey: comma-joined physical column names, the JSON ``pkeys``.
                Every name must exist among the table's physical columns.
            comment: physical; free description.
            caption_field: semantic; the column that captions a row.
            name_long: semantic; human label.
            name_short: semantic; short human label.
            name_plural: semantic; human label, plural form.
            pkey_columns: semantic; legacy comma-separated source fields for a
                single textual primary key; not SQL primary-key members.
            pkey_columns_joiner: semantic; legacy separator for that textual key.
                Absent or empty, the legacy uses underscore. Declaration only.
        """
        ...

    @element(
        parent_tags="table",
        sub_tags="column",
        collection_key="name",
        node_label="columns",
    )
    def columns(self):
        """The explicit collection of physical columns."""
        ...

    @element(
        parent_tags="table",
        sub_tags=_VIRTUAL_TAGS,
        collection_key="name",
        node_label="virtual_columns",
    )
    def virtual_columns(self):
        """The explicit collection of non-physical columns."""
        ...

    @element(
        parent_tags="table",
        sub_tags="compositeColumn",
        collection_key="name",
        node_label="composites",
    )
    def composites(self):
        """The explicit collection of composite column owners."""
        ...

    @element(
        parent_tags="table",
        sub_tags="constraint",
        collection_key="name",
        node_label="constraints",
    )
    def constraints(self):
        """The explicit collection of table constraints."""
        ...

    @element(
        parent_tags="table",
        sub_tags="index",
        collection_key="name",
        node_label="indexes",
    )
    def indexes(self):
        """The explicit collection of table indexes."""
        ...

    @element(parent_tags="columns", sub_tags="relation, validation[:1], encryption[:1], dynamic_fields[:1]",
             _meta={"projects_column": True, "projects_relation": True})
    def column(self, name: str, dtype: DTYPE | str | None = None,
               size: str | None = None,
               notnull: bool = False, unique: bool = False,
               indexed: bool = False, sqldefault: str | None = None,
               extra_sql: str | None = None,
               generated_expression: str | None = None,
               comment: str | None = None,
               name_long: str | None = None,
               name_short: str | None = None,
               group: str | None = None, sqlname: str | None = None,
               default: object = None,
               default_from: str | None = None, sql_value: str | None = None,
               read_only: bool = False, unmodifiable: bool = False, **extra):
        """A physical column — the only element that projects as a column.

        Args:
            name: the column name — physical, and this node's key.
            dtype: asqueel normalized type code. Absent, the renderer
                defaults to ``'A'`` when ``size`` is given, else ``'T'``.
            size: ``'n'`` or ``'min:max'`` character size.
            notnull: NOT NULL. Pkey members get it from their pkey
                membership, not from this flag.
            unique: single-column UNIQUE. A redundant one on a
                single-column pkey is dropped by the renderer.
            indexed: sugar — the renderer materializes a real index item
                (``structure-1.0`` has no ``indexed`` column attribute).
                A column carrying a foreign key is always indexed.
            sqldefault: SQL DEFAULT expression.
            extra_sql: verbatim tail of the column definition.
            generated_expression: GENERATED ALWAYS AS expression.
            comment: physical; the column comment.
            name_long: semantic; human label.
            name_short: semantic; human label, short form.
            group: semantic; field-group key.
        """
        ...

    @element(parent_tags="virtual_columns", sub_tags="relation")
    def aliasColumn(self, name: str, relation_path: str,
                    dtype: str | None = None,
                    name_long: str | None = None,
                    group: str | None = None, name_short: str | None = None,
                    comment: str | None = None, static: bool = False, **extra):
        """A virtual column projecting a related column. Never physical.

        An alias inherits the target column's relation as a weak relation during
        model rendering, unless it declares an explicit relation of its own.

        Args:
            name: the alias name.
            relation_path: ``@relation.column`` path to the source column.
            name_long: semantic; human label.
            group: semantic; field-group key.
            static: semantic; retain the legacy static declaration without executing it.
        """
        ...

    @element(parent_tags="virtual_columns", sub_tags="relation")
    def formulaColumn(self, name: str, sql_formula: str | bool | None = None,
                      expression: str | None = None, parameters: dict | None = None,
                      subqueries: dict | None = None, handler: str | None = None, static: bool = False,
                      select: dict | str | None = None,
                      exists: dict | str | None = None,
                      dtype: str | None = None,
                      name_long: str | None = None,
                      group: str | None = None, name_short: str | None = None,
                      comment: str | None = None, **extra):
        """A virtual column defined by SQL. Never physical.

        Args:
            name: the column name.
            sql_formula: an expression over the row's own columns.
            select: a scalar sub-select.
            exists: an EXISTS predicate.
            dtype: the resulting type code.
            name_long: semantic; human label.
            group: semantic; field-group key.
        """
        ...

    @element(parent_tags="virtual_columns", sub_tags="relation")
    def subQueryColumn(self, name: str, query: str | dict | None = None,
                       mode: str | None = None, dtype: str | None = None,
                       name_long: str | None = None,
                       group: str | None = None, name_short: str | None = None,
                       comment: str | None = None, **extra):
        """A virtual column defined by a sub-query. Never physical.

        Args:
            name: the column name.
            query: the sub-query declaration; may be supplied by a later contribution.
            mode: None, ``json``, ``xml`` or a legacy aggregate name; preserved
                without expansion or execution by the grammar.
            dtype: the declared result type.
            name_long: semantic; human label.
            group: semantic; field-group key.
        """
        ...

    @element(parent_tags="virtual_columns", sub_tags="relation")
    def pyColumn(self, name: str, py_method: str | None = None,
                 method: str | None = None, required_columns: str | tuple | list | None = None, static: bool = False,
                 dtype: str | None = None,
                 name_long: str | None = None,
                 group: str | None = None, name_short: str | None = None,
                 comment: str | None = None, **extra):
        """A virtual column computed in Python. Never physical.

        Args:
            name: the column name.
            py_method: the method computing it; defaults to
                ``pyColumn_<name>`` on the table class.
            dtype: the resulting type code.
            name_long: semantic; human label.
            group: semantic; field-group key.
        """
        ...

    @element(parent_tags="composites", sub_tags="relation",
             _meta={"projects_relation": True})
    def compositeColumn(self, name: str, columns: str, unique: bool = False,
                        name_long: str | None = None,
                        group: str | None = None, name_short: str | None = None,
                        comment: str | None = None, **extra):
        """N physical columns packed as one navigable key.

        Not a column of its own — it projects no column, only what its
        members already are. THE mechanism for a multi-column key: a
        composite FK is a ``relation`` on a compositeColumn, and a
        composite UNIQUE is ``unique=True`` here.

        Args:
            name: the composite name (GenroPy ``composed_of`` carried the
                members instead).
            columns: comma-joined member names, all physical columns of
                the same table.
            unique: projects a multi-column UNIQUE constraint.
            name_long: semantic; human label.
            group: semantic; field-group key.
        """
        ...

    @element(parent_tags="constraints", sub_tags="")
    def constraint(self, name: str, constraint_type: CONSTRAINT_TYPE,
                   columns: str | None = None,
                   check_clause: str | None = None, **extra):
        """A table constraint.

        Args:
            name: the constraint name — this node's key.
            constraint_type: ``'UNIQUE'`` (needs ``columns``) or
                ``'CHECK'`` (needs ``check_clause``).
            columns: comma-joined physical column names.
            check_clause: the CHECK expression.
        """
        ...

    @element(parent_tags="indexes", sub_tags="")
    def index(self, name: str | None = None, columns: object | None = None,
              unique: bool = False, method: str | None = None,
              where: str | None = None, tablespace: str | None = None,
              with_options: dict | None = None, **extra):
        """A table index.

        Args:
            name: the index name.
            columns: comma-joined names, or a ``{name: None | 'DESC'}``
                dict when per-column ordering matters.
            unique: a UNIQUE index.
            method: access method (``btree``, ``gin``, …).
            where: partial-index predicate.
            tablespace: target tablespace.
            with_options: storage parameters.
        """
        ...


class ColumnElements:
    """Column-level grammar: the relation."""

    @element(parent_tags="column, compositeColumn, aliasColumn, formulaColumn, subQueryColumn, pyColumn, bagItemColumn", sub_tags="")
    def relation(self, to: str, foreign_key: bool = False,
                 on_delete: FK_ACTION | str | None = None,
                 on_update: FK_ACTION | str | None = None,
                 deferred: bool = False, deferrable: bool = False,
                 initially_deferred: bool = False, indexed: bool = True,
                 back_reference: str | None = None,
                 one_name: str | None = None,
                 many_name: str | None = None,
                 one_one: bool = False, case_insensitive: bool = False,
                 name: str | None = None, inverse: str | None = None,
                 on_delete_sql: str | None = None, on_update_sql: str | None = None,
                 on_duplicate: str | bool | None = None, constraint_name: str | None = None,
                 one_group: str | None = None, many_group: str | None = None,
                 **extra):
        """A relation on a column. Navigable by default, physical on demand.

        At most one per local structural key: the grammar accepts the insertion
        so the whole document can be built, and ``SqlBuilder.validate_model``
        reports every conflicting relation together.

        Args:
            to: the target, ``schema.table.column`` or ``schema.table``
                (target columns default to the target pkey).
            foreign_key: emit a physical FK. Only these relations project
                into the migration JSON.
            on_delete: referential action on delete.
            on_update: referential action on update.
            deferred: compatibility sugar for DEFERRABLE INITIALLY DEFERRED.
            deferrable: make the foreign key DEFERRABLE. Without
                ``initially_deferred`` it is initially immediate.
            initially_deferred: start a deferrable foreign key deferred.
            indexed: the supporting index of the foreign key. On by
                default (GenroPy parity, D3); ``False`` states that the
                columns are deliberately left unindexed.
            back_reference: semantic; navigable path of the many side.
            one_name: semantic; human label of the one side.
            many_name: semantic; human label of the many side.
            one_one: semantic; the relation is 1:1.
            case_insensitive: semantic; join case-insensitively.
        """
        ...
