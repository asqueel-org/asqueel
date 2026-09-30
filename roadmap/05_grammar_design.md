# asqueel — SQL Model Grammar Design

**Version**: 0.2.0 · **Last Updated**: 2026-07-10 · **Status**: 🔴 DA REVISIONARE

The design document for the new SQL model grammar, built as a
genro-builders dialect in the `asqueel` package. It is grounded in
the legacy inventories `01`–`04` (see `00_INDEX.md`): every legacy
behavior referenced here has a file:line source in those documents.

---

## 1. Vision

Describe an entire database in Python through a builder grammar. The
**source tree is the single pivot**; every other representation is a
projection from/to the tree:

```
   .py idiomatic  ◀────┐   ┌────────────────────────┐   ┌──▶ DDL string (CREATE/ALTER)
   (emitter)           │   │      source tree       │   │    (SqlRenderer, partial/total)
                       ├───┤  package/table/column  ├───┤
   live DB        ────▶┘   │     (SqlBuilder)       │   └──▶ live objects (model runtime)
   (reader, introspect)    └────────────────────────┘        the object tree the app uses
                                      │  │
                normalized JSON ◀─────┘  └────▶ query compiler (later phase)
                (asqueel-migration)
```

- **Dual rendering** — the tree renders to two targets (see §1.1): a
  **DDL string** (create/update the DB) and a **live object model** (the
  runtime the app queries). The legacy "model obj" is just the second
  render target, not a separate compiled tree.
- **Renderer** (tree → DDL): partial (one table → its CREATE TABLE) or
  total; one renderer per SQL dialect.
- **Migration**: the tree projects into the normalized JSON of
  asqueel-migration (doc `03` §1), replacing the legacy
  `orm_extractor`; diff engine and command builder are reused as-is.
- **Round-trip** (like the XSD dialect): a reader (introspection → tree,
  the `db_extractor` queries already exist) and an emitter (tree →
  idiomatic .py — what the legacy package editor does).
- **Compiler** (later): `$col` / `@rel.col` / `:param` / `#macros`
  query compilation reading the same tree (contract in doc `02`).

Scope is **wider than the legacy**: the grammar reserves slots for the
entities the legacy migrate planned but never implemented (doc `03`
§6): views, functions, sequences, custom types, table triggers, CHECK
constraints, comments — plus extensions and event triggers which the
legacy handles only on the migrate side.

### 1.1 One tree, dual rendering (string AND live objects)

The core architectural decision (2026-07-06). A source tree does not
render only to a string. Exactly like **Textual** (render to live
widgets) and the **DOM** (render to nodes), the genro-builders engine
walks the tree **composing objects**, not concatenating strings (the
walk is object-based — no `"".join`). So the same `package/table/column`
source tree renders to **two targets**:

- **string → DDL** (`SqlRenderer`): `CREATE TABLE` / `ALTER TABLE`, to
  create and update the database (migrate, partial or total render);
- **live objects → the model runtime**: the `package/table/column`
  object hierarchy *with behavior*, which the application queries
  (`table.column('@rel.col')`, relation navigation, triggers).

This dissolves the legacy `DbModelSrc` (src) vs `DbModelObj` (obj)
duality: **there is one tree**. The legacy "model obj" is simply the
output of the render-to-objects target, not a second compiled tree kept
in sync with the first. The migrate and the DDL renderer are structural
consumers; the app consumes the live objects (behavior included).

*To verify against the engine when implementing*: the exact object-based
render hook (how children are composed into objects instead of joined
into a string). The capability exists (the Textual and DOM rails use
it); no SQL dialect uses it yet.

### 1.2 The object model: package/table/column with behavior

The runtime object hierarchy is `package → table → column` (legacy
`DbPackageObj`/`DbTableObj`/`DbColumnObj`) — which is **already the shape
of the source tree** (`db → schema → table → column`). Each level is an
object carrying data **and** behavior:

- **package/schema** → config, `sqlschema`/`sqlprefix`, macro
  registration, `custom_type_*`;
- **table** → the bulk of the logic: **triggers**
  (`onInserting`/`onInserted`/…), CRUD, user methods (`pyColumn_*`,
  `sql_formula_*`, …);
- **column** → metadata (dtype, size…), the relation, field-level
  triggers.

Behavior is of **two natures**, kept distinct:

- **structural / navigation** — generic, derived from the tree (resolve
  `@rel.col`, compose an sqlname, build joiners). Methods that read the
  tree.
