# SQL model grammar reference

Generated from the live grammar by `asqueel.grammar_doc.generate_grammar_md()`. Do not edit by hand: regenerate with `python -m asqueel.grammar_doc`.

Element signatures are **closed**: an attribute the signature does not declare raises. An element accepts only the attribute families its declaration names (`validate_*`, `var_*`, `select_*`, `col_*`), and `validation(**rules)` keeps its rules as data.

## Hierarchy

```
db
├── schemas[:1]
├── packages[:1]
├── extensions[:1]
└── options[:1]
```

## Elements

### `db`

Database root, one per model.

- Contains: schemas[:1], packages[:1], extensions[:1], options[:1]
- Child addressing: ordered internal labels for schemas, packages, extensions, options
- Projection flags: none declared
- Extra keys: not accepted

| parameter | type | default | plane | description |
| --- | --- | --- | --- | --- |
| name | `str` | *required* | physical | the database name — the JSON `entity_name`. |
| implementation | `str` | `'sqlite'` | physical |  |
| name_long | `str \| None` | `None` | physical |  |
| name_short | `str \| None` | `None` | physical |  |
| comment | `str \| None` | `None` | physical |  |

### `schemas`

Physical/legacy source collection, not a package configuration section.

Package configurations infer schemas from package.sqlschema.
This collection remains for physical migration input and older sources.

- Contains: schema
- Child addressing: SQL-name labels for schema
- Projection flags: none declared
- Extra keys: not accepted

| parameter | type | default | plane | description |
| --- | --- | --- | --- | --- |

### `extensions`

The explicit collection of database extensions.

- Contains: extension
- Child addressing: SQL-name labels for extension
- Projection flags: none declared
- Extra keys: not accepted

| parameter | type | default | plane | description |
| --- | --- | --- | --- | --- |

### `extension`

A PostgreSQL extension.

Rendered `CREATE EXTENSION IF NOT EXISTS` and never dropped.

- Contains: *nothing*
- Child addressing: no children
- Projection flags: none declared
- Extra keys: not accepted

| parameter | type | default | plane | description |
| --- | --- | --- | --- | --- |
| name | `str` | *required* | physical | the extension name (`pg_trgm`, `unaccent`, …). |
| name_long | `str \| None` | `None` | physical |  |
| name_short | `str \| None` | `None` | physical |  |
| comment | `str \| None` | `None` | physical |  |

### `schema`

A physical database schema, separate from logical packages.

- Contains: tables[:1], options[:1]
- Child addressing: ordered internal labels for tables, options
- Projection flags: none declared
- Extra keys: not accepted

| parameter | type | default | plane | description |
| --- | --- | --- | --- | --- |
| name | `str` | *required* | physical | the schema name — physical, and this node's key. |
| comment | `str \| None` | `None` | semantic | source-only free description; structure-1.0 schemas have no physical attribute slot. |
| sqlname | `str \| None` | `None` | physical |  |
| name_long | `str \| None` | `None` | physical |  |
| name_short | `str \| None` | `None` | physical |  |

### `tables`

The explicit collection of a schema's tables.

- Contains: table
- Child addressing: SQL-name labels for table
- Projection flags: none declared
- Extra keys: not accepted

| parameter | type | default | plane | description |
| --- | --- | --- | --- | --- |

### `table`

A table.

- Contains: columns[:1], virtual_columns[:1], composites[:1], constraints[:1], indexes[:1], options[:1], colgroup, virtualRelation
- Child addressing: ordered internal labels for columns, virtual_columns, composites, constraints, indexes, options, colgroup, virtualRelation
- Projection flags: none declared
- Extra keys: `partition_*`

