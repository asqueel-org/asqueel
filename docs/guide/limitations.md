# Current status

The rest of this manual describes the delivery model, including designed
capabilities. This chapter is the single implementation-status reference for
the checkout: it separates working behavior, planned contracts and open decisions.
Do not infer that every documented contract executes in the installed revision.

Asqueel currently provides a native PostgreSQL and SQLite execution path for new
applications. It is not a drop-in replacement for the complete Genropy legacy
runtime. This page describes behavior you can rely on when choosing APIs.

| Area | Available now | Boundary to account for |
|---|---|---|
| Data backend | PostgreSQL through psycopg 3; SQLite through sqlite3. | SQLite uses attached schema files and BEGIN IMMEDIATE; PostgreSQL-specific SQL is not translated. |
| Runtime | Synchronous execution, implicit transaction start and explicit completion. | No async API, worker pool, general-purpose connection pool or automatic retries; named connections are retained until closed. |
| Ownership | Independent named connections per thread, one active transaction per name. | Share the DB graph; each worker closes its own connections. No nested transactions or savepoints; no async task isolation. |
| Results | Materialized dictionary rows, row count and column metadata. | No streaming or lazy cursor; large results occupy application memory. |
| Querying | SELECT, parameters, projections, aliases, filters, ordering, limit/offset and supported to-one relation paths. | No DISTINCT ON, tuple-of-columns IN, `*` grouping or Python-side deduplication; not a universal SQL parser. |
| Formulas | SQL expressions, scalar select/exists dictionaries and named correlated subqueries. | Python providers, method callbacks, formula variants, subquery collections and advanced macros are outside the native profile. Partition filtering remains explicit inside subqueries. |
| Alias columns | Declared aliases inherit target metadata, allow local overrides, and resolve through supported to-one paths, including alias/formula targets. | Read-only; no to-many/virtualRelation. Default RETURNING excludes aliases; explicit relational aliases cannot be returned by DML. |
| Writes | INSERT/UPDATE/DELETE, RETURNING, rollback, explicit soft-delete and restore; before/after table hooks, database write hooks, and raw commands that retain change tracking. | Ordinary updates/deletes require exactly one row and a declared primary key. Raw predicates may match multiple rows; raw insertion also accepts a list. No record-cluster writes, automatic retry or implicit save of related records. |
| Environment | Nested scopes, detached snapshots and guarded contextual queries. | Not a permissions system; direct SQL does not acquire model policy predicates automatically. |
| Row policies | Declared partition scopes, draft and logical-deletion handling. | Tenant/store routing and legacy subtable behavior are not provided. Read policies are not complete write authorization. |
| Model/UI | Native declarations, resolved naming and linked column metadata. | No UI renderer/editor; UI visibility and read-only metadata do not enforce database permissions. |
| Import | PostgreSQL inspection with an explicit schema list and warnings. | No legacy application/package importer. Unsupported or application-only semantics must be reviewed separately. |
| Native objects | Ordinary supported table structures can be projected for migration tooling. | View/function/trigger lifecycle and physical partition management are not supported as a complete native-object workflow. |

For porting guidance, see [legacy compatibility](legacy.md) and
[legacy adaptations](../adattamenti-legacy.md). SQLite boundaries are in the [SQLite guide](sqlite.md). For errors and
unexpected results, see [troubleshooting](troubleshooting.md).

## Query and result boundaries

The compiler resolves supported Asqueel field references and preserves authored
SQL expressions. SQL fragments are trusted application code; bind external
values through parameters. Successful rendering does not validate every SQL
expression against the server.

Relation paths in the native profile require a uniquely identified target.
To-many navigation and automatic collection shaping are not implemented.
`aggregateRows` has been removed: there is no fallback that deduplicates or
reassembles exploded joins in Python. Choose an explicit SQL result shape.

Computed projection expressions need explicit aliases. Returned names must be
unique. Result metadata supplied to a direct `CompiledQuery` must match the
actual returned names, order and number of columns.

Pagination uses limit/offset; there is no keyset-pagination helper. Streaming,
COPY/executemany optimizations and query compilation/result caching are not provided by the
runtime. Application records cache their exactly-one-row snapshot until explicit
`refresh()`; ordinary query fetches always execute again. Record reads reject
custom projections, limit and offset so they cannot mask multiple matches.

## Policy boundaries

