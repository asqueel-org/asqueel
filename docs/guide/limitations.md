# Current capabilities and limitations

Genro SQL currently provides a native, synchronous PostgreSQL path for new
applications. It is not a drop-in replacement for the complete Genropy legacy
runtime. This page describes behavior you can rely on when choosing APIs.

| Area | Available now | Boundary to account for |
|---|---|---|
| Data backend | PostgreSQL through psycopg 3. | No other data backend is shipped. Dialect and driver protocols are extension points. |
| Runtime | Synchronous statement execution and explicit transactions. | No async API, worker pool, persistent connection pool or automatic retries. |
| Ownership | One active transaction per database instance. | Construct and use an instance on the same thread; no nested transactions or savepoints. |
| Results | Materialized dictionary rows, row count and column metadata. | No streaming or lazy cursor; large results occupy application memory. |
| Querying | SELECT, parameters, projections, aliases, filters, ordering, limit/offset and supported to-one relation paths. | Not a complete legacy query language or a universal SQL parser. |
| Formulas | SQL expressions, scalar select/exists dictionaries and named correlated subqueries. | Python providers, method callbacks, formula variants, subquery collections and advanced macros are outside the native profile. Partition filtering remains explicit inside subqueries. |
| Alias columns | Declared aliases inherit target metadata, allow local overrides, and resolve through supported to-one paths, including alias/formula targets. | Read-only; no to-many/virtualRelation. Default RETURNING excludes aliases; explicit relational aliases cannot be returned by DML. |
| Writes | INSERT/UPDATE/DELETE, RETURNING, rollback, explicit soft-delete and restore; before/after insert, update and delete hooks on application tables. | Hooked updates/deletes require exactly one row and a declared primary key. No record-cluster writes, automatic retry or implicit save of related records. |
| Environment | Nested scopes, detached snapshots and guarded contextual queries. | Not a permissions system; direct SQL does not acquire model policy predicates automatically. |
| Row policies | Declared partition scopes, draft and logical-deletion handling. | Tenant/store routing and legacy subtable behavior are not provided. Read policies are not complete write authorization. |
| Model/UI | Native declarations, resolved naming and linked column metadata. | No UI renderer/editor; UI visibility and read-only metadata do not enforce database permissions. |
| Import | PostgreSQL inspection with an explicit schema list and warnings. | No legacy application/package importer. Unsupported or application-only semantics must be reviewed separately. |
| Native objects | Ordinary supported table structures can be projected for migration tooling. | View/function/trigger lifecycle and physical partition management are not supported as a complete native-object workflow. |

## Query and result boundaries

The compiler resolves supported Genro field references and preserves authored
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
bulk/COPY helpers and query compilation/result caching are not provided by the
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

The application `SqlDatabase` keeps a shared transaction across table operations
and `db.execute()` calls until commit or rollback. Its connection is opened
lazily and closed when that transaction ends. Closing the database rolls back
pending work. The separate low-level `Database`/`PostgresDatabase.execute()`
convenience instead opens and completes a transaction per call; use an explicit
transaction when combining dependent operations through those components.

A statement error makes that transaction rollback-only. An uncertain commit
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
