# Release 0.7.0: consolidation and one model

Baseline: origin/main at 08a9b02 (Asqueel 0.6.3).

Every supported model entry point produces the hierarchical `DbModel`, consumed
by the existing SELECT/write compilers and physical projection. The consolidation
also includes the SQL parameter literal fix (#35) and documentation corrections
(#27, #37). No new query features or benchmark optimizations.

Python comes first:

- Replace the disconnected catalog snapshot with the same hierarchical model.
- Round-trip that model through version 2 JSON without connections or executable
  code, preserving migration fidelity checks.
- Remove the obsolete descriptor graph and its parallel physical projection.
- Keep operational rendering and model-only rendering as two return types over
  the same construction path.
- Verify SQLite/PostgreSQL, existing regressions, documentation and installed
  release artifacts before considering Python ready.

Only after Python passes these checks, update JavaScript against its verified
revision, including serialization and parity fixtures. Existing JS consolidation
work is preserved for that subsequent step. DB Manager is outside this task.
Publication and release tags require authorization separately from local preparation.

Original dirty checkouts are retained. The #35 fix was adapted to current adapters;
SELECT composite keys already work, and the retired `record()` path is not restored.
Q01 experiments and other unresolved feature requests remain in the backlog.

## Verification

Fresh installed-wheel suite on Python 3.12 with real PostgreSQL: **5,443 passed,
42 skipped, 20 pre-existing expected failures**, 94% coverage. Published ecosystem
dependencies: Builders 0.30.0, Bag 0.28.0, Toolbox 0.18.0, Migration 0.3.1.
Ruff, mypy (66 files), Sphinx with warnings as errors, strict Twine and distribution
checks passed, as did the minimum installation without Migration. A combined
JSON round-trip/formula literal regression passed against the installed wheel.
All final wheel Python modules match the tested installation byte for byte.
Remote CI and publication are pending.
