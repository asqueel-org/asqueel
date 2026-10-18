
## Phase 1

- Partition filter: legacy truthiness (`env.get(...)`), so `current_<path>=0` adds no filter; realigned tests moved partition values from 0/1 to 10/11. `current_<path>` and `allowed_<path>` both enter the plan's environment keys, so a cached plan is refused when either changes.
- `RowPolicies` keeps `draft_field` and `logical_deletion_field`; `PartitionScope` and the multi-partition `x_partitions` semantics (include_null, raise on missing context, relational partition paths) are gone with A1.4. The relational-partition read test and its strict xfail were deleted (31 strict xfails remain).
- `schema()` loses `x_sql_schema`; its physical name is `sqlname` (as `DbPackageObj.sqlschema` already read it). `package()` keeps `sqlschema`.
- `sql_<dialect>_<name>` suffixes other than `default|generatedExpression|extra` raise "Element 'column' does not accept"; `encrypted` and the `indexed`/`unique` strings are handled in the builder call, before grammar validation.
- Unknown names: `DbModel.table` returns None for a missing package; user-facing callers (`SqlDatabase.table`, subquery/virtualRelation targets, compiler context, relation targets, alias paths, policy fields) raise their own `Unknown package/schema`/`Unknown column` errors.
- Blocker: SQLite generated columns are invisible to asqueel-migration 0.2.3 (`PRAGMA table_info`); see the plan-defect claim on the phase.
