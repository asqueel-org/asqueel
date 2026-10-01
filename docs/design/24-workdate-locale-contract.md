# 24 — Workdate and locale context contract

Status: implemented and verified in the working tree after `022132b`; not yet
released. This closes the bounded F1 date/locale context slice, not F1 or full
legacy localization. No Babel dependency or locale catalogue was added.

## Evidence and decision

Legacy revision: `fa35e5adfa6ad1b269f3a22a9b12c4c1ee6513ea`.
Source inspection covered `gnrpy/gnr/sql/gnrsql/env.py` (properties and setters),
`gnrsql/helpers.py:TempEnv`, `gnr/core/gnrlocale.py:defaultLocale` and the
PostgreSQL/SQLite adapters' `setLocale` methods (both no-ops).
This slice used source inspection, not execution of the complete legacy runtime.

The user explicitly chose no locale validation for now. Legacy's `defaultLocale`
validates its fallback using Babel; native Asqueel deliberately preserves unknown
nonempty identifiers. Explicit truthy property values are already unvalidated
in legacy. Do not add a catalogue or optional validator implicitly.

| Contract | Native behavior and evidence |
|---|---|
| Workdate absent or false-valued | Current local `date.today()`, evaluated at access; matches the inspected getter. |
| Explicit truthy workdate | Preserved without parsing or conversion; driver binding still imposes its own supported types. |
| Explicit truthy locale | Preserved without validation or normalization. |
| Locale fallback | Use `GNR_LOCALE` if present, otherwise Python `locale.getlocale()[0]`; empty/absent result becomes `en_GB`. |
| Empty `GNR_LOCALE` | Select `en_GB`, even when the system locale is nonempty; corrected by this slice. |
| Unsupported locale identifier | Preserve it, including from the environment or system; accepted difference from Babel validation. |
| Scope and mutation | Nested overrides restore on exception; an introduced key changed inside a scope survives, following existing legacy tempEnv semantics. |
| Threads | One live mapping per worker; date/locale overrides do not leak to another worker or the main thread. |
| Queries | Effective defaults enter compiler snapshots; changed bindings reject stale execution, including a default workdate crossing midnight. Explicit query parameters win over environment lookup. |

The system fallback uses Python's current locale on every platform. Legacy has
an additional Windows UI-language lookup via Win32; that platform-specific
lookup is not ported or certified here. Localized parsing, formatting,
translation and database collation are outside this context-only contract.
No process-global `locale.setlocale()` is used.

## Verification

`tests/application_connections/test_locale_workdate.py` adds 11 cases covering the
fallback matrix, unknown values, dynamic dates, nested exception scopes, stale
queries, concurrent threads and real PostgreSQL/SQLite parameter binding.
Before the fix, the empty-environment regression failed (9 passed, 1 failed,
PostgreSQL deselected). After the fix the complete suite passes: **629 tests**,
**95% coverage**, with isolated PostgreSQL and SQLite. Ruff passes.

F1 still requires callback retry/residual-queue decisions PY02–PY04 and the
remaining caller-specific error paths from review 21. This result does not
change rollback protection, add localization services or certify Windows.
