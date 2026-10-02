# 34 — Analisi di `sysFields` nel legacy

Stato: analisi, nessuna decisione presa. Serve a decidere come asqueel fornisce
le stesse funzioni, una per volta.

Riferimenti: genropy `origin/develop` `1561d6547d7c`; asqueel `main`
`5b7c11dbf0a1`. Path relativi alla radice di ciascun repository. L'uso nelle
applicazioni viene dall'indice Sourcerer (sezione 26).

## 1. Dove sta e come arriva alla tabella

- `sysFields` è un metodo di `TableBase` (`gnrpy/gnr/app/gnrdbo.py:320`,
  metodo `:323-527`), non del livello SQL. `GnrDboTable(TableBase)` è a
  `gnrdbo.py:1556`. Gli helper sono a `gnrdbo.py:531-634`.
- La classe `Table` del `main.py` di ogni package (per esempio
  `projects/gnrcore/packages/adm/main.py:116`, `class Table(GnrDboTable)`) viene
  mescolata in ogni oggetto mixin di tabella (`gnrapp.py:648`, `:734-735`) e poi
  copiata sull'istanza `SqlTable` da `instanceMixin` (commento a
  `gnrdbo.py:637-641`).
- Quindi ogni `dir(self)` dentro `sysFields` guarda quell'oggetto combinato.
- Nel modello si chiama come `self.sysFields(tbl, ...)`, per esempio
  `projects/test_invoice/packages/invc/model/customer.py:9`.

## 2. Meccanismi generici usati da `sysFields`

### 2.1 Trigger di colonna

- In compilazione `DbColumnObj.doInit` (`gnrsqlmodel/columns.py:237-244`) legge
  gli attributi `onInserting`, `onUpdating`, `onDeleting`, `onInserted`,
  `onUpdated`, `onDeleted` di ogni colonna. Aggiunge
  `(colname, trigFunc, trigger_table)` a `table._fieldTriggers[event]`,
  nell'ordine di dichiarazione delle colonne.
- `indexed` e `unique` finiscono in `_indexedColumn` (`columns.py:233-236`).
- In esecuzione `_doFieldTriggers` (`gnrsqltable/crud.py:680-694`):
  - se il trigger è un callable chiama `trgFunc(record, fldname)`;
  - altrimenti chiama `getattr(ttable, 'trigger_<nome>')(record,
    fldname=..., tblname=self.fullname, **kwargs)`;
  - `ttable` è la tabella stessa, oppure `db.table(trigger_table)` se la colonna
    dichiara `trigger_table`;
  - negli eventi di update `kwargs` contiene `old_record`.

### 2.2 Ciclo di scrittura (`gnrsql/write.py`)

- `insert` (`:153-168`): `checkPkey` → `protect_validate` → `onInserting` di
  colonna → `trigger_onInserting` → trigger dei package esterni →
  `trigger_assignCounters` → `dbo_onInserting` → `protect_draft` → INSERT
  dell'adapter → `_onDbChange` → `onInserted` di colonna → …
- `update` (`:251-265`): `protect_update` → `protect_validate` → `onUpdating`
  di colonna → `trigger_onUpdating` → trigger dei package esterni →
  `dbo_onUpdating` → `trigger_assignCounters` → UPDATE dell'adapter →
  `updateRelated` → `_onDbChange` → `onUpdated` di colonna → …
- `delete` (`:294-319`): controllo `deletable` → `protect_delete` →
  `onDeleting` di colonna → … → `deleteRelated` → `dbo_onDeleting` → DELETE
  dell'adapter → … → `trigger_releaseCounters`.
- I `raw_*` (`:180-220`) saltano tutti i trigger e chiamano comunque
  `_onDbChange`.
- `insertRecordClusterFromJson` esegue anche gli `onInserting` di colonna e
  `assignCounters` prima di un `raw_insert` (`gnrsqltable/serialization.py:134-140`).

### 2.3 Livello applicativo del DB

- `GnrSqlAppDb.insert/update/delete/raw_*` (`gnrapp.py:425-496`) chiamano
  `application.notifyDbEvent` dopo la scrittura.
- `GnrApp.notifyDbEvent` non fa nulla (`gnrapp.py:1948-1949`).
- `GnrWsgiWebApp.notifyDbEvent` (`gnr/web/gnrwebapp.py:101-128`) accoda i
  `dbevents` di broadcast e scrive `adm.audit`.

### 2.4 Ambiente

- Una pagina web imposta `user`, `userTags`, `workdate`, `locale`,
  `external_host` e altri (`gnrwebpage.py:508-517`).
- `db.currentUser` restituisce `currentEnv['user']`, altrimenti
  `currentPage.user` (`gnrapp.py:536-538`). Esiste solo su `GnrSqlAppDb`.
- `:env_xxx` nelle formule è espanso da `ENVFINDER` (`gnrsqldata/compiler.py:424`).
- `sql_formula=True` è delegato al metodo `sql_formula_<campo>(attr)` della
  tabella (`compiler.py:396-397`).
- Gli attributi `var_*` di colonna diventano parametri della formula
  (`compiler.py:427`).

### 2.5 Costruzione differita del modello

- `deferOnBuilding` (`gnrsqlmodel/model.py:97-105`) accoda callback.
- `runOnBuildingCb` le esegue a `model.py:183`, dopo tutti i `config_db` e prima
  della costruzione dell'albero compilato (`model.py:187`).

### 2.6 Handler creati dagli attributi di tabella

- `SqlTable.__init__` crea `HierarchicalHandler` se c'è l'attributo
  `hierarchical`, e `XTDHandler` se c'è `xtdtable` (`gnrsqltable/table.py:82-85`).

### 2.7 Chi legge `_sysfield` e `_sendback`

- `recordCopy` salta le colonne `_sysfield`, salvo `draftField` e `parent_id`
  (`gnrsqltable/record.py:153-155`).
- La duplicazione azzera le colonne `unique` e `_sysfield`, salvo bozza e
  `parent_id` (`gnrsqltable/copy.py:267-274`).
- Il changeset del form client salta `_sysfield` (`genro_frm.js:1336`).
- Il generatore di risorse le salta (`gnr/dev/makers/resource.py:227`, `:475`).
- Le strutture di lookup inline le saltano (`resources/common/th/th_dynamic.py:43`).
- I record casuali le saltano
  (`resources/common/tables/_default/action/_common/random_records.py:288`).
- L'attributo passa nei metadati delle colonne della selezione
  (`gnrsqldata/selection.py:1397`).
- `_sendback`: il client `_getRecordCluster` decide nodo per nodo se inviarlo,
  `sendback = changesOnly ? node.attr._sendback : true` (`genro_frm.js:1821`).

## 3. `id` (default `True`)

- Colonna `id`: `size='22'`, `readOnly='y'`, `_sendback=True`, `_sysfield=True`,
  nel gruppo `group` (`gnrdbo.py:350`).
- Se la tabella non ha `pkey`, imposta `pkey='id'` (`gnrdbo.py:348`, `:351-353`).
  Un `pkg.table(..., pkey=...)` dichiarato prima vince.
