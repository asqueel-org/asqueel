# 72 — Inventario del namespace della tabella legacy

14 ottobre 2026. Censimento richiesto per valutare un oggetto tabella unico
oppure namespace/proxy come model, triggers e logic. **Nessuna decisione di
unificazione, nessuna nuova API e nessuna modifica al core in questo lavoro.**

## Metodo e perimetro

Riferimento congelato `fa35e5adfa6ad1b269f3a22a9b12c4c1ee6513ea`, già usato nel
confronto del renderer. Ispezione statica delle classi composte e ispezione degli
oggetti dopo il vero startup del modello di test_invoice_pg nel profilo offline
sanificato già usato dalle altre sonde. Non sono stati eseguiti query, trigger o
metodi applicativi. Le property non vengono valutate: si usa getattr_static.

Sono incluse le classi ereditate, i metodi applicati dinamicamente come mixin,
gli override effettivi, gli alias di backup e gli attributi dell'istanza.
“Pubblico” significa soltanto nome che non inizia con underscore; non è una
certificazione che ciascun nome sia API stabile o debba essere portato.
Dunder esclusi; gli altri nomi privati restano nel JSON per l'ispezione tecnica.

Il campione applicativo comprende le 75 tabelle legacy di sys, adm, invc.
Per il confronto col perimetro Asqueel si considerano 74 tabelle, escludendo
sys.locked_record. Non è un censimento di ogni personalizzazione di ogni
applicazione Genropy. Non conta colonne, chiavi della Bag o parametri dei metodi
come membri Python della tabella; non comprende nomi creati solo eseguendo
successivamente operazioni applicative.

[Probe riproducibile](probes/table_namespace_inventory.py) e
[inventario con provenienza file/riga](evidence/table-namespace/inventory.json).
Nel JSON, ogni namespace effettivo si ricostruisce con `common_operational` +
`operational_delta`, oppure `common_model` + `model_delta`: dati comuni archiviati
una sola volta, senza perdere nomi o provenienza.

## Dimensioni

| Classe prima della composizione applicativa | Metodi pubblici | Property | Altri attributi pubblici di classe |
| --- | ---: | ---: | ---: |
| SqlTable, incluse le basi | 147 | 31 | 0 |
| DbTableObj, incluse le basi | 39 | 43 | 1 |
| TableBase applicativa, incluse le basi | 74 | 0 | 0 |

L'unione dei namespace delle due classi SQL di base dà **239 nomi distinti**:
178 + 83 − 22 sovrapposizioni. Non si possono sommare anche i 74 metodi TableBase:
ci sono override; la composizione può conservare i metodi precedenti con un
underscore finale e aggiungere altri contributi del framework e dei package.

| Tabella effettiva | Metodi SqlTable | Property | Altri attributi | Totale operativo | Unione con modello |
| --- | ---: | ---: | ---: | ---: | ---: |
| invc.invoice | 232 | 31 | 4 | 267 | 330 |
| invc.invoice_row | 232 | 31 | 4 | 267 | 330 |
| invc.customer | 230 | 31 | 4 | 265 | 328 |
| adm.user | 253 | 31 | 4 | 288 | 351 |
| adm.htmltemplate_atc | 325 | 31 | 4 | 360 | 423 |

Sulla fattura: **267 nomi già operativi + 63 nuovi nomi del modello = 330**.
Il modello effettivo espone 90 nomi, 27 dei quali già presenti sulla tabella.
Fra le 74 tabelle ammesse, l'unione va da **327** (per esempio adm.access_group)
a **423** (adm.htmltemplate_atc).

È un'unione meccanica, non la dimensione obbligatoria della futura API:
comprende anche model/dbtable, strumenti di costruzione e funzioni rinviate.
Se si unificassero davvero le classi, alcuni riferimenti diventerebbero superflui.

## Ripartizione dei 147 metodi operativi di base

La suddivisione seguente è quella reale dei mixin del legacy, non una proposta
di nuovi namespace. Alcuni mixin raccolgono più responsabilità: CrudMixin
contiene anche readColumns/countRecords ed UtilsMixin contiene servizi diversi.

