# Attribution — full suite after merge 8e6222f

Run: `venv/bin/python -m pytest tests --no-cov -q -rfE -p no:cacheprovider --continue-on-collection-errors`, PostgreSQL 127.0.0.1:5432 and SQLite.

Result: 98 failed, 4601 passed, 42 skipped, 36 errors — 134 rows below. Without `--continue-on-collection-errors` the run stops at the 7 collection errors of G4.

Baseline: the same 134 nodeids fail with the same message on the write-cycle tip 1995fe4, before the merge. The merge introduces no new failure.

Static checks: `venv/bin/ruff check src tests scripts` passes; `venv/bin/python -m mypy src/asqueel` reports no issues in 62 source files. Nothing to attribute.

Classes: R = old test to realign to the merged API; B = integration bug in code; O = out of scope, to become an issue. Count: R 134, B 0, O 0. Every row fails before reaching the merged write code, so B rows can surface only once Phase 2 realigns the tests.

Draft numbers for O rows are assigned in Phase 2: see the section "Phase 2 — outcome" at the end.

## G1 — R — 89 rows

Cause: Test calls `table()` with a bare name (`item`, `invoice`, `customer`); the hierarchical model requires `package.table` since e96f0c1 (doc 99, contract 1).

Evidence: `src/asqueel/object_tree.py:376` raises `table() requires package.table`; the 8 `Regex pattern did not match` rows and the 2 `assert ... is` rows of `test_python_errors.py` receive this same error instead of the expected one.

Action: realign: qualify the table name; for `test_quickstart_as_published` the bare name is in `docs/guide/quickstart.md`.

