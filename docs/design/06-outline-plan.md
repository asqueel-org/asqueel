# 06 — Piano di massima e tracciabilità

Questo è un piano proposto, non un registro di implementazione. Nessuna fase
è dichiarata completata. Le verifiche storiche indicate nelle
[fonti](00-sources-and-evidence.md) non certificano il prodotto futuro.

## Strategia e dipendenze

Prima si fissa il contratto del modello, poi si realizza una prova verticale
PostgreSQL di lettura e scrittura. Gli importatori e il compiler crescono sullo
stesso contratto; non occorre completare l'importazione di tutto il legacy per
provare una query. L'adozione di un'applicazione reale precede le ottimizzazioni.

| Fase | Prerequisiti | Risultato principale |
|---|---|---|
| P0 | Dossier e fonti disponibili | Perimetro, baseline e campioni riproducibili. |
| P1 | P0 | Contratti del modello e composizione verificata. |
| P2 | Contratto minimo P1 | Importatori e confronto del modello dalle tre origini. |
| P3 | Contratto minimo P1, fixture P0 | Primo percorso PostgreSQL completo read/write. |
| P4 | P3, risoluzione del modello P1 | Compiler semantico e virtualRelation. |
| P5 | P4 e importazione del campione P2 | Bridge, scritture di dominio e adozione campione. |
| P6 | P5, misure iniziate in P3 | Prestazioni e gestione risorse verificate. |
| P7 | Contratti P1 e runtime/migrazioni stabilizzati | Estensione futura a oggetti nativi e partizioni fisiche. |
| P8 | P2–P6 nel profilo scelto | Rilascio, capacità dichiarate e ulteriori dialetti. |

P2 e P3 possono avanzare in parallelo dopo aver fissato il modello minimo.
P7 è un ramo prospettico: **non blocca il primo rilascio P8**. Quando disponibile,
la sua estensione attraverserà nuovamente le verifiche di rilascio. La numerazione
non impone nove passaggi rigidamente seriali.

## P0 — Baseline, perimetro e campioni

**Scopo.** Trasformare l'analisi in un perimetro verificabile prima di scrivere
il nuovo compiler.

**Attività e risultati.**

- Congelare revisioni, dipendenze e configurazioni dei confronti; distinguere
  la baseline legacy, il package attuale e le versioni del migratore.
- Selezionare un database di prova e un'applicazione/package rappresentativo;
  inventariare query, formule, relazioni, subtable, scope, hook e consumer dei risultati.
- Preparare fixture con duplicati legittimi, NULL, relazioni vuote, cardinalità
  multiple, nomi da quotare e override di schema/prefisso.
- Classificare il corpus in equivalenza legacy, correzione deliberata,
  nuovo contratto e funzionalità esclusa dal profilo iniziale.
- Censire gli usi di aggregateRows e associare una riscrittura esplicita a
  ogni forma: aggregato SQL, raccolta dichiarata o righe espanse.
- Registrare ambiente e procedura di riproduzione delle issue del migratore.

**Accettazione.** Ogni funzionalità del campione ha un contratto o un'esclusione
motivata; i risultati numerici delle fixture sono controllabili indipendentemente
dal legacy. Le divergenze intenzionali non vengono confuse con regressioni.

**Decisioni.** D-01, perimetro iniziale D-07 e D-12.
**Fuori fase.** Nessuna nuova architettura implementata; nessuna esecuzione
modificativa su database di produzione.

## P1 — Modello comune, identità e grammatiche

**Scopo.** Definire ciò che importatori, compiler, UI e migratore devono condividere.

**Attività e risultati.**

- Separare descrizione sorgente, modello risolto e proiezione fisica; fissare
  identità, riferimenti, serializzazione, versione e provenienza dei contributi.
- Definire colonne fisiche/virtuali, formule, relazioni, parametri e provider;
  distinguere attributi dichiarati, ereditati, derivati e non rappresentabili.
- Dare ai metadati UI inline e paralleli la stessa identità di colonna, con
  precedenze e profili espliciti; mantenere funzionamento senza librerie GUI.
- Formalizzare package/schema logico, schema SQL, prefisso, sqlname, maintable
  e tenant/store. Il compiler riceve nomi risolti, non concatena convenzioni proprie.
