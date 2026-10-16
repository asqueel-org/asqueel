# Add recordToUpdate: hooked update/delete of exactly one record selected by a where and read with a lock

## What is missing
A project cannot update or delete, through the write hooks, the one record selected by a `where`. There is no `recordToUpdate`, so no command reads the record with a lock, fails with RecordNotFoundError / RecordMultipleRowsError when the selection is not exactly one row, and only then runs the hooks. Today the caller must read and lock the record itself and pass it to `update`/`delete`.

## Evidence
- xfail tests: `tests/application_integration/test_raw_writes.py::test_ordinary_write_by_where_needs_exactly_one_record[*]`, `tests/application_integration/test_write_hooks.py::test_exactly_one_locked_record_before_any_hook[update|delete]`
- `src/asqueel/db_write.py:35-50`: `update` takes the record and `old_record` from the caller; no read, no lock.

## References
- Legacy: `recordToUpdate` / `RecordUpdater` in GenroPy `gnrsqltable`.
- `update` follows the legacy (no re-read, `old_record` from the caller); `recordToUpdate` is the standard way to read with a lock and update.
