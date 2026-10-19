
## Phase 1
- Cursors: `Database.cursor(query, cursorname=None)` runs through `_execute_on_connection`, so it shares the transaction state; the adapters gained `open_cursor` (PostgreSQL: psycopg named cursor when `cursorname` is given; SQLite ignores it and keeps `_begin` for `for_update`).
- `servercursor()` names its cursor `asqueel_<uuid>`; legacy passes `'*'` to its own generator of names.
- `iterfetch`/`serverfetch` yield NamedList chunks and stop at the first empty chunk (the contract expects `[2, 1]`; legacy also yields a trailing empty list). `cursor()`/`servercursor()` return the driver cursor with driver rows.
- `fetchAsBag` sorts by the key only; legacy `sorted()` on `(key, None, dict)` tuples gives the same order and fails on duplicate keys.
- The delete reread keeps the options of the removed `record()` (all physical columns, `exclude_draft=False`, `exclude_logical_deleted=False`, `ignore_partition=True`, `bagFields=True`) so its missing-row behaviour is unchanged.
- Stopped on a plan-defect claim about `fetchGrouped(ordered=True)`: see the phase Issue.
## Phase 1
- Plan-defect claim confirmed by the foreman: the contract test assumed `fetchGrouped(ordered=True)` sorts the keys; legacy keeps the fetch order. Line 84 corrected to `['y', 'x']` in both copies (run stopped on the user's answer, repair launched by the relaunch).

## Phase 2
- `environment_arguments(keys, snapshot)` lives in `environment.py`: `runtime.py` must not import `adapters` (tests/adapter_integration/test_boundaries.py); `prepare_arguments` and the runtime share it.
- `CompiledQuery.environment_keys` (and `SqlCompiledQuery.environment_keys`) carries the `:env_*` keys; `_execute_on_connection` rebuilds the params with the current values before the driver call. Explicit `env_*` caller parameters are not in the keys and are never overwritten.
- `refused_property(subject)` in `contracts.py` serves both the table refusals and `db.query`/`db.whereTranslator` (on `runtime.Database`).
- Tests outside the plan's list realigned by the same rule (a reused query no longer recompiles): test_postgres_policies, test_count, test_legacy_resolution, test_minimal_select, test_phase3_formulas, test_phase4_macros, test_phase4_star_bag, native_formulas/test_method_results and test_subquery_method_results; a scope that changes the SQL text (partition guards, #PERIOD dates, method formulas) builds a new query.
- Fake adapter of tests/application_connections/test_connections.py records `executed_params` so the env-at-execution realignments can assert the values sent.

## Phase 3
- `currentEnv['_virtual_columns_<pkg>_<tbl>']` holds the attribute dicts returned by the `formulaColumn_<x>()` methods, not column objects: environment snapshots deepcopy `currentEnv`, and the model objects do not support deepcopy. `DbTableObj.dynamic_columns` builds the column objects from the cached dicts at every access.
- The compiler reaches a compositeColumn through the virtual column lookup of `get_field_alias` (declared virtual, then composite, then dynamic) and compiles it as a formula with `composite_formula`; the "compositeColumn in place of a physical column" refusal left `physical_column` because it became unreachable. `DbTableObj.column()` also falls back to the dynamic columns, so result metadata resolves their dtype.
- The 'A' default lives in `DbVirtualColumnObj.dtype` for the formulaColumn tag, so declared and dynamic formula columns share it; the signature keeps `dtype=None`.
- Realigned outside the plan's list by the same rule: examples/model_grammar/configure.py (`expression=` → `sql_formula=`), tests/object_tree/test_relation_metadata.py (a formulaColumn without dtype now publishes 'A').

## Phase 4
- `aggr` validation and expansion live in `formula_definition` (compile time): the contract tests accept the error at declaration or compilation, and the grammar keeps only the attribute. The aggregate's function (`join`/`to_json`/`to_xml`/None) is written into the local `attrs['mode']` copy so the existing `subquery(..., aggregate=)` dispatch is reused.
- `#BAG`/`#BAGCOLS` are expanded only in the top-level SELECT (`parent is None`): a child subquery has no post-fetch step, so there they reach `_check_macros` and raise. `cursor()`/`servercursor()` return driver rows unchanged; `iterfetch`/`serverfetch` apply the Bag handling.
- `#ENV` reads the compiler's environment snapshot (it includes `workdate` and `locale`); the fallback table is resolved with `_known_table`, its handler on `.dbtable`.
- The queries.md example runs against the tutorial data, which has no X column: it reads the NULL `note` of invoice 11.
- Realigned: `test_macro` and `test_unported_macros_remain_explicit` keep #PREF/#TSQUERY; #ENV/#BAG/#BAGCOLS moved to new tests asserting the ValueError.

## Run inspection
- Phase 1 closed [!] on a true plan-defect claim: the contract test expected `fetchGrouped(ordered=True)` keys sorted, legacy keeps fetch order. The run was stopped on the user's answer, the foreman fixed line 84 in both copies (044c8f0), the relaunch held again on the same `> Issue:` and the user authorized the repair, which finished batch 3 (d4ea9e4).
- Phase 1 contract test fixes a non-legacy shape: `iterfetch(arraysize=2)` expected `[2, 1]`; legacy also yields a trailing empty chunk. The contract tests do not cover `serverfetch()`, the named PostgreSQL cursor, or the datetime branch of `fetchAsJson`.
- Phase 2 realigned 9 test files beyond the plan's list by the same rule (a reused query no longer recompiles).
- Phases 2, 3, 4 closed on the first attempt. Final suite 5118 passed, 42 skipped, 27 xfailed (the four asqueel#26 xfails lifted in Phase 3).