- Rappresentare separatamente subtable filtrata, specializzazione legacy,
  scope logico partition e descrittore di partizionamento fisico.
- Provare i montaggi Builders e la composizione di configurazioni con schema,
  tabella, colonna, validatore, emitter e consumer del migratore. Verificare
  override, rimozioni, conflitti e stabilità degli indirizzi.
- Riservare identità e dipendenze per view, funzioni e trigger futuri, senza
  fingere che un descrittore privo di executor sia già una funzionalità supportata.

**Accettazione.** Lo stesso piccolo modello, dichiarato in forme equivalenti,
produce riferimenti e mapping coerenti. I conflitti sono diagnosticati; un rename
non diventa implicitamente drop/create. UI parallela e inline danno la stessa
vista risolta. Il prototipo verifica i consumer, non soltanto la costruzione della Bag.

**Decisioni.** D-03, D-04, contratto D-05, forma minima D-06.
**Fuori fase.** Editor GUI completo, importatori universali, executor degli oggetti nativi.

## P2 — Importatori e fedeltà del modello

**Scopo.** Ottenere il modello comune da DB, dichiarazioni native e applicazioni legacy.

**Attività e risultati.**

- Importare da PostgreSQL tabelle, colonne, default, chiavi, indici e relazioni
  del profilo supportato; registrare gli oggetti riconosciuti ma non gestiti.
- Esportare dal runtime legacy inizializzato in ambiente controllato il modello
  effettivo dopo package/mixin/customizzazioni, conservando le informazioni disponibili.
- Segnalare callback, dipendenze e provenienze non serializzabili o non ricostruibili;
  non trasformare la loro assenza in una falsa equivalenza.
- Consentire overlay espliciti per UI e semantica che il DB non conserva; una
  reimportazione non deve cancellare contributi applicativi mantenuti separatamente.
- Confrontare i modelli risolti e le proiezioni fisiche dalle tre origini.
- Riprodurre #8 e #9 sulla versione scelta del migratore: correggere o bloccare
  la capacità interessata prima di usare quel percorso per migrazioni supportate.

**Accettazione.** Report di importazione con elementi fedeli, adattati e mancanti;
round-trip senza diff spurii per il sottoinsieme dichiarato. Nomi di indici,
ordinamento DESC e quoting sono verificati sul DB, non solo su stringhe generate.

**Decisioni.** Dettagli degli importatori entro D-03 e limiti del campione D-01/D-07.
**Fuori fase.** Ricostruzione automatica di intenzioni UI o Python assenti dal database.

## P3 — Prima prova verticale PostgreSQL read/write

**Scopo.** Dimostrare che il nuovo nucleo esegue operazioni reali end-to-end.

**Attività e risultati.**

- Implementare ingresso query minimo, resolver del modello, rappresentazione
  intermedia, binding parametri, emitter PostgreSQL e descrizione del risultato.
- Coprire proiezioni, filtri, ordinamento, paginazione minima e relazioni semplici,
  con alias e nomi fisici risolti centralmente.
- Implementare insert/update/delete, RETURNING, transazioni, rollback ed errori;
  definire proprietà delle connessioni e confini delle primitive SQL.
- Provare quote, stringhe, NULL, tipi e parametri ripetuti senza interpolare valori
  nell'SQL. Separare identificatori ed espressioni SQL dai parametri dati.
- Definire le dipendenze di compilazione e misurare costo, round-trip e risorse
  come baseline, prima di introdurre cache o ottimizzazioni.

**Accettazione.** Una fixture PostgreSQL percorre scrittura, lettura e rollback;
un errore intermedio non lascia operazioni parziali. Valori e metadati coincidono
con l'oracle indipendente per il profilo minimo. Nessuna promessa di copertura
dei contratti di dominio legacy deriva dal semplice successo delle primitive.

**Decisioni.** D-02, D-06 minimo e D-09 per le primitive.
**Fuori fase.** Compatibilità completa, record-cluster e hook di dominio completi.

## P4 — Semantica del compiler e virtualRelation

**Scopo.** Coprire la parte più delicata del linguaggio preservando cardinalità e scope.

**Attività e risultati.**

