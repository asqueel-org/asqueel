# 09 — Reassessing the product against the legacy object architecture

Internal architecture review, 29 September 2026. **The implemented package is a
useful SQL model/compiler/execution core, but it does not yet implement the
Asqueel application object model requested by the user.** This is a product
architecture gap, not a documentation or method-naming problem.

This review does not change the Python implementation or claim that the API
shown below exists. Previously written public-documentation edits remain
uncommitted and describe the current lower-level API; they are not evidence
that the application-facing architecture is complete.

## Scope and sources

The request is to understand the legacy path from configuration to live database
objects, then reassess the implementation against that evidence:

```python
# Required application usage; NOT an implemented API in this checkout.
rows = db.table('cont.cliente').query(
    columns='$id, $ragione_sociale',
    where='$attivo = :attivo',
    attivo=True,
).fetch()
```

The example preserves the legacy keyword-parameter style. The exact native
parameter spelling and compatibility alias rules must be covered by acceptance
cases, not silently changed by wrapping the current `params` argument.

- Legacy inspected: `genropy/genropy`, commit
  `fa35e5adfa6ad1b269f3a22a9b12c4c1ee6513ea`, local `gnrpy/gnr/sql` and supporting
  `gnrpy/gnr/core` sources. Three unrelated modified invoice fixtures were not
  used. Earlier dossiers used `e12f2ce...`; their line numbers and observations
  are historical, not a substitute for this inspection.
- Current SQL implementation: `bf66bcacfeededc7f0ce82cd5c48f6437aa174df`.
- Modern configuration/rendering contracts: installed `genro-builders==0.27.0`.
- Evidence combines source tracing and targeted executable probes. It is not
  a full legacy application run or a declaration of legacy compatibility.

Detailed source anchors and lifecycle traces:

| Document | What was inspected |
|---|---|
| [09A — Legacy object model](09a-legacy-object-model.md) | Source composition, model build, object identity, package/table/column objects and mixins. |
| [09B — Query, record and selection](09b-legacy-query-record-lifecycle.md) | Lazy query compilation, fetch, count, record cardinality, result shape and Bag resolvers. |
| [09C — Sessions and writes](09c-legacy-session-write-lifecycle.md) | Connection ownership, commit boundaries, CRUD dispatch, hook ordering and failure cleanup. |
| [09D — Modern configuration and rendering](09d-builders-configuration-and-object-rendering.md) | ConfigHandler layering, mounted grammars, object renderers and gaps in current SQL consumers. |

## 1. What the legacy actually builds

The legacy database is the application root. It owns the model, adapter,
connection/environment infrastructure, query access and writes. Model source
composition and object construction are separate steps:

```text
GnrSqlDb
  owns DbModel
    src: declarative Bag tree + package/table contributions
      config_db / config_db_<package> / config_db_custom and build callbacks
    build: source → DbModelObj.makeRoot(...) → linked runtime model tree
      package object
        DbTableObj (table metadata and model relations)
          dbtable: SqlTable (application behavior and mixins)
          column objects and relation metadata
  table('cont.cliente') → the model table's existing SqlTable
```

Key source locations: legacy `gnrsql/db.py:65–84`,
`gnrsqlmodel/model.py:107–179`, `gnrsqlmodel/table.py:105–107`,
`gnrsql/query.py:232–251`. See 09A for build order and callback details.

The distinction between `DbTableObj` and `SqlTable` matters. Returning a table
metadata dataclass is not equivalent to returning an operational table bound
to a DB. Conversely, retaining immutable descriptors inside the new implementation
is useful; they need not become connection-bearing objects themselves.

The legacy mechanism uses its own Bag structural-object factory and mixins.
The modern target should reuse the *responsibilities and lifecycle*, expressed
through current configuration grammars and object rendering. It should not
pretend the legacy already used modern ConfigHandler.

## 2. Where the current implementation diverges