### QueryMixin: 11 metodi

`colToAs`, `columnsFromString`, `frozenSelection`, `getQueryFields`, `opTranslate`, `parseSerializedKey`, `query`, `relatedQuery`, `relatedQueryPars`, `relationName`, `sqlWhereFromBag`.

### CrudMixin: 26 metodi

`batchUpdate`, `changePrimaryKeyValue`, `checkDuplicate`, `countRecords`, `delete`, `deleteRelated`, `deleteSelection`, `empty`, `existsRecord`, `expandBagFields`, `fillFromSqlTable`, `insert`, `insertMany`, `insertOrUpdate`, `lock`, `raw_delete`, `raw_insert`, `raw_update`, `readColumns`, `recordToUpdate`, `setColumns`, `sql_deleteSelection`, `update`, `updateRelated`, `writeRecordCluster`, `xmlDebug`.

### RecordMixin: 23 metodi

`buildrecord`, `cachedKey`, `cachedRecord`, `checkPkey`, `currentRelations`, `defaultValues`, `extendDefaultValues`, `findDuplicates`, `guessPkey`, `hasRelations`, `newRecordCaption`, `newrecord`, `record`, `recordAs`, `recordCaption`, `recordCoerceTypes`, `recordCopy`, `restoreUnifiedRecord`, `rowcaptionDecode`, `sampleValues`, `tableCachedData`, `unifyRecords`, `unifyRelatedRecords`.

### ColumnsMixin: 17 metodi

`baseViewColumns`, `column`, `counterColumns`, `fullRelationPath`, `getColumnPrintWidth`, `getPartitionCondition`, `getUserConfiguration`, `removeLocalizationFromText`, `subtable`, `variantColumn_age`, `variantColumn_age_day`, `variantColumn_captions`, `variantColumn_egvariant`, `variantColumn_fill`, `variantColumn_masked`, `variantColumn_sharevalue`, `variantColumn_unaccent`.

### TriggersMixin: 22 metodi

`check_deletable`, `check_updatable`, `diagnostic_errors`, `diagnostic_warnings`, `hasProtectionColumns`, `isDraft`, `islocked_delete`, `islocked_write`, `notifyDbUpdate`, `onLogChange`, `protect_delete`, `protect_update`, `protect_validate`, `touchRecords`, `trigger_assignCounters`, `trigger_onDeleted`, `trigger_onDeleting`, `trigger_onInserted`, `trigger_onInserting`, `trigger_onUpdated`, `trigger_onUpdating`, `trigger_releaseCounters`.

### SerializationMixin: 9 metodi

`fieldAggregate`, `fieldsChanged`, `importFromXmlDump`, `insertRecordClusterFromJson`, `recordToJson`, `recordToXml`, `relatedSelectionToJson`, `toXml`, `xmlDump`.

### CopyMixin: 13 metodi

`archiveRelatedRecords`, `duplicateRecord`, `getRowsForDuplication`, `insertPastedCluster`, `itemsAsText`, `onArchivingRecord`, `onCopyRecord`, `onCopySelection`, `onDuplicated`, `onDuplicating`, `onDuplicating_many`, `onPasteRecord`, `onPasteSelection`.

### UtilsMixin: 23 metodi

`cleanWrongSysRecordPkeys`, `compositeKey`, `copyToDb`, `copyToDbstore`, `createSysRecords`, `dependenciesTree`, `executeRetentionPolicy`, `exportToAuxInstance`, `getReleases`, `getResource`, `importFromAuxInstance`, `menu_dynamicMenuContent`, `menu_dynamicMenuLine`, `newPkeyValue`, `newUTCDatetime`, `onInited`, `onIniting`, `pkeyValue`, `realignRelatedTotalizers`, `relationExplorer`, `setQueryCondition`, `updateRecordsToLastRelease_raw`, `updateTotalizers`.

### SqlTable: 2 metodi

`exception`, `use_dbstores`.

### GnrObject: 1 metodi

`mixin`.

## Le 31 property operative

Queste espongono già una parte consistente della struttura senza obbligare
l'utente a passare da `.model`. Il numero di nomi nuovo nell'unificazione è
quindi molto inferiore alla somma dei due namespace.

