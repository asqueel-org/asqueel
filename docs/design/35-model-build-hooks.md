# 35 — Hook del legacy durante e dopo la costruzione del modello

Stato: analisi, nessuna decisione presa. Riferimenti: genropy `origin/develop`
`1561d6547d`; asqueel `main` `5b7c11d`. Path GenroPy relativi alla radice del
repository; path asqueel relativi a `src/asqueel/`.

## 1. Sequenza di avvio dell'applicazione

`GnrApp.__init__` → `init()` (`gnrpy/gnr/app/gnrapp.py:943`):

1. `onIniting()` (`:1033`).
2. Ciclo `addPackage` (`:1045`), che crea un `GnrPackage` per ogni package (`:1281`).
3. `GnrSqlAppDb(...)` (`:1081`); dentro, `GnrSqlDb.__init__` chiama
   `createModel()` (`gnrsql/db.py:149`) e poi `registerMacros()` (`db.py:158`).
4. Per ogni package: `initTableMixinDict()` (`:1084`), `db.packageMixin`
   (`:1085`), `db.tableMixin` (`:1087`).
5. `pkgBroadcast('onDbStarting')` (`:1089`).
6. `db.startup()` (`:1090`): `model.build()` (`db.py:381`), poi `started=True`
   (`db.py:382`).
7. `AppLocalizer` (`:1096`).
8. `onInited()` (`:1097`), che esegue `pkgBroadcast('onApplicationInited')` (`:1490`).

Dentro `DbModel.build` (`gnrpy/gnr/sql/gnrsqlmodel/model.py:107-192`):

1. tutti i `config_db` delle tabelle (`:142-170`);
2. tutti i `config_db` dei package (`:172-176`);
3. `moduleDict` (`:179`);
4. i metodi `onBuildingDbobj` (`:180-181`);
5. `runOnBuildingCb` (`:183`);
6. compilazione: `DbModelObj.makeRoot` (`:187`);
7. ripetizione delle relazioni con `addRelation` (`:188-190`).

## 2. Costruzione di ogni oggetto compilato

`GnrStructObj.__init__` (`gnrpy/gnr/core/gnrstructures.py:255-287`):
`_captureChildren` (`:281`) → `init()` (`:282`) → `parent.newChild` (`:284`) →
`buildChildren` (`:286`; un figlio entra in `parent.children` solo dopo il suo
costruttore, `:303-304`) → `afterChildrenCreation()` (`:287`).

`DbModelObj.init` (`gnrsqlmodel/obj.py:46-64`): `_getMixinObj()` (`:56`, per le
tabelle crea `SqlTable(self)`) → mixin registrato (`:58`) → attributo `mixin`
(`:59-63`) → `doInit()` (`:64`).

## 3. Elenco degli hook in ordine di esecuzione

Uso applicativo da Sourcerer, deduplicato per repo/path/riga, escluso genropy.

