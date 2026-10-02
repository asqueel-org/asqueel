# 38 — Analisi degli attributi di tabella e dello strato dbo nel legacy

Stato: analisi, nessuna decisione presa. Serve a decidere quali funzioni di
tabella diventano elementi del contenitore `options` (proposta 0001 §2.6) e
quali restano attributi della tabella.

Riferimenti: genropy `origin/develop` `5e7f02e8d774`, letto con `git show`.
`gnrdbo` = `gnrpy/gnr/app/gnrdbo.py`. `sysFields` è già analizzato nel
documento 34 e qui non si ripete. L'uso nelle applicazioni viene dall'indice
Sourcerer (sezione 6).

## 1. Classi dbo e funzioni che offrono

### 1.1 `GnrDboPackage` (gnrdbo:42)

- `updateFromExternalDb` (`:44`): copia le tabelle elencate nell'attributo di
  package `export_order`.
- `partitionParameters` (`:56`): legge l'attributo di package `partition`
  (`pkg.tbl.fld`). Nessun chiamante.
- Contatori `getCounter` / `getLastCounterDate` / `setCounter` (`:64`, `:77`,
  `:92`): delegano alla tabella `counter`.
- User object e preferenze (`:106-140`): delegano ad `adm`.
- Startup data (`:148`, `:157`, `:274`, `:278`): leggono `multidb` e
  `inStartupData` di tabella e di colonna.
- `handleLocalizedColumn` (`:219`): crea le colonne per lingua e riscrive
  l'attributo `hierarchical` (`:272`).

### 1.2 `TableBase` (gnrdbo:320), oltre a `sysFields`

- Protezione e validità: `hasProtectionColumns` (`:649`),
  `sql_formula___protecting_reasons` (`:655`, legge `protectionColumn`),
  `hasInvalidCheck` (`:667`), `sql_formula___invalid_reasons` (`:673`),
  `_isReadOnly` (`:682`, legge `readOnly`; nasconde `triggers.py:186`).
- Partizione: `formulaColumn_allowedForPartition` (`:692`),
  `getPartitionAllowedUsers` (`:702`).
- Gerarchia: varianti `hlv` / `hdepth` / `docurl` (`:732-744`), trigger
  (`:751`, `:754`), API pubbliche (`:758-778`, `:918`, `:922`).
- Record di sistema: `onDbUpgrade_createSysRecords` (`:829`),
  `createSysRecords` (`:832`), `sysRecord` (`:860`), `_sysRecordCreateCb`
  (`:863`, legge `sysRecord_masterfield`).
- Importer: `importerStructure` / `importerMatchIndex` / `importerCheck`
  (`:886-903`).
- Trigger di campo: `setRowCounter` (`:934`), `xtdDeletedRecord` (`:960`, mai
  registrato), `setRelidx` (`:963`), `setLocalizationPlaceholder` (`:975`),
  `setTSNow` (`:988`), `setProtectionTag` (`:1004`), `setCurrentUser`
  (`:1011`), `setAuditVersionIns/Upd` (`:1021`, `:1028`), `setRecordMd5`
  (`:1035`, vuoto).
- Valori ereditati: `inheritedFields` / `getInheritedValues` (`:1042`,
  `:1052`, attributo di colonna `inherited`).
- Hook di scrittura chiamati da `gnrsql/write.py:159`, `:256`, `:311`:
  `dbo_onInserting` (`:1073`), `dbo_onUpdating` (`:1077`), `dbo_onDeleting`
  (`:1099`); chiamano `checkDiagnostic` (`:1066`, legge `diagnostic`),
  `checkChangelog` (`:1090`, legge `chlog`), `protect_draft`,
  `onArchivingRecord`, `restoreUnifiedRecord`.
- Campi dinamici: `df_*` (`:1102-1210`, legge `df_fieldstable`).
- Colonne speciali: `templateColumn` (`:1248`), `endpointColumn` (`:1279`).
- Hosting: `hosting_copyToInstance` (`:1291`), `hosting_removeUnused`
  (`:1459`).
- Startup: `isInStartupData` (`:1469`, legge `inStartupData`,
  `totalize_maintable`).