Partition scopes are logical predicates, not PostgreSQL storage partitions.
The current scope and allowed values are both enforced when present; an empty
allowed collection matches no rows. Missing required scope context is an error.
`None`, a false-valued scalar and an absent key are distinct values.

Draft and logical-deletion exclusions apply to SELECT according to its options.
`delete()` remains a physical delete. Use `soft_delete()` to write an explicit
non-null tombstone and `restore()` to clear it. Do not infer write permissions
from an earlier filtered SELECT.

Logical-deletion `mark` mode adds `_isdeleted` using the actual tombstone field;
it is not automatically a boolean. It requires physical-column projections and
rejects opaque expressions/formulas. Relational policy fields have additional
restrictions in writes; use physical policy fields for supported native DML.

A query's environment guard prevents accidental reuse under changed relevant
context. It is not a substitute for database roles, constraints or application
authorization. Explicit bypass options must be used deliberately by the
application; the compiler does not decide who may use them.

## Transaction and value boundaries

`AsqueelDb`, `SqlDatabase`, `Database` and `PostgresDatabase` share one execution
implementation. Table operations and `db.execute()` use the current thread's
selected named connection until explicit commit or rollback. Connections open
lazily and are retained for reuse. `execute()` never commits automatically;
there is no public transaction object or connection context manager.
Closing the DB rolls back pending work and releases the current thread's
connections. Each worker must close its own connections.

An SQL execution error automatically rolls back the selected named connection.
A Python error in the write lifecycle marks the affected connection rollback-only:
commit is blocked until explicit rollback. An arbitrary Python exception outside
that lifecycle requires the caller to roll back its pending work. An uncertain commit
outcome does not mean the write failed; retries require application-specific
handling. See [transactions](transactions.md).

Compiled parameter maps are copied at the outer level. Do not mutate list,
dictionary, buffer or custom mutable parameter values while using a compiled
query. Environment snapshots and environment bindings copy their values deeply;
custom environment values must support `deepcopy` correctly.

## Import and migration boundaries

A database catalog contains physical structure, not the full application model.
Review `ImportResult.warnings` and maintain UI/application enrichment explicitly.
The importer reports unsupported objects rather than promising that the model
can reproduce every object or behavioral rule in an existing database.

Producing a migration structure is different from applying a migration.
Neither application rendering, `PostgresDatabase`, nor compiler construction creates tables. Use the
separate migration integration for supported structures and review the generated
plan before applying it. Do not treat unrepresented native objects as objects
the application may drop.

The supported modular declaration path uses one SQL grammar and explicit recipe
contributions. General dynamic grammar mounting is not a supported round-trip
contract for emitted Python. A recipe emitter preserves supported model content,
not the original source-file decomposition.

## How unsupported operations fail

Native features outside the declared profile generally raise
`UnsupportedFeatureError`; malformed arguments and mismatched adapters can raise
`ValueError` or `TypeError`. Driver errors propagate unchanged. Environment reuse
mismatches raise `EnvironmentMismatchError`, while closed or incorrectly used
runtime objects raise `DatabaseClosedError` or `TransactionStateError`.

A custom adapter must declare and test its own supported behavior. See
[adapters](adapters.md) for the boundaries; adding a capability name does not
implement the capability or certify another database backend.

## Designed capabilities and open decisions

The delivery guides include model path introspection, virtual relations,
provider/Python/Bag columns, subtables, Selection/Bag results, application
integration, legacy-package import and native SQL objects. These belong to the product plan; the availability
matrix above describes which parts execute in this checkout.

The Genropy guide records agreed differences: removal of aggregateRows and explicit
partition semantics. Output naming, default ordering, wildcard selection and
other unapproved divergences in the current implementation are compatibility
work, not accepted product differences. The implicit `pkey` column of GenroPy
queries is left to a future GenroPy adapter, not to the core. Native query results still
use dictionary rows; path lookup on live columns is not complete. Collection
bindings, count, grouping and distinct are implemented; Selection is not.

Standalone execution and application tables share the same execution service.
Names and signatures for new application providers, virtual-relation variants,
native-object declarations and some result APIs still need specification. The
manual explains their roles without inventing finalized constructors for them.

