## Phase 1

- Merge commit 8e6222f (`merge: read path 7cee8e8 into write cycle`), no conflict.
- Open merge in worktrees/write-cycle, read only: of its 16 staged files, 11 are byte-identical to the merged tree. 5 differ only by later read-path additions in 7cee8e8 (docs 42, 58, 99, docs/grammar.md, semantic_elements.py docstring: `table=` direct virtualRelation, aggregations, handoff 111 pointer). Nothing in the staged index is missing from the merged tree.
- Suite run with `--continue-on-collection-errors`, added to the plan's command: without it pytest stops at the 7 collection errors and nothing else can be attributed.
- Baseline: the 134 failing nodeids were run on an export of 1995fe4 (pre-merge write-cycle tip); all 134 fail there with the same message. They are the tests the read-path manifest `tests/read_path/pytest.args` excluded, never realigned after e96f0c1.
- Result: 134 R, 0 B, 0 O. No row reaches the merged write code, so B rows can only appear after Phase 2 realigns the tests.
- G10 (composite pkey) is R: legacy `gnrsqlmodel/table.py:194-209` requires `pkey` to name a column, composite through `composed_of`.
- G9 (tutorial `@customer`) is R: the relation path is the column name; `x_name` is not a relation name.
- Proposed deletions, pending the user's Verify: test_plans.py, adapter_dialect/test_postgres.py, test_wf_phase2_query_grouping.py (QueryPlan API removed).
