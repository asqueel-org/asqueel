# Cached fetch

A cached fetch materializes the rows of a query in the database under a name
`owner:name`. Pages of those rows are read later by start and count, sorted
and searched in the database, and dropped by owner. The Python process never
reads the rows to build it. It is available on PostgreSQL and SQLite; MySQL
and SQL Server raise `UnsupportedFeatureError` on every cached-fetch call.

## Enable it

The cached fetch is a db-level option:

```python
db.options().cachedFetch()
```

With it the model includes schema `_asql_` and its catalog table
`_asql_cached_fetch`, which `migrate()` creates. On SQLite the schema is the
attached file `_asql_.db`, like any other schema. Without the option every
cached-fetch call raises `UnsupportedFeatureError`. `cachedFetch()` at any
other level raises.

## Create a cached fetch

`fetch(destination_name='owner:name')` runs the query as
`CREATE TABLE ... AS SELECT` (an unlogged table on PostgreSQL) and returns the
number of rows:

```python
customers = db.table("sales.customer")
count = customers.query(
    columns="$id, $name, $city", where="$active IS TRUE", order_by="$name",
).fetch(destination_name="page42:customers")
```

- The name splits at the first `:`. An owner and a name are both required. An
  owner may not contain `,`, `(`, `)`, start with `!` nor start or end with a space.
- A fetch on an existing `owner:name` replaces it.
- `destination=` and `destination_name=` together raise; `format=` with
  `destination_name=` raises.
- The result lives in schema `_asql_` as table `p<owner>_<name>`. Characters
  other than letters, digits and `_` become `_`; beyond 63 bytes the name part
  becomes the first 12 hex characters of its SHA-256. Two names that give the
  same table raise.
- The work runs on the separate session `'_asql_cached_fetch'`, on the target
  of the caller's session, and is committed there. The caller's session is
  never committed. On SQLite `:memory:` the separate session cannot open, and
  the fetch raises; the shared `AsqueelDb`, which has no `currentEnv` of a
  call, raises too.
- The separate session sees only committed data: rows the caller wrote and
  has not committed yet are not in the result.
- A second fetch of the same `owner:name` from another process waits for the
  first and then replaces it.
- On SQLite the fetch holds the database's write lock until its commit: a long
  fetch makes the other writers wait, up to their busy timeout.

Every row gets a zero-based `_rowidx`. The numbering follows the query
`order_by`, or the table default `order_by`, then the primary key. With
`group_by` it follows `order_by`, then the `group_by` columns, then the other
output columns; with `distinct`, `order_by` then the output columns. The same
query on the same data gives the same numbering.

## Read pages

`table.cached('owner:name')` returns the cached fetch of that table; it raises
when the name does not exist or was created from another table.
`query(...)` builds a page and `fetch()` returns its rows:

```python
cached = customers.cached("page42:customers")
first = cached.query(columns="id, name", start=0, count=30).fetch()
lyon = cached.query(where="city = :city", city="Lyon", order_by="name", count=30).fetch()
```

- `columns`, `where` and `order_by` are plain SQL over the result columns:
  names without `$`, no relations.
- `columns='*'` is the result columns, `_rowidx` included.
- `start` is zero-based; `count`, a positive integer, is the maximum number of
  rows, fewer at the end. Without `count` the page runs to the end.
- A page of a cached fetch removed or replaced after `cached()` raises: call
  `cached()` again.
- Without `where` and `order_by` a page is a range of the current numbering.
  With them it is `ORDER BY ... LIMIT ... OFFSET`.
- `limit=` and `offset=` raise: use `start=` and `count=`.

Any process reads the cached fetch by its name: the catalog and the tables are
in the database.

## Sort

`sort()` orders the pages without touching the result table:

```python
cached.sort("city desc, name")
cached.sort(None)  # back to the original order
```

The sort table `s<owner>_<name>` holds `(_sortidx, _rowidx)`, with ties
ordered by `_rowidx`. A new sort replaces it; `sort(None)` drops it. A sort
keeps the active search.

## Search

`search(seed)` keeps only the rows whose text columns hold every token of the
seed, and returns the new total:

```python
total = cached.search("lyon mart")
total = cached.search(None)  # every row again
```

- The text columns are joined by a space; the seed is split on whitespace and
  every token must match.
- The match is case-insensitive (`ILIKE` on PostgreSQL, `LIKE` on SQLite);
  `%` and `_` in the seed are literal.
- The matching rows are renumbered from 0 and keep the active sort.
- `search(None)` clears the filter and returns the unfiltered total.

## Clean up

`cleanupCachedTable(owner=...)` drops result tables, sort tables and catalog
rows together:

```python
db.cleanupCachedTable(owner="page42")
db.cleanupCachedTable(owner="page42,page43")
db.cleanupCachedTable(owner="!(page42,page43)")  # every owner except these
```

A missing or empty owner, `'!()'`, and `!` or parentheses outside the
`!(...)` form raise. The cleanup runs on the separate session and is
committed there.