- Sequenze `adm.counter`: `counterColumns` (`:1484`), `trigger_assignCounters` /
  `trigger_releaseCounters` (`:1491`, `:1499`; chiamati da `write.py:158`,
  `:259`, `:319`), `guessCounter` (`:1518`), `_sequencesOnLoading` (`:1531`).
- Senza chiamanti: `addPhonetic` (`:715`), `invalidFieldsBag` (`:723`),
  `hasRecordTags` (`:1062`), `getCustomFieldsMenu` (`:1464`).

### 1.3 `GnrDboTable(TableBase)` (gnrdbo:1556)

- `notify` (`:1559`): pg NOTIFY su un canale.
- `use_dbstores` (`:1584`): restituisce `multidb`.
- Popolamento dal master db (`:1589`, `:1614`, `:1631`).

### 1.4 Classi derivate

| Classe | Riga | Cosa fa | Sottoclassi nel framework | File applicativi |
|---|---|---|---|---|
| `HostedTable` | `:1653` | `hosting_config` scrive `readOnly=True` | 0 | 5 (1 repository) |
| `XTDTable` | `:1658` | tabella `_xtd` della master; scrive `xtdtable` sulla master (`:1676`); legge `copy_deleted_record`, `chlog` | 0 | 4 (3 repository) |
| `AttachmentTable` | `:1702` | tabella `_atc` degli allegati; scrive `atc_attachmenttable` sulla master (`:1721`); endpoint, OCR, PDF | 6 | 206 (35+8 repository) |
| `TotalizeTable` | `:1972` | tabella di totali alimentata da un'altra (`tt_totalize*`, `tt_realign`) | 0 | 13 (5 repository) |
| `Table_sync_event` | `:2110` | `onTableTrigger` legge `sync_topic`; nessun chiamante | 0 | — |
| `Table_counter` | `:2140` | `transaction=False` | 0 | — |

- Le altre classi base usate dalle applicazioni sono definite nelle
  applicazioni stesse: `DetailTable` (erpy, 7 file), `GnrHTable` (4),
  `StoreTable` (3), `DynamicFieldsTable` (2), più classi singole (sezione 6.3).
- `gnrsqltable/table.py:82-85`: `hierarchical` crea `HierarchicalHandler`,
  `xtdtable` crea `XTDHandler`.

## 2. Inventario degli attributi di tabella

Categorie: M modello, W scrittura, Q query/compiler, UI interfaccia, EXT
estensione di package. Doc: ds docstring, docs cartella `docs/`, no nessuna.
«App» = file applicativi che lo passano a `pkg.table(` (sezione 6.1).

