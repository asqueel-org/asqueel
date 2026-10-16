# auto_counter: execute the row counter on insert

## What is missing
The `auto_counter` option declares `onInserting='setRowCounter'` only as data; `trigger_setRowCounter` does not exist, and `trigger_assignCounters` / `trigger_releaseCounters` are empty. `require_write_capabilities` refuses every table with an enabled option, so a table with `auto_counter` cannot be written.

## Evidence
- `src/asqueel/model_expansion.py:201-212`, `src/asqueel/db_write.py` (`trigger_assignCounters` call), `src/asqueel/model_source.py:242-243`

## References
- Legacy: `TableBase.trigger_setRowCounter`; legacy defect genropy/genropy#1693.
