
## Phase 1

- Baseline was red (8 failed, 6 errors) before any edit: all `no such table` from asqueel-migration 0.3.0 attaching `<schema>.db` while asqueel attached `<stem>_<schema>.db`. The plan's Notes name this as the reason Phase 1 runs first; no `[x]` phase owns it, so the phase proceeded instead of blocking.
- `foreignKeys` on PostgreSQL is refused in two places: the builder's `driver` check (raised at construction, where `connection(options=...)` is normalised into `driver(...)`) and `PostgresAdapter.connect` (connect kwargs passed without the builder). Both messages name it as a SQLite connection option.
- `driver()` in `model_elements.py` and the driver check in `builder.py` were not in the plan's Files; the decision "the `driver` element gains it" needs both. `docs/grammar.md` is generated from the elements and was regenerated.
- Realignments outside the discovery rule, all from the legacy layout (every schema file lives in the main file's folder): `test_hosting.py` put four databases in one folder, now one folder each; `test_mounted_grammar.py` named the main file `chat.db`, which is now schema `chat`'s file, so the main file became `archive.db`; `test_wf_phase21_delivery.py` asserts the pin string; `docs/guide/migrations.md` stated the old pin.