| Attributo | Letto in | Effetto | Doc | Cat | App |
|---|---|---|---|---|---|
| `pkey` | `gnrsqlmodel/table.py:212` | chiave primaria | ds+docs | M | 5219 |
| `pkey_columns`, `pkey_columns_joiner` | `gnrsqltable/utils.py:111-115` | `newPkeyValue` unisce più colonne | no | W | 25 |
| `name_short/long/full`, `name_plural`, `name_one` | `obj.py:110-126`; `table.py:142`; `th.py:170` | etichette | ds/docs | UI | 5707 (long), 5317 (plural) |
| `caption_field` | `table.py:247` e 12 altri punti | colonna di caption | no | UI | 5047 |
| `rowcaption` | `table.py:246` | caption del record | ds+docs | UI | 675 |
| `newrecord_caption` | `table.py:257` | caption del record nuovo | ds | UI | 20 |
| `sqlname` | `table.py:167` | nome SQL | ds | M | 2519 (2 repository) |
| `sqlschema` | `table.py:153` | schema SQL | ds | M | 0 |
| `comment` | nessuna lettura; `compiler.py:1144` lo scarta | nessuno | ds | M | 0 |
| `order_by` | `compiler.py:910` e altri 7 punti | ordinamento di default | no | Q | 105 |
| `queryfields` | `table.py:261`; `query.py:202` | colonne di default della query | ds | Q | 1 |
| `baseview` | `selection.py:110`; `get_selection.py:428` | colonne di default della selection | no | Q/UI | — |
| `preferred`, `weakCondition` | `db_select.py:162-163` | ordinamento e condizione del dbselect | no | UI | 3, 2 |
| `lookup` | `gnrmenu.py:768` e altri 4 punti | tabella di lookup | no | UI | 561 |
| `lastTS`, `noChangeMerge`, `noTestForMerge` | `table.py:218`, `:236`; `crud.py:509-527` | concorrenza ottimistica | ds/no | W | 0 |
| `logicalDeletionField`, `archivable` | `compiler.py:979`; `public.py:395` | cancellazione logica | ds/no | Q+W+UI | (sysFields), 40 |
| `draftField` | `compiler.py:987`; `write.py:161` | bozza | ds | Q+W | 1 |
| `readOnly`, `deletable` | gnrdbo:684; `write.py:294` | non scrivibile, non cancellabile | no/ds | W+UI | 1 (`readOnlyTable`, refuso), 9 |
| `protectionColumn` | gnrdbo:651 | motivo di protezione | no | Q | 1 |
| `invalidFields` | `crud.py:584` | campi invalidi | no | W | (sysFields) |
| `diagnostic` | gnrdbo:474, `:1067` | colonne errori/warning | no | W | 3 |
| `audit` | gnrdbo:469; `gnrwebapp.py:126` | versione e registro audit | docs | W | 20 |
| `logChanges` | `write.py:74` | change log | ds | W | — |
| `notify` | `write.py:100` | pg NOTIFY | ds | W | — |
| `broadcast` | gnrdbo:440; `gnrwebapp.py:70`, `:112` | eventi alle pagine | no | UI | 57 |
| `transaction` | `gnrapp.py:407` | scrittura solo dal transaction daemon | no | W | — |
| `unifyRecordsTag`, `syscodeTag`, `sysRecord_masterfield` | gnrdbo:475, `:522`, `:864` | unione record, record di sistema | no | M+UI | 58, 2, — |
| `counter`, `relidx` | `th_dynamic.py:75`; `xtd.py:65` | riordino righe, relidx | no | UI/W | (sysFields) |
| `hierarchical`, `hierarchical_caption_field`, `hierarchical_linked_to` | `table.py:82`; `hierarchical.py:113`; `copy.py:149` | gerarchia | no | M+UI | (sysFields), 42 |
| `xtdtable`, `copy_deleted_record`, `chlog` | `table.py:84`; gnrdbo:1690-1692 | tabella xtd | no | M/W | — |
| `atc_attachmenttable`, `endpoint_url`, `outdatedWatermark`, `handle_ocr` | `attachment.py:27`; gnrdbo:1758, `:1771`; `attachmanager.py:99` | allegati | no | M/UI | — |
| `df_fieldstable`, `df_fields` | gnrdbo:1145 | campi dinamici | no | M | 5 (`df_fields`) |
| `totalizer_<x>`; `totalize_maintable`, `totalize_maincolumn` | `utils.py:701`; gnrdbo:1471, `:2100` | totalizzatori | no | W | 9; 13 |
| `retention_policy` | `utils.py:744` | data retention | ds | W | — |
| `partition_<field>` | `columns.py:104-119` | partizione per riga | no | Q | 240 (23 repository) |
| `multi_tenant`, `tenant_column` | `table.py:123`; `env.py:166` | schema per tenant | ds/no | M | 8 |
| `maintable`, `default_subtable` | `table.py:116`; `compiler.py:958` | subtable | no | M/Q | 34 (`default_subtable`) |
| `multidb`, `multidb_onLocalWrite`, `multidb_fkeys`, `multidb_allRecords` | `columns.py:227`; `multidb/main.py` | sincronizzazione fra store | no | EXT | 134, 2 |
| `legacy_db`, `legacy_name`, `legacy_code`, `legacy_sync`, `external_pkey` | `gnrapp.py:1989`; `lgcy/main.py:27-36`; `serialization.py:207` | import da DB legacy | no | EXT | 3123, 3165, 6, 2, 2 |
| `version` | `utils.py:358` | copia fra istanze | no | M | 43 |
| `inStartupData` | gnrdbo:201, `:1470` | startup data | no | EXT | 45 |
| `checkpref` + `checkpref_*` | `gnrapp.py:1843` e altri 4 punti | visibilità da preferenza | no | UI | 30 |
| `permission_<name>` | `columns.py:429` | permessi custom | no | UI | 1 |
| `group_<code>` | `utils.py:616-619` | etichette dei gruppi di colonne | no | UI | 90 |
| `tabletype` | `gnrsql/query.py:199` | filtro di `tableTreeBag` | no | UI | 12 |
| `md_mode_*`, `default_md_mode` | `gridcustomizer.py:164`; `master_detail.py:156`, `:203` | master-detail | no | UI | 7 |
| `search_*`, `alias_on_field` | `genro_frm.js:815`; `th_tree.py:573` | box di ricerca, albero | no | UI | —, 1 |
| `openapi` | `api_engine/core.py:403` | esposizione openapi | ds | EXT | — |
| `mixin` | `obj.py:59` | mixin di classe | no | M | — |
| `sync_topic` | gnrdbo:2136 | topic di sync_event | no | — | — |

