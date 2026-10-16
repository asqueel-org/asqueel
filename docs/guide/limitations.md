# Current status

This page is the single implementation-status reference. It states what a new
project can do with this version of asqueel and what it refuses, with the open
issue for each limit. The rest of the manual describes the delivery model; when
another page and this one disagree, this page describes the installed code.

Asqueel is not a drop-in replacement for the complete GenroPy legacy runtime.
For porting guidance, see [legacy compatibility](legacy.md) and
[legacy adaptations](../adattamenti-legacy.md).

## What a new project can do

The light version reads, inserts, updates and deletes records, with formulas and
aggregations, on PostgreSQL and SQLite. The [tutorial](tutorial.md) runs every
step below on both databases.

| Area | Available | Boundary |
|---|---|---|
| Backends | PostgreSQL through psycopg 3; SQLite through sqlite3. | SQLite uses attached schema files and BEGIN IMMEDIATE. PostgreSQL-specific SQL is not translated. |
| Tables | `db.migrate()` creates and alters the declared tables; it needs `asqueel[migration]`. | Without the extra, create tables with your own DDL, as in the [quickstart](quickstart.md). |
| Reads | `query()` with projections, filters, ordering, limit/offset, `distinct`, `group_by`, `having`, `count()`; `record()` for exactly one row, `for_update=True` for a locked read. | No streaming cursor: rows are materialized Toolbox `NamedList` rows. |
| Relations | To-one paths such as `@customer_id.name`; inverse paths declared with `inverse` as LEFT JOIN; `@invoices.aggr(...)` for aggregates over related rows. | Virtual relations are not executed. |
| Formulas | SQL formula columns, table formula methods, `select`/`exists` dictionaries, named subqueries, `subQueryColumn`. | Formulas are read-only. JSON/XML `subQueryColumn` modes and `aggr(to_xml(...))` need PostgreSQL; `aggr(to_json(...))` runs on both. |
| Alias columns | `aliasColumn` through to-one paths, with inherited metadata and `originalColumn`. | Read-only: an alias key in a write mapping is skipped. |
| Writes | `insert`, `update`, `delete` with the legacy write cycle: table triggers, column triggers, `protect_*`, `onDelete`/`onUpdate` of the related records. `sql_insert`, `sql_update`, `sql_delete` write without triggers; `query(...).sql_update()` / `.sql_delete()` write the rows a query selects. | See the refusals below. |
| Keys | A key left empty is generated: `max(key)+1` for integer keys, a 22-character UUID for text keys, or `newPkeyValue()` overridden by the table. | `max(key)+1` is not safe under concurrent inserts; use a `serial` column or your own generator. |
| Transactions | Implicit start, explicit `db.commit()` / `db.rollback()`, named connections per thread, `deferToCommit`, `deferAfterCommit`, `deferredRaise`. | No async API, no savepoints, no automatic retry. |
| Row policies | Partition, draft and logical-deletion filters on reads. | They do not apply to writes (see below). |

## What the write cycle refuses

`insert`, `update` and `delete` raise `UnsupportedFeatureError` before any
trigger or SQL when the table declares something the cycle does not execute yet.
The check is `require_write_capabilities`; a table with any of these cannot be
written through the cycle.

