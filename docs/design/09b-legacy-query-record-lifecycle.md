# 09b — Legacy query, record, and selection lifecycle

Internal architecture audit, 2026-09-29. This document describes observed source
behavior and architectural decisions still needed for the product-level API
`db.table('cont.cliente').query(...).fetch()`. It does not declare that API
implemented. The existing compiler/runtime are useful lower-level components;
adding convenience method names alone would not reproduce the product contract.

## Evidence and scope

Legacy source inspected: `/Users/gporcari/Sviluppo/Genropy/genropy`, revision
`fa35e5adfa6ad1b269f3a22a9b12c4c1ee6513ea`. This is the current local source,
not the older `e12…` baseline used by earlier research documents. Source links
below identify concrete local files and line anchors at that revision. Existing
`REVIEW` comments in the legacy tree are not treated as evidence independently
of the executable statements.

Current implementation inspected in this repository: synchronous runtime,
common query compiler, PostgreSQL dialect/driver, row policies, and environment
binding. The repository HEAD at inspection is
`bf66bcacfeededc7f0ce82cd5c48f6437aa174df`; local working-tree source is the
implementation being compared. This is source analysis, not a claim that the
complete legacy application was booted or that every described branch was
executed during this audit.

### Source map

| ID | Responsibility | Source |
|---|---|---|
| L1 | Database table lookup and query forwarding | [gnrsql/query.py:232](/Users/gporcari/Sviluppo/Genropy/genropy/gnrpy/gnr/sql/gnrsql/query.py:232) |
| L2 | Table query entry point and defaults | [gnrsqltable/query.py:122](/Users/gporcari/Sviluppo/Genropy/genropy/gnrpy/gnr/sql/gnrsqltable/query.py:122) |
| L3 | SqlQuery construction and compilation | [gnrsqldata/query.py:143](/Users/gporcari/Sviluppo/Genropy/genropy/gnrpy/gnr/sql/gnrsqldata/query.py:143) |
| L4 | Execution-time environment and transaction behavior | [gnrsql/execute.py:46](/Users/gporcari/Sviluppo/Genropy/genropy/gnrpy/gnr/sql/gnrsql/execute.py:46) |
| L5 | Query compilation and policy/default processing | [gnrsqldata/compiler.py:831](/Users/gporcari/Sviluppo/Genropy/genropy/gnrpy/gnr/sql/gnrsqldata/compiler.py:831) |
| L6 | Table record entry point | [gnrsqltable/record.py:309](/Users/gporcari/Sviluppo/Genropy/genropy/gnrpy/gnr/sql/gnrsqltable/record.py:309) |
| L7 | Record construction, compilation, cardinality | [gnrsqldata/record.py:186](/Users/gporcari/Sviluppo/Genropy/genropy/gnrpy/gnr/sql/gnrsqldata/record.py:186) |
| L8 | Record-specific compiled shape/result map | [gnrsqldata/compiler.py:1106](/Users/gporcari/Sviluppo/Genropy/genropy/gnrpy/gnr/sql/gnrsqldata/compiler.py:1106) |
| L9 | Materialized selection and output pipeline | [gnrsqldata/selection.py:82](/Users/gporcari/Sviluppo/Genropy/genropy/gnrpy/gnr/sql/gnrsqldata/selection.py:82) |
| L10 | Named/positional legacy row access | [gnrlist.py:173](/Users/gporcari/Sviluppo/Genropy/genropy/gnrpy/gnr/core/gnrlist.py:173) |
| N1 | Current compiler/plan construction | [compiler.py:416](/Users/gporcari/Sviluppo/genro_ng/meta-genro-modules/sub-projects/genro-sql/src/genro_sql/compiler.py:416) |
| N2 | Current transaction and execution facade | [runtime.py:20](/Users/gporcari/Sviluppo/genro_ng/meta-genro-modules/sub-projects/genro-sql/src/genro_sql/runtime.py:20) |
| N3 | Current row materialization and metadata validation | [drivers/psycopg.py](/Users/gporcari/Sviluppo/genro_ng/meta-genro-modules/sub-projects/genro-sql/src/genro_sql/drivers/psycopg.py) |
| N4 | Current model, result, and environment contracts | [contracts.py](/Users/gporcari/Sviluppo/genro_ng/meta-genro-modules/sub-projects/genro-sql/src/genro_sql/contracts.py) |

