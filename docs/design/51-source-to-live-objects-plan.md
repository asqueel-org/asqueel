# 51 — Piano del render: source → oggetti vivi → JSON migrations

**Decisione successiva sui timestamp:** i timestamp di sistema sono DHZ;
la convenzione di scrittura nel DB è UTC. Per ora nessuna opzione
`timestamp_type` o `use_timezone`. Prevale sui punti ancora aperti citati sotto.
La baseline salvata del corpus usa già use_timezone=True (report 45).

Aggiornato il **13 ottobre 2026**, dopo il checkpoint grammaticale
`61bbbb5` e la fase 1 `43663f8`. **Fasi 0–3 completate; prossima verifica: relazioni e finalizzazione (4).**
La richiesta corrente è organizzare la costruzione degli oggetti e il JSON
migrations. Questo documento sostituisce la precedente sequenza A–E con fasi
verificabili, senza aprire il lavoro sul compilatore o introdurre nuove firme.
Prevalgono le decisioni 40, i rinvii 41, la grammatica 42 e le correzioni 49–50.

## Stato verificato e risultato da raggiungere

- La suite dopo le fasi 2–3 conta **1124 test superati e 1 saltato**. Ruff e mypy
  passano nell'ambiente di verifica. Il mypy dell'hook locale usa un ambiente
  diverso e segnala dipendenze/firme non allineate: verificare con l'ambiente
  riproducibile dei test, senza considerare ignorabili futuri errori di tipo.
- `SqlObjectRenderer` già compone la configurazione, prepara un modello e crea
  `SqlDatabase`: si completa questo percorso, non un secondo sistema di oggetti.
- `expand_options` espande le options strutturali concordate, incluse quelle
  con contributi fra tabelle, e conserva le altre nel modello. System_records
  e release attive restano rifiutate perché rinviate; diagnostics è rimossa.
- Il JSON di sys/adm/invc è verificato attraverso il ponte dalla source legacy
  espansa. L'esempio nativo corrente contiene soltanto una selezione di tabelle.
- Il traguardo aggiornato è una source nativa di **74 modelli** (sys 16, adm 40,
  invc 18; sys.locked_record esclusa), senza usare come ingresso
  XML espanso o snapshot JSON, da cui costruire oggetti completi e proiettare il
  JSON per migrations. La baseline rimane un oracolo indipendente per i test.

**Perimetro confermato dopo la fase 0:** system_records e sys.locked_record
esclusi; D-01/D-02 sono divergenze concordate nel rapporto 52. Non si richiede
un rimpiazzo integrale di GenroPy né identità del JSON oltre questo perimetro.
sys_fields(syscode=True) è successivamente approvata e implementata per la sola
colonna __syscode A :20, indicizzata e UNIQUE, disattivata per default.
Non riattiva system_records o i relativi virtuali.

### Regole che non vanno riaperte implicitamente

Schemi dedotti dai package; timestamp di sistema DHZ e convenzione UTC;
UUID legacy a 22 caratteri dichiarato senza generare valori; pkey_columns
come dati della tabella; validations come dict opaco, incluso validate_values.
VirtualRelation mantiene relation/table, condition, var_* e ask; :ask_<nome>
resta provvisorio fino al compilatore. Non reintrodurre inverse virtuali,
limit, order_by o one_one virtuali. SubQueryColumn conserva query=None,
mode=None e dtype; la sua query rimane dichiarativa.

ToolColumn, firma aliasTable, system_records, release e funzioni virtuali
rinviate seguono il registro 41. Nessun provider, behavior, nuovo resolver,
registro di hook o grammatica SQL aggiuntiva. I resolver di configurazione
restano quelli esistenti, inclusi EnvResolver e BagCbResolver.

## Confine e risultato

```text
source composta di tutti i package
    → render: espansioni, completamenti, collegamenti, verifiche
    → grafo completo degli oggetti vivi
    → proiezione fisica degli oggetti
    → JSON per asqueel-migration
```

Gli oggetti sono l'unica fonte del modello dopo il render. Il proiettore JSON
non rilegge la source, non riesegue options e non risolve callback applicativi.
Connessioni/configurazione amministrativa restano separate dal modello fisico.
Un eventuale buffer interno di costruzione non diventa una seconda source
pubblica da conservare, esportare o alimentare al migratore.