| Area | Current implementation | Missing or incompatible product behavior |
|---|---|---|
| DB configuration | Connection options are Python constructor arguments; `db(name)` grammar describes model structure. | One authoritative, grammar-backed DB configuration with owned views for its constituent objects. |
| Build result | `resolve_model()` creates descriptors; the SQL renderer is a direct-DDL placeholder. | A build/render operation returning a usable DB with a complete registered object graph. |
| DB ownership | Database owns driver, connection settings and environment; compiler independently owns model/environment. | DB coordinates configuration, model, table registry, compiler, adapters, session and environment. |
| Table access | `ResolvedModel.table()` returns a descriptor; Database has no `table()`. | Stable operational table handles, column/relation access, table methods and behavior extensions. |
| Query lifecycle | `compiler.select()` immediately returns a compiled snapshot. | A table-bound query intent with lazy terminal operations and explicit reuse semantics. |
| Execution scope | Every `db.execute()` opens, commits and closes a connection. | Related reads, locks and writes participate in a DB/session-owned unit of work. |
| Writes | Compiler emits parameterized DML, runtime executes it. | Record preparation, table behavior, hook ordering and transactional side effects. |
| Records | Only materialized row dictionaries and metadata. | Record identity/cardinality, loaded-state semantics, output forms and relation resolution. |
| Selection | QueryResult carries rows, rowcount and columns. | A distinct materialized collection contract when requested, with stable metadata and output behavior. |
| Grammar composition | One grammar plus helper functions; limited mounted-grammar experiment. | Consume each configuration node through its actual grammar and render the corresponding objects. |

These are confirmed by code, not inferred from omitted documentation. Offline
probes found no `Database.table`, `Database.model`, `Database.config` or
`Database.commit`; the resolved table has no `query`, and CompiledQuery has no
`fetch`. `SqlBuilder.render()` raises NotImplementedError. Seven existing
composition tests pass, including tests that deliberately expect mount export
and attribute-validation limitations (09D).

## 3. Semantic differences that a facade alone cannot repair

### Sessions and atomic writes

Legacy ordinary table writes do not each commit. They reuse the DB's selected
connection until an explicit commit/rollback or a higher-level boundary acts.
The current runtime's per-call commit can split one application action into
separate committed actions. A `table.insert()` wrapper around that default
would still behave differently, particularly when a hook writes another table.
A row lock also needs the subsequent update on the same transaction.

**Recommendation:** make the application DB own a lazy synchronous session/unit
of work, with explicit commit/rollback and an explicit transaction context.
High-level table operations join that unit rather than independently committing.
Autocommit-per-operation, if retained, must be an explicit mode. Rollback-only,
cleanup and uncertain-commit handling from the current runtime remain valuable.
The exact default boundary is a contract to settle before implementation, not
an assertion that legacy needs to be copied without changes. See 09C.

### Query intent and execution-time context

Legacy query construction is lazy. A query caches compilation but fetches data
again for each fetch. It resolves parts of context during compilation and
`:env_*` values at execution, which can produce mixed-time behavior. Records
instead cache both compilation and the loaded record; selections materialize
rows and carry collection state. See 09B.

**Recommendation:** distinguish a high-level reusable query intent from an
explicit compiled artifact. A terminal operation takes one coherent execution
context and compiles against it; keep the current environment-mismatch guard
for a compiled artifact deliberately reused later. Until a proper dependency
cache exists, fresh compilation is safer than carrying the legacy split-time
cache behavior into the new API. Inspecting SQL should not silently freeze an
otherwise reusable query's future context.

### Record and result semantics

Legacy fetch rows support named and positional access, and often include an
implicit primary-key projection and table default order. Record loading checks
missing/multiple matches and has visibility rules distinct from ordinary query
filters. Bag fields and lazy relation resolvers are observable behaviors.
Current dictionary rows and ResultColumn metadata are useful raw material, but
are not equivalent to those contracts. See 09B.

**Recommendation:** keep query, record and materialized selection as separate
objects with explicit result protocols. Decide row compatibility, default pkey
projection, missing/duplicate record errors and read-policy defaults before
claiming equivalent syntax. A record must not hide duplicates with LIMIT 1.
A deferred relation load needs an explicit DB/session/context owner and a defined
failure when that owner is closed. None of this requires async execution.

### Table behavior and hooks