- Formula `__record_pointer`: `'<fullname>.' || $<pkey>` (`gnrdbo.py:354-355`),
  creata solo con `id=True`.
- Nessun trigger. La chiave la genera `checkPkey` → `newPkeyValue` →
  `pkeyValue` (`gnrsqltable/record.py:620-631`; `gnrsqltable/utils.py:92-134`):
  - per una colonna T/A/C di 22 caratteri è un UUID (`utils.py:130-134`);
  - se il record ha `__syscode`, la chiave è quel codice completato con `'_'`
    fino alla dimensione (`utils.py:118-129`).
- `__record_pointer` lo legge solo `toolFormula`:
  `:env_external_host || '/_tools/<tool>?record_pointer=' || $__record_pointer`
  (`gnrsqlmodel/helpers.py:107-127`).
- L'opzione `hierarchical` richiede `id` attivo (`gnrdbo.py:382`).

## 4. `group`, `group_name` (default `'zzz'`, `'!![en]System'`)

- Attributo di tabella `group_<group> = group_name` (`gnrdbo.py:356-357`). Se
  uno dei due è vuoto, `group='_'` (`gnrdbo.py:358-359`).
- Nessun comportamento; serve solo al raggruppamento nell'albero dei campi.

## 5. Timestamp: `ins`, `upd`, `full_upd`

- Tipo: `tsType = 'DHZ' if config['db?use_timezone'] else 'DH'`
  (`gnrdbo.py:360`). Il valore di configurazione è valutato come booleano Python,
  senza `boolean()`.
- `ins` (default `True`): `__ins_ts`, `onInserting='setTSNow'`, `_sysfield`,
  `indexed=True` (`gnrdbo.py:361-362`).
- `upd` (default `True`): `__mod_ts`, `onUpdating='setTSNow'`,
  `onInserting='setTSNow'`, `_sysfield`, `indexed` (`gnrdbo.py:366-368`);
  `lastTS='__mod_ts'` se la tabella non ha già `lastTS` (`gnrdbo.py:369-371`).
- `full_upd` (default `False`): `__full_mod_ts`, indicizzato, senza trigger
  (`gnrdbo.py:372-373`).
- `trigger_setTSNow` (`gnrdbo.py:988-1002`):
  - non fa nulla se il record ha `_notUserChange` (lo imposta `touchRecords`,
    `gnrsqltable/triggers.py:93`);
  - scrive `datetime.now(pytz.utc)` per le colonne DHZ, `datetime.now()` senza
    fuso per DH;
  - se la tabella ha `__full_mod_ts`, copia lo stesso valore;
  - `__ins_ts` e `__mod_ts` sono due chiamate separate, quindi ognuna ha il suo
    `now()`;
  - non legge `workdate` né il fuso dall'ambiente.
- `deferredUpdateParentFullTs` / `updateParentFullTs` (`gnrdbo.py:1642-1648`)
  differiscono al commit un `batchUpdate(dict(), pkey=parent_id)` sul padre, che
  riesegue il suo `setTSNow`. Nessun chiamante di `deferredUpdateParentFullTs` né
  di `full_upd=` nel repository.

### 5.1 `lastTS`: concorrenza ottimistica

- Proprietà del modello `gnrsqlmodel/table.py:216-220`; della tabella
  `gnrsqltable/columns.py:216-218`.
- Caricamento: `get_record` mette `recInfo['lastTS'] = str(record[lastTS])`
  (`gnrwebpage_proxy/apphandler/get_record.py:268-269`).
- Salvataggio, in `writeRecordCluster` (`crud.py:522-565`):
  - confronta il `lastTS` del client con il valore bloccato nel DB;
  - se sono diversi e la tabella ha `noChangeMerge`, oppure l'operazione è un
    delete, alza «Another user modified the record»;
  - altrimenti confronta campo per campo: un campo il cui `oldValue` del client
    è diverso dal DB alza «Incompatible changes»;
  - `noTestForMerge` sulla tabella o sul package disattiva il confronto.
- I record one collegati restituiscono `lastTS_<rel>` (`crud.py:579-581`).
- Il client aggiorna `__mod_ts` / `lastTS` dopo il salvataggio
  (`genro_frm.js:1570-1580`) e lo confronta alla ricarica (`genro_frm.js:592`).
- `resultAttr['lastTS']` in `_gnrbasewebpage.py:541-543`.

### 5.2 Altri lettori di `__ins_ts` e `__mod_ts`

- Ordinamento di default `$__ins_ts` nelle viste e nei form TableHandler
  (`resources/common/th/th.py:819-820`; `th_view.py:1190-1191`).
- Il riallineamento `relidx` di xtd ordina per `$__ins_ts`
  (`gnrsqltable_proxy/xtd.py:55`, `:83`).
- `df_getFieldsRows_bag` ordina per `$__ins_ts` (`gnrdbo.py:1176`).
- La ricerca dei duplicati ordina per `$__mod_ts desc`
  (`gnrsqltable/record.py:535`; `th_view.py:935`).
- `hosting_copyToInstance` esclude `__ins_ts`, `__mod_ts`, `__ins_user`,
  `__mod_user` dal controllo delle modifiche (`gnrdbo.py:1423-1429`).
- `adm.audit` salta `__mod_ts` nel calcolo delle differenze
  (`adm/model/audit.py:36`).

## 6. `ldel` (default `True`): cancellazione logica

- Colonna `__del_ts`: `tsType`, nessun trigger, `_sysfield`, `indexed`
  (`gnrdbo.py:363-364`); attributo `logicalDeletionField='__del_ts'`
  (`gnrdbo.py:365`).
- Un `delete()` resta un DELETE fisico: nessuna conversione in `crud.py:103-114`
  né in `write.py:267-319`.
- La cancellazione logica è un update che imposta `__del_ts`. I percorsi:
  - il pulsante «archive» del form imposta il campo a `gnr.workdate` e salva
    (`resources/common/gnrcomponents/formhandler.py:350-365`);
  - la casella «Hidden» imposta `new Date()` oppure null (`formhandler.py:491-504`);
  - la RPC `archiveDbRows` imposta `datetime(archiveDate)` oppure `None` con
    `tblobj.update` (`gnrwebpage_proxy/apphandler/misc.py:264-304`).
- Quando `__del_ts` cambia, `TableBase.dbo_onUpdating` (`gnrdbo.py:1084-1088`):
  - chiama `onArchivingRecord(record, ts)`, che esegue `archiveRelatedRecords`
    (`gnrsqltable/copy.py:70-100`): un `batchUpdate` del campo di cancellazione
    di ogni tabella figlia collegata con `onDelete='cascade'`;
  - se il campo viene svuotato e `__moved_related` è presente, chiama
    `restoreUnifiedRecord` (sezione 18).