| parameter | type | default | plane | description |
| --- | --- | --- | --- | --- |
| name | `str` | *required* | physical | the table name — physical, and this node's key. |
| pkey | `str \| None` | `None` | physical | comma-joined physical column names, the JSON `pkeys`. Every name must exist among the table's physical columns. |
| comment | `str \| None` | `None` | physical | free description. |
| caption_field | `str \| None` | `None` | semantic | the column that captions a row. |
| name_long | `str \| None` | `None` | semantic | human label. |
| name_plural | `str \| None` | `None` | semantic | human label, plural form. |
| name_short | `str \| None` | `None` | semantic | short human label. |
| name_full | `str \| None` | `None` | physical |  |
| rowcaption | `str \| None` | `None` | physical |  |
| newrecord_caption | `str \| None` | `None` | physical |  |
| order_by | `str \| None` | `None` | physical |  |
| lookup | `bool` | `False` | physical |  |
| tabletype | `str \| None` | `None` | physical |  |
| sqlname | `str \| None` | `None` | physical |  |
| sqlschema | `str \| None` | `None` | physical |  |
| pkey_columns | `str \| None` | `None` | semantic | legacy comma-separated source fields for a single textual primary key; not SQL primary-key members. |
| pkey_columns_joiner | `str \| None` | `None` | semantic | legacy separator for that textual key. Absent or empty, the legacy uses underscore. Declaration only. |
| deletable | `bool` | `True` | physical | False refuses every delete of the table's records, as in GenroPy. |
| lastTS | `str \| None` | `None` | physical | the column holding the last modification timestamp. |
| logicalDeletionField | `str \| None` | `None` | physical | the column marking a row as logically deleted; queries exclude those rows. |
| draftField | `str \| None` | `None` | physical | the boolean column marking a draft row; queries exclude drafts. |
| protectionColumn | `str \| None` | `None` | physical | the column whose value protects a row. |
| x_table_class | `type \| None` | `None` | physical |  |
| x_expanded_legacy | `bool \| None` | `None` | physical |  |
| x_logical_pkey | `str \| None` | `None` | physical |  |

### `columns`

The explicit collection of physical columns.

- Contains: column
- Child addressing: SQL-name labels for column
- Projection flags: none declared
- Extra keys: not accepted

| parameter | type | default | plane | description |
| --- | --- | --- | --- | --- |

### `virtual_columns`

The explicit collection of non-physical columns.

- Contains: aliasColumn, formulaColumn, subQueryColumn, pyColumn, bagItemColumn
- Child addressing: SQL-name labels for aliasColumn, formulaColumn, subQueryColumn, pyColumn, bagItemColumn
- Projection flags: none declared
- Extra keys: not accepted

| parameter | type | default | plane | description |
| --- | --- | --- | --- | --- |

### `composites`

The explicit collection of composite column owners.

- Contains: compositeColumn
- Child addressing: SQL-name labels for compositeColumn
- Projection flags: none declared
- Extra keys: not accepted

| parameter | type | default | plane | description |
| --- | --- | --- | --- | --- |

### `constraints`

The explicit collection of table constraints.

- Contains: constraint
- Child addressing: SQL-name labels for constraint
- Projection flags: none declared
- Extra keys: not accepted

| parameter | type | default | plane | description |
| --- | --- | --- | --- | --- |

### `indexes`

The explicit collection of table indexes.

- Contains: index
- Child addressing: SQL-name labels for index
- Projection flags: none declared
- Extra keys: not accepted

| parameter | type | default | plane | description |
| --- | --- | --- | --- | --- |

### `column`

A physical column — the only element that projects as a column.

- Contains: relation, validation[:1], encryption[:1], dynamic_fields[:1]
- Child addressing: ordered internal labels for relation, validation, encryption, dynamic_fields
- Projection flags: `projects_column`, `projects_relation`
- Extra keys: `validate_*`, `sql_pg_*`, `sql_sqlite_*`

