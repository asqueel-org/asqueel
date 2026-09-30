# Transactions and database access

`AsqueelDb` uses one execution path for table operations and direct SQL.
A connection is opened lazily for the current thread and `connectionName`.
Statements stay pending until `db.commit()` or `db.rollback()`; commit retains
the connection for reuse. There is no public transaction object or connection
context manager.

## Complete work explicitly

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

Hooks and nested table writes participate in the same selected connection.
Reads also open a transaction. `execute()` does not commit a statement for you.
Closing rolls back pending work and never saves it.

## Select context with tempEnv

```python
with db.tempEnv(connectionName='independent', user='scheduler'):
    db.table('sales.customer').insert({'id': 3, 'name': 'Independent'})
    db.commit()
```

`tempEnv` changes context, not transaction boundaries. Leaving it restores the
previous selection without committing, rolling back or closing a connection.
Nested `tempEnv` blocks are supported; they do not create savepoints.
`temp_env` is the alternative spelling of the same method.

The default connection name is `_main_connection`. Each thread/name pair owns
an independent connection, deferred callbacks and error state. Changing names
does not complete pending work. Each name needs its own commit or rollback.
Independent connections cannot read each other's uncommitted rows and can block
on each other's locks. On SQLite, finish the current transaction before starting
work on another named connection to the same files; see [SQLite](sqlite.md).
Stores are not implemented: `storename` cannot select another database yet.

## Errors and recovery

An SQL execution error automatically rolls back the selected connection before
propagating the original exception. A later operation can start new work.
A Python failure in a table hook or shared write hook marks the connection
rollback-only: explicitly roll it back before reuse. Catching that exception does
not make the incomplete write committable.

If a hook on A calls SQL on B and B's error escapes, B rolls back and A's
incomplete write becomes rollback-only. Other connections remain independent.
If rollback itself fails, the physical connection is discarded; the original
SQL exception is preserved and `db.outcome` reports `unknown`.

## Deferred work

- `db.deferToCommit(callback, *args, **kwargs)` runs before the SQL commit.
- `db.deferAfterCommit(callback, *args, **kwargs)` runs after a successful commit.
- `db.deferredRaise(exception)` prevents the next commit from succeeding.

Callbacks belong to the selected thread/name. `_deferredBlock` groups callbacks;
`_deferredId` controls deduplication within that grouping. Callbacks run with
`onCommittingStep=True` and their connection selected. They can execute SQL,
including through table methods, but cannot recursively commit, roll back or
close the executing connection.

```python
with db.tempEnv(connectionName='worker'):
    db.table('sales.customer').insert({'id': 4, 'name': 'New customer'})
    db.deferToCommit(validate_pending_changes)
    db.deferAfterCommit(publish_committed_change)
    db.commit()
```

The callback names above stand for application functions. A precommit failure
blocks completion until rollback. A postcommit failure cannot undo a commit
already accepted by the server. If that callback started more SQL work, it may
leave a new failed transaction requiring rollback. Automatic retry is not provided.

`db.outcome` reports the selected connection's last outcome: `not_started`,
`active`, `committed`, `rolled_back` or `unknown`. An uncertain commit requires
application reconciliation, not blind replay.

## Thread ownership and cleanup

The model and table handles are shared; environment, connections, write depth
and trigger stacks are local to each thread. Custom table objects must not keep
per-request state on shared attributes. Concurrent async tasks in the same
thread are not isolated by this synchronous API.

```python
def worker(db, user):
    try:
        with db.tempEnv(user=user, connectionName='worker'):
            rows = db.table('sales.customer').query().fetch()
            db.commit()
            return rows
    finally:
        db.closeConnection()
```

`closeConnection()` releases all named connections of the calling thread and
permits subsequent reuse. `close()` additionally closes that thread's local DB
state permanently. Neither method closes another thread's connections: every
worker must perform its own cleanup. Cleanup attempts all local connections,
even if one fails.

The lower-level `Database` and `PostgresDatabase` facades share this execution
implementation and explicit completion rules. They do not offer a second
transaction API. See [direct execution](low-level-runtime.md),
[write hooks](hooks.md), and [legacy adaptations](../adattamenti-legacy.md).
