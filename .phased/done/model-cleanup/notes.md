## Phase 1
- `compose_recipe` returns the recipe, not a handler: `SqlDatabase` now takes `recipe=` and builds `SqlConfigHandler(recipe)` itself, so the object renderer's `finalize` needs no import from configuration.py. Rejected: keeping `config=` with a handler, which forced the renderer to wrap through configuration.py. `SqlDatabase` disappears in Phase 3.
- "Already composed" is the plain attribute `SqlBuilder.composed`, set by `compose_recipe`; `render()` on an uncomposed recipe renders a composed copy, so `materialized` lands on the copy, not on the authored recipe (two tests realigned).
- `prepare_source` keeps copying the recipe: the database keeps the composed recipe in `db.config`, and preparation (conninfo pop, runtime values, option expansion) must not mutate it. The implementation is passed in by the renderer and written on the `db` node before options expand, as before.
- `_validate_source_shape` runs only in `compose_recipe` and `validate_source`, no longer in `prepare_source`.

## Phase 2
- `SqlBuilder.__init__` re-reads the payload with `self._sourceroot.get_item(SOURCE_ROOT)` after `super().__init__`: BuilderBase reads it with brackets, and `SqlSourceBag.__getitem__` returns the node. The source object is the one BuilderBase created from `_source_class`; nothing is replaced.
- The implementation check of the old `SqlDatabase.__init__` is dropped from `finalize`: model and connection come from the same composed recipe, and the model keeps the full `'name:module'` implementation while the database keeps the short name, so the comparison was wrong, not only redundant.
- `SqlDatabase` stays as a base class without constructor until Phase 3 merges it; `finalize` accepts only an `AsqueelDb` target, as the contract test requires.
- `reloadModel` renders into the database before the SQL-schema check and restores the old model (unbinding the new one) when the check fails. Phase 3 reorders this.
- Tests describing a detached model (`_operational_db is None`, 'not bound' query errors, rebinding through `SqlDatabase(model=...)`) were realigned to the bound model: the plan removes every route to a detached model. The secrets test of the model-only render was deleted with its route: `AsqueelDb` reads the connection settings at construction, as `build_database` did.
- `artifacts/test_invoice_pg/objects_tree/migration.json` and `scripts/export_invoice_tree_migration.py` were deleted: after this phase both export scripts take the same route, and the native artifact already holds the same structure. Phase 5 has one script less to move.

## Phase 3
- The environment snapshot is the method `AsqueelDb.environment_snapshot()` (legacy has none); the write and query compilers call it. `_env_values` is the thread-local mapping without the open check, used by the execution internals that ran on `self.environment.currentEnv` before.
- `QueryCompiler(model, adapter, environment=None, _db=None)`: with `_db` it snapshots the database's currentEnv, otherwise `environment` is a plain mapping of defaults.
- `AsqueelDb(environment=)` takes a mapping of defaults (was a `SqlEnvironment`); `session(db)` lost its environment-type check, the only database class has a writable environment.
- `name_long`, `name_short`, `comment` are read from the composed recipe's `db` node at construction.
- `DbModel._database` stays as a plain `DbModelObj` over the `db` fragment without its namespaces: `object_tree_projection.py` reads its `extensions` until Phase 5 deletes the projection.
- `_recipe_from_node` returns a `SqlDatabaseConfig` instance filled by `_replay_node`.
- Tests of the low-level `Database` use `tests/unit_of_work.empty_database(conninfo, implementation=, connect_kwargs=, environment=)`, an `AsqueelDb` over a recipe with only the `db` node. Rejected: keeping a model-less database class, which the plan removes.
- `reloadModel` sets `old_model.db = None` and `SqlTable.db` raises 'not bound' when its model has no database: the documented invalidation of old tables holds without `_operational_db`.
- `workdate` reads `datetime.date.today()` through the module, so a patched `datetime.date` is seen, as the lazy import of the old environment allowed.

## Phase 4
- `virtual_columns` returns the declared container itself and inserts the `formulaColumn_<x>()` objects into its children, as legacy; a table without `formulaColumn_` methods never touches `currentEnv`. `dynamic_columns` filters the container by `structnode is None` (only the dynamic objects have no source node).
- Code running during the build reads `table['virtual_columns']` (declared only): `currentEnv` raises 'not ready' before the model is bound. `RelationTreeResolver` reads it too, so the cached relation tree does not capture the dynamic objects of one environment.
- The `_virtual_columns_*` keys hold live model objects, so `environment_snapshot` skips them like the transaction keys.
- Docs (`docs/guide/legacy-features.md:226`, `docs/api.rst`) not yet updated: the phase stopped at the tempEnv failure.

