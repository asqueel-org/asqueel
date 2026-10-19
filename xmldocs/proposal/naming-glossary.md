<!-- generated from naming-glossary.xml by xmldocs: do not edit, edit the XML -->

## Glossario dei nomi del linguaggio asqueel
*Proposal · proposal/naming-glossary · 2026-10-19 · draft*

### Problem

Il team deve prendere le decisioni finali sui nomi del linguaggio asqueel.

Il criterio è questo. Un nome che è una parola del nostro linguaggio segue la regola GenroPy. Il codice interno segue l'idioma Python.

La regola GenroPy ha tre punti:

- le parole si scrivono in camelCase: `formulaColumn`, `onInserting`;
- `_` separa solo un namespace dal nome: `sql_onDelete`, `trigger_onInserting`, `name_long`;
- una parola già singola resta singola: `rowcaption`, `tabletype`.

Questo documento elenca i nomi che un utente scrive o sovrascrive. Per ogni nome riporta la controparte GenroPy, quando esiste, e se il nome segue la regola. I nomi con grafia aperta rimandano a una decisione.

### Current state

#### Legenda e fonti

La colonna **Regola** ha quattro valori:

- `sì`: il nome segue la regola.
- `legacy`: il nome non segue la regola. È la grafia GenroPy e resta invariata.
- `cambiato`: il nome asqueel diverge dalla grafia GenroPy, per una decisione già presa. Il nome asqueel segue la regola.
- `aperto`: la grafia è aperta per il team. La cella Note indica la decisione.

Fonti asqueel: `src/asqueel/__init__.py`, `docs/grammar.md`, `docs/guide/legacy-features.md` e le classi pubbliche. Fonte GenroPy: il ramo `origin/develop` della repo genropy al commit `b5364b62eb` del 2026-10-19. I file GenroPy citati sono sotto `gnrpy/gnr/`.

`docs/design/112-legacy-inventory.md` è del 2026-10-17. È precedente alle Macro 4-6 e ha nomi superati, per esempio `on_delete` e `inverse=`. Questo glossario non lo usa per i nomi attuali.

- `READ` `sql/gnrsqlmodel/model.py:643` · 2026-10-19 — In GenroPy le dichiarazioni del modello sono metodi: `pkg.table()`, `tbl.column()`, `tbl.formulaColumn()`, `col.relation()`. In asqueel le stesse dichiarazioni sono elementi della grammar con lo stesso nome.

#### Elementi della grammar

*Elementi*

| asqueel | GenroPy | Regola | Note |
|---|---|---|---|
| `db`, `connection` | — | sì | configurazione |
| `schemas`, `schema`, `extensions`, `extension` | — | sì | `extension` sostituisce `SqlMigrator(extensions=)` |
| `packages`, `package` | `package()` | sì |  |
| `tables`, `table` | `table()` | sì |  |
| `columns`, `column` | `column()` | sì |  |
| `virtual_columns` | — (contenitore nuovo) | aperto |  (→ dn-elements). In GenroPy `virtual_columns` è una property del modello e un'opzione di query. |
| `composites`, `constraints`, `indexes` | — | sì | contenitori |
| `aliasColumn` | `aliasColumn()` | sì |  |
| `formulaColumn` | `formulaColumn()` | sì |  |
| `subQueryColumn` | `subQueryColumn()` | sì |  |
| `pyColumn` | `pyColumn()` | sì |  |
| `bagItemColumn` | `bagItemColumn()` | sì |  |
| `compositeColumn` | `compositeColumn()` | sì |  |
| `joinColumn` | `joinColumn()` | sì | solleva sempre un errore |
| `constraint`, `index` | `index()` | sì | `constraint` è nuovo |
| `relation` | `relation()` | sì |  |
| `weak_relation` | — | aperto |  (→ dn-elements) |
| `virtualRelation` | — | sì | nuovo, solo dentro `aggr` |
| `colgroup` | `colgroup()` | sì |  |
| `sys_fields` | `sysFields(tbl, …)` (`app/gnrdbo.py:324`) | aperto |  (→ dn-elements). La grafia GenroPy segue la regola, quella asqueel no. |
| `options`, `reset`, `driver`, `requires`, `type` | `type` corrisponde a `custom_type_<dtype>()` | sì |  |
| `validation`, `encryption` | — | sì |  |
| `hierarchical` | `sysFields(hierarchical=)` | sì |  |
| `auto_counter` | `sysFields(counter=)` | aperto |  (→ dn-elements) |
| `relative_index` | `sysFields(relidx=)` | aperto |  (→ dn-elements) |
| `dynamic_fields` | `sysFields(df=)` | aperto |  (→ dn-elements) |
| `record_hash` | `sysFields(md5=)` | aperto |  (→ dn-elements) |
| `full_update` | `sysFields(full_upd=)` | aperto |  (→ dn-elements) |
| `system_records` | `sysFields(sysrecords=)` | aperto |  (→ dn-elements) |
| `enabled_when` | — | aperto |  (→ dn-elements) |
| `protection` | `sysFields(useProtectionTag=)` | sì |  |
| `audit`, `release`, `retention`, `broadcast`, `archive`, `attachments`, `numbering` | — | sì | solo dichiarati: una scrittura sulla table viene rifiutata |

