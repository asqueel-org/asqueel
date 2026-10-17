# Context: plan/write-cycle
Parent: codex/core-release-0.6
Mode: manual
Theme: adapter base
Must not break: the full suite (4759 passed, 42 skipped, 32 strict xfail on PostgreSQL and SQLite at 6fe5848) stays green, apart from changes this plan states
Must not break: separate SELECT and DML compilers (QueryCompiler, WriteCompiler) over the single hierarchical model; this plan changes what they talk to, not their split
Must not break: later macros (.phased/roadmap.md) build on `db.adapter` as the one object that adapts the db to the implementation: dialect SQL, quoting, capabilities, connection, cursor, backend classes

## Objective
First macro of the cleanup decided on 2026-10-17 after the audit of unauthorized differences. Move to genro-builders 0.29 so `#TEMPLATE` uses `${name}`, then give asqueel the legacy `db.adapter`: one object per implementation that adapts the abstract db to the backend, replacing today's split between `dialects/` and `drivers/`.

## Work Plan
- [x] **Phase 1**: genro-builders 0.29 and `${name}` in #TEMPLATE
  - Run: opus / medium
  - Pattern: `library-standard` (dependency bump); `tests/test_template_macro.py` for the macro tests
  - Files: `pyproject.toml`, `src/asqueel/compiler.py` (`_TEMPLATE_MARK`, `_TEMPLATE_FIELD`), `tests/test_template_macro.py`, any module the new genro-builders/genro-bag versions break
  - Decisions: dependencies `genro-builders>=0.29.0,<0.30` and `genro-bag>=0.28.0,<0.29` (genro-builders 0.29.0 requires genro-bag>=0.28.0). From 0.29.0 builders keeps ordinary `${name}` attribute text literal (CHANGELOG 0.29.0, BREAKING). #TEMPLATE placeholder back to `${name}`, literal marker `$$` (user decision 2026-10-17). Breaking changes of genro-bag 0.28 / genro-builders 0.28-0.29 are absorbed in asqueel code, never pinned around.
  - Details: bump the two dependencies, recreate venv/ (`uv pip install --python venv/bin/python -e ".[dev,docs]"`), run the suite and fix what the upgrade breaks; switch `_TEMPLATE_MARK` to `$` and rewrite the tests with `${n}` and `$$`; add a test where `${n}` sits in a model `formulaColumn` attribute and reaches the compiler intact.
  - Done: `venv/bin/python -m pytest tests --no-cov -q` green on PostgreSQL and SQLite (only the existing strict xfails); `venv/bin/python -m pytest tests/test_template_macro.py --no-cov -q` green with `${n}` placeholders, including the model formulaColumn case; `grep -n "§" src/asqueel/compiler.py tests/test_template_macro.py` empty; ruff and mypy pass.
  > Done: genro-builders 0.29 / genro-bag 0.28; #TEMPLATE placeholder back to `${name}`, literal `$$`; XML text into Bag via `Bag.from_xml` (genro-bag 0.28 `Bag()` takes only dict/list/None); suite 4761 passed, 42 skipped, 32 xfailed; ruff, mypy clean
  > Files: pyproject.toml, src/asqueel/compiler.py, src/asqueel/legacy_source.py, src/asqueel/application_table.py, tests/test_template_macro.py, tests/test_native_option_expansion.py, tests/test_behavior_option_grammar.py, .phased/active/adapter-base/notes.md, .phased/active/adapter-base/plan.md
  > Review: `SqlSourceBag` is not a TYTX subtype, so `source.to_tytx()` raises and genro-bag 0.28 has no reader for the node-list `to_json`; the grammar test now reads `to_json` with `json.loads`. No plan decision covers registering it.

