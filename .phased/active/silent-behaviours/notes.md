## Planning

### Generic messages
Raise sites of `UnsupportedFeatureError` whose message does not name the feature the user wrote (recon at 569b88f; line numbers move with Phases 1-3):
- `src/asqueel/compiler.py`: 127 virtual/composite column "not connected yet"; 178 formulaColumn `subqueries=`/`handler=` (message does not name them); 189 other virtual tag "not connected yet"; 253 unknown subquery options (list only); 313 and 410 many relation in a path "not yet supported"; 538 many joiner with join_on/cnd/between (attribute not named); 582 `#macro` "Hierarchical macro expansion is not connected yet"; 741 wildcard prefix (token not shown); 888 leftover query options "Unsupported query options".
- `src/asqueel/application_table.py`: 87 unused keyword bindings (list); 129 `selection()` "outside this application profile"; 243 `_UNSUPPORTED` query options "Unsupported query options".
- `src/asqueel/projection.py`: 110 advanced unique/primary constraint; 145 advanced constraint index; 156 advanced index semantics (attribute not named).
- `src/asqueel/adapters/base.py`: 262 `mask_field_sql` "not implemented".
- `src/asqueel/runtime.py`: 122 storename "Database stores are not implemented in this profile".
- `src/asqueel/model_source.py`: 253 write on a table with pending declarations "not implemented".
Tests matching the old phrases: `tests/object_tree/test_phase2_relations.py` (6), `tests/object_tree/test_phase3_formulas.py` (1).

### Extras measured in the suite
A full run at 569b88f with the `_` gate instrumented: keys accepted through it, by prefix — `x_` (system and free), `group_`, `validate_`, `var_`, `hierarchical_`, `select_`, `legacy_`, `name_` (`name_full`), `template_`, `one_`, `atc_`, `cell_`, `batch_`, `nodup_`, `exist_`, `foo_`, `app_`, `ui_`, `notnull_`, `len_`, `domain_`, `col_`. Sources: `examples/test_invoice_pg`, `tests/oracles/test_invoice_pg/source.xml`, `tests/test_release_composition.py`, `tests/application_config/`, `tests/object_tree/test_structure.py`, `tests/object_tree/test_relation_metadata.py`.

## Phase 1
- Foreman clarification (2026-10-17), confirmed by the user at the gate: `back_reference=` disappears together with `inverse=`; `relation_name=` is the only name of the inverse. The Done grep of the old spellings includes `back_reference`.
- Gate (user, 2026-10-17): `'n::N'` together with `dtype=` raises `dtype passed twice` (the legacy overwrites silently; the grammar raises). The split applies to column, aliasColumn, formulaColumn, subQueryColumn, pyColumn, bagItemColumn, compositeColumn: the legacy routes all of them through `virtual_column`.
- Gate: action values are the legacy full names, any case. SQL: cascade, restrict, no action, setnull/set null, setdefault/set default. Python: cascade, raise, ignore, setnull, optional `:message`. The snake forms set_null/no_action/set_default disappear; abbreviations are Macro 7.
- Gate: `reader.py` (migration JSON -> model) writes `onDelete_sql`/`onUpdate_sql`; the migration JSON keeps `on_delete`/`on_update`. `deferrable`/`initially_deferred` stay (not in the decision).
- Build: compositeColumn does not split `name::dtype`. Its asqueel signature has no dtype: it is a key with dtype JS fixed, like the legacy `dtype='JS'`. bagItemColumn is a semantic element and splits like the other virtual columns.
- Build: a truthy limit/offset that is not a nonnegative int still raises; only falsy values skip the clause.
