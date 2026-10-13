# 52 — Fase 0: copertura legacy e differenze prima del render

13 ottobre 2026. **Ricognizione completata sui tre package e sui 75 modelli;
render non modificato.** D-01 e D-02 sono chiuse dalle esclusioni confermate
dall'utente: system_records e sys.locked_record fuori perimetro. La copertura
qui attestata è del censimento e delle aspettative, non del porting nativo.

Il riferimento legacy resta di 75 tabelle. Il corpus nativo previsto è di
**74 tabelle: sys 16, adm 40, invc 18**. L'obiettivo è la vicinanza al legacy
nel perimetro concordato, con divergenze esplicite, non il suo rimpiazzo
integrale. **Incremento successivo approvato:** `sys_fields(syscode=True)` è
implementata per la sola colonna indicizzata e UNIQUE; system_records resta
escluso. Le osservazioni sul render invariato descrivono la ricognizione iniziale.

Questo rapporto aggiorna il [censimento 43](43-test-invoice-model-coverage.md)
secondo le decisioni successive 40/41/49/50 e la fase 0 del
[piano 51](51-source-to-live-objects-plan.md). Non riattiva provider, behavior,
normalize, macro di modello, inverse virtuali o altre proposte superate.

## Evidenze e limiti

- Riesaminati i 76 file modello e i tre `main.py`: 17 sys, 41 adm, 18 invc.
  `adm/model/_packages/sys/task.py` contribuisce a una tabella esistente;
  `adm.htmltemplate_atc` eredita `AttachmentTable.config_db`.
- Verificati gli hash di tutti i 79 sorgenti del manifest e dei 227 file
  legacy importati dalla cattura: nessuna variazione. Nessun file aggiunto o
  rimosso dal perimetro del censimento. Verificati gli hash dei tre artefatti
  indipendenti `source.xml`, `model.json`, `physical.json`.
- La cattura legacy è un modello realmente costruito offline nel profilo
  sanificato del [report 45](45-release-baseline-and-oracle.md), non il dump del DB
  installato. Non è stata rigenerata né sono stati letti dati/credenziali del DB.
- Confrontati originali, cattura espansa, firme native, espansione corrente e
  proiezione fisica. Eseguite piccole prove native di grammatica e proiezione
  offline, senza modificare alcuna implementazione.
- L'esempio `examples/model_grammar/configure.py` contiene **8 tabelle
  parziali**. Nessuno dei 75 modelli è ancora certificato completo attraverso
  una source nativa. Il bridge verificato dal report 47 non dimostra tale parità.

| Package | Tabelle | Colonne fisiche | Elementi virtuali legacy | FK | Indici JSON | UNIQUE composite |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| sys | 17 | 195 | 90 | 7 | 56 | 0 |
| adm | 40 | 412 | 240 | 32 | 150 | 0 |
| invc | 18 | 189 | 204 | 19 | 76 | 1 |
| Totale | **75** | **796** | **534** | **58** | **282** | **1** |

I 534 elementi sono 532 colonne virtuali e due composite. Restano inoltre
quattro subtables di customer, il join condizionale di invoice e l'alias
di relazione di invoice_row. I conteggi degli indici del modello legacy sono
diversi da quelli JSON: comprendono anche indici rappresentati nel JSON dalle
chiavi/UNIQUE; non basta sottrarre due totali per trovare gli indici persi.

Evidenza navigabile: [audit JSON](evidence/invoice-render-coverage.json),
[script riproducibile](evidence/audit-invoice-render-coverage.py),
[inventario AST originale](evidence/test-invoice-model-inventory.json).
Il JSON riporta per tabella file, hash, metodi, posizioni delle dichiarazioni,
famiglie, nomi di tutte le colonne/virtuali, contatori fisici e normalizzazioni
di storage osservate. Le colonne non letterali nei file locali sono marcate
come **generate o dinamiche**, non attribuite arbitrariamente a una option:
per esempio i cicli di `sys.calendar` non sono espansioni di `sys_fields`.

## Matrice delle options