Legacy insert/update/delete are behavior pipelines, not just SQL verbs. They
prepare/check values, run ordered hooks, handle related writes and coordinate
transactional notifications/deferred callbacks. Some legacy exceptional paths
also have cleanup defects; they are evidence to avoid, not compatibility goals.

**Recommendation:** preserve an explicit table-behavior extension mechanism and
a verified hook order. Reuse DML compilation as the final persistence primitive.
Keep low-level/raw paths explicit so ordinary table writes do not accidentally
bypass preparation or hooks. Python hooks and future native database triggers
must not be conflated or automatically duplicated. See 09C.

## 4. Proposed construction and ownership contract

This is a design recommendation derived from the findings, not implemented code:

```text
configuration recipes / applicable grammar classes / parent layers
    ↓ resolve owned configuration, defaults and contributions
validate complete declarations and cross-table references
    ↓ object rendering/build
application DB
    ├── configuration view (connection/adapter/model configuration)
    ├── resolved model descriptors and stable table/column identities
    ├── operational table/column/relation registry
    ├── synchronous session / transaction / environment
    └── compiler + data dialect + driver
            ↓ table query terminal
       materialized rows / record / explicit selection
```

- One configuration source of truth; DB/table/column configuration accessors are
  scoped views, not unrelated copies with independent defaults.
- Configuration is trusted application input. The renderer constructs runtime
  objects on the owner thread; it does not eagerly open a connection or execute
  schema migrations.
- Allocate/register objects, then link cross-references, then expose the complete
  DB. Forward and cyclic relations must not depend on declaration order.
- `db.table(name)` returns the registered table handle for that DB. Two separately
  rendered DBs must not share mutable tables, Bag sources, session state or caches.
- A table owns access to its resolved metadata and DB services. Custom behavior
  attaches at this layer with a declared grammar/configuration contract.
- A query is tied to a table and its DB, but construction does not execute SQL.
  Terminals use the active session and a coherent environment snapshot.
- Physical migration projection remains independent. It neither creates the
  live object graph nor owns application transactions.

Builders 0.27 already provides parent layering and object renderer extension
points; the executed probes show no need to invent another generic configuration
framework. SQL-specific grammar, factory, validation, export and lifecycle work
is still required. See 09D, including None semantics and parent-source mutation.

## 5. What to retain, rework and keep excluded

**Retain as internal infrastructure:** logical/physical naming, column identity
and UI overlays; model diagnostics; common compiler/plan boundary; parameter
handling; dialect/driver separation; PostgreSQL introspection and explicit
migration projection; explicit partition/draft/deletion metadata; synchronous
execution and failure/cleanup checks.

**Rework as product integration:** DB configuration and renderer; operational
object registry; table-bound query/record/selection access; session ownership
and commit boundaries; CRUD behavior; mounted-grammar consumer/export support;
model/configuration lifecycle and cache invalidation.

**Keep user-decided changes:** no aggregateRows or Python reconstruction of
exploded joins; strict partition absence/falsy/empty-allowed behavior; synchronous
core first; store and tenant can follow. Keep physical partitions, logical scopes
and subtables distinct. Nothing in this audit silently re-enables permissive
legacy fallback or makes async a prerequisite.

Deferred or bounded support is acceptable only when declared. It must not be
used to call the basic DB/table/query object chain a later optional legacy bridge:
that chain is now a requirement for the new application's first usable product.

## 6. Correction sequence and acceptance gates

| Increment | Required outcome | Observable gate |
|---|---|---|
| A. Configuration and live graph | DB configuration grammar, effective per-node grammar, owned config views and object renderer. | Render without DB I/O; stable `db.table()` identity; two DBs isolated; parent overrides and mounted defaults work; invalid references fail before exposure. |
| B. Query and session vertical | Bound table/query intent, coherent execution environment and DB-owned transaction path. | Exact `db.table('cont.cliente').query(...).fetch()` on PostgreSQL; no I/O at query construction; repeated fetch reruns; current scope applied coherently; closed-owner error. |
| C. Record and write lifecycle | Explicit record semantics and table CRUD with behavior/preparation hooks. | Missing/single/multiple record cases; hook order; related write rolls back with root write; lock and update share transaction; no implicit commit inside table methods. |
| D. Compatibility and user-facing surface | Supported row/selection outputs, naming aliases and selected legacy signatures. | Representative application snippets run unchanged where promised; unsupported options fail; metadata/UI and Bag outputs retain identity; aggregateRows is rejected. |

