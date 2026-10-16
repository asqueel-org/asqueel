# _key_where overwrites a record key named __pkey__N without error

## What fails
`_key_where` writes `__pkey__N` into the record parameters without a collision check. A record with a key `__pkey__0` is overwritten silently and the statement uses the wrong value. `_selection_where` has the check.

## Evidence
- No test.
- `src/asqueel/write_compiler.py` (`_key_where`; compare `_selection_where`)