#### Attributi di table e package

*table*

| asqueel | GenroPy | Regola | Note |
|---|---|---|---|
| `name`, `pkey`, `comment`, `sqlname`, `sqlschema`, `lookup`, `tabletype`, `rowcaption` | uguali | sì |  |
| `name_long`, `name_short`, `name_full`, `name_plural` | uguali | sì | namespace `name_` |
| `caption_field`, `newrecord_caption`, `order_by` | uguali | legacy |  |
| `pkey_columns`, `pkey_columns_joiner` | uguali (`sql/gnrsqltable/utils.py:112`) | legacy |  |
| `lastTS`, `logicalDeletionField`, `draftField`, `protectionColumn` | uguali | sì | ripristinati dalla Macro 4 al posto di `x_draft_field` e simili |
| `partition_<field>` | uguale | sì | sostituisce `x_partition` e `options().partition()` |
| `deletable` | — (non è un attributo GenroPy) | sì |  |
| `x_table_class`, `x_expanded_legacy`, `x_logical_pkey` | — | aperto |  (→ dn-x-attrs) |

*package*

| asqueel | GenroPy | Regola | Note |
|---|---|---|---|
| `name`, `sqlschema`, `sqlprefix`, `comment`, `path` | uguali, tranne `path` | sì | `path` carica il layout GenroPy |
| `name_long`, `name_short`, `name_full` | uguali | sì |  |
| `config_attributes()`, `custom_type_<dtype>()`, `config_db(self, pkg)` | uguali | legacy | metodi delle classi `Package` e `Table` del layout GenroPy |

#### Attributi di column

*column*

| asqueel | GenroPy | Regola | Note |
|---|---|---|---|
| `name`, `dtype`, `size`, `default`, `notnull`, `unique`, `indexed`, `sqlname`, `comment`, `group`, `format`, `unmodifiable` | uguali | sì | `'name::dtype'` resta valido |
| `name_long`, `name_short`, `name_full` | uguali | sì |  |
| `onInserting`, `onUpdating`, `onDeleting`, `onInserted`, `onUpdated`, `onDeleted` | uguali | sì | il valore nomina un metodo `trigger_<name>` |
| `trigger_table`, `sql_value` | uguali | sì | namespace |
| `print_width` | uguale (`sql/gnrsqlmodel/columns.py:110`) | legacy |  |
| `sql_default` | `sqldefault` | cambiato | Macro 4 |
| `sql_extra` | `extra_sql` | cambiato | Macro 4 |
| `sql_generatedExpression` | `generated_expression` | cambiato | Macro 4 |
| `sql_pg_*`, `sql_sqlite_*` | — | sì | varianti per dialetto, Macro 4 |
| `validate_*` | uguale, nel layer web | sì | `values` diventa `validate_values` |
| `read_only` | `readOnly` (`app/gnrdbo.py:350`) | aperto |  (→ dn-read-only) |
| `default_from` | — | aperto |  (→ dn-default-from) |
| `x_identity`, `x_generation` | — | aperto |  (→ dn-x-attrs) |