- **application, per-table** — the triggers and custom methods, specific
  to each table, written by the user.

The per-table application logic attaches via a **sub-builder** per table
(each table is a sub-builder carrying its own methods) — mirroring the
legacy, where each table had its own `Table` class. *Mechanism to verify
against the engine.*

## 2. Agreed decisions

### 2.1 Hierarchy (base)

```
db                          # root of the model
├── schema                  # collection by name (legacy "package")
│   ├── table               # collection by name
│   │   ├── column          # physical
│   │   │   └── relation    # relation — child of ANY column kind
│   │   ├── aliasColumn     # relation_path
│   │   ├── formulaColumn   # sql_formula | select | exists
│   │   ├── subQueryColumn  # query + mode json|xml|aggr
│   │   ├── pyColumn        # py_method
│   │   ├── compositeColumn # composed_of — packs N columns as one key
│   │   ├── constraint      # UNIQUE / CHECK multi-column
│   │   ├── index
│   │   └── trigger         # [beyond legacy]
│   ├── view                # [beyond legacy]
│   ├── function            # [beyond legacy]
│   ├── sequence            # [beyond legacy]
│   └── dbtype              # ENUM/DOMAIN/COMPOSITE [beyond legacy]
├── extension               # [migrate-only in legacy]
└── eventTrigger            # [migrate-only in legacy]
```

`relation` is **always a child of a column**, never of a table: there
is a single way to declare a relationship. A relationship over more
than one column is expressed by putting the `relation` on a
`compositeColumn` that packs those columns as one key (see §2.4).

- **Direct children of table** — no plural container nodes
  (`t.column(...)`, not `t.columns.column(...)`): the tag types the
  node; projections group by entity.
- **`collection_key="name"`** on db/schema/table: children labelled by
  their own name → natural addressing (`public.customer.bank_id`),
  grammar-enforced name uniqueness, 1:1 projection onto the
  name-keyed dicts of the migration JSON.
- **`pkey` on the table, composite allowed** (`pkey="a,b"`), mapping to
  the JSON `pkeys` string.

### 2.2 Columns are a family of distinct elements

Each column kind is its own element (tag-dispatched by every consumer),
mirroring the legacy family (doc `01` §1.6–1.15). `bagItemColumn`,
`toolColumn`, `joinColumn` come later — they are sugar over the same
bases (and partly PG-specific: doc `01` §5.23).

`compositeColumn` is **first-class, not a later slice**: it packs N
physical columns as one named, navigable key, and is the mechanism for
composite pkey, composite unique and composite FK (§2.4). It must exist
regardless of relations (composite pkeys need it), so reusing it for
composite FKs keeps the model to one concept instead of two.

Column attributes: the physical plane is the migrate contract
(`dtype`, `size`, `notnull`, `sqldefault`, `unique`, `indexed`,
`extra_sql`, `generated_expression` — doc `03` §1.2) plus `sql_type`
as native escape hatch and `comment` (planned improvement in the
legacy). `dtype` uses the Genro normalized codes (doc `03` §5.1);
`sql_type`, when present, wins.

### 2.3 Open metadata everywhere

Every element accepts free kwargs stored as node attributes: the
semantic plane (`name_long`, `name_short`, `group`, validators,
trigger hooks, application extensions...) travels in the tree.
Consumers filter: the DDL renderer reads the physical plane, the
migration projection filters its keys, the future compiler reads the
semantic plane. This matches the legacy's open `**kwargs` (doc `01`
§2) without freezing the attribute inventory.

### 2.4 Relations: always on a column, virtual-friendly

**One declaration form only**: `relation` is a child of a column
(`column.relation('target')`), never of a table. This is the legacy
model — a single place where a relationship is born, the column that
carries the key. The table-level `from_columns`/`to_columns` form
(genro-proxy model, considered earlier) is **dropped**: it would be a
second way to express the same idea, redundant to maintain across
renderer, migrate and compiler.

- **Any column kind can carry a relation** — including virtual columns
  (formula/subquery/alias), which the legacy explicitly supports (doc
  `04` oracle #13: formula column with chained `.relation()`).
- **Multi-column (composite) relations go through a compositeColumn**
  (see §2.2): the relation stays on a single column (the composite),
  which packs N physical columns; the match is column-by-column under
  the hood. This is why compositeColumn is a first-class citizen, not
  an optional slice — it is *the* mechanism for composite keys (pkey,
  unique, FK) and their navigation. Example (doc `04`, `price_year`):

  ```python
  # target table: composite pkey packed as one column
  tbl.compositeColumn('product_year_key', columns='product_id,year', unique=True)

  # child table: composite FK = relation on ONE composite column
  tbl.compositeColumn('product_year_ref', columns='product_id,year') \
     .relation('price_year.product_year_key', relation_name='notes')
  ```

- **`to_columns` is deducible**: a relation with no explicit target
  columns points at the target table's pkey (composite pkey → the
  member columns). Only the *target* is deduced; whether it becomes a
  physical FK is a separate choice (`foreign_key`, below).
