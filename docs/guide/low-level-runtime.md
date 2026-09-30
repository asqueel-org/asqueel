# Independent low-level execution

`PostgresDatabase` and `Database` remain separate lower-level executors. Their
transaction behavior differs from the application session: `db.execute()` owns
and completes a transaction for one operation. Use `tx.execute()` to join an
explicit low-level transaction. The following examples use these low-level
classes, not `SqlDatabase`.

## Execute one statement

This example needs a reachable PostgreSQL database but no application tables:

```python
from genro_sql import CompiledQuery, PostgresDatabase

with PostgresDatabase('dbname=example') as db:
    result = db.execute(CompiledQuery(
        'SELECT %(message)s AS message',
        {'message': 'Hello'},
    ))
    print(result.rows)  # [{'message': 'Hello'}]
```

`db.execute()` opens a connection, executes the statement, commits and closes
that connection before returning. Use compiler-generated queries for model-aware
field resolution and row policies. Direct `CompiledQuery` SQL is a lower-level
interface; see [adapters and binding](adapters.md).

Results are materialized: `rows` is a list of dictionaries, `rowcount` is the
driver's affected/returned row count, and `columns` contains result metadata.
There is no cursor to consume or close after `execute()` returns.

## Group operations atomically

The following function assumes an existing model and database with `customer`
and `invoice` tables, generated `id` keys, and the fields shown. Neither compiler
construction nor runtime construction creates tables.

```python
from decimal import Decimal


def create_customer_and_invoice(db, compiler, name):
    with db.transaction() as tx:
        customer = tx.execute(compiler.insert(
            'customer', {'name': name}, returning='$id',
        ))
        customer_id = customer.rows[0]['id']
        invoice = tx.execute(compiler.insert(
            'invoice',
            {'customer_id': customer_id, 'total': Decimal('25.00')},
            returning='$id',
        ))
    # Both inserts have committed before control reaches this point.
    return customer_id, invoice.rows[0]['id']
```

All `tx.execute()` calls use the same connection. Normal exit commits; an
exception leaving the block rolls back. A Python exception from your own
application code also causes rollback.

Inside the block, call `tx.execute()`, not `db.execute()`. Nested transactions
on the same database instance are rejected; there are no nested savepoints.
Transactions are single-use and cannot execute after their context has exited.

## Handle errors outside the transaction

Catch the errors your application can handle around the entire transaction:

```python
import psycopg


def try_create_customer(db, compiler, name):
    try:
        with db.transaction() as tx:
            result = tx.execute(compiler.insert(
                'customer', {'name': name}, returning='$id',
            ))
    except psycopg.errors.UniqueViolation:
        return None
    return result.rows[0]['id']
```

An execution error makes the transaction **rollback-only**. Catching that error
inside the block does not repair the transaction: further statements raise
`TransactionStateError`, and an otherwise normal exit rolls back and raises
`TransactionStateError` instead of appearing to commit successfully. Start a
new transaction to retry an operation.

Profile and environment checks occur before dispatch. A rejected query that
never reaches the driver does not, by itself, mark the transaction rollback-only.
Other executed statements still commit on normal exit.

The runtime propagates driver exceptions rather than wrapping them. A failure
during commit or rollback still attempts to close the connection. If both the
transaction operation and connection cleanup fail, the first exception is
preserved and receives a note about the cleanup failure.

## Understand the transaction outcome

`tx.outcome` describes the observed lifecycle:

| Value | Meaning |
|---|---|
| `not_started` | The connection has not been opened successfully. |
| `active` | The transaction is open. |
| `committed` | The driver's commit call completed successfully. |
| `rolled_back` | The driver's rollback call completed successfully. |
| `unknown` | Commit or rollback raised; the final server state is not confirmed. |

Do not automatically retry a write after an unknown commit outcome: it may
already have committed. Resolve that uncertainty using application-specific
identifiers or reconciliation. A connection-close error after a successful
commit leaves the outcome as `committed`.

## Keep compiler and runtime environments aligned

Pass the same `SqlEnvironment` to both components when queries use contextual
parameters or partition scopes. For an existing `customer` model:

```python
from genro_sql import EnvironmentMismatchError, PostgresCompiler
from genro_sql import PostgresDatabase, SqlEnvironment


def read_customer(model, conninfo):
    environment = SqlEnvironment()
    compiler = PostgresCompiler(model, environment=environment)
    with PostgresDatabase(conninfo, environment=environment) as db:
        with db.temp_env(customer_id=7):
            query = compiler.select('customer', where='$id = :env_customer_id')
            result = db.execute(query)
        try:
            db.execute(query)
        except EnvironmentMismatchError:
            # Compile a new query inside the intended environment scope.
            pass
    return result
```

A query bound to an environment cannot be reused after its relevant context
changes. The runtime rejects that mismatch before opening a connection, or
before executing a statement in an existing transaction. Unrelated environment
keys do not invalidate a query that does not depend on them.

## Ownership and closing

A database instance belongs to the thread that constructed it. Its database
operations, transaction operations and `close()` must run on that thread;
cross-thread use raises `TransactionStateError`. If an application uses multiple
threads, construct and close a separate database instance within each thread.

`with db:` closes the database wrapper on exit. You can also call `db.close()`
explicitly; repeated close calls are harmless. Closing while a transaction is
active raises an error: exit the transaction first. A closed database cannot be
reopened.

There is no async runtime, worker pool, persistent connection pool, streaming,
automatic retry or driver-level timeout wrapper in this API. PostgreSQL
connection options can be passed through `connect_kwargs`; `autocommit=True`
is rejected because the runtime owns transaction completion.
