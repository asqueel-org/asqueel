# Using an SQL environment

`SqlEnvironment` supplies scoped values to query parameters and
[row policies](row-policies.md). A compiler takes one detached snapshot when it
builds a query plan. The database checks the query's recorded dependencies before
executing it, preventing accidental reuse under a different scope.

The database API is synchronous. Environment scopes do not start transactions,
open connections, or select another database.

## Application environment

An application `SqlDatabase` already shares one environment with its compiler
and session:

```python
# db comes from build_database(YourRecipe).
query = db.table('sales.customer').query(where='$id=:env_customer_id')
with db.temp_env(customer_id=1):
    with db.transaction():
        rows = query.fetch()
```

The terminal call uses the current environment even when the query was created
earlier. Inspecting `query.compiled` or `query.sqltext` does not freeze subsequent
fetches. A saved compiled statement still carries the dependency checks described
below.

## Create and share an environment with low-level components

```python
from genro_sql import PostgresCompiler, PostgresDatabase, SqlEnvironment

env = SqlEnvironment({'language': 'en'})
# `model` is a resolved model from builder declarations or database inspection.
compiler = PostgresCompiler(model, environment=env)
db = PostgresDatabase('dbname=myapp user=myapp', environment=env)
```

Use the same instance for compilation and execution. Creating a compiler and a
database without `environment=` gives each its own environment, so values added
to one are not automatically visible to the other.

For a complete model and executable query, start with the
[quickstart](quickstart.md) or [query guide](queries.md).

## Temporary scopes

```python
assert env.current_env['language'] == 'en'

with env.temp_env(language='it', organization=10):
    assert env.current_env['language'] == 'it'
    assert env.current_env['organization'] == 10

    with env.temp_env(organization=20):
        assert env.current_env['organization'] == 20

    assert env.current_env['organization'] == 10

assert env.current_env['language'] == 'en'
assert 'organization' not in env.current_env
```

Each scope overlays the current values and restores the previous scope on exit,
including when an exception is raised. `None` is a value, not a request to remove
a key. This matters for partitions: `organization=None` selects a NULL partition;
it does not mean that the current organization is absent.

`db.temp_env(...)` and `db.current_env` delegate to the database's environment.
The compatibility spellings `tempEnv(...)` and `currentEnv` are also available
on both the environment and database.

```python
with db.temp_env(organization=10):
    assert compiler.environment.current_env['organization'] == 10
```

This works because `compiler` and `db` share `env`. An environment scope itself
is not a database transaction. See [transactions](transactions.md) when several
statements need one commit or rollback boundary.

## Read snapshots instead of mutating context

`current_env` and `snapshot()` return detached snapshots with read-only outer
mappings. Defaults and temporary values are copied when they enter the
environment. Values must support Python's `deepcopy` protocol.

```python
source = [10, 20]
scoped = SqlEnvironment({'allowed_organizations': source})
source.append(30)
assert scoped.current_env['allowed_organizations'] == [10, 20]

snapshot = scoped.snapshot()
snapshot['allowed_organizations'].append(40)
assert scoped.current_env['allowed_organizations'] == [10, 20]
```

Nested values in a returned snapshot may be mutable, but changing them does not
change the environment. To alter context, enter another `temp_env` scope. The
API has no key-removal operation; choose defaults so that a value intended to be
absent in some scopes is not always installed at the outer level.

## Environment-backed parameters

A missing query parameter whose name begins with `env_` is looked up in the
environment after removing that prefix. An explicitly supplied parameter takes
precedence.

With the model from the [query guide](queries.md):

```python
with env.temp_env(minimum_total=100):
    query = compiler.select(
        'sales.invoice', '$id, $total',
        where='$total >= :env_minimum_total',
    )
    assert query.params['env_minimum_total'] == 100

    explicit = compiler.select(
        'sales.invoice', '$id, $total',
        where='$total >= :env_minimum_total',
        params={'env_minimum_total': 250},
    )
    assert explicit.params['env_minimum_total'] == 250
```

The environment key is `minimum_total`, not `env_minimum_total`. A missing
parameter without the `env_` prefix does not fall back to the environment.
If neither an explicit parameter nor the corresponding environment value
exists, compilation raises `ValueError`.

The same resolution applies where expressions use named parameters in
projections, ordering, formulas, and update/delete predicates. Environment
values are bound as data; they are never inserted as SQL fragments. Parameter
values still need to be acceptable for their database expressions.

An explicit `params` override affects that placeholder only. It does not change
the environment or override a partition policy that separately reads an
environment key.

## Reuse compiled queries in compatible scopes

Only environment keys actually used by a query are recorded. Partition
policies also record the relevant keys that were absent, because adding one
can change which rows should be visible.

For example, with an organization partition that names both `organization`
and `allowed_organizations`:

```python
# This example uses the policy model from row-policies.md.
with env.temp_env(organization=10):
    query = compiler.select('app.document', '$id, $title')
    rows = db.execute(query).rows

# Entering organization=20 and executing the previous `query` would raise
# EnvironmentMismatchError. Compile a new query inside the new scope instead.
with env.temp_env(organization=20):
    new_query = compiler.select('app.document', '$id, $title')
    rows = db.execute(new_query).rows
```

Changing a recorded value, removing a recorded present key, or introducing a
previously absent recorded key raises `EnvironmentMismatchError` at execution.
Adding an unrelated environment key does not invalidate the query. Returning
to the same relevant values and key presence allows reuse.

A placeholder resolved entirely from explicit `params` does not by itself
create an environment dependency. Likewise, `ignore_partition=True` removes
partition dependencies, although other `:env_*` parameters can still bind the
query to its environment.

Compilation captures values; it does not defer parameter lookup until execution.
There is no automatic rebinding or recompilation when a scope changes. Keep
compilation near execution when working with request-specific values.

These checks happen through `Database`/`PostgresDatabase` and their transaction
objects. Executing `query.sql` directly through psycopg does not perform an
environment compatibility check.

## Environment scopes and transactions

Share the environment and compile each operation under its intended scope:

```python
# Uses the policy model from row-policies.md and an existing app.document table.
with db.transaction() as tx:
    with env.temp_env(organization=10):
        tx.execute(compiler.insert(
            'app.document', {'id': 100, 'title': 'First organization'},
        ))
    with env.temp_env(organization=20):
        tx.execute(compiler.insert(
            'app.document', {'id': 101, 'title': 'Second organization'},
        ))
```

The scopes control query compilation and validation while both operations use
the same database transaction. They do not switch the connection or provide
tenant/store routing. Use `tx.execute()` inside an active transaction rather
than `db.execute()`.

Database and transaction objects are owned by the thread that created the
database. Environment values are context-local, but that does not make these
objects shareable across threads. Close a database with its context manager or
`db.close()` when finished; detailed lifecycle rules are in
[transactions](transactions.md).