| parameter | type | default | plane | description |
| --- | --- | --- | --- | --- |
| name | `str` | *required* | physical | the column name — physical, and this node's key. |
| dtype | `DTYPE \| str \| None` | `None` | physical | asqueel normalized type code. Absent, the renderer defaults to `'A'` when `size` is given, else `'T'`. |
| size | `str \| None` | `None` | physical | `'n'` or `'min:max'` character size. |
| notnull | `bool` | `False` | physical | NOT NULL. Pkey members get it from their pkey membership, not from this flag. |
| unique | `bool \| str` | `False` | physical | single-column UNIQUE. A redundant one on a single-column pkey is dropped by the renderer. A string is read as in GenroPy: `n`, `no`, `f`, `false`, `0` are false. |
| indexed | `bool \| str \| dict` | `False` | physical | sugar — the renderer materializes a real index item (`structure-1.0` has no `indexed` column attribute). A column carrying a relation is always indexed. A string is read as `unique`. A dict carries the index options, as legacy `fill_json_column_index`: `method`, `where`, `tablespace`, `sorting` (comma-separated, one direction per column), `with_<name>` (a `WITH` storage option) and `unique` (without `where` it makes the column unique and creates no index; with `where` a partial unique index). |
| sql_default | `str \| None` | `None` | physical | SQL DEFAULT expression. |
| sql_extra | `str \| None` | `None` | physical | verbatim tail of the column definition. |
| sql_generatedExpression | `str \| None` | `None` | physical | GENERATED ALWAYS AS expression. sql_<dialect>_default, sql_<dialect>_generatedExpression, sql_<dialect>_extra: the same for one dialect (`pg`, `sqlite`); they win on it. |
| comment | `str \| None` | `None` | physical | the column comment. |
| name_long | `str \| None` | `None` | semantic | human label. |
| name_short | `str \| None` | `None` | semantic | human label, short form. |
| name_full | `str \| None` | `None` | semantic | human label, full form. |
| format | `str \| None` | `None` | semantic | display format. |
| print_width | `int \| None` | `None` | semantic | print width. |
| group | `str \| None` | `None` | semantic | field-group key. onInserting, onUpdating, onDeleting, onInserted, onUpdated, onDeleted: field triggers, as in GenroPy: a method name, called as `trigger_<name>(record, fldname=, tblname=)` on the table or on `trigger_table`, or a callable `f(record, fldname)`. They run at every write, in column declaration order. |
| sqlname | `str \| None` | `None` | physical |  |
| default | `object` | `None` | physical |  |
| default_from | `str \| None` | `None` | physical |  |
| sql_value | `str \| None` | `None` | physical |  |
| read_only | `bool` | `False` | physical |  |
| unmodifiable | `bool` | `False` | physical |  |
| onInserting | `object` | `None` | physical |  |
| onUpdating | `object` | `None` | physical |  |
| onDeleting | `object` | `None` | physical |  |
| onInserted | `object` | `None` | physical |  |
| onUpdated | `object` | `None` | physical |  |
| onDeleted | `object` | `None` | physical |  |
| trigger_table | `str \| None` | `None` | physical |  |
| x_identity | `str \| None` | `None` | physical |  |
| x_generation | `dict \| None` | `None` | physical |  |

### `aliasColumn`

A virtual column projecting a related column. Never physical.

An alias inherits the target column's relation as a weak relation during
model rendering, unless it declares an explicit relation of its own.

- Contains: relation
- Child addressing: ordered internal labels for relation
- Projection flags: none declared
- Extra keys: not accepted

| parameter | type | default | plane | description |
| --- | --- | --- | --- | --- |
| name | `str` | *required* | physical | the alias name. |
| relation_path | `str` | *required* | physical | `@relation.column` path to the source column. |
| dtype | `str \| None` | `None` | physical |  |
| name_long | `str \| None` | `None` | semantic | human label. |
| group | `str \| None` | `None` | semantic | field-group key. |
| name_short | `str \| None` | `None` | physical |  |
| comment | `str \| None` | `None` | physical |  |
| static | `bool` | `False` | semantic | retain the legacy static declaration without executing it. |
| x_identity | `str \| None` | `None` | physical |  |

### `formulaColumn`

A virtual column defined by SQL. Never physical.

- Contains: relation
- Child addressing: ordered internal labels for relation
- Projection flags: none declared
- Extra keys: `var_*`, `select_*`, `exists_*`

| parameter | type | default | plane | description |
| --- | --- | --- | --- | --- |
| name | `str` | *required* | physical | the column name. |
| sql_formula | `str \| bool \| None` | `None` | physical | an expression over the row's own columns. |
| static | `bool` | `False` | physical |  |
| select | `dict \| str \| None` | `None` | physical | a scalar sub-select. |
| exists | `dict \| str \| None` | `None` | physical | an EXISTS predicate. |
| dtype | `str \| None` | `None` | physical | the resulting type code; `A` when omitted. |
| name_long | `str \| None` | `None` | semantic | human label. |
| group | `str \| None` | `None` | semantic | field-group key. |
| name_short | `str \| None` | `None` | physical |  |
| comment | `str \| None` | `None` | physical |  |
| x_identity | `str \| None` | `None` | physical |  |

### `subQueryColumn`

A virtual column defined by a sub-query. Never physical.

- Contains: relation
- Child addressing: ordered internal labels for relation
- Projection flags: none declared
- Extra keys: `var_*`

| parameter | type | default | plane | description |
| --- | --- | --- | --- | --- |
| name | `str` | *required* | physical | the column name. |
| query | `str \| dict \| None` | `None` | physical | the sub-query declaration; may be supplied by a later contribution. |
| aggr | `str \| None` | `None` | physical | one call of the `.aggr()` grammar (count, sum, avg, min, max, join, to_json, to_xml); it replaces the query columns. |
| mode | `str \| None` | `None` | physical | None, `json` or `xml`, as legacy; not together with `aggr`. |
| dtype | `str \| None` | `None` | physical | the declared result type. |
| name_long | `str \| None` | `None` | semantic | human label. |
| group | `str \| None` | `None` | semantic | field-group key. |
| name_short | `str \| None` | `None` | physical |  |
| comment | `str \| None` | `None` | physical |  |
| x_identity | `str \| None` | `None` | physical |  |

