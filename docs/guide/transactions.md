# Transactions and database access

`AsqueelDb` uses one execution path for table operations and direct SQL.
A connection is opened lazily for the current thread and `connectionName`.
Statements stay pending until `db.commit()` or `db.rollback()`; commit retains
the connection for reuse. There is no public transaction object. Outside a
request, the unit of work is [`session(db)`](#sessions).

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
`db.closeConnection()` rolls back pending work and never saves it.

## Select context with tempEnv

```python
with db.tempEnv(connectionName='independent', user='scheduler'):
    db.table('sales.customer').insert({'id': 3, 'name': 'Independent'})
    db.commit()
```

`tempEnv` changes context, not transaction boundaries. Leaving it restores the
previous selection without committing, rolling back or closing a connection.
Nested `tempEnv` blocks are supported; they do not create savepoints.
With explicit named connection declarations, the selected name must be declared
in the [configuration](cli.md#connection-declaration). Older single-target
recipes allow additional runtime names using the same physical settings.
`temp_env` is the alternative spelling of the same method.

The default connection name is `_main_connection`. Each thread/name pair owns
an independent connection, deferred-callback queues and error state. Changing names
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
SQL exception is preserved and the connection stays rollback-only until
`db.rollback()`.

## Deferred work

- `db.deferToCommit(callback, *args, **kwargs)` runs before the SQL commit.
- `db.deferAfterCommit(callback, *args, **kwargs)` runs after a successful commit.
- `db.deferredRaise(exception)` prevents the next commit from succeeding.

Callbacks belong to the selected thread/name. As in GenroPy, the queues live in
`db.currentEnv`, under `to_commit_defer_calls__main_db_<connectionName>` and
`after_commit_defer_calls__main_db_<connectionName>`; `clearCurrentEnv()` drops
them. `deferredRaise` appends to `currentEnv['_pendingExceptions']`, which is
shared by every connection name: the next commit, on any name, raises them and
empties the list. `_deferredBlock` groups callbacks;
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

A commit whose driver call fails is uncertain: the server may have accepted
it. The connection is discarded and the error propagates. An uncertain commit
requires application reconciliation, not blind replay.

## Sessions

`session(db, **env)` is the unit of work outside a request, as a GenroPy page
request is inside one.

```python
from asqueel import session

with session(db, user='scheduler'):
    db.table('sales.customer').insert({'id': 5, 'name': 'Batch'})
    db.commit()
```

- Entry clears `currentEnv`, then applies the given values.
- Exit calls `db.closeConnection()`, also when the body raises. Work not
  committed is rolled back.
- The database stays usable after the session.
- One session at a time per database and thread: a nested `session(db)` on the
  same thread raises `TransactionStateError`.

A host built on `AsqueelDbMixin` opens the session itself at the first take of
a database during a call, and leaves it in `release_databases()`; see
[configuration grammars](configuration-grammars.md).

## Thread ownership and cleanup

The model and table handles are shared; environment, connections, write depth
and trigger stacks are local to each thread. Custom table objects must not keep
per-request state on shared attributes. Concurrent async tasks in the same
thread are not isolated by this synchronous API.

```python
def worker(db, user):
    with session(db, user=user):
        with db.tempEnv(connectionName='worker'):
            rows = db.table('sales.customer').query().fetch()
            db.commit()
        return rows
```

`closeConnection()` is the GenroPy release: it rolls back what was not
committed and closes all named connections of the calling thread. The database
stays usable: the next statement opens a new connection. It does not close
another thread's connections: every worker must perform its own cleanup,
directly or through `session(db)`. Cleanup attempts all local connections, even
if one fails.

The lower-level `Database` and `PostgresDatabase` facades share this execution
implementation and explicit completion rules. They do not offer a second
transaction API. See [direct execution](low-level-runtime.md),
[write hooks](hooks.md), and [legacy adaptations](../adattamenti-legacy.md).

### Recovery after a callback exception

A callback is removed before invocation; `commit()` does not automatically retry
it. A precommit exception blocks commit until rollback, which clears the pending
queues. An escaping postcommit Python exception stops dispatch; callbacks not yet
reached remain pending. If the
callback started new SQL work, roll back that failed work before reuse; this
cannot undo the earlier successful commit. Without new SQL, another `commit()`
is a no-op. If the application deliberately starts and commits new work in
the same context, it can run the remaining callbacks. Rollback or connection
cleanup clears them; SQL execution errors retain their automatic rollback rules.

At a request boundary, leave the session before starting the next request. Do not retry an entire
write just because an after-commit notification failed: the write is already
committed. External callback effects are not undone by database rollback.

The callback implementer can catch an expected external-service failure with
`try/except` and return normally to let later callbacks run. This does not
repair a database error: caught SQL or table-write failures retain the existing
rollback protections. Do not commit or roll back recursively inside a callback.
