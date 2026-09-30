# Asqueel moderno: obiettivi e proposta architetturale

29 settembre 2026. Documento di indirizzo, non descrizione di funzionalità
già implementate. Gli obiettivi della sezione 1 sono indicazioni dell'utente;
le altre sezioni contengono proposte da valutare. I nomi delle nuove API negli
esempi sono illustrativi e non costituiscono ancora un contratto approvato.

Il [dossier organizzato](design/README.md) raccoglie finding, obiettivi,
decisioni e piano di massima. Per obiettivi e decisioni fa riferimento il dossier;
questo documento conserva il dettaglio delle proposte architetturali.

## 1. Obiettivi acquisiti

1. Costruire un Asqueel moderno che conservi i punti migliori del legacy.
2. PostgreSQL è il database principale, in lettura e scrittura. Gli altri
   dialetti possono avere copertura inferiore, purché esplicita.
3. Ricostruire il modello sia da database esistenti sia da package/applicazioni
   legacy; mantenere anche la dichiarazione nativa con Builders.
4. Consentire mixin e componenti di adattamento della sintassi legacy da usare
   nelle applicazioni legacy.
5. Proporre miglioramenti di sintassi e prestazioni, senza imporre al nucleo
   nuovo tutti i comportamenti accidentali del precedente.
6. Eliminare `aggregateRows` e la ricomposizione Python dei join esplosivi,
   anche dal livello di compatibilità. È un vincolo acquisito, non una decisione aperta.
7. Raccogliere le informazioni tecniche, semantiche e d'interfaccia di una
   colonna in un'entità unica oppure in due entità collegate. Le informazioni
   d'interfaccia devono poter essere dichiarate nel modello o parallelamente.
8. Includere nel modello obiettivo le `virtualRelation` della nuova proposta
   GEP, secondo il contratto della discussione di settembre e i punti aperti dichiarati.
9. Prevedere, in prospettiva, view, trigger e funzioni native del database,
   accanto a hook e funzioni Python. Il contratto di asqueel-migration deve
   evolvere per gestirli; non sono richiesti nella prima implementazione.
10. Modellare esplicitamente subtable e partition del legacy, distinguendole
    da view, virtualRelation, tenant/store e partizionamento fisico del database.
11. Consentire il nome dello schema logico come prefisso del nome fisico
    delle tabelle, indipendentemente dall'uso di uno schema SQL nativo.

Conseguenza: la [specifica legacy](compiler/legacy-compatible-spec.md) è un
contratto per importatori e adattatori e un inventario delle funzionalità utili.
Non definisce automaticamente l'API nativa del prodotto nuovo. I
[casi di conformità](compiler/compatibility-cases.md) restano indispensabili
per misurare la compatibilità dichiarata dal bridge.

## 2. Cosa conservare del legacy

- Navigazione dichiarativa delle relazioni e nomi logici indipendenti dal SQL.
- Colonne fisiche e virtuali interrogabili attraverso una superficie comune.
- Formule, alias, sottoquery, varianti e parametri applicativi.
- Modello ricco di dtype, etichette, formati e metadati utilizzabili dalla GUI.
- Composizione per package e personalizzazioni di applicazione/istanza.
- Query dinamiche, filtri Bag, risultati strutturati e relazioni navigabili.
- Regole di dominio, validazioni, hook e salvataggio di strutture correlate,
  attraverso un livello runtime dichiarato.
- SQL espressivo: il framework non deve impedire di usare PostgreSQL direttamente.

Da isolare nell'adattatore: nomi dei parametri basati su id Python, sostituzioni
testuali fragili, pkey e DISTINCT impliciti, ambiguità dei count e dipendenze
ambientali non dichiarate. L'aggregazione Python dei join esplosivi viene eliminata.

Le query che dipendono da `aggregateRows` richiedono una migrazione esplicita:
aggregati calcolati dal database sull'insieme corretto, raccolte dichiarate oppure
righe espanse mantenute come tali. Il bridge deve segnalare una richiesta della
vecchia aggregazione, senza ignorarla né simularla. La conversione di risultati
già definiti in Bag/JSON resta possibile; non deve deduplicare, sommare o
ricostruire implicitamente la cardinalità delle righe dopo il fetch.

## 3. Struttura del sistema

```text
Database esistente ─────────────┐
Package/applicazione legacy ────┼─→ descrizioni di modello + provenienza
Ricette native Builders ───────┘                  ↓
                                  composizione e validazione
                                                ↓
                                     modello semantico comune
                                      ↙         ↓          ↘
                             migrazioni      runtime      strumenti/GUI
                                               ↓
API nativa / adattatore query legacy / filtri Bag → compiler
                                               ↓
                                 piano SQL + parametri + risultati
                                               ↓
                                  adapter PostgreSQL / altri adapter
```

Propongo confini di responsabilità, senza dividere subito tutto in nuovi
pacchetti Python:

| Componente | Responsabilità |
|---|---|
| Modello | Identità, tipi, relazioni, virtuali, regole e metadati. |
| Builders/composizione | Dichiarazione, montaggi di grammatica, contributi e override. |
| Importatori | Database e legacy → descrizioni normalizzate con rapporto di fedeltà. |
| Compiler | Query e comandi → piani SQL; scope, tipi, cardinalità e parametri. |
| Runtime | Connessioni, transazioni, hook, esecuzione, streaming, record e risultati. |
| Adapter | Capability, rendering, driver e introspezione specifici del database. |
| Compatibilità | Sintassi e contratti dei consumer legacy. |
| Migrazioni | Diff e applicazione delle sole modifiche fisiche, tramite il migratore. |

Il runtime delle scritture merita un progetto proprio: produrre INSERT/UPDATE
corretti non sostituisce validazioni, trigger applicativi, transazioni e salvataggi
correlati. Il piano precedente sul compiler copriva prevalentemente SELECT.