Schemi dedotti da package.sqlschema; default e sqlprefix come concordati nel
legacy. Niente schema dichiarativo separato, variabili DB dichiarate, nuovi
resolver Asqueel, registro/versionamento di provider o import dinamici inventati.
Provider e behavior sono rimossi dalla grammatica. Questo piano riguarda
la traduzione del modello, senza predisporre binding per esecuzioni successive.

## Evidenza legacy e differenza deliberata di collocazione

Riferimenti nel checkout `/Users/gporcari/Sviluppo/Genropy/genropy`:

- `gnrpy/gnr/sql/gnrsqlmodel/model.py`, DbModel.build (107–179): configura tutti
  i mixin di tabella e package; esegue onBuildingDbobj e runOnBuildingCb; costruisce
  DbModelObj; infine aggiunge le relazioni accumulate in _columnsWithRelations.
- Stesso file, deferOnBuilding/runOnBuildingCb (90–105): i completamenti che
  dipendono da altre tabelle sono rinviati finché le dichiarazioni sono presenti.
  Non occorre copiare il dettaglio accidentale dello stack LIFO come nuova API.
- `gnrpy/gnr/app/gnrdbo.py`, sysFields (323–525): campi standard, gerarchia,
  contatori, audit, diagnostica, dynamic fields, protezioni, release, sysrecords.
- Stesso file, sysFields_df/counter/relidx e linkHierarchicalToMaster (546 ss.);
  AttachmentTable.config_db: allegati con campi di sistema, contatore,
  FK al master, virtuali e contributo agli attributi del master.
- `gnrpy/gnr/sql/gnrsqlmodel/columns.py`, DbColumnObj.doInit: raccoglie le relazioni
  durante la costruzione; non richiede che il target sia già costruito.
- `gnrpy/gnr/sql/gnrsqlmodel/model.py`, addRelation/checkRelationIndex (182 ss.,
  357 ss.): relazioni dirette/inverse e indici con modello già disponibile.

Nel legacy buona parte delle espansioni avveniva in config_db/sysFields prima
che build costruisse gli oggetti. Per Asqueel la decisione è diversa e precisa:
la source conserva le options e la loro espansione appartiene al render.
Si riproducono dipendenze ed effetti verificati, non l'esecuzione anticipata dei
metodi di configurazione dentro la costruzione della source.

## Ordine interno del render

### 1. Acquisire e validare la source composta

Ricevere tutti i contributi già ordinati, compreso adm → sys.task. Lavorare su
uno stato privato senza modificare la source del chiamante. Applicare i default
soltanto dopo la composizione; rispettare False, None, reset e personalizzazioni.
Controllare firme, livelli e identità, senza ancora pretendere l'esistenza di
colonne promesse dalle options. Gli errori conservano percorso e contributo.

### 2. Preparare tutti i package e tutte le tabelle

Indicizzare le identità logiche prima di collegare qualsiasi relazione. Dedurre
gli schemi e determinare i nomi fisici da package, sqlprefix e override ammessi.
Conservare package vuoti. Rendere disponibili alias di tipo locali (money, perc)
e dipendenze di package. Preparare le colonne esplicite e le dichiarazioni di
virtuali, composite e relazioni, mantenendo ancora non collegati i riferimenti.
Il grafo in costruzione è privato: non viene pubblicato come DB utilizzabile.

### 3. Espandere le options locali secondo le dipendenze

L'ordine segue i dati necessari, non l'ordine delle chiamate nella configurazione.
Non serve introdurre una grammatica pubblica di priorità o dipendenze.

