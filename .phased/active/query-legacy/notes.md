
## Phase 1
- Cursors: `Database.cursor(query, cursorname=None)` runs through `_execute_on_connection`, so it shares the transaction state; the adapters gained `open_cursor` (PostgreSQL: psycopg named cursor when `cursorname` is given; SQLite ignores it and keeps `_begin` for `for_update`).
- `servercursor()` names its cursor `asqueel_<uuid>`; legacy passes `'*'` to its own generator of names.
- `iterfetch`/`serverfetch` yield NamedList chunks and stop at the first empty chunk (the contract expects `[2, 1]`; legacy also yields a trailing empty list). `cursor()`/`servercursor()` return the driver cursor with driver rows.
- `fetchAsBag` sorts by the key only; legacy `sorted()` on `(key, None, dict)` tuples gives the same order and fails on duplicate keys.
- The delete reread keeps the options of the removed `record()` (all physical columns, `exclude_draft=False`, `exclude_logical_deleted=False`, `ignore_partition=True`, `bagFields=True`) so its missing-row behaviour is unchanged.
- Stopped on a plan-defect claim about `fetchGrouped(ordered=True)`: see the phase Issue.
## Phase 1
- Plan-defect claim confirmed by the foreman: the contract test assumed `fetchGrouped(ordered=True)` sorts the keys; legacy keeps the fetch order. Line 84 corrected to `['y', 'x']` in both copies (run stopped on the user's answer, repair launched by the relaunch).