| nodeid | class | evidence | area | action |
|---|---|---|---|---|
| `tests/application_config/test_application.py::test_rollback_only_session_rejects_write_before_calling_hooks` | R | tests/application_config/test_application.py:104 | application_config | realign |
| `tests/application_connections/test_deferred.py::test_hooks_can_register_both_queues_and_deferred_errors` | R | tests/application_connections/test_deferred.py:29 | application_connections | realign |
| `tests/application_connections/test_deferred.py::test_stack_tracks_nested_writes_and_restores_after_exception` | R | tests/application_connections/test_deferred.py:213 | application_connections | realign |
| `tests/application_connections/test_python_errors.py::test_db_context_preserves_hook_exception_when_cleanup_also_fails[close]` | R | tests/application_connections/test_python_errors.py:81 | application_connections | realign |
| `tests/application_connections/test_python_errors.py::test_db_context_preserves_hook_exception_when_cleanup_also_fails[rollback]` | R | tests/application_connections/test_python_errors.py:81 | application_connections | realign |
| `tests/application_connections/test_python_errors.py::test_reused_exception_from_an_earlier_sql_attempt_is_a_new_hook_failure` | R | tests/application_connections/test_python_errors.py:57 | application_connections | realign |
| `tests/application_connections/test_python_errors.py::test_sql_error_on_another_connection_cannot_commit_incomplete_outer_write[trigger_onInserted]` | R | tests/application_connections/test_python_errors.py:22 | application_connections | realign |
| `tests/application_connections/test_python_errors.py::test_sql_error_on_another_connection_cannot_commit_incomplete_outer_write[trigger_onInserting]` | R | tests/application_connections/test_python_errors.py:22 | application_connections | realign |
| `tests/application_connections/test_request_lifecycle.py::test_next_request_inherits_no_pending_work_or_context[after-postgresql]` | R | tests/application_connections/test_request_lifecycle.py:98 | application_connections | realign |
| `tests/application_connections/test_request_lifecycle.py::test_next_request_inherits_no_pending_work_or_context[after-sqlite]` | R | tests/application_connections/test_request_lifecycle.py:98 | application_connections | realign |
| `tests/application_connections/test_request_lifecycle.py::test_next_request_inherits_no_pending_work_or_context[application-postgresql]` | R | tests/application_connections/test_request_lifecycle.py:98 | application_connections | realign |
| `tests/application_connections/test_request_lifecycle.py::test_next_request_inherits_no_pending_work_or_context[application-sqlite]` | R | tests/application_connections/test_request_lifecycle.py:98 | application_connections | realign |
| `tests/application_connections/test_request_lifecycle.py::test_next_request_inherits_no_pending_work_or_context[before-postgresql]` | R | tests/application_connections/test_request_lifecycle.py:98 | application_connections | realign |
| `tests/application_connections/test_request_lifecycle.py::test_next_request_inherits_no_pending_work_or_context[before-sqlite]` | R | tests/application_connections/test_request_lifecycle.py:98 | application_connections | realign |
| `tests/application_connections/test_request_lifecycle.py::test_next_request_inherits_no_pending_work_or_context[hook-postgresql]` | R | tests/application_connections/test_request_lifecycle.py:98 | application_connections | realign |
| `tests/application_connections/test_request_lifecycle.py::test_next_request_inherits_no_pending_work_or_context[hook-sqlite]` | R | tests/application_connections/test_request_lifecycle.py:98 | application_connections | realign |
| `tests/application_connections/test_request_lifecycle.py::test_next_request_inherits_no_pending_work_or_context[sql-postgresql]` | R | tests/application_connections/test_request_lifecycle.py:98 | application_connections | realign |
| `tests/application_connections/test_request_lifecycle.py::test_next_request_inherits_no_pending_work_or_context[sql-sqlite]` | R | tests/application_connections/test_request_lifecycle.py:98 | application_connections | realign |
| `tests/application_integration/test_alias_columns.py::test_aliases_are_read_only_and_default_dml_returning_is_physical` | R | tests/application_integration/test_alias_columns.py:73 | application_integration | realign |
| `tests/application_integration/test_formula_subqueries.py::test_default_returning_does_not_evaluate_subquery_virtuals[package]` | R | tests/application_integration/test_formula_subqueries.py:93 | application_integration | realign |
| `tests/application_integration/test_formula_subqueries.py::test_default_returning_does_not_evaluate_subquery_virtuals[schema]` | R | tests/application_integration/test_formula_subqueries.py:93 | application_integration | realign |
| `tests/application_integration/test_postgres_application.py::test_caught_hook_error_cannot_turn_context_exit_into_success` | R | tests/application_integration/test_postgres_application.py:153 | application_integration | realign |
| `tests/application_integration/test_postgres_application.py::test_caught_hook_error_remains_rollback_only_and_cannot_commit` | R | tests/application_integration/test_postgres_application.py:110 | application_integration | realign |
| `tests/application_integration/test_postgres_application.py::test_database_constraint_failure_rolls_back_previous_operations` | R | tests/application_integration/test_postgres_application.py:164 | application_integration | realign |
| `tests/application_integration/test_postgres_application.py::test_manual_rollback_and_close_discard_cross_table_writes` | R | tests/application_integration/test_postgres_application.py:84 | application_integration | realign |
| `tests/application_integration/test_postgres_application.py::test_manual_unit_of_work_is_shared_and_invisible_until_explicit_commit` | R | tests/application_integration/test_postgres_application.py:65 | application_integration | realign |
| `tests/application_integration/test_postgres_application.py::test_named_connections_have_independent_visibility_and_physical_identity` | R | tests/application_integration/test_postgres_application.py:176 | application_integration | realign |
| `tests/application_integration/test_postgres_application.py::test_query_compiles_in_terminal_environment_and_record_refreshes_explicitly` | R | tests/application_integration/test_postgres_application.py:125 | application_integration | realign |
| `tests/application_integration/test_postgres_application.py::test_shared_database_threads_have_independent_postgres_connections` | R | tests/application_integration/test_postgres_application.py:221 | application_integration | realign |
| `tests/application_integration/test_postgres_application.py::test_sql_error_in_named_connection_rolls_back_hooks_and_allows_reuse` | R | tests/application_integration/test_postgres_application.py:195 | application_integration | realign |
| `tests/application_integration/test_postgres_application.py::test_transaction_context_commits_hooks_together_and_rolls_back_hook_failure` | R | tests/application_integration/test_postgres_application.py:97 | application_integration | realign |
| `tests/application_integration/test_postgres_policies.py::test_application_partition_draft_deletion_and_scoped_writes` | R | tests/application_integration/test_postgres_policies.py:47 | application_integration | realign |
| `tests/application_integration/test_python_errors_postgres.py::test_failed_batch_can_commit_error_log_on_system_connection` | R | tests/application_integration/test_write_hooks.py:82 | application_integration | realign |
| `tests/application_integration/test_python_errors_postgres.py::test_failed_batch_item_can_be_rolled_back_logged_and_skipped[deferred]` | R | tests/application_integration/test_write_hooks.py:82 | application_integration | realign |
| `tests/application_integration/test_python_errors_postgres.py::test_failed_batch_item_can_be_rolled_back_logged_and_skipped[python]` | R | tests/application_integration/test_write_hooks.py:82 | application_integration | realign |
| `tests/application_integration/test_python_errors_postgres.py::test_failed_batch_item_can_be_rolled_back_logged_and_skipped[sql]` | R | tests/application_integration/test_write_hooks.py:82 | application_integration | realign |
| `tests/application_integration/test_python_errors_postgres.py::test_handled_external_failure_can_be_saved_as_status` | R | tests/application_integration/test_write_hooks.py:82 | application_integration | realign |
| `tests/application_integration/test_python_errors_postgres.py::test_other_connection_sql_failure_aborts_outer_hook_but_not_independent_work[trigger_onUpdated]` | R | tests/application_integration/test_write_hooks.py:82 | application_integration | realign |
| `tests/application_integration/test_python_errors_postgres.py::test_other_connection_sql_failure_aborts_outer_hook_but_not_independent_work[trigger_onUpdating]` | R | tests/application_integration/test_write_hooks.py:82 | application_integration | realign |
| `tests/application_integration/test_python_errors_postgres.py::test_python_failure_matrix_keeps_current_native_rollback_contract` | R | tests/application_integration/test_python_errors_postgres.py:21 | application_integration | realign |
| `tests/application_integration/test_raw_writes.py::test_ordinary_cardinality_and_raw_predicates[postgresql-delete-False-False]` | R | tests/application_integration/test_raw_writes.py:76 | application_integration | realign |
| `tests/application_integration/test_raw_writes.py::test_ordinary_cardinality_and_raw_predicates[postgresql-delete-False-True]` | R | tests/application_integration/test_raw_writes.py:76 | application_integration | realign |
| `tests/application_integration/test_raw_writes.py::test_ordinary_cardinality_and_raw_predicates[postgresql-delete-True-False]` | R | tests/application_integration/test_raw_writes.py:76 | application_integration | realign |
| `tests/application_integration/test_raw_writes.py::test_ordinary_cardinality_and_raw_predicates[postgresql-delete-True-True]` | R | tests/application_integration/test_raw_writes.py:76 | application_integration | realign |
| `tests/application_integration/test_raw_writes.py::test_ordinary_cardinality_and_raw_predicates[postgresql-update-False-False]` | R | tests/application_integration/test_raw_writes.py:76 | application_integration | realign |
| `tests/application_integration/test_raw_writes.py::test_ordinary_cardinality_and_raw_predicates[postgresql-update-False-True]` | R | tests/application_integration/test_raw_writes.py:76 | application_integration | realign |
| `tests/application_integration/test_raw_writes.py::test_ordinary_cardinality_and_raw_predicates[postgresql-update-True-False]` | R | tests/application_integration/test_raw_writes.py:76 | application_integration | realign |
| `tests/application_integration/test_raw_writes.py::test_ordinary_cardinality_and_raw_predicates[postgresql-update-True-True]` | R | tests/application_integration/test_raw_writes.py:76 | application_integration | realign |
| `tests/application_integration/test_raw_writes.py::test_ordinary_cardinality_and_raw_predicates[sqlite-delete-False-False]` | R | tests/application_integration/test_raw_writes.py:76 | application_integration | realign |
| `tests/application_integration/test_raw_writes.py::test_ordinary_cardinality_and_raw_predicates[sqlite-delete-False-True]` | R | tests/application_integration/test_raw_writes.py:76 | application_integration | realign |
| `tests/application_integration/test_raw_writes.py::test_ordinary_cardinality_and_raw_predicates[sqlite-delete-True-False]` | R | tests/application_integration/test_raw_writes.py:76 | application_integration | realign |
| `tests/application_integration/test_raw_writes.py::test_ordinary_cardinality_and_raw_predicates[sqlite-delete-True-True]` | R | tests/application_integration/test_raw_writes.py:76 | application_integration | realign |
| `tests/application_integration/test_raw_writes.py::test_ordinary_cardinality_and_raw_predicates[sqlite-update-False-False]` | R | tests/application_integration/test_raw_writes.py:76 | application_integration | realign |
| `tests/application_integration/test_raw_writes.py::test_ordinary_cardinality_and_raw_predicates[sqlite-update-False-True]` | R | tests/application_integration/test_raw_writes.py:76 | application_integration | realign |
| `tests/application_integration/test_raw_writes.py::test_ordinary_cardinality_and_raw_predicates[sqlite-update-True-False]` | R | tests/application_integration/test_raw_writes.py:76 | application_integration | realign |
| `tests/application_integration/test_raw_writes.py::test_ordinary_cardinality_and_raw_predicates[sqlite-update-True-True]` | R | tests/application_integration/test_raw_writes.py:76 | application_integration | realign |
| `tests/application_integration/test_raw_writes.py::test_raw_insert_input_contract_and_hook_mutation[postgresql]` | R | tests/application_integration/test_raw_writes.py:157 | application_integration | realign |
| `tests/application_integration/test_raw_writes.py::test_raw_insert_input_contract_and_hook_mutation[sqlite]` | R | tests/application_integration/test_raw_writes.py:157 | application_integration | realign |
| `tests/application_integration/test_raw_writes.py::test_raw_list_late_python_failure_requires_rollback[postgresql]` | R | tests/application_integration/test_raw_writes.py:135 | application_integration | realign |
| `tests/application_integration/test_raw_writes.py::test_raw_list_late_python_failure_requires_rollback[sqlite]` | R | tests/application_integration/test_raw_writes.py:135 | application_integration | realign |
| `tests/application_integration/test_raw_writes.py::test_raw_list_late_sql_failure_rolls_back_entire_pending_work[postgresql]` | R | tests/application_integration/test_raw_writes.py:145 | application_integration | realign |
| `tests/application_integration/test_raw_writes.py::test_raw_list_late_sql_failure_rolls_back_entire_pending_work[sqlite]` | R | tests/application_integration/test_raw_writes.py:145 | application_integration | realign |
| `tests/application_integration/test_write_hooks.py::test_caught_precommit_sql_failure_cannot_announce_commit` | R | tests/application_integration/test_write_hooks.py:82 | application_integration | realign |
| `tests/application_integration/test_write_hooks.py::test_deferred_registered_in_hook_shares_commit_and_observer_visibility` | R | tests/application_integration/test_write_hooks.py:82 | application_integration | realign |
| `tests/application_integration/test_write_hooks.py::test_exactly_one_locked_record_before_any_hook[delete]` | R | tests/application_integration/test_write_hooks.py:82 | application_integration | realign |
| `tests/application_integration/test_write_hooks.py::test_exactly_one_locked_record_before_any_hook[update]` | R | tests/application_integration/test_write_hooks.py:82 | application_integration | realign |
| `tests/application_integration/test_write_hooks.py::test_full_records_old_snapshot_composite_zero_key_and_atomic_hooks` | R | tests/application_integration/test_write_hooks.py:82 | application_integration | realign |
| `tests/application_integration/test_write_hooks.py::test_hook_key_change_uses_saved_old_key_and_raw_allows_batch_writes` | R | tests/application_integration/test_write_hooks.py:82 | application_integration | realign |
| `tests/application_integration/test_write_hooks.py::test_post_hook_failure_rolls_back_write_and_cross_table_effects[delete]` | R | tests/application_integration/test_write_hooks.py:82 | application_integration | realign |
| `tests/application_integration/test_write_hooks.py::test_post_hook_failure_rolls_back_write_and_cross_table_effects[update]` | R | tests/application_integration/test_write_hooks.py:82 | application_integration | realign |
| `tests/application_integration/test_write_hooks.py::test_pre_hook_holds_postgres_row_lock` | R | tests/application_integration/test_write_hooks.py:82 | application_integration | realign |
| `tests/application_integration/test_write_hooks.py::test_precommit_exception_rolls_back_real_writes_and_skips_after` | R | tests/application_integration/test_write_hooks.py:82 | application_integration | realign |
| `tests/application_integration/test_write_hooks.py::test_soft_delete_restore_call_update_hooks_with_deleted_record_visible` | R | tests/application_integration/test_write_hooks.py:82 | application_integration | realign |
| `tests/application_integration/test_write_lifecycle.py::test_integration_hook_error_blocks_commit_for_normal_and_raw[postgresql]` | R | tests/application_integration/test_write_lifecycle.py:126 | application_integration | realign |
| `tests/application_integration/test_write_lifecycle.py::test_integration_hook_error_blocks_commit_for_normal_and_raw[sqlite]` | R | tests/application_integration/test_write_lifecycle.py:126 | application_integration | realign |
| `tests/application_integration/test_write_lifecycle.py::test_normal_and_raw_insertion_share_tracking_and_nested_execution[postgresql]` | R | tests/application_integration/test_write_lifecycle.py:80 | application_integration | realign |
| `tests/application_integration/test_write_lifecycle.py::test_normal_and_raw_insertion_share_tracking_and_nested_execution[sqlite]` | R | tests/application_integration/test_write_lifecycle.py:80 | application_integration | realign |
| `tests/application_integration/test_write_lifecycle.py::test_update_and_delete_track_raw_without_table_hooks[postgresql]` | R | tests/application_integration/test_write_lifecycle.py:99 | application_integration | realign |
| `tests/application_integration/test_write_lifecycle.py::test_update_and_delete_track_raw_without_table_hooks[sqlite]` | R | tests/application_integration/test_write_lifecycle.py:99 | application_integration | realign |
| `tests/documentation/test_examples.py::test_quickstart_as_published` | R | tests/documentation/test_examples.py:67 | documentation | realign |
| `tests/sqlite/test_sqlite_application.py::test_another_named_connection_times_out_without_losing_first_transaction` | R | tests/sqlite/test_sqlite_application.py:152 | sqlite | realign |
| `tests/sqlite/test_sqlite_application.py::test_hook_failure_blocks_commit_and_rollback_restores_usability` | R | tests/sqlite/test_sqlite_application.py:71 | sqlite | realign |
| `tests/sqlite/test_sqlite_application.py::test_normal_and_raw_commands_share_execute_and_explicit_commit` | R | tests/sqlite/test_sqlite_application.py:52 | sqlite | realign |
| `tests/sqlite/test_sqlite_application.py::test_parameters_environment_percent_literals_and_sql_error` | R | tests/sqlite/test_sqlite_application.py:93 | sqlite | realign |
| `tests/sqlite/test_sqlite_application.py::test_raw_commands_keep_partition_checks_and_formula_results` | R | tests/sqlite/test_sqlite_application.py:179 | sqlite | realign |
| `tests/sqlite/test_sqlite_application.py::test_sqlite_cli_reuses_existing_migrator_and_file_layout` | R | tests/sqlite/test_sqlite_application.py:122 | sqlite | realign |
| `tests/sqlite/test_sqlite_application.py::test_threads_and_named_connections_use_same_files_with_independent_state` | R | tests/sqlite/test_sqlite_application.py:103 | sqlite | realign |
| `tests/test_release_model_semantics.py::test_custom_types_forward_fk_inference_inverse_and_application_sql_actions` | R | tests/test_release_model_semantics.py:26 | tests (root) | realign |
| `tests/test_release_model_semantics.py::test_validation_embedding_and_explicit_form_match_and_remain_detached` | R | tests/test_release_model_semantics.py:47 | tests (root) | realign |