Stato comune attuale: `expand_options` rifiuta tutte le TABLE_OPTIONS attive.
`sys_fields` ha una prima espansione incompleta. La presenza di una firma non
equivale quindi al supporto del render. Le tabelle citate sotto sono fixture
legacy indipendenti in `tests/oracles/test_invoice_pg/model.json` e `source.xml`;
le firme sono verificate dai test grammaticali, gli effetti nativi dalle fasi
successive. I numeri indicano impieghi dichiarati o ereditati, non le formule
generate dalle altre options.

| Dichiarazione nativa | Evidenza / fixture | Effetto atteso e dipendenze | Stato / fase |
| --- | --- | --- | --- |
| `sys_fields(...)` | 67 tabelle: sys 13, adm 36, invc 18; `GnrDboTable.sysFields` | PK se richiesta; id, timestamp, utente, logicalDeletionField, lastTS, draftField, gruppo e metadati; `__record_pointer` anche con id=False; quattro virtuali di protezione/invalidità | Parziale; completare in 2. Preservare metodi come dati, senza invocarli. R-02/R-03 separati |
| `sys_fields(syscode=True)` | Campo __syscode legacy di adm.htag/language/xgroup; nuova attivazione esplicita concordata | Solo __syscode A :20, indicizzata e UNIQUE; flag False per default | Implementata con prove in test_syscode.py; nessun system_records |
| `hierarchical(columns=...)` | sys.widget, adm.htag/menu, invc.product_group/product_type | parent_id + FK differita/inversa `_children`, hierarchical_pkey UNIQUE, `_parent_h_pkey`, coppie hierarchical_* / _parent_h_*, child_count, hlevel, attributi ordine/broadcast | Da espandere, 2 e 4. Attenzione a product_group: gerarchia su `code,_row_count`, contatore dichiarato nello stesso sysFields |
| `auto_counter(scope=...)` | 10 tabelle, inclusa AttachmentTable; invoice_row scope invoice_id | `_row_count` L; nelle quattro gerarchie con counter anche `_h_count`, `_parent_h_count`, `_h_sortcol`; conservare scope/order_by | Da espandere in 2. Nessuna assegnazione del contatore |
| `dynamic_fields(templates=...)` | sys.widget, invc.product_type | df_fields X, df_fbcolumns L, df_custom_templates X con templates, df_colswidth; nessuna compilazione dei campi dinamici | Da espandere in 2 |
| `column.dynamic_fields(source=...)` | invc.product.details: subfields='product_type_id' | Conservare il riferimento al campo; dipende dal collegamento a product_type. Non crea altre colonne fisiche | Traduzione dichiarativa, 2/4 |
| `record_hash()` | adm.user, md5=True | `__rec_md5` e attributi legacy; il legacy non specifica un elenco columns | Da espandere in 2; nessun calcolo hash |
| `audit(mode='lazy')` | sys.widget | `__version` L; il ramo legacy lo aggiunge quando audit è attivo | Da espandere in 2; nessun log o incremento |
| `attachments(master='adm.htmltemplate')` | adm.htmltemplate_atc, base AttachmentTable | 16 colonne fisiche e 9 virtuali complessive nel profilo; sys_fields + counter maintable_id + FK differita con SQL cascade; attributo atc_attachmenttable sul master | Da espandere in 3. Riusare espansioni locali, non copiare campi già espansi. Correzione C-02 |
| `partition(name, field=..., value=...)` | invc.customer.state e invoice.customer_state, riferimento legacy invc_state | Conservare campo e valore/resolver esistente; alias customer_state dipende da customer. Nessun DDL o filtro eseguito | Solo dati, 2/4; nessun context registry |
| `tenant()` | adm.counter: multi_tenant=True | Conservare flag; profilo legacy senza tenant_schemas | Solo dati; non inventare tenant_id o schemi tenant |
| `retention(field=..., days=...)` | sys.error: 60; sys.task_execution: 180; campo __ins_ts | Conservare politica | Solo dati; nessuna cancellazione |
| `broadcast(columns=...)`, `archive()` | adm.userobject: objtype e archivable=True | Conservare dati; broadcast parent_id delle gerarchie è invece prodotto dalla loro espansione | Solo dati; nessun evento |
| `enabled_when(preference=...)` | adm.connection e served_page: adm.dev.connection_log_enabled | Conservare checkpref | Solo dati; non eliminare le tabelle durante il render |
| `numbering('inv_number', parameters=...)` | invc.invoice.counter_inv_number | Conservare il dict della regola; non invocare il metodo durante il render né allocare numeri | Solo dati; fase 5 trascrive la dichiarazione originale |
| `system_records(...)` | adm.htag esplicita sysrecords=True; language e xgroup hanno sysRecord_* | Genererebbe __syscode UNIQUE e due virtuali per tabella | **Fuori perimetro R-02; divergenza D-01 accettata**. Firma records/masterfield/tag non approvata |
| `release(...)` | Nessun _release_* né __release nel corpus | Il legacy genera __release L quando rileva i metodi | R-03; nessuno scarto nel corpus. Firma handlers non approvata |
| `full_update()` | Nessun impiego nel corpus; sysFields full_upd | __full_mod_ts DHZ indicizzato | Evidenza nel helper, non copertura del corpus; fixture minima in 2 |
| `protection(...)` | Nessun useProtectionTag nel corpus; sysFields_protectionTag | __protection_tag e __protected_by_tag. Distinti dai quattro virtuali di base, presenti sulle 67 tabelle | Variante da verificare in 2; `rules` non giustificato dal corpus |
| `diagnostics(...)` | Nessun diagnostic/invalidFields/invalidRelations nel corpus | Rami distinti: __warnings/__errors; __invalid_fields e __is_invalid | Non certificata dal corpus; precisare il mapping prima di implementare varianti. Non dedurre i campi da `rules` |
| `relative_index(relation=...)` | Nessun relidx nel corpus; sysFields_relidx/addRelXtdRelidxColumn | `_relidx` locale e contatore nella tabella master_xtd; richiede quella tabella | Fixture minima in 3, nessuna tabella xtd da inventare nel corpus |
| varianti hierarchical root_id/virtual_roots/linked_to/depth | Assenti nel corpus; sysFields/linkHierarchicalToMaster | Campi root/virtuali/livelli; linked_to modifica entrambe le tabelle | Non certificabili con i 75 modelli; fixture dedicate e verifica firma, prima di implementarle |
| `package.options().type(...)`, `.requires(...)` | invc.custom_type_money/perc; adm.required_packages | money N14,2, perc N5,2 e format; dipendenza adm→sys | Infrastruttura presente; portare anche i metadati format. Nessuna macro aggiunta |