| Passaggio | Espansioni | Dipendenze e limiti |
| --- | --- | --- |
| Preparazione dei casi composti | attachments | Raccogliere gli effetti verificati di AttachmentTable e predisporre i campi richiesti; riusare le stesse routine interne di sys_fields e contatore. Registrare il collegamento al master per il completamento successivo. |
| Identità e campi di base | sys_fields; dichiarazione pkey_columns | Stabilire PK, id, timestamp, campi utente, cancellazione logica e bozza. Registrare la modalità UUID concordata senza collegare o invocare un generatore. pkey_columns conserva componenti e regola senza calcolare chiavi. |
| Campi locali aggiuntivi | full_update, record_hash, audit, dynamic_fields, parti locali di protection | Generare campi e descrizioni verificate senza interrogare l'audit. Record di sistema e release rinviati esplicitamente (41, R-02 e R-03). Gli altri effetti impliciti di sysFields nel legacy, come i virtuali di protezione/invalidità e record_pointer, non vanno persi. |
| Strutture gerarchiche | hierarchical | PK e colonne base devono esistere. Creare parent_id, percorsi gerarchici, campi parent e varianti effettivamente richieste; registrare relazioni da collegare dopo. |
| Ordinamento e contatori di riga | auto_counter, relative_index | Con hierarchical attiva usare il ramo gerarchico legacy, con _h_count, _parent_h_count e _h_sortcol. Senza gerarchia, gestire lo scope relativo. Rinviare i completamenti su altre tabelle. |
| Comportamenti senza allocazione di valori | numbering, partition, tenant, retention, broadcast, archive, enabled_when; cifratura e metodi applicativi | Trasferire i valori di configurazione risolti sugli oggetti, senza collegare esecutori. Le espansioni non assegnano numeri, cancellano dati, emettono eventi o accedono allo storage. I resolver dichiarati seguono comunque la semantica di Builders descritta sotto; nessuna eccezione implicita per tenant o partition. |

Non è un ordine totale artificiale: le espansioni indipendenti possono essere
eseguite nello stesso passaggio. Ciascuna espansione si applica una volta; i
completamenti rinviati hanno prerequisiti identificabili. Nessun ciclo di
riesecuzione indiscriminata di tutte le options fino a un risultato casuale.

Le colonne generate possono ricevere personalizzazioni compatibili già composte.
Due produttori non devono creare due copie della stessa colonna; tipo/identità
incompatibili devono produrre un errore. Un'opzione disabilitata non cancella
una colonna esplicitamente dichiarata dall'applicazione.

### 4. Completare le dipendenze fra tabelle

Con tutte le strutture locali presenti, completare gli effetti equivalenti ai
callback legacy deferOnBuilding: gerarchie collegate a un master, relative_index
sulla tabella riferita, contributi dell'allegato al master, dipendenze analoghe
riscontrate nel corpus. Individuare i target usando l'indice globale delle tabelle.

Un riferimento necessario per completare struttura o tipo può essere individuato
ora, senza pubblicare la relazione definitiva. Se un completamento dipende dal
risultato di un altro, eseguirlo dopo il suo prerequisito. Riferimento mancante o
ciclo che impedisce di determinare un valore strutturale: errore nominativo,
mai omissione silenziosa. I cicli fra FK, invece, non sono di per sé errori.

### 5. Risolvere tipi, chiavi e relazioni dirette

Dopo che le options hanno prodotto tutti i possibili target:

1. completare i tipi locali e qualificare i riferimenti relativi al package;
2. identificare PK e componenti delle composite nell'ordine dichiarato;
3. collegare relazioni fisiche e weak relations alle colonne/tabelle reali;
4. inferire dtype/size omessi dai target, anche lungo catene di riferimenti;
5. verificare compatibilità dei tipi, cardinalità delle chiavi e requisiti SQL
   delle FK. Una weak relation non diventa una FK per inferenza;
6. conservare separatamente azioni applicative e azioni SQL.

Nessun requisito di ordine topologico dei package: sys e adm possono riferirsi
reciprocamente. Le relazioni circolari sono ammesse quando le strutture sono
determinabili. Una catena di tipi omessi senza un tipo determinabile non viene
riempita arbitrariamente per far passare il render.

### 6. Inverse, virtual relations e dipendenze virtuali

Creare le inverse delle relazioni dirette, con nomi e collisioni verificati.
Poi collegare virtual relations su percorsi esistenti e relazioni condizionali;
conservare var_* e ask, con riferimento provvisorio `:ask_<nome>` ai campi
ask denominati `<nome>`; la scelta sarà rivedibile al compilatore.
limit, order_by e one_one sono esclusi dalla firma
per rinvio esplicito (41, R-06). Non generare inverse
delle virtual relations: funzione rinviata (41, R-05).