`attributes`, `availablePermissions`, `columns`, `currentTrigger`, `db`, `dbImplementation`, `dbevents`, `dbroot`, `defaultRetentionPolicy`, `draftField`, `indexes`, `lastTS`, `logicalDeletionField`, `model`, `multi_tenant`, `multidb`, `newrecord_caption`, `noChangeMerge`, `partitionParameters`, `pkey`, `pkeys`, `pkg`, `real_columns`, `relations`, `relations_many`, `relations_one`, `rowcaption`, `totalizers`, `user_config`, `virtual_columns`, `whereTranslator`.

## I 63 nomi che il modello aggiungerebbe a invc.invoice

### Metodi: 35

`afterChildrenCreation`, `asBag`, `bagItemFormula`, `buildChild`, `buildChildren`, `deleteChild`, `deleteChildren`, `doInit`, `get`, `getAttr`, `getById`, `getColPermissions`, `getItem`, `getJoiner`, `getRelation`, `getRelationBlock`, `getResolver`, `getTableJoinerPath`, `getTag`, `getVirtualColumn`, `init`, `items`, `keys`, `makeRoot`, `manyRelationsList`, `newChild`, `newRelationResolver`, `onDelete`, `oneRelationsList`, `pluggedColumns`, `resolveRelationPath`, `starColumns`, `toJson`, `values`, `virtualColumnAttributes`.

### Property: 22

`adapted_sqlname`, `adapter`, `composite_columns`, `dependencies`, `dynamic_columns`, `full_virtual_columns`, `maintable`, `metadata`, `name_full`, `name_short`, `parent`, `queryfields`, `relatingColumns`, `root`, `sqlfullname`, `sqlname`, `sqlnamemapper`, `sqlschema`, `static_virtual_columns`, `structnode`, `subtables`, `table_aliases`.

### Attributi: 6

`allcolumns`, `childalias`, `children`, `dbtable`, `id`, `sqlclass`.

`metadata` e `table_aliases` in questa lista sono membri del legacy censito,
non introduzioni nella grammatica Asqueel. Lo stesso vale per funzionalità già
rinviate, ad esempio system records, diagnostica e pyColumn.

## I 27 nomi sovrapposti sulla fattura

`attributes`, `column`, `columns`, `db`, `dbroot`, `draftField`, `fullRelationPath`, `fullname`, `indexes`, `lastTS`, `logicalDeletionField`, `mixin`, `multi_tenant`, `name`, `name_long`, `name_plural`, `newrecord_caption`, `noChangeMerge`, `pkey`, `pkeys`, `pkg`, `relations`, `relations_many`, `relations_one`, `rowcaption`, `subtable`, `virtual_columns`.

Non sono 27 conflitti indipendenti: molte property e metodi sono esposizioni
per delega del modello. Per esempio SqlTable.column richiama model.column.
Restano da scegliere le implementazioni da conservare in un'eventuale fusione;
non basta ereditare le due classi e affidarsi all'ordine della MRO.

Lo stato interno, escluso dai conteggi pubblici, comprende nel modello
_fieldTriggers, _indexedColumn, _sqlnamemapper, _parent e _dbroot. Anche questo
va collocato esplicitamente: i proxy di accesso non lo separano automaticamente.

## I 74 metodi applicativi comuni di TableBase

Si aggiungono contatori, gerarchie, campi dinamici, configurazione e hook del
framework. Alcuni sostituiscono metodi già presenti: non sono 74 nomi nuovi su
ogni tabella. Lista completa:

`addPhonetic`, `addRelXtdRelidxColumn`, `assignCounterColumn`, `checkChangelog`, `checkDiagnostic`, `counterColumns`, `createSysRecords`, `dbo_onDeleting`, `dbo_onInserting`, `dbo_onUpdating`, `df_getFieldsRows`, `df_getFieldsRows_bag`, `df_getFieldsRows_table`, `df_getQuerableFields`, `df_importLegacyScript`, `df_subFieldsBag`, `endpointColumn`, `formulaColumn_allowedForPartition`, `getCounterPars`, `getCustomFieldsMenu`, `getHierarchicalData`, `getHierarchicalDataBag`, `getHierarchicalPathsFromPkeys`, `getInheritedValues`, `getPartitionAllowedUsers`, `getProtectionTag`, `guessCounter`, `hasInvalidCheck`, `hasProtectionColumns`, `hasRecordTags`, `hierarchicalSearch`, `hosting_copyToInstance`, `hosting_removeUnused`, `importerCheck`, `importerMatchIndex`, `importerStructure`, `inheritedFields`, `invalidFieldsBag`, `isInStartupData`, `linkHierarchicalToMaster`, `normalizeText`, `onDbUpgrade_createSysRecords`, `pathFromPkey`, `releaseCounterColumn`, `setTagColumn`, `sql_formula___invalid_reasons`, `sql_formula___protecting_reasons`, `sysFields`, `sysFields_counter`, `sysFields_df`, `sysFields_extra`, `sysFields_protectionTag`, `sysFields_relidx`, `sysRecord`, `templateColumn`, `trigger_assignCounters`, `trigger_hierarchical_after`, `trigger_hierarchical_before`, `trigger_insertLinkedHierarchicalRoot`, `trigger_releaseCounters`, `trigger_setAuditVersionIns`, `trigger_setAuditVersionUpd`, `trigger_setCurrentUser`, `trigger_setLocalizationPlaceholder`, `trigger_setProtectionTag`, `trigger_setRecordMd5`, `trigger_setRelidx`, `trigger_setRowCounter`, `trigger_setTSNow`, `trigger_updateLinkedHierarchicalRoot`, `trigger_xtdDeletedRecord`, `variantColumn_docurl`, `variantColumn_hdepth`, `variantColumn_hlv`.

## Esempi di contributi specifici dei package

I nomi seguenti sono i metodi effettivi la cui implementazione proviene da
`projects/`, compresi override del core. Gli altri metodi applicativi sono
censiti nel JSON; non sono eseguiti dalla sonda.

### invc.invoice

`calculateTotals`, `config_db`, `counter_inv_number`, `defaultValues`.

### invc.invoice_row

`config_db`, `trigger_onDeleted`, `trigger_onInserted`, `trigger_onUpdated`.

### invc.customer

`config_db`, `pyColumn_customer_score`.

### adm.user

`checkExternalTable`, `config_db`, `createPassword`, `getPreference`, `get_all_tags`, `importUsers`, `importerStructure`, `inviteUser`, `isInStartupData`, `loadRecord`, `loginPreference`, `onChangedTags`, `partitionioning_pkeys`, `populate`, `pushNotification`, `pyColumn_all_tags`, `pyColumn_cover_logo`, `pyColumn_square_logo`, `sendInvitationEmail`, `setPreference`, `syncExternalUser`, `trigger_onInserted`, `trigger_onInserting`, `trigger_onUpdated`, `trigger_onUpdating`, `use_dbstores`, `validateNewPassword`.

## Hook, personalizzazioni e binding di self

Il legacy distingue più famiglie, non soltanto sei callback CRUD:

- `trigger_onInserting`, `trigger_onInserted`, `trigger_onUpdating`,
  `trigger_onUpdated`, `trigger_onDeleting`, `trigger_onDeleted`;
- trigger di campo come `trigger_setTSNow`, `trigger_setCurrentUser`,
  `trigger_setRowCounter` e callback dichiarate sulle colonne;
- `dbo_onInserting`, `dbo_onUpdating`, `dbo_onDeleting` del livello applicativo;
- protezioni `protect_*`, controlli `check_*`, diagnostica;
- hook `onIniting`/`onInited`, copia/duplicazione e notifiche;
- trigger aggiuntivi dei package richiamati da _doExternalPkgTriggers.

Gli indici dei trigger di campo sono nel modello, i metodi sono sulla tabella
operativa. Il percorso write coordina l'ordine; non si può dedurre dal solo
prefisso. La sonda non certifica l'esecuzione dei trigger: l'ordine è stato
controllato nel sorgente `gnrsql/write.py` e il dispatch dei trigger di campo in
`gnrsqltable/crud.py`.