## G2 — R — 22 rows

Cause: Fixture builds the read compiler on the removed `contracts.ResolvedModel`/`Table`; DML assertions belong to `WriteCompiler` (doc 99, contracts 3 and 8).

Evidence: `src/asqueel/compiler.py:809` raises `QueryCompiler requires a hierarchical DbModel`.

Action: realign: build the hierarchical model; move DML assertions to `WriteCompiler`.

| nodeid | class | evidence | area | action |
|---|---|---|---|---|
| `tests/adapter_compiler/test_locking.py::test_non_select_lock_is_rejected[delete]` | R | tests/adapter_compiler/test_locking.py:17 | adapter_compiler | realign |
| `tests/adapter_compiler/test_locking.py::test_non_select_lock_is_rejected[insert]` | R | tests/adapter_compiler/test_locking.py:17 | adapter_compiler | realign |
| `tests/adapter_compiler/test_locking.py::test_non_select_lock_is_rejected[update]` | R | tests/adapter_compiler/test_locking.py:17 | adapter_compiler | realign |
| `tests/native_compiler/test_aliases.py::test_wildcard_excludes_dynamic_aliases_and_dml_defaults_stay_physical` | R | tests/native_compiler/test_aliases.py:34 | native_compiler | realign |
| `tests/native_compiler/test_compiler.py::test_dml_rejects_formula_writes_and_relation_paths` | R | tests/native_compiler/test_compiler.py:23 | native_compiler | realign |
| `tests/native_compiler/test_compiler.py::test_insert_values_mapping_and_default_values` | R | tests/native_compiler/test_compiler.py:23 | native_compiler | realign |
| `tests/native_compiler/test_compiler.py::test_quoted_logical_names_work_in_wildcards_predicates_and_returning[50%]` | R | tests/native_compiler/test_compiler.py:63 | native_compiler | realign |
| `tests/native_compiler/test_compiler.py::test_quoted_logical_names_work_in_wildcards_predicates_and_returning[\u03b1\u03c1\u03b9\u03b8\u03bc\u03cc\u03c2]` | R | tests/native_compiler/test_compiler.py:63 | native_compiler | realign |
| `tests/native_compiler/test_compiler.py::test_quoted_logical_names_work_in_wildcards_predicates_and_returning[a"b]` | R | tests/native_compiler/test_compiler.py:63 | native_compiler | realign |
| `tests/native_compiler/test_compiler.py::test_quoted_logical_names_work_in_wildcards_predicates_and_returning[a-b]` | R | tests/native_compiler/test_compiler.py:63 | native_compiler | realign |
| `tests/native_compiler/test_compiler.py::test_quoted_logical_names_work_in_wildcards_predicates_and_returning[citt\xe0]` | R | tests/native_compiler/test_compiler.py:63 | native_compiler | realign |
| `tests/native_compiler/test_compiler.py::test_quoted_logical_names_work_in_wildcards_predicates_and_returning[display name]` | R | tests/native_compiler/test_compiler.py:63 | native_compiler | realign |
| `tests/native_compiler/test_compiler.py::test_result_source_preserves_stable_identity_across_alias_and_physical_names` | R | tests/native_compiler/test_compiler.py:99 | native_compiler | realign |
| `tests/native_compiler/test_compiler.py::test_returning_formula_that_requires_join_is_rejected` | R | tests/native_compiler/test_compiler.py:81 | native_compiler | realign |
| `tests/native_compiler/test_compiler.py::test_update_collision_returning_and_line_comment` | R | tests/native_compiler/test_compiler.py:23 | native_compiler | realign |
| `tests/native_compiler/test_compiler.py::test_writes_need_predicate[ ]` | R | tests/native_compiler/test_compiler.py:23 | native_compiler | realign |
| `tests/native_compiler/test_compiler.py::test_writes_need_predicate[-- comment]` | R | tests/native_compiler/test_compiler.py:23 | native_compiler | realign |
| `tests/native_compiler/test_compiler.py::test_writes_need_predicate[/* comment */]` | R | tests/native_compiler/test_compiler.py:23 | native_compiler | realign |
| `tests/native_compiler/test_compiler.py::test_writes_need_predicate[None]` | R | tests/native_compiler/test_compiler.py:23 | native_compiler | realign |
| `tests/native_compiler/test_compiler.py::test_writes_need_predicate[]` | R | tests/native_compiler/test_compiler.py:23 | native_compiler | realign |
| `tests/native_compiler/test_subqueries.py::test_default_returning_excludes_transitive_virtual_dependencies` | R | tests/native_compiler/test_subqueries.py:53 | native_compiler | realign |
| `tests/native_compiler/test_subqueries.py::test_dml_default_excludes_subqueries_and_explicit_request_rejected` | R | tests/native_compiler/test_subqueries.py:42 | native_compiler | realign |