Risolvere aliasColumn e percorsi esplicitamente dichiarati verso colonne
fisiche/generate/virtuali. Collegare i riferimenti strutturali già espressi
dalla grammatica; conservare formule, sottoquery, pyColumn e bagItemColumn
con attributi e descrittori, senza analizzare o compilare le loro espressioni
per inventare ulteriori dipendenze. Un alias può richiedere il completamento
di una virtualRelation: seguire questa dipendenza strutturale. Segnalare cicli
di alias o percorsi non risolvibili, distinti dalle normali FK circolari.

Le funzioni Python dichiarate non vengono invocate sui record. Non occorre
implementare aggregati, macro, query o validazioni per conservare il modello.
Una relazione ordinaria one_one non crea automaticamente UNIQUE.
Il caso invoice → discount_tier e invoice_row → customer è obbligatorio.

### 7. Finalizzare vincoli, indici e grafo

Completare indici e vincoli implicati dalle dichiarazioni e dalle relazioni, con
nomi fisici definitivi. Applicare le regole di deduplicazione già previste senza
considerare equivalenti indici diversi per ordine, predicato o metodo. Conservare
metadati, gruppi, validation, virtuali e comportamenti anche se non producono DDL.

Verificare globalmente conflitti fisici, target mancanti e dichiarazioni rimaste
senza effetto o senza rappresentazione. Solo dopo il successo pubblicare il grafo
DB/package/table/column/relation attraverso gli oggetti esistenti, completandoli
ove necessario. Nessun DB parzialmente pronto in caso di errore. Eliminare la
dipendenza degli oggetti dalla source del modello: modificarla dopo il render
non deve cambiare gli oggetti già restituiti.

## Resolver: comportamento esistente di Builders

Si usano BagResolver, EnvResolver e BagCbResolver di genro-bag, rispettandone
cache e semantica. Non si introducono nuove classi o un linguaggio di resolver.

Il percorso di riferimento è quello di Builders: resolver nella source,
valutazione durante il render tramite runtime_values, valore risultante
nell'oggetto. Anche un BagCbResolver viene valutato secondo questa semantica.
La costruzione e composizione della source restano distinte dal render.

Non è concordata una conservazione dei resolver negli oggetti vivi né una
politica diversa per attributi specifici. La lettura di un resolver in
_effective_model_builder non costituisce di per sé un errore: il percorso va
verificato rispetto alla semantica esistente, senza introdurre eccezioni.

Il calcolo dei valori durante letture e scritture sarà affrontato nella relativa
fase. Questo piano non decide il comportamento futuro di default dei record,
workdate o partition. Il JSON migrations deriva dalla struttura fisica degli
oggetti completati; nessun nuovo codec remoto in questa fase.

## Piano di implementazione per fasi

La sequenza segue le dipendenze. Ogni fase termina con un risultato verificabile,
un aggiornamento di questo piano e un commit dedicato. Il completamento di una
fase non autorizza a dichiarare completata la successiva o l'intera release.

| Fase | Risultato | Dipende da |
| --- | --- | --- |
| 0 — Mappa di copertura e confronto | Effetti legacy e differenze attese espliciti per ogni option e modello | Checkpoint 61bbbb5 |
| 1 — Percorso di render e oggetti | Render minimo coerente, resolver corretti, source invariata | 0 |
| 2 — Espansioni locali | Campi standard e options locali complete, con prove per famiglia | 1 |
| 3 — Espansioni fra tabelle | Gerarchie collegate, contatori relativi, allegati e contributi al master | 2 |
| 4 — Relazioni e modello completo | Tipi, chiavi, percorsi, inverse ordinarie, indici e oggetti pubblicabili | 3 |
| 5 — Source nativa del corpus | I 74 modelli inclusi, confrontati con il legacy e le divergenze concordate | 4 |
| 6 — JSON dagli oggetti | Proiezione indipendente dalla source e migrations verificate su PostgreSQL | 5 |

### Fase 0 — Mappa di copertura e differenze

**Lavoro:** riesaminare il censimento 43, gli effetti di gnrdbo.sysFields e
AttachmentTable, le estensioni dei package e gli oracoli del report 47. Creare
una matrice tracciabile con: dichiarazione nativa, sorgente legacy, colonne/
relazioni/indici/virtuali prodotti, dati soltanto conservati, dipendenze,
rinvio applicabile, fixture di verifica e stato. Usare il corpus per trovare
casi concreti, non solo per contare tabelle.

