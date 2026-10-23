# Work with a current environment

An environment is a scoped mapping of application context: current organization,
request language or a value used by several query predicates. `AsqueelDb`
owns the environment; its compiler and its named connections read it.
Changing `connectionName` selects a separate connection lazily; other context
changes do not select a different database. Store selection and tenant routing
are separate application/database concerns.

## Set context for an operation

With the [tutorial](tutorial.md) database:

```python
query = db.table("sales.customer").query(
    columns="$id, $name", where="$id=:env_customer_id",
)
with db.tempEnv(customer_id=1):
    rows = query.fetch()
    assert rows[0]["name"] == "Ada"
    db.rollback()  # Finish this read-only transaction.
```

The parameter `:env_customer_id` uses the environment key `customer_id`. The query
was constructed before entering the scope, but compiles inside it at `.fetch()`.
`currentEnv` exposes the live mutable mapping; `db.environment_snapshot()`
returns a detached copy.

For defaults, supply a mapping when building your database:

```python
from asqueel import AsqueelDb

# Shop is the application recipe from the tutorial.
configured_db = AsqueelDb(Shop, environment={"language": "en"})
try:
    assert configured_db.currentEnv["language"] == "en"
    with configured_db.tempEnv(language="it", organization=10):
        assert configured_db.currentEnv["language"] == "it"
        with configured_db.tempEnv(organization=20):
            assert configured_db.currentEnv["organization"] == 20
        assert configured_db.currentEnv["organization"] == 10
    assert configured_db.currentEnv["language"] == "en"
    assert "organization" not in configured_db.currentEnv
finally:
    configured_db.closeConnection()

```

Application scopes follow legacy `tempEnv`: keys that existed on entry are
restored on exit, including on exception. A newly introduced key is removed if
its value is still equal to the supplied temporary value; if replaced with a
different value, it remains. Changes to unrelated keys remain as well. Temporary
values are not deep-copied. These details matter for mutable context and pending
application state.

`None` is a value, not removal of a key; for a partition, `current_<path>=None`
filters nothing, like absence. Use `del db.currentEnv['key']`
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
with db.tempEnv(minimum_total=100):
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
`env_` prefix activates that convention. Missing values are bound as `None` (SQL NULL). Context values are bound data, never SQL fragments. The same lookup
works in projections, formulas, ordering and write predicates.

Overriding a placeholder does not change the environment or bypass a separate
partition policy. Policies read their declared context keys independently.

## Live context and detached snapshots

Use `db.currentEnv` when deliberately changing application context, and
`db.environment_snapshot()` for a detached snapshot with a read-only outer
mapping. The snapshot also resolves the workdate/locale defaults for
compilation. Snapshot nested values are copied.

Custom values used in snapshots must support `deepcopy`. The mutable application
mapping and its temporary scopes belong to the calling thread. Each thread gets
its own mapping; do not pass that mutable mapping to another thread or async task.

## Reuse a query in another environment

```python
query = db.table("sales.customer").query(
    columns="$id, $name", where="$id=:env_customer_id",
)
with db.tempEnv(customer_id=1):
    first = query.fetch()   # compiles once, reads customer_id=1
with db.tempEnv(customer_id=2):
    second = query.fetch()  # same SQL text, reads customer_id=2
db.rollback()
```

As in legacy, a query compiles once, on first use, and keeps its compiled form
(A2.19): `query.compiled`, `query.sqltext` and `query.sqlparams` always return the
same compilation. The `:env_*` parameters are not frozen in it: every execution
reads them again from the current environment, also for a saved `CompiledQuery`
passed to `db.execute`. What the environment changes in the SQL text itself
(partition guards, `#PERIOD` dates) stays the one of the first compilation:
build a new query in the new scope to change it.

Explicit parameter values (`env_customer_id=5` passed to the query) are caller
inputs: they are not read from the environment.

`ignore_partition=True` removes partition dependencies but does not remove any
other `:env_*` dependency. Direct psycopg execution does not perform Asqueel's
environment checks.

## Combine context scopes with one transaction

For `app.document` from the [row-policy guide](row-policies.md):

```python
try:
    with db.tempEnv(organization=10):
        db.table("app.document").insert({"id": 100, "title": "First organization"})
    with db.tempEnv(organization=20):
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

## Compile without a database

`QueryCompiler(model, adapter, environment={...})` compiles against a plain
mapping of defaults. Execution needs an `AsqueelDb`: its compiler reads the
database's own `currentEnv`.

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

This is an application pattern. Outside a request,
[`session(db, **env)`](transactions.md#sessions) gives the same boundary: entry
clears the context and applies the values, exit calls `closeConnection()`. A
nested helper belonging to the same request should reuse its initialized
context, not clear it again. A request instance is owned by one synchronous
worker; async task isolation is not supplied by this pattern.
`closeConnection()` permits subsequent requests to reuse the DB.
`clearCurrentEnv()` alone does not roll back work; it drops the pending
deferred callbacks, which live in `currentEnv`.
