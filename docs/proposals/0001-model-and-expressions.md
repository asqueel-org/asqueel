# Proposal 0001 — Declaring models and writing expressions

| | |
|---|---|
| **Status** | Proposal — for team review |
| **Implementation** | Not yet in the code. asqueel 0.4.0 behaves as described in the current guide. |
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
  decision of a GenroPy proposal (GEP). Section 8 lists them.
- **An unsupported form raises an explicit error.** It never produces a
  different result.
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
  is no longer accepted. **Open** (plan 33, D2) — proposed: refused.
- A name used by a physical and a virtual column of the same table is an error.
  Today asqueel accepts it and the virtual column silently replaces the
  physical one. Whether to port GenroPy's `_override` escape: **Open**
  (plan 33, D4).

Supported column elements: `column`, `formulaColumn`, `aliasColumn`,
`subQueryColumn`, `pyColumn`, `compositeColumn`.
Not supported, with an explicit error: `joinColumn`, `bagItemColumn`,
`toolColumn`, `aliasTable`, `subtable`, `localized` and `ext_*` columns.

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
- Further attributes of `colgroup`: **Open** (plan 33, D6).

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
  parameter of `weak_relation`. These are `virtualRelation` cases; until it
  exists they raise an error.
- The rows of the many side are reached through the inverse relation (section
  3.2), not through a relation declared on the one side.
- Parameter names of `relation` and `weak_relation` (GenroPy `related_column`,
  `relation_name`, `onDelete`/`onDelete_sql`, `onUpdate`/`onUpdate_sql`
  against asqueel's current `to`, `back_reference`, `on_delete`,
  `on_update`): **Open** (plan 33, D10).

### 2.4 Composite keys

```python
tbl.compositeColumn('product_year_key', columns='product_id,year', unique=True)
tbl.compositeColumn('product_year_ref', columns='product_id,year').relation('invc.price_year.product_year_key')
```

- `unique=True` creates a multi-column `UNIQUE` constraint. **Decided**
  (same as GenroPy).
- `.relation(...)` on a composite targets another composite and joins the
  member columns in order. **Decided** (same as GenroPy).
- Whether the composite is also a selectable column whose value is GenroPy's
  JSON-like text `'["P1", 2024]'`, included in `*`: **Open** (plan 33, D3).

### 2.5 Indexes created by relations — Decided

- Every `relation` and every `weak_relation` creates an index on its source
  columns. Without it, inverse navigation and every `DELETE`/`UPDATE` of the
  referenced key read the whole source table; PostgreSQL does not create it.
- The index is not created when the source columns are already the leading
  columns of the primary key, of a `UNIQUE` constraint or of a declared index.
- There is no option to switch it off.
- An index on the target columns when they are not the target's primary key:
  **Open** (plan 33, D9) — proposed: created, as in GenroPy, unless the target
  is unique.

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
`@invoices.to_json($number, $date)`. The parser already recognises this form
and reports that it is not available yet.

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
- First macros: `#THIS`, `#IN_RANGE`, `#PERIOD`. **Open** (plan 32, D5).
- `#ENV` is not ported: `:env_name` replaces it.

### 3.5 `table.column()` — Decided

- `table.column('name')`, `table.column('$name')` and
  `table.column('@customer_id.name')` return the same column the compiler
  resolves.
- A column offers `relatedTable()` and `relatedColumn()`, as in GenroPy.
- A missing name: error or `None` (GenroPy returns `None` for a plain name and
  raises for a path): **Open** (plan 32, D3).
- Exception names (GenroPy `GnrSqlMissingField`, `GnrSqlMissingColumn`,
  `GnrSqlRelationError`): **Open** (plan 32, D8).

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

### 4.4 Still to decide

The column list of the count mode and the automatic `pkey` column: **Open**.

## 5. Effects on migrations

| Declaration | Database |
|---|---|
| `relation` | `FOREIGN KEY` + index on the source columns (section 2.5) |
| `weak_relation` | index on the source columns |
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

## 7. Breaking changes for asqueel 0.4 users

- Columns declared on the table instead of through `columns()` /
  `virtual_columns()` (if D2 is confirmed).
- `relation()` always creates a foreign key; the former
  `relation(foreign_key=False)` becomes `weak_relation()`;
  `case_insensitive=True` becomes `weak_relation(insensitive=True)`.
- `x_name` removed; outgoing relations are named after their column.
- `@customer.country.name` without `@` on intermediate segments removed.
- Automatic names `_customer_id_name` instead of `customer_name`.
- `*` no longer selects formulas and aliases that are not `static`.
- `indexed=False` on a relation removed.

## 8. Divergences from GenroPy

| GenroPy | asqueel | Reason |
|---|---|---|
| `relation()` without `mode` is logical; `mode='foreignkey'` adds the FK | `relation()` is the FK; `weak_relation()` is logical | 3555 of 4134 `.relation(` declarations (86%) in the 8 largest indexed application repositories use `mode='foreignkey'` |
| `mode='insensitive'` | `weak_relation(insensitive=True)` | a foreign key cannot compare case-insensitively; no usage of `mode='insensitive'` in the same repositories |
| `group='<name>.<NNN>'` on columns, `group_<name>=` on the table; `'_'`, `'*'`, `one_group`, `many_group` | `colgroup` only | the legacy encoding mixes grouping, ordering and interface visibility; its `colgroup` counter never advances (every column gets `.001`) |
| `*prefix_` returns every column | error | regression of commit `87e8c97018` (2020); genropy/genropy#1504 |
| `*@rel`, `*@rel.prefix_`, `*name`, `*@rel.(a,b)` | error | genropy/genropy#623; GEP 1 §9.6 |
| `indexed` on a relation is ignored (always indexed) | always indexed, skipped only when covered by leading columns of another key or index | GenroPy checks pkey membership, not leading position |
| a relation to a non-unique target is accepted | `relation`: error (database requirement); `weak_relation`: trusted; non-unique links: `virtualRelation` | silent row duplication in GenroPy navigation |

## 9. Open decisions

| Id | Question |
|---|---|
| Plan 33 D2 | Refuse the explicit containers `columns()` / `virtual_columns()` |
| Plan 33 D3 | Composite as a selectable JSON-like column |
| Plan 33 D4 | Port `_override` |
| Plan 33 D6 | Further `colgroup` attributes |
| Plan 33 D9 | Index on non-pkey target columns |
| Plan 33 D10 | Parameter names of `relation` / `weak_relation` |
| Plan 32 D3 | Missing name in `column()`: error or `None` |
| Plan 32 D5 | First macros |
| Plan 32 D8 | Exception names |
| — | Count mode column list; automatic `pkey` column |
