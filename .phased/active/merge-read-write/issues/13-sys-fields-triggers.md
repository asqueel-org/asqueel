# sys_fields: execute the field triggers on write

## What is missing
The `sys_fields` option declares its columns (`__ins_ts`, `__mod_ts`, `__ins_user`, ...) with the legacy triggers only as data (`setTSNow`, `setCurrentUser`). `trigger_setTSNow` and `trigger_setCurrentUser` do not exist, and `require_write_capabilities` refuses every table with an enabled option. A table with `sys_fields` cannot be written.

## Evidence
- `src/asqueel/model_expansion.py:113-141`, `src/asqueel/model_source.py:242-243`

## References
- Legacy: `gnrdbo.sysFields`, `TableBase.trigger_setTSNow`, `trigger_setCurrentUser` (user from the environment `user`).
