# Transactions and database access

An `AsqueelDb` holds the model and the configuration shared by every call.
A `SessionDb` holds the connection, `currentEnv` and transaction state of one
call; `db.session()` returns it ([sessions](#sessions)). Table operations and
direct SQL run on a `SessionDb`, through one execution path. The connection
opens lazily. Statements stay pending until `db.commit()` or `db.rollback()`;
commit retains the connection for reuse. There is no public transaction object.
In the examples below `db` is a `SessionDb`.

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
Reads also open a transaction. `execute()` commits only with `autocommit=True`.
Every `db.commit()` ends by calling `db.onDbCommitted()`, a method without
effect that a database subclass overrides, also when nothing was pending.
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

The main session of a call is named `_main_connection`. Each named session of
a call owns an independent connection, deferred-callback queues and error state.
`tempEnv(connectionName='x')` runs the block's statements on the connection of
the call's session `x`, opened on first use on the configured connection `x`
(`main` when none is declared) and closed with the session that opened it; the
environment stays the caller's. Changing names
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

Callbacks belong to the selected connection name. The queues live in
`db.currentEnv`, under `to_commit_defer_calls__main_db_<connectionName>` and
`after_commit_defer_calls__main_db_<connectionName>`; `clearCurrentEnv()` drops
them. `deferredRaise` appends to
`_pendingExceptions__main_db_<connectionName>`: legacy keeps one global
`currentEnv['_pendingExceptions']`, asqueel keeps one list per named
connection, like the deferred queues. The next commit of that name raises them
and empties the list; a rollback of that name empties it. `_deferredBlock` groups callbacks;
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

`db.session(name=None, *, target='main', **env)` returns the `SessionDb` of
the current call: the main one, or the one called `name`. A call is one
request, one job or one console command.

```python
from asqueel import AsqueelDb

shared = AsqueelDb('myapp')
with shared.session(user='scheduler') as db:
    db.table('sales.customer').insert({'id': 5, 'name': 'Batch'})
    db.commit()
shared.close()
```

- A new session copies the `environment=` defaults of the `AsqueelDb`, then
  applies `env`.
- `target` is the configured connection the session connects to.
- Within one call, `session(name)` returns the open session of that name.
  Passing `env` to an already open session raises `TransactionStateError`.
- `session(...)` on a `SessionDb` asks its `AsqueelDb`.
- `close()` rolls back what was not committed and closes the connection. A
  closed session refuses any later use with `TransactionStateError`.
- As a context manager, a `SessionDb` is the current session of the body and
  closes at exit. An exit by exception rolls back; the body's error propagates.
- `AsqueelDb.close()` closes every open session of that database.
- `closeConnection()` keeps its meaning: it rolls back, closes the connection
  and leaves the session usable; the next statement opens a new connection.
- The shared `AsqueelDb` holds no connection: `execute`, `commit`,
  `rollback` and table writes on it raise `TransactionStateError`. It still
  compiles queries and reads the model.

An asqueel session is one call. It is not a PostgreSQL session: the call's
statements reach the server on the connection the session opens.

A host built on `AsqueelDbMixin` hands the main session of the call and, in
`release_databases()`, closes the calls it opened: the main session and the
named sessions of the same call; see
[configuration grammars](configuration-grammars.md).

### Close with uncommitted work

A clean close of a session with uncommitted work (a statement other than a
read: `SELECT`, `SHOW`, `EXPLAIN`, `VALUES`, a `WITH` without `INSERT`,
`UPDATE`, `DELETE` or `MERGE`, a `PRAGMA` without `=`), or with deferred
callbacks still queued, rolls back and logs a warning on the
`asqueel.application` logger:

```text
database <model>, session <name>: closed with uncommitted work, rolled back
```

A session that only read closes without the warning. A test suite turns the
warning into a failure with a logger filter:

```python
import logging


class FailOnUncommittedClose(logging.Filter):
    def filter(self, record):
        if 'closed with uncommitted work' in record.getMessage():
            raise AssertionError(record.getMessage())
        return True


logging.getLogger('asqueel.application').addFilter(FailOnUncommittedClose())
```

A close by exception rolls back without the warning.

### Calls, threads and tasks

The model and the table classes are shared; each `SessionDb` has its own
tables, adapter, compilers, environment, connections and trigger stack. The
current session of a call lives in a `ContextVar` of the `AsqueelDb`: each
`contextvars` context is a separate call, and so is each new call on a reused
worker thread once the sessions of the previous call are closed. A
`SessionDb` may move between threads of its call; concurrent use of one
`SessionDb` (a statement, a fetch, a close) raises `TransactionStateError`.

Each asyncio task needs a session of its own: a task created from a context
that holds a session shares it, and the statements of two tasks would
interleave in one transaction between their `await`s.

A session of an `AsqueelDb` subclass is an instance of a class derived from
`SessionDb` and from the subclass: it has the subclass's methods, but the
subclass's `__init__` does not run for it. Keep instance state on the shared
database and reach it as `session.shared`.

```python
def worker(shared, user):
    with shared.session(user=user) as db:
        rows = db.table('sales.customer').query().fetch()
        db.commit()
    return rows
```

### pgbouncer

pgbouncer is supported in `session` pool mode: a session keeps one server
connection from its first statement to its close. `transaction` pool mode is
not supported: it can hand each transaction a different server connection,
while two things asqueel uses live on one server connection. psycopg 3
prepares a statement on the server after it runs `prepare_threshold = 5`
times, and `cursorname` opens a server-side cursor.

### SQLite `:memory:`

A `:memory:` database is reached by one session at a time: opening a second
session while one is open raises `TransactionStateError`. The `AsqueelDb`
opens one connection and lends it to the open session; `closeConnection()`,
the close of a session and `migrate()` keep its data, `AsqueelDb.close()`
discards it. Work a session left uncommitted is rolled back when the
connection is lent again.

An `AsqueelDb` whose recipe declares no package executes statements with the
same explicit completion rules. There is no second transaction API. See [direct execution](low-level-runtime.md)
and [write hooks](hooks.md).

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