## 1. Public call trace: table → query → fetch

The ordinary application path is:

```text
db.table('cont.cliente')
  → db.model.table(...)
  → model table's dbtable object (or _mixinobj during model construction)
  → table.query(columns=..., where=..., **bindings)
      → decorators extract jc_* arguments / attach comment / audit
      → SqlQuery(table, options, sqlparams, extra kwargs)
      → no cursor or SQL execution yet
  → query.fetch()
      → query.cursor()
          → temporary currentImplementation context
          → query.sqltext
              → query.compiled, cached after first access
                  → query.compileQuery()
                  → SqlQueryCompiler(...).compiledQuery(...)
              → compiled.get_sqltext(db)
              → adapter.compileSql(...)
          → db.execute(sql, query.sqlparams, dbtable, storename)
              → execution-time env_* lookup and adapter argument preparation
              → cursor.execute(...)
      → cursor.fetchall()
      → cursor.close()
      → Python-column evaluation, decryption, Bag decoding
      → row list
```

Evidence: L1–L5; terminal fetch implementation at
[query.py:235](/Users/gporcari/Sviluppo/Genropy/genropy/gnrpy/gnr/sql/gnrsqldata/query.py:235).
The table entry point is decorated with `extract_kwargs(jc=True)`; its loop over
`jc_kwargs.values()` must therefore be read with the decorator, not diagnosed
as an unconditional failure from the bare Python default `None`.

The application-facing table is not merely a `Table` descriptor. It carries its
own methods, database reference, model, implementation context, permission hooks,
relation helpers, and package defaults. Current `ResolvedModel.table(...)`
returns metadata; it is not the missing application table handle.

### Default contract before any SQL is executed

The table/query layers establish the following defaults:

| Behavior | Observed legacy rule | Current lower-level behavior |
|---|---|---|
| Unspecified/falsy columns | Replaced with `'*'` in SqlQuery construction | `columns='*'` default; explicit `None`/empty projections are rejected |
| Primary-key projection | `addPkeyColumn=True` when a pkey exists; compiler can add a `pkey` alias | No implicit extra pkey projection |
| Table-defined ordering | Used when explicit ordering is falsy and query initially nonaggregate | Only explicit ordering is rendered |
| Draft/deletion | Both excluded by default for ordinary queries | Matching native defaults when policies are explicitly declared |
| Partition | Legacy provider default enabled; first partition declaration and truthy context rules | Explicit validated multiple scopes, strict missing-context rules, AND semantics |
| Bag fields | Query `bagFields=False`, promoted to true by `for_update` | Bag result decoding is not implemented |
| Locking | `for_update` is accepted and reaches compiled SQL | No FOR UPDATE option in current query plan/compiler |
| Store | Table package default can populate `_storename` | No store routing |
| Parameters | `sqlparams` plus arbitrary extra keyword bindings | Explicit `params` mapping; unsupported options rejected |

Sources: L2–L3, and
[compiler.py:899](/Users/gporcari/Sviluppo/Genropy/genropy/gnrpy/gnr/sql/gnrsqldata/compiler.py:899).
These differences affect returned columns, order, visibility, and lock lifetime;
they are not equivalent to changing only the spelling of `params`.

## 2. Two different kinds of laziness

### 2.1 Query objects cache compilation, not fetched rows

`SqlQuery.__init__` sets `_compiled=None`. The `compiled` property fills that
cache once. Accessing `sqltext` or calling `test()` triggers compilation, even
without database execution. `fetch()`, `selection()`, and `cursor()` each
execute; they do not reuse a cached row list.

Thus two `fetch()` calls can observe different database contents while using
the same compiled structure. A debugging call can advance the moment at which
structural context is evaluated.

Source anchors:
[query.py:210](/Users/gporcari/Sviluppo/Genropy/genropy/gnrpy/gnr/sql/gnrsqldata/query.py:210),
[query.py:401](/Users/gporcari/Sviluppo/Genropy/genropy/gnrpy/gnr/sql/gnrsqldata/query.py:401).

