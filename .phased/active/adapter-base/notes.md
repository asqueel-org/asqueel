
## Phase 1
- genro-bag 0.28 `Bag(source)` accepts only dict, list or None. XML text goes through `Bag.from_xml`: `legacy_source.from_expanded_legacy_xml` and the 'X' column of `record.output('record')` (NULL stays an empty Bag, as `Bag(None)` gave before); test oracle in `tests/test_native_option_expansion.py` likewise.
- genro-bag 0.28 has no reader for the node-list JSON that `to_json` writes (`from_json` is a deprecated alias of `from_tytx`, which reads plain data). `to_tytx` refuses `SqlSourceBag` (not in the TYTX subtype dictionary). `test_grammar_export_and_source_json_preserve_declarations` now reads `to_json` with `json.loads`; the code is unchanged. Registering `SqlSourceBag` as a TYTX subtype was not done: no plan decision covers it.
- Model check: builders 0.29 keeps `${n}` literal in a `formulaColumn` attribute (test `test_model_keeps_template_placeholders_literal`).

## Phase 2

- Foreman, clarify 1 (2026-10-17), answers to the gate questions:
  1. 'postgres' vs 'postgres3': not decided — ask the user. Foreman's information: asqueel depends only on psycopg 3; a separate psycopg2 adapter would add a new dependency.
  2. currentImplementation: decided (decisioni.md A8.1, user 2026-10-17: «cambio adapter dall'ambiente con currentImplementation»). In Phase 2: db.adapter reads currentEnv['currentImplementation'] and loads that adapter on demand, as legacy. Plan edit proposed.
  3. ageAtDate on SQLite: the legacy SQLite adapter has no form (base SQL uses EXTRACT(EPOCH FROM), absent in SQLite). Proposed: SQLite raises an explicit error naming the missing capability ("anything outside the grammar raises", user 2026-10-17); the test asserts the SQL on PostgreSQL and the error on SQLite.
  4. Implementation names: decided (A8.1): legacy names 'postgres', 'postgres3', 'sqlite', default 'sqlite'. 'postgresql' is not a legacy name: it raises, no alias (rule "outside the grammar raises"). Configurations, tests and docs using 'postgresql' are realigned in this phase.
- Gate, user (2026-10-17): 'postgres' and 'postgres3' both load the psycopg 3 adapter (no psycopg2 dependency).
- Gate, user (2026-10-17): accepted the foreman's plan edit — currentImplementation is in Phase 2.
- Gate, user (2026-10-17): accepted the foreman's proposal — ageAtDate on SQLite raises an explicit error; the test asserts the PostgreSQL SQL and the SQLite error.
- Gate approved by the user (2026-10-17). Technical choices taken from the legacy and the user's rules:
  - modules `asqueel/adapters/{base,postgres,postgres3,sqlite}.py`, each exposing `SqlDbAdapter`, loaded as legacy `module.SqlDbAdapter(db)`; `postgres3` loads the same class as `postgres`.
  - legacy method names where a legacy method exists: compileSql, asTranslator, adaptSqlName (current quoting, checks kept), string_join (was concat_non_null), prepareSqlText, adaptTupleListSet, connect, cursor; other methods keep their current names; `capabilities` attribute as today.
  - `QueryCompiler(model, adapter)`, `WriteCompiler(adapter)`, `Database(..., implementation=...)`; `driver=`/`dialect=` arguments and `db.dialect`/`db.driver` removed; test fakes become fake adapters loaded with `name:module`.
  - `PostgresDatabase` and `PostgresCompiler` stay, built on the adapter.
  - `mask_field_sql` raises on an invalid mode (legacy falls back to 2-4); `string_agg` escapes the separator (legacy does not).
  - Sphinx pages in the toctree showing the removed classes are realigned; docs/design and probes are historical and untouched.
- Build: rows are indexed by `cursor.description[i][0]` on both backends, as legacy (GnrDictCursor._build_index, GnrSqliteCursor); the fake psycopg cursor of tests/native_runtime/test_runtime.py now exposes a DB-API description tuple instead of `.name`. `cursor()` returns a cursor usable as a context manager (psycopg as is, sqlite3 through closing).
- Build: ageAtDate with an unknown timeUnit raises ValueError (legacy falls back to 'day'), same rule as mask_field_sql; the base adapter's mask_field_sql raises UnsupportedFeatureError (legacy warns and returns the field). Batch 4 SQL checked equal to the legacy adapters' output at 95da66ee for every case in tests/adapters/test_adapter_functions.py.
- Naming review (2026-10-17): all names accepted, markers stripped.