| Declaration | Issue |
|---|---|
| option `sys_fields` | [#29](https://github.com/asqueel-org/asqueel/issues/29) |
| option `hierarchical` | [#30](https://github.com/asqueel-org/asqueel/issues/30) |
| option `auto_counter` | [#31](https://github.com/asqueel-org/asqueel/issues/31) |
| any other enabled table option | no issue yet |
| column `default`, `default_from`, `x_generation` | [#28](https://github.com/asqueel-org/asqueel/issues/28) (newrecord with defaults) |
| column `read_only`, `unmodifiable` | no issue yet |
| a column child other than its relation | no issue yet |
| a table expanded from a legacy source (`x_expanded_legacy`) | no issue yet |

Other operations a project may expect and that are missing or fail:

| Operation | Status | Issue |
|---|---|---|
| SELECT and `record()` on a table whose pkey is a `compositeColumn` | fails | [#26](https://github.com/asqueel-org/asqueel/issues/26) |
| `recordToUpdate`: hooked update/delete of one record read with a lock | missing | [#17](https://github.com/asqueel-org/asqueel/issues/17) |
| `batchUpdate`: hooked update of the records of a selection | missing | [#32](https://github.com/asqueel-org/asqueel/issues/32) |
| table partitions applied to insert, update and delete | not applied, as in GenroPy | [#15](https://github.com/asqueel-org/asqueel/issues/15) |
| `newrecord` with defaults | missing | [#28](https://github.com/asqueel-org/asqueel/issues/28) |

Known defects with an open issue: logical deletion ignores the deletion
timestamp in read filters ([#16](https://github.com/asqueel-org/asqueel/issues/16));
the hierarchical model has no JSON round trip ([#18](https://github.com/asqueel-org/asqueel/issues/18));
a `%` in a physical name is not escaped for psycopg ([#19](https://github.com/asqueel-org/asqueel/issues/19));
quoted logical names `$"..."` are not supported ([#20](https://github.com/asqueel-org/asqueel/issues/20));
the write compiler does not check the dialect capabilities ([#21](https://github.com/asqueel-org/asqueel/issues/21));
`inspect_postgres` returns a removed model type ([#22](https://github.com/asqueel-org/asqueel/issues/22));
`pkey='a,b'` is accepted ([#23](https://github.com/asqueel-org/asqueel/issues/23));
a record key named `__pkey__N` is overwritten without error ([#24](https://github.com/asqueel-org/asqueel/issues/24));
a schema-tag model cannot set a table prefix ([#25](https://github.com/asqueel-org/asqueel/issues/25)).

## Write cycle boundaries

- The commands modify the caller's record in place and return it. Values the
  database decides (`sql_value`, generated columns, server defaults of omitted
  columns) are read back with RETURNING on PostgreSQL. SQLite has no RETURNING
  in the write cycle. There is no `returning=` argument.
- Keys of the mapping that are not physical columns (alias, formula, `@path`,
  unknown names) do not become SQL columns. They raise no error.
- `update` takes the key from `old_record`, then `pkey`, then the record. It
  writes every physical column present in the record, `None` included. It does
  not check the number of updated rows.
- `delete` accepts a key string or a record. It must remove exactly one row,
  otherwise `RecordNotFoundError`. A missing key string returns without error.
- `delete` is always a physical DELETE. There is no soft-delete or restore
  command: write the logical-deletion column with `update`.
- `sql_insert` accepts one record or a list; a list runs one `executemany` per
  group of records with the same columns, without RETURNING.
- A Python error inside the cycle makes the connection rollback-only: call
  `db.rollback()` before reusing it.

## Query and result boundaries

`query.execute()`, `fetch()` and `count()` run on the owning database
connection and return Toolbox `NamedList` rows. The count terminal follows the
legacy rules, including retained LIMIT/OFFSET. See {download}`the hierarchical
terminal report <../design/92-hierarchical-fetch-count.md>`.

The compiler resolves asqueel field references and preserves authored
SQL expressions. SQL fragments are trusted application code. External data
belongs in parameters, but the compiler preserves legacy symbolic WHERE values:
recognized `$column` and `@relation.column` strings can become model references
rather than literal bindings. Validate external input and use the legacy escape
when such strings must remain literal; see
[symbolic parameters](queries.md#symbolic-parameters-and-external-values).
Successful rendering does not validate every SQL expression against the server.

A to-many path in a projection returns one SQL row per related row. To obtain
one value per parent row, use `@relation.aggr(...)` (see [queries](queries.md)).
`aggregateRows` has been removed: there is no Python-side deduplication of
exploded joins.

Computed projection expressions need explicit aliases. Returned names must be
unique. Pagination uses limit/offset; there is no keyset-pagination helper and
no query or result cache. A record caches its row until `refresh()`; ordinary
query fetches always execute again. Record reads reject custom projections,
limit and offset so they cannot mask multiple matches.

## Policy boundaries

Partition scopes are logical predicates, not PostgreSQL storage partitions.
On reads, the current scope and allowed values are both enforced when present;
an empty allowed collection matches no rows. Missing required scope context is
an error. Writes do not read them: `insert` does not fill the partition column
and `update`/`delete` do not check the row's partition, as in GenroPy (#15).

Draft and logical-deletion exclusions apply to SELECT according to its options.
`delete()` is a physical delete.

A query's environment guard prevents accidental reuse under changed relevant
context. It is not a substitute for database roles, constraints or application
authorization.

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
queries is left to a future GenroPy adapter, not to the core. Native query results use Toolbox `NamedList` rows with name and position access; path lookup on live columns is not complete. Collection
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

`*` follows the legacy physical/static-column convention, including `bagFields`.
On the native 74-table fixture, `adm.htmltemplate_atc` still requires unsupported
static Python columns; the other 73 tables compile on both dialects. Automatic
relation aliases omit the target leading underscore (`customer_name` instead of
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
Formula variants and Python columns are not implemented. String references call
`subquery_<name>()` on the current SELECT's root table, as in the legacy compiler;
the method returns the existing query mapping. XML subQueryColumn still requires
a dictionary declaration. RuntimeModel integration remains pending.
Native subQueryColumn dictionaries compile plain scalar SELECTs on both dialects,
and JSON/XML collections on PostgreSQL. SQLite rejects those collection modes;
there is no implicit DISTINCT or LIMIT, nor a synthetic aggregate for other modes.
Table SQL formula methods use the existing application table, as documented in
[formulas](formulas.md). Structured subquery formulas
are read-only. DML cannot traverse relations or return expressions requiring joins.

### Hooks, environment and application integration

The write cycle runs, in the legacy order, the table triggers (`trigger_on*`),
the column triggers (`onInserting` ... `onDeleted` column attributes),
`protect_update`, `protect_delete`, `protect_validate`, `protect_draft` and the
`onDelete`/`onUpdate` actions of related records. Counters (#31), package
triggers and legacy application mixins are not executed. After-statement hooks are not
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