- Il client riceve tutti gli attributi di tabella: `base.py:424-426`
  (`.controller.table`), `th_view.py:1617-1619` (`.table`).

## 3. Meccanismi con cui un package agisce su una tabella

- **Colonna `ext_<pkg>=`** (`gnrsqlmodel/model.py:854`, `:936`, `:948-956`):
  l'argomento diventa attributo di colonna; per ogni package installato si
  chiama `pkgobj.ext_config(tblsrc, colname, colattr, **kw)`. Nel framework
  nessun package definisce `ext_config`; nelle applicazioni lo definisce solo
  `gnrdbextra:main.py` (4 versioni, per `ltx` ed `emb`). Uso: `ext_ltx` in 10
  file di 6 repository; `ext_emb` 0.
- **Sulla tabella non esiste un `ext_*`**: `table()` (`model.py:643`) non ha
  `extract_kwargs`. Gli equivalenti, senza un nome comune:
  - `config_db_<pkgid>` sul mixin della tabella (`model.py:128-137`, sotto
    `customize_<pkg>`; colonne marcate `_owner_package`);
  - `onBuildingDbobj` del package (`model.py:177-179`), che legge gli
    attributi delle tabelle (`multidb/main.py:70-84`; `lgcy/main.py:30-41`);
  - `onApplicationInited` del package con `instanceMixin` sulle tabelle che
    hanno un attributo (`multidb/main.py:39-45`; `lgcy/main.py:23-28`);
  - `trigger_<event>_<pkgid>` sulla tabella (`crud.py:696-711`), escludibili
    con l'env `avoid_trigger_<pkgid>`;
  - `sysFields_extra_*` sulla classe tabella (gnrdbo:633).
- **Attributi di tabella letti da package applicativi**, non dal framework:
  `e2l` (`erpy:main.py:63`), `survey` (`gnrextra:main.py:23`),
  `parametersRoot` (`gnrexperiments:main.py:32`), `next_table`
  (`cusl:main.py:54`), `wkfl` (`teamset:packages/wkfl/main.py:38`), `tmsh_*`,
  `md_*`. Le applicazioni usano quindi gli attributi di tabella come punto di
  estensione per i propri package.
- **Famiglie `extract_kwargs` / `dictExtract`**: tabella `partition_`,
  `permission_`, `totalizer_`, `checkpref_`, `md_mode_`, `search_`, `group_`;
  colonna `variant_`, `ext_`, `col_`, `subgroup_`, `endpoint_`; relazione
  `resolver_`, `meta_`; `sysFields` `counter_`.

## 4. Attributi orfani