- Lettori:
  - compiler (`gnrsqldata/compiler.py:979-984`, uguale in `compiler_next.py:974-979`):
    `excludeLogicalDeleted=True` (default) aggiunge `$__del_ts IS NULL`; `'mark'`
    aggiunge `$__del_ts AS "_isdeleted"` se la query non è aggregata né count;
  - le subquery delle formule hanno `excludeLogicalDeleted=False` di default
    (`compiler.py:414`);
  - il caricamento di un record con più righe scarta quelle cancellate
    (`gnrsqldata/record.py:360-361`);
  - `get_record` imposta `recInfo['_logical_deleted']` (`get_record.py:270-271`);
  - le selezioni delle griglie passano a `'mark'` (`get_selection.py:294-295`,
    `:315`); le righe portano `_isdeleted` (`misc.py:488`; `serialization.py:382`);
  - i controlli della vista TableHandler mostrano o nascondono con
    `.excludeLogicalDeleted` (`th_view.py:1621-1630`);
  - le pagine pubbliche calcolano `archive` dall'attributo `archivable` o dalla
    preferenza `tblconf.archivable_tag` (`resources/common/public.py:392-395`);
  - i percorsi interni passano `excludeLogicalDeleted=False`: `updateRelated`,
    `deleteRelated` (`crud.py:165`, `:211`), `checkDuplicate` (`crud.py:241-250`),
    xtd, release e altri;
  - `unifyRecords` scrive `__del_ts=datetime.now()` sul record di origine
    (`gnrsqltable/record.py:470-474`).
- Propagazione alle tabelle figlie: `checkAutoStatic` (sezione 23).

## 7. `user_ins`, `user_upd`

- Default da `_sysFields_defaults` (`gnrdbo.py:531-538`), quando l'argomento è
  `None`: `user_ins = boolean(config['sysfield?user_ins'])`, default **vero**;
  `user_upd = boolean(config['sysfield?user_upd'])`, default **falso**.
- `__ins_user` con `onInserting='setCurrentUser'` (`gnrdbo.py:481-482`);
  `__mod_user` con `onUpdating` e `onInserting='setCurrentUser'`
  (`gnrdbo.py:483-484`). Nessuna delle due dichiara dtype o size.
- `trigger_setCurrentUser` (`gnrdbo.py:1011-1019`): salvo `_notUserChange`,
  scrive `self.db.currentUser`.
- Lettori: l'esclusione di `hosting_copyToInstance` (`gnrdbo.py:1427`).
  `adm.audit` legge `currentEnv['user']` per conto suo (`audit.py:25-26`).

## 8. `md5` (default `False`)

- `__rec_md5` con `onUpdating` / `onInserting='setRecordMd5'`
  (`gnrdbo.py:375-377`). Il `name_long` è un copia-incolla, `'!![en]Update date'`.
- `trigger_setRecordMd5` è `pass` (`gnrdbo.py:1035-1040`): la colonna non si
  riempie mai. Nessun lettore.

## 9. `useProtectionTag`

- `sysFields_protectionTag` (`gnrdbo.py:378-379`, `:540-544`); il valore passato
  come `protectionTag` è ignorato.
- Colonna `__protection_tag`: `_sysfield`, `_sendback`,
  `onInserting='setProtectionTag'`.
- Formula `__protected_by_tag` (B): `CASE WHEN $__protection_tag IS NULL THEN
  NULL ELSE NOT (',' || :env_userTags || ',' LIKE '%%,' || $__protection_tag ||
  ',%%') END`.
- `trigger_setProtectionTag` scrive `self.getProtectionTag(record=record)`, un
  hook che restituisce `None` di default (`gnrdbo.py:1004-1009`).
- Lettori: per il prefisso `__protected_by_*` entra in `__protecting_reasons`
  (sezione 19); `TableBase._isReadOnly` (`gnrdbo.py:682-690`) nega la scrittura
  se `__protection_tag` non è fra `currentEnv['userTags']`; la griglia aggiunge
  la classe `_gnrProtectionPass` (`genro_grid.js:2601-2602`).

## 10. `hierarchical` e sotto-opzioni

- Normalizzazione: `'pkey'` se `True`, altrimenti `'<valore>,pkey'`
  (`gnrdbo.py:381`); richiede `id` (`:382`).
- Creati (`gnrdbo.py:385-444`):
  - `parent_id`: size 22, `_sysfield`, trigger `onInserting` /
    `onUpdating='hierarchical_before'` e `onUpdated='hierarchical_after'`;
    relazione verso `<tbl>.id` con `mode='foreignkey'`, `onDelete='cascade'`,
    `relation_name='_children'`, `deferred=True` (`:385-392`);
  - formula `child_count` (L): subselect `COUNT(*)` su
    `@_children.parent_id=#THIS.id` (`:393-394`);
  - formula `hlevel`: numero di `/` in `$hierarchical_pkey` più 1 (`:395`);
  - per ogni campo della lista (`:411-428`): per `pkey`, `hierarchical_pkey`
    (`unique=True`, `_sysfield`) e `_parent_h_pkey`; per un altro campo `fld`
    (eventualmente `fld:unique`), `hierarchical_<fld>` (`unique` con `:unique`,
    `hierarchical_field_of=fld`) e `_parent_h_<fld>`. Chiama `tbl.column(fld)`
    per leggere `name_long`, quindi `fld` deve essere già dichiarato;
  - attributo `hierarchical=','.join(hfields)` (`:436`);
  - senza `counter`, `order_by` di default `$hierarchical_<primo>` (`:437-438`);
  - `broadcast` riceve `parent_id` (`:440-444`).
- `hierarchical_root_id`: colonna `root_id` di 22 caratteri con
  `sql_value="substring(:hierarchical_pkey from 1 for 22)"`, relazione verso
  `<tbl>.id` con `relation_name='_grandchildren'`, `onDelete='ignore'`
  (`gnrdbo.py:396-402`). `sql_value` è scritto come espressione SQL in
  INSERT/UPDATE (`sql/adapters/_gnrbaseadapter.py:755-756`, `:814-817`, `:859-862`).
- `hierarchical_virtual_roots`: colonna `_virtual_node` (B),
  `copyFromParent=True` (`gnrdbo.py:403-404`); la leggono il drag-and-drop
  dell'albero (`resources/common/th/th_tree.js:109`; `th_tree.py:560`, `:574`).
- `hdepth`: `variant='hdepth'` e `variant_hdepth_levels` sull'ultima colonna
  gerarchica; senza gruppo crea il gruppo `hierarchical_<fld>`
  (`gnrdbo.py:429-435`). L'espansione delle varianti (`gnrsqlmodel/table.py:444-460`)
  passa per `TableBase.variantColumn_hdepth` (`gnrdbo.py:738-742`) e
  `HierarchicalHandler.variantColumn_hdepth` (`hierarchical.py:237-250`) e
  produce le formule `<campo>_01 … <campo>_(livelli-1)` con
  `array_to_string((string_to_array(...,'/'))[1:i],'/')`.