- **Relation mode → orthogonal flags** (resolves question 1): the
  legacy `mode` string (`relation|foreignkey|insensitive|custom`)
  multiplexed independent axes. Replaced by `foreign_key=True/False`
  (emit the physical constraint? — **default False**, i.e. a relation is
  logical/navigable unless the physical FK is explicitly requested, as
  in the legacy) and `case_insensitive=True/False` (`lower()=lower()`
  match); `cnd`/`join_on` are ordinary attributes.
  `custom` disappears — in the legacy it was an inert label auto-set
  when a `cnd` was present (`gnrsqlmodel/columns.py:227-229`), never
  read to make a decision.
- **Inverse-relation naming — path vs label kept separate** (resolves
  question 2, decided 2026-07-06). Two orthogonal axes, never merged
  (the legacy `relation_name` did both jobs — see doc `01` §5.12–13):
  - **path** (technical, navigable identifier, unique per table): the
    "one" side needs nothing — it navigates via the FK column itself
    (`@customer_id`); the "many" side takes **`back_reference`**
    (`@invoices` from customer). Default = the child table's name when
    unambiguous; **mandatory with a loud error** when two FKs target the
    same table (the `comune_nascita`/`comune_residenza` case) — no
    auto-generated ugly `pkg_table_column` names.
  - **name** (human label, translatable `!!...`, spaces allowed, not
    unique): **`one_name`** = how the many-side sees the one
    (from invoice: "Cliente"); **`many_name`** = how the one-side sees
    the many (from customer: "Fatture").
  - `private_relation` (legacy implicit flag) is dropped: exclusion from
    auto-navigation becomes an explicit `navigable=False`.
  - `one_one` becomes a boolean flag (`one_one=True`), not the magic
    string `'*'`.
  - Filtered back-relations (genro-proxy `add_back(condition)`)
    **deferred** — parent of `subtable` (question 4).
- **Two remaining planes kept separate**, as in the legacy (doc `01`
  §1.18, §3): semantic (`eager_*`, `one_group`/`many_group`,
  python-level `onDelete`/`onUpdate`, `onDuplicate`) vs physical
  (`onDelete_sql`/`onUpdate_sql`, `deferred` → the FK the migrate sees).
- **Coherence rule in the grammar**: a relation under a virtual column
  cannot be `foreign_key=True` (no SQL constraint from a formula);
  the migrate projects only physical FK relations (legacy: FK emitted
  only if `joiner['foreignkey']`, doc `03` §2.3), the compiler
  navigates them all.

The default of `foreign_key` is **False** (decided 2026-07-06):
relations are logical/navigable by default, the physical constraint is
opt-in.

### 2.5 Style

- **kwargs only** (builders convention); no `name::dtype` positional
  shorthand (inconsistent even in the legacy — doc `01` §5.3).
- camelCase for grammar names per NAMING_CONVENTIONS.md.
- Loud errors, no silent fallbacks (contrast with legacy `addRelation`
  swallowing all exceptions — doc `01` §5.10).

### 2.6 Views (deferred — reminder)

Views are **not designed now**, kept as a reminder for a later slice.
Notes captured (2026-07-06) for when we resume:

- **Definition from a Genropy query**: the compiler returns SQL, so a
  view can be defined pythonically (`columns`/`where`/… even
  multi-table) and compiled to the `SELECT` that goes into
  `CREATE VIEW`. Raw-SQL `definition="SELECT ..."` is the interim form
  usable before the compiler exists.
