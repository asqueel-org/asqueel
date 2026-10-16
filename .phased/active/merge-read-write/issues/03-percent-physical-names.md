# A '%' in a physical table or column name is not escaped for psycopg

## What fails
On PostgreSQL a table whose physical table or column name contains `%` cannot be read or written: psycopg reads the `%` as a placeholder.

## Evidence
- xfail tests: `tests/native_compiler/test_compiler.py::test_insert_escapes_percent_in_physical_names`, `tests/test_plans.py::test_compiled_sql_escapes_percent_in_physical_names`
- `src/asqueel/drivers/sql.py:110-111`