## 4. Un modello comune, con più descrizioni

### 4.1 Struttura fisica

Schema, tabelle, viste, colonne, tipi, nullabilità, default, identity, generated
columns, PK/FK/unique/check, indici e proprietà specifiche del database.
Per PostgreSQL includere progressivamente enum, domain, array, range/multirange,
JSONB, partizioni, indici parziali/espressivi e operator class.

Gli oggetti non rappresentabili nell'API portabile vanno conservati come
descrizioni specifiche del dialetto, marcate come tali. Non eliminarli durante
un successivo round-trip o diff solo perché il modello non li comprende ancora.

### 4.2 Semantica applicativa

La mappatura dei nomi fisici segue il contratto della sezione 4.5; non deve
essere ricostruita dai singoli consumer concatenando nomi arbitrariamente.

Relazioni logiche anche prive di FK, direzione, cardinalità e relativa evidenza;
alias, formule, aggregati, relazioni filtrate, dtype applicativi, etichette,
formati, policy, hook e modalità di caricamento dei risultati.

Separare cardinalità **dichiarata** da cardinalità **garantita da vincoli**:
un one_one dichiarato non autorizza da solo trasformazioni che assumono unicità
reale. Distinguere inoltre relazioni navigabili da relazioni scrivibili.

### 4.3 Provenienza e composizione

Ogni oggetto e attributo dovrebbe conservare origine, nome originale, contributi,
eventuale override e livello di fedeltà. Il modello deve poter spiegare:
«questa formula viene dal package X; questa proprietà è sovrascritta
dall'applicazione Y; questo vincolo è stato rilevato dal database».

Usare identificatori stabili distinti dal nome modificabile aiuta anche a
distinguere rename da drop/create. Gli identificatori non sono sempre
ricostruibili da un database arbitrario: serve una mappa persistente del progetto,
non una garanzia universale basata su OID.

Per i metadati applicativi proporrei namespace estensibili e tipizzati dove
possibile, preservando gli attributi sconosciuti importati. Il vincolo attuale
`x_` sugli extra non può diventare una causa di perdita nell'import legacy.

### 4.4 Identità della colonna e informazioni d'interfaccia

**Requisito acquisito:** tutte le informazioni relative a una colonna devono
essere accessibili attraverso una sola identità, indipendentemente da dove
sono dichiarate. Vale per colonne fisiche, virtuali e alias.

Sono ammesse entrambe le organizzazioni:

| Organizzazione | Descrizione |
|---|---|
| Entità unica | La colonna contiene definizione tecnica/semantica e sezione `ui`. |
| Due entità collegate | La colonna contiene la definizione tecnica/semantica; un descrittore d'interfaccia la riferisce tramite identità stabile. |

Propongo un accesso unificato ai metadati risolti in entrambi i casi. Un form,
una griglia o un editor di filtri non deve ricostruire la definizione cercando
manualmente in più registri. La seconda organizzazione permette a più applicazioni
di arricchire lo stesso modello senza richiedere modifiche alla sua sorgente.

L'identità canonica della colonna e il collegamento sono nel modello; percorso
leggibile e nomi fisici sono proprietà distinte. Il descrittore UI non replica
dtype, formula o vincoli: li consulta dalla colonna collegata.

| Gruppo | Informazioni da raccogliere |
|---|---|
| Tecnico e dominio | Tipo, nullabilità, precisione, default del dominio, vincoli, formula, relazione, unità di misura, validazioni e scrivibilità. |
| Presentazione | Etichetta e chiave di traduzione, descrizione, aiuto, formato, allineamento, larghezze suggerite, icone e rappresentazione del NULL. |
| Editing | Editor/widget suggerito, placeholder, maschera, suggerimenti e opzioni del controllo. |
| Valori e relazioni | Valori ammessi, provider delle opzioni, campi di identificazione/descrizione e suggerimenti per il lookup. |
| Ricerca | Editor del filtro, operatori suggeriti e modalità di ricerca compatibili con il tipo. |
| Contesti UI | Personalizzazioni per form, griglia, dettaglio, ricerca ed esportazione. |

Esempio concettuale delle due forme, non sintassi API approvata:

```text
Definizione integrata:
  colonna invoice.total
    tipo: decimal
    ui:
      label: Totale
      format: currency
      editor: amount

Definizione parallela equivalente:
  colonna invoice.total
    tipo: decimal
  interfaccia-colonna riferita all'identità di invoice.total
    label: Totale
    format: currency
    editor: amount
```

Regole proposte per renderle interoperabili:

1. Il modello risolto offre la stessa vista della colonna nelle due forme.
   La collocazione inline o parallela non determina da sola una precedenza.
2. I contributi seguono livelli e provenienza della composizione. Conflitti
   nello stesso livello sono segnalati; gli override intenzionali sono espliciti.
3. I metadati comuni sono la base; i profili form/griglia/ricerca applicano
   override per contesto. Layout e ordine dei campi di una schermata restano
   nella definizione della schermata, riferiti alle medesime identità.
4. I riferimenti UI mancanti sono errori di validazione. Rename e reimportazione
   preservano i collegamenti tramite la mappa di identità del progetto; i casi
   ambigui richiedono riconciliazione, non riassegnazione per somiglianza.
5. Vincoli e validazioni di dominio hanno un'unica definizione autorevole e
   possono essere presentati nell'interfaccia. Un controllo nascosto/read-only
   nell'interfaccia non modifica autorizzazioni e scrivibilità del runtime.
6. L'UI è facoltativa: il modello deve funzionare anche in uso headless.
   Preferenze per librerie di widget specifiche vivono in estensioni UI, senza
   imporre al compiler SQL dipendenze dal framework grafico.
7. La proiezione per migrazioni esclude l'UI. Cambiare un'etichetta o un widget
   non genera DDL né invalida il piano SQL quando la semantica non cambia.