## G3 — R — 7 rows

Cause: Test calls DML methods (`insert`, `update`, `delete`) on the read compiler; DML lives in `WriteCompiler` (doc 99, contract 8).

Evidence: `AttributeError: QueryCompiler/PostgresCompiler object has no attribute insert/update/delete`.

Action: realign: compile DML through `db.write_compiler` or the table write cycle.

| nodeid | class | evidence | area | action |
|---|---|---|---|---|
| `tests/native_compiler/test_inverse_relations.py::test_inverse_does_not_enable_joined_dml[postgresql]` | R | tests/native_compiler/test_inverse_relations.py:41 | native_compiler | realign |
| `tests/native_compiler/test_inverse_relations.py::test_inverse_does_not_enable_joined_dml[sqlite]` | R | tests/native_compiler/test_inverse_relations.py:41 | native_compiler | realign |
| `tests/native_compiler/test_native_star.py::test_returning_keeps_all_physical_columns[postgresql]` | R | tests/native_compiler/test_native_star.py:34 | native_compiler | realign |
| `tests/native_compiler/test_native_star.py::test_returning_keeps_all_physical_columns[sqlite]` | R | tests/native_compiler/test_native_star.py:34 | native_compiler | realign |
| `tests/native_integration/test_postgres_vertical.py::test_python_error_rolls_back_transaction_and_database_remains_usable` | R | tests/native_integration/test_postgres_vertical.py:138 | native_integration | realign |
| `tests/native_integration/test_postgres_vertical.py::test_separate_database_transactions_keep_independent_commit_and_rollback` | R | tests/native_integration/test_postgres_vertical.py:154 | native_integration | realign |
| `tests/native_integration/test_row_policies.py::test_writes_soft_delete_restore_and_scope_isolation` | R | tests/native_integration/test_row_policies.py:118 | native_integration | realign |

