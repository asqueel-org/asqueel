# inspect_postgres returns the removed contracts.ResolvedModel

## What fails
A model imported from a PostgreSQL database with `inspect_postgres` cannot be queried: it is a `contracts.ResolvedModel`, which QueryCompiler rejects (it requires a DbModel).

## Evidence
- xfail test: `tests/test_postgres_vertical.py::test_imported_model_compiles_selects`
- `src/asqueel/importers.py:207`, `src/asqueel/compiler.py:808-809`
