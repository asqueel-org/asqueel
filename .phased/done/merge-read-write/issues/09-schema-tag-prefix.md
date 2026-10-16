# A schema-tag model cannot set a table prefix

## What fails
A model built with the schema tags (SqlBuilder) cannot set a table prefix: the schema validator refuses `sqlprefix`, and `x_sql_prefix`, documented in `docs/native-model.md:13-15`, is ignored by `tableSqlName`.

## Evidence
- No test.
- `src/asqueel/object_tree.py:146-153`, `docs/native-model.md:13-15`