- **Migrate**: `CREATE OR REPLACE VIEW` (idempotent). The diff ("has the
  view changed?") is the hard part — PostgreSQL rewrites the stored
  definition (`pg_get_viewdef` qualifies names, adds casts), so a
  literal compare always reports a change. First idea: **normalize
  whitespace and compare**; since Postgres rewrites more than spacing,
  the robust route is to **hash the declared (source) definition** and
  compare that, independent of how Postgres stores it.
- **Materialized views**: same construct with a `materialized=True` flag
  (refresh is a separate op from create) — also deferred.
- Views and subtables are **complementary, not substitutes**: subtable =
  a named subset/subtype of the *same physical table* (query-time
  filter, writable); view = a derived DB object (possibly multi-table,
  persistent, read-only). The legacy had only subtables because views
  were never implemented (planned in the migrate, doc `03` §6).

### 2.7 Reusable column blocks (sysFields generalized)

`sysFields` is one case of a broader idea (2026-07-06): **reusable
blocks of columns** included across tables — an `address` block
(street, number, zip, city, province), an `identity` block
(first_name, last_name), a `contacts` block. Declare the block once,
include it wherever needed.

- **Build-time, real columns**: a block expands into actual persistent
  `column` nodes (the migrate creates them), not a render-time ephemeral
  expansion. So the mechanism is build-time. `sysFields` is the "audit"
  block; `draftField`/`logicalDeletion`/`counter` are separate blocks.
- **Parametric / prefix** — the key improvement over the legacy: a block
  is often included **more than once in the same table** (residential
  vs shipping address → `residential_city`, `shipping_city`), so a block
  takes a prefix or parameters.
- **Mechanism candidate: `struct_method`** (build-time, materializes
  columns) rather than `@component` (render-time, ephemeral). *To verify
  against the engine.*
- **Distinct from `colgroup`** (question 5): a colgroup is a *local
  visual grouping* of already-declared columns; a block is a *shared
  template* of columns. Related — a block may carry its own colgroup for
  the UI — but different concepts.
- These blocks are part of the application layer (question 3), not the
  pure base grammar: they encode Genropy conventions, expanding into
  pure-grammar columns.

## 3. Design questions raised by the inventories (to discuss)

Ordered; each is a separate decision to take one at a time.

1. ~~**Relation mode as orthogonal flags.**~~ **RESOLVED** (2026-07-06):
   the `mode` string is replaced by `foreign_key=True/False` and
   `case_insensitive=True/False`; `cnd`/`join_on` are ordinary
   attributes; `custom` disappears (inert label). Also decided in the
   same discussion: relations are always on a column (no table-level
   form), composite relations go through a compositeColumn, `to_columns`
   defaults to the target pkey. See §2.4.
   - **1b — RESOLVED** (2026-07-06): `foreign_key` defaults to **False**
     — relations are logical/navigable by default, the physical
     constraint is opt-in (legacy behavior).
2. ~~**Back-relation naming.**~~ **RESOLVED** (2026-07-06): path vs
   label separated. `back_reference` = navigable path of the "many"
   side (`@invoices`), mandatory-with-error on ambiguity, default =
   child table name; `one_name`/`many_name` = human labels of the two
   directions. `private_relation` → explicit `navigable=False`;
   `one_one='*'` → `one_one=True`. Filtered back-relations deferred
   (parent of question 4). See §2.4.
3. **Table-header system patterns.** `sysFields` (id/ins_ts/draft/
   logical deletion/counter/hierarchical), `rowcaption`/`caption_field`,
   `partition_*`, `multi_tenant`, `lookup` (doc `04` §2c, oracle #8,
   #14, #19). These live ABOVE the pure grammar in the legacy (dbo
   mixins). Decide what is grammar, what is a downstream layer.
4. **subtable.** Two unrelated meanings in the legacy (doc `01` §5.22):
   package-level single-table inheritance (discriminator column) and
   table-level named filter. Probably two distinct elements — names to
   be chosen.
5. **colgroup.** Ordinal group labelling with side effects on the table
   node (doc `01` §1.5). Keep, redesign, or drop to downstream?
6. **Extension mechanism.** Legacy mixins (`config_db`,
   `config_db_<pkg>`, `ext_*` hooks, `custom_type_<dtype>` — doc `01`
   §5.16–17). The builders engine has components/sub-builders/
   struct_methods; map the use cases.
7. **PG leakage.** bagItem xpath formulas, json/xml aggregation SQL,
   tool HTML-in-SQL are PostgreSQL-specific text generated at grammar
   time in the legacy (doc `01` §5.23). In the new design the grammar
   stores intent (declarative attributes); the renderer/dialect emits
   SQL. This moves `subQueryColumn` mode json/xml expansion into the
   renderer.
8. **Deferred validation.** compositeColumn validates at build end
   (doc `01` §1.10); the builders engine has its own lifecycle
   (create/preprocess) — map deferral onto it.
9. **Localized / variant / encrypted columns.** Stringly-typed,
   env-dependent machinery in the legacy (doc `01` §5.20–21). Decide
   which enter the grammar now and in what shape.
10. **Naming of implicit indexes.** Three conventions in the legacy
    (doc `01` §5.11); the migrate uses structural hashed names (doc
    `03` §1.3). Proposal: adopt the hashed-name model everywhere.

## 4. Implementation plan (slices)

1. **Slice 1 — base grammar**: `db`, `schema`, `table`, `column`,
   `aliasColumn`, `formulaColumn`, `subQueryColumn`, `pyColumn`,
   `compositeColumn`, `relation` (on a column, incl. composite),
   `constraint`, `index`. Tests from the oracle shortlist (doc `04` §6,
   items 1–7, 10, 16). compositeColumn is in this slice because
   composite pkey/unique/FK all depend on it.
2. **Slice 2 — DDL renderer** (CREATE TABLE first, postgres dialect),
   validated against the exact-SQL expectations of
   `test_gnrsqlmigration.py`.
3. **Slice 3 — migration projection** (tree → normalized JSON),
   plugging into asqueel-migration.
4. **Slice 4 — beyond-legacy entities** (view, function, sequence,
   dbtype, trigger, extension, eventTrigger, CHECK, comments).
5. **Slice 5 — round-trip** (reader + emitter).
6. **Later — query compiler** (doc `02` as contract).

---

## 5. Package layout and the legacy dialect (2026-07-10)

Decisions taken by the project owner, recorded here (they refine, but do
not replace, §2–§4).

### 5.1 Folder layout per grammar dialect

`src/asqueel/` is organised in one sub-package per grammar dialect,
plus a shared base:

- **`base/`** — shared base classes (a common builder base and/or a
  renderer base) used by every dialect. Kept minimal: nothing is added
  here speculatively. As of this slice the two dialects share no concrete
  code, so `base/` carries only its role docstring.
- **`legacy/`** — the backward-compatible grammar. It lets an existing
  GenroPy legacy model (`DbModelSrc`) be ported almost verbatim: same
  element names and same attribute names as the legacy inventory
  (doc `01`), while obeying the builders conventions.
- **`modern/`** — the current optimized grammar (§2.4/§2.5), moved from
  the previous flat `sql_builder.py` / `sql_elements.py` /
  `sql_renderer.py` **as-is** (no behavioural change in this slice).

### 5.2 The legacy dialect comes first

The legacy dialect is implemented before the modern one is completed: it
is the migration path for the existing models. Its element and attribute
names are taken **verbatim** from doc `01`. The only deliberate
divergences from legacy source-compatibility are the builders
conventions:

- kwargs only (no positional magic, no `name::dtype` shorthand);
- no silent string-to-bool coercions (legacy coerced `indexed`/`unique`
  string flags — doc `01` §1.6);
- loud errors instead of silent fallbacks (contrast the legacy
  `addRelation` swallowing all exceptions — doc `01` §5.10).

Everything else — including the open `**kwargs` plane, so that
application/extension metadata (`ltx_*`, `variant_*`, `ext_*`, …) lands
untouched as node attributes — mirrors the legacy grammar.

### 5.3 Backend-specific grammar goes into composable mixins

Backend-specific vocabulary (e.g. a future `PostgresElements` carrying
`extension`, `eventTrigger`, `dbtype`) is **not** part of the
backend-abstract core grammar: it is a composable grammar mixin, added
to a builder alongside the core element mixin. This is **documented only**
now; no backend mixin is implemented in this slice.

### 5.4 `sysFields` is not grammar

`sysFields` is a legacy **helper method** (a table-header convenience that
expands into audit columns — doc `01` §5.18, `checkAutoStatic`), not a
grammar element. It is therefore **excluded** from the legacy dialect
grammar. The broader "reusable column blocks" idea (§2.7) covers the same
need at the application layer, out of the pure grammar.

---

## Riferimenti

- Session: `ce254e4b-4c8c-49ae-a635-12536130ad35` (2026-07-06)
- Inventories: `01_legacy_model_grammar.md`, `02_legacy_compiler_query.md`, `03_legacy_migration_adapters.md`, `04_legacy_tests_inventory.md`
- Design decisions taken in review are dated inline (§2.4, §3 q1).
- `genro-proxy/src/genro_proxy/sql/relation.py` was surveyed for the
  table-level relation form; that form was **not** adopted (§2.4).