**Confronto indipendente:** aspettative ricavate da sorgenti/catture legacy,
non dalla stessa funzione Asqueel da verificare. Distinguere dichiarazioni
originali da effetti generati. Annotare in anticipo gli impatti fisici dei
rinvii e l'indice di sys.locked_record omesso dall'estrattore storico.

**Criterio di completamento:** ogni famiglia di options e ogni costrutto usato
nei 75 modelli ha un effetto atteso o un rinvio documentato. Una differenza
non concordata viene presentata all'utente prima di adattare il contratto o
l'oracolo. Si può continuare sui casi indipendenti mentre quel punto resta aperto.

**Consegna:** matrice di copertura del render e registro delle differenze,
collegati da questo documento; nessun nuovo costrutto di grammatica.

**Esito del 13 ottobre:** [rapporto 52](52-invoice-render-coverage.md) e
[evidenza per tutti i modelli](evidence/invoice-render-coverage.json).
Verificati 75 modelli, 79 sorgenti del manifest, 227 import legacy e integrità
degli oracoli. D-01 (system_records) e D-02 (sys.locked_record) sono state
risolte dall'utente escludendole dal perimetro; scarti registrati nel rapporto.
La sola colonna syscode è stata successivamente approvata e implementata,
distinta dal concetto di system_records.
Le carenze native C-01–C-05 sono classificate separatamente.
Nessuna modifica al render. Il rinvio di release non produce scarti nel corpus.

### Fase 1 — Percorso di render e oggetti esistenti

**Lavoro:** seguire SqlObjectRenderer → configurazione effettiva → resolve_model
→ SqlDatabase. Definire nel percorso esistente quando si applicano default,
si leggono i resolver e si finalizzano gli oggetti. Indicizzare tutti i package
e le tabelle prima dei collegamenti. Separare i dati strutturali risolti dalla
configurazione amministrativa delle connessioni.

**File principali:** object_renderer.py, configuration.py, model_source.py,
application.py, application_table.py, contracts.py e model_sections.py.

**Prove:** modello piccolo con più package e schema condiviso, override fisici,
package vuoti, contributi, EnvResolver e BagCbResolver. Build/clone/composizione
non eseguono i resolver; il render segue la semantica Builders esistente e
porta negli oggetti i valori risultanti. Non imporre un nuovo conteggio globale
di chiamate: verificare caching e invalidazione secondo i resolver già usati.
Nessuna connessione SQL o operazione applicativa durante il render.

**Criterio di completamento:** modello minimo ispezionabile con oggetti esistenti,
identità coerenti e source non modificata. Cambiare la source dopo il render
non altera il modello già restituito. Un errore non pubblica un DB parziale.

**Esito del 13 ottobre — fase 1 completata:**

- Source con attributi piatti e namespace nel nome; rimossi definitivamente
  `metadata` (attributo/elemento) e il contenitore `x_ui`. I consumatori dei
  precedenti attributi UI usano il prefisso piatto `x_ui_*`.
- `validate_*` rimane sulla colonna della source; `extract_kwargs(validate=True)`
  produce le validations nella traduzione. La forma `.validation(**rules)` già
  concordata segue le stesse precedenze dei contributi.
- `_effective_model_builder` applica i default dopo la composizione e usa
  `runtime_values` di Builders per tutti gli attributi strutturali, inclusi
  quelli con prefisso. Nessuna nuova risoluzione ricorsiva dei valori.
- Le connessioni amministrative non vengono attraversate dal render strutturale;
  `connection_settings` mantiene il proprio percorso. `db.config` resta il
  lettore amministrativo; `table.config` e `column.config` leggono il modello
  completato, inclusi dtype inferiti, alias e validations.
- Verificati oggetti stabili, schema condiviso, package vuoti, override fisici,
  isolamento dalle modifiche alla source e mancata pubblicazione su errore.
  Nessuna connessione SQL durante il render.

