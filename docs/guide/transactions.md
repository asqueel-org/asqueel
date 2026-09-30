# Transactions and database access

Application objects use a shared, lazy synchronous session. `SqlDatabase` table
operations and `db.execute()` retain the selected named connection’s transaction
until explicit completion.
A connection is opened only when a statement is executed.

The examples below assume `db = AsqueelDb(YourRecipe)` and existing tables.
Building a recipe never creates or migrates tables.

## Complete a unit of work explicitly

```python
customer = db.table('sales.customer')
try:
    customer.insert({'id': 1, 'name': 'Ada'})
    customer.insert({'id': 2, 'name': 'Grace'})
    db.commit()
except Exception:
    db.rollback()
    raise
```

Both inserts use the same transaction. Other table operations on `db`, including
reads and work performed by table hooks, join that transaction. After commit
or rollback, the next executed statement starts a new transaction lazily on the
same physical connection.

`db.close()` rolls back pending work and closes the sessions. It never commits
pending writes; call `db.commit()` explicitly to save them. Database operations
must run on the constructing thread.

## Optional atomic scope

```python
with db.transaction():
    customer = db.table('sales.customer')
    customer.insert({'id': 1, 'name': 'Ada'})
    customer.insert({'id': 2, 'name': 'Grace'})
    rows = customer.query(order_by='$id').fetch()
```

Normal exit commits; any exception leaving the scope rolls back. Inside this
application-level scope, continue using `db.table()` and `db.execute()`: they
share the scope's session. `with db.transaction() as scoped_db:` yields the same
`SqlDatabase` object. An empty scope opens no connection.

Enter a transaction scope only when there is no pending session transaction.
Even a prior SELECT can have opened one; call `db.commit()` or `db.rollback()`
first. Nested scopes and manual commit/rollback inside a scope are rejected.
There are no nested savepoints.

## Recover after failure

Catch errors outside the atomic scope:

```python
import psycopg

try:
    with db.transaction():
        db.table('sales.customer').insert({'id': 1, 'name': 'Ada'})
except psycopg.errors.UniqueViolation:
    # The scope has already rolled back; the session can be reused.
    pass
```

An executed SQL error automatically rolls back the selected connection before
propagating the original error. Previous writes on that connection are discarded;
with ordinary implicit transactions, a later operation can start new work without
an additional manual rollback. Other named connections remain independent. If a table hook on A calls SQL on
B and B's error escapes the hook, B is rolled back automatically, while A's
incomplete table operation becomes rollback-only. A rollback on B cannot undo
work already performed on A. A connection unrelated to that operation remains
usable.

A Python domain error in a table write/hook still marks that session rollback-only;
call `db.rollback()` before reuse. Inside the optional atomic scope, a caught SQL
error also prevents successful scope completion: exit raises `TransactionStateError`.
If automatic rollback itself fails, the connection is discarded, the outcome is
`unknown`, and explicit recovery is required. The original SQL error is preserved
with the rollback failure as its cause.

For batch processing, catch a failed item outside its write, roll back, then
save its error status and continue with the next item in a new transaction.
An independent named connection can commit an error log while the failed main
transaction awaits rollback. Catching an external service error before a
successful database write can also let you store that error as application
status; this does not require committing a failed database operation.

A hook cannot commit, roll back or close the database during its enclosing write.
This ensures its changes and the primary write have one transaction boundary.
Direct compiled-query profile/environment rejection occurs before dispatch;
it does not independently poison a healthy session. A failure inside a table
write is treated as a failed domain operation, even before SQL has run.

`db.outcome` reports `not_started`, `active`, `committed`, `rolled_back`, or
`unknown`. Unknown commit outcomes must be reconciled with application-specific
identifiers before retrying a write: the server may already have committed it.
Driver errors propagate without being wrapped, and cleanup is still attempted.

## Independent named connections

The same database object can keep several connections to the same database:

```python
customer = db.table('sales.customer')
customer.insert({'id': 10, 'name': 'Pending on main'})
with db.tempEnv(connectionName='independent'):
    customer.insert({'id': 20, 'name': 'Committed separately'})
    db.commit()
db.rollback()  # Discards id=10; id=20 remains committed.
```

