# hierarchical: execute the field triggers on write and connect the macro expansion

## What is missing
- The `hierarchical` option declares `onInserting/onUpdating='hierarchical_before'` and `onUpdated='hierarchical_after'` only as data; `trigger_hierarchical_before/after` do not exist.
- `require_write_capabilities` refuses every table with an enabled option, so a hierarchical table cannot be written.
- The read compiler refuses the hierarchical macros: `Hierarchical macro expansion is not connected yet`.

## Evidence
- `src/asqueel/model_expansion.py:229-272`, `src/asqueel/compiler.py:519`, `src/asqueel/model_source.py:242-243`

## References
- Legacy: `gnrdbo.sysFields(hierarchical=...)`, `TableBase.trigger_hierarchical_before/after`.