Commit callbacks (`deferToCommit`, `deferAfterCommit`, `deferredRaise`) are
available per named connection. Handled errors allow dispatch to continue;
escaping errors stop dispatch and reach the application. After a Python
postcommit failure, unreached callbacks remain pending until rollback/connection
cleanup or a deliberate later transaction in the same context. There is no
automatic retry, and failed new work still requires rollback.

The synchronous F1 context/connection/recovery profile is verified; this does
not certify a complete legacy application port. Workdate/locale identifiers
are deliberately not validated. Application request cleanup is required before
reusing a worker for another request. Normal legacy record-cluster
saves already abort on propagated errors; this is not a difference in normal
save behavior.
Six hook positions and pre/post-commit Python failures have been compared on
PostgreSQL; the difference is described in [legacy compatibility](legacy.md). Deferred callbacks and trigger-stack behavior now have targeted verification;
application event integration remains separate.

## Verified commit lifecycle

Table hooks can register pre/post-commit callbacks and deferred errors. Named
queues, callback ordering/deduplication/recursion, commit context and trigger
parent/level are covered by regression tests. Original legacy queue methods,
using the legacy Bag, have been compared with native dispatch. PostgreSQL tests
verify visibility, rollback and that failed pre-commit work cannot announce a
successful commit. This does not establish complete GnrSqlAppDb event integration
or equivalence for every Python hook failure.

## Detailed checkout differences

### Queries, formulas and result names

`*` currently expands all resolved columns, including aliases and formulas,
rather than the target physical/static-column convention. Automatic relation
aliases omit the target leading underscore (`customer_name` instead of
`_customer_name`). Use explicit projections and aliases for stable result contracts.
Relation path segments currently require ASCII identifiers.

Collection bindings accept `IN :ids`, `NOT IN :ids` and PostgreSQL
`= ANY(:ids)`. An empty collection matches no rows for `IN`; NULL members
retain SQL three-valued semantics. Use an explicit array cast when SQL cannot
infer the parameter type. Mixing one parameter between collection and scalar
position is an error. `count()`, `distinct`, `group_by` and `having` are
available with the rules in [queries](queries.md); `count()` rejects a query
carrying `limit` or `offset`. There is no implicit primary-key projection or
model default ordering, and no NOWAIT/SKIP LOCKED query option.

Scalar subquery definitions accept `table`, `columns`, `where`, `params`/`sqlparams`,
`order_by`, `limit`, `offset`, policy options and `cast`. Cast syntax does not
support quoted custom type names. Compatibility options are restricted to
`subtable='*'`, `addPkeyColumn=False` and `ignoreTableOrderBy=True`.
Method-based subqueries, formula callbacks/variants, Python columns and separate
subquery collection columns are not implemented. Structured subquery formulas
are read-only. DML cannot traverse relations or return expressions requiring joins.

### Hooks, environment and application integration

Only the documented table before/after write hooks execute. Field/package
triggers, protection callbacks, counters, related-record cascades and legacy
application mixins still need integration. After-statement hooks are not
post-commit callbacks. Deferred callbacks are available; application event queues
still need integration. Locale defaults do not yet use full Babel catalog validation.
Selecting an unsupported store fails before SQL execution.

### Configuration and generated references

Grammar acceptance alone does not establish execution support. The Builders
baseline has limitations with indirectly inherited redecorated grammar overrides;
use explicit grammar composition and verify both configuration and resolved model.
The object renderer does not accept explicit delivery targets or `target=False`.
Generated API and grammar reference pages reflect the checked-out code; conceptual
guides also explain the delivery design. Use documentation matching your installed
version when checking exact signatures.

### Import and migration coverage

Views, materialized views, foreign tables, inherited/partitioned tables and
partitions are not imported as queryable tables in this checkout. Sequences,
triggers, routines, row-level security and external FK targets are reported as
unsupported or unmanaged. Roles, grants and extended dependencies are not modeled.
The catalog importer does not import legacy application packages.

Migration projection rejects model warnings, identity/generated columns,
sequence ownership/dependent defaults, custom collations, known lossy type
conversions, unsupported/unvalidated constraints and external foreign keys.
Expression indexes, INCLUDE columns, custom opclasses, advanced index options
and column-subset SET NULL/SET DEFAULT actions are also rejected where their
semantics cannot be represented. CHECK expressions and partial-index predicates
with remapped columns require safe SQL rewriting and otherwise fail projection.
These are coverage gaps, not a recommendation to remove metadata or database objects.
