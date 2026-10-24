# Copyright 2025 Softwell S.r.l. - SPDX-License-Identifier: Apache-2.0
"""SQL model grammar — explicit structural collections.

Four grammar mixins, one per containment level, composed into
:class:`~asqueel.builder.SqlBuilder`:

- :class:`DbElements` — ``db``, ``extension``
- :class:`SchemaElements` — ``tables``
- :class:`TableElements` — ``table`` and everything a table holds
- :class:`ColumnElements` — ``relation``

Hierarchy::

    db
    ├── packages → package → tables → table
    │   ├── columns → column → relation
    │   ├── virtual_columns → aliasColumn / formulaColumn /
    │   │   subQueryColumn / pyColumn
    │   ├── composites → compositeColumn → relation
    │   ├── constraints → constraint
    │   └── indexes → index
    └── extensions → extension

Two planes. The **physical** plane projects into the asqueel-migration
JSON (``structure-1.0``): ``db``/``package``/``table``, physical ``column``
attributes, ``foreign_key`` relations, ``constraint``, ``index``. The
**semantic** plane (``name_*``, ``group``, ``caption_field``, …) travels as
node attributes the migration projection ignores; the compiler and the GUI
read it.

Signatures are **closed**: every element declares its physical AND its
enumerated semantic parameters, typed. An element with ``**extra`` accepts
only the attribute families its ``_meta['attribute_families']`` names
(``validate_*`` on column, ``var_*``/``select_*``/``exists_*`` on formulaColumn), so a
typo (``dtypo=``) is a loud error naming the declared set instead of a
silently stored attribute.

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

from genro_builders.builder import CustomTypes, Range, Regex, element

from .catalog import _VIRTUAL_COLUMN_TAGS

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

#: Table constraint kinds. Single-column uniqueness is the ``unique`` column
#: attribute, not a constraint entity.
CONSTRAINT_TYPE = Literal["UNIQUE", "CHECK"]

#: Constraints the grammar checks at declaration. An ``int`` base refuses ``bool``.
CUSTOM_TYPES = CustomTypes()
NON_NEGATIVE_INT = CUSTOM_TYPES.register("nonNegativeInt", int, Range(ge=0))
POSITIVE_INT = CUSTOM_TYPES.register("positiveInt", int, Range(ge=1))
NON_NEGATIVE_NUMBER = CUSTOM_TYPES.register("nonNegativeNumber", float, Range(ge=0))
SQL_PREFIX = CUSTOM_TYPES.register("sqlPrefix", str, Regex(r"[\s\S]*[^_]"))


class DbElements:
    """Database-level grammar: the root and its collections."""

    @element(sub_tags="packages[:1], extensions[:1], options[:1]", node_label="db")
    def db(self, name: str, implementation: str = 'sqlite',
           name_long: str | None = None, name_short: str | None = None,
           comment: str | None = None):
        """Database root, one per model.

        Args:
            name: the database name — the JSON ``entity_name``.
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
                  name_short: str | None = None, comment: str | None = None):
        """A PostgreSQL extension.

        Rendered ``CREATE EXTENSION IF NOT EXISTS`` and never dropped.

        Args:
            name: the extension name (``pg_trgm``, ``unaccent``, …).
        """
        ...


class SchemaElements:
    """Package-level grammar: the collection of tables."""

    @element(
        parent_tags="package",
        sub_tags="table",
        collection_key="name",
        node_label="tables",
    )
    def tables(self):
        """The explicit collection of a package's tables."""
        ...


