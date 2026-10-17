
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