| # | Fase | Hook | Default | Chiamante | Argomenti, `self` | Può modificare | Esempi nel framework | Uso applicativo |
|---|---|---|---|---|---|---|---|---|
| 1 | avvio app | `GnrApp.onIniting` | no-op, `gnrapp.py:1481` | `gnrapp.py:1033` | nessuno; GnrApp (override in `custom/custom.py`, `:937-939`) | stato dell'app; DB e modello non esistono | nessuno | non contato |
| 2 | caricamento package | `config_attributes` | `gnrapp.py:760` (`{}`) | `:651`, `:660` | nessuno; pkgMixin | attributi del package | ogni `main.py`, es. `projects/gnrcore/packages/orgn/main.py:6` | non contato |
| 3 | caricamento package | `required_packages` | `gnrapp.py:689` (`[]`), forma attributo `:670-675` | `:1284` | nessuno | package caricati; i richiesti prima | non verificato | non contato |
| 4 | costruzione DB | `registerMacros(db)` | `db.py:211`; `gnrapp.py:374` | `db.py:158` → `gnrapp.py:397` `pkgBroadcast('registerMacros', self)` | `db` (`app.db` non ancora assegnato, `:383-386`); GnrPackage | registry delle macro (`db.addMacro`, `db.py:225`) | `projects/test_invoice/packages/invc/main.py:20` | non contato |
| 5 | sorgente | `GnrPackage.configure` | `gnrapp.py:789-812` | `:691` | nessuno | `struct.package(...)` (`:803`), `model/config_db.xml` (`:805-808`), `custom/<pkg>/model/config_db.xml` (`:810-812`) | — | — |
| 6 | sorgente | `config_db(pkg)` della tabella | via `_doObjMixinConfig` (`model.py:125-127`) | `model.py:154`; tabelle in ordine alfabetico nel package (`:146-147`), package in ordine di registrazione | `pkgsrc`; GnrMixinObj con `.db`, `._tblname`, `._cls` (`:150-153`) | sorgente di qualunque package | 186 `def config_db(` in `projects/`; `gnrdbo.py:1666`, `:1711`, `:2111`, `:2143` | non contato |
| 7 | sorgente | `config_db_<pkgid>(pkg)` (estensione da un altro package) | mixin con suffisso da `model/_packages/<pkg>/<tbl>.py` (`gnrapp.py:743-746`) | `model.py:129-137`, subito dopo il `config_db` della tabella | `pkgsrc`; la sottoscrizione `customize_<pkg>` marca le colonne con `_owner_package` (`:120-123`, `:132-135`) | sorgente | `projects/gnrcore/packages/multidb/lib/storetable.py:6` | non contato |
| 8 | sorgente | `config_db_custom(pkg)` | opzionale | `model.py:139-140` | `pkgsrc` | sorgente | nessuno | non contato |
| 9 | sorgente | helper di `TableBase` in `config_db`: `sysFields`, `sysFields_extra_*` (`gnrdbo.py:632-634`), scansioni `sysRecord_*` (`:514`) e `_release_*` (`:510`) | `gnrdbo.py:324` | il `config_db` | nodo `tbl` | colonne e attributi; registra `deferOnBuilding` (`:407`, `:463`) | `gnrdbo.py:1976` | vedi documento 34 |
| 10 | sorgente | `onTableConfig(tbl)` | **non è un hook del framework**: metodo vuoto che `XTDTable` (`gnrdbo.py:1698`) e `AttachmentTable` (`:1816`) chiamano dal proprio `config_db` (`:1696`, `:1766`) | `gnrdbo.py:1696`, `:1766` | nodo `tbl`; mixin di tabella | sorgente della tabella xtd/atc | nessuno | circa 37 implementazioni in 13 repository, quasi tutte `*_atc`; es. `amnis model/anagrafica_atc.py:5`, `anaci packages/anc_base/model/socio_atc.py:11` |
| 11 | sorgente | `ext_config(tblsrc, colname, colattr, **kw)` | nessuno | `model.py:952-956`, in `DbModelSrc.column` con argomenti `ext_<pkg>_*` | GnrPackage | sorgente | nessuno | non contato |
| 12 | sorgente | `handleLocalizedColumn(tblsrc, colname, colattr, languages)` | `gnrdbo.py:219` | `model.py:958-965`, in `column()` con `localized` | GnrPackage | colonne per lingua e colgroup | `gnrdbo.py:219` | non contato |
| 13 | sorgente | `_decorateChildAttributes` (colgroup) | `model.py:840-851` | `gnrstructures.py:176-179` | argomenti del figlio | attributi del figlio | interno | — |
| 14 | fine sorgente | `config_db(pkg)` / `config_db_<pkg>` / `config_db_custom` del package | `_doObjMixinConfig` | `model.py:176`, dopo **tutti** i `config_db` delle tabelle | `pkgsrc`; pkgMixin con `.db` (`:175`) | sorgente | quasi ogni `main.py` ha `config_db(self,pkg): pass` (`orgn/main.py:10`) | non contato |
| 15 | fine sorgente | `onBuildingDbobj()` | opzionale nella classe Package | raccolti a `model.py:177-178`, eseguiti a `:180-181` nell'ordine dei mixin dei package | nessuno; pkgMixin (`self.db.model.src`, `self.db.model.mixins`) | tutto il sorgente, anche tabelle di altri package; può registrare `deferOnBuilding` | `multidb/main.py:70`, `lgcy/main.py:30`, `orgn/main.py:17` | circa 8 in 6 repository (teamset `main.py:33`, `packages/wkfl/main.py:33`, gnrextra, gnrdbextra, gnrexperiments, gnrwork) |
| 16 | fine sorgente | `deferOnBuilding(cb,*a,**kw)` / `runOnBuildingCb()` | `model.py:97-105`, `:91-95` | `model.py:183` | argomenti salvati | sorgente | `compositeColumn` (`model.py:1099` → `_buildCompositeColumnFormula` `:1105-1142`); `gnrdbo.py:407`, `:463` | non contato |
| 17 | compilazione package | mixin del package su `DbPackageObj` e `__onmixin__` | `obj.py:58`; `gnrlang.py:613-614` | `obj.py:58` | — | oggetto package compilato | — | — |
| 18 | compilazione tabella | `SqlTable.__init__` → `HierarchicalHandler` / `XTDHandler` | `gnrsqltable/table.py:74-85` | `obj.py:56` tramite `gnrsqlmodel/table.py:105-107`, **prima** del mixin | legge `tblobj.attributes['hierarchical'/'xtdtable']` | attributi di dbtable | `gnrsqltable_proxy/hierarchical.py:204`, `xtd.py:26` | — |
| 19 | compilazione tabella | mixin della tabella su SqlTable (`_plugins`, `_pluginId`), attributo `mixin`, `__onmixin__` | `obj.py:58-63` | — | — | metodi di dbtable | — | — |
| 20 | compilazione tabella | `SqlTable.onIniting()` / `onInited()` | no-op, `gnrsqltable/utils.py:158`, `:162` | `gnrsqlmodel/table.py:60`, `:65` (`DbTableObj.doInit`) | nessuno; SqlTable | gira **prima** che esistano le colonne | nessuno in `projects/` | non contato |
| 21 | compilazione colonna | `custom_type_<dtype>()` | metodo del package, cercato su `DbPackageObj` | `columns.py:126-133` (`DbBaseColumnObj.doInit`); `baseDtype` in `helpers.py:101` per `bagItemColumn` (`model.py:1169-1172`) | nessuno; restituisce un dict con `dtype` | attributi della colonna (gli espliciti vincono) | `projects/test_invoice/packages/invc/main.py:27`, `:30` | almeno 154 righe in circa 22 repository (conteggio troncato); es. erpy `custom_type_money/qta/cambio`, `dlfgest main.py:13` |
| 22 | compilazione colonna | `DbColumnObj.doInit` (interno) | `columns.py:220-244` | `obj.py:64` | — | `table.sqlnamemapper`; accoda relazioni in `model._columnsWithRelations` (`:230-232`); `_indexedColumn`; `_fieldTriggers` da `onInserting`…`onDeleted` (`:237-244`) | — | — |
| 23 | compilazione colonna virtuale | `DbVirtualColumnObj.doInit` | `columns.py:266-284` | `obj.py:64` | — | accoda relazioni virtuali (`virtual=True`) | — | — |
| 24 | fine tabella | `DbTableObj.afterChildrenCreation` | `gnrsqlmodel/table.py:67-81` | `gnrstructures.py:287` | — | contenitori vuoti e indici da `_indexedColumn` | — | — |
| 25 | dopo compilazione | `addRelation` → `checkRelationIndex`, `checkAutoStatic` | `model.py:195-368`, `:370-388`, `:390-429` | `model.py:188-190` | `reldict` salvato | `model.relations`; indici nel modello compilato; `checkAutoStatic` scrive su **sorgente e oggetto** (`:420-429`) | — | — |
| 26 | prima della build | `onDbStarting()` | nessun default | `gnrapp.py:1089`, **prima** di `db.startup`, quindi prima della build nonostante il nome | nessuno; GnrPackage (`self.db` disponibile) | attributi del DB; modello non ancora costruito | `projects/gnrcore/packages/sys/main.py:15` (`db.changeLogTable`) | 0 |
| 27 | dopo la build | `GnrApp.onInited` → `onApplicationInited()` dei package | `gnrapp.py:1485-1490`; default no-op `:814` | `gnrapp.py:1097` | nessuno; GnrPackage | oggetti compilati e dbtable (per esempio `instanceMixin` su SqlTable); `_doMixin` rifiutato dopo l'avvio (`model.py:512-513`) | `multidb/main.py:38-46`, `lgcy/main.py:20-28` | circa 18 in 6 repository (gnrdbextra, gnrwork, teamset, erpy `main.py:56`, gnrextra, gnrexperiments) |
| 28 | avvio web | `onSiteInited()` | — | `gnr/web/gnrwsgisite.py:938` | nessuno | runtime | nessuno | non contato |
| 29 | runtime, per ambiente | `formulaColumn_*()`, `variantColumn_<v>(colname,**kw)`, `db.localVirtualColumns` / `customVirtualColumns` | `gnrsqlmodel/table.py:405-427`, `:440-471`; `gnrapp.py:540`, `:564` | proprietà `virtual_columns`, `table.py:358-384` (cache in `currentEnv`) | — | aggiungono `DbVirtualColumnObj` al modello compilato a ogni accesso | `gnrdbo.py:692`, `:732-744`; `gnrsqltable/columns.py:297-392`; `docu/model/documentation.py:49` | non contato |
| 30 | setup del DB | `onDbSetup` del package → `onDbSetup`, `onDbSetup_*` delle tabelle | `gnrapp.py:822-823` | `gnr/app/cli/gnrdbsetup.py:177`; `gnr/db/cli/gnrmigrate.py:253` (dopo il DDL) | nessuno; GnrPackage, poi SqlTable | dati | `adm/model/tblinfo.py:15` (`onDbSetup_populate`) | 0 |
| 31 | aggiornamento del DB | `dbUpgradeBroadcast`: `onDbUpgrade`, `onDbUpgrade_*`, poi `onDbUpgradeDone`, `onDbUpgradeDone_*`; i default dei package inoltrano alle tabelle | `gnrapp.py:1500-1507`, `:825-829` | `gnrdbsetup.py:161`, `:179`; `gnrmigrate.py:214`, `:255`; `multidb/lib/storetable.py:73`; poi `sys.upgrade.runUpgrades` (`gnrdbsetup.py:162`, `:180`) | nessuno | dati | `gnrdbo.py:829` `onDbUpgrade_createSysRecords` (ogni tabella `TableBase`); `sys/model/calendar.py:51`; `glbl/model/nazione.py:17`; `adm/model/userobject.py:106` | 3 in 3 repository (`erpyready model/allergene.py:30`, `erpylight model/causale_cbi.py:13`, `anaci packages/anc_cnv/model/allergene.py:30`) |

