# SQL model grammar reference

Generated from the live grammar by `genro_sql.grammar_doc.generate_grammar_md()`. Do not edit by hand: regenerate with `python -m genro_sql.grammar_doc`.

Domain element signatures are **semi-closed**: they declare their physical and enumerated semantic parameters. Where `**extra` is accepted, each extra key must start with `x_`.

## Hierarchy

```
db
├── schemas[:1]
└── extensions[:1]
```

## Elements

### `db`

Database root, one per model.

- Contains: schemas[:1], extensions[:1]
- Child addressing: ordered internal labels for schemas, extensions
- Projection flags: none declared
- Extra keys: not accepted

| parameter | type | default | plane | description |
| --- | --- | --- | --- | --- |
| name | `str` | *required* | physical | the database name — the JSON `entity_name`. |

### `schemas`

The explicit collection of database schemas.

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
- Extra keys: accepted (`x_` prefix required)

| parameter | type | default | plane | description |
| --- | --- | --- | --- | --- |
| name | `str` | *required* | physical | the extension name (`pg_trgm`, `unaccent`, …). |

### `schema`

A database schema (a 'package' in GenroPy vocabulary).

- Contains: tables[:1]
- Child addressing: ordered internal labels for tables
- Projection flags: none declared
- Extra keys: accepted (`x_` prefix required)

| parameter | type | default | plane | description |
| --- | --- | --- | --- | --- |
| name | `str` | *required* | physical | the schema name — physical, and this node's key. |
| comment | `str \| None` | `None` | semantic | source-only free description; structure-1.0 schemas have no physical attribute slot. |

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

- Contains: columns[:1], virtual_columns[:1], composites[:1], constraints[:1], indexes[:1]
- Child addressing: ordered internal labels for columns, virtual_columns, composites, constraints, indexes
- Projection flags: none declared
- Extra keys: accepted (`x_` prefix required)

| parameter | type | default | plane | description |
| --- | --- | --- | --- | --- |
| name | `str` | *required* | physical | the table name — physical, and this node's key. |
| pkey | `str \| None` | `None` | physical | comma-joined physical column names, the JSON `pkeys`. Every name must exist among the table's physical columns. |
| comment | `str \| None` | `None` | physical | free description. |
| caption_field | `str \| None` | `None` | semantic | the column that captions a row. |
| name_long | `str \| None` | `None` | semantic | human label. |
| name_plural | `str \| None` | `None` | semantic | human label, plural form. |

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

- Contains: aliasColumn, formulaColumn, subQueryColumn, pyColumn
- Child addressing: SQL-name labels for aliasColumn, formulaColumn, subQueryColumn, pyColumn
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

- Contains: relation
- Child addressing: ordered internal labels for relation
- Projection flags: `projects_column`, `projects_relation`
- Extra keys: accepted (`x_` prefix required)

| parameter | type | default | plane | description |
| --- | --- | --- | --- | --- |
| name | `str` | *required* | physical | the column name — physical, and this node's key. |
| dtype | `DTYPE \| None` | `None` | physical | Genro normalized type code. Absent, the renderer defaults to `'A'` when `size` is given, else `'T'`. |
| size | `str \| None` | `None` | physical | `'n'` or `'min:max'` character size. |
| notnull | `bool` | `False` | physical | NOT NULL. Pkey members get it from their pkey membership, not from this flag. |
| unique | `bool` | `False` | physical | single-column UNIQUE. A redundant one on a single-column pkey is dropped by the renderer. |
| indexed | `bool` | `False` | physical | sugar — the renderer materializes a real index item (`structure-1.0` has no `indexed` column attribute). A column carrying a foreign key is always indexed. |
| sqldefault | `str \| None` | `None` | physical | SQL DEFAULT expression. |
| extra_sql | `str \| None` | `None` | physical | verbatim tail of the column definition. |
| generated_expression | `str \| None` | `None` | physical | GENERATED ALWAYS AS expression. |
| comment | `str \| None` | `None` | physical | the column comment. |
| name_long | `str \| None` | `None` | semantic | human label. |
| name_short | `str \| None` | `None` | semantic | human label, short form. |
| group | `str \| None` | `None` | semantic | field-group key. |

### `aliasColumn`

A virtual column projecting a related column. Never physical.

An alias reads through a relation that already exists, so it never
carries one of its own.

- Contains: *nothing*
- Child addressing: no children
- Projection flags: none declared
- Extra keys: accepted (`x_` prefix required)

| parameter | type | default | plane | description |
| --- | --- | --- | --- | --- |
| name | `str` | *required* | physical | the alias name. |
| relation_path | `str` | *required* | physical | `@relation.column` path to the source column. |
| name_long | `str \| None` | `None` | semantic | human label. |
| group | `str \| None` | `None` | semantic | field-group key. |

### `formulaColumn`

A virtual column defined by SQL. Never physical.

