# 49 — Correzioni e verifica delle aggiunte alla grammatica

**Stato corrente delle virtual relations:** `limit`, `order_by` e `one_one`
sono rinviati ed esclusi dalla firma (41, R-06), come `inverse` (R-05).
I riferimenti precedenti alla loro conservazione e alla regola limit/order_by
registrano revisioni superate, non il contratto corrente.


**Decisione successiva sui timestamp:** i timestamp di sistema sono DHZ;
la convenzione di scrittura nel DB è UTC. Per ora nessuna opzione
`timestamp_type` o `use_timezone`. Prevale sui punti ancora aperti citati sotto.
La baseline salvata del corpus usa già use_timezone=True (report 45).

**Decisione successiva:** [schemi dedotti dai package](50-schemas-from-packages.md);
nessuna dichiarazione schemas nella nuova configurazione.

12 ottobre 2026. Richiesta dell'utente: togliere la dichiarazione di variabili
DB introdotta dall'assistente, usare EnvResolver e resolver esistenti, incluso
BagCbResolver per valori calcolati; controllare le altre aggiunte non concordate.
**Perimetro: source e grammatica. Nessun nuovo rendering a oggetti vivi.**

**Aggiornamento successivo vincolante:** lo scopo attuale è grammatica e
traduzione, senza anticipare contratti esecutivi. `provider` è ora rimosso da
tutte le firme, inclusa encryption; `behavior(...)` è rimosso. I riferimenti
qui sotto a provider facoltativi descrivono la revisione precedente, superata.

## Correzioni effettuate

| Aggiunta dell'assistente | Riscontro e correzione |
| --- | --- |
| `db.options().context(...)` | Mai concordata, nessun equivalente dichiarativo necessario nel legacy. Rimossa da elementi, dispatch, grammatica generata ed esempi. Le vecchie source con questo nodo sono rifiutate. |
| `partition(..., context='...')`, `tenant(context='...')` | Introducevano un contratto aggiuntivo di nomi ambiente. Rimossi i parametri; partition conserva il campo e riceve `value`, anche EnvResolver/BagCbResolver. Tenant può dichiarare il solo flag presente nel legacy. |
| Provider obbligatori per audit, tenant, retention, broadcast, archive, enabled_when, attachments, numbering e cifratura | Il legacy non richiede questi nomi. Tolto l'obbligo; nessun nome fittizio nell'esempio. Il parametro facoltativo già esposto resta una proposta di binding, non un registro implementato o deciso. |
| Sintassi di versione dei provider, per esempio `@1` | Nessuna decisione né necessità verificata. Rimossi contratto, validatore specifico ed esempi; le stringhe eventualmente fornite restano opache. |
| `column.generation(type='uuid'/'manual'/'sequence')` | Il documento 40 lasciava aperti i casi ulteriori e confermava UUID in sys_fields. Rimossa l'API separata e il suo contratto proposto. Rimane sys_fields(id={'type': 'uuid'}). |
| Rifiuto dei resolver come oggetti non JSON | Incompatibile con l'indicazione dell'utente. I payload dati ammettono BagResolver senza chiamarlo; un callback viene racchiuso in BagCbResolver. Non aggiunti nuovi resolver Asqueel. |
| `invc.invoice_atc`, `invc.settings`, schema `business`, assenza di adm, requires sys su invc | Esempi inventati, non test_invoice_pg. Sostituiti con selezione di tabelle dei tre package reali e mapping sys/adm/invc. L'allegato reale è adm.htmltemplate_atc; la dipendenza verificata è adm → sys. |
| Gerarchia product_type su code; audit/retention/archive sull'invoice | Attribuzioni dell'esempio non verificate. Ripristinata la gerarchia legacy su description e tolte le options aggiunte per mostrare il catalogo. |

`value` è il parametro minimo per fornire direttamente il valore/resolver della
partition secondo l'ultima indicazione; non è un nuovo registro. Il suo uso
applicativo e la risoluzione sono della prossima fase.

## Provenienza delle famiglie rimaste