Per gli allegati non risultano atc_types/atc_download nel mixin effettivo:
non generare atc_type/atc_download. Non risultano contributi sysFields_extra_*
nelle classi del corpus. `counter_kwargs`, root_id e altri rami assenti non
diventano requisiti impliciti dei 75 modelli.

## Altri costrutti: traduzione da conservare

| Superficie legacy osservata | Traduzione / effetto atteso | Verifica / limite |
| --- | --- | --- |
| Package config_attributes: sqlschema/sqlprefix/comment/name_* e _syspackage | Package e schema dedotto; i dati aggiuntivi restano metadati, nessuno schema separato | Tre main.py e test_release_resolved_model |
| Table, column, dtype/size, notnull, unique, indexed, pkey | Dichiarazioni fisiche; distinguere tipo logico e storage | C-01; conteggi per ogni tabella nel registro |
| pkey_columns / pkey_columns_joiner | Attributi di tabella nei sei casi censiti, incluso `$domain,$key` di shorturl | Non calcolare la chiave; non convertire in PK SQL multicolonna |
| CompositeColumn unique / relazione composite | Due composite price_year/price_year_note, UNIQUE su year,product_id e FK ordinata | Test release_model_semantics + oracolo fisico |
| relation mode=foreignkey, relazione senza mode, relazione su formula | FK fisica oppure relazione debole; conservare azioni applicative, gruppi, one_one e inverse ordinarie | Collegamenti dopo espansioni; non inferire UNIQUE da one_one. C-02/C-03 |
| index('lock_table,lock_pkey', unique=True) | Indice unico composto sulla tabella sys.locked_record | **D-02**: intera tabella fuori perimetro nativo; evidenza storica conservata |
| joinColumn + cnd | VirtualRelation con table/condition/var_* e aliasColumn della chiave target | invoice.discount_tier_id; nessuna colonna/FK fisica. Escludere inverse/one_one virtuali come deciso |
| aliasTable customer | virtualRelation('customer', relation='@invoice_id.@customer_id') | invoice_row; firma aliasTable esclusa, funzione rappresentata dalla virtualRelation |
| aliasColumn, static, dtype | Conservare percorso e override; risolvere identità dopo le relazioni | 13 modelli espliciti; static accettato dalla grammatica attuale |
| formulaColumn, sql_formula, select/exists, select_*, var_* | Conservare dichiarazioni, dict e nomi legacy; nessuna analisi SQL o conversione necessaria in nuovi binding | 23 modelli espliciti + virtuali generati. Probe positivo per select_*/var_*; i formati aggiuntivi parameters/subqueries/handler non sono necessari per portarli |
| subQueryColumn | query/mode/dtype come dati; rows_json, notes_xml, max_row_price di invoice | Non confrontare la source nativa con l'SQL aggregato già generato dal legacy come se fosse la stessa dichiarazione. Query interna da rivedere al compilatore |
| pyColumn, py_method, required_columns, template_* | Metodo simbolico e attributi conservati; default legacy pyColumn_<nome> | Sette modelli inclusi allegati. Probe positivo template_name/localized/outdatedWatermark; nessun registry o esecuzione Python |
| bagItemColumn | Conservare bagcolumn/itempath/dtype | invc.product; niente estrazione XML nel render |
| subtable condition | Quattro filtri su invc.customer, nessun DDL | Conservare le stringhe; non compilare filtri |
| validate_notnull/len/case/nodup/notnull_error; values | Dict validations, prefix stripping; values→validate_values approvato | 13 modelli; nessuna normalize, traduzione messaggi o valutazione delle regole |
| default/defaultFrom/sql_value, readOnly/unmodifiable | default, default_from, sql_value, read_only/unmodifiable come dati | Non convertirli in DEFAULT SQL; defaultValues/workdate è operativo e resta fuori |
| encrypted X/R/Q | encryption(mode=...) | Tre modalità in customer; nessun provider o chiave nel modello |
| group_*, group, colgroup; _addClass/cell_format/format/_sendback/batch_assign | Gruppi e metadati UI conservati | Non sono ragioni per introdurre una grammatica nuova. Nel port mantenere tutte le etichette e gli attributi originali |
| _sysfield/legacy_name/noTestForMerge/name_full, attributi extra | Dati originali/metadati senza effetto DDL implicito | Non promettere rename automatici, merge applicativi o comportamento operativo |
| Cicli, string_agg del dialetto, itemTypeValues | L'host costruisce dichiarazioni concrete; per valori calcolati usare i resolver esistenti quando necessario | Nessun nuovo resolver: itemTypeValues è una costante verificata; un resolver di configurazione non sostituisce un default operativo |
| trigger_*, defaultValues, pkeyValue, registerMacros, sysRecord_* | Riferimenti sorgente censiti; esecuzione esterna a questo traguardo | Nessuna nuova firma behavior/macro. Non eseguire metodi sui record per completare la struttura |