`onArchivingRecord` (`gnrsqltable/copy.py:70`) è un hook di runtime
dell'archiviazione, non del ciclo del modello.

## 4. Dipendenze di ordine

- Tutti i `config_db` delle tabelle, di tutti i package, girano prima di ogni
  `config_db` di package (`model.py:142-170` contro `:172-176`): il `config_db`
  del package e `onBuildingDbobj` vedono il sorgente completo delle tabelle.
- Nel package le tabelle girano in ordine alfabetico (`model.py:147`). I
  `config_db` di `XTDTable` e `AttachmentTable` leggono il sorgente del master
  (`gnrdbo.py:1674`, `:1720`): funziona perché `x_xtd` e `x_atc` vengono dopo `x`.
- Le tabelle del package A vedono il sorgente di B solo se B è registrato prima. I
  package richiesti si aggiungono prima di chi li richiede (`gnrapp.py:1284-1287`).
- `onBuildingDbobj` gira nell'ordine di registrazione dei package
  (`gnrapp.py:1083-1085` → Bag dei mixin).
- Le callback differite girano dopo tutti gli `onBuildingDbobj`, in ordine LIFO
  (`pop()`, `model.py:94`); girano anche quelle registrate durante lo
  svuotamento (`while`, `:93`).
- Il proxy `SqlTable` e gli handler gerarchico/xtd nascono prima del mixin
  (`obj.py:56` contro `:58`). `onIniting`/`onInited` girano prima di qualsiasi
  oggetto colonna (`gnrstructures.py:282` contro `:286`).
