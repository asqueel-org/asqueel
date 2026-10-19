
## Phase 1

- Partition filter: legacy truthiness (`env.get(...)`), so `current_<path>=0` adds no filter; realigned tests moved partition values from 0/1 to 10/11. `current_<path>` and `allowed_<path>` both enter the plan's environment keys, so a cached plan is refused when either changes.
- `RowPolicies` keeps `draft_field` and `logical_deletion_field`; `PartitionScope` and the multi-partition `x_partitions` semantics (include_null, raise on missing context, relational partition paths) are gone with A1.4. The relational-partition read test and its strict xfail were deleted (31 strict xfails remain).
- `schema()` loses `x_sql_schema`; its physical name is `sqlname` (as `DbPackageObj.sqlschema` already read it). `package()` keeps `sqlschema`.
- `sql_<dialect>_<name>` suffixes other than `default|generatedExpression|extra` raise "Element 'column' does not accept"; `encrypted` and the `indexed`/`unique` strings are handled in the builder call, before grammar validation.
- Unknown names: `DbModel.table` returns None for a missing package; user-facing callers (`SqlDatabase.table`, subquery/virtualRelation targets, compiler context, relation targets, alias paths, policy fields) raise their own `Unknown package/schema`/`Unknown column` errors.
- Blocker: SQLite generated columns are invisible to asqueel-migration 0.2.3 (`PRAGMA table_info`); see the plan-defect claim on the phase.

## Phase 2

- Physical index name: the legacy migrator never passes `index_name` (`gnrsqlmigration/orm_extractor.py:465`), so legacy SQL index names are the migrator's hashed ones. Rule chosen in place of `x_auto_name`: an index whose name equals `default_index_name(table, columns)` (`<table>_<columns joined by _>_key`, `common.py`) gets the hashed SQL name in `migration.py` and in the object-tree projection; any other name is the SQL name. The legacy migration oracle (`tests/object_tree/test_migration.py`) stays identical.
- `x_auto_name` also left `constraint()`: nothing in src set it; the UNIQUE constraint name is always the declared one.
- `index` lost the "name is required outside a package" refusal: the legacy default name applies everywhere; `test_wf_phase12_model_boundaries.py` realigned.
- A package `relation` with `cnd` defaults `foreign_key` to False; an explicit `foreign_key=True` beside `cnd` is not refused (the plan does not say).
- `pkey='a,b'` raises only on package tables: schema-level tables read from a database (`projection.py`) carry a comma pkey.
- Blocker: the cnd contract test calls `migration_plan()` on `:memory:`, refused by design; see the plan-defect claim.

## Phase 4

- The loader runs in `configuration._owned_handler`, after layer composition and before the shape validation: the layout becomes ordinary source declarations, so every renderer sees it. `path` is popped from the package node once loaded, so a second preparation of the same source does not load the folder twice.
- `custom_type_<dtype>()` results are written as `pkg.options().type(<dtype>, **result)`: `resolve_source_types` applies them unchanged, and keys outside `type()` (`dtype`, `size`, `name_long`, `name_short`) raise as grammar errors.
- `config_attributes()` keys are set with `setdefault` on the package node: element attributes win.
- Modules are executed with `importlib.util.spec_from_file_location`, not registered in `sys.modules` and without touching `sys.path`.
- `object_tree.py`, `model_source.py`, `application_table.py` from the plan's Files needed no change: `x_table_class` already carries the runtime class and `_check_table_methods`.
## Run inspection
- Phase 1 closed [!] on a plan-defect claim: SQLite generated columns are not read back by asqueel-migration 0.2.3 (`PRAGMA table_info`), and the Done grep matched the contract test itself. The foreman applied the fix on the user's answer.
- The foreman's first apply committed only the test copies and wrote `green` while the plan still showed [!]; the launcher started a repair, which the foreman stopped on the user's answer before it changed anything. The plan was closed by hand (6ebd670) and the run relaunched from Phase 2.
- Phase 2 closed [!] on a plan-defect claim: a contract test migrated an in-memory SQLite database, which `migration_plan()` refuses (decision A7.3). Applied on the user's answer (94a7ef7).
- Phases 3 and 4 closed on the first attempt. Final suite 4992 passed, 42 skipped, 31 xfailed (one strict xfail, asqueel#15, left with x_partition in Phase 1).
- Both plan defects were in contract tests written at planning time; no code defect reached a repair.

## Final touch
Reviewed revision: e126aec (review extended, one opus reviewer over c3c2612..e126aec; QA none, the plan has no Verify: steps).

| # | Finding | Root cause | Fix | Road |
|---|---|---|---|---|
| 1 | A layer extending a layout table dropped its Table class (triggers silently off) | x_table_class set only on tables new after config_db | Table class bound by module name; a module not declaring its table raises | final touch |
| 2 | main.py Table, Package.config_db / config_db_* / onBuildingDbobj ignored | loader read only config_attributes and custom_type_* | each raises naming the member | final touch |
| 3 | custom_type_<dtype> limited to dtype/size/names, error named `type` | routed through options().type() | result applied as column attributes, explicit ones win | final touch |
| 4 | crash on a model module without tables, on Package without config_attributes | unchecked None, missing default | module/table name check; config_attributes defaults to {} | final touch |
| 5 | guide docs contradicting partition, pkey, ext_* behaviour; PartitionScope in api.rst | not realigned | limitations, cheatsheet, environment, legacy, legacy-features, api.rst aligned; unpublished root docs (row-policies.md, native-model.md, delivery notes) left as historical records | final touch |
| 6 | legacy XML loader gave the generic error for encrypted/localized/variant/ext_*/mixin | _grammar checked before the specific refusals | _ABSENT_FEATURES refused by name | final touch |
| 7 | "not available in this release" built by hand at the Macro 4 sites | no helper | contracts.not_available(); Macro 4 sites use it. Macro 2 sites keep their own f-strings (same phrase, still greppable) | final touch |
| 8 | dialect list written in three places | literals | SQL_DIALECTS and SQL_COLUMN_KEYS drive builder and elements | final touch |
| 9 | index SQL name rule differs from legacy (hashed always) | Macro 7 concern | roadmap note under Macro 7 | roadmap |
| 10 | relation(cnd=, foreign_key=True) projected the FK | setdefault only | explicit foreign_key=True with cnd raises | final touch |
| 11 | pkey='a,b' still accepted on schema-level tables | — | no change: schema-level tables are the form reader.py:183-184 produces from the database; raising there breaks the reader round trip | dismissed |

Naming: the 18 new callables keep their names (11 legacy properties, 7 internal helpers); all wf:phase-N:new markers removed.
Checks run: tests/test_package_layout_edges.py (new), tests/test_release_invoice_migration.py (new loader test), contract tests of the 4 phases, full suite 5001 passed / 42 skipped / 31 xfailed, ruff, mypy clean, marker sweep empty.

Re-check (light, effort low, over 1b384a7 and its callers): 3 residuals, corrected on the user's answer in `wf: final touch — +3`:
- custom_type_<dtype>() values now pass the column rules (str_boolean for indexed/unique, specific refusals for encrypted/variant/localized/ext_*); an unknown key was already refused by model validation (checked);
- a custom_type_<dtype>() without dtype raises;
- `_columns` walks Bag values only.
Checks: tests/test_package_layout_edges.py (3 new cases), full suite 5004 passed / 42 skipped / 31 xfailed, ruff, mypy clean.