- **Letti dal framework ma mai scritti dal framework** (li scrivono solo le
  applicazioni, se le scrivono): `preferred`, `weakCondition`, `baseview`,
  `queryfields`, `tenant_column`, `version`, `external_pkey`,
  `protectionColumn`, `diagnostic`, `chlog`, `copy_deleted_record`,
  `syscodeTag`, `hasRecordTags`, `df_fieldstable`, `unifyRecordsTag`,
  `logChanges`, `deletable`, `endpoint_url`, `outdatedWatermark`,
  `handle_ocr`, `md_mode_*`, `default_md_mode`, `totalizer_*`,
  `totalize_maintable`, `totalize_maincolumn`, `multidb_allRecords`,
  `name_one`, `alias_on_field`, `search_*`, `mixin`, `readOnly`; `notify` e
  `openapi` solo nei test.
- **Scritti ma mai letti come attributo di tabella**: `sync`, `ignoreUnify`,
  `hosting_prepopulate`, `storetable`, `comment`.
- **Refusi nelle applicazioni**, senza lettore: `rowCaption`
  (`dlfgest:model/concessionario.py:8`), `captionField`
  (`colto:model/marca.py:6`), `partitioned_progetto_id` (teamset, 2 file),
  `readOnlyTable` (anaci), `wpn` (anaci), `branch_field` (sandbox),
  `codice_tabella` (erpyready). In GenroPy un attributo sconosciuto è
  accettato in silenzio.

## 5. Incongruenze del legacy

- `onTableTrigger` usa `tblobj.lastTs`; la proprietà è `lastTS` (gnrdbo:2128;
  `columns.py:218`). Verificato.
- `utils.py:707` chiama `totalize_realign_sql`, che non esiste. Verificato.
- Due prefissi per i totalizzatori: `totalizer_` (`utils.py:701`) e
  `totalize_` (gnrdbo:1471, `:2100`).
- Due formati di partizione: package `partition='pkg.tbl.fld'` (gnrdbo:56,
  senza chiamanti) e tabella `partition_<field>=<path>` (`columns.py:104`);
  `_subtable_package` non copia `partition_*` (`model.py:739`).
- `dojo11.py:1030` legge `size` dagli attributi di una tabella; è un
  attributo di colonna.
- Tabella xtd: `xtd.py:43` scrive `xtd['id']`, ma la pkey è `main_id`
  (gnrdbo:1668) e la colonna `id` è commentata (`:1683`).
- `chlog` non fa nulla: `mainChangelog` e `relatedChangelog` sono `pass`
  (`xtd.py:96-100`), ma XTDTable aggiunge le colonne `chlog_*`
  (gnrdbo:1692-1694).
- `orm_extractor.py:153` ignora `sqlschema`, che `table.py:153` legge.
- `readOnly` ha due implementazioni (`triggers.py:186`, gnrdbo:682).
- `protect_draft` è chiamato da `write.py:161-163` all'insert e da
  `dbo_onUpdating` (gnrdbo:1081) all'update.
- `multidb_onLocalWrite` ha due default: `'merge'` (`multidb/main.py:82`) e
  `'raise'` (`:296`).

## 6. Uso nelle applicazioni (Sourcerer)

Metodo: `code_search_code` su `pkg.table(`, 155 pagine fino alla pagina vuota;
chiamate lette con `ast`; unità = file `repo:path`. Risultato: 5720 file
applicativi propri (66 repository, 5944 chiamate), 516 file di estensione
(`model/_packages/`, 49 repository), 179 file del framework.

### 6.1 Argomenti di `pkg.table(`

- Quasi universali: `name_long` 5707, `name_plural` 5317, `pkey` 5219,
  `caption_field` 5047.
- Modelli generati da DB legacy: `legacy_name` 3165, `legacy_db` 3123,
  `sqlname` 2519, concentrati in lavialattea e osi. Esclusi questi restano
  2555 file.
- Funzioni usate davvero (file / repository): `lookup` 561/44, `rowcaption`
  675/29, `partition_*` 240/23, `multidb` 134/8, `order_by` 105/23,
  `group_*` 90/21, `defaultDataset` 83/5, `unifyRecordsTag` 58/21,
  `broadcast` 57/15, `inStartupData` 45/7, `version` 43/2,
  `hierarchical_caption_field` 42/16, `archivable` 40/15,
  `default_subtable` 34/6, `checkpref` 30/5, `pkey_columns` 25/11,
  `newrecord_caption` 20/11, `audit` 20/6, `totalize_maintable` 13/5,
  `tabletype` 12/4, `deletable` 9/1.