#### Attributi delle colonne virtuali

*aliasColumn, formulaColumn, subQueryColumn, pyColumn, bagItemColumn, compositeColumn*

| asqueel | GenroPy | Regola | Note |
|---|---|---|---|
| `relation_path` (aliasColumn) | uguale | legacy |  |
| `sql_formula`, `select`, `exists`, `static`, `var_*`, `select_*`, `exists_*` (formulaColumn) | uguali | sì | la Macro 5 ha tolto `expression=`, `parameters=`, `subqueries=`, `handler=` |
| `query`, `mode` (subQueryColumn) | uguali | sì |  |
| `aggr` (subQueryColumn) | — (GenroPy usa internamente `subquery_aggr=mode`) | sì | nuovo, Macro 5 |
| `py_method`, `required_columns` (pyColumn) | uguali | legacy |  |
| `method` (pyColumn) | — | sì |  |
| `bagcolumn`, `itempath` (bagItemColumn) | uguali | sì |  |
| `columns`, `unique` (compositeColumn) | uguali | sì |  |
| `relation`, `table`, `condition`, `ask` (virtualRelation) | — | sì |  |

#### Attributi di relation e weak_relation

*relation*

| asqueel | GenroPy | Regola | Note |
|---|---|---|---|
| `to` | primo argomento posizionale `related_column` | sì |  |
| `onDelete`, `onUpdate`, `onDuplicate`, `deferred`, `between`, `cnd` | uguali | sì | la Macro 2 ha ripristinato `onDelete` e `onUpdate` al posto di `on_delete` e `on_update` |
| `onDelete_sql`, `onUpdate_sql` | uguali | legacy | la Macro 2 ha scartato `sql_onDelete` |
| `one_name`, `many_name`, `one_one`, `one_group`, `many_group`, `many_order_by`, `eager_one`, `eager_many` | uguali | legacy |  |
| `relation_name`, `external_relation`, `resolver_kwargs`, `join_on` | uguali | legacy | `relation_name` sostituisce `inverse=` e `back_reference=` |
| `name`, `indexed`, `deferrable` | — | sì |  |
| `foreign_key`, `case_insensitive` | `mode='foreignkey'`, `mode='insensitive'` | aperto |  (→ dn-relation-attrs) |
| `initially_deferred`, `constraint_name` | — (solo campi interni della migrazione) | aperto |  (→ dn-relation-attrs) |
| `x_weak`, `x_canonical`, `x_name` | — | aperto |  (→ dn-x-attrs) |

#### Attributi degli altri elementi

*index, constraint, sys_fields, hierarchical e opzioni*

| asqueel | GenroPy | Regola | Note |
|---|---|---|---|
| `columns`, `name`, `unique` (index) | uguali (`sql/gnrsqlmodel/model.py:1326`) | sì | nome di default `<table>_<cols>_key`, Macro 4 |
| `method`, `where`, `tablespace` (index) | — | sì |  |
| `with_options` (index); `constraint_type`, `check_clause` (constraint) | — (solo campi interni degli adapter) | aperto |  (→ dn-element-attrs) |
| `id`, `ins`, `upd`, `ldel`, `draft`, `group`, `enabled`, `syscode` (sys\_fields) | argomenti di `sysFields`, tranne `enabled` e `syscode`; `draft` era `draftField` | sì |  |
| `user_ins`, `user_upd`, `group_name` (sys\_fields) | argomenti di `sysFields` | legacy |  |
| `columns`, `parent`, `depth` (hierarchical) | `depth` era `hdepth` | sì |  |
| `root_id`, `virtual_roots`, `linked_to` (hierarchical) | `hierarchical_root_id`, `hierarchical_virtual_roots`, `hierarchical_linked_to` | aperto |  (→ dn-element-attrs). Senza il namespace `hierarchical_` il `_` separa due parole. |
| `caption_field` (hierarchical) | uguale a `caption_field` di table | legacy |  |
| `scope`, `field` (auto\_counter); `templates`, `source` (dynamic\_fields); `algorithm` (record\_hash); `mode` (audit, encryption); `days` (retention); `preference` (enabled\_when) | — | sì |  |
| `version_field` (audit) | — | aperto |  (→ dn-element-attrs) |
| `name_long`, `name_short` e `col_*` (colgroup) | uguali | sì | `colgroup_label` e `group_<name>` sollevano un errore |
| `connect_timeout`, `application_name`, `sslmode`, `sslrootcert`, `cached_statements` (driver) | — | sì | nomi dei parametri dei driver PostgreSQL e sqlite3: fuori dal linguaggio |