### `pyColumn`

A virtual column computed in Python. Never physical.

- Contains: relation
- Child addressing: ordered internal labels for relation
- Projection flags: none declared
- Extra keys: not accepted

| parameter | type | default | plane | description |
| --- | --- | --- | --- | --- |
| name | `str` | *required* | physical | the column name. |
| py_method | `str \| None` | `None` | physical | the method computing it; defaults to `pyColumn_<name>` on the table class. |
| method | `str \| None` | `None` | physical |  |
| required_columns | `str \| tuple \| list \| None` | `None` | physical |  |
| static | `bool` | `False` | physical |  |
| dtype | `str \| None` | `None` | physical | the resulting type code. |
| name_long | `str \| None` | `None` | semantic | human label. |
| group | `str \| None` | `None` | semantic | field-group key. |
| name_short | `str \| None` | `None` | physical |  |
| comment | `str \| None` | `None` | physical |  |
| x_identity | `str \| None` | `None` | physical |  |

### `compositeColumn`

N physical columns packed as one navigable key.

Not a column of its own — it projects no column, only what its
members already are. THE mechanism for a multi-column key: a
composite FK is a `relation` on a compositeColumn, and a
composite UNIQUE is `unique=True` here.

- Contains: relation
- Child addressing: ordered internal labels for relation
- Projection flags: `projects_relation`
- Extra keys: not accepted

| parameter | type | default | plane | description |
| --- | --- | --- | --- | --- |
| name | `str` | *required* | physical | the composite name (GenroPy `composed_of` carried the members instead). |
| columns | `str` | *required* | physical | comma-joined member names, all physical columns of the same table. |
| unique | `bool` | `False` | physical | projects a multi-column UNIQUE constraint. |
| name_long | `str \| None` | `None` | semantic | human label. |
| group | `str \| None` | `None` | semantic | field-group key. |
| name_short | `str \| None` | `None` | physical |  |
| comment | `str \| None` | `None` | physical |  |

### `constraint`

A table constraint.

- Contains: *nothing*
- Child addressing: no children
- Projection flags: none declared
- Extra keys: not accepted

| parameter | type | default | plane | description |
| --- | --- | --- | --- | --- |
| name | `str` | *required* | physical | the constraint name — this node's key. |
| constraint_type | `CONSTRAINT_TYPE` | *required* | physical | `'UNIQUE'` (needs `columns`) or `'CHECK'` (needs `check_clause`). |
| columns | `str \| None` | `None` | physical | comma-joined physical column names. |
| check_clause | `str \| None` | `None` | physical | the CHECK expression. |

### `index`

A table index.

- Contains: *nothing*
- Child addressing: no children
- Projection flags: none declared
- Extra keys: not accepted

| parameter | type | default | plane | description |
| --- | --- | --- | --- | --- |
| columns | `object \| None` | `None` | physical | comma-joined names, a list or tuple of names, or a `{name: None \| 'DESC'}` dict when per-column ordering matters. |
| name | `str \| None` | `None` | physical | the index name; `<table>_<columns joined by _>_key` when absent, as in GenroPy. |
| unique | `bool \| None` | `None` | physical | a UNIQUE index. |
| method | `str \| None` | `None` | physical | access method (`btree`, `gin`, …). |
| where | `str \| None` | `None` | physical | partial-index predicate. |
| tablespace | `str \| None` | `None` | physical | target tablespace. |
| with_options | `dict \| None` | `None` | physical | storage parameters. |

### `relation`

A relation on a column. Navigable by default, physical on demand.

At most one per local structural key: the grammar accepts the insertion
so the whole document can be built, and `SqlBuilder.validate_model`
reports every conflicting relation together.

- Contains: *nothing*
- Child addressing: no children
- Projection flags: none declared
- Extra keys: not accepted