Prove: `tests/application_config/test_render_structure.py`, suite applicativa,
validazioni/composizione e suite completa (**1084 pass, 1 skip**); Ruff e mypy
superati. L'audit dei 75 modelli legacy conferma gli snapshot immutati. Il JSON
fisico del ponte legacy resta identico all'oracolo. Questo esito non completa
l'espansione delle options né la source nativa dei 74 modelli inclusi.

### Fase 2 — Options con effetti locali

Diagnostica configurabile, invalidFields e invalidRelations sono fuori perimetro
per decisione del 13 ottobre (41, R-07); nessuna firma diagnostics da implementare.

**Lavoro, in ordine di dipendenza:**

1. Completare sys_fields, tipi locali, PK e dati pkey_columns.
2. Riprodurre campi e virtuali locali di full_update, record_hash, audit,
   protection e dynamic_fields secondo la matrice della fase 0.
3. Espandere hierarchical e poi il ramo gerarchico di auto_counter.
4. Conservare le options senza effetti strutturali individuati, senza eseguirle.

**File principali:** model_expansion.py, model_source.py; eventuali helper
interni devono riflettere le famiglie esistenti, senza registry o priorità
pubbliche. Le options non ancora gestite continuano a produrre un errore
esplicito: non rimuovere in blocco il controllo che oggi ne impedisce l'omissione.

**Prove:** confronto di nomi, dtype/size, default strutturali, metadati, virtuali
e indici; disattivazione, personalizzazione delle colonne generate, conflitti,
render ripetuti e permutazione delle dichiarazioni indipendenti. Campi con
UUID22 restano dichiarazioni: nessun nuovo UUID, numero o record generato.

**Criterio di completamento:** ogni famiglia locale prevista ha una prova di
parità, o una differenza già approvata. sys_fields non è considerato completo
solo perché produce id e timestamp: includere record_pointer e gli altri
virtuali impliciti verificati, rispettando R-02/R-03.

**Esito del 13 ottobre — fase 2 completata:** campi sys_fields, virtuali di
base e record_pointer, full_update, record_hash, audit, dynamic_fields,
protection con tag, gerarchie e contatori sono tradotti in dichiarazioni del
modello. Le altre options rimangono accessibili negli oggetti con i loro valori;
nessuna allocazione o esecuzione applicativa. Gli alias di tipo vengono risolti
anche prima delle espansioni. I default impliciti sono distinti dagli attributi
espliciti, così non annullano indexed/unique e le personalizzazioni compatibili.
Confronto indipendente con source.xml per le cinque gerarchie del corpus e
adm.user; varianti fuori corpus verificate contro i corrispondenti helper legacy.

### Fase 3 — Espansioni che coinvolgono altre tabelle

**Lavoro:** completare attachments, relative_index, link gerarchici al master
e contributi come adm → sys.task. Una dichiarazione composta (attachments)
riusa le espansioni locali già verificate; il collegamento al master avviene
quando entrambe le strutture esistono. Non assumere un ordine alfabetico dei
package né eseguire callback di scrittura per riprodurre effetti strutturali.

**Prove:** adm.htmltemplate_atc e il suo master, gli usi reali di relidx e
gerarchie collegate trovati nella fase 0; master dichiarato prima/dopo,
contributi incrociati, riferimenti mancanti, completamenti ripetuti e conflitti.

**Criterio di completamento:** tutti i campi e riferimenti strutturali attesi
sono presenti una volta sola. I completamenti non dipendono dall'ordine delle
dichiarazioni indipendenti e non producono accessi a storage o database.

**Esito del 13 ottobre — fase 3 completata:** attachments riusa sys_fields e
auto_counter; completa colonne, virtuali, FK e contributo atc_attachmenttable
al master. Gerarchie linked_to e relative_index contribuiscono alle tabelle
riferite dopo le espansioni locali. La tabella master_xtd deve già esistere.
Verificati master prima/dopo, assenza di mutazioni sulla source, conflitti e
render senza connessioni. Il confronto allegati usa adm.htmltemplate_atc con
user_upd=False esplicito, mantenendo il default pubblico concordato True.
On_duplicate conserva False/stringhe legacy; set_null implica deferred quando
non specificato. Nessun callback di scrittura viene invocato.

