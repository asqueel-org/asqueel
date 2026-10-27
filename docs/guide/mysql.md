# MySQL

MySQL support is experimental. It uses the same `AsqueelDb`, `SessionDb`, table
commands and migrations as SQLite and PostgreSQL, with the limits listed below.
Its tests are not part of the automatic test run; they run on demand.

## Requirements

- MySQL 8.0.19 or later.
- The PyMySQL driver: `pip install 'asqueel[mysql]'`.

Every connection adds `ANSI_QUOTES`, `PIPES_AS_CONCAT` and
`NO_BACKSLASH_ESCAPES` to the session `sql_mode`: identifiers are
double-quoted, `||` concatenates and string literals follow the standard rule.
A SQL schema is a MySQL database on the same server.

## Configuration

```python
from asqueel import SqlDatabaseConfig

class Recipe(SqlDatabaseConfig):
    def main(self, root):
        db = root.db('example', implementation='mysql')
        db.connection('main', database='example', host='127.0.0.1', port=3306,
                      user='app', password='secret')
        columns = db.packages().package('app', sqlschema='app', sqlprefix=False).tables().table('item', pkey='id').columns()
        columns.column('id', dtype='I')
        columns.column('name', dtype='T')
```

MySQL takes connection fields; a `dsn` or conninfo string is refused.
`foreignKeys` is a SQLite option and is refused. `connection.options().driver(...)`
accepts only SQLite and PostgreSQL option names.

## What MySQL refuses

Each item raises `UnsupportedFeatureError`.

- Writes whose values the database decides: an insert on a table with a
  `serial` key or a database default left empty, and an insert or update of a
  `sql_value` or generated column. MySQL has no `RETURNING`, so those values
  could not be read back. Give the key from the application.
- `lock_table`: `LOCK TABLES` commits the open transaction.
- `analyze()`: `ANALYZE TABLE` commits the open transaction.
- Deferred constraints.
- Join aggregates (`GROUP_CONCAT` takes only a literal separator), `to_json`
  subqueries (`JSON_ARRAYAGG` does not keep the row order), `to_xml`,
  `subQueryColumn` modes, `bagItemColumn` XPath extraction and `ageAtDate`.

UPDATE and DELETE of a query selection (`query(...).sql_update(...)`,
`sql_delete()`) are not available: MySQL rejects a subquery on the table being
changed (error 1093), and the statement fails with that error.

`vacuum()` runs `OPTIMIZE TABLE` on a separate connection.

## Running the tests

The tests in `tests/mysql` need a reachable MySQL server:

```bash
pip install -e '.[dev,mysql]'
GNR_TEST_MYSQL_PORT=3306 GNR_TEST_MYSQL_PASSWORD=secret python -m pytest --no-cov tests/mysql
```

`GNR_TEST_MYSQL_HOST`, `GNR_TEST_MYSQL_PORT`, `GNR_TEST_MYSQL_USER` and
`GNR_TEST_MYSQL_PASSWORD` select the server; without one the tests are skipped.
