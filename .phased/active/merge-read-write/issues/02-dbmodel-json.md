# The hierarchical DbModel has no JSON round trip

## What fails
`model_to_json` / `model_from_json` raise TypeError on a DbModel. A project cannot serialise a model and load it back.

## Evidence
- xfail tests: `tests/test_release_model_semantics.py::test_validation_model_survives_a_json_round_trip`, `tests/test_native_option_expansion.py::test_declarative_options_survive_a_json_round_trip`
- `src/asqueel/model_codec.py:16-30,50`
