# For Genropy users

Genro SQL carries forward the database-centered application model of Genropy.
The familiar entry point remains:

```python
rows = db.table('sales.invoice').query(
    columns='$id, @customer_id.name AS customer_name, $total',
    where='$total >= :minimum',
    minimum=100,
).fetch()
```

Use this chapter to understand the relationship with legacy Genro SQL and the
intentional differences. It is organized around application behavior rather
than the internal modules of either implementation.

## Contracts to carry forward

| Area | Contract |
|---|---|
| Database objects | A live db owns tables, columns, relations and execution context. |
| Relation paths | FK-based paths such as `@customer_id.state` and multi-hop paths such as `@customer_id.@state_id.name`. |
| Computed columns | Alias and formula declarations attach reusable values and metadata to the model. |
| Query language | `$field`, `@path`, bound parameters and `#NAME` Genro constructs. |
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

`aggregateRows` is removed, including from the compatibility adapter. Express
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

The compatibility adapter translates legacy declarations and application
conventions. It must preserve their observable contract or expose an explicitly
agreed difference. It is separate from SQL dialect adapters.

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