The object also exposes mutable `querypars`, `sqlparams`, `relationDict`, and
join conditions. `setJoinCondition()` updates the condition dictionary without
invalidating an already populated `_compiled`. A nonempty supplied `sqlparams`
dictionary is retained and updated with extra keyword arguments; it is not
unconditionally copied. A new facade should not accidentally inherit these
mutation/cache interactions.

### 2.2 Environment resolution happens at more than one time

Compilation reads structural environment: subtable selection, injected
environment conditions, partition choice, macros/providers, and store-dependent
columns. Execution then scans SQL for `:env_*`, reads `db.currentEnv`, and merges
explicit SQL arguments over those values. Missing environment values become
`None` through `.get()`, with special fallback handling for `env_workdate`.

Sources:
[compiler.py:954](/Users/gporcari/Sviluppo/Genropy/genropy/gnrpy/gnr/sql/gnrsqldata/compiler.py:954),
[execute.py:92](/Users/gporcari/Sviluppo/Genropy/genropy/gnrpy/gnr/sql/gnrsql/execute.py:92).

Concrete consequence:

```text
Construct Q under context A       → no compilation yet
Read Q.sqltext under context B    → structure can now be cached from B
Call Q.fetch under context C      → cached structure + current env_* values from C
```

This is not a coherent immutable snapshot contract. It also is not purely
late-bound query evaluation: structural decisions may already be frozen.

The current native compiler deliberately captures one environment snapshot
when building a plan, binds its used values, records relevant missing keys,
and rejects incompatible reuse at runtime. That is a meaningful improvement,
but a product Query wrapper must decide *when* to call this compiler.

**Recommended native behavior:** constructing a query stores intent; each
terminal execution compiles in the current environment, then executes that
bound query. An explicit compiled-query artifact retains today's snapshot and
reuse guard. Inspecting SQL should not silently pin the environment of later
fetches. This recommendation is not yet an implemented public contract.

## 3. Fetch results are more than cursor tuples

Legacy fetch rows normally support both named and positional access through
`GnrNamedList`: `row['name']`, `row[0]`, list ordering, and mapping-style helpers.
Current `QueryResult.rows` contains ordinary dictionaries. A wrapper returning
`result.rows` would preserve named lookups but break numeric lookups and other
row methods. Decide whether the native product offers plain mappings while an
explicit legacy adapter supplies named-list compatibility.

L10 documents and implements the dual access semantics. Do not confuse a
`SqlSelection`'s column index mapping with metadata returned by an ordinary
`fetch()`; the ordinary terminal returns the rows themselves.

The single-cursor fetch pipeline is ordered:

1. Fetch and close the cursor.
2. Evaluate Python virtual-column handlers.
3. Decrypt encrypted fields.
4. Decode/expand declared Bag columns.

Sources:
[query.py:241](/Users/gporcari/Sviluppo/Genropy/genropy/gnrpy/gnr/sql/gnrsqldata/query.py:241),
[query.py:295](/Users/gporcari/Sviluppo/Genropy/genropy/gnrpy/gnr/sql/gnrsqldata/query.py:295).

Current dtype/UI metadata does not perform those transformations. A successful
SQL fetch returning encrypted text, a serialized Bag, or a Python-column
placeholder is not equivalent to the expected application result. Unsupported
model/output features must be identified before claiming facade compatibility.

The multi-cursor fetch branch returns before the same postprocessing pipeline.
This is a source-observed inconsistency to exclude from any blanket parity
promise; store support is deferred rather than reproduced accidentally.

### Convenience terminal contracts

| Method | Observed behavior requiring a decision |
|---|---|
| `fetchPkeys()` | Calls fetch and extracts the table's physical logical pkey name from each row; this is not simply “take the first result column.” |
| `fetchAsDict(key=...)` | Builds a mapping; duplicate keys overwrite earlier entries. Ordered mode changes mapping type, not SQL ordering. |
| `fetchGrouped(key=...)` | Explicitly groups rows into lists by a selected key. This is a requested output operation, distinct from hidden join-row aggregation. |
| `fetchAsBag()` | Builds a Bag with row values in node attributes, not a generic JSON conversion. |
| `fetchAsJson()` | Applies legacy serialization including datetime handling and fallback string conversion. |