Fonti: [decisioni 40](40-model-and-operation-recipes.md),
[censimento 43](43-test-invoice-model-coverage.md),
[inventario AST](evidence/test-invoice-model-inventory.json) e sorgenti GenroPy.
Il checkout legacy è `/Users/gporcari/Sviluppo/Genropy/genropy`.

| Famiglia | Evidenza |
| --- | --- |
| db, connection, schemas, packages, options; quattro attributi table | Decisioni esplicite del documento 40 e della conversazione. Options ammesse ai vari livelli non implica funzioni nuove approvate per ciascun livello. |
| sys_fields, UUID 22 e campi standard | Decisioni 40; gnrpy/gnr/app/gnrdbo.py sysFields; algoritmo gnrpy/gnr/core/gnrlang.py getUuid. |
| validation e validate_* | Decisione esplicita sull'embedding locale; invc/customer.py. |
| hierarchical, auto_counter, dynamic_fields, relative_index | gnrdbo.py sysFields, sysFields_counter, sysFields_df, sysFields_relidx; invc/product_type.py e invoice_row.py. hdepth, root_id e linked_to esistono nel legacy. |
| record_hash, full_update, protection, diagnostics, system_records, release | gnrdbo.py sysFields e helper, documentati nell'analisi 34. md5 su adm/user.py; metodi sysRecord_* e _release_* nel legacy. |
| pkey_from | pkey_columns: sys/service.py, adm/counter.py e altri. È una chiave testuale derivata, distinta dalle chiavi composite SQL. |
| audit | sys/widget.py, audit lazy; non l'invoice del precedente esempio. |
| partition | invc/customer.py partition_state e invc/invoice.py partition_customer_state. |
| tenant | adm/counter.py multi_tenant=True. Nessuna variabile tenant_id necessaria da dichiarare sul DB. |
| retention | sys/error.py (__ins_ts, 60), sys/task_execution.py (__ins_ts, 180). |
| broadcast, archive, enabled_when | adm/userobject.py broadcast/archivable; adm/connection.py e served_page.py checkpref. |
| attachments | adm/htmltemplate_atc.py eredita AttachmentTable; gnrdbo.py contiene l'espansione legacy. |
| numbering | invc/invoice.py counter_inv_number; l'esempio conserva il relativo dizionario. |
| type, requires, macro | invc/main.py custom_type_money/perc e registerMacros/addMacro; adm/main.py required_packages. Il bisogno legacy è verificato, la nuova firma macro e il suo binding restano proposte. |
| relation, weak_relation, virtualRelation, alias/formule/sottoquery, composite, indici | Costruzioni presenti nell'inventario 43; relations e virtual relations richieste esplicitamente. Le forme nuove sono adattamenti di sintassi, non comportamenti già verificati. |
| behavior | Il bisogno di collegare i metodi della Table esiste nel legacy; la firma dichiarativa è una proposta. Registro, import, versione e precedenza degli hook non sono decisioni acquisite. |
| metadata/x_ui, normalize, encryption, colgroup | Il legacy ha metadati UI, validate_case, encrypted e group_*; la loro collocazione nelle nuove sezioni è proposta nel 42, non una decisione nominativa dell'utente. |

## Proposte da non presentare come decisioni

La richiesta di formulare una grammatica finale da rivedere autorizzava una
proposta concreta, non a etichettarne ogni dettaglio come già concordato.
Restano da rivedere: nomi delle sezioni adattate dal legacy, parametri dei
provider facoltativi, firme macro/behavior, precedenza dei default e hook,
normalizzazione distinta da validation, policy di errore pkey_from e dettagli
delle virtual relations. Non è stato introdotto codice che ne esegua gli effetti.

Anche il default DHZ proposto in sys_fields non era una decisione sulla timezone:
la scelta resta aperta nel documento 40. L'esempio specifica DH e user_upd=False
per mostrare il profilo legacy, senza attribuire quel profilo a tutti i modelli.
Il default user_upd=True di Asqueel è invece una decisione esplicita e resta.

## Resolver e limiti della verifica