- [>] **Phase 2**: `db.adapter` as in the legacy  `vast`
  > In execution since 2026-10-17T14:25:00Z
  - Run: opus / high
  > Batches: 1 adapter classes absorbing dialects/ (SQL text, quoting, capabilities) | 2 connection, cursor, execute and the translations now in drivers/sql.py | 3 db.adapter wiring, implementation loading, compilers and runtime on the adapter, old modules removed | 4 string_agg, unaccentFormula, mask_field_sql, ageAtDate with tests
  - Pattern: legacy `gnrpy/gnr/sql/adapters/_gnrbaseadapter.py:SqlDbAdapter`, `gnrpy/gnr/sql/adapters/gnrpostgres.py`, `gnrpy/gnr/sql/adapters/gnrsqlite.py` at GenroPy `95da66ee` (`git -C ~/Sviluppo/Genropy/genropy show 95da66ee:<path>`); legacy loading `gnrpy/gnr/sql/gnrsql/db.py:151-156`; current code to absorb: `src/asqueel/dialects/{base,postgres,sqlite,_bag_xml}.py`, `src/asqueel/drivers/{base,psycopg,sqlite,sql,result}.py`
  - Files: `src/asqueel/adapters/` (new: base, postgres, sqlite and what the batches need), `src/asqueel/application.py`, `src/asqueel/runtime.py`, `src/asqueel/compiler.py`, `src/asqueel/write_compiler.py`, `src/asqueel/configuration.py`, `src/asqueel/application_table.py`, `src/asqueel/__init__.py`, the tests that import dialects/drivers; `src/asqueel/dialects/` and `src/asqueel/drivers/` removed
  - Decisions: (user, 2026-10-17) «il db è astrazione e adapter è l'oggetto che adatta il db all'implementazione e ne segue le peculiarità, anche su cursore, classi, capabilities». One adapter class per implementation, a base class plus PostgreSQL and SQLite, as legacy `SqlDbAdapter`; NOT a facade over the current dialect and driver. `db.adapter` is the single object; compilers and runtime reach the backend only through it. Implementation selection as legacy (user, 2026-10-17): default `sqlite`; names `postgres`, `postgres3`, `sqlite`; external module `name:module`; `db.adapter` follows `currentEnv['currentImplementation']` and loads that adapter on demand. Dialect translations now in `drivers/sql.py` (ILIKE, REGEXP, IS TRUE/FALSE on SQLite, collections) move into the adapter. `db.adapter.string_agg(field, separator)`, `unaccentFormula`, `mask_field_sql`, `ageAtDate` as legacy (user, 2026-10-17). Method names of the adapter follow the legacy where a legacy method exists; asqueel methods with no legacy counterpart keep their current names. No compatibility aliases for the removed modules (`PostgresDialect`, `PsycopgDriver`, `SqliteDialect`, `SqliteDriver` exports go). The capability catalogue stays as today: its redesign is a separate proposal (roadmap Macro 7).
  - Details: build the adapter classes from the legacy structure, moving into them the asqueel code of dialects/ and drivers/ (no behaviour change beyond the decisions above); wire `db.adapter`; route compilers, runtime and execution through it; load the implementation as legacy; add the four model functions with tests on both dialects (expected SQL per dialect taken from the legacy adapters); update the tests that import the old modules.
  - Done: full suite green on PostgreSQL and SQLite (only the existing strict xfails, plus the new tests); `grep -rn "asqueel.dialects\|asqueel.drivers\|from .dialects\|from .drivers\|from ..dialects\|from ..drivers" src tests` empty; `test -d src/asqueel/dialects || test -d src/asqueel/drivers` fails; a test asserts `type(db.adapter)` per implementation for 'sqlite', 'postgres', 'postgres3' and that the default implementation is 'sqlite'; tests for string_agg, unaccentFormula, mask_field_sql, ageAtDate pass on both dialects; ruff, mypy and `sphinx -W` pass.
  - Verify: now — read the adapter base class: it reads as the legacy SqlDbAdapter, one place per backend peculiarity.

## Notes
- Adopted branch plan/write-cycle, worktree worktrees/write-cycle. No push. Commits carry no AI attribution.
- The full list of the 2026-10-17 decisions is the local, untracked file `temp/audit-invenzioni/decisioni.md`; later macros are in `.phased/roadmap.md`.
- Test environment: memory note asqueel-test-environment.
