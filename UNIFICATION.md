# Release 0.7.0: one model

Baseline: origin/main at 08a9b02 (Asqueel 0.6.3).

The release has one objective: every supported model entry point produces the
hierarchical `DbModel`, consumed by the existing SELECT/write compilers and
physical projection. No new query features or benchmark optimizations.

Python comes first:

- Replace the disconnected catalog snapshot with the same hierarchical model.
- Make JSON round trips work for that model without serializing connections or
  executing embedded code, preserving migration fidelity checks.
- Remove the obsolete descriptor graph and its parallel physical projection.
- Keep operational rendering and model-only rendering as two return types over
  the same construction path, and document that distinction.
- Verify SQLite/PostgreSQL, all existing regressions, documentation and installed
  release artifacts before considering Python ready.

Then update JavaScript against the verified Python revision, including the model
serialization contract and parity fixtures. Existing browser/demo work is outside
this release. Publication and release tags follow review of the prepared artifacts.

Other dirty checkouts, including the earlier #35/#26 work on 0.6.0, are retained.
Those fixes must be assessed separately against current main, not copied wholesale.

## Python verification

The 0.7.0 wheel was installed into a fresh environment with published
Builders 0.30.0, Bag 0.28.0, Toolbox 0.18.0 and Migration 0.3.1.
`check_installed.py --workers 2 --postgresql`: 5,390 passed, 42 skipped,
20 pre-existing expected failures; 94% coverage. Sphinx with warnings as errors,
strict Twine checks and distribution checks passed. Wheel and sdist are prepared
in `dist/`; no tag or publication has been performed.