EnvResolver legge l'ambiente del processo, non automaticamente currentEnv.
Per currentEnv/workdate applicativi l'host passa un callback a BagCbResolver.
La source conserva entrambi senza leggere credenziali o chiamare il callback.
Non si serializza automaticamente codice Python: il round-trip JSON dei dati
puri non dimostra la trasferibilità dei callback. La fase delle ricette remote
dovrà stabilire il binding usando le capacità già disponibili.

L'[esempio corretto](../../examples/model_grammar/configure.py) usa solo nomi di
tabelle dell'inventario, ma seleziona dichiarazioni per la revisione: non è il
porting integrale delle 75 tabelle. Riferimenti a tabelle non mostrate sono
intenzionali e non vengono risolti in questa fase. Etichette italiane e nomi
delle variabili di processo sono scelte illustrative, non estratti di credenziali.

Le prove impediscono l'esecuzione di resolver durante build, clone e composizione,
verificano rifiuto delle API ritirate anche in source importate, dichiarazioni
senza provider fittizi e appartenenza delle tabelle all'inventario. Restano i
controlli di firme chiuse, payload, composizione e grammar export.

Esito: **1000 test superati, 1 saltato**, inclusi i test PostgreSQL locali;
Ruff superato e mypy senza errori nei 50 file sorgente nell’ambiente di verifica.

## Ricontrollo successivo: residui effettivamente trovati

La precedente revisione non aveva eliminato tutti i residui. Verifica mirata
di codice, test, esempio e documenti 40–51 contro le decisioni e i sorgenti
legacy locali; non è una certificazione dell'intero repository.

| Residuo | Evidenza e stato |
| --- | --- |
| Registro obbligatorio dei provider | Il piano 44 lo richiedeva ancora nel perimetro e nel titolo P2, contraddicendo la correzione della sezione P2. Rimossi entrambi i requisiti; nessun registro aggiuntivo deciso. |
| Resolver differiti negli oggetti | Il piano 51 aveva introdotto questa regola senza decisione. Rimossa; corretto anche il divieto implicito di valutazione di tenant/partition. Valgono i resolver di Builders: source → valutazione nel render → valore nell'oggetto. |
| DHZ come default definitivo | model_elements.sys_fields lo espone, model_expansion lo usa per le colonne e test_release_composition lo verifica. Non è soltanto testo: ha un effetto fisico. Il legacy sceglie DH/DHZ tramite use_timezone (gnrdbo.py:359); il contratto 40 lascia la scelta aperta. Corretta la pretesa documentale nel 42; il default nel codice resta da chiudere esplicitamente, senza sostituirlo con un'altra scelta arbitraria. |
| Ordine di hook e regole RAW/bulk | Il 42 presentava una sequenza e regole di esecuzione non chiuse nel 40. Ritirate come requisito; appartengono alla fase lettura/scrittura. Non è stata modificata l'esecuzione esistente. |
| Provider opzionali e macro/behavior | Le firme sono ancora nel codice, anche se il 49 le qualifica come proposte. model_elements.macro parla persino di handler registrato. Non è stato trovato un registro implementato in questi elementi, ma la presenza grammaticale non approva il binding. |
| Policy aggiuntive nelle firme | pkey_from impone missing='error'; option_validation richiede records per system_records e handlers per release. Il legacy rileva anche metodi sysRecord_* e _release_* (gnrdbo.py:509–513). Sono adattamenti proposti già vincolanti nella validazione source; non basta citare la famiglia legacy per dichiararne concordati tutti i parametri. |
| Esempio gerarchico non equivalente | configure.py usa hierarchical + auto_counter('parent_id'); product_type legacy usa counter=True e gnrdbo.py:448 vieta un contatore relativo nel ramo gerarchico. Il piano 51 lo segnalava già: l'esempio non è ancora una prova di parità. |
| workdate come default di configurazione | configure.py e il documento 48 usano column(default=BagCbResolver(...)); il legacy invoice.defaultValues legge workdate durante l'operazione. La valutazione nel render non è equivalente. L'esempio dimostra la sintassi dei resolver, non la riproduzione di quel comportamento legacy; il binding operativo resta aperto. |

