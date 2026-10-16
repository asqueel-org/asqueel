# pkey='a,b' is accepted, while the legacy requires pkey to name one column

## What fails
`WriteCompiler.pkeys` accepts `pkey='a,b'` and the `table` grammar describes `pkey` as comma-joined names. The legacy requires `pkey` to name one column; a composite key goes through `composed_of`. `object_tree.physical_columns` fails on such a pkey, so the model is accepted at declaration and fails later.

## Evidence
- No test.
- `src/asqueel/write_compiler.py:34-42`, `src/asqueel/elements.py:179`, `src/asqueel/object_tree.py:386-391`
- Legacy: `gnrsqlmodel/table.py:194-209`
