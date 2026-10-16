# docs/guide/models.md contradicts the code

## What is wrong
- `docs/guide/models.md:160-162` names `originalColumn` and `model.ui`, which do not exist.
- `docs/guide/models.md:188-189` says that writes with an alias in their value mapping fail explicitly, and mentions `RETURNING '*'`; both contradict the current record-key and return behaviour of the write cycle.

## Evidence
- No test.
- `docs/guide/models.md:160-162,188-189`