#### Metodi e hook di table

*table*

| asqueel | GenroPy | Regola | Note |
|---|---|---|---|
| `query()`, `insert()`, `update()`, `delete()`, `insertOrUpdate()`, `lock()` | uguali (`sql/gnrsqltable/crud.py`) | sì |  |
| `column()`, `db`, `model`, `fullname`, `pkeys`, `currentTrigger` | uguali | sì |  |
| `checkPkey()`, `newPkeyValue()`, `pkeyValue()` | uguali | sì |  |
| `deleteRelated()`, `updateRelated()`, `archiveRelatedRecords()` | uguali | sì | `onArchivingRecord` manca |
| `sql_insert()`, `sql_update()`, `sql_delete()` | `raw_insert()`, `insertMany()`, `raw_update()`, `raw_delete()` | cambiato | namespace `sql_` |
| `trigger_onInserting`, `trigger_onInserted`, `trigger_onUpdating`, `trigger_onUpdated`, `trigger_onDeleting`, `trigger_onDeleted` | uguali (`sql/gnrsqltable/triggers.py:112`) | sì | override |
| `protect_update`, `protect_delete`, `protect_validate` | uguali | sì | override |
| `protect_draft` | uguale (`app/gnrdbo.py:1084`) | sì | override facoltativo; `dbo_onInserting` e simili sono rimossi |
| `trigger_assignCounters`, `trigger_releaseCounters`, `trigger_setTSNow`, `trigger_setCurrentUser` | uguali | sì |  |
| `trigger_hierarchical_before`, `trigger_hierarchical_after` | uguali (`app/gnrdbo.py:753`) | legacy |  |
| `trigger_<name>` | uguale | sì | chiamato dagli attributi `onInserting` e simili |
| `exception(exception, record, msg)` | uguale (`sql/gnrsqltable/table.py:92`) | sì | valori: `'save'`, `'delete'`, `'protect_update'`, `'protect_delete'`, `'protect_validate'`, `'business_logic'`, `'standard'` |
| `formulaColumn_<x>()`, `sql_formula_<name>()`, `subquery_<name>()`, `env_<name>()`, `pyColumn_<name>()` | uguali | sì | namespace |
| `hierarchicalHandler` | — | sì |  |

#### Opzioni e metodi di query

*table.query(…) e SqlQuery*

| asqueel | GenroPy | Regola | Note |
|---|---|---|---|
| `columns`, `where`, `sqlparams`, `limit`, `offset`, `distinct`, `having`, `bagFields`, `addPkeyColumn` | uguali (`sql/gnrsqltable/query.py:125`) | sì |  |
| `order_by`, `group_by`, `for_update` | uguali | legacy |  |
| `exclude_draft`, `exclude_logical_deleted`, `ignore_partition` | `excludeDraft`, `excludeLogicalDeleted`, `ignorePartition` | aperto |  (→ dn-query-options). Oggi asqueel accetta entrambe le grafie. |
| `compiled`, `sqltext`, `sqlparams` | — | sì |  |
| `test()`, `cursor()`, `fetch()`, `servercursor()`, `serverfetch()`, `iterfetch()`, `count()` | uguali (`sql/gnrsqldata/query.py`) | sì |  |
| `fetchPkeys()`, `fetchAsJson()`, `fetchAsDict()`, `fetchAsBag()`, `fetchGrouped()`, `handleBagColumns()` | uguali | sì |  |
| `execute()` | — | sì |  |
| `fetchRecord(ignoreMissing=)` | `table.record()` | sì | nuovo |
| `update(updater)`, `delete()` | `table.batchUpdate()`, `table.deleteSelection()` | cambiato | metodi della query, Macro 6 |
| `sql_update(values)`, `sql_delete()` | `table.sql_deleteSelection()` per `sql_delete` | cambiato | Macro 6 |
| macro `#THIS`, `#IN_RANGE`, `#PERIOD`, `#ENV`, `#BAG`, `#BAGCOLS` | uguali | — | maiuscolo per convenzione delle macro |