- `hierarchical_linked_to`: attributo `hierarchical_linked_to` e
  `linkHierarchicalToMaster` differito (`gnrdbo.py:405-409`, `:563-585`):
  - sulla tabella gerarchica aggiunge `<reltbl>_<relpkey>`: `copyFromParent`,
    `fkeyToMaster`, FK verso la tabella collegata con `relation_name='<tblname>s'`,
    `onDelete='cascade'`;
  - sulla tabella collegata aggiunge `root_<tblname>_id`:
    `onInserting='insertLinkedHierarchicalRoot'`,
    `onUpdating='updateLinkedHierarchicalRoot'`, FK `one_one='*'`,
    `onDelete_sql='setnull'`;
  - `trigger_insertLinkedHierarchicalRoot` (`gnrdbo.py:588-601`) assegna la
    pkey se manca, inserisce un nodo radice con `id` uguale alla pkey completata
    con `ljust(22,'_')`, copia i campi gerarchici presenti e salva l'id della
    radice nel record;
  - `trigger_updateLinkedHierarchicalRoot` (`gnrdbo.py:603-613`) aggiorna la
    radice quando quei campi cambiano;
  - copia e incolla: `gnrsqltable/copy.py:148-154`, `:198-202`
    (`_duplicateLinkedTree`).
- `HierarchicalHandler` (`gnrsqltable_proxy/hierarchical.py:202-383`),
  raggiunto da `trigger_hierarchical_before/after` (`gnrdbo.py:751-755`):
  - `trigger_before` (`:252-283`): carica il padre con `subtable='*'`; se esiste
    `_row_count`, il record è un insert e non ha `_row_count`, imposta
    `_row_count = max(_row_count dei fratelli) + 1` (`:260-268`); per ogni campo
    imposta `_parent_h_<f>` al `hierarchical_<f>` del padre e `hierarchical_<f>`
    a `padre/valore`, oppure a `valore` alla radice (`:269-274`); copia dal padre
    ogni colonna `copyFromParent` (`:275-278`); con un contatore imposta
    `_parent_h_count` e ricalcola `_h_count = _h_count del padre +
    encode36(_row_count, 2)` se il conteggio è cambiato (`:279-283`);
  - `trigger_after` (`:287-308`): se un `hierarchical_<f>` o il contatore sono
    cambiati, rilegge i figli `for_update` ed esegue `tblobj.update` su ognuno, in
    cascata ricorsiva;
  - API di lettura e navigazione: `getHierarchicalData` /
    `TableHandlerTreeResolver` (`:28-200`, `:311-332`), `pathFromPkey`
    (`:334-341`), `getHierarchicalPathsFromPkeys` (`:343-360`), `getAncestors`
    (`:363-372`), `fixRowCount` (`:374-383`), `variantColumn_hlv` (`:226-235`);
    esposte come metodi pubblici a `gnrdbo.py:757-775`, `:917-932`.
- Altri lettori: `df_getFieldsRows_*` usano `hierarchical_pkey` / `hlevel` per i
  campi ereditati dei form dinamici (`gnrdbo.py:1172-1207`); il riordino
  dell'albero (`th_tree.py:157-167`); la cascata `_children` guida cancellazione e
  archiviazione con `deleteRelated` / `archiveRelatedRecords`.

## 11. `counter`: contatore locale di riga (`_row_count`)

È separato dalle sequenze `adm.counter` dei metodi `counter_<campo>` (sezione 11.1).

- Attributo `counter = <valore>` (`gnrdbo.py:447`).
- Senza gerarchia: `sysFields_counter(tbl, '_row_count', counter=...)`
  (`gnrdbo.py:457`, `:554-556`): colonna `_row_count` (L),
  `onInserting='setRowCounter'`, `counter=True`, `_counter_fkey=<counter>`;
  `order_by` di default `$_row_count` (`gnrdbo.py:458`).
- Con gerarchia (`counter` deve essere `True`, assert a `:449`): colonne
  `_h_count`, `_parent_h_count` e `_row_count` con `counter=True` ma **senza**
  trigger (`:450-452`); formula `_h_sortcol` `$_h_count`, oppure
  `COALESCE($_h_count,$<primo>)` (`:453-454`), costruita con la stringa
  `hierarchical` grezza, che conterrebbe ancora `:unique` se indicato;
  `order_by` di default `$_h_sortcol` (`:455`).
- `trigger_setRowCounter` (`gnrdbo.py:934-958`):
  - non fa nulla se il valore c'è già;
  - `_counter_fkey=True` dà un massimo globale; un elenco di FK separate da
    virgola dà un massimo per ogni combinazione di FK (NULL confrontato con
    `IS NULL`);
  - query `order_by $fld desc limit 1` con `excludeDraft=False`;
    `excludeLogicalDeleted` resta al default vero, quindi le righe cancellate
    logicamente non contano nel massimo;
  - espressione `last = fetch[0].get(fld) or 1 if fetch else 0`, poi
    `record[fld] = last + 1`: un massimo memorizzato nullo produce 2.
- Lettori:
  - riordino delle righe con drag: `grid_selfDragRows=tblobj.attributes.get('counter')`
    (`resources/common/th/th_dynamic.py:75`; `sys/webpages/lookup_page.py:70`;
    `lookuptables.py:82`); le colonne con l'attributo `counter` diventano
    `fieldcell(counter=True)` (`th_dynamic.py:41-42`); la griglia imposta
    `counterField` (`genro_grid.js:1916`) e invia le modifiche
    (`genro_grid.js:3668-3711`) a `counterFieldChanges`, che usa `batchUpdate`
    ed è raw salvo `triggerOnUpdate` sulla colonna (`misc.py:59-83`);
  - `fixRowCount` e i trigger gerarchici;
  - il gestore degli allegati ordina per `_row_count`
    (`resources/common/gnrcomponents/attachmanager/attachmanager.py:70-117`, `:568`).

### 11.1 Sequenze `adm.counter` (non create da `sysFields`)

- `counterColumns()` restituisce ogni metodo `counter_<campo>` (`gnrdbo.py:1484-1485`).
- `trigger_assignCounters` gira all'insert e all'update (`write.py:158`, `:259`)
  e chiama `adm.counter.assignCounter` (`gnrdbo.py:1499-1515`); quando un record
  torna bozza chiama `releaseCounters` (`gnrdbo.py:1491-1502`).
- `assignCounter` salta le bozze salvo `assignIfDraft` (`adm/model/counter.py:220-224`).
- `releaseCounter` al delete (`write.py:319`; `counter.py:344`).
- `_sequencesOnLoading` / `guessCounter` mostrano i valori previsti
  (`gnrdbo.py:1517-1553`; `get_record.py:281-285`).

## 12. `counter_kwargs` (`counter_<nome>=<fkeys>`)

- `@extract_kwargs(counter=True)` (`gnrdbo.py:323`; `gnr/core/gnrdecorator.py:97`)
  raccoglie gli argomenti `counter_*`.
- Per ognuno `sysFields_counter(tbl, '_row_count_<k>', counter=v)` crea
  `_row_count_<k>` con `setRowCounter` (`gnrdbo.py:466-468`), senza attributo di
  tabella né `order_by`.