- Ampliare scanner/normalizzazione e resolver con SQL opaco, formule, parametri
  strutturali, sottoquery, macro e contesti di espansione documentati.
- Unificare gli ingressi testuale, Bag e strutturato sullo stesso motore semantico.
- Esplicitare granularità del risultato, join, EXISTS, aggregati, count e raccolte;
  mantenere duplicati legittimi, ordine richiesto e comportamento sugli insiemi vuoti.
- Implementare virtualRelation secondo il contratto GEP: binding fra sorgente
  e target, theta/filter, composizione, cicli, sola lettura, limite e cardinalità.
- Risolvere le questioni GEP ancora aperte prima di implementarne il comportamento;
  distinguere unicità garantita dal DB, cardinalità dichiarata e limit=1.
- Integrare scope e subtable senza trasformare filtri di LEFT JOIN in WHERE
  che eliminano le righe sorgenti.
- Rifiutare aggregateRows con diagnostica di migrazione. Verificare sostituzioni
  esplicite senza ricomposizione/deduplicazione Python nascosta.
- Propagare metadati dei risultati derivati senza inventare una colonna fisica
  o ereditare automaticamente una validazione non più applicabile.

**Accettazione.** Corpus eseguibile con SQL, binding, valori, cardinalità, ordine,
NULL e metadati controllati. L'equivalenza con il legacy si applica solo ai casi
classificati come equivalenza; nuovi contratti e correzioni hanno oracle propri.

**Decisioni.** D-08, estensioni D-06, risoluzioni puntuali D-07.
**Fuori fase.** Emulazione aggregateRows e ottimizzazioni che cambiano i risultati.

## P5 — Bridge legacy e scritture di dominio

**Scopo.** Usare il nucleo nuovo in un'applicazione reale con un profilo dichiarato.

**Attività e risultati.**

- Fornire mixin/adattatori per gli ingressi e i consumer scelti: query, record,
  selection, Bag e risultati; mantenere il motore semantico nel nucleo comune.
- Integrare formule/provider e metadati UI con un consumer reale, verificando
  contesti form/grid/filter e colonne derivate.
- Definire e implementare i contratti scelti per hook, record-cluster,
  validazioni, concorrenza, cancellazione logica e bulk.
- Separare policy di lettura da autorizzazioni/regole di scrittura. Dichiarare
  quali hook scattano per ogni operazione e chi possiede la transazione.
- Migrare gli usi di aggregateRows del campione alle forme esplicite e
  confrontare il significato applicativo, non soltanto la forma dei risultati.
- Predisporre adozione e ritorno al percorso precedente a livello di applicazione,
  senza due transaction manager sullo stesso flusso e senza fallback silenziosi
  che eludano il contratto scelto.

**Accettazione.** Scenari applicativi completi su dati di prova: letture, scritture,
errore intermedio, conflitto concorrente e rollback. Ogni eccezione al profilo
ha diagnostica e percorso documentato. Nessun residuo aggregateRows nel bridge.

**Decisioni.** D-07 definitivo per il profilo, D-09 dominio, integrazione D-05.
**Fuori fase.** Copertura di ogni applicazione legacy e ogni possibile callback.

## P6 — Prestazioni e ciclo di vita delle risorse

**Scopo.** Migliorare costi misurati senza indebolire i contratti semantici.

**Attività e risultati.**

- Confrontare baseline e implementazione su distribuzioni realistiche e casi
  difficili: fan-out, alta selettività, molti NULL, pochi/molti gruppi e pagine profonde.
- Misurare compilazione, query count, tempo DB, latenza complessiva/p95 e memoria;
  separare avvio a freddo, cache calda ed effetto della cache del server.
- Valutare cache di compilazione dipendente da modello, dialetto e contesto
  strutturale; controllare invalidazione e isolamento tenant, senza assumere
  necessaria una cache dei dati di risultato.
- Verificare streaming, chiusura anticipata, eccezioni, pool e durata della
  transazione. Dichiarare supporto sync/async effettivo.
- Valutare batch, raccolte esplicite, eliminazione di N+1 e keyset pagination
  quando applicabili al contratto e all'ordine richiesto.