## G4 — R — 7 rows

Cause: Test module imports removed API: `asqueel.query_plan` (QueryPlan, Fragment, SqlStatement), `asqueel.writes` (WriteMixin), `compiler.quote_identifier` (doc 99, contract 3).

Evidence: collection `ModuleNotFoundError` / `ImportError`.

Action: per row.

| nodeid | class | evidence | area | action |
|---|---|---|---|---|
| `tests/adapter_compiler/test_plans.py` | R | tests/adapter_compiler/test_plans.py:4 | adapter_compiler | realign — keep the `%` escaping of physical names and the identifier quoting on `prepare_sql` / `WriteCompiler`; drop the assertions on QueryPlan/Fragment structure |
| `tests/adapter_dialect/test_postgres.py` | R | tests/adapter_dialect/test_postgres.py:8 | adapter_dialect | realign — keep DEFAULT VALUES, RETURNING as a separate capability, and line comments that cannot swallow the following clause, on `WriteCompiler` |
| `tests/adapter_dialect/test_postgres_execution.py` | R | tests/adapter_dialect/test_postgres_execution.py:8 | adapter_dialect | realign — guard property (a line comment cannot remove the UPDATE predicate) restated on `WriteCompiler` |
| `tests/adapter_integration/test_postgres_pipeline.py` | R | tests/adapter_integration/test_postgres_pipeline.py:11 | adapter_integration | realign — explicit pipeline restated on `prepare_sql` / `CompiledQuery` / `db.execute` |
| `tests/application_table/test_handles.py` | R | tests/application_table/test_handles.py:1 | application_table | realign — 10 write-hook tests restated on the table write cycle (`table_crud.py`, `db_write.py`) |
| `tests/native_compiler/test_policies.py` | R | tests/native_compiler/test_policies.py:12 | native_compiler | realign — DML partition/draft guards on the write cycle; soft delete/restore have no write-side code, Phase 2 decides whether that part becomes O |
| `tests/test_wf_phase2_query_grouping.py` | R | tests/test_wf_phase2_query_grouping.py:7 | tests (root) | realign — keep the refusal of GROUP BY/HAVING outside SELECT on the current compilers |