## 13. `relidx`: indice relativo al master, nella tabella `_xtd`

- Attributo `relidx=<fkey>` (`gnrdbo.py:461`); colonna `_relidx` (L),
  `onInserting='setRelidx'`, `relidx=True`, `_relidx_fkey`, `format='0000'`
  (`gnrdbo.py:462`, `:558-561`).
- `addRelXtdRelidxColumn` differito (`gnrdbo.py:463-465`, `:616-629`): legge la
  relazione di `<fkey>` e aggiunge `<pkg>_<tbl>_relidx` (L) alla tabella
  `<masterpkg>.<mastertbl>_xtd`. Quella tabella `_xtd` deve esistere, dichiarata
  da una sottoclasse `XTDTable` (`gnrdbo.py:1658-1696`), il cui `config_db`
  imposta l'attributo `xtdtable` del master (`:1676`), che crea `tblobj.xtd`.
- `trigger_setRelidx` (`gnrdbo.py:963-973`): non fa nulla se il valore c'è; apre
  `mastertable.xtd.recordToUpdate(record[fkey], insertMissing=True)`,
  incrementa `xtd['<pkg>_<tbl>_relidx']` e assegna il valore a `_relidx`.
  `XTDHandler.__getattr__` inoltra alla tabella xtd (`xtd.py:31-32`).
- Lettori: `XTDHandler.realignRelatedRelIdx` / `realignRelatedRelIdxAll`
  (`gnrsqltable_proxy/xtd.py:50-91`) rinumerano `_relidx` per `__ins_ts` con
  `raw_update` e riscrivono i totali nella riga xtd.

## 14. `audit` (attributo di tabella)

- Colonna `__version` (L) con `onInserting='setAuditVersionIns'` e
  `onUpdating='setAuditVersionUpd'` (`gnrdbo.py:469-473`): l'insert scrive `0`
  (`:1021-1026`), l'update `(record.get(fld) or 0) + 1` (`:1028-1033`).
- `GnrWsgiWebApp.notifyDbEvent` chiama `adm.audit.audit(tblobj, event,
  audit_mode=<attr>, ...)` (`gnrwebapp.py:126-128`). `audit`
  (`adm/model/audit.py:22-47`):
  - in modalità `lazy` salta gli insert;
  - registra `currentEnv['user']`, `__version` ed `env_transaction_id`;
  - insert e delete salvano il record intero come XML; l'update salva i campi
    cambiati, esclusi `__version` e `__mod_ts`;
  - in modalità lazy, con versione 1, scrive un insert sintetico di versione 0.
- Solo l'applicazione web fa questo: `GnrApp.notifyDbEvent` non fa nulla
  (`gnrapp.py:1948-1949`).
- `raw_update` salta i trigger di colonna, quindi `__version` non aumenta, ma
  invia comunque l'evento con `old_record = record or dict(record)`
  (`gnrapp.py:484`): nessun campo risulta cambiato e non si registra nulla.

## 15. `diagnostic` (attributo di tabella)

- Colonne `__warnings` ed `__errors` (`gnrdbo.py:474`, `:478-480`).
- `dbo_onInserting` / `dbo_onUpdating` chiamano `checkDiagnostic`
  (`gnrdbo.py:1066-1078`), che scrive `'\n'.join(diagnostic_errors(record))` e
  l'equivalente per i warning, oppure `None`. Gli hook di base registrano un
  warning e restituiscono `None` (`gnrsqltable/triggers.py:160-168`).
- Nessun altro lettore.

## 16. `draftField`

- `'__is_draft'` se `True`, altrimenti il nome dato; attributo `draftField`
  (`gnrdbo.py:485-487`); colonna B, `_sysfield`, `_sendback`, `indexed`
  (`gnrdbo.py:488`).
- All'insert `write.py:161-163` imposta `record[draftField] = protect_draft(record)`
  se la tabella definisce `protect_draft`; all'update lo fa `dbo_onUpdating`
  (`gnrdbo.py:1081-1083`). Nessun trigger di colonna.
- Lettori:
  - compiler: `excludeDraft=True` (default) aggiunge `$<draft> IS NOT TRUE`
    (`compiler.py:986-989`); le subquery delle formule hanno `excludeDraft=False`
    (`compiler.py:413`);
  - `isDraft` (`gnrsqltable/triggers.py:207-210`);
  - assegnazione e rilascio di `adm.counter` (sezione 11.1);
  - `get_record` imposta `recInfo['_draft']` (`get_record.py:272-273`);
  - `recordCopy` e la duplicazione mantengono il valore (`record.py:153-155`;
    `copy.py:268`);
  - la griglia aggiunge la classe `gnrDraftRow` (`genro_grid.js:2604-2605`, `:3098`);
  - il form imposta `__is_draft` (`genro_frm.js:1738`);
  - la conferma di grouplet e wizard
    (`resources/common/gnrcomponents/grouplet/grouplet.py:529`, `:751-769`, `:856`;
    `grouplet.js:259-260`);
  - le viste TableHandler hanno `excludeDraft=True` di default
    (`th_view.py:1624-1625`).
- Propagazione alle tabelle figlie: `checkAutoStatic` (sezione 23).

## 17. `invalidFields`, `invalidRelations`

- Con `invalidFields`: attributo `invalidFields='__invalid_fields'` e colonna
  `__invalid_fields` (testo) (`gnrdbo.py:489-499`).
- Formula `__is_invalid` (B, `aggregator='OR'`): `( $__invalid_fields IS NOT NULL )
  OR <rel>.__is_invalid ...`, un termine per ogni path di `invalidRelations`
  separato da virgola, passato così com'è (per esempio `@rows`).
- `writeRecordCluster` scrive `toJsonJS(recordClusterAttr['_invalidFields'])`
  oppure `None` a ogni salvataggio (`crud.py:584-588`); il valore arriva dai
  campi non validi del form client (`genro_frm.js:1893`, `:2329-2336`).
- Lettori: `get_record` restituisce `recInfo['_invalidFields'] = fromJson(...)`
  (`get_record.py:275-277`); `invalidFieldsBag` (`gnrdbo.py:723-730`).

## 18. `unifyRecordsTag` (attributo di tabella)

- Colonna `__moved_related` (X) (`gnrdbo.py:475-477`).
- `_unifyRecords_default` (`gnrsqltable/record.py:447-476`): sposta i record
  collegati dall'origine alla destinazione; se `__moved_related` esiste, salva il
  Bag delle relazioni spostate come XML e imposta `__del_ts=now()` con
  `raw_update`; altrimenti cancella fisicamente l'origine. Le righe `:466-468`
  salvano `sourceRecord[pkey]` sotto la chiave `'destPkey'`.
- `restoreUnifiedRecord` (`record.py:382-396`), avviato da `dbo_onUpdating`
  quando `__del_ts` viene svuotato, riporta indietro le relazioni. Usa
  `record['id']` fisso alla riga `:393`.