- Le relazioni esistono solo dopo la compilazione dell'intero albero
  (`model.py:188-190`); il `doInit` delle colonne può solo accodarle.

## 5. Difetti verificati

1. Il broadcast dei package con `*` legge l'app invece del package:
   `_pkgBroadcast` chiama `objectExtract(self, …)` con `self` = GnrApp
   (`gnrapp.py:1514`). I metodi `onDbUpgrade_*`, `onDbSetup_*`,
   `onDbUpgradeDone_*` dei package non vengono mai chiamati; un metodo dell'app
   con quel prefisso viene chiamato una volta per package.
2. I package `readOnly` sono saltati (`gnrapp.py:1511`): non ricevono
   `registerMacros`, `onDbStarting`, `onApplicationInited`, `onDbSetup`,
   `onDbUpgrade`.
3. `tableBroadcast` si interrompe: `changed = changed or self._tableBroadcast(...)`
   (`gnrapp.py:834`). Dopo un evento che restituisce un valore vero, gli eventi
   successivi (per esempio `onDbSetup_*`) non girano per quel package.
4. `autocommit` non viene inoltrato: `tableBroadcast` non lo passa a
   `_tableBroadcast` (`gnrapp.py:831-834`), quindi il commit a `:849-850` non
   avviene mai; la riga `:843` è un assegnamento morto.