Non si eliminano le famiglie richieste né si cambiano default pubblici durante
questo controllo: il risultato identifica cosa richiede ancora correzione o
decisione. La richiesta di proporre una grammatica autorizzava adattamenti di
sintassi; non autorizzava a presentarli come semantica concordata.

Verifica mirata eseguita: **93 test superati** in test_behavior_option_grammar,
test_release_composition e test_release_model_source. Confermano tra l'altro
il rifiuto di context/generation, la costruzione senza chiamare resolver e lo
stato attuale delle firme. Non provano che quelle firme siano state approvate,
né la parità del render nativo completo, ancora da realizzare.

## Applicazione del perimetro grammatica e traduzione

- Rimossi provider e behavior da firme, dispatch e grammatica esportata.
  Le dichiarazioni importate che li contengono vengono rifiutate esplicitamente.
- Conservate le options che descrivono il modello: per dichiarare audit,
  allegati, cifratura o numerazione non serve identificare un futuro esecutore.
- Eliminati dal piano del render i collegamenti a generatori e altri esecutori;
  il render traduce dichiarazioni e risolve valori tramite Builders.
- Corretto l'esempio gerarchico in auto_counter() e rimosso il falso equivalente
  di defaultValues/workdate. I test dei callback riguardano valori della
  configurazione, senza attribuire loro una semantica di default per scrittura.

Restano aperti i dettagli grammaticali già elencati, inclusi DH/DHZ e le firme
macro/release/system_records: la rimozione dei provider non certifica
automaticamente come concordata ogni altra proposta. Non sono state introdotte
implementazioni di comportamenti di lettura o scrittura.

Verifica dopo la rimozione: **1003 test superati, 1 saltato** nella suite completa,
inclusi i test PostgreSQL locali; Ruff superato, mypy senza errori nei 50 file
sorgente e diff senza errori di whitespace. Grammatica pubblicata rigenerata.

## Precedenza del legacy e chiave testuale derivata

Decisione: il legacy prevale; scostamenti motivati richiedono approvazione
preventiva dell'utente. pkey_from e missing sono rimossi. La tabella dichiara
pkey_columns e pkey_columns_joiner, come sys.service e sys.upgrade.
I riferimenti a pkey_from nelle revisioni precedenti sono superati.
La traduzione conserva questi attributi senza costruire valori né trasformarli
in componenti della primary key SQL. Esempi e grammatica esportata aggiornati.

## Macro — confine confermato il 13 ottobre

La registrazione e l'espansione delle macro SQL appartengono alla compilazione
delle query, non alla struttura del modello. Nel legacy invc/main.py separa
registerMacros da config_db; addMacro in gnrsql/db.py configura le compilazioni.
Rimossa quindi options().macro dalla grammatica strutturale e dall'export.
Restano le espressioni del modello che contengono riferimenti a macro:
conservarle non richiede registrare o eseguire macro durante la traduzione
strutturale. Nessuna nuova API del compilatore è definita in questa revisione.

## Validation — dizionario della colonna, 13 ottobre

Decisione: validation e validate_* producono il medesimo column.validations,
un dict. Controlli e trasformazioni restano insieme; case conserva il valore
legacy, inclusi U e c. Rimossi normalize e il contenitore messages; i messaggi
restano nelle chiavi *_error. Source importate con queste forme ritirate sono
rifiutate. Il bridge legacy trasferisce ora anche validate_case.
La traduzione conserva le regole senza invocare validate_value, applicare case
o inferire NOT NULL. I dettagli delle altre regole restano da verificare.

Verifica della revisione: **1021 test superati, 1 saltato** nella suite completa,
inclusi PostgreSQL, bridge legacy e JSON migrations. Ruff superato; mypy senza
errori nei 50 file sorgente. Verificati anche il dizionario sulla colonna viva,
l'equivalenza delle due forme, la composizione e il round-trip del modello.

## exist e nodup — correzione grammaticale, 13 ottobre