Le fasi 2 e 3 costituiscono questo unico incremento richiesto sulle options.
Le 40 prove mirate sono in tests/test_native_option_expansion.py. Suite completa:
**1124 pass, 1 skip**; Ruff e mypy (50 file) superati. Non certificano ancora
il port nativo integrale dei 74 modelli né la relativa proiezione fisica.

### Fase 4 — Relazioni, virtuali dichiarative e finalizzazione

**Lavoro:** completare inferenza dtype/size, PK e composite; collegare FK e
weak relations; produrre le inverse ordinarie; collegare i percorsi di
virtualRelation e aliasColumn; finalizzare indici, nomi e vincoli. Conservare
validations, query e mode di subQueryColumn, espressioni, ask/var_*, metadati
e riferimenti simbolici ai metodi. Nessuna analisi SQL aggiuntiva necessaria
per far apparire completi gli oggetti.

**Prove:** relazioni dichiarate prima dei target, sys↔adm, adm→sys.task,
price_year/price_year_note, invoice→discount_tier e invoice_row→customer;
FK circolari determinabili, catene di tipi omessi, cicli di alias, collisioni
di nomi fisici, differenze tra FK e weak, indici con ordine/metodo/predicato
non equivalenti. Le virtual relations non producono inverse, limit o one_one.

**Criterio di completamento:** nessun riferimento strutturale irrisolto o
completamento pendente quando viene pubblicato il grafo. L'ispezione del
modello usa gli oggetti, non la source. Le espressioni ancora da compilare
sono riconoscibili come dichiarazioni, non presentate come funzioni eseguibili.

### Fase 5 — Tutti i package di test_invoice_pg in source nativa

**Lavoro:** trascrivere le configurazioni originali, le options ereditate e i
contributi dei package per sys (16), adm (40), invc (18), escludendo
sys.locked_record e gli effetti system_records come concordato. Le fixture minime
usate prima si estendono al corpus; non si ricopiano le colonne espanse per
aggirare una option non implementata. L'XML legacy resta soltanto una fonte
indipendente di confronto. Nessuna dipendenza del producer dal ponte legacy.

**Prove:** confronto per package/table/column/relation/index e delle
dichiarazioni non fisiche, con copertura nominativa dei 74 modelli inclusi e
registro delle divergenze rispetto ai 75 legacy; variazione
controllata di una option e verifica degli effetti reali sugli oggetti;
modifica della source originale dopo il render senza variazioni del modello.

**Criterio di completamento:** tutti i modelli nativi rendono con esito positivo,
nessuna option attiva viene ignorata e nessun elemento atteso scompare senza
una voce nel registro delle differenze. Una dichiarazione non ancora rivista
che blocca la copertura viene discussa, non sostituita con API nuove implicite.

### Fase 6 — JSON migrations esclusivamente dagli oggetti

**Lavoro:** usare la proiezione fisica esistente a partire dal modello completo.
Verificare il percorso pubblico disponibile e adeguarne il collegamento agli
oggetti senza un secondo passaggio di espansione. Un builder fisico interno
può essere un dettaglio della proiezione, non un ritorno alla source originale.

**File principali:** projection.py e migration.py; integrazione con il modello
completato e con tests/test_release_invoice_migration.py.

**Prove obbligatorie:**

1. Produrre il JSON senza leggere source, resolver o ponte legacy; dopo il
   render, renderli indisponibili nella prova per intercettare accessi residui.
2. Validare con StructureValidator e confrontare con l'oracolo indipendente;
   ogni differenza deve avere provenienza e decisione esplicite.
3. Applicare a PostgreSQL temporaneo, fare introspezione e ottenere una seconda
   diff vuota. Non usare test_invoice_pg come database su cui applicare DDL.
4. Provare modifiche controllate a colonne, FK e indici, preservando oggetti
   SQL esterni non gestiti secondo le verifiche già presenti.

**Criterio di completamento:** source nativa → oggetti → JSON verificato su
tutti i package, senza dipendenza produttiva dagli snapshot. Report finale
con conteggi, differenze concordate e prove PostgreSQL. Questo chiude il
traguardo strutturale, non certifica compiler, scritture o rilascio pubblico.

## Verifiche e gestione delle decisioni durante il lavoro

- Test mirati alla famiglia modificata in ogni incremento; suite completa,
  Ruff e mypy nell'ambiente riproducibile alle chiusure di fase. Usare gli
  oracoli esistenti senza riscriverli per far passare un test.
