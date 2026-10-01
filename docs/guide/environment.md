# Work with a current environment

An environment is a scoped mapping of application context: current organization,
request language or a value used by several query predicates. `SqlDatabase`
shares an application environment between its compiler and named connections.
Changing `connectionName` selects a separate connection lazily; other context
changes do not select a different database. Store selection and tenant routing
are separate application/database concerns.

## Set context for an operation

With the [tutorial](tutorial.md) database:

```python
query = db.table("sales.customer").query(
    columns="$id, $name", where="$id=:env_customer_id",
)
with db.temp_env(customer_id=1):
    rows = query.fetch()
    assert rows[0]["name"] == "Ada"
    db.rollback()  # Finish this read-only transaction.
```

The parameter `:env_customer_id` uses the environment key `customer_id`. The query
was constructed before entering the scope, but compiles inside it at `.fetch()`.
`tempEnv` is the legacy spelling of `temp_env`. `currentEnv` exposes the live
mutable mapping; `current_env` returns a detached snapshot.

For defaults, supply an environment when building your database:

```python
from asqueel import SqlEnvironment, AsqueelDb

# Shop is the application recipe from the tutorial.
configured_db = AsqueelDb(Shop, environment=SqlEnvironment({"language": "en"}))
try:
    assert configured_db.current_env["language"] == "en"
    with configured_db.temp_env(language="it", organization=10):
        assert configured_db.current_env["language"] == "it"
        with configured_db.temp_env(organization=20):
            assert configured_db.current_env["organization"] == 20
        assert configured_db.current_env["organization"] == 10
    assert configured_db.current_env["language"] == "en"
    assert "organization" not in configured_db.current_env
finally:
    configured_db.close()

```

Application scopes follow legacy `tempEnv`: keys that existed on entry are
restored on exit, including on exception. A newly introduced key is removed if
its value is still equal to the supplied temporary value; if replaced with a
different value, it remains. Changes to unrelated keys remain as well. Temporary
values are not deep-copied. These details matter for mutable context and pending
application state.

`None` is a value, not removal of a key. For a partition, `organization=None`
means the NULL partition; absence is different. Use `del db.currentEnv['key']`
or `.pop()` to remove a key. `db.updateEnv(...)` updates values; with
`_excludeNoneValues=True` it skips only None, preserving 0 and False.
`db.currentEnv = mapping` replaces the live dictionary, retaining its identity;
`db.clearCurrentEnv()` replaces it with an empty dictionary. Neither operation
commits or closes named connections.

`db.workdate` defaults to today's local date, evaluated when read. `db.locale`
uses a truthy explicit value, otherwise `GNR_LOCALE` when that variable exists,
otherwise Python's `locale.getlocale()[0]`. An empty default becomes `en_GB`;
in particular, `GNR_LOCALE=""` selects `en_GB`, not the system locale.
Both properties can be set explicitly. A false-valued override (`None`, `""`,
`False` or `0`) selects the fallback. Values are not coerced or validated:
there is no locale catalogue or Babel dependency. Unlike legacy's default-locale
validation, an unknown nonempty identifier is preserved. These properties do
not change the process locale, database collation or date formatting. Application
compiler snapshots resolve these defaults for `:env_workdate` and `:env_locale`.
Localization services belong to the application-linked layer; business-date
and locale context are available to queries without requiring a web page.

Defaults do not populate `currentEnv`. `tempEnv` restores overridden values,
including after exceptions, using the scope rules above. Each thread owns its
values. Compiled environment bindings capture the effective date/locale and
reject execution when those values change, including a default date crossing
midnight. Explicit query parameters take precedence over environment values.

## Bind explicit values or fall back to context

Explicit parameters take precedence over environment lookup:

```python
with db.temp_env(minimum_total=100):
    query = db.table("sales.invoice").query(
        columns="$id, $total", where="$total >= :env_minimum_total",
    )
    assert query.compiled.params["env_minimum_total"] == 100
    explicit = db.table("sales.invoice").query(
        columns="$id, $total", where="$total >= :env_minimum_total",
        env_minimum_total=250,
    )
    assert explicit.compiled.params["env_minimum_total"] == 250
```

A normal `:minimum_total` parameter does not fall back to the environment; the
`env_` prefix activates that convention. Missing values raise `ValueError` during
compilation. Context values are bound data, never SQL fragments. The same lookup
works in projections, formulas, ordering and write predicates.

Overriding a placeholder does not change the environment or bypass a separate
partition policy. Policies read their declared context keys independently.

## Live context and detached snapshots

Use `db.currentEnv` when deliberately changing application context, and
`db.current_env` for a detached snapshot with a read-only outer mapping.
`db.environment.snapshot()` additionally resolves workdate/locale defaults for
compilation. Snapshot nested values are copied.