#### Database, environment e session

*Database*

| asqueel | GenroPy | Regola | Note |
|---|---|---|---|
| `adapter`, `implementation`, `currentConnectionName`, `usingMainConnection()` | uguali (`sql/gnrsql/env.py`) | sì |  |
| `currentEnv`, `currentUser`, `workdate`, `locale`, `updateEnv()`, `clearCurrentEnv()`, `tempEnv()` | uguali | sì |  |
| `current_env`, `temp_env()` | — | aperto |  (→ dn-env-methods). Sono doppioni di `currentEnv` e `tempEnv()`. |
| `execute(sql, sqlargs, cursor, cursorname, autocommit, dbtable, storename)` | uguale (`sql/gnrsql/execute.py:47`) | sì | firma ripristinata dalla Macro 6 |
| `_adaptArguments` (argomento di `execute`) | uguale | legacy |  |
| `executemany()`, `cursor()` | — | sì |  |
| `deferToCommit()`, `deferAfterCommit()`, `deferredRaise()` | uguali (`sql/gnrsql/transactions.py`) | sì |  |
| `commit()`, `rollback()`, `closeConnection()`, `onDbCommitted()` | uguali | sì | `onDbCommitted` è un override |
| `setLocale()`, `setConstraintsDeferred()`, `analyze()`, `vacuum()` | uguali | sì | Macro 6 |
| `session(db, **env)` | — (corrisponde a una page request GenroPy) | sì | nome dato dall'utente il 2026-10-19 |
| chiavi di environment `connectionName`, `storename`, `user`, `workdate`, `locale`, `currentImplementation`, `current_<path>`, `allowed_<path>` | uguali | sì |  |

#### API di integrazione

Questi nomi servono a chi integra asqueel in un'applicazione. Non è stato deciso se sono parole del linguaggio o API Python.

*Database, AsqueelDb, AsqueelDbMixin*

| asqueel | GenroPy | Regola | Note |
|---|---|---|---|
| `Database(conninfo, implementation, connect_kwargs, environment)` | — | aperto |  (→ dn-integration) |
| `AsqueelDb.migration_plan(allow_removals=)`, `migrate(allow_removals=)` | `checkDb`, `diffOrmToSql`, `syncOrmToSql` | aperto |  (→ dn-integration) |
| `asqueel_owner_name`, `asqueel_owner()`, `asqueel_dbs`, `taken_databases`, `set_asqueel_db()`, `get_db()`, `release_databases()` | — | aperto |  (→ dn-integration) |

#### Fuori dal glossario

- Nomi di classe ed eccezioni (`SqlQuery`, `RecordNotFoundError`, `UnsupportedFeatureError`, …): CapWords, come in Python e in GenroPy.
- Comandi CLI (`asqueel db plan`, `asqueel db apply --allow-removals`): convenzione delle CLI.
- Helper privati e interni del compiler: idioma Python.

### Proposed solution

Ogni nome aperto si decide con la regola GenroPy. Le decisioni sono elencate sotto, una per gruppo di nomi.

- **must** — I nomi marcati `legacy` restano come in GenroPy, anche quando non seguono la regola. *(Decisione registrata: la sintassi GenroPy resta, e cambiarla richiede motivi scritti forti.)*
- **must** — Ogni nome ha una sola grafia. Due grafie dello stesso nome non convivono.
- **should** — Un nome nuovo di asqueel che è una parola del linguaggio segue la regola: camelCase, `_` solo per un namespace.

### Decisions

- **dn-query-options** `open` — Quale grafia resta per le opzioni di query `exclude_draft`, `exclude_logical_deleted`, `ignore_partition`?
   1. **Solo la grafia GenroPy**: `excludeDraft`, `excludeLogicalDeleted`, `ignorePartition`. È la grafia GenroPy e segue la regola. Le grafie con `_` spariscono.
   2. **Entrambe, come oggi**: La grafia con `_` è quella principale. La grafia GenroPy è un alias (`application_table.py:37-41`).