Rinominati exists/exists_error in exist/exist_error; le vecchie chiavi sono
rifiutate anche nelle source importate. Entrambe le regole accettano bool e
str, senza cambiare il valore dichiarato. Le chiavi legacy exist_* e nodup_*
sono conservate, inclusi parametri, messaggi e condizioni. Il riferimento è
genro_frm.js: validate_exist/validate_nodup e callValidation; getRecordCount
non viene invocato dalla traduzione. Nessun nuovo esecutore implementato.

Prossimi punti grammaticali da esaminare singolarmente: collocazione di values
(attributo di colonna nel legacy), validate_empty, attributi comuni dei
validatori non ancora conservati, altre regole legacy del client, e firme delle
relazioni virtuali. Record di sistema e release restano rinviati (registro 41).

Verifica: **1042 test superati, 1 saltato** nella suite completa, inclusi
PostgreSQL e il confronto migrations. Ruff e mypy superati. Le prove mirate
coprono entrambe le forme, composizione, round-trip, parametri legacy, rifiuto
di exists e assenza di nuovi vincoli o risoluzione dei riferimenti.


## Validation — sola conservazione, 13 ottobre

La decisione successiva supera le restrizioni sui nomi e sui tipi descritte
nelle due revisioni precedenti. La firma è `validation(**rules)`: salva i
parametri senza validarli semanticamente. Gli attributi `validate_*` perdono
solo il prefisso; anche le source importate conservano i dati. Nessuna
correzione automatica dei nomi, nessun default di regola e nessuna esecuzione.
Non serve chiudere ora il vocabolario delle singole validazioni.

`values` nel legacy è un attributo di colonna usato per le scelte dei widget
(genro_wdg.js); non compare nei validationTags di genro_frm.js. La firma
`validation(values=...)` era un'aggiunta non concordata: eliminato il catalogo
esplicito dalla grammatica. Accettare dati arbitrari non introduce regole.
La decisione successiva riportata sotto approva espressamente `validate_values`.

Verifica: **1049 test superati, 1 saltato** nella suite completa, inclusi
PostgreSQL e confronto migrations. Ruff e mypy superati. Verificate entrambe
le forme dichiarative, source importate, composizione e round-trip senza
controlli sul vocabolario o sui tipi delle regole.

## validate_values — differenza dal legacy approvata, 13 ottobre

L'utente approva esplicitamente la differenza: al posto dell'attributo legacy
di colonna `values`, Asqueel dichiara `validate_values`, equivalente alla forma
`validation(values=...)`. La dichiarazione viene conservata sotto la chiave
`values` del dict `column.validations`, senza interpretazione, esecuzione o
deduzione di vincoli SQL. L'uso futuro da parte dei widget resta da definire.
La grammatica aperta già conserva questi dati; non occorre modificarla.


## aliasTable — rinvio e chiarimento, 13 ottobre

L'utente esclude per ora la firma `aliasTable` dalla grammatica (41, R-04),
ma conferma che `virtualRelation` resta. La precedente rimozione anche della
forma `virtualRelation(name, relation=...)` era un'interpretazione errata:
ripristinati parametro, esempio e traduzione dei `table_aliases` legacy.
Nessuna esclusione di `aliasColumn` o dei join condizionali.
La prossima firma da confrontare con il legacy riguarda `joinColumn(...).relation(...)`.


## Virtual relations — riallineamento alla GEP, 13 ottobre

