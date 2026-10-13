# 51 — Piano del render: source → oggetti vivi → JSON migrations

**Decisione successiva sui timestamp:** i timestamp di sistema sono DHZ;
la convenzione di scrittura nel DB è UTC. Per ora nessuna opzione
`timestamp_type` o `use_timezone`. Prevale sui punti ancora aperti citati sotto.
La baseline salvata del corpus usa già use_timezone=True (report 45).

12 ottobre 2026. **Piano da rivedere, non implementazione né nuove API approvate.**
Incarico: definire ordine di espansione delle options e risoluzione delle
relazioni basandosi sul legacy e sui resolver esistenti. Prevalgono le decisioni
40 e le correzioni 49–50. In questo incremento si modificano solo documenti.

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
  AttachmentTable.config_db (1697 ss.): allegati con campi di sistema, contatore,
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
| Campi locali aggiuntivi | full_update, record_hash, audit, dynamic_fields, parti locali di protection/diagnostics | Generare campi e descrizioni verificate senza interrogare l'audit. Record di sistema e release rinviati esplicitamente (41, R-02 e R-03). Gli altri effetti impliciti di sysFields nel legacy, come i virtuali di protezione/invalidità e record_pointer, non vanno persi. |
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

Risolvere aliasColumn e percorsi verso colonne generate/virtuali, dipendenze di
formule/sottoquery, pyColumn e bagItemColumn. Se questi elementi dipendono l'uno
dall'altro, seguirne le dipendenze effettive: l'elenco sopra non impone di risolvere
un alias prima della virtual relation che gli serve. Segnalare cicli di alias o
dipendenze non risolvibili; non equipararli a una normale FK circolare.

Le formule e i metodi vengono collegati e validati quanto necessario al modello,
non eseguiti su dati. Una relazione one_one non crea automaticamente UNIQUE.
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

## Incrementi di implementazione e prove di uscita

| Incremento | Lavoro | Prova prima di proseguire |
| --- | --- | --- |
| A — Percorso di render e resolver | Riutilizzare SqlObjectRenderer, model_source e i costruttori esistenti; isolare costruzione/pubblicazione e rispettare la semantica dei resolver di Builders. | Render minimo con package, colonne, EnvResolver e BagCbResolver: valutazione durante il render e valori risultanti negli oggetti; nessuna esecuzione SQL da parte del render, source invariata, nessun accesso alla source del modello dopo la pubblicazione. |
| B — Espansioni locali | sys_fields completo, campi accessori, gerarchie, contatori, dynamic fields, audit e parti locali degli allegati. | Confronto puntuale con output legacy; inversione dell'ordine delle options indipendenti; composizione, disattivazione e conflitti; nessun UUID/numero/record creato. |
| C — Completamenti e relazioni | Dipendenze inter-tabella, composite, FK/weak, inverse, virtual relations, alias e indici. | Relazioni in avanti, sys↔adm, adm→sys.task, gerarchie, allegati, price_year/price_year_note, discount_tier e alias di customer; errori leggibili per riferimenti e cicli non risolvibili. |
| D — Corpus nativo completo | Trascrivere tutte le configurazioni dei 75 modelli e il contributo inter-package usando la grammatica, senza source legacy già espansa. | Confronto degli oggetti e delle dichiarazioni virtuali/comportamentali, non solo conteggio delle tabelle. Registro delle differenze rispetto al legacy. |
| E — Proiezione migrations | Partire esclusivamente dal grafo completato; usare la proiezione fisica esistente dopo averla verificata. | Source e resolver non consultati; StructureValidator, confronto del JSON, apply/introspection/seconda diff vuota su DB temporaneo. |

A parità di source e valori strutturali risolti, render ripetute devono dare lo
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
- sys_fields nativo oggi non copre tutti i virtuali/protezioni/diagnostica
  prodotti nel legacy. Record di sistema e release sono esclusi dall'espansione
  corrente per rinvio esplicito (41, R-02 e R-03); la documentazione legacy
  ne conserva il riferimento per la ripresa.
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

Questo piano non esegue gli incrementi, non cambia la grammatica e non dichiara
chiusa P2. Il piano 44 viene riallineato per non imporre registri o versionamenti
che la revisione ha ritirato.