- **dn-env-methods** `open` — Restano i doppioni `current_env` e `temp_env()` accanto a `currentEnv` e `tempEnv()`?
   1. **Solo currentEnv e tempEnv**: Sono i nomi GenroPy e seguono la regola.
   2. **Entrambe, come oggi**: Le due grafie stanno in `runtime.py:143-193` e in `environment.py`.
- **dn-read-only** `open` — Come si scrive l'attributo di column `read_only`?
   1. **readOnly**: È la grafia GenroPy (`app/gnrdbo.py:350`) e segue la regola.
   2. **read_only**: È la grafia attuale di asqueel.
- **dn-default-from** `open` — Come si scrive l'attributo di column `default_from`, che non esiste in GenroPy?
   1. **defaultFrom**: Segue la regola.
   2. **default_from**: È la grafia attuale.
- **dn-elements** `open` — Gli elementi della grammar con `_` passano in camelCase? Gli elementi sono `sys_fields`, `weak_relation`, `virtual_columns`, `auto_counter`, `relative_index`, `dynamic_fields`, `record_hash`, `full_update`, `system_records`, `enabled_when`.
   1. **camelCase**: `sysFields`, `weakRelation`, `virtualColumns`, `autoCounter`, `relativeIndex`, `dynamicFields`, `recordHash`, `fullUpdate`, `systemRecords`, `enabledWhen`. `sysFields` torna alla grafia GenroPy.
   2. **Come oggi**: Gli elementi restano con `_`.
- **dn-element-attrs** `open` — Gli attributi nuovi con `_` degli altri elementi passano in camelCase? Gli attributi sono `with_options` (index), `constraint_type` e `check_clause` (constraint), `root_id`, `virtual_roots` e `linked_to` (hierarchical), `version_field` (audit).
   1. **camelCase**: `withOptions`, `constraintType`, `checkClause`, `rootId`, `virtualRoots`, `linkedTo`, `versionField`.
   2. **Come oggi**: Gli attributi restano con `_`.
- **dn-relation-attrs** `open` — Gli attributi nuovi di relation con `_` passano in camelCase? Gli attributi sono `foreign_key`, `case_insensitive`, `initially_deferred`, `constraint_name`. `foreign_key` e `case_insensitive` sostituiscono il `mode=` di GenroPy.
   1. **camelCase**: `foreignKey`, `caseInsensitive`, `initiallyDeferred`, `constraintName`.
   2. **Come oggi**: Gli attributi restano con `_`.
- **dn-x-attrs** `open` — Negli attributi dichiarati `x_*`, la parte dopo `x_` passa in camelCase? Gli attributi sono `x_identity`, `x_generation`, `x_weak`, `x_canonical`, `x_name`, `x_table_class`, `x_expanded_legacy`, `x_logical_pkey`. Sono attributi dichiarati nella grammar, non attributi liberi.
   1. **x_ più camelCase**: `x_tableClass`, `x_expandedLegacy`, `x_logicalPkey`. Gli altri sono già una parola singola.
   2. **Come oggi**: Gli attributi restano come sono.
- **dn-integration** `open` — I nomi dell'API di integrazione sono parole del linguaggio o API Python? Sono `connect_kwargs`, `migration_plan()`, `allow_removals` e i metodi di `AsqueelDbMixin`.
   1. **Linguaggio: camelCase**: `connectKwargs`, `migrationPlan()`, `allowRemovals`, `asqueelOwnerName`, `setAsqueelDb()`, `getDb()`, `releaseDatabases()`.
   2. **API Python: come oggi**: I nomi restano nell'idioma Python.

### Consequences

Ogni nome che passa in camelCase cambia in quattro posti: la grammar, il codice, i test e `docs/grammar.md`, che è generato.

Togliere una delle due grafie rompe il codice che usa quella grafia. Le due grafie esistono oggi in `dn-query-options` e `dn-env-methods`.