La composizione legacy conserva anche implementazioni precedenti con nomi
come `defaultValues_`, `trigger_assignCounters_`, `counterColumns_`.
Questi nomi sono inclusi nel conteggio, perché effettivamente presenti. Un futuro
namespace deve considerare override e chiamate all'implementazione precedente,
non soltanto il binding di self. Non viene decisa qui una nuova convenzione.

## Indicazioni per la scelta, non implementazioni

Le tre separazioni più evidenti dal censimento sono:

1. Struttura, introspezione e costruzione dell'albero: possibile ambito `model`.
2. Callback e loro implementazioni: possibile ambito `triggers`, preservando
   distinzione fra trigger di campo, tabella e package e l'ordine legacy.
3. Metodi propri del dominio applicativo: possibile ambito `logic`.

Le operazioni frequenti query/record/insert/update/delete/column possono
continuare a essere accessibili direttamente dalla tabella. Serializzazione,
copia, import/export, contatori e gerarchie sono altri gruppi distinguibili,
ma la scelta di portarli e dei rispettivi nomi non è implicita nel censimento.
I metodi di costruzione config_db/sysFields non devono necessariamente essere
membri del futuro oggetto operativo soltanto perché il legacy li mescolava.

**Un proxy che traduce logic.calculate_tax in logic_calculate_tax organizza
l'accesso, ma mantiene il metodo prefissato nel namespace Python della tabella.**
Non riduce da solo il numero dei membri, né delle proprietà o dello stato.
Riduce l'ambiguità dei nomi e permette accessi raggruppati; un completamento
utile del proxy richiede anche la scoperta dei membri (per esempio __dir__).
Ospitare fisicamente i metodi altrove e legarli alla tabella è un'altra scelta,
non necessaria per valutare la proposta attuale e non introdotta qui.

## Conteggi per tutte le tabelle nel perimetro nativo

Le righe seguenti descrivono sempre gli oggetti legacy effettivi, non gli oggetti
Asqueel. sys.locked_record è registrata nel JSON ma esclusa da questa tabella.

