# Proposal 0001 — Declaring models and writing expressions

| | |
|---|---|
| **Status** | Proposal — for team review |
| **Implementation** | Not yet in the code. asqueel 0.4.0 behaves as described in the current guide. asqueel is being written: parts of this target arrive in later increments, without provisional implementations. |
| **Date** | 2026-10-02 |
| **Applies to** | asqueel after 0.4.0 |
| **Plans** | [32 — expression parser and resolver](../design/32-expression-resolver-plan.md), [33 — model structure](../design/33-structure-rectification-plan.md) |
| **Legacy reference** | GenroPy `origin/develop` `51e4270c54` |

This document describes how a model is declared and how expressions are
written in asqueel once plans 32 and 33 are implemented. It is written as the
final documentation, so that the team can review the result rather than the
plans. Each rule is marked **Decided** or **Open**. Nothing here is implemented
yet.

## 1. Principles

- **GenroPy syntax is the default.** A model or an expression written for
  GenroPy means the same thing in asqueel when asqueel supports it.
- **No alternative spellings.** asqueel does not add a second way to write
  something GenroPy already expresses.
- **Divergences are written down with an external reason**: an inventory of
  real usage, a legacy defect shown in the code, a database requirement, or a
  decision of a GenroPy proposal (GEP). Section 7 lists them.
- **An unsupported form raises an explicit error.** It never produces a
  different result.
- **Python first.** When in doubt between a behaviour implemented in Python and
  one delegated to SQL, the Python one prevails: Python triggers are far more
  powerful. Names follow: the short name is the Python action, the `_sql`
  suffix marks the SQL one.
- **snake_case for parameters.** A GenroPy parameter keeps its name in snake
  form (`onDelete_sql` → `on_delete_sql`). GenroPy element names keep their
  spelling (`formulaColumn`, `aliasColumn`, `compositeColumn`).
- **The declaration is a recipe; the model is a tree of objects.** A model
  declaration builds a source tree. A renderer turns it into specialized
  Python objects (tables, columns, relations). The renderer may read a node
  before building and may produce several objects from one node: there is no
  one-to-one correspondence between declaration nodes and model objects.
  **Decided.**
