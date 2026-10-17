
## Phase 1
- genro-bag 0.28 `Bag(source)` accepts only dict, list or None. XML text goes through `Bag.from_xml`: `legacy_source.from_expanded_legacy_xml` and the 'X' column of `record.output('record')` (NULL stays an empty Bag, as `Bag(None)` gave before); test oracle in `tests/test_native_option_expansion.py` likewise.
- genro-bag 0.28 has no reader for the node-list JSON that `to_json` writes (`from_json` is a deprecated alias of `from_tytx`, which reads plain data). `to_tytx` refuses `SqlSourceBag` (not in the TYTX subtype dictionary). `test_grammar_export_and_source_json_preserve_declarations` now reads `to_json` with `json.loads`; the code is unchanged. Registering `SqlSourceBag` as a TYTX subtype was not done: no plan decision covers it.
- Model check: builders 0.29 keeps `${n}` literal in a `formulaColumn` attribute (test `test_model_keeps_template_placeholders_literal`).
