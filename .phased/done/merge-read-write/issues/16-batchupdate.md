# Add batchUpdate: hooked update of the records of a selection

## What is missing
There is no `batchUpdate`. A project cannot update several records through the write hooks: `query(...).sql_update(values)` runs one statement without hooks. Logical deletion of a set of records (update of `__del_ts`) has no hooked path either.

## Evidence
- `src/asqueel/application_table.py:110` (`sql_update` on a query, no hooks)

## References
- Legacy: `batchUpdate` in GenroPy `gnrsqltable`.
- Related: recordToUpdate issue; asqueel-org/asqueel#16.