The standalone `SqlEnvironment` remains a separate low-level API with copied,
context-local scopes, useful when constructing compiler/executor components
independently:

```python
from asqueel import SqlEnvironment

source = [10, 20]
environment = SqlEnvironment({"allowed_organizations": source})
source.append(30)
snapshot = environment.snapshot()
snapshot["allowed_organizations"].append(40)
assert environment.current_env["allowed_organizations"] == [10, 20]
```

Custom values used in snapshots must support `deepcopy`. The mutable application
mapping and its temporary scopes belong to the calling thread. Each thread gets
its own mapping; do not pass that mutable mapping to another thread or async task.

## Distinguish a lazy query from a compiled statement

```python
from asqueel import EnvironmentMismatchError

query = db.table("sales.customer").query(
    columns="$id, $name", where="$id=:env_customer_id",
)
with db.temp_env(customer_id=1):
    compiled = query.compiled

with db.temp_env(customer_id=2):
    try:
        db.execute(compiled)
    except EnvironmentMismatchError:
        pass  # Rejected before execution: it captured customer_id=1.
    try:
        rows = query.fetch()  # Fresh compilation now uses customer_id=2.
        db.commit()
    except Exception:
        db.rollback()
        raise

```

Compilation captures values; a saved `CompiledQuery` does not automatically
rebind. By contrast, every terminal call on `SqlQuery` recompiles. Inspecting
`query.sqltext` or `query.compiled` does not change the behavior of its next fetch.

Only relevant context keys are recorded. Unrelated keys do not invalidate a
statement. Partition guards record relevant absent keys too: adding an allowed
set can change the intended restriction. Returning to the same values and key
presence permits reuse. Explicit parameter values do not by themselves create
environment dependencies.

`ignore_partition=True` removes partition dependencies but does not remove any
other `:env_*` dependency. Direct psycopg execution does not perform Asqueel's
environment checks.

## Combine context scopes with one transaction

For `app.document` from the [row-policy guide](row-policies.md):

```python
try:
    with db.temp_env(organization=10):
        db.table("app.document").insert({"id": 100, "title": "First organization"})
    with db.temp_env(organization=20):
        db.table("app.document").insert({"id": 101, "title": "Second organization"})
    db.commit()
except Exception:
    db.rollback()
    raise

```

Both operations share one transaction. Their partition columns are filled using
their respective current organization. Switching context does not switch databases.
The model graph is shared; mutable application environments and named connections
are isolated per thread. Concurrent async tasks within one thread are unsupported.

## Advanced: share context between independent components

When constructing a compiler and low-level executor yourself, supply the same
instance to both:

```python
from asqueel import PostgresCompiler, PostgresDatabase, SqlEnvironment

# model is a resolved model; no database connection is needed for compilation.
environment = SqlEnvironment()
compiler = PostgresCompiler(model, environment=environment)
with PostgresDatabase("dbname=example", environment=environment) as executor:
    with environment.temp_env(customer_id=1):
        compiled = compiler.select("sales.customer", where="$id=:env_customer_id")
        rows = executor.execute(compiled).rows
```

Independent default environments do not share values. The low-level executor's
transaction behavior differs from `SqlDatabase`; see [low-level execution](low-level-runtime.md).

## Application-owned request boundary

A web request, network handler or job instance can expose a `db` property which
returns a shared AsqueelDb and initializes the current worker’s context only on
first access. For example, this application class uses existing DB methods:

```python
class Request:
    def __init__(self, shared_db, user, workdate, locale):
        self.shared_db = shared_db
        self.values = dict(user=user, workdate=workdate, locale=locale)
        self._db = None

    @property
    def db(self):
        if self._db is None:
            self._db = self.shared_db
            self._db.clearCurrentEnv()
            self._db.updateEnv(**self.values)
        return self._db

    def cleanup(self):
        try:
            self.shared_db.closeConnection()
        finally:
            self.shared_db.clearCurrentEnv()
```

The request dispatcher must call cleanup on success and failure, before reusing
that worker for another request. Business code commits explicitly; cleanup rolls
back pending work and releases all named connections in that thread. It does not
undo a successful commit. Preserve the original application exception if cleanup
also fails. Repeated `request.db` access does not reset context during the request.

This is an application pattern, not a new Asqueel request/session class. A nested
helper belonging to the same request should reuse its initialized context, not
clear it again. A request instance is owned by one synchronous worker; async
task isolation is not supplied by this pattern. `closeConnection()` permits
subsequent requests to reuse the DB; `close()` permanently closes that worker’s
DB state. `clearCurrentEnv()` alone neither rolls back work nor clears pending
connection callbacks.