5. L'override di un hook perde o duplica il default: `instanceMixin` salva il
   metodo sovrascritto come `nome_` (`gnrlang.py:599-601`).
   - Un package che sovrascrive `onDbSetup`/`onDbUpgrade` sostituisce il
     broadcast di default alle tabelle (`gnrapp.py:822-829`), se non lo chiama.
   - Un override di `onInited` dell'app sopprime `onApplicationInited`, se non
     chiama `onInited_`.
   - Sulle tabelle, un `onDbUpgrade_` salvato corrisponde al pattern
     `onDbUpgrade_*` (`objectExtract`, `gnrlang.py:128-134`), quindi gira anche
     l'originale sovrascritto. Ricavato dal codice, non eseguito.
6. `onDbStarting` gira prima della costruzione del modello (`gnrapp.py:1089`
   contro `:1090`).
7. `registerMacros` gira prima che `app.db` sia assegnato (`db.py:158` dentro il
   costruttore a `gnrapp.py:1081`): per questo riceve `db` come argomento.
8. Il modello compilato viene modificato durante la costruzione del sorgente:
   `virtual_column` scrive nel modello compilato quando `obj` esiste già
   (`model.py:1028-1037`, marcato REVIEW); `checkAutoStatic` modifica sorgente e
   oggetto dopo la compilazione (`model.py:420-429`).
9. `addRelation` intercetta ogni eccezione e la registra soltanto, salvo debug
   (`model.py:360-368`).
10. La docstring di `GnrPackage.configure` elenca i passi di `config_db`
    (`gnrapp.py:790-800`), ma il metodo dichiara solo il package e l'XML
    (`:802-812`); le chiamate reali stanno a `model.py:142-176`.
11. `virtual_columns` non è thread-safe: la proprietà modifica `children` e
    `currentEnv` in lettura (`gnrsqlmodel/table.py:365-368`).

## 6. Asqueel oggi

- **Sorgente:** la grammatica `SqlBuilder` ha un `main(self, root)` vuoto
  (`builder.py:74`). Non verificato dove genro-builders lo chiama.
- **Configurazione:** `_owned_handler` (`configuration.py:87-92`) sovrappone le
  ricette `ConfigHandler`; `_effective_model_builder` (`configuration.py:179-199`)
  copia il builder e scrive i default di configurazione e di firma sui nodi. È
  l'unico passo che rielabora il sorgente.
- **Risoluzione del modello:** `resolve_model` (`model.py:33-146`) esegue
  `validate_model` (`:39`), il passo tabelle/colonne (`:51-120`), il passo
  relazioni (`:121-144`), `_resolve_aliases` (`:145`) e `validate_row_policies`
  (`:146`). Non accetta callback e rifiuta le funzioni basate su callback:
  subquery con metodo (`:151`), formule SQL con metodo (`:165`),
  `virtualRelation` (`:46-47`), scope partition/subtable/tenant/store (`:55-56`).
- **Applicazione:** `AsqueelDb` (`application.py:71-85`): configurazione →
  `resolve_model` → `SqlDatabase.__init__` (`:18-48`). L'unico punto di
  estensione per tabella è l'attributo `x_table_class` (`:44-47`), una
  sottoclasse di `SqlTable` istanziata come `table_class(db, descriptor)`.
  `SqlTable.__init__` (`application_table.py:187-196`) crea le handle di colonne
  e relazioni.
- **Registry:** `DatabaseRegistry` (`registry.py:14-63`) contiene solo schede con
  path, senza hook.
- **Niente gira dopo la risoluzione o dopo l'apertura del DB:** nessun equivalente
  di `onBuildingDbobj`, `deferOnBuilding`, `onIniting`/`onInited`,
  `custom_type`, `onDbStarting`, `onApplicationInited`, `onDbSetup`,
  `onDbUpgrade`. La connessione si apre alla prima esecuzione
  (`runtime.py:369-374`), senza hook di connessione.
- **Solo hook di runtime:** `trigger_on*` della tabella
  (`application_table.py:270-287`); `onWriting`, `onExecutingWrite`,
  `_onDbChange`, `onWritten` del DB (`writes.py:9-19`); `deferToCommit` /
  `deferAfterCommit` (`runtime.py:206-214`).
