## Phase 1

- Merge commit 8e6222f (`merge: read path 7cee8e8 into write cycle`), no conflict.
- Open merge in worktrees/write-cycle, read only: of its 16 staged files, 11 are byte-identical to the merged tree. 5 differ only by later read-path additions in 7cee8e8 (docs 42, 58, 99, docs/grammar.md, semantic_elements.py docstring: `table=` direct virtualRelation, aggregations, handoff 111 pointer). Nothing in the staged index is missing from the merged tree.
- Suite run with `--continue-on-collection-errors`, added to the plan's command: without it pytest stops at the 7 collection errors and nothing else can be attributed.
- Baseline: the 134 failing nodeids were run on an export of 1995fe4 (pre-merge write-cycle tip); all 134 fail there with the same message. They are the tests the read-path manifest `tests/read_path/pytest.args` excluded, never realigned after e96f0c1.
- Result: 134 R, 0 B, 0 O. No row reaches the merged write code, so B rows can only appear after Phase 2 realigns the tests.
- G10 (composite pkey) is R: legacy `gnrsqlmodel/table.py:194-209` requires `pkey` to name a column, composite through `composed_of`.
- G9 (tutorial `@customer`) is R: the relation path is the column name; `x_name` is not a relation name.
- No test is deleted. test_plans.py, adapter_dialect/test_postgres.py and test_wf_phase2_query_grouping.py assert properties no write test covers (`%` escaping of physical names, RETURNING capability, line comments that cannot swallow the following clause, GROUP BY outside SELECT refused); tests/write_compiler covers only DEFAULT VALUES (test_write_compiler.py:91). They are realigned in Phase 2; only the QueryPlan/Fragment structure assertions go.
- G9 confirmed R on the legacy: `gnrsqlmodel/columns.py:180` resolves `'@%s' % self.name`; `relation_name` names only the inverse relation.

## Phase 2

- Foreman, clarify 1 (2026-10-16): an assertion on behaviour that a closed write-cycle decision removed on purpose (d-db-hooks, d-sql-effects, d-return, d-reverse, d-trigger-stack, d-logical-delete) or that the write cycle reproduces from the legacy is an R row: the assertion is rewritten to the decided mechanism, or dropped when the decided mechanism has nothing to assert. Not a deletion, not O. Soft delete/restore restated as an update of the logical-deletion field. Removing a whole test stays a deletion: it needs the user's approval in the phase chat (plan, Phase 2 Decisions).
- Foreman, clarify 2 (2026-10-16): partition-on-write tests are covered by the existing open issue asqueel-org/asqueel#15 ("Apply table partitions to writes"). Their xfail reason is `asqueel#15: <one line>`, no new issue draft. Phase 3 does not draft an issue for them.