- Mai usati: `lastTS`, `noChangeMerge`, `noTestForMerge`, `sqlschema`,
  `comment`, `ext_*` sulla tabella.
- Estensioni (`model/_packages/`): 364 file su 516 chiamano solo
  `pkg.table('nome')`; gli altri aggiungono soprattutto `pkey`, etichette,
  `partition_*`, `group_*`, `multidb`.

### 6.2 Attributi impostati dopo la creazione

- 6 `setdefault`, 2 `update`, 2 assegnazioni nelle tabelle proprie, tutte in
  classi base scritte dalle applicazioni (per esempio
  `colto:model/contratto_chg.py:35-42`).
- Nelle estensioni 21 `update` e 5 assegnazioni: `multidb` 8, `version` 6,
  `partition_*` 5, etichette.
- Una cancellazione: `del tbl.attributes["rowcaption"]`
  (`frigel_cont:model/_packages/erpy_base/staff.py:9`).

### 6.3 Classi base

- `object`: 5658 file propri, 509 di estensione.
- `AttachmentTable` 206, `TotalizeTable` 13, `DetailTable` 7, `GnrDboTable`
  5, `HostedTable` 5, `GnrHTable` 4, `XTDTable` 4, `StoreTable` 3,
  `DynamicFieldsTable` 2, mixin multipli 9, classi singole delle applicazioni.

### 6.4 Attributi di colonna che sono funzioni

- `_sendback` 106 file in 28 repository; `onInserting=` 28; `onUpdating=` 16;
  `sql_value=` 23; `_sysfield=` 2; `protected=` 1; `copyFromParent` 1;
  `triggerOnUpdate` 0.

## 7. Classe `Table` di package (`main.py`)

La classe `Table` del `main.py` di un package viene mescolata in ogni tabella
del package (`gnrapp.py:648`, `:734-735`; documento 34 §1).

Metodo: `code_search_code` su `class Package(` con il `main.py` intero nel
contesto, 7 pagine fino alla pagina vuota; 307 `main.py` su 314 indicizzati;
deduplicati per repo, schema del package e contenuto. Una misura precedente
(77 file in 49 repository) veniva da un'altra query e non coincide con questa.

### 7.1 Quante e cosa contengono

| | Package | Repository |
|---|---|---|
| `class Table(GnrDboTable)` nel framework | 19 | 1 |
| `class Table(GnrDboTable)` nelle applicazioni | 180 | 68 |
| di cui vuote (`pass`) | 12 + 150 | — |
| non vuote | 7 + 30 | 1 + 20 |

- La classe base è sempre `GnrDboTable`.
- Nelle classi non vuote: 0 override degli hook di scrittura (`trigger_on*`,
  `dbo_on*`, `protect_*`), 0 wrapper di `sysFields`, 0 `sysFields_extra_*`,
  `counter_*`, `sysRecord_*`, `df_*`, colonne calcolate per metodo.
- Contenuto reale:
  - politica dei dbstore (`use_dbstores`, `isInStartupData`): 6 package
    (framework multidb, adm, biz, email, sys; `mbe` base);
  - helper che aggiungono colonne, chiamati dai `configure` delle tabelle
    (`aliasColumn`, `bagItemColumn`, `formulaColumn`): 9 package in 7
    repository (per esempio `erpy:main.py(erpy_base):29`);
  - import e migrazione da altri sistemi: 8 package;
  - utility di numeri e formati: 5 package;
  - helper di dominio e di servizio: 11 package;
  - trigger con nome proprio: 2 package (teamset).
- Attributi letti da queste classi: 3 casi; uno è un attributo di package
  (`self.pkg.attributes.get('use_dbstores')`, framework email).

### 7.2 Hook di package nello stesso `main.py`

| Hook | Framework (package) | Applicazioni (package / repository) |
|---|---|---|
| `onBuildingDbobj` | 3 | 6 / 6 |
| `onApplicationInited` + `instanceMixin` | 2 | 8 / 6 |
| `config_db` del package non vuoto | 0 | 1 |
| `custom_type_<dtype>` | 0 | 75 / 27 |