- Lettori: il TableHandler pubblico abilita il drag-and-drop di unione se
  `checkResourcePermission(unifyRecordsTag, userTags)` passa
  (`resources/common/public.py:533-541`).

## 19. Sempre creati: motivi di protezione e di invalidità

- `__protecting_reasons` e `__invalid_reasons` con `sql_formula=True`;
  `__is_protected_row` = `$__protecting_reasons!=''`;
  `__is_invalid_row` = `$__invalid_reasons!=''` (`gnrdbo.py:503-507`).
- Generazione SQL: `compiler.py:396-397` chiama i metodi della tabella.
  - `sql_formula___protecting_reasons` (`gnrdbo.py:655-665`): include
    l'attributo di tabella `protectionColumn` come motivo quando non è null, e
    ogni colonna virtuale che inizia con `__protected_by_` come motivo
    `<suffisso>` quando è TRUE; restituisce `array_to_string(ARRAY[...],',')`
    oppure `NULL`.
  - `sql_formula___invalid_reasons` (`gnrdbo.py:673-680`): lo stesso per
    `__invalid_by_*`.
- `hasProtectionColumns` (`gnrdbo.py:649-653`) e `hasInvalidCheck`
  (`gnrdbo.py:667-671`) controllano se esistono colonne di quei tipi.
- Lettori:
  - le selezioni aggiungono `$__is_protected_row AS _is_readonly_row,
    $__protecting_reasons` e gli equivalenti di invalidità
    (`gnr/app/gnrsqltable_proxy/selection.py:136-140`; `get_selection.py:455-460`);
  - `get_record` le carica come colonne virtuali (`get_record.py:182-192`);
  - `TableBase._isReadOnly` (`gnrdbo.py:682-690`) restituisce
    `__protecting_reasons` se presente; da lì `_islocked_write` /
    `_islocked_delete` (`triggers.py:190-201`) e
    `recInfo['_protect_write'/'_protect_delete']` (`get_record.py:221-225`);
  - tooltip della griglia (`genro_grid.js:2033`); colonna di stato del
    TableHandler (`resources/common/th/th.py:198-201`); filtro degli invalidi
    (`th_view.py:941`, `:976`); la cancellazione di una selezione salta le righe
    protette (`resources/common/tables/_default/action/_common/delete_selection_rows.py:24-28`).
- **Nessun controllo nel ciclo di scrittura:** in `gnrpy/gnr` e
  `resources/common` non ci sono override di `protect_update` /
  `protect_delete`, e quelli di base non fanno nulla (`triggers.py:140-150`). La
  protezione vale solo nell'interfaccia e nelle informazioni del record, salvo
  override dell'applicazione.
- Produttori a livello di package: `lgcy/main.py:61`, `multidb/main.py:84` (una
  `__protected_by_mainstore` fisica), `orgn/model/annotation.py:94`.

## 20. Metodi `_release_*`: colonna `__release`

- `__release` (L) se in `dir(self)` esiste un metodo `_release_<N>`
  (`gnrdbo.py:510-511`).
- `getReleases` (`gnrsqltable/utils.py:390-410`) richiede metodi numerati 1..N;
  ognuno restituisce un dict con `updater` ed eventuale `extra_columns`.
- `updateRecordsToLastRelease_raw` (`utils.py:412-450`) legge le righe con
  `__release IS NULL OR < N`, applica gli updater mancanti, imposta
  `__release=N` e chiama `raw_update`. Il chiamante è il batch
  `resources/common/tables/_default/action/_common/release_updater.py:21-23`.

## 21. `sysrecords`, metodi `sysRecord_*`, `syscodeTag`

- Se `sysrecords is None`, diventa l'elenco dei nomi di `dir(self)` che
  iniziano con `sysRecord_` (`gnrdbo.py:513-514`).
- Creati (`gnrdbo.py:515-526`):
  - `__syscode`: `size=':20'`, `unique`, `indexed`;
  - formula `__protected_by_syscode` (B): `CASE WHEN $__syscode IS NULL THEN NULL
    ELSE NOT (',' || :env_userTags || ',' LIKE '%%,' || :systag || ',%%') END`,
    con `var_systag` dall'attributo `syscodeTag`, default `'superadmin'`; entra in
    `__protecting_reasons`;
  - formula `__invalid_by_duplicate_sysrecord`: `$__syscode LIKE '_ERR_DUP_%'`.
    Nessuno scrive `_ERR_DUP_` in `gnrpy`, `projects` o `resources`.
- Comportamento:
  - `sysRecord(code)` è `cachedRecord(code, keyField='__syscode',
    createCb=_sysRecordCreateCb)` (`gnrdbo.py:860-861`; `gnrsqltable/record.py:183-232`);
  - `_sysRecordCreateCb` (`gnrdbo.py:863-884`) gira sotto
    `tempEnv(connectionName='system')`, chiama `sysRecord_<code>()`; se una riga
    corrisponde già a `sysRecord_masterfield` (default la pkey) la aggiorna con
    `__syscode`, altrimenti inserisce; poi fa commit;
  - la pkey deriva dal syscode (`utils.py:118-129`);
  - `createSysRecords` (`gnrdbo.py:832-858`) crea i metodi con `mandatory=True`,
    o li aggiorna con `do_update`; gira all'aggiornamento del DB con
    `onDbUpgrade_createSysRecords` (`gnrdbo.py:829-830`; dispatch
    `tableBroadcast('onDbUpgrade,onDbUpgrade_*')` in `gnrapp.py:826`).
- Lettori: `guessPkey` risolve un identificativo con `sysRecord_<id>`
  (`gnrsqltable/record.py:297-298`); `cleanWrongSysRecordPkeys` (`utils.py:57-69`);
  il caricamento dei dati iniziali rifiuta discrepanze fra syscode e id
  (`gnrdbo.py:187-195`); l'import di archivi azzera `__syscode`
  (`gnrsql/schema.py:169-170`); `adm.htag` usa `sysRecord_masterfield`
  (`adm/model/htag.py:11`); `gnr/lib/services/rms.py:78` chiama
  `sysRecord('_SYSTEM_')`.

## 22. `sysFields_extra`

- È l'ultima istruzione di `sysFields` (`gnrdbo.py:527`): chiama ogni metodo di
  `dir(self)` che inizia con `sysFields_extra_` e non finisce con `_`
  (`gnrdbo.py:632-634`).
- Unica implementazione: `TotalizeTable.sysFields_extra_totalize`, che aggiunge
  `_refcount` (L, `totalize_value=1`) (`gnrdbo.py:1972-1977`).

## 23. `checkAutoStatic` (`gnrsqlmodel/model.py:390-429`)

- Gira da `addRelation` quando `onDelete == 'cascade' and db.auto_static_enabled`,
  oppure quando la relazione ha `childmode` (`model.py:352-358`).
  `auto_static_enabled` vale `boolean(config['db?auto_static_enabled']) is not
  False` con un'applicazione; in standalone vale `None` (`gnrsql/db.py:355-362`).