| parameter | type | default | plane | description |
| --- | --- | --- | --- | --- |
| to | `str` | *required* | physical | the target, `schema.table.column` or `schema.table` (target columns default to the target pkey). |
| foreign_key | `bool` | `False` | physical | emit a physical FK. Only these relations project a foreign key into the migration JSON; every relation on a physical column indexes it. |
| onDelete | `str \| None` | `None` | semantic | Python action on delete of the target row, as in GenroPy: `raise`, `cascade`, `setnull`, `ignore`, optionally followed by `:message`. |
| onUpdate | `str \| None` | `None` | semantic | Python action on update, same values. |
| onDelete_sql | `str \| None` | `None` | physical | SQL action of the foreign key on delete: `cascade`, `restrict`, `no action`, `setnull`, `setdefault` (any case; `set null`/`set default` too), or the legacy abbreviations `C`, `R`, `N`, `SN`, `SD`. |
| onUpdate_sql | `str \| None` | `None` | physical | SQL action of the foreign key on update, same values; `cascade` when absent, as in GenroPy. |
| deferred | `bool` | `False` | physical | DEFERRABLE INITIALLY DEFERRED. True by default when `onDelete` or `onDelete_sql` is `setnull`, as in GenroPy. |
| deferrable | `bool` | `False` | physical | make the foreign key DEFERRABLE. Without `initially_deferred` it is initially immediate. |
| initially_deferred | `bool` | `False` | physical | start a deferrable foreign key deferred. |
| indexed | `bool` | `True` | physical | the index of the relation columns, with or without a foreign key. On by default, as legacy; `False` states that the columns are deliberately left unindexed. |
| one_name | `str \| None` | `None` | semantic | human label of the one side. |
| many_name | `str \| None` | `None` | semantic | human label of the many side. |
| one_one | `bool \| Literal['*']` | `False` | semantic | the relation is 1:1. `'*'` without `relation_name` names the inverse after the many table and makes it public, as in GenroPy. |
| case_insensitive | `bool` | `False` | semantic | join case-insensitively. |
| name | `str \| None` | `None` | physical |  |
| relation_name | `str \| None` | `None` | semantic | name of the inverse relation on the target (`@<relation_name>`), as in GenroPy. |
| onDuplicate | `str \| bool \| None` | `None` | physical |  |
| constraint_name | `str \| None` | `None` | physical |  |
| one_group | `str \| None` | `None` | physical |  |
| many_group | `str \| None` | `None` | physical |  |
| many_order_by | `str \| None` | `None` | physical |  |
| eager_one | `bool \| None` | `None` | physical |  |
| eager_many | `bool \| None` | `None` | physical |  |
| external_relation | `bool \| None` | `None` | physical |  |
| resolver_kwargs | `dict \| None` | `None` | physical |  |
| join_on | `str \| None` | `None` | semantic | the ON condition in place of the key equality. Wins over `cnd`. |
| cnd | `str \| None` | `None` | semantic | the ON condition in place of the key equality. The relation projects no foreign key (GenroPy `mode='custom'`). |
| between | `str \| None` | `None` | semantic | `'value;low;high'`, a range condition in place of the key equality. |
| x_weak | `bool \| None` | `None` | physical |  |
| x_canonical | `bool \| None` | `None` | physical |  |
| x_name | `str \| None` | `None` | physical |  |

### `colgroup`

Ordered group handle; col_* defaults apply to declarations made through it.

- Contains: *nothing*
- Child addressing: no children
- Projection flags: none declared
- Extra keys: `col_*`

| parameter | type | default | plane | description |
| --- | --- | --- | --- | --- |
| name | `str` | *required* | physical |  |
| name_long | `str \| None` | `None` | physical |  |
| name_short | `str \| None` | `None` | physical |  |
| comment | `str \| None` | `None` | physical |  |

### `packages`

Logical packages; distinct from physical schemas.

- Contains: package
- Child addressing: SQL-name labels for package
- Projection flags: none declared
- Extra keys: not accepted

| parameter | type | default | plane | description |
| --- | --- | --- | --- | --- |

### `package`

Logical table namespace with an explicit physical placement.

- Contains: tables[:1], options[:1]
- Child addressing: ordered internal labels for tables, options
- Projection flags: none declared
- Extra keys: not accepted

| parameter | type | default | plane | description |
| --- | --- | --- | --- | --- |
| name | `str` | *required* | semantic | package identifier. |
| sqlschema | `str \| None` | `None` | physical | physical schema name, inferred without a schema declaration; None selects the dialect default. Packages can share a schema. |
| sqlprefix | `bool \| str` | `True` | physical | True uses the package name, False omits the prefix. |
| name_long | `str \| None` | `None` | semantic | human label. |
| name_short | `str \| None` | `None` | semantic | short label. |
| name_full | `str \| None` | `None` | physical |  |
| comment | `str \| None` | `None` | semantic | package description. |
| path | `str \| None` | `None` | physical | folder in the legacy layout (`main.py` with class `Package`, `model/<table>.py` with class `Table`) whose tables the package loads. |