Source:
[query.py:320](/Users/gporcari/Sviluppo/Genropy/genropy/gnrpy/gnr/sql/gnrsqldata/query.py:320).
For a partial projection, verify that the selected key actually exists; do not
silently substitute the compiler's synthetic `pkey` alias or a positional value.

## 4. Count is its own terminal, not length of fetch

`SqlQuery.count()` calls `compileQuery(count=True)` directly and therefore does
not necessarily use the cached `query.compiled`. It executes the count-specific
SQL, then interprets either a single `gnr_row_count` value or the number of
returned rows/groups. Distinct/grouped queries have different paths; multi-store
counts sum store-specific results.

Sources:
[query.py:557](/Users/gporcari/Sviluppo/Genropy/genropy/gnrpy/gnr/sql/gnrsqldata/query.py:557),
[compiler.py:937](/Users/gporcari/Sviluppo/Genropy/genropy/gnrpy/gnr/sql/gnrsqldata/compiler.py:937).

The compiler removes ordering in count mode. It does not establish a clean
universal “total ignoring pagination” rule: `limit` and `offset` still reach the
compiled query. Counting groups, counting distinct results, counting root rows,
and counting the current page require distinct semantic decisions.

The current compiler can accept an authored `COUNT(*) AS n` projection, but it
has no count terminal or grouping/distinct plan model. A facade cannot safely
implement `count()` by replacing arbitrary projections with COUNT(*) or by
returning `len(fetch())` and still claim those legacy contracts.

Acceptance examples must cover an ungrouped filter, a limited query, grouped
results, distinct results, NULLs, and relation fan-out. Define pagination
semantics explicitly before implementing the public count terminal.

## 5. Selection is a materialized collection with behavior

The trace is different from an ordinary fetch:

```text
query.selection(...)
  → _dofetch(pyWhere)
  → cursor column index + materialized data + result postprocessing
  → _prepColAttrs(index)
  → SqlSelection(table, data, index, colAttrs, querypars, key, ...)
  → selection.output(mode, ...), sorting/filtering/key operations
```

Sources:
[query.py:411](/Users/gporcari/Sviluppo/Genropy/genropy/gnrpy/gnr/sql/gnrsqldata/query.py:411),
[query.py:446](/Users/gporcari/Sviluppo/Genropy/genropy/gnrpy/gnr/sql/gnrsqldata/query.py:446), L9.

`_prepColAttrs` resolves aliases and relation expressions back to model columns,
handles synthetic `pkey`, merges requested permission metadata, removes the
comment, translates `dtype` to `dataType`, translates `name_long` to `label`, and
includes print width. Current `ResultColumn(dtype, source, ui)` is a cleaner
basis but is not this existing consumer schema.

`SqlSelection` keeps rows, query parameters, table identity, column attributes,
key/index state, sorting/filtering state, join context, and optional frozen-data
storage. `output()` dispatches to data, dictlist, JSON, Bag, grid, records,
pkeylist, text, and other modes. Output-level offset/limit/filtering act on
already materialized data; they are not SQL pagination. Some record-based modes
can trigger additional record loads through resolvers.

Sources:
[selection.py:256](/Users/gporcari/Sviluppo/Genropy/genropy/gnrpy/gnr/sql/gnrsqldata/selection.py:256),
[selection.py:862](/Users/gporcari/Sviluppo/Genropy/genropy/gnrpy/gnr/sql/gnrsqldata/selection.py:862),
[selection.py:1096](/Users/gporcari/Sviluppo/Genropy/genropy/gnrpy/gnr/sql/gnrsqldata/selection.py:1096).

**Acquired change:** `_aggregateRows`/`aggregateRows` must disappear, including
from compatibility code. A selection cannot implicitly fold exploded join rows
or deduplicate legitimate values in Python. Explicit grouping requested by the
caller or explicit SQL collection/aggregation operations require their own
contracts and must not reintroduce that behavior under another method name.

## 6. Record lookup is a separate contract

The record path is:

```text
table.record(pkey=..., where=..., mode=None, ...)
  → SqlRecord(...), with _compiled=None and _result=None
  → if mode supplied: record.output(mode) immediately
  → otherwise return lazy record object
record.output('dict' / 'bag' / ...)
  → result access
      → compile record-specific SELECT if needed
      → require a usable selector
      → execute, fetch all candidate rows, close cursor
      → enforce record cardinality / missing-record behavior
      → cache _result
  → build requested output using record result map and resolvers
```

Sources: L6–L8 and
[record.py:263](/Users/gporcari/Sviluppo/Genropy/genropy/gnrpy/gnr/sql/gnrsqldata/record.py:263).
Unlike SqlQuery, SqlRecord caches both its compiled representation and its
loaded result. Repeated output conversions generally reuse the root record,
while relation resolvers may perform later database reads.

### 6.1 Selector precedence

The implemented priority is:

1. Truthy explicit `where`.
2. Otherwise `pkey is not None`, including `0`.
3. Otherwise equality predicates for supplied parameter names recognized as
   table columns.

If no selector survives, execution raises `RecordSelectionError`. The separate
serialized composite-key conversion uses a truthy pkey check and string syntax;
it should not be mistaken for a fully typed composite-key API.

Source:
[record.py:290](/Users/gporcari/Sviluppo/Genropy/genropy/gnrpy/gnr/sql/gnrsqldata/record.py:290).
The kwargs fallback manually assembles field references rather than following
the same robust logical-to-physical naming path as an explicit `$field`.
Preserve selector precedence as an explicit compatibility decision; improve
identifier resolution rather than copying text assembly.

### 6.2 Cardinality and deletion behavior

Record execution distinguishes zero, one, and multiple root candidates:

- Zero raises `RecordNotExistingError`, unless `ignoreMissing=True`, which
  stores an empty Bag result.
- One is accepted, even if logically deleted.
- Multiple candidates may first be collapsed by legacy exploding-record logic;
  then logically deleted candidates are removed if a deletion field exists.
  One remaining live row is accepted. Otherwise `ignoreDuplicate` can select
  the first candidate, or `RecordDuplicateError` is raised.

Source:
[record.py:319](/Users/gporcari/Sviluppo/Genropy/genropy/gnrpy/gnr/sql/gnrsqldata/record.py:319).
The “multiple candidates all deleted + ignoreDuplicate” branch indexes the
filtered list without a nonempty check. This is an anomaly, not a target behavior.

`compiledRecordQuery()` builds physical columns, requested virtual columns,
relation metadata, and a result map. It does **not** run the ordinary query
pipeline that adds draft/deleted/partition/subtable defaults, and it does not
set `LIMIT 1`. `_recordWhere` resolves the supplied selector only.

Sources: L8 and
[compiler.py:1399](/Users/gporcari/Sviluppo/Genropy/genropy/gnrpy/gnr/sql/gnrsqldata/compiler.py:1399).
Therefore implementing record lookup as `select(..., limit=1)` would silently
hide duplicates, change deleted/draft visibility, and lose the record data
shape. A native record contract must separately choose visibility and enforce
cardinality. The current stricter partition behavior must not be bypassed
implicitly merely to mimic the older record path.

Where root-row uniqueness is proven and no expansion exists, fetching at most
two rows could implement an exactly-one cardinality check. That is an execution
strategy, not permission to accept the first row silently.

### 6.3 Record shape and lazy relations

Record SQL aliases physical fields as `t0_<field>` and retains relation/field
attributes in `resultmap`. Output modes are materially different:

| Output | Contract |
|---|---|
| `dict` | Flat values with root alias prefix removed, Python-column handling and decryption. |
| `record` | A plain Bag without relationship resolvers. |
| `bag` | A SqlRecordBag containing fields and lazy relationship resolvers. |
| `newrecord` / `sample` | Default/sample construction paths, not ordinary existing-row SELECTs. |
| `json` | Serialization of record dict output. |