**Accettazione.** Report riproducibile con soglie concordate D-10; correttezza
prima/dopo invariata. Nessuna perdita di connessioni o cursori nei percorsi
di errore e nessuna contaminazione fra contesti nelle cache.

**Decisioni.** D-10 prima dell'ottimizzazione; eventuali ampliamenti D-02/D-09.
**Fuori fase.** Promesse generiche di velocità e benchmark senza carico rappresentativo.

## P7 — Estensione futura: oggetti nativi e partizioni fisiche

**Scopo.** Estendere modello e sqlmigration a view, funzioni, trigger e storage partizionato.

**Attività e risultati.**

- Definire identità, firma, corpo, dipendenze, proprietà e gestione degli oggetti;
  distinguere oggetti gestiti, esterni e non supportati.
- Estendere introspezione, diff, pianificazione e applicazione delle migrazioni,
  incluse differenze fra CREATE/REPLACE, ALTER e drop/recreate.
- Pianificare dipendenze fra tabelle, view, funzioni e trigger; diagnosticare
  operazioni distruttive e limiti di reversibilità invece di promettere rollback universale.
- Definire convivenza fra trigger DB e hook Python: ordine osservabile, transazione,
  effetti eseguiti una volta, bypass tramite SQL diretto e bulk.
- Supportare le strategie PostgreSQL di partizionamento scelte con chiavi,
  bounds, partizioni, attach/detach e vincoli; misurare lock e impatto operativo.
- Integrare schema/prefisso e quoting anche nei riferimenti interni agli oggetti;
  preservare oggetti estranei al perimetro gestito.

**Accettazione.** Round-trip dei cataloghi, diff idempotente e applicazione
su database di prova con dipendenze reali; test di errore e ripartenza. Le
capacità non implementate restano esplicite, senza handler che dichiarano successo
senza effetto. Le partizioni fisiche non cambiano il significato degli scope logici.

**Decisioni.** D-11, eventuali requisiti aggiuntivi D-02/D-09.
**Fuori fase.** Obbligo di completare questa estensione prima del primo rilascio.
Le correzioni di base #8/#9 del migratore non sono rinviate a P7.

## P8 — Capacità, ulteriori dialetti e rilascio

**Scopo.** Pubblicare un insieme di contratti comprensibile e riproducibile.

**Attività e risultati.**

- Definire la matrice delle capacità per versione/dialetto: lettura, scrittura,
  migrazione, tipi, macro ed estensioni. Errore esplicito per operazioni non supportate.
- Portare il sottoinsieme scelto sugli altri dialetti, con test reali dei percorsi
  dichiarati. La generazione di una stringa SQL non certifica supporto runtime.
- Versionare modello, API e bridge; fornire guida di importazione, migrazione,
  rimozione aggregateRows, anomalie corrette e limiti residui.
- Rendere riproducibili dipendenze, installazione, test e dataset; aggiornare
  i minimi dell'ecosistema Genro secondo le versioni stabili verificate al momento.
- Documentare primo profilo di rilascio e percorso di estensione, inclusa P7
  quando sarà pronta. Non presentare le funzionalità prospettiche come disponibili.

**Accettazione.** Installazione pulita e suite del profilo riuscite; nessun
fallimento noto mascherato da capacità pienamente supportata. Le esclusioni sono
visibili nella matrice e le regressioni del campione sono riproducibili.

**Decisioni.** D-12 e revisione del profilo D-07.
**Fuori fase.** Parità indiscriminata fra tutti i dialetti.

## Tracciabilità obiettivi → finding → fasi → verifiche

I prefissi dei casi rimandano al [corpus di conformità](../compiler/compatibility-cases.md).
Le verifiche runtime, di importazione e prestazione ancora prive di un caso
numerato devono diventare test durante la fase indicata; questa tabella non
ne dichiara l'esistenza o il superamento.

