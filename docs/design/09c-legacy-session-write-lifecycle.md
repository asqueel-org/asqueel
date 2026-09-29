# 09c — Legacy database sessions, writes and record lifecycle

## Architectural conclusion

The legacy product's reusable logic lives above SQL rendering: table methods,
mutable records, ordered hooks, relation cascades, deferred commit work and the
session that keeps their statements together. The current synchronous runtime
is a useful execution primitive, but **its `db.execute()` is not a compatible
replacement for legacy `GnrSqlDb.execute()`**. The former commits and closes a
fresh connection per call; the latter normally returns a cursor on a reusable
session connection without committing. Reusing the legacy table layer requires
an explicit session/table service boundary and transaction-bound dispatch.

This document is an internal architecture audit, not a declaration that legacy
hooks, record clusters or session compatibility have been implemented.

## Source register

Legacy source revision: **`fa35e5adfa6ad1b269f3a22a9b12c4c1ee6513ea`** in
`/Users/gporcari/Sviluppo/Genropy/genropy`. The audited SQL source files had no
working-tree modifications. This is a different baseline from the earlier
historical `e12...` analysis; findings below refer to `fa35...` only.

Native source revision: **`bf66bcacfeededc7f0ce82cd5c48f6437aa174df`** in this
repository. Runtime, environment, driver and compiler files were unchanged
relative to that revision when inspected.

`L<n>:a–b` and `N<n>:a–b` below refer to the numbered lines of these exact files.