### `options`

Singleton section of typed functions, validated for its owning level.

- Contains: *
- Child addressing: ordered internal labels for *
- Projection flags: none declared
- Extra keys: not accepted

| parameter | type | default | plane | description |
| --- | --- | --- | --- | --- |

### `reset`

Remove an accumulated option before subsequent declarations rebuild it.

- Contains: *nothing*
- Child addressing: no children
- Projection flags: none declared
- Extra keys: not accepted

| parameter | type | default | plane | description |
| --- | --- | --- | --- | --- |
| name | `str` | *required* | physical |  |

### `driver`

Driver options, checked against the connection's configured dialect.

- Contains: *nothing*
- Child addressing: no children
- Projection flags: none declared
- Extra keys: not accepted

| parameter | type | default | plane | description |
| --- | --- | --- | --- | --- |
| connect_timeout | `int \| None` | `None` | physical |  |
| application_name | `str \| None` | `None` | physical |  |
| sslmode | `str \| None` | `None` | physical |  |
| sslrootcert | `str \| None` | `None` | physical |  |
| options | `str \| None` | `None` | physical |  |
| timeout | `float \| int \| None` | `None` | physical |  |
| cached_statements | `int \| None` | `None` | physical |  |
| foreignKeys | `bool \| None` | `None` | physical |  |

### `requires`

Names of packages that must be present when resolving the model.

- Contains: *nothing*
- Child addressing: no children
- Projection flags: none declared
- Extra keys: not accepted

| parameter | type | default | plane | description |
| --- | --- | --- | --- | --- |
| packages | `str \| list[str] \| tuple[str, ...]` | *required* | physical |  |

### `type`

Package-local column type and its explicit presentation defaults.

- Contains: *nothing*
- Child addressing: no children
- Projection flags: none declared
- Extra keys: not accepted

| parameter | type | default | plane | description |
| --- | --- | --- | --- | --- |
| name | `str` | *required* | physical |  |
| dtype | `DTYPE` | *required* | physical |  |
| size | `str \| None` | `None` | physical |  |
| name_long | `str \| None` | `None` | physical |  |
| name_short | `str \| None` | `None` | physical |  |

### `sys_fields`

Describe system fields; expansion happens only during rendering.

syscode opts into __syscode, A size :20, indexed and unique.
It adds no system-record behavior, virtual columns or generated values.

- Contains: *nothing*
- Child addressing: no children
- Projection flags: none declared
- Extra keys: not accepted

| parameter | type | default | plane | description |
| --- | --- | --- | --- | --- |
| id | `bool \| dict` | `True` | physical |  |
| ins | `bool \| dict` | `True` | physical |  |
| upd | `bool \| dict` | `True` | physical |  |
| user_ins | `bool \| dict` | `True` | physical |  |
| user_upd | `bool \| dict` | `True` | physical |  |
| ldel | `bool \| dict` | `True` | physical |  |
| draft | `bool \| dict` | `False` | physical |  |
| group | `str` | `'zzz'` | physical |  |
| group_name | `str` | `'System'` | physical |  |
| enabled | `bool` | `True` | physical |  |
| syscode | `bool` | `False` | physical |  |

### `validation`

Preserve column validation declarations without interpreting rules.

Embedded validate_* attributes produce the same dictionary, stripping
only the prefix. Names and values are retained without vocabulary or
rule-specific type checks. Translation never executes these rules.

- Contains: *nothing*
- Child addressing: no children
- Projection flags: none declared
- Extra keys: preserved as validation data without rule-specific checks

| parameter | type | default | plane | description |
| --- | --- | --- | --- | --- |

### `encryption`



- Contains: *nothing*
- Child addressing: no children
- Projection flags: none declared
- Extra keys: not accepted

| parameter | type | default | plane | description |
| --- | --- | --- | --- | --- |
| mode | `Literal['X', 'R', 'Q']` | *required* | physical |  |

### `weak_relation`



- Contains: *nothing*
- Child addressing: no children
- Projection flags: none declared
- Extra keys: not accepted

| parameter | type | default | plane | description |
| --- | --- | --- | --- | --- |
| to | `str` | *required* | physical |  |
| name | `str \| None` | `None` | physical |  |
| relation_name | `str \| None` | `None` | physical |  |
| indexed | `bool` | `True` | physical |  |
| one_one | `bool` | `False` | physical |  |
| onDelete | `str \| None` | `None` | physical |  |
| onUpdate | `str \| None` | `None` | physical |  |
| onDuplicate | `str \| bool \| None` | `None` | physical |  |
| one_name | `str \| None` | `None` | physical |  |
| many_name | `str \| None` | `None` | physical |  |
| one_group | `str \| None` | `None` | physical |  |
| many_group | `str \| None` | `None` | physical |  |