Sources:
[record.py:414](/Users/gporcari/Sviluppo/Genropy/genropy/gnrpy/gnr/sql/gnrsqldata/record.py:414),
[record.py:456](/Users/gporcari/Sviluppo/Genropy/genropy/gnrpy/gnr/sql/gnrsqldata/record.py:456),
[record.py:509](/Users/gporcari/Sviluppo/Genropy/genropy/gnrpy/gnr/sql/gnrsqldata/record.py:509).
The flat dict path strips a fixed three-character prefix in this revision;
nondefault alias prefixes therefore need characterization, not blind reuse.

The record map distinguishes one-side, one-to-one, and many-side relationships.
Bag output can attach resolvers that later instantiate another record or
related query; changing a foreign-key Bag node can refresh its resolver.
A related selection uses query defaults, whereas a related record uses the
record path. Uniformly applying the parent's query policy to every lazy relation
would be a behavior change.

Sources:
[compiler.py:1187](/Users/gporcari/Sviluppo/Genropy/genropy/gnrpy/gnr/sql/gnrsqldata/compiler.py:1187),
[record.py:94](/Users/gporcari/Sviluppo/Genropy/genropy/gnrpy/gnr/sql/gnrsqldata/record.py:94),
[record.py:156](/Users/gporcari/Sviluppo/Genropy/genropy/gnrpy/gnr/sql/gnrsqldata/record.py:156),
[record.py:706](/Users/gporcari/Sviluppo/Genropy/genropy/gnrpy/gnr/sql/gnrsqldata/record.py:706).

`SqlRecordBag` additionally has a persistence-facing `save()` method: it merges
provided fields, dispatches to the table's insert/update according to `isNew`,
and changes that flag after insertion. A dictionary result is not an editable
record object with this lifecycle. Exposing native `save()` would require a
separate contract for defaults, dirty/original values, hooks, and transaction
ownership; the existing CRUD compiler alone does not establish it.

Source:
[record.py:782](/Users/gporcari/Sviluppo/Genropy/genropy/gnrpy/gnr/sql/gnrsqldata/record.py:782).

The legacy `aggregateRecords` helper also folds an exploded result before
record cardinality checks. The acquired prohibition on hidden Python
reaggregation must cover this route, not only the selection option named
`aggregateRows`. Record collections need explicit retrieval semantics instead.

## 7. Transaction and resource ownership are public semantics

Legacy `db.execute(..., autocommit=False)` obtains a cursor on the database's
current connection, marks the connection uncommitted, and returns the cursor.
It does not create and commit a fresh transaction for each ordinary query.
Exceptions invoke database rollback; explicit autocommit is a separate option.

Source:
[execute.py:123](/Users/gporcari/Sviluppo/Genropy/genropy/gnrpy/gnr/sql/gnrsql/execute.py:123).

Current `Database.execute()` creates a fresh transaction and connection for that
operation, commits on success, and closes the connection. Inside an explicit
transaction, callers must use `tx.execute()`; calling the database's execute
would attempt a nested transaction. These are valid synchronous semantics, but
application table/query handles need a clear executor association.

Critical example: a future `record(for_update=True)` followed by an update is
not safe if the record terminal commits immediately and releases the lock.
The facade must execute both operations in the same explicit transaction.
Choosing a transaction-bound table handle or another explicit execution context
is a prerequisite to promising lock-based record editing.

Legacy `serverfetch` returns a cursor plus a chunk generator; `iterfetch` yields
chunks rather than individual rows. `_cursorGenerator` closes on exhaustion,
not through a general early-exit finally block. Its loop can yield an empty
terminal chunk. These lifetime details should not be copied as desirable
behavior.

Source:
[query.py:504](/Users/gporcari/Sviluppo/Genropy/genropy/gnrpy/gnr/sql/gnrsqldata/query.py:504).
The ordinary `_dofetch` branch used by `selection()` also lacks the explicit
cursor close present in `fetch()`. Cursor cleanup is therefore not uniform
across legacy terminals. Current results are eager and connections close with
their transaction.
A future streaming terminal needs an explicit connection/transaction lifetime
and guaranteed cleanup on interruption. The chosen runtime remains synchronous;
no implicit event loop, worker thread, or async facade is part of this proposal.

## 8. Critical mismatch register