- Per `draftField` e `logicalDeletionField`: se il padre ha l'attributo e la
  figlia no, aggiunge alla figlia `aliasColumn(<campo del padre>,
  '@<fkey>.<campo>', static=True, group='zz')` e imposta l'attributo della figlia
  allo stesso nome, sia nel sorgente sia nell'oggetto compilato
  (`model.py:416-429`).
- Effetto: le colonne virtuali static entrano sempre in `*` e nel caricamento dei
  record (`gnrsqlmodel/table.py:395-402`, `:490`; `compiler.py:1246`). I filtri
  `$__del_ts IS NULL` / `$__is_draft IS NOT TRUE` della figlia
  (`compiler.py:979-989`) si risolvono quindi con il join verso il padre. La
  figlia non ha un `__del_ts` fisico, salvo `sysFields(ldel=True)`: in quel caso
  l'attributo proprio c'è e l'alias non si crea.
- Durante la costruzione, `aliasColumn` → `virtualColumn` inserisce direttamente
  nel modello compilato quando `auto_static_enabled` (`model.py:1028-1037`).

## 24. Configurazione, introspezione, ordine di dichiarazione

- Configurazione: `config['db?use_timezone']` (`gnrdbo.py:360`),
  `config['sysfield?user_ins'|'user_upd']` (`:533-537`),
  `config['db?auto_static_enabled']` (`db.py:362`).
- Introspezione della classe (`dir(self)`): `_release_*` (`:510`), `sysRecord_*`
  (`:514`), `sysFields_extra_*` (`:633`); in esecuzione `counter_*` (`:1485`),
  `sysRecord_*` con `mandatory` (`:834-838`), `sql_formula_*` (`compiler.py:397`).
- Ordine:
  - `pkey` diventa `'id'` solo se manca (`:351-353`);
  - `order_by` usa `setdefault` (`:438`, `:455`, `:458`): vince un `order_by`
    dichiarato prima; con gerarchia e contatore la riga `:438` è saltata;
  - `lastTS` si imposta solo se manca (`:369-371`);
  - `broadcast` viene esteso, non sostituito (`:440-444`);
  - i campi nominati da `hierarchical` devono essere già dichiarati
    (`tbl.column(fld)` a `:423`);
  - `__record_pointer` legge `tbl.attributes['fullname']` al momento della
    chiamata (`:354`);
  - i trigger di colonna girano nell'ordine di dichiarazione
    (`columns.py:238-244`): `__ins_ts` e `__mod_ts` (`:361-368`) prima di
    `parent_id` (`:385`);
  - `linkHierarchicalToMaster` e `addRelXtdRelidxColumn` sono differiti a
    `runOnBuildingCb` (`model.py:183`), quindi possono modificare il sorgente di
    altre tabelle.
- `TableBase._isReadOnly` (`gnrdbo.py:682-690`) nasconde
  `TriggersMixin._isReadOnly` (`triggers.py:186-188`) sulle tabelle dbo;
  restituisce `False` di default, il che maschera il problema `is not False`
  annotato a `triggers.py:199`.

## 25. Asqueel oggi (`main` `5b7c11db`)

- **Policy di riga.** Attributi di tabella `x_draft_field`,
  `x_logical_deletion_field`, `x_partition` / `x_partitions`, letti da
  `_parse_row_policies` (`src/asqueel/model.py:290-318`) in
  `RowPolicies(partitions, draft_field, logical_deletion_field)`
  (`contracts.py:44-55`); rifiutati fuori dalla tabella (`model.py:41-46`).
  `validate_row_policies` (`model.py:348-391`) richiede:
  - il campo bozza deve essere una **colonna fisica booleana della stessa
    tabella** (`relational=False`, `model.py:378-381`);
  - il campo di cancellazione una colonna fisica nullable;
  - i due campi diversi;
  - le partition possono usare path to-one (`model.py:321-345`);
  - le policy non si deducono dai nomi delle colonne (`model.py:349-353`).
  Per la regola `relational=False` non c'è l'equivalente dell'ereditarietà di
  `checkAutoStatic`.
- **Compiler.** `select_policies` (`compiler.py:326-347`) aggiunge
  `<draft> IS NOT TRUE` e `<ldel> IS NULL`, oppure `'mark'` con la proiezione
  `_isdeleted`; la modalità mark rifiuta le proiezioni con formule. Default
  `exclude_draft=True`, `exclude_logical_deleted=True` (`compiler.py:630-631`,
  `:699-700`); le subquery hanno `False` (`:412-414`). `_tombstone` /
  `soft_delete` / `restore` (`compiler.py:784-802`; `application_table.py:342-355`)
  sono update espliciti del campo di cancellazione; `soft_delete` richiede un
  valore non `None` passato dal chiamante; nessuna cascata alle figlie e nessun
  hook `onArchivingRecord`.
- **Ciclo di scrittura** (`writes.py:69-159`): `onWriting` → `trigger_on*ing`
  della tabella → `onExecutingWrite` → SQL → `_onDbChange` → `trigger_on*ed` →
  `onWritten`. Update e delete bloccano e uniscono prima il record vecchio
  (`writes.py:103-106`, `:143`; `_locked_record` in `application_table.py:302-310`).
  I raw saltano solo gli hook di tabella. Mancano: trigger di colonna,
  `checkPkey`, contatori, cascata `deleteRelated` / `updateRelated`, `dbo_on*`,
  `protect_*`, controllo `lastTS`, salvataggio di record cluster.
- **Ambiente.** `SqlEnvironment` (`environment.py:27-72`) e
  `ApplicationEnvironment` (`:75-138`, `tempEnv` legacy, default di `workdate` e
  `locale`); `:env_<chiave>` dall'istantanea dell'ambiente (`compiler.py:175-185`).
  Nessun `currentUser`, `userTags` o ripiego sulla pagina.
- **Formule.** `sql_formula=True` (callback di metodo) alza
  `UnsupportedFeatureError` (`model.py:164-165`): è il meccanismo dietro
  `__protecting_reasons` e `__invalid_reasons`.
- **Modello e DDL.** `column(unique=, indexed=, sqldefault=, generated_expression=)`
  (`elements.py:222-255`) e `aliasColumn` (`elements.py:258`).
- **Roadmap.** `roadmap/05_grammar_design.md:285-311`, `:333-337` tratta
  `sysFields` come blocchi di colonne riusabili del livello applicativo, con
  decisione aperta.
- Non presenti: handler gerarchico, sysrecords, contatori, audit, broadcast,
  `lastTS`, `_sendback`, `_sysfield`, `invalidFields`, df, `_release_`, unione di
  record.

## 26. Uso nelle applicazioni (Sourcerer)

Copertura parziale: circa il 57–62% dei moduli (limite di 40 pagine). Dati e
parser: scratchpad della sessione, `sysfields/calls.json`.

- **1617 chiamate in 61 repository applicativi**; 108 nel framework `genropy`.
- Per repository: erpy 283, icond 114, teamset 101, risco 82, erpylight 79,
  pfrc 78, teamset_v1 59, erpyready 52, colto 51, aisla 45, mbe 42, writers 37,
  dlfgest 36, gnrcommunication 33, contractmanager 31.