- Contains: *nothing*
- Child addressing: no children
- Projection flags: none declared
- Extra keys: accepted (`x_` prefix required)

| parameter | type | default | plane | description |
| --- | --- | --- | --- | --- |
| name | `str` | *required* | physical | the column name. |
| sql_formula | `str \| None` | `None` | physical | an expression over the row's own columns. |
| select | `str \| None` | `None` | physical | a scalar sub-select. |
| exists | `str \| None` | `None` | physical | an EXISTS predicate. |
| dtype | `DTYPE \| None` | `None` | physical | the resulting type code. |
| name_long | `str \| None` | `None` | semantic | human label. |
| group | `str \| None` | `None` | semantic | field-group key. |

### `subQueryColumn`

A virtual column defined by a sub-query. Never physical.

- Contains: *nothing*
- Child addressing: no children
- Projection flags: none declared
- Extra keys: accepted (`x_` prefix required)

| parameter | type | default | plane | description |
| --- | --- | --- | --- | --- |
| name | `str` | *required* | physical | the column name. |
| query | `str` | *required* | physical | the sub-query. |
| mode | `str \| None` | `None` | physical | `json`, `xml` or a scalar aggregate. Expanding it is the renderer's job, not grammar-time. |
| name_long | `str \| None` | `None` | semantic | human label. |
| group | `str \| None` | `None` | semantic | field-group key. |

### `pyColumn`

A virtual column computed in Python. Never physical.

- Contains: *nothing*
- Child addressing: no children
- Projection flags: none declared
- Extra keys: accepted (`x_` prefix required)

| parameter | type | default | plane | description |
| --- | --- | --- | --- | --- |
| name | `str` | *required* | physical | the column name. |
| py_method | `str \| None` | `None` | physical | the method computing it; defaults to `pyColumn_<name>` on the table class. |
| dtype | `DTYPE \| None` | `None` | physical | the resulting type code. |
| name_long | `str \| None` | `None` | semantic | human label. |
| group | `str \| None` | `None` | semantic | field-group key. |

### `compositeColumn`

N physical columns packed as one navigable key.

Not a column of its own — it projects no column, only what its
members already are. THE mechanism for a multi-column key: a
composite FK is a `relation` on a compositeColumn, and a
composite UNIQUE is `unique=True` here.

- Contains: relation
- Child addressing: ordered internal labels for relation
- Projection flags: `projects_relation`
- Extra keys: accepted (`x_` prefix required)

| parameter | type | default | plane | description |
| --- | --- | --- | --- | --- |
| name | `str` | *required* | physical | the composite name (GenroPy `composed_of` carried the members instead). |
| columns | `str` | *required* | physical | comma-joined member names, all physical columns of the same table. |
| unique | `bool` | `False` | physical | projects a multi-column UNIQUE constraint. |
| name_long | `str \| None` | `None` | semantic | human label. |
| group | `str \| None` | `None` | semantic | field-group key. |

### `constraint`

A table constraint.

- Contains: *nothing*
- Child addressing: no children
- Projection flags: none declared
- Extra keys: accepted (`x_` prefix required)

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
- Extra keys: accepted (`x_` prefix required)

| parameter | type | default | plane | description |
| --- | --- | --- | --- | --- |
| name | `str` | *required* | physical | the index name. |
| columns | `object \| None` | `None` | physical | comma-joined names, or a `{name: None \| 'DESC'}` dict when per-column ordering matters. |
| unique | `bool` | `False` | physical | a UNIQUE index. |
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
- Extra keys: accepted (`x_` prefix required)

| parameter | type | default | plane | description |
| --- | --- | --- | --- | --- |
| to | `str` | *required* | physical | the target, `schema.table.column` or `schema.table` (target columns default to the target pkey). |
| foreign_key | `bool` | `False` | physical | emit a physical FK. Only these relations project into the migration JSON. |
| on_delete | `FK_ACTION \| None` | `None` | physical | referential action on delete. |
| on_update | `FK_ACTION \| None` | `None` | physical | referential action on update. |
| deferred | `bool` | `False` | physical | compatibility sugar for DEFERRABLE INITIALLY DEFERRED. |
| deferrable | `bool` | `False` | physical | make the foreign key DEFERRABLE. Without `initially_deferred` it is initially immediate. |
| initially_deferred | `bool` | `False` | physical | start a deferrable foreign key deferred. |
| indexed | `bool` | `True` | physical | the supporting index of the foreign key. On by default (GenroPy parity, D3); `False` states that the columns are deliberately left unindexed. |
| back_reference | `str \| None` | `None` | semantic | navigable path of the many side. |
| one_name | `str \| None` | `None` | semantic | human label of the one side. |
| many_name | `str \| None` | `None` | semantic | human label of the many side. |
| one_one | `bool` | `False` | semantic | the relation is 1:1. |
| case_insensitive | `bool` | `False` | semantic | join case-insensitively. |