### `bagItemColumn`



- Contains: relation
- Child addressing: ordered internal labels for relation
- Projection flags: none declared
- Extra keys: not accepted

| parameter | type | default | plane | description |
| --- | --- | --- | --- | --- |
| name | `str` | *required* | physical |  |
| bagcolumn | `str` | *required* | physical |  |
| itempath | `str` | *required* | physical |  |
| dtype | `str \| None` | `None` | physical |  |
| group | `str \| None` | `None` | physical |  |
| name_long | `str \| None` | `None` | physical |  |
| name_short | `str \| None` | `None` | physical |  |
| comment | `str \| None` | `None` | physical |  |
| x_identity | `str \| None` | `None` | physical |  |

### `virtualRelation`

GEP virtual relation; var_* binds source expressions as declaration data.

table names a direct target and requires a nonempty condition in the
completed source. condition refers to the target. var_* expressions refer to the source
and are used as :var_* in condition. An ask field named <name> is
referenced as :ask_<name>. This namespace is provisional until compiler
design. ask and bindings are preserved as data, without SQL rewriting.
Unlike the GEP, order_by, limit and one_one are deferred, along with
virtual inverses.

- Contains: *nothing*
- Child addressing: no children
- Projection flags: none declared
- Extra keys: `var_*`

| parameter | type | default | plane | description |
| --- | --- | --- | --- | --- |
| name | `str` | *required* | physical |  |
| relation | `str \| None` | `None` | physical |  |
| table | `str \| None` | `None` | physical |  |
| condition | `str \| None` | `None` | physical |  |
| ask | `dict \| None` | `None` | physical |  |
| name_long | `str \| None` | `None` | physical |  |
| name_short | `str \| None` | `None` | physical |  |
| comment | `str \| None` | `None` | physical |  |

### `hierarchical`

Declare a hierarchy; column entries are names or {name, unique} mappings.

- Contains: *nothing*
- Child addressing: no children
- Projection flags: none declared
- Extra keys: not accepted

| parameter | type | default | plane | description |
| --- | --- | --- | --- | --- |
| columns | `str \| list \| tuple \| None` | `None` | semantic |  |
| parent | `str` | `'parent_id'` | semantic |  |
| root_id | `bool` | `False` | semantic |  |
| virtual_roots | `bool` | `False` | semantic |  |
| linked_to | `str \| None` | `None` | semantic |  |
| depth | `int \| None` | `None` | semantic |  |
| caption_field | `str \| None` | `None` | semantic |  |
| enabled | `bool` | `True` | semantic |  |

### `auto_counter`

Declare a counter and its scope; no value allocation during construction.

- Contains: *nothing*
- Child addressing: no children
- Projection flags: none declared
- Extra keys: not accepted

| parameter | type | default | plane | description |
| --- | --- | --- | --- | --- |
| scope | `str \| list \| tuple \| None` | `None` | semantic |  |
| field | `str` | `'_row_count'` | semantic |  |
| enabled | `bool` | `True` | semantic |  |

### `relative_index`

Declare a relative index; relation required when enabled.

- Contains: *nothing*
- Child addressing: no children
- Projection flags: none declared
- Extra keys: not accepted

| parameter | type | default | plane | description |
| --- | --- | --- | --- | --- |
| relation | `str \| None` | `None` | semantic |  |
| field | `str` | `'_relidx'` | semantic |  |
| enabled | `bool` | `True` | semantic |  |

### `dynamic_fields`

Table option uses templates; column declaration requires source.

- Contains: *nothing*
- Child addressing: no children
- Projection flags: none declared
- Extra keys: not accepted

| parameter | type | default | plane | description |
| --- | --- | --- | --- | --- |
| templates | `dict \| str \| None` | `None` | semantic |  |
| source | `str \| None` | `None` | semantic |  |
| enabled | `bool` | `True` | semantic |  |

### `record_hash`

Declare a record comparison hash, independent of SQL defaults.

- Contains: *nothing*
- Child addressing: no children
- Projection flags: none declared
- Extra keys: not accepted