- **The design leaves room for two planned features**: relation functions
  ([GEP 1](https://github.com/genropy/genropy_meta/blob/main/gep/GEP-0001-relation-aggregates.md),
  e.g. `@invoices.sum($total)`) and `virtualRelation`
  ([genropy/genropy_meta#1](https://github.com/genropy/genropy_meta/issues/1)).
  Nothing in this proposal duplicates what they will provide.

## 2. Declaring a table's content

Schema and table declarations are unchanged by this proposal. Table and column
names in the examples are illustrative.

### 2.1 Columns are declared on the table — Decided

```python
tbl = tables.table('invoice', pkey='id')
tbl.column('id', dtype='L')
tbl.column('customer_id', dtype='L').relation('sales.customer.id')
tbl.column('total', dtype='N', size='12,2', notnull=True)
tbl.formulaColumn('double_total', sql_formula='$total * 2', dtype='N')
tbl.aliasColumn('customer_name', relation_path='@customer_id.name')
tbl.index('total')
```

Physical columns, virtual columns and indexes are declared directly on the
table, as in GenroPy. The internal containers (`columns`, `virtual_columns`,
`indexes`) exist but are not written by the developer.

- The explicit form `tbl.columns().column(...)` / `tbl.virtual_columns()...`
  is no longer accepted. **Decided.**
- A name used by a physical and a virtual column of the same table is an error.
  Today asqueel accepts it and the virtual column silently replaces the
  physical one. **Decided.** GenroPy's `_override=True` is used where a package
  modifies another package's table; it comes with package composition.

Supported column elements: `column`, `formulaColumn`, `aliasColumn`,
`subQueryColumn`, `pyColumn`, `compositeColumn`.
Not available yet (the grammar does not know them): `joinColumn`, `bagItemColumn`,
`toolColumn`, `aliasTable`, `subtable`, `localized` and `ext_*` columns.

`constraint` is not part of the model. A unique key on several columns is
`compositeColumn(..., unique=True)`. `CHECK` constraints come back with the
other native database objects (triggers, functions, views). Importing a
database that has `CHECK` constraints imports the model without them and warns
with their names; migrations are additive, so the constraints stay in the
database. **Decided.**

### 2.2 Column groups — Decided

```python
addr = tbl.colgroup('address', name_long='Address')
addr.column('street')
addr.formulaColumn('label', sql_formula="$street || ' ' || $city")
tbl.column('city', colgroup='address')
```

- A group is declared once with `tbl.colgroup(name, name_long=...)`.
- A column, physical or virtual, joins a group in one of two ways: it is
  declared through the group, or it is declared on the table with
  `colgroup='<name>'`. The second form serves helpers that add columns outside
  the group's block.
- The order of the columns in a group is their declaration order. There are no
  position numbers: to change the order, change the declaration.
- `col_*` arguments of `colgroup` are defaults for every column of the group,
  for named parameters as well (`col_dtype`, `col_size`, ...).
- A method called on a group behaves exactly as on the table (an index declared
  through a group is named after the table).
- Errors: `colgroup='<name>'` of an undeclared group; a column declared through
  a group with a different `colgroup` attribute; the same group declared twice.
- Groups only group. Visibility in a user interface and the placement of
  relation nodes in a fields tree are not part of the model core.
- `colgroup` takes only `name_long` and `col_*` defaults. Interface attributes,
  if needed, go through `x_ui`. **Decided.**

### 2.3 Relations — Decided

```python
tbl.column('customer_id', dtype='L').relation('sales.customer.id')
tbl.column('customer_code', size=':10').weak_relation('sales.customer.code')
tbl.column('legacy_code', size=':10').weak_relation('sales.customer.code', insensitive=True)
```

| Element | Database | Target |
|---|---|---|
| `relation(...)` | `FOREIGN KEY` | must have a unique key (primary key, `unique` column or `UNIQUE` composite); otherwise an error, because the database requires it |
| `weak_relation(...)` | no constraint | trusted to be unique; not checked |

- `weak_relation(..., insensitive=True)` joins without case distinction.
- A link to a target that is not unique, a filtered relation, or one row chosen
  by order and limit (for example the last invoice of a customer) is not a
  parameter of `weak_relation`. These are `virtualRelation` cases, not
  available until it exists.
- The rows of the many side are reached through the inverse relation (section
  3.2), not through a relation declared on the one side.
- Parameters, **Decided**: `related_column` (target), `relation_name`
  (inverse name), `one_name`, `many_name`, `one_one`, `on_delete` /
  `on_update` (Python actions on related records), `on_delete_sql` /
  `on_update_sql` (SQL actions of the foreign key), `deferred`, `deferrable`,
  `initially_deferred`.
- `on_delete` / `on_update` (Python actions: `'cascade'`, `'setnull'`,
  `'raise'`) belong to the target API and arrive with the related-records write
  cycle. Until then the model validator rejects them as unknown attributes.
  **Decided.**

#### Every foreign key cascades key updates — Decided

`on_update_sql` defaults to `'cascade'`, as in GenroPy. Every foreign key is
created with `ON UPDATE CASCADE`: when the key of a referenced record changes,
the database updates the rows that point to it. Without this default the
database would refuse the key change while related rows exist.

```python
tbl.column('customer_id', dtype='L').relation('sales.customer.id')
# FOREIGN KEY (customer_id) REFERENCES sales.customer (id) ON UPDATE CASCADE
tbl.column('owner_id', dtype='L').relation('sales.user.id', on_update_sql=None)
# FOREIGN KEY (owner_id) REFERENCES sales.user (id)  — no action on update
```

Today asqueel creates foreign keys without an update action; this changes.

### 2.4 Composite keys — Decided

```python
tbl = tables.table('price_year', pkey='product_year_key')
tbl.column('product_id', dtype='L')
tbl.column('year', dtype='L')
tbl.compositeColumn('product_year_key', columns='product_id,year', unique=True)

note = tables.table('price_year_note', pkey='id')
note.compositeColumn('product_year_ref', columns='product_id,year').relation('invc.price_year.product_year_key')
```

One concept covers every key on several columns, as in GenroPy:

- A `compositeColumn` is a virtual column. Its value is the serialized key,
  e.g. `'["P1", 2024]'`. It is `static=True` by default, so `*` selects it.
- `unique=True` creates a multi-column `UNIQUE` constraint.
- `.relation(...)` on a composite targets another composite and joins the
  member columns in order.
- `pkey` always names one column, physical or composite. A composite primary
  key is `pkey='<composite name>'`; `table.pkeys` returns the member columns.
- The serialized value is the identity of a record with a composite key: it is
  the `pkey` value of query results and of records, and GenroPy reads it back
  with `parseSerializedKey`.

### 2.5 Indexes created by relations — Decided

- Every `relation` and every `weak_relation` creates an index on its source
  columns. Without it, inverse navigation and every `DELETE`/`UPDATE` of the
  referenced key read the whole source table; PostgreSQL does not create it.
- The index is not created when the source columns are already the leading
  columns of the primary key, of a `UNIQUE` constraint or of a declared index.
- There is no option to switch it off.
- A `weak_relation` also creates an index on its target columns, as GenroPy
  does, unless they are already the leading columns of a primary key, a
  `UNIQUE` constraint or an index. A `relation` targets a unique key, which is
  already indexed. **Decided.**

### 2.6 Table features are grammar elements — Decided

GenroPy adds system columns and behaviours through `sysFields(...)` arguments
and table attributes. asqueel declares them as elements inside `table`, each
describing one function. The future GenroPy adapter maps the legacy forms
onto them.

| Element | Functions |
|---|---|
| `sys_fields` | generated primary key, insert and update timestamps, insert and update user, logical deletion, draft |
| `auto_counter` | row numbering, over the whole table or inside a foreign key; numbering inside a master that does not reuse numbers |
| `hierarchical` | tree structure (section 2.7) |

- The functions are taken from what GenroPy offers, not from its
  implementation.
- The other `sysFields` functions (optimistic concurrency, audit, diagnostics,
  row protection, invalid fields, record merge, system records, versioned
  updates) are **Open**: each is discussed on its own.
- The parameters of each element are **Open**.

#### The `options` container — Decided

```python
class ProductTypeModel:
    def configure(self, tables):
        tbl = tables.table('product_type', pkey='id')
        tbl.column('description')
        opts = tbl.options()
        opts.sys_fields()
        opts.hierarchical('description')
        opts.auto_counter('parent_id')
        return tbl
```

- A table is declared in one method, `configure(self, tables)`. There is no
  `config_db` and no method per role.
- Table features are declared inside an explicit container, `tbl.options()`:
  a child of `table`, at most one per table, holding `sys_fields`,
  `hierarchical` and `auto_counter`. `auto_counter` may appear more than once,
  one per foreign key.
- A feature element outside `options` is an error.
- Dependencies between features are checked by the model validator: for
  example `hierarchical` requires a single-column primary key.
- Columns are declared directly on the table (section 2.1) because they are
  its content; features describe how the table behaves and stay visible as a
  separate block. This is why `options` is explicit while `columns` is not.
- Every option is a grammar element with a typed signature and a docstring,
  so the generated grammar reference (`asqueel.grammar_doc`, checked byte for
  byte by a test) documents each option, its parameters and its defaults. In
  GenroPy the same information is spread over `sysFields` keyword arguments
  and table attributes read in many places.

### 2.7 Hierarchical tables — Decided

- The model is GenroPy's: a `parent_id` relation plus materialized paths,
  physical, of the primary key (`hierarchical_pkey`) and of the declared
  fields (`hierarchical_<field>`).
- Moving a node or renaming a path field rewrites the subtree one child at a
  time, with the Python triggers ("Python first"). Reason: hierarchical tables
  are very static; moves and renames are rare and reads matter more.
- Sibling order is `auto_counter('parent_id')`. The maximum + 1 is computed
  with a lock on the parent row.
- The tree sort key (`_h_count`) keeps GenroPy's format: 2 base-36 characters
  per level, compatible with existing databases. The 1296th sibling under the
  same parent is an explicit error on insert.
- The core provides subtree, ancestors and root, with the node included or
  excluded explicitly. Their form is decided together with GEP 1 and
  `virtualRelation`.

Corrections with respect to GenroPy, **Decided** (section 7):

- moving a node under one of its descendants is an error;
- parent, children and siblings are read without the draft and
  logical-deletion filters;
- a moved node takes the last position among its new siblings;
- every `LIKE` on a path generated by the core escapes `_` and `%`;
- on PostgreSQL the path index is created with `text_pattern_ops`.

**Open**: a null value in a path field; a `/` inside a path value;
`copyFromParent` only on insert and move; `_parent_h_*` computed instead of
physical.

Not available yet: `hierarchical_linked_to`, virtual roots, `hdepth`.

## 3. Writing expressions

### 3.1 Syntax — Decided

| Form | Meaning |
|---|---|
| `$col` | column of the current table |
| `@customer_id.name` | column reached through the relation of `customer_id` |
| `@customer_id.@state_id.name` | several hops; every relation segment starts with `@` |
| `:name` | bound parameter |
| `:env_name` | value from the environment |
| `#THIS.<path>` | column of the outer row inside a correlated subquery |
| `#NAME(arguments)` | macro (section 3.4) |
| `#name` | named subquery of a formula |

- `@customer.country.name` (an intermediate segment without `@`) is an error.
  GenroPy does not accept it either.
- Expressions are parsed once, by one parser, and resolved by one resolver
  shared by queries, formulas, row policies and `table.column()`.

### 3.2 Relation names — Decided

- An outgoing relation is named after its column: `@customer_id`.
- An inverse relation is named by `relation_name` on the declaring relation.
  Without it, the name follows GenroPy's rule `<schema>_<table>_<column>` and
  the relation is private. **Proposed** (plan 32, step 2).
- `x_name` no longer names a relation.

### 3.3 Many-side hops — Decided

A path through a relation that reaches several rows (for example `@invoices`
from a customer) is an error. Its values will be reached through GEP 1 relation
functions: `@invoices.count()`, `@invoices.sum($total)`,
`@invoices.to_json($number, $date)`. The parser already reads this form, so
GEP 1 only adds the functions.

asqueel never compiles a join that multiplies the rows of the main table, and
never regroups rows in Python.

### 3.4 Macros

- A macro is a construct of the language, expanded during compilation into
  parts of the expression; paths inside its arguments are resolved like any
  other path. **Decided** (decision of 30 September 2026).
- Macros are registered per level (core, dialect, application, package) and per
  context (columns, where, order by, group by, having, relation condition,
  formula, record). A macro unknown to the dialect is a compilation error.
  **Proposed** (plan 32, step 6).
- `#THIS.<path>` is a column or a path of the outer row inside a correlated
  subquery, resolved by the outer query; its joins belong to the outer query. It
  works in `select`/`exists` conditions and in `sql_formula`, where GenroPy does
  not expand `#THIS.@rel.col` (genropy/genropy#1505). Outside a correlated
  context it is an error. **Decided.**
- `#IN_RANGE(value, start, end)` is true when `start <= value <= end`; a `NULL`
  bound leaves that side open, and two `NULL` bounds are always true (GenroPy
  semantics). Arguments are any expression: column, path, parameter,
  `:env_name`, `#THIS.<path>`. It expands in every context, `group by`, `having`
  and record queries included. **Decided.**
- `#PERIOD($field, :p)` filters `$field` on the period described by the value of
  `p` (`'today'`, `'today;today+7'`, `'questa settimana'`, `'2024'`, ...). The
  period is decoded by `genro_toolbox.dates.parse_period(text, workdate,
  locale)` (genro-toolbox 0.15.0) with the `workdate` and `locale` of the
  context; an unrecognised value raises `PeriodError`. The parser replays 2796
  GenroPy cases; its 432 approved divergences are listed with their reasons in
  genro-toolbox (`tests/data/period_parser_divergences.json`). **Decided.** The generated SQL is always
  half-open, `$field >= :p_from AND $field < :p_to_next` with `p_to_next` the day
  after the end; a single day uses the same form. On a `date` column the result
  is GenroPy's; on a timestamp column the last day is included, which GenroPy's
  `BETWEEN` missed. **Decided.** A parameter is written `:p`; a literal value is quoted, `#PERIOD($date, '2024')`
  or `#PERIOD($date, 'today;today+7')`; a missing parameter is an error.
  **Decided**, to be reviewed after genropy/genropy#1509 (GenroPy also accepts
  the bare name `p`).
- The period of `#PERIOD` cannot come from a column (`#PERIOD($date, $col)`):
  the period text is decoded in Python while the query is compiled, before any
  row exists. GenroPy does not expand that form either. Use
  `#IN_RANGE($date, $start, $end)` when the row holds the two dates, or a
  parameter (`:p`, `:env_p`) when the period is known before execution.
  **Decided.**
- `#ENV` is not ported: `:env_name` replaces it.

### 3.5 `table.column()` — Decided

- `table.column('name')`, `table.column('$name')` and
  `table.column('@customer_id.name')` return the same column the compiler
  resolves.
- A column offers `relatedTable()` and `relatedColumn()`, as in GenroPy.
- A missing plain name returns `None`; a path through a missing relation raises.
  This is GenroPy's behaviour, and `table.column('x') is not None` is the
  framework's way to test whether a table has a column. **Decided.**
- Exceptions form one hierarchy rooted in `GnrSqlException` (GenroPy name), one
  class per case: `GnrSqlMissingTable`, `GnrSqlMissingField` (missing relation),
  `GnrSqlMissingColumn` (missing final column of a path),
  `GnrSqlInvalidVirtualColumn`, `GnrSqlRelationError` (relation declaration).
  In GenroPy these derive from `GnrException` and escape
  `except GnrSqlException`. **Decided.**

## 4. Selecting columns

### 4.1 `*` — Decided

`*` selects, in declaration order, the physical columns (columns with
`dtype='X'` only when `bagFields=True`; it is false in queries and true in
records), then the virtual columns declared `static=True`. This is GenroPy's
rule. Today asqueel also selects formulas and aliases; that changes.

### 4.2 Other expansions — Decided

| Form | asqueel | Reason |
|---|---|---|
| `*prefix_` | error | Superfluous; since 2020 GenroPy returns every column for it ([genropy/genropy#1504](https://github.com/genropy/genropy/issues/1504)) |
| `*name` (virtual column) | error | Only feeds `*@rel.(a,b)` |
| `*@rel`, `*@rel.prefix_` | error | No usage in indexed projects ([genropy/genropy#623](https://github.com/genropy/genropy/issues/623)) |
| `*@rel.(a,b)` | error | Removed by GEP 1 §9.6; replaced by `@rel.to_json($a, $b)` |

### 4.3 Automatic result names — Decided

A path without `AS` takes GenroPy's name: every non-alphanumeric character
becomes `_`, and a leading digit gets a `_` prefix. `@customer_id.name` becomes
`_customer_id_name`. GenroPy clients and exports compute the same name
(`genro_grid.js`, `apphandler/export.py`). Today asqueel produces
`customer_name`; that changes.

### 4.4 The `pkey` column and the count — Decided

- asqueel does not add a `pkey` column to query results. GenroPy adds
  `$<pkey> AS pkey` by default (`addPkeyColumn=True`), except for tables without
  a primary key, count mode, `distinct`, `group_by` and formula subqueries. That
  behaviour belongs to the future GenroPy adapter, not to the asqueel core.
- `count()` returns the same number as GenroPy for plain, `group_by` and
  `distinct` queries; it raises with `limit` or `offset`.

## 5. Effects on migrations

| Declaration | Database |
|---|---|
| `relation` | `FOREIGN KEY ... ON UPDATE CASCADE` + index on the source columns (sections 2.3, 2.5) |
| `weak_relation` | index on the source columns and, when not already covered, on the target columns |
| `compositeColumn(..., unique=True)` | `UNIQUE` on the member columns |
| `relation` on a composite | composite `FOREIGN KEY` + index |
| `colgroup` | nothing |
| virtual columns | nothing |

## 6. Planned, not part of this proposal

- **GEP 1 relation functions** on many-side relations.
- **`virtualRelation`**: filtered relations, links without a foreign key to a
  target that is not unique, one row chosen by order and limit
  (`virtualRelation('last_invoice', relation='@invoices', order_by='$date DESC', limit=1)`),
  read-only.
- **Macros** `#BAG`, `#BAGCOLS`, `TSQUERY`/`VECQUERY`, `#PREF`.
- **Grouping.** The core will provide what GenroPy's grouped view needs, for
  any interface: a declarative, serializable grouping request (breaks,
  aggregates from a closed list, filters, pivot); breaks on a hierarchical
  table that produce intermediate nodes with their totals at any depth;
  roll-up rules computed in Python over a flat SQL `GROUP BY`; drill-down by
  condition instead of a list of primary keys; chaining, where the condition
  of a group filters a new grouping; model metadata for the interface. The
  GenroPy adapter translates the legacy grid structure into the request and
  the result back into the legacy shape. **Direction decided**; details open.

## 7. Divergences from GenroPy

| GenroPy | asqueel | Reason |
|---|---|---|
| `relation()` without `mode` is logical; `mode='foreignkey'` adds the FK | `relation()` is the FK; `weak_relation()` is logical | 3555 of 4134 `.relation(` declarations (86%) in the 8 largest indexed application repositories use `mode='foreignkey'` |
| `mode='insensitive'` | `weak_relation(insensitive=True)` | a foreign key cannot compare case-insensitively; no usage of `mode='insensitive'` in the same repositories |
| `group='<name>.<NNN>'` on columns, `group_<name>=` on the table; `'_'`, `'*'`, `one_group`, `many_group` | `colgroup` only | the legacy encoding mixes grouping, ordering and interface visibility; its `colgroup` counter never advances (every column gets `.001`) |
| `*prefix_` returns every column | error | regression of commit `87e8c97018` (2020); genropy/genropy#1504 |
| `*@rel`, `*@rel.prefix_`, `*name`, `*@rel.(a,b)` | error | genropy/genropy#623; GEP 1 §9.6 |
| `indexed` on a relation is ignored (always indexed) | always indexed, skipped only when covered by leading columns of another key or index | GenroPy checks pkey membership, not leading position |
| a relation to a non-unique target is accepted | `relation`: error (database requirement); `weak_relation`: trusted; non-unique links: `virtualRelation` | silent row duplication in GenroPy navigation |
| moving a node under its descendant is not checked on the server | error | endless cascade; genropy/genropy#1523 |
| hierarchical triggers read parent and children with the draft and logical-deletion filters | read without filters | wrong paths; genropy/genropy#1524 |
| a moved node keeps its old sibling position; `_h_count` empty above 1295 siblings | last position under the new parent; explicit error above 1295 | duplicate positions and broken order; genropy/genropy#1525 |
| `LIKE` on paths without escape; no pattern index | escaped `LIKE`; `text_pattern_ops` index on PostgreSQL | ids contain `_`; prefix `LIKE` cannot use the index with a non-C collation; genropy/genropy#1526 |

## 8. Open decisions

| Id | Question |
|---|---|
| genropy/genropy#1509 | `#PERIOD`: whether the bare parameter name `p` stays valid next to `:p` |
| — | Parameters of `sys_fields`, `auto_counter`, `hierarchical` |
| — | Hierarchical: null path value, `/` in a path value, `copyFromParent`, `_parent_h_*` |
| — | Which GenroPy table attributes become `options` elements and which stay attributes of the table ([analysis 38](https://github.com/asqueel-org/asqueel/blob/main/docs/design/38-table-attributes-analysis.md)) |
| — | How a package registers its own options, the mechanism GenroPy packages emulate with table attributes and mixins (analysis 38 §7.3) |
| — | Which model-build hooks asqueel supports ([analysis 35](https://github.com/asqueel-org/asqueel/blob/main/docs/design/35-model-build-hooks.md)) |
| — | Primary key generation and new records: `pkeyValue`, `newPkeyValue`, `newRecord` |