8. I risultati delle query conservano l'identità d'origine e un descrittore di
   risultato: un AS può ereditare label/formato, mentre un aggregato deve
   ricalcolare tipo e scrivibilità, senza ereditare ciecamente l'editor del campo.
9. L'import legacy raccoglie name_long, formati, attributi di editing e altri
   metadati disponibili; preserva gli extra sconosciuti con provenienza.
   L'introspezione DB fornisce solo quanto osservabile, arricchibile a parte.

Questa impostazione si integra con le grammatiche in cascata: il vocabolario
UI può essere un'estensione della dichiarazione della colonna oppure una
grammatica parallela di descrittori collegati. In entrambi i casi la validazione
e la lettura dei metadati operano sul modello composto.

### 4.5 Schema logico, schema SQL e prefisso delle tabelle

Il modello deve distinguere identità logica della tabella, schema/namespace
logico, schema SQL fisico e nome SQL fisico. Il nome dello schema logico può
essere usato come prefisso del nome fisico della tabella.

Esempi di politiche alternative per la stessa tabella logica `crm.customer`:

| Politica | Destinazione fisica illustrativa |
|---|---|
| Schema SQL nativo, senza prefisso | `crm.customer` |
| Prefisso su schema SQL condiviso | `public.crm_customer` |
| Schema SQL nativo più prefisso | `crm.crm_customer` |
| Override esplicito | `public.customers_archive` |

Sono opzioni di mappatura, non equivalenze da indovinare. Il default del
prodotto nuovo resta da scegliere; l'import legacy deve preservare la mappatura
effettiva. Nei dialetti privi di schema SQL il prefisso può conservare la
separazione dei namespace, con controllo delle collisioni.

Nel legacy verificato, `sqlprefix=True` usa il nome del **package**, False
disabilita il prefisso e una stringa lo personalizza. `sqlschema` seleziona
separatamente lo schema SQL; `sqlname` esplicito della tabella prevale sul nome
generato. Package e schema SQL non coincidono necessariamente. Le subtable
basate su maintable usano il riferimento SQL della maintable.

Il nuovo contratto deve quindi supportare prefisso derivato dallo schema logico,
dal package importato, prefisso esplicito o nessun prefisso. La mappa risolta
deve essere condivisa da query, scritture, relazioni/FK, introspezione e migrazioni,
incluse view, funzioni e trigger che referenziano le tabelle.

Quoting, limiti di lunghezza e collisioni sono validati dopo la risoluzione.
La selezione dello schema tenant non deve modificare anche il prefisso della
tabella senza una politica esplicita. Cambiare la politica su un database
esistente richiede una migrazione di rename/mapping, non drop/create impliciti.

L'introspezione non deve separare automaticamente `crm_customer` al primo
underscore: il nome può essere arbitrario. Occorre una convenzione dichiarata
o una mappa persistente; l'identità logica e i metadati UI collegati rimangono
stabili quando cambia soltanto il nome fisico.

## 5. Grammatiche in cascata e configurazione

Le famiglie di oggetti includono anche quelle prospettiche descritte nelle
sezioni 5.1 e 5.2: predisporre il contratto non significa implementarle tutte subito.

Raccomando di usare i meccanismi di grammatica distribuita di Builders per le
estensioni del modello, mantenendo coerente il vocabolario SQL fondamentale.
Il piccolo prototipo già eseguito mostra che i montaggi possono mantenere gli
indirizzi per nome; resta da provarne l'integrazione con i consumer SQL attuali.

Distinguere sempre:

1. **Grammatica:** quali elementi e attributi può dichiarare ciascun contributo.
2. **Composizione:** come package, applicazione e istanza contribuiscono allo stesso
   modello e come vengono risolti i conflitti.
3. **Configurazione runtime:** connessioni, store, pool, profilo e parametri.

Per i contributi applicativi propongo precedenza esplicita package → applicazione
→ istanza, con provenienza. L'introspezione del database è una descrizione dello
stato osservato: non deve sovrascrivere automaticamente lo stato desiderato del
modello durante la composizione.

Il merge generico Bag non basta per tutti gli oggetti SQL: aggiungere una colonna,
sostituire una formula, rimuovere un vincolo e rinominare una tabella sono operazioni
diverse. Servono regole per famiglia, conflitti segnalati, rimozione esplicita e
override intenzionale. Non rendere ogni tabella un dialetto indipendente quando
cambiano soltanto i suoi dati di dichiarazione.

### 5.1 View, trigger e funzioni native: estensione prospettica

Questi oggetti devono essere rappresentabili nel modello, nell'introspezione
e nel contratto di migrazione. Il supporto iniziale può restare assente, ma
deve essere dichiarato per capability; nessuna applicazione silenziosamente
incompleta di un modello che li richiede.

| Oggetto | Informazioni da conservare |
|---|---|
| View SQL | Identità/schema, definizione, colonne/tipi, dipendenze, opzioni e capability di scrittura. |
| Materialized view, proposta correlata | Definizione e dipendenze più indici e politica di refresh; non confonderla con una view ordinaria. |
| Funzione nativa | Schema, nome e firma degli argomenti per distinguere overload; risultato scalare/set/tabella, linguaggio, corpo, proprietà e dipendenze. |
| Trigger DML | Tabella/view, eventi, BEFORE/AFTER/INSTEAD OF dove applicabile, livello riga/statement, condizione, funzione invocata e stato. |
| Event trigger DDL | Famiglia separata dai trigger sulle righe; eventi, funzione e dipendenze specifiche. |
| Hook Python | Provider, fase, eventi, contesto runtime e contratto degli effetti. Nessuna traduzione automatica in trigger SQL. |