| Obiettivo | Finding principali | Fasi | Evidenza di accettazione da produrre |
|---|---|---|---|
| O-01 Autonomia | F-M01, F-C02, F-R01 | P1, P3, P8 | Installazione e query/DML senza dipendenza obbligatoria dal runtime legacy. |
| O-02 PostgreSQL | F-R01–F-R04 | P3, P5, P8 | Esecuzione read/write, tipi, RETURNING, transazioni e rollback. |
| O-03 Altri dialetti | F-R03, F-G06 | P8 | Matrice capacità ed esecuzione reale del sottoinsieme dichiarato. |
| O-04 Modello da DB | F-M11, F-G01, F-G10 | P2 | Importazione e round-trip fisico; report informazioni assenti. |
| O-05 Modello da legacy | F-M06, F-M12, F-M13 | P2, P5 | Confronto modello runtime, overlay e provider del campione. |
| O-06 Modello nativo | F-M02–F-M08 | P1, P2 | Composizione, conflitti, serializzazione e consumer della grammatica. |
| O-07 UI | F-M09, F-M10, F-C19 | P1, P4, P5 | U01–U09 e consumer GUI/headless. |
| O-08 Nomi | F-M14, F-G04 | P1–P3, P7 | NM01–NM06, quoting e naming nel diff. |
| O-09 Compiler/bridge | F-C01–F-C11, F-C14–F-C19 | P0, P3–P5 | Corpus legacy classificato, anomalie deliberate e consumer reali. |
| O-10 Rimozione aggregateRows | F-C12, F-C13 | P0, P4, P5 | C37–C39, L26 e migrazione dei call site del campione. |
| O-11 VirtualRelation | F-M19, F-M20, F-C20, F-C21 | P1, P4 | VR01–VR08, binding, cardinalità, ordine e scope EXISTS. |
| O-12 Subtable/scope | F-M15–F-M18, F-R04 | P1, P2, P4, P5 | SP01–SP09, inclusi contesti e differenza fra letture/scritture. |
| O-13 Scritture di dominio | F-R02, F-R04, F-R06, F-R07 | P3, P5 | Hook, cluster, concorrenza, bulk e rollback applicativo. |
| O-14 Oggetti nativi | F-G06–F-G10, F-R07 | P1, P7 | DB01–DB06, cataloghi e dipendenze; convivenza Python/DB. |
| O-15 Migrazioni | F-G01–F-G10 | P1–P3, P7, P8 | Issue #8/#9, diff idempotente e protezione oggetti esterni. |
| O-16 Sintassi | F-C01, F-C17, F-C20, F-C21 | P1, P3, P4 | Esempi equivalenti dei frontend e diagnostiche sui casi ambigui. |
| O-17 Prestazioni | F-C22, F-R05, F-R08–F-R10 | P3, P6 | Benchmark riproducibili, correttezza e gestione risorse. |
| O-18 Adozione/diagnostica | F-M13, F-C03, F-C04, F-G05 | P0, P2, P5, P8 | Provenienza, errori contestuali, profili e guida di migrazione. |

## Rischi che determinano l'ordine del lavoro

1. **Modello incompleto:** partire dall'emitter SQL rende costoso integrare poi
   UI, provenance e naming. P1 deve fissare i contratti minimi, senza costruire
   ogni estensione prima di ottenere la prova verticale P3.
2. **Falsa compatibilità:** SQL valido e snapshot identici non garantiscono
   cardinalità, NULL, alias e contratti applicativi. P0 classifica i casi;
   P4/P5 verificano risultati e consumer.
3. **Importazione troppo promettente:** il DB non conserva tutta la semantica
   e il modello legacy risolto non conserva necessariamente tutte le provenienze.
   P2 deve produrre un report delle perdite, non nasconderle.
4. **Scritture sottostimate:** primitive SQL corrette non bastano per hook,
   cluster, scope e concorrenza. P5 è un gate distinto dalla prova P3.
5. **Migrazioni considerate equivalenti al modello:** dichiarare un oggetto
   non implica saperlo introspezionare, confrontare e applicare. Le capacità
   del migratore devono essere verificate separatamente in P2/P7.
6. **Ottimizzazione prematura:** cache e riscritture possono contaminare contesti
   o cambiare granularità. Si raccolgono misure in P3 ma si ottimizza dopo il corpus.

Non si assegnano tempi a priori: mancano ancora campione reale, profilo legacy
e soglie prestazionali. Dopo P0/P1 si potrà stimare la prima consegna, separando
il percorso essenziale PostgreSQL dalle estensioni e dagli altri dialetti.