Esempio di traduzione del solo join condizionale, usando esclusivamente la
firma già concordata (non è un'implementazione del compilatore):

```python
invoice.virtualRelation(
    'discount_tier_id', table='invc.discount_tier',
    condition='$customer_type_code = :var_customer_type '
              'AND $min_amount <= :var_total AND $max_amount > :var_total',
    var_customer_type='@customer_id.customer_type_code', var_total='$total')
invoice.aliasColumn('discount_tier_id', relation_path='@discount_tier_id.id')
```

## Divergenze concordate e proposta residua

### D-01 — Rinvio di system_records contro completezza del corpus

Il rinvio R-02 comprendeva esplicitamente l'espansione strutturale. Nel corpus
produce questa conseguenza precisa:

- **adm.htag, adm.language, adm.xgroup:** verrebbero meno tre colonne
  `__syscode`, le rispettive UNIQUE e sei virtuali (`__protected_by_syscode`,
  `__invalid_by_duplicate_sysrecord`). Questi indici unici sono rappresentati
  dall'attributo unique della colonna, non dai 282 indici JSON separati.
- **adm.htag.authorization_tag** è una formula applicativa esplicita,
  `COALESCE($__syscode,$hierarchical_code)`: lasciarla identica senza il campo
  rende il modello incompleto, anche se il compilatore è rimandato.
- **adm.install_checklist.__syscode resta:** dichiarazione esplicita, PK,
  nessun metodo sysRecord_* e nessuna delle due virtuali di sistema.

**Decisione dell'utente:** system_records resta fuori perimetro, anche per
l'espansione strutturale. Si valuterà in futuro se reintrodurre il concetto;
la precedente proposta di riaprirlo per ottenere parità non è accolta.
Le differenze sopra restano nel registro, senza modificare l'oracolo o
reintrodurre funzionalità solo per far coincidere il JSON.

**Alternativa approvata dall'utente e implementata:**
`sys_fields(syscode=True)` dichiara soltanto `__syscode` A size `:20`,
indicizzata e **UNIQUE come nel legacy**. `syscode=False` è il default.
Non genera le due virtuali di system_records, non rileva sysRecord_*,
non crea record e non assegna codici.

Nel port di adm.htag, adm.language e adm.xgroup usare questa attivazione
esplicita per conservare il campo e la UNIQUE; non rilevare automaticamente
i metodi legacy. La dipendenza di authorization_tag può così essere soddisfatta
senza cambiare la formula o reintrodurre system_records. Restano escluse le
sei virtuali di sistema e tutta la gestione dei record. Il precedente scarto
ipotizzato di tre colonne non si applica quando syscode è attivata; la source
nativa completa e i relativi conteggi restano da verificare nelle fasi 5–6.

### D-02 — sys.locked_record fuori perimetro

`sys/model/locked_record.py:15` dichiara un indice unico su
`lock_table,lock_pkey`. Esiste nel modello catturato come
`locked_record_lock_table_lock_pkey_key`, ma `OrmExtractor` non lo esporta.

**Decisione dell'utente:** sys.locked_record è fuori perimetro, non soltanto
il suo indice. La tabella resta nel censimento/oracolo legacy, ma non entra
nella source nativa né nel relativo JSON migrations. Il corpus nativo passa
quindi a 74 tabelle. La proposta di aggiungere quell'indice al nuovo JSON è
superata; il supporto generale agli indici rimane nel perimetro.

## Correzioni necessarie, non nuove scelte di prodotto

**C-01 — Proiezione dei tipi.** Il probe nativo corrente restituisce
`id: A/22`, `bag: X`, `prefix: A/:20`; l'estrattore legacy normalizza a
`C/22`, `T`, `A/0:20`. Nel corpus ci sono 91 CHAR(22), oltre ad altre lunghezze
fisse. X/Z/P vanno proiettati allo storage legacy mantenendo il tipo logico
negli oggetti; alias money/perc e size numeriche richiedono la stessa verifica.
Questa normalizzazione oggi è nel bridge, non nella proiezione nativa completa.
Non cambiare colonne native in C/T nella source solo per copiare il JSON:
rispettare la separazione tipo logico/storage. Fase 6, con controlli già in 2/4.

**C-02 — onDuplicate=False.** AttachmentTable dichiara letteralmente False
sulla relazione maintable_id; la firma `on_duplicate: str | None` lo rifiuta.
Il validatore del render ammette inoltre un catalogo copy/ignore/raise,
mentre il legacy usa anche recursive nella gestione delle duplicazioni.
Il bridge attuale converte False in 'ignore' (e True in 'copy'), conservando
anche l'originale in x_legacy: questa conversione non va trasferita alla source
nativa come se fosse la dichiarazione originale. Per la traduzione conservare
il dato legacy senza un vocabolario esecutivo inventato. Non implementare la
duplicazione. Correzione grammaticale da fare prima dell'espansione allegati.

**C-03 — Deferrability implicita.** `adm.group.no2fa_alternative_group` ha onDelete='setnull'
senza deferred esplicito. `DbModel.addRelation` lo rende differito; il bridge
lo conserva, il percorso nativo attuale non applica questa inferenza.
Riprodurre il legacy in fase 4. L'indicizzazione delle relazioni deboli resta
da controllare su entrambi i lati; non basta il numero delle FK.

**C-04 — Sys_fields incompleta.** Nel codice mancano ancora gruppo/etichette,
attributi di tabella, parte dei metadati e i quattro virtuali standard.
Il fatto che questi descrivano protezione/invalidità non li trasforma in
esecuzione operativa: conservarli come dichiarazioni. Fase 2.

**C-05 — Documenti e varianti non certificate.** Le vecchie matrici 43/47
parlano ancora di provider, normalize, pkey_from e inverse virtuali come parte
della proposta di allora. Il rapporto presente prevale e le marca come storia.
Le varianti assenti nel corpus (per esempio diagnostics.rules, protection.rules,
counter_kwargs) non ricevono un'approvazione implicita dalla copertura dei 75
modelli. Per usarle occorrono verifica specifica della firma o rinvio esplicito;
non bloccano la traduzione delle dichiarazioni effettivamente presenti.

## Differenze già concordate: non riaprire

- `user_upd=True` è il default Asqueel approvato; la cattura ha False. Nel
  corpus nativo dichiarare **user_upd=False** per le 67 tabelle con sys_fields,
  compresa l'espansione degli allegati. Non cambiare il default pubblico.
- DHZ per i timestamp di sistema coincide col profilo catturato. Le **19
  colonne DH applicative** non sono timestamp generati di sistema e non vanno
  convertite tutte automaticamente. Convenzione UTC distinta dal tipo SQL.
- values→validate_values e validate_case conservato nel dict; nessuna normalize.
- AliasTable esclusa come firma, sostituita qui dalla virtualRelation già decisa.
- Inverse, one_one, order_by e limit delle virtualRelation rinviati. Il join di
  invoice perde deliberatamente la dichiarazione di inversa/cardinalità, senza
  effetto sul JSON fisico. Nessuna regressione delle inverse ordinarie.
- Ask/var_* restano come concordati; il corpus non usa ask e non può certificarne
  la futura semantica SQL. Namespace provvisorio rinviato al compilatore.
- Release non produce scarti: non ci sono colonne __release nel corpus.
- Schemi dedotti dai package, resolver esistenti, nessun registro context.

## Riproduzione e verifiche

```sh
PYTHONPATH=src:../asqueel-migration/src /tmp/asqueel-repo-audit-env/bin/python \
  docs/design/evidence/audit-invoice-render-coverage.py \
  /Users/gporcari/Sviluppo/Genropy/genropy \
  /tmp/invoice-render-coverage.json
```

L'ambiente indicato è quello locale di verifica; lo script richiede Asqueel e
le sue dipendenze, mentre ispeziona GenroPy staticamente senza importarlo.
Non modifica gli oracoli. La riproduzione controlla membership e hash prima
di usare la cattura; una variazione fa fallire la verifica.

Verifica mirata: **103 test superati** (oracolo fisico di tutti i package,
options, virtualRelation, subQueryColumn e validation). Suite completa di
chiusura: **1067 superati, 1 saltato**, incluso il gate PostgreSQL del bridge
esistente su database temporaneo. Ruff e mypy nell'ambiente di audit superati.
Nessuna operazione sul DB applicativo test_invoice_pg. Il gate PostgreSQL del
percorso nativo rimane in fase 6: questi test non lo certificano. Nessuna
modifica a `src/`, alle firme o ai resolver.

**Verifiche dell'incremento successivo syscode:** aggiunte firma booleana ed
espansione circoscritta della colonna, con 11 casi in `tests/test_syscode.py`:
default/disattivazione, source invariata, render ripetibile, UNIQUE nel JSON,
assenza di comportamenti system_records, PK esplicita, conflitti e tipi del
flag. Suite completa: **1078 superati, 1 saltato**; Ruff e mypy nell'ambiente
di audit superati. Grammatica generata e hash dell'audit aggiornati; nessun
oracolo legacy modificato.

## Registro dei 75 modelli

Nella tabella seguente C/V indica colonne fisiche/elementi virtuali legacy,
incluse le composite. Tutte le righe hanno sorgenti e aspettative verificati
nell'audit JSON; le 74 incluse restano **da certificare sul percorso nativo**.
sys.locked_record resta soltanto come riferimento escluso.
Le famiglie elencate evidenziano dichiarazioni particolari, non sostituiscono
l'elenco completo di colonne, virtuali e riferimenti conservato nell'evidenza.

| Modello | C/V | Famiglie particolari |
| --- | ---: | --- |
| adm.access_group | 7/5 | base / metadati |
| adm.api_token | 15/7 | formula |
| adm.api_token_tag | 7/7 | alias |
| adm.audit | 12/5 | base / metadati |
| adm.authorization | 12/5 | base / metadati |
| adm.backup | 9/6 | formula |
| adm.ckstyle | 10/6 | formula |
| adm.connection | 8/1 | alias, enabled_when |
| adm.counter | 14/5 | pkey_columns, tenant |
| adm.day | 3/0 | base / metadati |
| adm.group | 11/6 | auto_counter, formula |
| adm.group_helpdoc | 8/6 | alias, auto_counter |
| adm.helpdoc | 8/5 | base / metadati |
| adm.htag | 22/11 | auto_counter, formula, hierarchical, system_records; D-01 |
| adm.htmltemplate | 14/5 | base / metadati |
| adm.htmltemplate_atc | 16/9 | attachments, auto_counter, python_column |
| adm.install_checklist | 11/5 | base / metadati; __syscode esplicita, PK |
| adm.language | 8/7 | auto_counter, system_records; D-01 |
| adm.letterhead_type | 6/5 | base / metadati |
| adm.menu | 18/12 | alias, auto_counter, hierarchical |
| adm.menu_page | 10/5 | base / metadati |
| adm.notification | 16/8 | formula |
| adm.pkginfo | 6/5 | base / metadati |
| adm.preference | 6/5 | base / metadati |
| adm.record_tag | 8/5 | base / metadati |
| adm.sent_email | 10/5 | base / metadati |
| adm.served_page | 6/0 | enabled_when |
| adm.shortcut | 8/5 | auto_counter |
| adm.tblinfo | 7/5 | base / metadati |
| adm.tblinfo_item | 10/5 | pkey_columns |
| adm.user | 29/14 | formula, python_column, record_hash |
| adm.user_access_group | 7/5 | base / metadati |
| adm.user_config | 10/7 | formula |
| adm.user_group | 7/5 | base / metadati |
| adm.user_notification | 9/5 | base / metadati |
| adm.user_setting | 8/5 | pkey_columns |
| adm.user_tag | 8/14 | alias, formula |
| adm.userobject | 20/10 | archive, broadcast, formula, python_column |
| adm.week | 1/2 | formula |
| adm.xgroup | 7/7 | system_records; D-01 |
| invc.customer | 19/28 | alias, encryption, formula, groups, partition, python_column, subtable |
| invc.customer_type | 6/5 | base / metadati |
| invc.discount_tier | 10/5 | base / metadati |
| invc.invoice | 12/33 | alias, formula, numbering, partition, subquery, virtual_relation |
| invc.invoice_note | 9/9 | formula |
| invc.invoice_row | 13/28 | alias, auto_counter, formula, virtual_relation |
| invc.payment_type | 6/5 | base / metadati |
| invc.postcode | 10/5 | base / metadati |
| invc.price_year | 9/8 | alias, composite, formula |
| invc.price_year_note | 9/9 | alias, composite |
| invc.product | 13/23 | alias, bag_item, dynamic_fields_column, formula, python_column |
| invc.product_group | 17/8 | auto_counter, hierarchical |
| invc.product_type | 18/8 | auto_counter, dynamic_fields, hierarchical |
| invc.region | 6/5 | base / metadati |
| invc.staff | 12/10 | alias, formula |
| invc.staff_role | 6/5 | base / metadati |
| invc.state | 7/5 | base / metadati |
| invc.vat_type | 7/5 | base / metadati |
| sys.batch_log | 12/7 | formula |
| sys.calendar | 1/5 | formula, python_column |
| sys.dataretention | 8/5 | base / metadati |
| sys.dbchange | 8/5 | base / metadati |
| sys.error | 20/6 | formula, retention |
| sys.external_token | 13/1 | python_column |
| sys.external_token_use | 4/0 | base / metadati |
| sys.externalcall_log | 10/5 | base / metadati |
| sys.locked_record | 7/0 | Esclusa dal corpus nativo; riferimento legacy, D-02 |
| sys.service | 11/5 | pkey_columns |
| sys.shared_object | 9/5 | base / metadati |
| sys.shorturl | 12/5 | pkey_columns |
| sys.task | 28/9 | formula; contributo adm → sys.task |
| sys.task_execution | 15/15 | alias, formula, retention |
| sys.task_result | 11/5 | base / metadati |
| sys.upgrade | 8/5 | pkey_columns |
| sys.widget | 18/7 | audit, dynamic_fields, hierarchical |
