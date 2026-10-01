# Recovery caller review index

Candidate numbers match `recovery_callers_catalog.json` at legacy revision
`fa35e5adfa6ad1b269f3a22a9b12c4c1ee6513ea`. Classification is source review
unless explicitly marked executed; execution uses the bounded fixture described in
[report 21](../21-recovery-callers.md). Syntactic later calls do not prove reachability.

| ID | Source / scope / try line | Classification | Evidence / limit |
|---|---|---|---|
| RC01 | `gnrpy/gnr/app/gnrapp.py:1817` — `GnrApp.importTableFromLegacyDb` | Preflight/fallback | Lookup, validation, parsing or non-database update; not evidence for committing a failed database write. |
| RC02 | `gnrpy/gnr/app/gnrdbo.py:1930` — `AttachmentTable.trigger_onDeletedAtc` | Handled external error | Storage cleanup error is caught within the helper/hook; no escaping write failure. |
| RC03 | `gnrpy/gnr/core/loghandlers/gnrapp.py:15` — `GnrAppLoggingHandler._process_record` | Executed: logger risk | Python hook failure is swallowed without rollback. Next log commits partial work in legacy; native blocks both until recovery. |
| RC04 | `gnrpy/gnr/core/loghandlers/postgres.py:69` — `GnrPostgresqlLoggingHandler._process_record` | Outside native application recovery | Raw driver, adapter retry, read-only utility or remote RPC; no application hook continuation contract established. |
| RC05 | `gnrpy/gnr/db/cli/gnrmigrate.py:211` — `main` | Rollback/close before reuse | Handler rolls back, rethrows after rollback, or closes the connection before subsequent work. |
| RC06 | `gnrpy/gnr/sql/adapters/_gnrbasepostgresadapter.py:401` — `PostgresSqlDbBaseAdapter._createDb` | Outside native application recovery | Raw driver, adapter retry, read-only utility or remote RPC; no application hook continuation contract established. |
| RC07 | `gnrpy/gnr/sql/adapters/gnrmysql.py:139` — `SqlDbAdapter.createDb` | Outside native application recovery | Raw driver, adapter retry, read-only utility or remote RPC; no application hook continuation contract established. |
| RC08 | `gnrpy/gnr/sql/adapters/gnrsqlite.py:161` — `SqlDbAdapter.execute` | No exception handler | Try/finally cleanup only; lexical candidate, not swallowed-error recovery. |
| RC09 | `gnrpy/gnr/sql/adapters/gnrsqlite.py:182` — `SqlDbAdapter.raw_fetch` | No exception handler | Try/finally cleanup only; lexical candidate, not swallowed-error recovery. |
| RC10 | `gnrpy/gnr/sql/adapters/gnrsqlite.py:508` — `GnrSqliteCursor.execute` | Outside native application recovery | Raw driver, adapter retry, read-only utility or remote RPC; no application hook continuation contract established. |
| RC11 | `gnrpy/gnr/sql/adapters/gnrsqlite.py:516` — `GnrSqliteCursor.execute` | Outside native application recovery | Raw driver, adapter retry, read-only utility or remote RPC; no application hook continuation contract established. |
| RC12 | `gnrpy/gnr/sql/gnrsql/connections.py:52` — `ConnectionMixin.closeConnection` | Connection cleanup | Suppresses errors during rollback/close; not continuation of an application write. |
| RC13 | `gnrpy/gnr/sql/gnrsql/execute.py:123` — `ExecuteMixin.execute` | Rollback/close before reuse | Handler rolls back, rethrows after rollback, or closes the connection before subsequent work. |
| RC14 | `gnrpy/gnr/sql/gnrsqlmigration/executor.py:290` — `ExecutorMixin.verifyConversionBackups` | Migration-only boundary | Backup verification/DDL cleanup reports errors; not a tested application hook recovery contract. |
| RC15 | `gnrpy/gnr/sql/gnrsqlmodel/model.py:240` — `DbModel.addRelation` | Preflight/fallback | Lookup, validation, parsing or non-database update; not evidence for committing a failed database write. |
| RC16 | `gnrpy/gnr/sql/gnrsqltable/triggers.py:220` — `TriggersMixin.check_updatable` | Preflight/fallback | Lookup, validation, parsing or non-database update; not evidence for committing a failed database write. |
| RC17 | `gnrpy/gnr/sql/gnrsqltable/triggers.py:229` — `TriggersMixin.check_deletable` | Preflight/fallback | Lookup, validation, parsing or non-database update; not evidence for committing a failed database write. |
| RC18 | `gnrpy/gnr/sql/gnrsqlutils.py:203` — `SqlModelChecker.addExtensions` | Executed: DDL recovery | Original extension methods, real failing DDL: automatic rollback in both; isolate unrelated work. Report 27. |
| RC19 | `gnrpy/gnr/sql/gnrsqlutils.py:611` — `SqlModelChecker.changeRelations` | Rollback/close before reuse | Handler rolls back, rethrows after rollback, or closes the connection before subsequent work. |
| RC20 | `gnrpy/gnr/sql/pgutils.py:36` — `PgDbUtils._query_to_json` | Outside native application recovery | Raw driver, adapter retry, read-only utility or remote RPC; no application hook continuation contract established. |
| RC21 | `gnrpy/gnr/web/_gnrbasewebpage.py:574` — `GnrBaseWebPage.deleteRecordCluster` | Returns error / skips success commit | Inspected method does not commit after its caught failure. Caller cleanup is not certified for every entry. |
| RC22 | `gnrpy/gnr/web/_gnrbasewebpage.py:594` — `GnrBaseWebPage.deleteDbRow` | Returns error / skips success commit | Inspected method does not commit after its caught failure. Caller cleanup is not certified for every entry. |
| RC23 | `gnrpy/gnr/web/batch/btcbase.py:70` — `BaseResourceBatch.__call__` | Executed: independent log | Batch reports failure and commits log on system connection; failed main work disappears on cleanup. |
| RC24 | `gnrpy/gnr/web/batch/btcbase.py:87` — `BaseResourceBatch.__call__` | Rethrows | Error while reporting is rethrown. |
| RC25 | `gnrpy/gnr/web/batch/btcbase.py:117` — `BaseResourceBatch._post_process` | Missing-commit diagnostic | Auto-commit failure is reported; handler does not force a later commit. |
| RC26 | `gnrpy/gnr/web/batch/btcmail.py:43` — `BaseResourceMail._send_one_email_legacy` | Executed: success-log DB failure | SQL recovery matches; Python failure requires rollback before fallback log. External send cannot be undone. Report 27. |
| RC27 | `gnrpy/gnr/web/cli/gnrstoragemove.py:95` — `StorageMover.run` | No exception handler | Try/finally cleanup only; lexical candidate, not swallowed-error recovery. |
| RC28 | `gnrpy/gnr/web/cli/gnrstoragemove.py:104` — `StorageMover.run` | Preflight/fallback | Lookup, validation, parsing or non-database update; not evidence for committing a failed database write. |
| RC29 | `gnrpy/gnr/web/cli/gnrstoragemove.py:109` — `StorageMover.run` | Preflight/fallback | Lookup, validation, parsing or non-database update; not evidence for committing a failed database write. |
| RC30 | `gnrpy/gnr/web/cli/gnrtaskcontrol.py:103` — `main` | Outside native application recovery | Raw driver, adapter retry, read-only utility or remote RPC; no application hook continuation contract established. |
| RC31 | `gnrpy/gnr/web/gnrwebpage_proxy/apphandler/misc.py:237` — `MiscMixin.deleteDbRows` | Returns error / skips success commit | Inspected method does not commit after its caught failure. Caller cleanup is not certified for every entry. |
| RC32 | `gnrpy/gnr/web/gnrwebpage_proxy/apphandler/misc.py:293` — `MiscMixin.archiveDbRows` | Returns error / skips success commit | Inspected method does not commit after its caught failure. Caller cleanup is not certified for every entry. |
| RC33 | `gnrpy/gnr/web/gnrwsgisite.py:457` — `GnrWsgiSite.__init__` | Preflight/fallback | Lookup, validation, parsing or non-database update; not evidence for committing a failed database write. |
| RC34 | `gnrpy/gnr/web/gnrwsgisite_proxy/gnrresourceloader.py:117` — `ResourceLoader.find_webtools` | Preflight/fallback | Lookup, validation, parsing or non-database update; not evidence for committing a failed database write. |
| RC35 | `gnrpy/tests/sql/common.py:149` — `BaseGnrSqlTest.teardown_class` | No exception handler | Try/finally cleanup only; lexical candidate, not swallowed-error recovery. |
| RC36 | `gnrpy/tests/sql/conftest.py:164` — `_db_pg` | No exception handler | Try/finally cleanup only; lexical candidate, not swallowed-error recovery. |
| RC37 | `gnrpy/tests/sql/conftest.py:174` — `_db_pg` | No exception handler | Try/finally cleanup only; lexical candidate, not swallowed-error recovery. |
| RC38 | `gnrpy/tests/sql/test_db_notify.py:136` — `TestDbNotifyPayload.test_notify_true_insert` | No exception handler | Try/finally cleanup only; lexical candidate, not swallowed-error recovery. |
| RC39 | `gnrpy/tests/sql/test_db_notify.py:166` — `TestDbNotifyPayload.test_notify_fields_delete` | No exception handler | Try/finally cleanup only; lexical candidate, not swallowed-error recovery. |
| RC40 | `gnrpy/tests/sql/test_db_notify.py:194` — `TestDbNotifyPayload.test_notify_fields_update_changed` | No exception handler | Try/finally cleanup only; lexical candidate, not swallowed-error recovery. |
| RC41 | `gnrpy/tests/sql/test_db_notify.py:225` — `TestDbNotifyPayload.test_notify_fields_update_no_change` | No exception handler | Try/finally cleanup only; lexical candidate, not swallowed-error recovery. |
| RC42 | `gnrpy/tests/web/gnrstoragehandler_test.py:1014` — `TestStorageHandler.test_relative_storage_from_service_record` | No exception handler | Try/finally cleanup only; lexical candidate, not swallowed-error recovery. |
| RC43 | `projects/gnrcore/packages/adm/model/backup.py:36` — `Table.deleteBackupFile` | Handled external error | Storage cleanup error is caught within the helper/hook; no escaping write failure. |
| RC44 | `projects/gnrcore/packages/adm/model/preference.py:113` — `Table.loadPreference` | Preflight/fallback | Lookup, validation, parsing or non-database update; not evidence for committing a failed database write. |
| RC45 | `projects/gnrcore/packages/adm/model/userobject.py:156` — `Table.checkResourceUserObject` | Executed: visitor write failure | Custom directory walk can swallow hook OSError; adapter must narrow catch or rollback. SQL propagates. Fixture filesystem. Report 27. |
| RC46 | `projects/gnrcore/packages/adm/resources/login.py:522` — `LoginComponent.login_createNewUser` | Returns error / skips success commit | Inspected method does not commit after its caught failure. Caller cleanup is not certified for every entry. |
| RC47 | `projects/gnrcore/packages/adm/resources/login.py:594` — `LoginComponent.login_confirmNewPassword` | Returns error / skips success commit | Inspected method does not commit after its caught failure. Caller cleanup is not certified for every entry. |
| RC48 | `projects/gnrcore/packages/docu/tests/test_docu_resolver.py:265` — `TestDocuResolver.test_homonym_candidates_are_bounded` | No exception handler | Try/finally cleanup only; lexical candidate, not swallowed-error recovery. |
| RC49 | `projects/gnrcore/packages/email/lib/imap.py:61` — `ImapReceiver.receive` | Executed: rollback before reuse | Active IMAP receiver rolls back bad message, advances checkpoint, then accepts next message; Python/SQL/deferred cases tested. |
| RC50 | `projects/gnrcore/packages/email/lib/utils.py:67` — `ImapReceiver.receive` | Executed: old helper boundary | Attachment Python failure can leak partial writes in legacy; native blocks reuse. Rollback required before continuation. External users unknown. Report 27. |
| RC51 | `projects/gnrcore/packages/email/model/message.py:390` — `Table.sendMessage` | Executed: queue-removal DB failure | Success SMTP stub followed by DB removal error: SQL recovery matches; Python failure requires explicit recovery. No actual mail sent. Report 27. |
| RC52 | `projects/gnrcore/packages/email/resources/services/mailproxy/mailproxy.py:370` — `Main.activateService` | Returns error / skips success commit | Inspected method does not commit after its caught failure. Caller cleanup is not certified for every entry. |
| RC53 | `projects/gnrcore/packages/email/resources/tables/account/action/receive_mail.py:21` — `Main.do` | Rollback/close before reuse | Handler rolls back, rethrows after rollback, or closes the connection before subsequent work. |
| RC54 | `projects/gnrcore/packages/email/webpages/mailproxy/mp_endpoint.py:220` — `GnrCustomWebPage._update_from_delivery_report` | Preflight/fallback | Lookup, validation, parsing or non-database update; not evidence for committing a failed database write. |
| RC55 | `projects/gnrcore/packages/email/webpages/mailproxy/mp_endpoint.py:231` — `GnrCustomWebPage._update_from_delivery_report` | Preflight/fallback | Lookup, validation, parsing or non-database update; not evidence for committing a failed database write. |
| RC56 | `projects/gnrcore/packages/multidb/main.py:475` — `MultidbTable._checkSyncAll_store` | Multi-store boundary | Bulk/raw fallback bypasses hooks; SQL failure rollback precedes fallback. Not evidence for retaining failed hook writes. |
| RC57 | `projects/gnrcore/packages/multidb/model/_packages/adm/user.py:14` — `Table.newStoreUser` | Returns error / skips success commit | Inspected method does not commit after its caught failure. Caller cleanup is not certified for every entry. |
| RC58 | `projects/gnrcore/packages/sys/model/locked_record.py:28` — `Table.lockRecord` | Rollback/close before reuse | Handler rolls back, rethrows after rollback, or closes the connection before subsequent work. |
| RC59 | `projects/gnrcore/packages/sys/model/upgrade.py:74` — `Table.runUpgrade` | Executed: rollback before error log | Upgrade rolls back before persisting error record in new transaction; Python/deferred cases tested. |
| RC60 | `projects/gnrcore/packages/sys/webpages/ep_table.py:79` — `GnrCustomWebPage._get_documentNode` | Preflight/fallback | Lookup, validation, parsing or non-database update; not evidence for committing a failed database write. |
| RC61 | `resources/common/_unused/standardRecordViews.py:136` — `RecordAndViews.rpc_save` | Returns error / skips success commit | Inspected method does not commit after its caught failure. Caller cleanup is not certified for every entry. |