class TableElements:
    """Table-level grammar: the table and everything it holds."""

    @element(
        parent_tags="tables",
        sub_tags=(
            "columns[:1], virtual_columns[:1], composites[:1], "
            "constraints[:1], indexes[:1], options[:1], colgroup, virtualRelation"
        ),
        _meta={"attribute_families": ["partition_"]},
    )
    def table(self, name: str, pkey: str | None = None,
              comment: str | None = None,
              caption_field: str | None = None,
              name_long: str | None = None,
              name_plural: str | None = None,
              name_short: str | None = None, name_full: str | None = None,
              rowcaption: str | None = None,
              newrecord_caption: str | None = None, order_by: str | None = None,
              lookup: bool = False, tabletype: str | None = None,
              sqlname: str | None = None, sqlschema: str | None = None,
              pkey_columns: str | None = None,
              pkey_columns_joiner: str | None = None, deletable: bool = True,
              lastTS: str | None = None, logicalDeletionField: str | None = None,
              draftField: str | None = None, protectionColumn: str | None = None,
              **extra):
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
            deletable: False refuses every delete of the table's records.
            lastTS: the column holding the last modification timestamp.
            logicalDeletionField: the column marking a row as logically deleted;
                queries exclude those rows.
            draftField: the boolean column marking a draft row; queries exclude drafts.
            protectionColumn: the column whose value protects a row.
            partition_<field>: ``'<path>'`` partitions the table on ``<field>``:
                env ``current_<path>`` filters on it, else env
                ``allowed_<path>`` filters on its values or NULL. The first counts.
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
        sub_tags=", ".join(_VIRTUAL_COLUMN_TAGS),
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

    @element(parent_tags="columns", sub_tags="relation, df[:1]",
             _meta={"projects_column": True, "projects_relation": True,
                    "attribute_families": ["validate_"]})
    def column(self, name: str, dtype: DTYPE | str | None = None,
               size: str | None = None,
               notnull: bool = False, unique: bool | str = False,
               indexed: bool | str | dict = False, sql_default: str | None = None,
               sql_extra: str | None = None,
               sql_generatedExpression: str | None = None,
               sql_pg_default: str | None = None, sql_pg_extra: str | None = None,
               sql_pg_generatedExpression: str | None = None,
               sql_sqlite_default: str | None = None, sql_sqlite_extra: str | None = None,
               sql_sqlite_generatedExpression: str | None = None,
               comment: str | None = None,
               name_long: str | None = None,
               name_short: str | None = None, name_full: str | None = None,
               format: str | None = None, print_width: int | None = None,
               group: str | None = None, sqlname: str | None = None,
               default: object = None,
               default_from: str | None = None, sql_value: str | None = None,
               readOnly: bool = False, unmodifiable: bool = False,
               onInserting: object = None, onUpdating: object = None, onDeleting: object = None,
               onInserted: object = None, onUpdated: object = None, onDeleted: object = None,
               trigger_table: str | None = None,
               **extra):
        """A physical column — the only element that projects as a column.

        Args:
            name: the column name — physical, and this node's key.
            dtype: asqueel normalized type code. Absent, the renderer
                defaults to ``'A'`` when ``size`` is given, else ``'T'``.
            size: ``'n'`` or ``'min:max'`` character size.
            notnull: NOT NULL. Pkey members get it from their pkey
                membership, not from this flag.
            unique: single-column UNIQUE. A redundant one on a
                single-column pkey is dropped by the renderer. A string is
                read as a boolean: ``n``, ``no``, ``f``, ``false``, ``0`` are false.
            indexed: sugar — the renderer materializes a real index item
                (``structure-1.0`` has no ``indexed`` column attribute).
                A column carrying a relation is always indexed. A string
                is read as ``unique``. A dict carries the index options, as
                legacy ``fill_json_column_index``: ``method``, ``where``,
                ``tablespace``, ``sorting`` (comma-separated, one direction
                per column), ``with_<name>`` (a ``WITH`` storage option) and
                ``unique`` (without ``where`` it makes the column unique and
                creates no index; with ``where`` a partial unique index).
            sql_default: SQL DEFAULT expression.
            sql_extra: verbatim tail of the column definition.
            sql_generatedExpression: GENERATED ALWAYS AS expression.
            sql_pg_default: ``sql_default`` on PostgreSQL; wins over it there.
            sql_pg_extra: ``sql_extra`` on PostgreSQL; wins over it there.
            sql_pg_generatedExpression: ``sql_generatedExpression`` on PostgreSQL; wins over it there.
            sql_sqlite_default: ``sql_default`` on SQLite; wins over it there.
            sql_sqlite_extra: ``sql_extra`` on SQLite; wins over it there.
            sql_sqlite_generatedExpression: ``sql_generatedExpression`` on SQLite; wins over it there.
            comment: physical; the column comment.
            name_long: semantic; human label.
            name_short: semantic; human label, short form.
            name_full: semantic; human label, full form.
            format: semantic; display format.
            print_width: semantic; print width.
            group: semantic; field-group key.
            onInserting, onUpdating, onDeleting, onInserted, onUpdated, onDeleted:
                field triggers: a method name, called as
                ``trigger_<name>(record, fldname=, tblname=)`` on the table or
                on ``trigger_table``, or a callable ``f(record, fldname)``.
                They run at every write, in column declaration order.
        """
        ...

    @element(parent_tags="virtual_columns", sub_tags="relation")
    def aliasColumn(self, name: str, relation_path: str,
                    dtype: str | None = None,
                    name_long: str | None = None,
                    group: str | None = None, name_short: str | None = None,
                    comment: str | None = None, static: bool = False):
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

    @element(parent_tags="virtual_columns", sub_tags="relation",
             _meta={"attribute_families": ["var_", "select_", "exists_"]})
    def formulaColumn(self, name: str, sql_formula: str | bool | None = None, static: bool = False,
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
            dtype: the resulting type code; ``A`` when omitted.
            name_long: semantic; human label.
            group: semantic; field-group key.
        """
        ...

    @element(parent_tags="virtual_columns", sub_tags="relation",
             _meta={"attribute_families": ["var_"]})
    def subQueryColumn(self, name: str, query: str | dict | None = None,
                       aggr: str | None = None, mode: str | None = None, dtype: str | None = None,
                       name_long: str | None = None,
                       group: str | None = None, name_short: str | None = None,
                       comment: str | None = None, **extra):
        """A virtual column defined by a sub-query. Never physical.

        Args:
            name: the column name.
            query: the sub-query declaration; may be supplied by a later contribution.
            aggr: one call of the ``.aggr()`` grammar (count, sum, avg, min,
                max, join, to_json, to_xml); it replaces the query columns.
            mode: None, ``json`` or ``xml``, as legacy; not together with ``aggr``.
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
                 comment: str | None = None):
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
                        comment: str | None = None):
        """N physical columns packed as one navigable key.

        Not a column of its own — it projects no column, only what its
        members already are. THE mechanism for a multi-column key: a
        composite FK is a ``relation`` on a compositeColumn, and a
        composite UNIQUE is ``unique=True`` here.

        Args:
            name: the composite name.
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
                   check_clause: str | None = None):
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
    def index(self, columns: object | None = None, name: str | None = None,
              unique: bool | None = None, method: str | None = None,
              where: str | None = None, tablespace: str | None = None,
              with_options: dict | None = None):
        """A table index.

        Args:
            columns: comma-joined names, a list or tuple of names, or a
                ``{name: None | 'DESC'}`` dict when per-column ordering matters.
            name: the index name; ``<table>_<columns joined by _>_key``
                when absent.
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
    def relation(self, related_column: str, foreign_key: bool = False,
                 onDelete: str | None = None, onUpdate: str | None = None,
                 onDelete_sql: str | None = None, onUpdate_sql: str | None = None,
                 deferred: bool = False, deferrable: bool = False,
                 initially_deferred: bool = False, indexed: bool = True,
                 one_name: str | None = None,
                 many_name: str | None = None,
                 one_one: bool | Literal['*'] = False, insensitive: bool = False,
                 name: str | None = None, relation_name: str | None = None,
                 onDuplicate: str | bool | None = None, constraint_name: str | None = None,
                 one_group: str | None = None, many_group: str | None = None,
                 many_order_by: str | None = None, eager_one: bool | None = None,
                 eager_many: bool | None = None, external_relation: bool | None = None,
                 resolver_kwargs: dict | None = None, join_on: str | None = None,
                 cnd: str | None = None, between: str | None = None):
        """A relation on a column. Navigable by default, physical on demand.

        At most one per local structural key: the grammar accepts the insertion
        so the whole document can be built, and ``SqlBuilder.validate_model``
        reports every conflicting relation together.

        Args:
            related_column: the target, ``package.table.column`` or ``package.table``
                (target columns default to the target pkey).
            foreign_key: emit a physical FK. Only these relations project
                a foreign key into the migration JSON; every relation on a
                physical column indexes it.
            onDelete: semantic; Python action on delete of the target row:
                ``raise``, ``cascade``, ``setnull``, ``ignore``,
                optionally followed by ``:message``.
            onUpdate: semantic; Python action on update, same values.
            onDelete_sql: SQL action of the foreign key on delete:
                ``cascade``, ``restrict``, ``no action``, ``setnull``,
                ``setdefault`` (any case; ``set null``/``set default`` too),
                or the legacy abbreviations ``C``, ``R``, ``N``, ``SN``, ``SD``.
            onUpdate_sql: SQL action of the foreign key on update, same
                values; ``cascade`` when absent.
            deferred: DEFERRABLE INITIALLY DEFERRED. True by default when
                ``onDelete`` or ``onDelete_sql`` is ``setnull``.
            deferrable: make the foreign key DEFERRABLE. Without
                ``initially_deferred`` it is initially immediate.
            initially_deferred: start a deferrable foreign key deferred.
            indexed: the index of the relation columns, with or without a
                foreign key. On by default, as legacy; ``False`` states that
                the columns are deliberately left unindexed.
            relation_name: semantic; name of the inverse relation on the target
                (``@<relation_name>``).
            one_name: semantic; human label of the one side.
            many_name: semantic; human label of the many side.
            one_one: semantic; the relation is 1:1. ``'*'`` without
                ``relation_name`` names the inverse after the many table and
                makes it public.
            insensitive: semantic; join case-insensitively.
            join_on: semantic; the ON condition in place of the key
                equality. Wins over ``cnd``.
            cnd: semantic; the ON condition in place of the key equality.
                The relation projects no foreign key.
            between: semantic; ``'value;low;high'``, a range condition in
                place of the key equality.
        """
        ...