| parameter | type | default | plane | description |
| --- | --- | --- | --- | --- |
| field | `str` | `'__rec_md5'` | semantic |  |
| columns | `str \| list \| tuple \| None` | `None` | semantic |  |
| algorithm | `Literal['md5']` | `'md5'` | semantic |  |
| enabled | `bool` | `True` | semantic |  |

### `full_update`

Declare the timestamp for updates including related content.

- Contains: *nothing*
- Child addressing: no children
- Projection flags: none declared
- Extra keys: not accepted

| parameter | type | default | plane | description |
| --- | --- | --- | --- | --- |
| field | `str` | `'__full_mod_ts'` | semantic |  |
| enabled | `bool` | `True` | semantic |  |

### `audit`

Declare audit; mode required when enabled.

- Contains: *nothing*
- Child addressing: no children
- Projection flags: none declared
- Extra keys: not accepted

| parameter | type | default | plane | description |
| --- | --- | --- | --- | --- |
| mode | `Literal['full', 'lazy'] \| None` | `None` | semantic |  |
| version_field | `str` | `'__version'` | semantic |  |
| enabled | `bool` | `True` | semantic |  |

### `system_records`

Declare system records or symbolic factories; never insert data at build time.

- Contains: *nothing*
- Child addressing: no children
- Projection flags: none declared
- Extra keys: not accepted

| parameter | type | default | plane | description |
| --- | --- | --- | --- | --- |
| records | `dict \| None` | `None` | semantic |  |
| masterfield | `str \| None` | `None` | semantic |  |
| tag | `str` | `'superadmin'` | semantic |  |
| enabled | `bool` | `True` | semantic |  |

### `protection`

Declare protection expressions or symbolic rules.

- Contains: *nothing*
- Child addressing: no children
- Projection flags: none declared
- Extra keys: not accepted

| parameter | type | default | plane | description |
| --- | --- | --- | --- | --- |
| rules | `list \| tuple \| None` | `None` | semantic |  |
| tag | `str \| None` | `None` | semantic |  |
| enabled | `bool` | `True` | semantic |  |

### `release`

Declare version-to-handler references; no transformations run at build time.

- Contains: *nothing*
- Child addressing: no children
- Projection flags: none declared
- Extra keys: not accepted

| parameter | type | default | plane | description |
| --- | --- | --- | --- | --- |
| handlers | `dict \| None` | `None` | semantic |  |
| enabled | `bool` | `True` | semantic |  |

### `retention`

Declare retention by field and nonnegative days.

- Contains: *nothing*
- Child addressing: no children
- Projection flags: none declared
- Extra keys: not accepted

| parameter | type | default | plane | description |
| --- | --- | --- | --- | --- |
| field | `str \| None` | `None` | semantic |  |
| days | `int \| None` | `None` | semantic |  |
| enabled | `bool` | `True` | semantic |  |

### `broadcast`

Declare change events; no events emitted at build time.

- Contains: *nothing*
- Child addressing: no children
- Projection flags: none declared
- Extra keys: not accepted

| parameter | type | default | plane | description |
| --- | --- | --- | --- | --- |
| columns | `str \| list \| tuple \| None` | `None` | semantic |  |
| enabled | `bool` | `True` | semantic |  |

### `archive`

Declare the legacy archivable flag.

- Contains: *nothing*
- Child addressing: no children
- Projection flags: none declared
- Extra keys: not accepted

| parameter | type | default | plane | description |
| --- | --- | --- | --- | --- |
| enabled | `bool` | `True` | semantic |  |

### `enabled_when`

Declare a preference condition without evaluating it.

- Contains: *nothing*
- Child addressing: no children
- Projection flags: none declared
- Extra keys: not accepted

| parameter | type | default | plane | description |
| --- | --- | --- | --- | --- |
| preference | `str \| None` | `None` | semantic |  |
| enabled | `bool` | `True` | semantic |  |

### `attachments`

Declare attachment expansion for its master table.

- Contains: *nothing*
- Child addressing: no children
- Projection flags: none declared
- Extra keys: not accepted

| parameter | type | default | plane | description |
| --- | --- | --- | --- | --- |
| master | `str \| None` | `None` | semantic |  |
| enabled | `bool` | `True` | semantic |  |

### `numbering`

Declare the parameters of a named numbering rule.

- Contains: *nothing*
- Child addressing: no children
- Projection flags: none declared
- Extra keys: not accepted

| parameter | type | default | plane | description |
| --- | --- | --- | --- | --- |
| field | `str` | *required* | semantic |  |
| parameters | `dict \| None` | `None` | semantic |  |
| enabled | `bool` | `True` | semantic |  |