Una view nativa può essere esposta come sorgente interrogabile con identità
di colonna e UI. La scrivibilità deve derivare da una capability verificata,
non dalla sua somiglianza con una tabella; PostgreSQL consente differenti
modalità di aggiornamento delle view.
[CREATE VIEW](https://www.postgresql.org/docs/18/sql-createview.html).

Per le funzioni native il compiler deve conoscere firma, tipo restituito e
proprietà rilevanti alle trasformazioni: non duplicare o spostare chiamate
volatili come se fossero pure. Volatilità, parallel safety, STRICT, privilegi,
SECURITY INVOKER/DEFINER e configurazione del contesto sono parte del descrittore,
non testo accessorio da perdere nell'import/export.
[CREATE FUNCTION](https://www.postgresql.org/docs/18/sql-createfunction.html).

Convivenza con gli hook Python:

- I trigger nativi operano nel database anche quando la scrittura non passa
  dal runtime Python. Gli hook Python operano nel percorso runtime che li invoca.
- Dichiarare quale componente è responsabile di ogni regola: la stessa logica
  non deve essere eseguita due volte per un'importazione o per un bulk.
- Definire le fasi hook prima del comando, trigger durante il comando, hook
  successivi e notifiche dopo il commit. Trigger differibili e statement-level
  impediscono di ridurre tutto a un unico ordine prima/dopo per riga.
- Rollback, eccezioni, valori restituiti e necessità di ricaricare dati dopo
  modifiche native vanno provati insieme. Non promettere che RETURNING rifletta
  qualsiasi ulteriore scrittura eseguita da un trigger AFTER.

[Comportamento dei trigger PostgreSQL](https://www.postgresql.org/docs/18/trigger-definition.html).

Per asqueel-migration propongo un'estensione versionata del contratto che
comprenda reader, strutture normalizzate, validazione, diff, piano e writer.
Requisiti: creazione/modifica/rimozione, identità delle funzioni per firma,
dipendenze fra funzioni/view/tabelle/trigger e ordinamento delle operazioni.
CREATE OR REPLACE non risolve ogni cambiamento: il planner deve distinguere
sostituzione consentita, ricreazione e migrazione esplicita.

Preservare corpi SQL e proprietà senza normalizzazioni che ne cambino la
semantica. Il grafo deve ammettere dipendenze esplicite per SQL dinamico/codice
procedurale non analizzabile. Segnalare cambiamenti distruttivi e oggetti esterni
al perimetro gestito; non usare CASCADE per nascondere dipendenze non risolte.
Il collaudo richiede round-trip su DB reale, secondo diff vuoto quando previsto,
comportamento degli oggetti creati e test di convivenza con gli hook Python.

Stato osservato nel checkout locale del migratore: esistono entità
`event_trigger`, ma `added_event_trigger` e `removed_event_trigger` nel
command builder sono no-op. Questo non certifica supporto end-to-end degli
event trigger, né dei trigger DML, delle view o delle funzioni. L'estensione è
un obiettivo futuro, non una capability da attribuire alla versione attuale.

### 5.2 Subtable, partizioni e altri concetti da tenere distinti

| Concetto | Significato nel modello | Conseguenze |
|---|---|---|
| Subtable dichiarata sulla tabella | Sottoinsieme nominato tramite condizione, con parametri e metadati. | Filtro di query e identità semantica/UI; non crea automaticamente una view SQL. |
| Subtable dichiarata sul package legacy | Specializzazione di modello con `maintable`, campi/relazioni ereditati e discriminatore `__subtable`. | Riferimento SQL alla maintable e comportamento specifico da preservare in import e scritture; non equiparare a PostgreSQL INHERITS. |
| Partizione logica legacy `partition_*` | Ambito applicativo basato su campo e contesto corrente/consentito. | Policy che contribuisce al WHERE; non crea partizioni fisiche. |
| Partizionamento fisico PostgreSQL | Tabella partizionata e partizioni con strategia RANGE/LIST/HASH, chiavi e limiti. | DDL, routing del database, attach/detach, indici e vincoli specifici. |
| Tenant/store | Contesto di isolamento o selezione schema/connessione. | Distinto da un filtro logico e dalla suddivisione fisica della tabella. |
| VirtualRelation | Insieme target collegato a una riga sorgente, eventualmente filtrato/limitato. | Navigazione e aggregati con correlazione; non è una subtable né una view nativa. |
| View nativa | Oggetto SQL con definizione e colonne proprie. | Dipendenze, introspezione e migrazione; può proiettare/joinare/aggregare. |

Dettagli della baseline legacy che l'importatore deve conservare:

1. La subtable di tabella registra anche una virtuale booleana `subtable_<nome>`
   e può avere parametri `condition_*`; non è soltanto un nome da anteporre al WHERE.
2. La subtable di package copia dichiarazioni con `sql_inherited`, usa
   `maintable`, aggiunge `__subtable` e definizioni `_main`/default_subtable.
   La copia esclude attributi `partition_*`: non estendere automaticamente
   quelle policy alla specializzazione durante la nuova importazione.
3. `subtable='*'` disattiva il filtro subtable, non la partizione logica,
   il tenant o l'eventuale RLS. Default, contesto e argomento esplicito
   mantengono la precedenza documentata nella specifica legacy.
4. `getPartitionCondition` usa prima `current_<path>` truthy; altrimenti
   `allowed_<path>` truthy produce un filtro che ammette anche campo NULL;
   altrimenti cerca una relazione verso `__allowed_partition`. Se non trova
   una condizione non c'è un filtro garantito: non chiamare questo meccanismo
   una barriera di autorizzazione completa.
5. `ignorePartition` riguarda quella policy applicativa. Una lista consentita
   vuota e un current falsy non hanno nel vecchio codice la semantica intuitiva
   «nessun accesso»: vanno caratterizzati e resi espliciti nel profilo nuovo.
6. `partitionParameters` sceglie la prima dichiarazione `partition_*`.
   Più dimensioni di partizione logica richiedono un contratto nuovo; non
   assumere che il legacy le componga già correttamente.

Nel modello nuovo propongo descrittori distinti per subset/specializzazione,
scope applicativo, tenant/store e storage partitioning. Le regole possono
convivere, ma ciascuna conserva origine e scopo. Un bypass non deve disabilitare
le altre regole accidentalmente.

Per le scritture vanno dichiarati default/validazione del discriminatore,
possibilità di cambiare appartenenza alla subtable o allo scope e comportamento
di UPDATE/DELETE filtrati. Un filtro di lettura non è automaticamente una
validazione d'inserimento: l'import legacy deve inventariare gli hook effettivi.

Il partizionamento fisico entra invece nella prospettiva del migratore:
strategia, chiavi, partizioni/default, limiti, gerarchia, attach/detach e impatto
sui dati. Cambiare strategia o trasformare una tabella ordinaria richiede un
piano appropriato, non una semplice variazione di attributo. Pruning e routing
sono responsabilità del database, non del filtro `partition_*`.
[Partizionamento PostgreSQL](https://www.postgresql.org/docs/18/ddl-partitioning.html).

## 6. Costruire il modello da un database

Propongo un importatore che produca quattro risultati: modello fisico,
relazioni deducibili, rapporto delle informazioni mancanti e ricetta nativa
rigenerabile. Le estensioni manuali stanno in contributi separati, così una
nuova introspezione non le sovrascrive.

| Ricostruibile dal database | Non ricostruibile in generale |
|---|---|
| Tabelle, colonne, nomi SQL e tipi | Organizzazione originaria dei package Python. |
| Vincoli, indici, default e commenti presenti | Formule Python, callback e hook applicativi. |
| Viste e oggetti specifici rappresentabili | Etichette, widget e preferenze non memorizzati nel DB. |
| Relazioni da FK e unicità garantita | Relazioni logiche prive di vincoli e loro nomi desiderati. |
| Policy/trigger definiti nel database | Policy che esistono soltanto nell'applicazione. |

Le inferenze da convenzioni, per esempio `customer_id`, devono essere suggerimenti
con evidenza; non diventano FK o relazioni certe automaticamente. Un database
senza PK deve poter essere letto; le operazioni record che richiedono identità
devono dichiarare la propria limitazione.

Il test di accettazione è una nuova introspezione senza differenze inattese su
un database di prova dopo l'export/import degli oggetti supportati. Conservare
separatamente gli oggetti non gestiti. Il round-trip non deve applicare DDL
all'ambiente sorgente.

## 7. Costruire il modello da package e applicazioni legacy

Servono due percorsi complementari:

- **Estrazione statica:** inventario di dichiarazioni e dipendenze senza eseguire
  codice. Utile per diagnosi e per il sottoinsieme dichiarativo, ma non risolve
  in generale Python dinamico, sysFields, callback e personalizzazioni.
- **Esportazione dal modello runtime risolto:** avviare l'applicazione legacy in
  un ambiente dedicato e raccogliere il modello dopo mixin, config_db e override.
  È il percorso di riferimento quando interessa il comportamento effettivo.

L'esportatore runtime deve dichiarare quali dipendenze inizializza: l'avvio di
una vera applicazione può eseguire codice e richiedere servizi. Non descriverlo
come una lettura innocua di soli file. Prevedere una modalità di estrazione
controllata e un rapporto delle funzionalità non esportabili.

Un package isolato può dipendere da altri package e dall'istanza: esportare il
grafo delle dipendenze e segnalare il contesto assente. Una callback Python può
essere conservata come riferimento a un provider legacy, tradotta se supportata
o marcata non risolta; non è serializzabile automaticamente come formula SQL.

La provenienza va catturata durante la composizione dove possibile. Dal solo
modello finale si può osservare un valore, ma non sempre ricostruire quale
override lo abbia prodotto.

Proporrei livelli di fedeltà per oggetto:

| Livello | Significato |
|---|---|
| Nativo | Rappresentato senza dipendenze dal legacy. |
| Adattato | Stessa semantica attraverso un traduttore noto. |
| Collegato | Richiede ancora un provider/callback legacy. |
| Non risolto | Manca codice o contesto; utilizzabilità limitata e visibile. |

Importare il modello, eseguire vecchie query ed eseguire l'intera applicazione
sono tre traguardi diversi. Non promettere compatibilità applicativa completa
solo perché l'importazione dello schema riesce.

## 8. Compatibilità tramite mixin e adapter

La concessione dei mixin permette di mantenere pulito il nucleo nuovo.
Raccomando mixin sottili che delegano a servizi, evitando gerarchie multiple
profonde con stato implicito e override del planner.

| Adattatore | Compito |
|---|---|
| Dichiarazioni legacy | config_db, package, sysFields e metadati → modello comune. |
| Query legacy | Opzioni implicite, stringhe e query Bag → QuerySpec. |
| Risultati legacy | Alias, pkey aggiunta, Bag, resultmap, selection e resolver. |
| Scritture legacy | API esistenti, validazioni e hook → runtime dei comandi. |
| Contesto legacy | currentEnv e parametri dell'istanza → contesto esplicito. |

Il bridge può essere adottato progressivamente per applicazione o tabella, ma
non deve mischiare transaction manager differenti nella stessa operazione.
Profilo di compatibilità e versione vanno dichiarati: i 19 casi ambigui censiti
non devono riapparire come condizioni sparse nel nucleo.

## 9. Miglioramenti proposti della sintassi nativa

Gli esempi seguenti descrivono intenzioni e alternative. Non sono API esistenti.

### 9.1 Conservare i riferimenti familiari, aggiungere una forma strutturata

Terrei `$campo`, `@relazione.campo`, `:parametro` e AS nel frontend testuale.
Aggiungerei un frontend a oggetti e una forma per i filtri Bag, entrambi diretti
allo stesso albero semantico. SQL testuale e API strutturata non devono avere
regole diverse per relazioni e tipi.

Una SELECT potrebbe accettare elementi separati per evitare ambiguità di comma:

```python
# Proposta, non API implementata.
q = customer.select(
    "$id",
    "$name",
    "@invoices.sum($total) AS invoiced",
)
q = q.where("@invoices.exists($status=:status)", status="open")
```

### 9.2 Rendere esplicita la cardinalità

La distinzione centrale è fra scalare, insieme e righe esplose:

| Intenzione | Sintassi candidata / comportamento |
|---|---|
| Campo di una relazione one | `@customer.name`. |
| Somma sulle fatture | `@invoices.sum($total)`. |
| Numero di fatture | `@invoices.count()`. |
| Almeno una fattura aperta | `@invoices.exists($status=:status)`. |
| Nessuna fattura aperta | NOT dell'EXISTS precedente. |
| Raccolta di valori | `@invoices.to_array($number)` con ordine esplicito quando necessario. |
| Raccolta di record | Proiezione strutturata della relazione, resa come JSON/Bag/righe. |
| Una riga per fattura | Operazione esplicita di espansione della relazione. |

Nell'API nativa, una foglia many in una proiezione che richiede uno scalare
dovrebbe chiedere un aggregato, una raccolta o un'espansione. Il frontend legacy
può conservare la vecchia navigazione esplosiva. La scelta di un'altra semantica
per la stessa stringa deve risultare dal profilo usato, mai dal caso.

Distinguere anche «esiste una fattura che soddisfa A e B» da «esiste una fattura
che soddisfa A ed esiste una fattura che soddisfa B»: due EXISTS indipendenti
non sono sempre equivalenti a uno solo.

### 9.3 Precisare gli aggregati

- `@invoices.@rows.sum($quantity)` aggrega tutte le righe raggiunte.
- `@invoices.avg(@rows.sum($quantity))` aggrega prima per fattura, poi sui totali.
- `count()` conta righe, `count($field)` valori non NULL, distinct è esplicito.
- SUM su insieme vuoto conserva NULL salvo richiesta esplicita di default/COALESCE.
- Numeri usano somma; testi usano un'operazione di concatenazione distinta.
  Eviterei `sum` che cambia significato in concatenazione in base al dtype.
- Ogni aggregato/raccolta definisce filtri, ordine, NULL, duplicati e tipo di uscita.

### 9.4 Relazioni virtuali nominate

Le `virtualRelation` fanno parte del modello obiettivo. Il riferimento è
l'evoluzione della proposta GEP sulle relazioni nella
[discussione dedicata](https://github.com/genropy/genropy_meta/issues/1), che
adotta questo nome unico al posto della separazione manyRelation/relationView.
Non si tratta di una funzionalità già implementata nel compiler legacy.

Contratto da portare nel modello e nel compiler:

- `relation=` deriva da una relazione esistente; `table=` definisce un
  collegamento con una tabella destinazione anche senza FK.
- In `condition`, `$col` e `@rel.col` appartengono alla destinazione B.
  Espressioni della riga sorgente A arrivano attraverso binding
  `var_nome=<espressione di A>`, usati come `:var_nome`. Non si introduce
  `#THIS` in questa grammatica.
- Predicati dipendenti dalla sorgente definiscono il collegamento; quelli
  indipendenti definiscono filtri. La classificazione deve rispettare la
  struttura booleana, senza separare impropriamente gli OR. Il caso `table=`
  richiede un collegamento effettivo, non un prodotto cartesiano filtrato accidentale.
- Sono relazioni derivate di sola lettura, escluse dal salvataggio dei
  record-cluster e dalla generazione automatica di FK/vincoli/azioni onDelete.
- Supportano composizione di relazioni e filtri, con rilevamento dei cicli.
- `order_by` e `limit` si applicano all'insieme raggiunto per ciascuna riga
  sorgente. `limit=1` produce cardinalità al massimo uno e richiede ordine
  deterministico; senza limite, dichiarare one_one non dimostra l'unicità dei dati.
- Restano navigabili da query e GUI e utilizzabili negli aggregati per relazione.
  Le condizioni nella navigazione LEFT restano nell'ON, preservando le righe
  sorgenti senza corrispondenza.
- Metadati d'interfaccia e parametri `ask` seguono il modello comune; binding,
  ambiente e varianti entrano nell'identità del contesto di compilazione.

Esempi ripresi dalla proposta, non API già implementate:

```python
tbl.virtualRelation('invoices_current_year', relation='@invoices',
                    condition='$year = :env_current_year')
tbl.virtualRelation('discount_tiers', table='invc.discount_tier',
                    condition='$customer_type_code = :var_type',
                    var_type='$customer_type_code')
tbl.virtualRelation('last_invoice', relation='@invoices',
                    order_by='$date DESC, $id DESC', limit=1)
```

Restano da consolidare i punti aperti della discussione: derivazione da relazioni
già limitate, inverse dei collegamenti filtrati e collisioni/namespacing dei
parametri ask. Non considerarli risolti per il solo fatto di includere
virtualRelation nell'obiettivo. Il binding `var_*` a espressioni di A è una
semantica nuova, distinta dai valori costanti var_* delle formule legacy.

### 9.5 Eliminare ambiguità frequenti

| Proposta nativa | Beneficio |
|---|---|
| Parametri-valore separati da riferimenti-campo espliciti | Una stringa che inizia con `$` resta un valore se passata come valore. |
| Nessuna pkey nascosta nella SELECT generica | Proiezione prevedibile; l'API record può richiedere identità. |
| Nessun DISTINCT aggiunto per correggere un modello many ambiguo | Cardinalità visibile e aggregati corretti. |
| `limit(0)` restituisce zero righe | Semantica coerente, senza dipendere dalla truthiness. |
| `count_rows()` distinto da count delle entità | Non confondere righe joinate, gruppi e record principali. |
| `count_total()` distinto da count della pagina | LIMIT/OFFSET non alterano un conteggio a sorpresa. |
| Query immutabili e componibili | Una modifica non cambia una query condivisa altrove. |
| Alias espliciti per espressioni; collisioni segnalate | Nomi di output stabili senza sovrascritture silenziose. |
| `one()`, `one_or_none()`, `first()` distinti | Differenza esplicita fra unicità attesa e prima riga. |
| Intervalli chiusi/semiaperti dichiarati | Date e timestamp senza divergenze fra macro simili. |
| Policy applicate tramite contesto esplicito | Dipendenze visibili e bypass intenzionali. |
| SQL opaco marcato come tale, binding separati | Accesso completo al dialetto senza ricorrere a interpolazioni. |

Uniformerei anche macro e funzioni: un registry con firme, tipi, contesti,
dipendenze e capability. Il frontend legacy traduce le vecchie #MACRO; quello
nativo non dovrebbe dipendere dall'ordine casuale delle sostituzioni testuali.
Full-text e vector avrebbero un oggetto/contesto ricerca esplicito, riutilizzato
da filtro, ranking e highlight, senza canali nascosti dentro sqlparams.

## 10. PostgreSQL completo anche nelle scritture

Propongo due livelli dichiarati: comandi SQL espliciti e operazioni di dominio
che applicano validazioni/hook. Il livello scelto deve essere visibile, soprattutto
per bulk: accelerare saltando hook senza dirlo cambia il significato dell'operazione.

| Area | Contratto da progettare |
|---|---|
| INSERT | Colonne omesse/default distinte da NULL; generated/identity; RETURNING. |
| UPDATE | Patch dei soli campi indicati; espressioni incrementali; RETURNING. |
| DELETE | Hard delete distinto dalla policy soft delete; risultato e righe coinvolte. |
| UPSERT | Chiave/vincolo di conflitto esplicito, azione e condizione; niente SELECT preventivo obbligatorio. |
| Scritture multiple | Batch/multirow con gestione coerente di default, errori e risultati. |
| Bulk/COPY | Canale dedicato, conversioni e politica degli hook esplicite. |
| Transazioni | Commit/rollback, savepoint, unità di lavoro e responsabilità delle connessioni. |
| Concorrenza | Lock, optimistic locking con versione attesa e conflitto distinguibile. |
| Retry | Solo per errori/operazioni adatti; niente ripetizione cieca di effetti esterni. |
| Record correlati | Grafo di dipendenze, PK generate, ordine delle scritture e atomicità. |
| Hook | Ordine definito, effetti transazionali e callback dopo il commit separati. |
| DML massivo | Supporto a INSERT da SELECT, UPDATE/DELETE con condizioni e sorgenti quando previsto. |

`RETURNING` e `ON CONFLICT` sono primitive da esporre direttamente sul percorso
PostgreSQL, senza richiedere round-trip di lettura aggiuntivi quando non servono.
[Documentazione INSERT](https://www.postgresql.org/docs/18/sql-insert.html).

COPY è un percorso bulk specifico: vanno controllati vincoli, trigger, privilegi
e limiti rispetto alle policy, oltre alle conversioni. Non è equivalente a
invocare il runtime degli hook Python per ogni riga.
[Documentazione COPY](https://www.postgresql.org/docs/18/sql-copy.html).

Tenant e policy devono essere coerenti anche nelle scritture. L'eventuale RLS
PostgreSQL è un livello ulteriore, con semantica propria per lettura/scrittura,
ruoli e owner; non sostituisce automaticamente le policy applicative.
[Documentazione RLS](https://www.postgresql.org/docs/18/ddl-rowsecurity.html).

## 11. Miglioramenti di prestazioni e come verificarli

La prima ottimizzazione è evitare lavoro e molteplicità non richiesti.
Il planner PostgreSQL resta responsabile del piano fisico; Genro deve produrre
una rappresentazione SQL corretta e abbastanza chiara, senza tentare subito
di costruire un secondo ottimizzatore a costi.

| Intervento proposto | Vantaggio atteso | Verifica / limite |
|---|---|---|
| Aggregati per relazione | Evita prodotti di righe e ricomposizione Python | Stessi NULL/duplicati e risultati su casi con cardinalità diverse. |
| EXISTS per predicati di esistenza espliciti | Evita proiezioni/join non necessari | Non riscrivere arbitrariamente predicati legacy o NOT IN con NULL. |
| Più aggregati sullo stesso insieme in una sorgente comune | Riduce scansioni ripetute | Stessi filtri, scope, politica NULL e assenza di effetti volatili. |
| Sottoquery correlata, LATERAL o join preaggregato | Forme alternative per carichi diversi | Nessuna vincente universale; misurare selettività e numero righe. |
| Caricamento relazioni per gruppi | Evita vere query N+1 | Numero query e volume dati; snapshot transazionale coerente. |
| Paginazione keyset | Riduce lavoro su pagine profonde ordinate | Ordine stabile, NULL e tie-break; niente salto arbitrario alla pagina N. |
| Proiezioni minime | Meno I/O, conversioni e memoria | Non selezionare Bag/JSON grandi o virtuali costose inutilizzate. |
| Streaming e fetch a blocchi | Memoria proporzionale al blocco | Durata transazione/cursore, chiusura su errore e cancellazione. |
| Batch, COPY e RETURNING | Meno round-trip e overhead per riga | Distinguere canale SQL e canale con hook di dominio. |
| Cache del parsing | Riusa struttura sintattica | Chiave per grammatica/profilo, senza valori di utente. |
| Cache del piano risolto | Riusa risoluzione modello | Versione modello, dialetto, policy e struttura delle varianti. |
| Statement preparati del driver | Possibile riduzione del costo ripetuto | Piano generico/specifico, pool e cambio schema; misurare. |
| Pool connessioni | Riduce apertura connessioni | Reset corretto di tenant, ruolo, transazione e contesto. |
| Conversioni lazy/opt-in | Evita costo Bag/JSON/Python non richiesto | Tipo di risultato esplicito; niente cambio silenzioso dell'API. |
| Indici guidati dal carico | Riduce accessi nelle query frequenti | Suggerimenti con EXPLAIN, non creazione automatica indiscriminata. |

LATERAL consente dipendenze dalla riga esterna, ma non garantisce da solo una
scansione più economica. Anche una sottoquery correlata può essere parte di
un unico SQL e non implica N+1 chiamate al database.
[Table expressions](https://www.postgresql.org/docs/18/queries-table-expressions.html).

Non userei CTE come sinonimo di ottimizzazione: folding/materializzazione e
riutilizzo possono favorire o ostacolare un caso concreto.
[WITH queries](https://www.postgresql.org/docs/18/queries-with.html).

Eviterei inizialmente la cache dei risultati, l'identity map generalizzata e
l'invalidazione distribuita: introducono contratti di coerenza molto più ampi
della cache del compiler. Async è utile per concorrenza/I/O, ma non rende
automaticamente più veloce la singola query. Progettare fin dall'inizio la
separazione compiler/esecutore consente un executor async successivo.

## 12. Diagnostica come funzionalità del prodotto

Propongo strumenti che mostrino per ogni query:

- Espressione originale e posizione dell'errore.
- Colonne, relazioni e policy risolte, con provenienza dal modello.
- Cardinalità prevista e punto in cui si introduce un insieme many.
- SQL prodotto, tipi dei binding e parametri sensibili oscurati.
- Numero di query, righe, tempo di compilazione/esecuzione/postprocessing.
- Strategia di caricamento e trasformazioni applicate.
- Differenze rispetto al compiler legacy, quando richiesto.

Per i benchmark distinguere EXPLAIN da EXPLAIN ANALYZE: quest'ultimo esegue
la query. Per DML e funzioni con effetti non va offerto come anteprima innocua.
[Using EXPLAIN](https://www.postgresql.org/docs/18/using-explain.html).

Misurare carichi piccoli/grandi, filtri selettivi/non selettivi, dati sbilanciati,
NULL, molte relazioni e latenza di rete. Confrontare anche p95, query count,
buffer e memoria, non soltanto il tempo medio su dati uniformi.

## 13. Dialetti a capacità dichiarate

Propongo PostgreSQL come implementazione di riferimento e SQLite come secondo
adapter utile per il sottoinsieme portabile e test rapidi. MySQL/MariaDB, MSSQL
e altri vengono coperti secondo necessità reali, con matrice pubblica.

Ogni funzionalità ha uno stato: nativa, emulata con semantica dichiarata oppure
non supportata. La matrice dipende anche da versione server, driver ed estensioni.
La versione minima PostgreSQL è una decisione di distribuzione da prendere
prima della release, non deducibile dal solo obiettivo «PostgreSQL primario».

Il compiler può rifiutare una funzionalità non supportata prima di eseguire SQL.
Non deve offrire una finta portabilità convertendo in silenzio JSONB, lock,
full-text, vector o RETURNING in un comportamento diverso.

## 14. Priorità e sequenza suggerita

| Passo | Risultato verificabile |
|---|---|
| 1. Contratti comuni | Modello, cardinalità, tipi, composizione, contesto, risultati e transazioni descritti. |
| 2. Modello da tre origini | Stesso piccolo dominio ottenuto da DB, app legacy e ricetta nativa, con rapporto di fedeltà. |
| 3. Percorso PostgreSQL minimo completo | Lettura con relazione + INSERT/UPDATE/DELETE + RETURNING e rollback su DB reale. |
| 4. Compiler nativo | Scope, formule, aggregati per relazione, esistenza, gruppi, sottoquery e query Bag. |
| 5. Bridge legacy incrementale | Applicazione campione con casi di lettura e scrittura effettivi, confrontati sul baseline. |
| 6. Runtime applicativo | Hook, grafi di scrittura, policy, concorrenza e caricamento relazioni. |
| 7. Ottimizzazioni misurate | Benchmark ripetibili e strategie alternative dove migliorano il carico reale. |
| 8. Dialetti ulteriori | Stesso corpus nel sottoinsieme dichiarato, errori espliciti fuori da esso. |

Le prove PostgreSQL e SQLite possono iniziare subito; la tabella non implica
attendere la fine del compiler per provare l'esecuzione. Il passo 3 è un percorso
verticale piccolo ma completo, utile a verificare presto che il modello non sia
stato progettato soltanto per le SELECT.

Priorità alta: modello comune, importer runtime legacy, introspezione fedele,
lettura/scrittura PostgreSQL, aggregati corretti, parametri espliciti e bridge.
Priorità successiva: ottimizzazioni del piano, ergonomia estesa, seconda API a
oggetti, async e copertura di altri dialetti. Evitare una grande riscrittura
senza un'applicazione campione che verifichi i confini durante lo sviluppo.

## 15. Decisioni da risolvere durante la progettazione

Questi punti non impediscono la proposta, ma devono essere chiusi prima delle
relative implementazioni:

1. Package/applicazione campione e database campione rappresentativi.
2. Minimo PostgreSQL e driver; altri dialetti richiesti nella prima release.
3. Forma nativa finale: frontend testuale iniziale, oggetti e ruolo di Bag.
4. Semantica della proiezione many, dei default degli aggregati e delle raccolte.
5. Confine delle scritture: primitive SQL, hook di dominio e record-cluster.
6. Politica dei metadati extra e schema della provenienza.
7. Composizione package/app/istanza, conflitti e rimozioni esplicite.
8. Livelli di compatibilità e anomalie legacy da emulare effettivamente.

Non propongo di decidere tutto subito: partirei dai contratti del modello e
dal dominio campione, portando lettura e scrittura nel primo prototipo. Questo
rende concrete le decisioni senza bloccarle su una sintassi ancora teorica.
