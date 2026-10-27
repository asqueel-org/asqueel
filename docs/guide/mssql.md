# SQL Server

SQL Server support is experimental. It uses the same `AsqueelDb`, `SessionDb`,
table commands and migrations as SQLite and PostgreSQL, with the limits listed
below. Its tests are not part of the automatic test run; they run on demand.

## Requirements

- SQL Server 2017 or later (formulas use `CONCAT_WS`); tested on SQL Server 2022.
- The pymssql driver: `pip install 'asqueel[mssql]'`.

pymssql opens every connection with `QUOTED_IDENTIFIER ON`: identifiers are
double-quoted, as in the SQL the compilers write. `ILIKE` runs as `LIKE`, whose
case sensitivity follows the column collation. `IS TRUE` / `IS FALSE` on a
`bit` column runs as a comparison with 1 / 0. `LIMIT` and `OFFSET` become
`TOP (n)` or `OFFSET ... FETCH`.

## Configuration

```python
from asqueel import SqlDatabaseConfig

class Recipe(SqlDatabaseConfig):
    def main(self, root):
        db = root.db('example', implementation='mssql')
        db.connection('main', database='example', host='127.0.0.1', port=1433,
                      user='app', password='secret')
        columns = db.packages().package('app', sqlschema='app', sqlprefix=False).tables().table('item', pkey='id').columns()
        columns.column('id', dtype='I')
        columns.column('name', dtype='T')
```

SQL Server takes connection fields; a `dsn` or conninfo string is refused.
`foreignKeys` is a SQLite option and is refused.

## What SQL Server refuses

Each item raises `UnsupportedFeatureError`.

- Writes whose values the database decides: an insert on a table with a
  `serial` key or a database default left empty, and an insert or update on a
  table with a `sql_value` or generated column. The write compiler writes
  `RETURNING`, which T-SQL does not have, so those values could not be read
  back. Give the key from the application.
- `||` concatenation, in a formula or in the `__record_pointer` column. Use
  `CONCAT(...)` in formulas.
- `~*` and `REGEXP` regular expressions.
- `lock_table` (T-SQL has no `LOCK`) and `vacuum()`.
- UPDATE and DELETE of a query selection: they use a row-value `IN`, which
  T-SQL does not have.
- `for_update` with a mode (`'nowait'`, ...); `for_update=True` adds
  `WITH (UPDLOCK, ROWLOCK)`.
- Deferred constraints.
- Ordered join aggregates, `to_json` subqueries, `to_xml`, `subQueryColumn`
  modes and `bagItemColumn` XPath extraction.
- Text outside a binding that pymssql would read as a binding
  (`%(name)s`, `%(name)d`): pymssql has no escape for it. Any other `%` is
  written as is.

`analyze()` runs `EXEC sp_updatestats` in the current transaction.

## Running the tests

The tests in `tests/adapter_mssql` need a reachable SQL Server:

```bash
pip install -e '.[dev,mssql]'
GNR_TEST_MSSQL_PORT=1433 GNR_TEST_MSSQL_PASSWORD=secret python -m pytest --no-cov tests/adapter_mssql
```

`GNR_TEST_MSSQL_HOST`, `GNR_TEST_MSSQL_PORT`, `GNR_TEST_MSSQL_USER` and
`GNR_TEST_MSSQL_PASSWORD` select the server; without a password or a server
the tests are skipped.
