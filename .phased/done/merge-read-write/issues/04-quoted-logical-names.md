# Quoted logical names $"..." are not supported

## What fails
- The read compiler does not accept quoted logical names `$"..."` in wildcards, predicates and RETURNING.
- DML binds a logical name that is not an identifier to a truncated parameter.
- A missing binding becomes None instead of an error.

## Evidence
- xfail tests: `tests/native_compiler/test_compiler.py::test_quoted_logical_names_work_in_wildcards_predicates_and_returning[*]`
- `src/asqueel/compiler.py:28`, `src/asqueel/drivers/sql.py:13,104-105`
