# WriteCompiler does not enforce the dialect capabilities

## What fails
- `INSERT ... DEFAULT VALUES` is emitted on a dialect without `default_values`.
- On a dialect without `returning_insert`, RETURNING is dropped silently; the caller gets no returned values and no error.

## Evidence
- xfail test: `tests/adapter_dialect/test_postgres.py::test_missing_write_capabilities_are_rejected`
- `src/asqueel/write_compiler.py` (`_insert_sql`, `_returning`)