### 7.3 Opzioni registrate da un package

I 10 package che usano `instanceMixin` fanno tutti la stessa cosa: scorrono le
tabelle di tutti i package e aggiungono un mixin dove la tabella dichiara un
attributo del package.

| Package | Attributi di tabella letti | Mixin |
|---|---|---|
| framework multidb | `multidb`, `multidb_fkeys`, `multidb_onLocalWrite`, `multidb_allRecords` | `MultidbTable` |
| framework tmsh | `tmsh_resource`, `structure_field` | `TmshResourceTable` |
| gnrwork tmsh | `tmsh_bookable`, `tmsh_allocator`, `tmsh_opening`, `tmsh_closure` | `TmshBookableTable` |
| gnrdbextra mtx | `multi_tenant`, `multi_tenant_fkeys` | `MultiTenantTable` |
| gnrdbextra emb | `emb_fields` (scritto da `ext_config`) | `EmbTableMixin` |
| gnrdbextra ltx | `ltx_fields`, `ltx_document_connection` (scritti da `ext_config`) | `LTXLocalTableMixin`, `LTXRelatedTableMixin` |
| gnrextra srvy | `survey` | `PluggedTable` |
| teamset wkfl | `wkfl` (dict con `mode` e prefissi `flow_`, `workflow_`, `formula_`) | `ApprovableTable` |
| erpy e2l | `e2l` (dict con `destinationTable`, `identifierColumns`) | `SyncE2LTable` |
| gnrexperiments prmf | `parametersRoot`, `parametric_fields` | `PluggedTable` |

- I default di package per tutte le tabelle sono rari: la politica dei
  dbstore (6 package) e un `config_db` di package che scrive `multidb='*'`
  sulle tabelle di un altro package (`frigel_cont:main.py(frgl):11-18`).
- `custom_type_<dtype>` (75 package) è un default di package per i dtype delle
  colonne, non per la tabella. Nomi più frequenti: `money` 74, `percentuale`
  35, `cambio` 35, `qta` 33, `extendedmoney` 18.

## 8. Sintesi per `options`

Ricavata dalle sezioni precedenti. Nessuna decisione presa.

- Un attributo di tabella sconosciuto oggi è accettato in silenzio (refusi
  della sezione 4); in `options` ogni opzione è un elemento con firma, quindi
  un refuso è un errore.
- Gli attributi descrittivi quasi universali (`pkey`, etichette,
  `caption_field`, `rowcaption`) sono proprietà della tabella, non funzioni.
- Le funzioni usate davvero, raggruppabili per funzione con i nomi legacy:
  - interfaccia: `lookup`, `group_*`, `checkpref`, `tabletype`,
    `hierarchical_caption_field`, `broadcast`, `md_mode_*`;
  - query: `order_by`, `partition_*`, `default_subtable`;
  - scrittura: `archivable`, `deletable`, `audit`, `unifyRecordsTag`,
    `pkey_columns`;
  - dati e sincronizzazione: `multidb`, `inStartupData`, `version`,
    `defaultDataset`, `totalize_*`;
  - import legacy: `legacy_db`, `legacy_name`, `legacy_code`, `sqlname`.
- Le classi base `AttachmentTable` (206 file) e `TotalizeTable` (13) sono
  funzioni di tabella scritte come ereditarietà: candidati a opzioni.
- Il modo dominante con cui un package aggiunge una funzione a tabelle di
  altri package è l'opzione registrata: un attributo di tabella letto dal
  package proprietario, che aggiunge un mixin (10 package in 7 repository,
  sezione 7.3). `options` deve permettere a un package di registrare le
  proprie opzioni, con firma e documentazione.
- I default di package per tutte le tabelle sono rari (sezione 7.3): non
  servono come primo meccanismo.
- La classe `Table` di package non ridefinisce mai gli hook di scrittura né
  `sysFields` (sezione 7.1): contiene helper e utility.
- Mai usati nelle applicazioni: `lastTS`, `noChangeMerge`, `noTestForMerge`,
  `sqlschema`, `comment`.
