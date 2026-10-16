# SELECT and record() fail on a table whose pkey is a compositeColumn

## What fails
A SELECT on a table whose pkey is a compositeColumn fails with `virtual/composite columns are not connected yet`; `record(...)` on such a table fails too. A project with a composite key cannot read those records, nor read them with a lock before a write.

## Evidence
- xfail tests: `tests/application_integration/test_write_hooks.py::test_record_read_with_lock_includes_the_draft_row`, `::test_pre_hook_holds_postgres_row_lock`, `::test_logically_deleted_record_is_hidden_until_restored`, `tests/test_handles.py::test_composite_record_reads_through_the_physical_names`
- `src/asqueel/compiler.py:63-66,570-571`