## Phase 5
- `rendered_item` builds each table item locally (physical columns, constraints, explicit indexes, local auto-indexes) and keeps the relations pending; `finalize` resolves relation targets across tables, adds the FK items and the target-side indexes, validates and delivers. No walk state survives to `finalize`: the implementation travels in the schema/table fragments.
- Physical names are computed in the walk from the `db`, package/schema and table nodes; index and constraint columns naming a composite expand to its members, as `object_tree_projection._mapped` did. The refusals of partial indexes and CHECK constraints on tables with remapped columns are kept.
- `_package_storage` (legacy `convert_colattr`) moved into migration.py; it applies to package tables only, as before.
- The auto-index rule was not merged into one definition across `object_tree.py`, `object_tree_relations.py`, `model_source.py` and migration.py: the goldens and suite pass with the route-A rules over the prepared source; merging them is left for the repair or the quality check.
- Delivery: no target returns the dict; a path, a writable or a callable receives JSON text (`indent=2`, trailing newline) through `RendererBase.finalize`.
- Implied `deferred=True` for a `SET NULL` relation (`resolve_source_references`) now applies only inside a package: outside one the old direct migration route never implied it, and `test_sql_actions_reach_the_migration_foreign_key_outside_a_package` pins that. Schema-based live models lose the implied flag too; the suite and goldens stay green.

## Phase 6
- Variable names are assigned in `finalize`, walking the fragments in tree order with the same counter as `emit()` (`columns_2`, `tables_2`). Rejected: names from the node path in `rendered_item`, as the Decision suggested: they cannot reproduce the counter suffixes, and the byte-identical output is the contract.
- Each fragment carries tag, name, ordered call arguments (from `node.attr`, signature order, extras sorted) and child fragments; `finalize` writes the module and delivers it through `RendererBase.finalize` (no target returns the text).
- `get_render` returns this renderer for every node: a mounted subtree carries its own builder, whose default renderer is `objects`.
- No `SqlModelCatalog` in the renderer: the walk gives the same children in source order.

## Run inspection
- Phases 1-3 closed on their first session, each with planned batches; Phase 3 left a WIP note between batch 2 and 3 and closed in the same run.
- Phase 4 closed `[!]` with a plan-defect claim: `tempEnv` keeps the cached dynamic columns, as legacy `TempEnv`; the user accepted the realignment of `test_dynamic_formula_columns_are_evaluated_in_the_environment` (`clearCurrentEnv()` first), applied by the foreman.
- Phase 5 closed `[!]` with a plan-defect claim on three tests of the removed live-object route; the user accepted; two tests realigned to change the `db.config.builder` source; the third (`SET NULL` outside a package) passed unchanged on the committed code, so the claim's part (3) did not hold.
- Phase 6 closed `[!]` with a plan-defect claim: the empty-model refusal now comes from the composition step (`exactly one root element`); the user accepted the realignment.
- No repair session ran; no budget cap tripped.
- Focus points for the quality check: tests deleted with removed routes (Phase 2: model-only secrets test, `renderer_sql` tests; Phase 3: `tests/environment/test_environment.py`, shared-environment and `_bind_db` tests, `test_session_requires_a_writable_environment`); files deleted outside `Files:` (Phase 2: `artifacts/test_invoice_pg/objects_tree/migration.json`, `scripts/export_invoice_tree_migration.py`); `DbModel._database` still in `object_tree.py:428` after the projection removal; `AsqueelDb(environment=)` now takes a mapping; new names for the naming review (`compose_recipe`, `SqlBuilder.composed`, `environment_snapshot`, `DbTableObj.physical_columns`, the `wf:phase-` markers); `scripts/check_installed.py` not run in a core-only environment.

## Final touch
- Reviewed revision: 9373a75 (review extended, effort high, in-session over 58422af..9373a75). QA: none (the plan has no Verify steps, no verify.md). Naming: all names accepted as proposed; markers removed.
- Correction commit: 8a2effe.

| Finding (evidence) | Root cause | Fix | Verification | Road |
|---|---|---|---|---|
| SET NULL implied deferred only inside packages (`model_source.py:142`) | Phase 5 bent the rule to keep a test that pinned the old direct route; legacy applies it to every relation (`gnrsqlmodel/model.py:263-264`) | condition restored for every relation; `test_sql_actions_reach_the_migration_foreign_key_outside_a_package` expects `deferrable` and `initially_deferred` | that test, full suite, goldens | final touch |
| `reloadModel` lost the old model on a failed build | `finalize` assigns `target.model` before `build`; only the SQL-schema refusal restored the old model | `reloadModel` restores the previous model on any exception of the render or the schema check | new `tests/sqlite/test_memory_migration.py::test_a_failed_model_build_keeps_the_original_model`, full suite | final touch |
| `DbModel._database` built and never read (`object_tree.py:428`) | kept by Phase 3 for the projection Phase 5 deleted | removed with its `replace` import | full suite | final touch |
| 9 `wf:phase-N:new` markers | autonomous run | removed, names kept | `grep -rn "wf:phase-" src tests scripts` empty | final touch |
| `QueryCompiler._environment_snapshot` one-line wrapper | two environment sources on the compiler | not changed (cleanup, not a defect) | — | none |

- Checks run after the batch: full suite 5419 passed / 42 skipped / 20 xfailed; ruff clean; sphinx -E -W clean; contract-test copies byte-identical to the plan copies.
- Re-check (light, low) over the touched files: no residual finding.
- Left unverified: `scripts/check_installed.py` in an environment without asqueel-migration.
- No row on the phase road.
