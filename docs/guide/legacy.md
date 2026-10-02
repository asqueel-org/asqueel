# For Genropy users

Asqueel carries forward the database-centered application model of Genropy.
The familiar entry point remains:

```python
rows = db.table('sales.invoice').query(
    columns='$id, @customer_id.name AS customer_name, $total',
    where='$total >= :minimum',
    minimum=100,
).fetch()
```

Use this chapter to understand the relationship with Genropy’s legacy database layer and the
intentional differences. It is organized around application behavior rather
than the internal modules of either implementation.

## Contracts to carry forward

| Area | Contract |
|---|---|
| Database objects | A live db owns tables, columns, relations and execution context. |
| Relation paths | FK-based paths such as `@customer_id.state` and multi-hop paths such as `@customer_id.@state_id.name`. |
| Computed columns | Alias and formula declarations attach reusable values and metadata to the model. |
| Query language | `$field`, `@path`, bound parameters and `#NAME` Asqueel constructs. |
| Transactions | Implicit transaction start; explicit commit/rollback and independent named connections. |
| Environment | Mutable currentEnv and scoped tempEnv, with business date and application context. |
| Commit lifecycle | Work before commit, work after commit and application events have distinct responsibilities. |
| Application boundary | A standalone DB plus an application-linked layer analogous to GnrSqlDb/GnrSqlAppDb. |

A relation path belongs to model introspection as well as query compilation.
A formula-derived relationship and an ordinary FK differ in declaration, but
both need a clear target and cardinality. Multiple connections to the same DB
remain distinct from multiple stores.

## Deliberate differences

### Explicit collection shapes replace aggregateRows

`aggregateRows` is not implemented in Asqueel. Express
related collections and aggregates as explicit results or correlated queries.
Do not rely on a Python pass to deduplicate multiplied join rows and rebuild
objects after fetching. When porting such a query, identify its intended parent
identity, collection cardinality, ordering and NULL/empty behavior first.

### Partition context has explicit semantics

The new partition contract treats `0` and `False` as valid values. An empty
allowed collection selects no rows. Missing required context raises an error
unless bypass is explicitly requested. When both current and allowed values
are present, both restrict access. The old possibility of silently omitting a
filter is not carried forward.

These are application row scopes. They do not define a PostgreSQL physical
partition or a logical subtable.

### Configuration is rendered into live objects

Package and application contributions pass through configuration grammars and
rendering. This gives the same model to data access, metadata consumers and
schema tooling. Model inspection from an existing database is complemented by
application metadata; a catalog cannot recover Python behavior or UI intentions.

A future compatibility adapter would translate legacy declarations and application
conventions. It is not implemented. Its intended contract must preserve observable
behavior or expose an agreed difference; this is separate from SQL dialect adapters.

## Python errors: normal saves and explicit recovery

Normal legacy record-cluster saves do not reach commit when a write or an
`onSaving`/`onSaved` hook raises. Request cleanup rolls back pending work.
An error queued with `deferredRaise()` also prevents commit, including retry.
The distinction below concerns code that deliberately catches an ordinary
Python exception and continues at the low-level database API.

If you catch a Python error from a write hook or pre-commit callback, the legacy
standalone core can still let you commit the writes already performed. Current
Asqueel requires rollback before reuse. After-commit errors cannot undo a commit
that has already succeeded; any new work started by the failed callback must
be rolled back in Asqueel. Residual callbacks are discarded during that recovery.

Legacy comparisons run on PostgreSQL; native recovery tests cover PostgreSQL and SQLite. It does not mean
that normal legacy saves persisted failed operations. The reviewed legacy callers have explicit adaptation obligations in the
[legacy adaptation map](../adattamenti-legacy.md). Do not port code that catches a hook error
and continues to commit without reviewing its intended effects. See
[transactions](transactions.md) for the current native behavior. Web request
cleanup and application-specific exception handlers are separate from this
standalone-core comparison.

## Move application integration to its own layer

Keep generic database operations in the standalone layer. Connect localization,
resources, permission services, events and dynamic model contributions through
the application-linked layer. Genropy-specific page, site and adm conventions
belong in the compatibility integration. New applications need the application
layer too; they do not need to adopt the entire legacy web framework.

This preserves the purpose of GnrSqlAppDb without duplicating the compiler or
transaction machinery in the bridge.

## Adapt one application behavior at a time

1. Preserve logical table names and verify schema/prefix/physical-name mapping.
2. Trace declarations and mixins into the effective model, including UI metadata.
3. Compare path resolution, result names and types, wildcard behavior and record
   cardinality on representative data.
4. Compare writes, hook ordering, named connections, rollback and deferred work.
5. Replace aggregateRows queries with explicit shapes and apply the partition
   contract above.

A shorter native implementation is not sufficient evidence of compatibility.
Use the same input and compare returned values, persisted effects and failure
behavior. New deliberate differences belong in this chapter when agreed;
implementation progress is tracked separately from the migration contract.