| ID | Source |
|---|---|
| L1 | [gnrsql/connections.py](https://github.com/genropy/genropy/blob/fa35e5adfa6ad1b269f3a22a9b12c4c1ee6513ea/gnrpy/gnr/sql/gnrsql/connections.py) |
| L2 | [gnrsql/transactions.py](https://github.com/genropy/genropy/blob/fa35e5adfa6ad1b269f3a22a9b12c4c1ee6513ea/gnrpy/gnr/sql/gnrsql/transactions.py) |
| L3 | [gnrsql/write.py](https://github.com/genropy/genropy/blob/fa35e5adfa6ad1b269f3a22a9b12c4c1ee6513ea/gnrpy/gnr/sql/gnrsql/write.py) |
| L4 | [gnrsql/env.py](https://github.com/genropy/genropy/blob/fa35e5adfa6ad1b269f3a22a9b12c4c1ee6513ea/gnrpy/gnr/sql/gnrsql/env.py) |
| L5 | [gnrsql/execute.py](https://github.com/genropy/genropy/blob/fa35e5adfa6ad1b269f3a22a9b12c4c1ee6513ea/gnrpy/gnr/sql/gnrsql/execute.py) |
| L6 | [gnrsqltable/crud.py](https://github.com/genropy/genropy/blob/fa35e5adfa6ad1b269f3a22a9b12c4c1ee6513ea/gnrpy/gnr/sql/gnrsqltable/crud.py) |
| L7 | [gnrsqltable/triggers.py](https://github.com/genropy/genropy/blob/fa35e5adfa6ad1b269f3a22a9b12c4c1ee6513ea/gnrpy/gnr/sql/gnrsqltable/triggers.py) |
| L8 | [gnrsqltable/record.py](https://github.com/genropy/genropy/blob/fa35e5adfa6ad1b269f3a22a9b12c4c1ee6513ea/gnrpy/gnr/sql/gnrsqltable/record.py) |
| L9 | [gnrsqldata/record.py](https://github.com/genropy/genropy/blob/fa35e5adfa6ad1b269f3a22a9b12c4c1ee6513ea/gnrpy/gnr/sql/gnrsqldata/record.py) |
| L10 | [gnrsql/helpers.py](https://github.com/genropy/genropy/blob/fa35e5adfa6ad1b269f3a22a9b12c4c1ee6513ea/gnrpy/gnr/sql/gnrsql/helpers.py) |
| L11 | [gnrsqltable/helpers.py](https://github.com/genropy/genropy/blob/fa35e5adfa6ad1b269f3a22a9b12c4c1ee6513ea/gnrpy/gnr/sql/gnrsqltable/helpers.py) |
| L12 | [adapters/gnrpostgres.py](https://github.com/genropy/genropy/blob/fa35e5adfa6ad1b269f3a22a9b12c4c1ee6513ea/gnrpy/gnr/sql/adapters/gnrpostgres.py) |
| L13 | [adapters/_gnrbaseadapter.py](https://github.com/genropy/genropy/blob/fa35e5adfa6ad1b269f3a22a9b12c4c1ee6513ea/gnrpy/gnr/sql/adapters/_gnrbaseadapter.py) |
| N1 | [runtime.py](../../src/genro_sql/runtime.py) |
| N2 | [environment.py](../../src/genro_sql/environment.py) |
| N3 | [drivers/psycopg.py](../../src/genro_sql/drivers/psycopg.py) |
| N4 | [contracts.py](../../src/genro_sql/contracts.py) |

Evidence labels: **COD** means direct inspection of executable source;
**PRO** means a targeted source-extraction probe run during this audit;
**INF** means an architectural consequence reasoned from those facts. Source
comments marked `REVIEW` are not treated as independent evidence: the executable
bodies were checked. No complete legacy application, DB request cycle or
multi-store scenario was run for this audit.

## 1. Connection and transaction ownership

### 1.1 The legacy database object is a session router

**COD — L1:79–119; L4:203–211.** Connections are cached first by thread ID and
then by `(storename, connectionName)`. The connection receives `storename`,
`connectionName` and a mutable `committed` flag. `currentStorename` and
`currentConnectionName` are resolved from the live thread environment, with
root/main fallbacks. `connection` can return a list for `'*'` or comma-separated
store names. This is a cache of session connections, not an observed bounded
pool with admission/backpressure semantics.

**INF.** The same `GnrSqlDb` object can serve multiple thread-local sessions.
A table object references that router; it does not permanently bind one physical
connection. The current native `Database` instead belongs to its constructing
thread and permits one active transaction, N1:27–38,54–60,118–134. Keeping the
new low-level thread ownership rule is compatible with a future higher-level
session facade that resolves the correct thread-owned executor. Sharing one
native `Database` object between legacy threads is not compatible.

### 1.2 Three different meanings of autocommit

**COD.** These legacy mechanisms must not be conflated:

| Mechanism | Actual behavior | Source |
|---|---|---|
| Adapter `connect(autoCommit=True)` | Enables psycopg2's autocommit isolation mode. | L12:120–145 |
| `db.execute(..., autocommit=True)` | Executes on the session connection, then invokes the framework `commit()` pipeline. Default is `False`. | L5:46–56,159–162 |
| `db.autoCommit()` | Examines recorded DB events; commits if every event allows it, otherwise raises `GnrMissedCommitException`; no events means return. | L2:219–233 |

**COD — N1:34–36,72–76,118–134,152–188.** Native `Database` rejects
`connect_kwargs['autocommit']=True`, but `db.execute(query)` deliberately opens
an explicit transaction and commits it automatically on normal return. Each
call opens and closes a fresh connection. `with db:` only closes the wrapper;
it does not group the contained statements into one transaction.

**INF — compatibility blocker.** A legacy sequence `insert(parent)` followed by
`insert(child)` followed by `db.commit()` cannot be mapped to two independent
native `db.execute()` calls: the first could persist even if the second fails.
The table/service layer must route both statements through the same active
transaction. The current `tx.execute()` already supplies the primitive needed
for that arrangement; the session facade does not yet exist.

### 1.3 Low-level execute owns a cursor, not a complete result lifecycle

**COD — L5:92–162.** Legacy execute resolves `:env_*` at execution time, lets
explicit `sqlargs` override the environment-derived values, special-cases
workdate/store, converts bytes to UTF-8 strings and strips certain escaped value
prefixes. It routes the store, adapts SQL, creates or reuses a cursor, executes,
marks the single connection uncommitted, optionally runs a debugger, and returns
the cursor. Named server-side cursors are supported. The adapter's ordinary
insert/update/delete methods call this same execute path, L13:797–819,843–892.

**COD — L5:152–160.** An exception inside its execution/debugger try block calls
`rollback()` and is re-raised. Argument adaptation occurs before that try block.
The function does not make all possible framework errors transaction-fatal:
a Python hook error outside execute is not covered by this handler.

**COD — N1:136–150; N3 `execute`.** The native driver returns fully materialized
rows and closes its cursor before returning. A driver execution error marks the
active transaction rollback-only; cleanup occurs at transaction exit. The
wrapper does not allow a caller to catch that error and continue executing as
if the transaction were healthy. Pre-dispatch profile/environment validation
errors are distinct: no SQL ran and those checks do not set rollback-only.

**INF.** Eager result ownership is a sound default for the new native API, but
legacy consumers expecting `cursor.index`, `fetchone`, `fetchall`, named cursors
or selection/record objects need a defined adapter. Replacing their cursor with
a list silently would break their contracts.

### 1.4 Framework commit is a queue-processing algorithm

**COD — L2:65–93.** `commit()` repeatedly chooses an uncommitted connection with
the currently active connection name. For that connection it:

1. Enters its store context with `onCommittingStep=True`.
2. Drains the before-commit callback queue.
3. Checks the environment's pending exceptions and raises if present.
4. Calls physical `connection.commit()`.
5. Marks `connection.committed = True`.
6. Enters the store context and drains the after-commit queue.
7. Re-evaluates the available uncommitted connections, then calls `onDbCommitted()`
   after the loop finishes.

The flag is set **before** after-commit callbacks; the docstring's numbered list
has the reverse ordering. The executable code governs this finding.

**COD — L2:95–129,171–208.** Queues are environment Bags keyed by queue name and
`connectionKey()`, ordered by blocks. Entries contain callable/args/kwargs.
Deduplication uses callable identity and `_deferredId`; existing kwargs can be
returned to the caller. An entry is popped before its callback runs; recursion
controls concern removal of an entry reintroduced under that label.

**INF.** These callbacks cannot be reduced to one `driver.commit()` call. A new
session layer must distinguish before-commit work, post-commit work and event
publication. A post-commit error cannot retroactively roll back already committed
writes. No exactly-once external delivery guarantee follows from the legacy queue.
Multiple physical commits are sequential here; no distributed atomic commit is
implemented by this loop.

### 1.5 Rollback and cleanup scopes differ

**COD — L2:252–287.** `rollback()` rolls back only the currently selected
connection or connection list. `rollbackAll()` walks uncommitted connections
sharing the current connection name across stores, rolls them back, clears their
deferred queues, then clears pending exceptions. Trigger-induced writes in a
different store therefore make the distinction material. Neither inspected
rollback method marks `committed=True` after rollback; do not interpret the flag
as a complete transaction-state machine.

**COD — L1:41–57.** `closeConnection()` pops each connection from the thread cache,
then rolls back and closes in one try block, suppressing exceptions. If rollback
raises, the later close in that block is skipped. This is a cleanup risk visible
in control flow, not a reproduced connection leak in this audit.

**COD — N1:152–188.** The native runtime attempts close even after commit/rollback
fails, reports uncertain outcome as `unknown`, preserves the original transaction
error if close also fails, and releases its active transaction marker. It has no
multi-store rollback or deferred queues. These more explicit failure semantics
should be preserved when adding session/domain operations.

## 2. Table dispatch and write semantics worth reusing

### 2.1 Table methods are the domain-facing API

**COD — L6:53–142.** `table.insert(record)` calls `db.insert(self, record)` and
returns the same record. Normal `update` similarly returns the potentially
mutated record; it derives an old primary key when needed and may enter a
package-specific store/implementation context. Delete accepts a string key,
loads and locks that record, ignores a missing record, then invokes DB deletion.
None of these methods commits. The decorators add SQL/audit context around the
operation; their full application logging contracts are outside this audit.

**INF.** A record is not just input to a DML compiler: generated keys, defaults
and hook mutations become caller-visible state. A future table API must specify
whether it retains this in-place contract, returns a new record, or provides both
through a compatibility adapter. Returning only a `QueryResult` does not preserve it.

### 2.2 Exact normal-write ordering

**COD + PRO — L3:153–168,251–265,294–319.** The following order was verified both
from source and with extracted WriteMixin methods against recording stubs. The
probe isolates dispatch order; it does not execute real SQL or application hooks.

| Stage | Insert | Update | Delete |
|---|---|---|---|
| Initial guards | `checkPkey`, `protect_validate` | `protect_update`, `protect_validate` | `deletable`/permission check, `protect_delete` |
| Before field hooks | `onInserting` | `onUpdating(record, old_record)` | `onDeleting` |
| Before table hook | `trigger_onInserting` | `trigger_onUpdating` | `trigger_onDeleting` |
| Before package hooks | External package `onInserting` | External package `onUpdating` | External package `onDeleting` |
| Pre-SQL work | Assign counters; optional `dbo_onInserting`; optional draft protection | Optional `dbo_onUpdating`; assign counters | `deleteRelated`; optional `dbo_onDeleting` |
| Physical SQL | Adapter insert | Adapter update | Adapter delete |
| Immediate post-SQL work | `_onDbChange` | `updateRelated`, then `_onDbChange` | `_onDbChange` |
| After hooks | Field, table, external package `onInserted` | Field, table, external package `onUpdated` | Field, table, external package `onDeleted` |
| Final step | — | — | Release counters |

The relative positions matter. For example, related rows are deleted before the
parent SQL, update cascades run after its SQL, and a delete failure before the
last step prevents counter release. An adapter that collects all hooks into a
single unordered list would not preserve these behaviors.

**COD — L3:72–85,87–131.** `_onDbChange` can update totalizers, invoke change-log
hooks and write a log record, then delegate configured DB notification to the
adapter. The base `notifyDbEvent()` is a no-op; do not confuse that method with
the concrete `_dbNotify` path or assume that all notifications are equivalent.

### 2.3 Raw and bulk writes have different contracts

**COD — L3:170–220; L6:278–321,394–436.**

| Operation family | Python domain hooks | Additional observable behavior |
|---|---|---|
| Normal insert/update/delete | Ordered lifecycle above | Protection, counters, cascades and change tracking. |
| `raw_insert/raw_update/raw_delete` | Skip normal write hooks | Still call `_onDbChange(..., _raw=True)`: totalizers/logging/notifications may run. |
| `insertMany` | Direct adapter delegation | Does not invoke the per-record lifecycle in WriteMixin. |
| `deleteSelection` | Loads rows and calls normal delete per row | Locks selection and preserves per-row delete lifecycle. |
| `sql_deleteSelection` | Uses adapter SQL delete | Different from per-row domain deletion. |
| `batchUpdate` | Chooses normal or raw update | Optional callbacks and explicit commit scheduling. |

The integer `autocommit` batch path tests `i % commit_every == 0` with zero-based
`i`, L6:400–403,412–436: its first boundary is the first processed iteration, not
an asserted full batch of N records. Characterize/fix that deliberately if ported;
it is not a reason to silently make every operation auto-commit.

**INF.** Preserve explicit operation categories. A new bulk API should state
which hooks and side effects it runs; the word “raw” alone does not mean “only SQL”
in the existing application model.

### 2.4 Cascades are application operations, not only FK clauses

**COD — L6:148–227.** Update/delete relation handling reads relation metadata,
loads related rows with locking and with draft/logical-deletion/partition filters
bypassed, and dispatches related table operations for cascade/set-null behavior.
Those related operations can run their own hooks. The source distinguishes
raise/ignore/cascade/set-null and contains store-routing decisions.

**INF.** Replacing this with an `ON DELETE CASCADE` constraint is not automatically
equivalent: Python hook order, counters, logging and other side effects differ.
Native constraints remain useful, but ownership of each rule must be declared
before native triggers or cascades coexist with Python logic. Store behavior
remains deferred; the single-store path still needs same-transaction recursion.

### 2.5 Trigger extensibility and error cleanup

**COD — L6:685–715; L7:117–155,179–185.** Field triggers are model-registered:
callable triggers receive `(record, field_name)`; named triggers are resolved
against the current or configured trigger table and receive contextual kwargs.
External-package hooks follow application package iteration and honor
`avoid_trigger_<package>` for all or selected events. Base lifecycle/protection/
counter hooks are intentionally overridable no-ops.

**COD + PRO — L10:74–83.** The `in_triggerstack` decorator pushes a trigger entry,
invokes the wrapped operation, then pops only on normal return. The extraction
probe raised inside the wrapped operation and observed one stale stack entry.
Preserve nested-trigger introspection as a product capability, but use guaranteed
cleanup rather than reproducing this failure behavior.

**INF.** Hook exceptions are transaction failures at the domain level even if
no driver error occurred. Run the whole domain operation within one explicit
transaction boundary, and do not catch/repackage a hook exception in a way that
allows the remaining transaction to commit unnoticed.

## 3. Records, locking and changesets

### 3.1 Record loading and construction are separate workflows

**COD — L8:106–138,161–177,309–344,620–632.** New-record construction applies
application defaults, optional source-record copying, explicit overrides,
optional key assignment and extended defaults. Existing-record access constructs
`SqlRecord` with relation/output/lock/store options; it need not load immediately.
`checkPkey` can mutate an inserted record by assigning a generated key.

**COD — L9:283–370.** Compilation and result loading are lazy properties. Record
execution fetches and closes a cursor, then enforces missing/duplicate-record
semantics, with flags affecting those errors. It is not simply SELECT LIMIT 1.
Record loading also has a historical exploding-column aggregation path.

**Decision.** Preserve explicit cardinality/errors and output contracts that an
application depends on. Do not revive Python reassembly/deduplication of expanded
joins: the user's removal of aggregateRows applies to equivalent hidden behavior,
not just to one method name. Record output needing collections must specify them.

### 3.2 `recordToUpdate` is not a transaction context

**COD + PRO — L6:343–345; L11:124–192.** `RecordUpdater` loads/locks a record and
saves its old values. On successful context exit it dispatches insert/update/delete,
normal or raw. Setting the primary key to literal `False` selects deletion.
Its body does not commit or establish a transaction. The source sets
`self.for_update = for_update or True`; the probe confirmed `for_update=False`
still becomes `True`. This behavior needs an explicit compatibility decision,
not an undocumented transfer into the native API.

**INF.** The row lock must remain held until the surrounding unit of work ends.
Implementing its initial read with native standalone `db.execute()` would commit
and release the lock before the user edits/saves the record. A future record
updater must be bound to an existing transaction or clearly own the entire unit.

### 3.3 Record clusters combine ordering and concurrency checks

**COD — L6:498–631,644–679.** `writeRecordCluster` splits the Bag changeset into
main fields, related-one and related-many nodes. It interprets new/delete/primary-key
flags, loads existing records with `for_update=True`, captures old values, and
uses timestamp/field-old-value comparisons to detect incompatible changes.
The exact concurrency policy depends on `noChangeMerge`, `noTestForMerge`, the
presence of `lastTS`, deletion intent and field metadata; it is not a universal
optimistic-version check.

Related-one clusters are saved first and their keys copied into the main record.
The main record is inserted/updated next. Related-many clusters follow with the
parent key assigned where appropriate. Delete of an existing main record follows
the table delete path. The splitter ignores relation nodes carrying `None`, and
can recover missing relation mode from the model. It mutates the input cluster
while separating relation nodes.

**INF.** Reusable pieces include explicit changesets, old/new values, relation
ordering and meaningful concurrency errors. Their transaction owner must cover
the whole graph, including recursive hooks. “Compile a list of DML statements”
without these contracts would lose application behavior. Native virtual relations
must remain read-only and outside implicit cluster writes, per the agreed design.

### 3.4 Saving a record Bag does not commit it

**COD — L9:759–797.** `SqlRecordBag` holds a DB/table reference and `isNew` state.
`save()` merges kwargs into the Bag, calls table insert/update and flips `isNew`
after insert. It does not call commit. The flag describes the local lifecycle,
not confirmed transaction durability: a later rollback can undo the insert.

**INF.** A modern record facade needs a clear distinction between new/persisted
in the current transaction and durably committed. Reusing the legacy flag without
that explanation would expose misleading state after rollback.

## 4. Environment and lazy resolver boundaries

### 4.1 Mutable session services cannot all become deepcopy context values

**COD — L4:59–71,75–117; L10:192–218.** Legacy `currentEnv` is a mutable dictionary
indexed by thread ID and can be replaced or updated directly. It contains not
only scalar query context but deferred callback Bags, trigger stacks, DB events
and pending exceptions. `TempEnv` overlays keys, restores existing values and
conditionally removes keys introduced by the scope.

**PRO.** With an initially empty environment, `with TempEnv(db, introduced=1)`
followed by changing `introduced` to `2` leaves `introduced=2` after exit: newly
introduced keys are removed only if their values still compare equal to the
original scope value. This differs from complete scope restoration.

**COD — N2:15–71.** Native `SqlEnvironment` isolates contexts with `ContextVar`,
copies values on initialization/scope entry/read, returns detached snapshots
and always resets the scope token. `None` is an explicit value; absence is
separate. Its dictionary-shaped aliases do not support direct live mutation.

**INF — required split.** Keep immutable/copied query context separate from
mutable session execution state. Deferred callbacks, trigger recursion state,
connection registries and event accumulators should live in a session/unit-of-work
object. Deepcopying the entire legacy environment on every access would either
break shared queue identity, fail for resources, or change application behavior.
A compatibility adapter must expose intentional operations for those services;
renaming `currentEnv` alone is not sufficient.

### 4.2 Lazy Bag relations defer both SQL and context selection

**COD — L9:77–116,140–170,591–603,633–641,673–687.** Related-record/selection
resolvers retain the DB object plus relation keys, join conditions and selected
query context metadata. `load()` constructs a fresh record/query when accessed.
Record resolver serialization removes the direct DB reference and stores a
symbolic `maindb` marker. An explicit relation store field may provide store
routing, but a full execution-time environment/transaction snapshot is not captured
by these resolver constructors.

**INF, not a reproduced concurrent bug.** Passing an unresolved record Bag to
another thread or loading it after its original scope has ended may execute under
that consumer's thread-local environment and connection. It cannot be assumed to
remain in the original row-lock/transaction scope. Cached resolver results and
mutable parent Bags add further shared-object concerns; this audit does not claim
that every Bag resolver is unsafe or that its base implementation has no locking.
The specific source-backed issue is the absence of a captured DB session contract
in the SQL resolver boundary inspected here.

**Decision recommendation.** Keep resolver-based convenience only behind explicit
lifetime/context rules: resolve eagerly within the unit of work, or retain a
session handle with validity checks and declared rebinding behavior. Do not ship
an async/thread wrapper that moves these objects implicitly. The current product
is synchronous; any async API remains deferred until the core contracts settle.

## 5. Reuse map and deliberate modernization

| Concern | Preserve from legacy | Deliberately change / current gap |
|---|---|---|
| Table-facing programming model | Model-aware table operations and overridable application logic. | Native core currently exposes compiler/runtime primitives, not the complete table service. |
| Unit of work | Several table writes/hooks share one uncommitted transaction. | Explicit ownership and fail-closed rollback-only state; never auto-commit each nested operation. |
| Hook ordering | Guard/field/table/package order; old/new record contracts; counters and cascades. | Guaranteed stack cleanup; distinguish post-SQL from post-commit events. |
| Raw/bulk behavior | Explicitly separate bypass modes and documented side effects. | No silent skipping of protection or event behavior under a generic “fast path”. |
| Environment | Convenient nested contextual values and explicit argument precedence. | ContextVar snapshots, missing/None distinction and stale-query guards; mutable session services kept separate. |
| Record lifecycle | Missing/duplicate errors, defaults, keys, update locks and conflict diagnostics. | Defined transaction lifetime and rollback state; no accidental LIMIT-1 replacement. |
| Result collections | Explicit collection semantics needed by the application. | aggregateRows and equivalent hidden Python join recomposition stay removed. |
| Row scope | Declarative partition/draft/logical-deletion intent. | Strict native scope behavior is intentional; historical bypass defaults are not blanket authorization. |
| Store/tenant | Preserve concepts and model identities for later adaptation. | Routing and multi-store coordination remain deferred, not half-emulated by one connection. |
| Backend extension | Separate physical SQL/driver behavior from application hooks. | Native trigger/function/view coexistence needs explicit ownership; not an automatic replacement for Python hooks. |

## 6. Suggested architecture boundary, not an implementation plan

1. **Application DB facade:** resolves tables and current session; provides stable
   application vocabulary. It must not conflate “get a DB service” with “open a
   fresh auto-committing connection”.
2. **Session / unit of work:** owns the active native transaction, hook stack,
   deferred queues, event accumulation and commit outcome. Recursive table calls
   reuse its transaction; they do not enter another low-level transaction.
3. **Table service:** defaults, keys, protection, hook dispatch, related writes,
   record changesets and application-specific methods. Legacy mixins adapt here.
4. **Compiler / model:** resolves expressions, physical mappings, result metadata
   and declared policies. It does not execute domain hooks during compilation.
5. **Driver / synchronous runtime:** binds, executes, materializes and handles
   physical transaction completion with the already implemented failure rules.

These roles can be implemented with small cooperating objects; they do not
require copying the entire legacy object graph. The key acceptance criterion is
behavior: an application method calling another table method must still execute
one coherent, rollback-capable domain operation.

## 7. Verification performed and tests required before reuse

Performed in this audit:

- Read all requested lifecycle modules and the supporting adapter/helper paths
  needed to resolve dispatch and context behavior at the recorded commits.
- Executed six focused probes by extracting AST definitions from the exact legacy
  files and supplying recording stubs: insert order, update order, delete order,
  TempEnv overwritten-new-key behavior, trigger-stack exception cleanup, and
  RecordUpdater locking/update dispatch. All six assertions passed.
- Inspected existing native tests covering same-thread execution, nested/closed
  state errors, callback reentrancy, rollback-only, commit/close failures,
  environment guards and copied snapshots. No full-suite rerun was necessary for
  this documentation-only audit; prior suite success is not evidence of legacy
  application compatibility.

The extraction probes intentionally remove integration dependencies: write-order
probes use an identity trigger-stack decorator and stub adapter; the stack itself
is tested separately. They do not certify real hooks, locking, notifications or
transaction effects on PostgreSQL.

The standalone [probe script](evidence/legacy_session_probes.py) is preserved with
this audit. It accepts the Genropy repository root, uses only the Python standard
library, and prints a JSON summary after its six checks pass. Use a checkout at
the pinned legacy revision; a different revision may intentionally change these
characterizations.

```sh
git -C /path/to/genropy rev-parse HEAD
python docs/design/evidence/legacy_session_probes.py /path/to/genropy
```

The first command must report `fa35e5adfa6ad1b269f3a22a9b12c4c1ee6513ea`.
The script executes extracted definitions in stub namespaces, not the complete
modules; it does not edit the checkout, open a database or install dependencies.

Before claiming reuse compatibility, build a small real application test with:

- Parent/child operations and a nested table hook, followed by failure after the
  parent SQL: no partial persistence and no stale hook-stack state.
- Record-to-update read/lock/edit/save spanning one transaction, with a concurrent
  connection proving the lock's lifetime and release.
- Before-commit callbacks that add further work; after-commit failure with an
  honestly reported already-committed outcome; queue state after rollback.
- Normal/raw/bulk paths checked separately for hook, totalizer, logging and event
  differences; no accidental commit between graph nodes.
- A record Bag or resolver accessed after scope exit or from another thread:
  explicit supported behavior or a deterministic rejection, never silent context
  rebinding presented as the original transaction.
- Application defaults/generated keys and record flags before/after rollback;
  old-value conflict handling for the chosen record-cluster profile.

No implementation changes, public-guide edits, commits or pushes were made for
this audit. The document identifies which logic should be reused and which
boundaries must be added before that reuse is safe and behaviorally meaningful.