## G5 — R — 2 rows

Cause: `SqlTable.insert` returns the record (legacy contract), not a result with `.rows`.

Evidence: `src/asqueel/table_crud.py:33-36`.

Action: realign: assert on the returned record; RETURNING rows through `sql_insert`.

| nodeid | class | evidence | area | action |
|---|---|---|---|---|
| `tests/adapter_integration/test_named_list_rows.py::test_returning_and_record_dict_keep_their_declared_interfaces[postgresql]` | R | tests/adapter_integration/test_named_list_rows.py:72 | adapter_integration | realign |
| `tests/adapter_integration/test_named_list_rows.py::test_returning_and_record_dict_keep_their_declared_interfaces[sqlite]` | R | tests/adapter_integration/test_named_list_rows.py:72 | adapter_integration | realign |

## G6 — R — 2 rows

Cause: Test calls `db.raw_insert('item', ...)`; the raw command is `SqlTable.sql_insert`.

Evidence: `src/asqueel/application_table.py:306`.

Action: realign: `db.table('<pkg>.item').sql_insert(records)`.

| nodeid | class | evidence | area | action |
|---|---|---|---|---|
| `tests/application_integration/test_raw_writes.py::test_raw_insert_list_results_defaults_and_no_implicit_commit[postgresql]` | R | tests/application_integration/test_raw_writes.py:114 | application_integration | realign |
| `tests/application_integration/test_raw_writes.py::test_raw_insert_list_results_defaults_and_no_implicit_commit[sqlite]` | R | tests/application_integration/test_raw_writes.py:114 | application_integration | realign |