The default name is `_main_connection`. Each name opens a connection lazily and
retains it after commit/rollback. `db.currentConnectionName` identifies the
selection; `db.outcome` describes that name's session. Changing names does not
commit, roll back or close anything. Database isolation and locks still apply;
an independent connection cannot assume it can read the main connection's
uncommitted rows. Avoid making it wait on locks held by the suspended work.

`db.closeConnection()` rolls back and closes every named connection, while keeping
the database object usable. `db.close()` also closes every name and permanently
closes the object. Cleanup attempts all connections even if one fails.

The optional `db.transaction()` scope owns only the name selected on entry.
Work on other names is independent and requires its own completion. An empty
scope opens no connection. Selecting another store changes the database context;
selecting another connection name separates transactional work within it.

## Work around commit

`deferToCommit()` registers work to run before the database commit.
`deferAfterCommit()` registers work after a successful commit. Grouping and
identifiers organize and deduplicate deferred work. Keep that work associated
with its connection context: committing one name must not drain another name's
callbacks.

Callbacks run with `onCommittingStep=True` and the connection name whose
transaction is being completed. They can execute queries, perform table writes
and register more deferred work. They cannot explicitly call commit, rollback
or close on the session already being completed.

Blocks named by `_deferredBlock` execute in sorted order; callbacks within a
block execute in registration order. `_deferredId` deduplicates registrations
of the **same callable object** within that block. The registration method
returns the stored kwargs dictionary, so a later registration can update it.
False-valued IDs request separate entries. Nonempty IDs are compared as strings.
Retain a bound method reference if its identity must remain stable across calls.

Re-registering a callback under the same ID while it runs does not run it again
unless the callable has `deferredCommitRecursion=True`. Such callbacks must
provide their own termination condition. Registration alone does not open a
connection or begin a transaction; callbacks wait for transactional work.

```python
def record_committed(table, pkey):
    print(f"Committed {table}: {pkey}")

customer = db.table('sales.customer')
customer.insert({'id': 101, 'name': 'Ada'})
db.deferAfterCommit(record_committed, table=customer.fullname, pkey=101)
db.commit()
```

`deferredRaise(exception)` queues an error for the commit boundary and raises
`DeferredCommitError` there. A pre-commit Python failure prevents commit and
requires rollback with the implicit transaction API; the optional transaction
scope performs that rollback automatically. A caught SQL failure still aborts
the active commit dispatch, so it cannot resume and publish a successful outcome.
Rollback, SQL rollback, closure and uncertain commit discard queued work.

A successful after-commit callback may issue SQL and thereby start a new
transaction, which the commit loop then completes as in Genropy. If that callback
fails, already committed work stays committed. Roll back any new work explicitly,
or let the optional transaction scope roll it back on exit.

Deferred errors prevent successful commit. Application events are collected
within the write lifecycle and handed to the application integration after
commit; a database event is not itself a web notification. A rollback must not
publish an event claiming that the discarded write succeeded.

A failure after the server has committed cannot undo that commit. Applications
must distinguish failed database work from a failure to publish its outcome.

## Environment scopes

The application database shares one environment between its compiler and session:

```python
with db.temp_env(customer_id=7):
    with db.transaction():
        rows = db.table('sales.customer').query(
            where='$id = :env_customer_id',
        ).fetch()
```

A `SqlQuery` recompiles when a terminal is called. Its `.compiled` property
instead returns a fixed compiled statement with environment bindings. Executing
that statement after a relevant environment value changes raises
`EnvironmentMismatchError`. See [environment scopes](environment.md).


## Choose one transaction API

| Object you constructed | Execute inside an atomic scope | Standalone execute |
|---|---|---|
| `AsqueelDb(Recipe)` → `SqlDatabase` | `db.table(...).query(...).fetch()` or `db.execute(...)` | Keeps the session transaction pending. |
| `PostgresDatabase(...)` / `Database(...)` | `with db.transaction() as tx:` then `tx.execute(...)` | Owns and completes a transaction for that statement. |

For ordinary application code, use the first row throughout. The second is an
integration interface for callers managing compiled statements. Its complete
lifecycle is documented in [low-level execution](low-level-runtime.md).

Continue with [table hooks](hooks.md) for business rules in the same transaction,
or [troubleshooting](troubleshooting.md) for common session errors.