- Ogni consegna indica comportamento aggiunto, prove eseguite, limiti rimasti
  e prossima dipendenza. Un errore di traduzione deve riportare il percorso
  del nodo e la dichiarazione che non può essere completata.
- Ogni nuova necessità grammaticale o differenza sostanziale dal legacy viene
  presentata prima di implementarla. Proseguire sulle parti indipendenti;
  nessuna politica di fallback silenzioso per mantenere verdi i conteggi.
- Una firma accettata non implica autorizzazione a implementarne i comportamenti
  applicativi. L'esecuzione dei resolver di configurazione segue Builders;
  record hooks, macro, validazioni sui dati e query applicative restano fuori.
- Il piano prevede un commit per fase verificata. Nessun tag, pubblicazione di
  release o push implicito. La numerazione della release resta nel piano 44.

A parità di source e valori strutturali risolti, render ripetuti devono dare lo
stesso modello. Non imporre tale uguaglianza se cambiano volontariamente valori
esterni che determinano la struttura.

## Baseline e punti da non decidere implicitamente

Baseline fisica del report 47: sys 17, adm 40, invc 18 tabelle; 796 colonne,
58 FK, 282 indici e 1 UNIQUE composita nel JSON dell'estrattore legacy. Questo
è l'oracolo da confrontare, non un input da ricopiare nel producer nativo.
Il report segnala già che l'indice esplicito di sys.locked_record non è esportato
dall'estrattore legacy: il nuovo percorso non può sopprimerlo di nascosto per
raggiungere lo stesso conteggio. Ogni differenza di questo tipo va presentata
prima di attestare equivalenza, senza introdurre qui una nuova policy.

Dettagli rilevati da correggere/verificare all'inizio dell'incremento pertinente:

- L'esempio è corretto in hierarchical + auto_counter(), senza scope relativo,
  per rappresentare counter=True del legacy. La futura traduzione va verificata
  sui campi gerarchici di product_type; il controllo grammaticale non prova parità.
- sys_fields copre i virtuali di base concordati. Diagnostica configurabile,
  record di sistema e release restano esclusi (41, R-02/R-03/R-07);
  la documentazione legacy ne conserva il riferimento per la ripresa.
- I metodi applicativi non richiedono una dichiarazione behavior o provider.
  La traduzione conserva i dati del modello; non predispone esecutori, registri
  o precedenze degli hook per una fase successiva.
- Timestamp di sistema DHZ e convenzione di scrittura UTC, senza opzioni.
  La baseline salvata usa già use_timezone=True. user_upd=True resta il default
  Asqueel concordato; il corpus può disabilitarlo esplicitamente per parità.
- La proiezione oggi usa anche un builder fisico interno. È riutilizzabile se
  viene popolato esclusivamente dagli oggetti, senza rifare espansioni o inferenze
  che appartengono al render. Il grafo degli oggetti deve già essere completo.

## File da interessare

Percorso esistente da adeguare, non architettura nuova: object_renderer.py,
configuration.py (_effective_model_builder), model_source.py, model_expansion.py,
model.py, application.py/application_table.py e model_sections.py/contracts.py.
Solo dopo, projection.py e migration.py. Test dedicati per ogni incremento più
le verifiche già disponibili in test_release_* e gli oracoli test_invoice_pg.

## Stato di avanzamento

- [x] Fase 0 — Mappa di copertura e differenze: rapporto 52; D-01/D-02 escluse per decisione.
- [x] Fase 1 — Percorso di render e oggetti esistenti.
- [x] Fase 2 — Espansioni locali.
- [x] Fase 3 — Espansioni fra tabelle.
- [ ] Fase 4 — Relazioni e finalizzazione.
- [ ] Fase 5 — Source nativa dei 74 modelli inclusi.
- [ ] Fase 6 — JSON dagli oggetti e verifica migrations.

La fase 0 è conclusa come ricognizione; D-01/D-02 sono divergenze concordate.
Le fasi 1–3 sono completate nel perimetro concordato. Restano le verifiche di
finalizzazione (4), il corpus nativo completo (5) e il JSON dagli oggetti (6).
P2 e la release non sono ancora chiuse.