Fonte riletta: GEP-0002-many-relations.md in genropy_meta e soprattutto la
[revisione della discussione](https://github.com/genropy/genropy_meta/issues/1#issuecomment-5803053743),
che passa da manyRelation a virtualRelation. L'utente conferma var_*, ask,
order_by e limit, rinviando inverse e chiedendo di rimuoverne la generazione.

La grammatica conserva var_* come espressioni della sorgente e condition come
predicato sulla destinazione; rimosse le mappe source_parameters e parameters.
Eliminato il rifiuto di condition insieme a relation: i filtri sono previsti
dalla GEP. Rimossi inverse e la generazione delle inverse virtuali, comprese
quelle prodotte dal ponte legacy. Le inverse ordinarie restano operative.
Nessun compilatore di binding, filtro, ordine o limite introdotto.

Restano aperti nella GEP i dettagli della derivazione da relazioni limitate e
il prefisso dei parametri ask; inverse è ora un rinvio esplicito (41, R-05).
La traduzione completa della cnd legacy nella sintassi GEP non viene anticipata:
il ponte offline la conserva come espressione legacy opaca, senza eseguirla.

Verifica: **1057 test superati, 1 saltato**, inclusi PostgreSQL e confronto
del JSON migrations su tutti i 75 modelli del corpus. Ruff e mypy superati.
Test mirati per binding, ask, ordine/limite, filtri su relation, composizione,
round-trip, rifiuto delle firme ritirate e assenza di inverse virtuali;
le inverse ordinarie e il JSON fisico restano invariati.


## Limit richiede order_by — decisione del 13 ottobre

L'utente stabilisce che limit ha senso soltanto con un ordinamento. La
validazione della source composta richiede order_by non vuoto quando limit
è dichiarato. Nessun ordinamento inserito automaticamente. I due attributi
possono essere forniti in contributi separati; order_by senza limit resta
ammesso. Il comportamento della derivazione da una virtualRelation già
limitata resta da decidere, senza adottare implicitamente il divieto proposto.


## VirtualRelation — rinvio di limit, order_by e one_one, 13 ottobre

Decisione esplicita dell'utente: rimuovere limit e order_by dalla grammatica,
rinviando anche one_one come dichiarazione di cardinalità. Differenza dalla
GEP registrata nel rinvio R-06. Rimossi firme e controlli dedicati ai limiti;
source dirette e importate rifiutano gli attributi ritirati. Aggiornati esempi
e piani. Il ponte legacy conserva one_one soltanto nei metadati originali.
Nessuna modifica a query, subQueryColumn o one_one delle relazioni ordinarie.
Resta da discutere il namespace ask; il problema delle derivazioni limitate
non appartiene più al perimetro grammaticale corrente.

Verifica: **89 test mirati superati**, incluso il confronto del JSON migrations
su tutti i 75 modelli; JSON fisico invariato. Ruff e mypy superati. Verificato
il rifiuto degli attributi rinviati anche nelle source importate e la loro
assenza dalle dichiarazioni virtuali tradotte dal corpus legacy.


## Ask — namespace provvisorio approvato, 13 ottobre

L'utente conferma per ora `:ask_<nome>` nella condition, mantenendo
`name='<nome>'` nei fields di ask. Ogni parametro appartiene alla dichiarazione
che lo contiene. Questo chiude provvisoriamente il punto lasciato aperto dalla
GEP: le decisioni potranno essere riviste durante il lavoro sul compilatore.

Aggiornati contratto grammaticale, esempio e verifica di composizione e
round-trip. Nessun parser, riscrittore di parametri SQL o raccolta di valori
aggiunto: condition e ask rimangono dati dichiarativi. La forma precedente
`:year` negli esempi ask è sostituita da `:ask_year`, senza introdurre ora una
conversione automatica o un controllo SQL sui testi importati.


## SubQueryColumn — firma legacy confermata, 13 ottobre

L'utente conferma query=None, mode=None, dtype e metadati della colonna.
Riferimento: genropy/gnrpy/gnr/sql/gnrsqlmodel/model.py, subQueryColumn;
esempio max_row_price in projects/test_invoice/packages/invc/model/invoice.py.
Corretta la firma Asqueel che richiedeva query e ometteva dtype; corretto il
documento che proponeva mode='scalar'. Nessun enum chiuso sui mode e nessuna
espansione SQL aggiunta. La struttura interna di query resta da esaminare.


## Checkpoint prima del render degli oggetti, 13 ottobre

Verifica pre-commit della revisione grammaticale: **1067 test superati,
1 saltato** nella suite completa, inclusi PostgreSQL e confronto del JSON
migrations di tutti i package. Ruff e mypy superati; diff senza errori
di whitespace. Il percorso nativo completo resta il lavoro successivo (51).