| ID | Mismatch | Why a superficial wrapper is insufficient | Required decision/acceptance evidence |
|---|---|---|---|
| LIFE-01 | Metadata table vs application table | No owner/executor/method contract in Table dataclass | A bound table handle has stable logical identity and a defined database/transaction owner |
| LIFE-02 | Eager native compilation vs lazy query intent | Construction scope and fetch scope can differ | Construct in A, execute in B; declare whether B is used or mismatch rejected |
| LIFE-03 | Legacy split-time env evaluation | Cached structure and late values can disagree | Inspection does not silently change terminal semantics; compiled artifacts retain native snapshot guards |
| LIFE-04 | Repeat fetch vs cached record | Caching all terminals changes freshness; caching none changes record/resolver behavior | Two fetches rerun; loaded record snapshot and refresh semantics explicitly defined |
| LIFE-05 | Implicit pkey and default order | UI keys and deterministic ordering may disappear | Partial projection, renamed physical pkey, compound pkey, explicit ordering override |
| LIFE-06 | Named-list vs dict rows | Positional row consumers break | Document native row protocol and any explicit legacy adapter |
| LIFE-07 | Fetch transformations | Ciphertext/serialized Bags/placeholders are not logical values | Unsupported transformations rejected or implemented in a typed result pipeline |
| LIFE-08 | Count meaning | SQL COUNT, group count, page size differ | Cases for grouping/distinct/page/NULL/fan-out; no hidden row reaggregation |
| LIFE-09 | Record visibility/cardinality | Ordinary SELECT defaults hide records; LIMIT 1 hides duplicates | Missing/single/multiple/deleted/draft/partition cases with explicit native rules |
| LIFE-10 | Selection metadata/output | QueryResult is not a stateful collection or grid/Bag output | Stable column/UI identity and defined materialized outputs; no aggregateRows |
| LIFE-11 | Lock/transaction lifetime | Per-call commit releases FOR UPDATE protection | Fetch-for-update and subsequent write share one explicit transaction |
| LIFE-12 | Lazy relation lifetime | Resolvers may execute after parent query/session ends | Define environment, executor availability, and closed-context errors |
| LIFE-13 | Mutation after compilation | Stale caches and shared parameter mutation | Immutable intent or explicit copy/invalidation; caller params not mutated |
| LIFE-14 | Streaming/resource ownership | Existing eager runtime cannot return a live cursor safely | Deferred capability with close/early-exit/error contract, synchronous throughout |

## 9. Preserve, change, and defer explicitly

### Preserve as product capabilities, with declared profiles

- The database → table → query → terminal shape the application expects.
- Model-based column/relation resolution and bound values.
- Separate row-list, selection, and exactly-one-record concepts.
- Column identity and UI information connected to query results.
- Explicit missing/duplicate-record behavior rather than accidental list errors.
- Query construction without I/O; materialization at a terminal operation.
- Parameter-name compatibility through an adapter where needed, without
  treating every unknown native keyword as a silently accepted binding.

### Change intentionally

- Remove aggregateRows and equivalent hidden Python reaggregation, including
  the record collapse path; preserve legitimate duplicates.
- Keep synchronous execution and explicit transaction ownership.
- Preserve native identifier quoting, strict scope handling, environment
  snapshots, and incompatible-reuse errors at the compiled-query boundary.
- Avoid stale mutable query caches and caller parameter mutation.
- Reject unsupported output/record/locking features rather than returning a
  superficially similar but semantically different object.
- Keep SQL LIMIT 0 as zero rows; do not import legacy truthiness anomalies.

### Defer without pretending equivalence

- Store fan-out, store/tenant routing, and merged store results.
- Full legacy Bag resolvers, output formatting, freeze/unfreeze selection
  persistence, and every application mixin.
- Streaming until resource ownership is specified and implemented.
- Record locking until the transaction-bound facade and dialect capability exist.

The lower-level compiler, plans, dialect, driver, and synchronous transaction
runtime can remain the execution foundation. The missing work is a coherent
application data API above them: intent lifecycle, materialization contracts,
record semantics, and executor/context ownership. Its first useful slice should
be specified against the mismatch register, not judged complete merely because
`query(...).fetch()` can be made to return a list.