## G7 — R — 1 rows

Cause: Test reads options through the removed `.config()` accessor (doc 99, contract 1: no `.config`).

Evidence: `AttributeError: DbTableObj object has no attribute config`.

Action: realign: read `item.model.options`.

| nodeid | class | evidence | area | action |
|---|---|---|---|---|
| `tests/test_native_option_expansion.py::test_declarative_options_are_preserved_without_new_columns_or_runtime_effects` | R | tests/test_native_option_expansion.py:203 | tests (root) | realign |

## G8 — R — 1 rows

Cause: Test passes `ui=` to `resolve_model`, whose signature is `resolve_model(builder)`.

Evidence: `src/asqueel/model.py:137`.

Action: realign: drop `ui=` and use the hierarchical model.

| nodeid | class | evidence | area | action |
|---|---|---|---|---|
| `tests/native_integration/test_postgres_vertical.py::test_native_model_compiler_runtime_and_import` | R | tests/native_integration/test_postgres_vertical.py:76 | native_integration | realign |

## G9 — R — 2 rows

Cause: Tutorial declares `x_name="customer"` and queries `@customer.name`; the relation path is the column name `@customer_id`, as in the legacy.

Evidence: `docs/guide/_examples/shop_tutorial.py:34,111`; `src/asqueel/compiler.py:226` `Relation @customer not found`; legacy `gnrsqlmodel/columns.py:180` looks up `'@%s' % self.name`, and `relation_name` (`model.py:251-287`) names only the inverse relation.

Action: realign: the tutorial (docs file) uses `@customer_id`.

| nodeid | class | evidence | area | action |
|---|---|---|---|---|
| `tests/documentation/test_examples.py::test_application_query_guide_against_tutorial_data` | R | collection | documentation | realign |
| `tests/documentation/test_examples.py::test_downloadable_tutorial` | R | collection | documentation | realign |

## G10 — R — 1 rows

Cause: Test declares `pkey='x,y'` without a compositeColumn; the legacy requires `pkey` to name a column, composite through `composed_of` (`gnrpy/gnr/sql/gnrsqlmodel/table.py:194-209`).

Evidence: `src/asqueel/object_tree.py:239` `Unknown column s.parent.x,y`.

Action: realign: declare a compositeColumn and use its name as pkey.

| nodeid | class | evidence | area | action |
|---|---|---|---|---|
| `tests/native_model/test_postgres.py::test_composite_fk_is_applied_and_enforced_by_postgres_migration` | R | collection | native_model | realign |

## Phase 2 — outcome

Every row above was realigned; its nodeid is collected and passes, except:

- `test_raw_writes.py::test_raw_list_late_python_failure_requires_rollback[postgresql|sqlite]` — deleted, approved at the Phase 2 gate (it failed only through `onWritten`; `sql_insert` runs no Python code).
- `test_handles.py::test_delete_hook_cannot_redirect_the_saved_key` — deleted, approved at the Phase 2 gate (the write cycle reproduces the legacy, d-legacy-bugs). The file-level row stays: the other tests of the module are realigned, some renamed.
- `test_compiler.py::test_writes_need_predicate[...]` — the five parametrized nodeids become the single `test_writes_need_predicate`: WriteCompiler takes no free predicate, every write uses a key WHERE.
- Rows whose whole test is O, marked `xfail(strict=True)`: `test_write_hooks.py::test_exactly_one_locked_record_before_any_hook[update|delete]` (draft 1), `test_write_hooks.py::test_pre_hook_holds_postgres_row_lock` (draft 10), `test_compiler.py::test_quoted_logical_names_work_in_wildcards_predicates_and_returning[*]` (draft 4), `test_policies.py::test_allowed_only_insert_requires_value_and_empty_allowed_refuses_insert` (asqueel#15).

Assertions on behaviour removed by closed write-cycle decisions were rewritten to the decided mechanism or dropped (notes.md § Phase 2, foreman clarify 1). Assertions on O behaviour that was part of an otherwise R test moved into new xfail tests next to it.

### B rows fixed in code

- WriteCompiler: a `--` line comment in a `sql_value` removed the clause that followed it (on UPDATE the WHERE, so every row was updated). Each `sql_value` is now followed by a newline (`src/asqueel/write_compiler.py`). Tests: `tests/adapter_dialect/test_postgres.py::test_clauses_have_fixed_separators_without_repairing_expression_text`, `tests/adapter_dialect/test_postgres_execution.py`.
- `query(...).sql_update/sql_delete` copied `group_by`/`having` into the key SELECT; they are now refused with `UnsupportedFeatureError` (`src/asqueel/application_table.py`, `_key_plan`). Test: `tests/test_wf_phase2_query_grouping.py`.

### O rows — issue drafts for Phase 3

| draft | problem | xfail tests | evidence |
|---|---|---|---|
| 1 | `recordToUpdate` is missing: no hooked update/delete of exactly one record selected by a `where` and read with a lock (RecordNotFoundError / RecordMultipleRowsError before the hooks). Deferred feature. | `test_raw_writes.py::test_ordinary_write_by_where_needs_exactly_one_record[*]`, `test_write_hooks.py::test_exactly_one_locked_record_before_any_hook[*]` | `src/asqueel/db_write.py:35-50`; write-cycle plan d-reverse |
| 2 | The hierarchical DbModel has no JSON round trip: `model_to_json`/`model_from_json` raise TypeError on a DbModel. | `test_release_model_semantics.py::test_validation_model_survives_a_json_round_trip`, `test_native_option_expansion.py::test_declarative_options_survive_a_json_round_trip` | `src/asqueel/model_codec.py:16-30,50` |
| 3 | A `%` in a physical table or column name is not escaped for psycopg; such a table cannot be read or written on PostgreSQL. | `test_compiler.py::test_insert_escapes_percent_in_physical_names`, `test_plans.py::test_compiled_sql_escapes_percent_in_physical_names` | `src/asqueel/drivers/sql.py:110-111` |
| 4 | Quoted logical names `$"..."` are not supported by the read compiler; DML binds a logical name that is not an identifier to a truncated parameter, and a missing binding becomes None. | `test_compiler.py::test_quoted_logical_names_work_in_wildcards_predicates_and_returning[*]` | `src/asqueel/compiler.py:28`, `src/asqueel/drivers/sql.py:13,104-105` |
| 5 | WriteCompiler does not enforce the dialect capabilities: DEFAULT VALUES is emitted without `default_values`, a missing `returning_insert` silently drops RETURNING. | `test_postgres.py::test_missing_write_capabilities_are_rejected` | `src/asqueel/write_compiler.py` (`_insert_sql`, `_returning`) |
| 6 | `inspect_postgres` still returns the removed `contracts.ResolvedModel`, which QueryCompiler rejects. | `test_postgres_vertical.py::test_imported_model_compiles_selects` | `src/asqueel/importers.py:207`, `src/asqueel/compiler.py:808-809` |
| 7 | `pkey='a,b'` is accepted by `WriteCompiler.pkeys` and described by the `table` grammar as comma-joined names, while the legacy requires `pkey` to name one column (composite through `composed_of`) and `object_tree.physical_columns` fails on it. No test. | — | `src/asqueel/write_compiler.py:34-42`, `src/asqueel/elements.py:179`, `src/asqueel/object_tree.py:386-391`; legacy `gnrsqlmodel/table.py:194-209` |
| 8 | `_key_where` writes `__pkey__N` into the record parameters without a collision check; a record key `__pkey__0` is overwritten silently. No test. | — | `src/asqueel/write_compiler.py` (`_key_where`; `_selection_where` has the check) |
| 9 | A schema-tag model (SqlBuilder) cannot set a table prefix: the schema validator refuses `sqlprefix`, and `x_sql_prefix`, documented in `docs/native-model.md:13-15`, is ignored by `tableSqlName`. No test. | — | `src/asqueel/object_tree.py:146-153` |
| 10 | A SELECT on a table whose pkey is a compositeColumn fails with `virtual/composite columns are not connected yet`; `record(...)` on such a table fails too. Known read-path limit (write-cycle plan, p-sql status). | `test_write_hooks.py::test_record_read_with_lock_includes_the_draft_row`, `test_write_hooks.py::test_pre_hook_holds_postgres_row_lock`, `test_write_hooks.py::test_logically_deleted_record_is_hidden_until_restored`, `test_handles.py::test_composite_record_reads_through_the_physical_names` | `src/asqueel/compiler.py:63-66,570-571` |
| 11 | `docs/guide/models.md` keeps prose that contradicts the code: `originalColumn` and `model.ui` (:160-162) do not exist; "writes with an alias in their value mapping fail explicitly" and `RETURNING '*'` (:188-189) contradict d-record-keys and d-return. No test. | — | `docs/guide/models.md:160-162,188-189` |

Partitions on write are covered by the open issue asqueel-org/asqueel#15; their xfail reason is `asqueel#15: ...` and Phase 3 drafts nothing for them: `test_postgres_policies.py::test_application_insert_fills_the_partition_field`, `test_sqlite_application.py::test_raw_insert_refuses_and_fills_the_partition`, `test_policies.py::test_dml_partition_guards_and_autofill`, `test_policies.py::test_allowed_only_insert_requires_value_and_empty_allowed_refuses_insert`, `test_policies.py::test_relational_partition_writes_are_explicitly_unsupported`, `test_row_policies.py::test_writes_fill_and_guard_the_partition`.