| Tabella | Metodi operativi | Nomi operativi totali | Nomi strutturali | Sovrapposti | Unione |
| --- | ---: | ---: | ---: | ---: | ---: |
| adm.access_group | 229 | 264 | 90 | 27 | 327 |
| adm.api_token | 234 | 269 | 90 | 27 | 332 |
| adm.api_token_tag | 229 | 264 | 90 | 27 | 327 |
| adm.audit | 231 | 266 | 90 | 27 | 329 |
| adm.authorization | 238 | 273 | 90 | 27 | 336 |
| adm.backup | 232 | 267 | 90 | 27 | 330 |
| adm.ckstyle | 230 | 265 | 90 | 27 | 328 |
| adm.connection | 236 | 271 | 90 | 27 | 334 |
| adm.counter | 248 | 283 | 90 | 27 | 346 |
| adm.day | 230 | 265 | 90 | 27 | 328 |
| adm.group | 230 | 265 | 90 | 27 | 328 |
| adm.group_helpdoc | 229 | 264 | 90 | 27 | 327 |
| adm.helpdoc | 229 | 264 | 90 | 27 | 327 |
| adm.htag | 233 | 269 | 90 | 27 | 332 |
| adm.htmltemplate | 238 | 273 | 90 | 27 | 336 |
| adm.htmltemplate_atc | 325 | 360 | 90 | 27 | 423 |
| adm.install_checklist | 230 | 265 | 90 | 27 | 328 |
| adm.language | 232 | 267 | 90 | 27 | 330 |
| adm.letterhead_type | 229 | 264 | 90 | 27 | 327 |
| adm.menu | 235 | 271 | 90 | 27 | 334 |
| adm.menu_page | 229 | 264 | 90 | 27 | 327 |
| adm.notification | 239 | 274 | 90 | 27 | 337 |
| adm.pkginfo | 229 | 264 | 90 | 27 | 327 |
| adm.preference | 239 | 274 | 90 | 27 | 337 |
| adm.record_tag | 229 | 264 | 90 | 27 | 327 |
| adm.sent_email | 229 | 264 | 90 | 27 | 327 |
| adm.served_page | 235 | 270 | 90 | 27 | 333 |
| adm.shortcut | 229 | 264 | 90 | 27 | 327 |
| adm.tblinfo | 231 | 266 | 90 | 27 | 329 |
| adm.tblinfo_item | 233 | 268 | 90 | 27 | 331 |
| adm.user | 253 | 288 | 90 | 27 | 351 |
| adm.user_access_group | 231 | 266 | 90 | 27 | 329 |
| adm.user_config | 244 | 279 | 90 | 27 | 342 |
| adm.user_group | 229 | 264 | 90 | 27 | 327 |
| adm.user_notification | 233 | 268 | 90 | 27 | 331 |
| adm.user_setting | 232 | 267 | 90 | 27 | 330 |
| adm.user_tag | 233 | 268 | 90 | 27 | 331 |
| adm.userobject | 245 | 280 | 90 | 27 | 343 |
| adm.week | 230 | 265 | 90 | 27 | 328 |
| adm.xgroup | 232 | 267 | 90 | 27 | 330 |
| invc.customer | 230 | 265 | 90 | 27 | 328 |
| invc.customer_type | 229 | 264 | 90 | 27 | 327 |
| invc.discount_tier | 229 | 264 | 90 | 27 | 327 |
| invc.invoice | 232 | 267 | 90 | 27 | 330 |
| invc.invoice_note | 229 | 264 | 90 | 27 | 327 |
| invc.invoice_row | 232 | 267 | 90 | 27 | 330 |
| invc.payment_type | 229 | 264 | 90 | 27 | 327 |
| invc.postcode | 229 | 264 | 90 | 27 | 327 |
| invc.price_year | 229 | 264 | 90 | 27 | 327 |
| invc.price_year_note | 229 | 264 | 90 | 27 | 327 |
| invc.product | 230 | 265 | 90 | 27 | 328 |
| invc.product_group | 229 | 265 | 90 | 27 | 328 |
| invc.product_type | 229 | 265 | 90 | 27 | 328 |
| invc.region | 229 | 264 | 90 | 27 | 327 |
| invc.staff | 229 | 264 | 90 | 27 | 327 |
| invc.staff_role | 229 | 264 | 90 | 27 | 327 |
| invc.state | 229 | 264 | 90 | 27 | 327 |
| invc.vat_type | 229 | 264 | 90 | 27 | 327 |
| sys.batch_log | 229 | 264 | 90 | 27 | 327 |
| sys.calendar | 232 | 267 | 90 | 27 | 330 |
| sys.dataretention | 229 | 264 | 90 | 27 | 327 |
| sys.dbchange | 231 | 266 | 90 | 27 | 329 |
| sys.error | 230 | 265 | 90 | 27 | 328 |
| sys.external_token | 236 | 271 | 90 | 27 | 334 |
| sys.external_token_use | 229 | 264 | 90 | 27 | 327 |
| sys.externalcall_log | 229 | 264 | 90 | 27 | 327 |
| sys.service | 235 | 270 | 90 | 27 | 333 |
| sys.shared_object | 231 | 266 | 90 | 27 | 329 |
| sys.shorturl | 229 | 264 | 90 | 27 | 327 |
| sys.task | 240 | 275 | 90 | 27 | 338 |
| sys.task_execution | 229 | 264 | 90 | 27 | 327 |
| sys.task_result | 229 | 264 | 90 | 27 | 327 |
| sys.upgrade | 233 | 268 | 90 | 27 | 331 |
| sys.widget | 230 | 266 | 90 | 27 | 329 |

## Riproduzione

Eseguire `docs/design/probes/table_namespace_inventory.py` con il Python e
PYTHONPATH del checkout legacy congelato. Il probe riutilizza
scripts/capture_legacy_invoice.py con il profilo sanificato e intercetta solo
il momento di estrazione della struttura per ispezionare gli oggetti. Nessun
file della source legacy viene modificato. Le fixture temporanee sono rimosse.

Verificata la ricostruzione esatta common + delta per ciascun namespace.
Nessuna modifica al renderer, al compilatore, alla grammatica o al runtime.