- Numero di argomenti per chiamata: 0 → 940, 1 → 460, 2 → 144, 3 → 48, 4 → 8,
  5 → 17.

| Argomento | Chiamate | Valori |
|---|---|---|
| `id` | 276 | `False` 244; `True` 30; `None` 1; `'code'` 1 |
| `counter` | 207 | `True` 97; il nome di una FK 104 (64 nomi diversi); elenco 5; espressione 1 |
| `user_upd` | 120 | `True` 120 |
| `hierarchical` | 85 | un campo 61 (`'descrizione'` 30, `'description'` 10, `'name'` 7…); più campi 22; `True` 2 |
| `df` | 69 | `True` 67; `False` 2 |
| `user_ins` | 60 | `True` 47; `False` 13 |
| `draftField` | 52 | `True` 52, nessun nome personalizzato |
| `ldel` | 34 | `False` 34 |
| `ins` | 21 | `False` 17; `True` 4 |
| `upd` | 21 | `False` 18; `True` 3 |
| `group` | 12 | `'_'` 4, `'j_system'` 2, `'z'` 2, `'group_di'` 2, altri |
| `full_upd` | 11 | `True` 11 |
| `hierarchical_root_id` | 7 | `True` 7 |
| `invalidFields` | 7 | `True` 7 |
| `useProtectionTag` | 6 | `'superadmin'` 6 |
| `relidx` | 5 | `'ordine_id'` 3, `'produzione_id'` 2 |
| `hdepth` | 2 | 3 |
| `md5` | 1 | `True` |
| `invalidRelations` | 1 | `'@esperienze'` |
| `counter_*` | 3 | per esempio `counter_ordine=True`, `counter_ordvis=True` |
| fuori firma (assorbiti da `**kwargs`) | 9 | `pkey=False` 5; `audit=True` 2; `changelog=True` 1; `useProtectionTags=True` 1 (refuso) |

- Mai usati nelle applicazioni: `hierarchical_virtual_roots`,
  `hierarchical_linked_to`, `group_name`, `sysrecords`, `counter_kwargs`
  esplicito. Il framework usa `sysrecords=True` (1) e `mod=False` (1).
- Combinazioni principali: nessun argomento 940 (58,1%); `id=False` 193 (70,1%
  cumulato); `counter='<fkey>'` 97 (76,1%); `user_upd=True` 50 (79,2%);
  `draftField=True` 34 (81,3%); `user_ins=True, user_upd=True` 29 (83,1%);
  `counter=True, hierarchical=<campi>` 27 (84,7%); con `df=True` 23 (86,1%);
  `counter=True` 20 e `df=True` 20 (88,6%); tabelle di totalizzazione
  `id=False, ins=False, upd=False, ldel=False, user_ins=False` 13 (89,4%). Le
  prime 15 forme coprono il 92,2%.

| Elemento | Conteggio |
|---|---|
| metodi `def sysRecord_` | 2232 in 370 moduli di 42 repository; 1974 con `@metadata(mandatory=True)` |
| metodi `def sysFields_extra_` | 0 nelle applicazioni |
| metodi `def _release_` | 3, tutti in pfrc (`_release_1`) |
| `audit=` in `pkg.table(` | 25: `True` 16, `False` 5, `'lazy'` 4 |
| `diagnostic=` | 3, tutti `True` |
| `unifyRecordsTag=` | 70 in 22 repository, quasi tutti `'admin'` |
| `syscodeTag=` | 2, entrambi `'admin'` |
| `lastTS=` esplicito | 0 |
| `id=False` con `pkey=` | 235 su 244; pkey `codice` 126, `code` 44, `codekey` 12, `id` 11, `nome` 5 |

- Caso inverso: 27 tabelle dichiarano una pkey diversa da `id` (soprattutto
  `codice`) e chiamano `sysFields` con `id=True` di default; in 5 di queste
  `pkey=False` è passato a `sysFields` invece di `id=False`.

## 27. Meccanismi del nucleo richiesti

1. **Blocchi di colonne e attributi in dichiarazione**, con default che
   rispettano quanto già dichiarato (`pkey`, `order_by`, `lastTS`); callback
   differite su altre tabelle; introspezione della classe (`_release_*`,
   `sysRecord_*`, `sysFields_extra_*`). Servono a tutte le funzioni.
2. **Trigger di colonna** per nome, nell'ordine di dichiarazione, con
   `trigger_table` opzionale e il flag `_notUserChange`: timestamp, utente, md5,
   contatori, relidx, audit, protection tag, gerarchia, radice collegata.
3. **Ciclo di scrittura completo** con `old_record` e hook di tabella
   (`dbo_on*`, `protect_draft`, assegnazione e rilascio contatori,
   `updateRelated`/`deleteRelated`, `_onDbChange`, evento applicativo dopo la
   scrittura): bozza, cancellazione logica con archiviazione delle figlie e
   ripristino delle unioni, diagnostica, audit e broadcast, cascata gerarchica.
4. **Valori di ambiente**: `user`, `userTags`, `workdate`, `external_host`,
   `env_transaction_id`; configurazione: `db?use_timezone`,
   `sysfield?user_ins/user_upd`, `db?auto_static_enabled`.
5. **Policy di riga** con ereditarietà verso le figlie a cascata
   (`checkAutoStatic`). Asqueel ha le policy ma richiede la colonna fisica nella
   stessa tabella.
6. **Concorrenza ottimistica e salvataggio di record cluster**: `lastTS`,
   `noChangeMerge`, `noTestForMerge`, `invalidFields`, contratto `_sendback` con
   il client.
7. **Contatori**: massimo più uno per combinazione di FK, con le scelte su bozze
   e cancellati; `relidx` con la tabella `xtd`; sequenze `adm.counter` legate alla
   bozza.
8. **Handler gerarchico**: path, `root_id`, nodi virtuali, `hdepth`, radice
   collegata, contatore nella gerarchia; API di albero, path e antenati; valori
   SQL in scrittura (`sql_value`).
9. **Record di sistema**: `__syscode` unico, `sysRecord()` con creazione
   differita sotto la connessione di sistema, pkey dal syscode,
   `createSysRecords` all'aggiornamento del DB, risoluzione `guessPkey`.
10. **Motivi di protezione e invalidità**: formule generate da metodi
    (`sql_formula=True`) che raccolgono `__protected_by_*` / `__invalid_by_*`,
    parametri `var_*`. Nessun controllo lato server di default. Asqueel oggi
    rifiuta `sql_formula=True`.
11. **Audit e broadcast**: tabella `adm.audit`, attributo `audit`, payload di
    `broadcast`, agganciati all'evento dopo la scrittura dell'applicazione web.
12. **Aggiornamenti per versione**: `__release` e updater `_release_N` con
    `raw_update`.
13. **Form dinamici (df)**: solo colonne; il comportamento sta nell'interfaccia e
    nei metodi `df_*`.