Existing component tests remain useful. Add these **application-flow contracts**
before expanding features, and keep count/pagination, selection transformations,
Bag resolver lifetime and hook side effects individually observable. Do not label
stages complete solely because isolated compiler or executor tests pass.

The first working vertical should include configuration → DB → table → query →
fetch **and** two related writes with rollback. Finishing another low-level
compiler feature before that vertical would repeat the current mismatch.

## 7. Reassessment of earlier delivery claims

The 337-test result remains evidence for the implemented component contracts.
It does not demonstrate the application API above: those tests mostly construct
a compiler and executor separately. The prior V1 delivery reports should be read
as delivery of a low-level native core, not completion of the requested Asqueel
product. Their passing results are not withdrawn; their scope is corrected.

The earlier choice to defer the operational object layer and accept only recipe
helper composition does not satisfy the clarified requirement. The internal
[decisions](05-decisions.md) and [version proposal](07-release-proposal.md) are
updated to make this distinction explicit. Public guides must be revised again
when the object API actually exists, rather than publish fictional examples now.

## 8. First implementation following this review

The working tree now adds `SqlDatabaseConfig`, an object renderer and
`build_database()`. They own their configuration recipe, apply the effective
per-node grammar defaults, resolve a complete model, and create one database
with stable table, column and relation handles before any connection is opened.
The original compiler and low-level executor remain implementation components.

`SqlTable.query()` returns detached query intent. Each terminal compiles against
the current environment; `fetch()` executes again, whereas record output caches
an exactly-one-row snapshot until `refresh()`. Application operations use one
lazy synchronous session, with explicit commit/rollback or a transaction scope.
Closing the database rolls back pending work. A table failure poisons that unit
of work, including Python insert-hook failures and related writes.

This covers the first configuration/query/session vertical and the initial
record/insert lifecycle. It **does not close all of stages C and D**: locking,
old-record preparation, update/delete hooks, Bag/selection outputs, implicit
primary-key projection and table ordering, and the full legacy mixin pipeline
still need explicit contracts and implementation. The native result profile is
dictionary rows and `QueryResult` for writes. AggregateRows remains unsupported.

Configuration is read as a construction snapshot: modifying the exposed source
after rendering does not rebuild the resolved model or live registry. Build a
new database for a new configuration. A transaction context requires an idle
session; it does not silently adopt earlier reads or writes.

Verification of this increment: **391 tests passed**, overall coverage **95%**,
including eight new PostgreSQL application-flow tests. An independent connection
verified visibility only after commit and rollback of both root and hook writes.
The policy test traversed configuration, table, compiler and session for missing
scope, zero, empty allowed sets, draft and logical deletion. Ruff, mypy and the
strict English Sphinx build passed; the published quickstart ran against the
disposable PostgreSQL server. A locally built wheel also rendered and compiled
on Python 3.11 without the optional PostgreSQL or migration dependencies.

## 9. Update/delete lifecycle increment

Following the first vertical, native update and delete hooks now acquire a
PostgreSQL base-row lock before receiving the old record. Hooked operations
require exactly one row and a primary key; the lock query reads at most two rows
to detect ambiguity. They target the saved old key, including composite and zero
keys. Update hooks receive detached old snapshots and a complete physical new
record; soft deletion and restoration use the same update path. Tables without
overridden hooks retain their existing set-based operations.

This implements the core old-record/lock/hook contract of stage C. It does not
implement legacy protection callbacks, field triggers, external package mixins,
counters or cascades. The public `for_update=True` option is supported by the
compiler and dialect as a capability, not appended by the application layer.
Locks remain owned by the shared session, and related hook writes roll back
together on failure. The integration suite checks lock contention using a second
PostgreSQL connection with a bounded lock timeout.
