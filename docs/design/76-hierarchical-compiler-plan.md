# 76 — Piano di raccordo del compilatore al modello gerarchico

**Decisione corrente, 15 ottobre 2026 — piano per fasi legacy:**
[diagramma e piano 86](86-legacy-compiler-logical-phases.md).
La sostituzione di QueryPlan/Fragment comprende da subito la risoluzione delle
relazioni sul nuovo albero: la SELECT fisica da sola non valida l’architettura.
Contenitore equivalente a SqlCompiledQuery, clausole SQL e kwargs separati,
assemblaggio e preparazione agli adapter. Binding PostgreSQL invariato:
ClientCursor ritirato; il parametro tra apici è un errore d’uso e non un requisito.
Piano operativo in cinque fasi, con riferimenti legacy e prove di chiusura.
Obiettivo vincolante: reimplementazione chiara e leggibile dello stesso algoritmo,
senza variazioni non concordate; ricorsione e ordine delle operazioni preservati.
Fase 1 verificata nel [rapporto 87](87-legacy-rewrite-phase1-baseline.md):
144 test legacy passati e 2 skip, 148 SELECT fisiche equivalenti; censite
144 relazioni native. Sul nuovo albero il raccordo relazionale manca ancora.
Contratti e differenze fissati; compilatore invariato, fase 2 non iniziata.
Le note successive conservano lo storico dei passi precedenti.

**Stato corrente, 15 ottobre 2026 — renderer riallineato dopo R4:**
[rapporto 85](85-legacy-renderer-and-postgres-binding.md), [piano 79](79-legacy-compiler-realignment-plan.md).
Eliminate le scansioni dal renderer condiviso; assemblaggio e WHERE seguono il
legacy. **3.944 test passati, 13 saltati**, 148 SELECT fisiche e JSON migration
invariato. Scomparse le quattro differenze del renderer nel corpus R4.
Binding PostgreSQL invariato: proposta ClientCursor provata su otto SELECT,
da discutere prima dell’adozione. Collisione IN separata e invariata.
R5/relazioni non avviata. Misure aggiornate e limiti nel rapporto.
Le note successive conservano lo storico dei passi precedenti.

**Stato corrente, 15 ottobre 2026 — verifica R4 eseguita, accettazione aperta:**
[rapporto 84](84-legacy-realignment-r4.md), [piano 79](79-legacy-compiler-realignment-plan.md).
**3.918 test superati, 13 saltati**; 15 prove legacy, 148 SELECT fisiche e JSON
migration dei 74 modelli verificati. Confronto integrato sui tre compilatori:
82/84 casi eseguiti da entrambi con stessi risultati sul nuovo albero.
Restano la differenza di binding PostgreSQL, la collisione postgres3 già nota
e residui dello scanner nel renderer condiviso. SELECT ordinaria più rapida del
legacy; 100 proiezioni ripetute ancora 2,3–2,6 volte più lente. Nessuna modifica
agli algoritmi; R5/relazioni non avviata. Dettagli e misure nel rapporto.
Le note successive conservano lo storico dei passi precedenti.

**Aggiornamento R1–R3, 14 ottobre 2026:** [rapporto 81](81-legacy-realignment-r1.md)
[rapporto 82](82-legacy-realignment-r2.md) e [rapporto 83](83-legacy-realignment-r3.md).
Il nucleo della SELECT fisica usa ora raccolta, risoluzione e sostituzione legacy;
il riuso dello scanner descritto nella fase 1 sotto è superato. Prima delle
relazioni resta R4 del piano 79. Proiezioni, parametri simbolici locali e
preparazione negli adapter sono raccordati e verificati nei rispettivi perimetri. Nessuna aggiunta non concordata da riproporre.

**Priorità corretta, 14 ottobre 2026:** il [confronto 78](78-scanner-legacy-comparison.md)
ha mostrato incompatibilità e non giustifica il riuso automatico dello scanner.
Il [piano 79](79-legacy-compiler-realignment-plan.md) precede ora la fase 2:
ripristino degli algoritmi legacy, senza aggiunte non concordate.
Le fasi 0–1 sotto sono incrementi implementati, non una certificazione di parità.

**Delega agli adapter confermata:** il piano 79 conserva le responsabilità legacy
di `adapter.compileSql` e `adapter.prepareSqlText`, separando la preparazione
di SQL/kwargs dall'esecuzione. Restano anche le deleghe per quoting, alias e macro
durante la compilazione; il nucleo non gestisce casi specifici SQLite/PostgreSQL.

**Avanzamento, 14 ottobre 2026:** fasi 0 e 1 completate nel
[rapporto 77](77-hierarchical-minimal-select.md). SELECT fisica minima direttamente
sugli oggetti gerarchici; SQL e kwargs senza esecuzione. Fasi 2–6 ancora aperte.
Mixin e RuntimeModel rimangono separati. La descrizione di baseline sotto
fotografa lo stato precedente a questo incremento.

14 ottobre 2026. Piano richiesto dopo il [JSON migration gerarchico](75-hierarchical-migration-json.md).
**Solo indagine e pianificazione: nessun codice applicativo modificato e nessuna
nuova suite eseguita in questo passo.** Le fasi seguenti non sono implementate.

## Obiettivo e regola di riferimento

Ottenere `compiled.sql` e `dict(compiled.params)` da una query sulla SqlTable
collegata al nuovo DbModel. Il compilatore deve navigare gli oggetti gerarchici
e il ramo relations, senza ricostruire la source, riespandere options o convertirli
nei vecchi Table/Column/Relation di ResolvedModel.

La sintassi resta quella acquisita: query legacy, `$campo`, `@relazione.campo`,
AS, formule e dichiarazioni di sottoquery già presenti. Nessun nuovo builder,
flag pubblico, provider, registro di handler o grammatica delle espressioni.

**Il legacy prevale.** Una differenza del compilatore attuale non diventa una
decisione acquisita perché compare nei test o nei rapporti precedenti. Dove
la parità con il legacy contrasta con un comportamento attuale e non esiste
una decisione esplicita, prevale il legacy; chiedere solo per un impedimento concreto.
I branch sperimentali sono fonti da confrontare, non un pacchetto da importare.

Il vecchio percorso resta disponibile durante il raccordo. Il default del
renderer non cambia. Scritture e record restano esclusi dal nuovo percorso.
L'obiettivo qui è compilazione senza I/O; non si certificano fetch, elaborazione
Python delle righe o lifecycle applicativo attraverso il successo dei test SQL.

## Stato verificato e punti di accoppiamento

La baseline registrata dal rapporto 75 è **2.300 test superati, 13 saltati**.
I 74 modelli sono costruiti nel nuovo albero, con 789 colonne fisiche, 526 virtuali
e il ramo globale relations. SqlDatabase riusa le `.dbtable`; sul nuovo modello
la proprietà compiler rifiuta ancora l'accesso. Il JSON migration è verificato.

| Punto attuale | Perché richiede un raccordo |
| --- | --- |
| QueryCompiler.__init__ | Legge attributes/descrittori di ResolvedModel, risolve alias e valida RowPolicies; non può ricevere DbModel cambiando soltanto l'annotazione di tipo |
| _Context.table_ref, field, projection | Usano physical_name, key, columns unificato, is_virtual, identity e ui; nel nuovo albero ci sono sqlname/fullname, contenitori distinti e attributi della colonna |
| _Context.related | Legge Relation.target/columns/target_columns/kind; il legacy usa nodi Bag, joiner e cursore relazionale |
| formula_definition / formula_scope | Parte delle definizioni è già stata normalizzata in model.py; nel nuovo albero resta la dichiarazione originale tradotta, da leggere senza costruire un descrittore parallelo |
| subquery / #THIS | Devono conservare il modello e l'alias della riga proprietaria mentre cambiano radice SELECT e scope dei parametri |
| select_policies / native_partition_predicates | Gli oggetti options del nuovo albero hanno tag, nome del nodo e attributes, non il contratto Option.name/enabled del vecchio modello |
| SqlTable._sql_reasons | I due metodi di sistema enumerano attualmente columns con is_virtual; nel nuovo albero devono leggere virtual_columns, senza modificare le formule prodotte |
| SqlDatabase.compiler | Va collegato progressivamente al nuovo percorso dopo i relativi test; il blocco delle scritture deve rimanere distinto |

Non aggiungere proprietà fittizie agli oggetti solo per far sembrare DbModel un
ResolvedModel. Le differenze di lettura vanno isolate; SQL plan, dialetto e binding
restano riutilizzabili dopo averne verificato i contratti.

## Confronto degli algoritmi

Riletti gli otto snapshot locali già censiti. Riferimenti, righe e impronte AST
sono nelle [evidenze statiche](evidence/compiler-tree-plan/source-review.json).
I risultati storici delle suite sono nel [rapporto 59](59-formula-legacy-baseline.md):
non sono presentati come test rieseguiti oggi. I dettagli dei refactor restano
nel [rapporto 57](57-legacy-compiler-refactoring-review.md).

| Riferimento | Da riprendere o confrontare | Da non importare automaticamente |
| --- | --- | --- |
| Legacy fa35e5a | getFieldAlias → _findRelationAlias → _getRelationAlias; cursore relazionale, joiner O/M, chiavi composite, cache per percorso/alias, ricorsione alias/formule | Tutto il runtime delle righe, macro non portate e i rami legacy fuori perimetro |
| Compound 4c075f7 | Stessa separazione fra query compilata e stato di compilazione, utile per test di riuso | UNION e altri operatori, ancora rinviati |
| v2 68f35b9 | ColumnCompiler e AliasManager separano responsabilità; identità del percorso di JOIN | Aggregazione automatica dei many, conversione sottoquery→JOIN, segnaposto lazy; getFieldAlias ricopia ancora stato mutabile dal collaboratore |
| v3 67bba0e / merged 19da337 | _handleFormulaColumn, _preprocessFormula, _compiledSubQuery separano parti della compilazione | _condense_subqueries e deduplicazione per hash non dimostrano equivalenza per limiti, ordine e binding |
| v4 38d210c | Stessa distinzione delle formule; RuntimeModel e ripristino del contesto mostrano il requisito di modello effettivo coerente | normalize_subquery_dict modifica in-place e introduce join_to/join_from/join_condition; nessuna di queste firme viene acquisita |
| simplify 13b8918 | Accesso alle virtuali attraverso il modello completo e percorso alternativo | Il WIP non è una base già equivalente: i fallimenti storici su alias/campi restano controesempi |
| next 12cfdcc | Percorso alternativo e test di confronto con il compilatore originale | La copia separata non dimostra un nuovo algoritmo semanticamente completo |

Due differenze concrete da preservare nella valutazione:

1. Nel legacy la chiamata `sql_formula_<nome>(attr)` precede l'estrazione dei
   parametri `var_*`. v2/v4 li estraggono prima: seguire il legacy e i test già
   portati che consentono al metodo di aggiungere var_* e select_*.
2. Il legacy distingue alias di tabella, riferimenti alle colonne e parametri.
   Il mangling di alcuni branch usa id dell'oggetto e sostituzioni regex.
   Asqueel ha già Identifier/Parameter, scanner e _Bindings: il piano 79 richiede
   di verificarne il contratto rispetto al legacy, senza conservarlo automaticamente.
   Non far passare SQL già manglizzato in un secondo mangler né riutilizzare
   un allocatore di alias per i valori.

## Organizzazione prevista, senza nuove API

La parte da portare è la risoluzione semantica dei nomi e delle relazioni.
Il percorso deve rispettare: query → risoluzione sul modello e relation tree →
assemblaggio SQL delegato all'adapter → preparazione SQL/kwargs delegata secondo
il legacy, senza esecuzione. QueryPlan, dialetti e formatter già presenti sono
riutilizzabili nel raccordo se rispettano questo contratto; non costituiscono
una decisione di sostituire la delega legacy. QueryPlan non sostituisce il modello.

Separare nel codice le responsabilità che già esistono: lettura del modello,
navigazione e allocazione JOIN, espansione formule/sottoquery, parametri,
rendering del piano. Non fissare ora nomi di nuove classi o un framework di
adapter: ogni estrazione deve avere un uso concreto e test del comportamento
prima/dopo. Evitare sia un secondo monolite copiato dal legacy sia condizioni
distribuite in ogni metodo per simulare i vecchi descrittori.

Lo stato di compilazione appartiene alla singola chiamata. Nessun alias SQL,
parametro manglizzato, formula espansa o risultato di un metodo viene salvato
nel DbModel condiviso. La cache lazy strutturale di RelationTreeResolver rimane
distinta dalle cache della compilazione: materializzarla non significa scriverci
alias o stato SQL.

## Fase 0 — Contratti e baseline del raccordo

**Lavoro:** congelare la lista dei test da ripassare e classificare ogni caso:
copertura esistente da mantenere, divergenza esplicitamente concordata, punto
non deciso, funzionalità rinviata. Riutilizzare manifest e oracoli dei rapporti
59–69 e aggiungere i riferimenti alle funzioni effettivamente portate.

Confrontare query equivalenti su legacy e percorso attuale prima di usarle
come aspettativa del nuovo. Congelare cardinalità, NULL, valori dei parametri,
tipi e metadati di risultato, non soltanto la stringa SQL.

**Uscita:** matrice caso → riferimento → esito atteso → motivazione della
differenza. Nessun test indebolito, eliminato o marcato xfail per far avanzare
il nuovo percorso. Differenze non decise restano visibili e bloccano soltanto
la semantica interessata. La baseline non autorizza da sola i comportamenti.

## Fase 1 — SELECT minimale sul nuovo albero

**Lavoro:** raccordare l'ingresso del compilatore da SqlDatabase e leggere
DbTableObj/DbColumnObj direttamente. Cominciare da colonne fisiche, AS,
espressioni già ammesse, WHERE, ORDER BY e LIMIT/OFFSET già supportati, senza
relazioni o formule. L'incremento iniziale ha riutilizzato scanner, frammenti SQL,
QueryPlan, dialetti e formatter. Questa scelta è ora da riallineare secondo il
piano 79: il confronto di output e kwargs ha evidenziato compatibilità perse.

Questo è il **primo incremento implementativo proposto**. Non richiede mixin,
RuntimeModel o decisioni sulle relazioni many. I costrutti non ancora raccordati
devono fallire esplicitamente; niente ricorso nascosto al vecchio modello.

**Verifiche:** schemi/prefissi/nomi SQL, parametri con date/Decimal/NULL,
identificatori quotati, commenti/stringhe/cast protetti, valori mancanti,
riuso della query e nessuna connessione. PostgreSQL e SQLite per le capacità
comuni. `compiled.sql`, params e input_parameters coerenti con il contratto.

**Uscita:** una query sulla `.dbtable` del nuovo albero produce SELECT e kwargs;
nessuna ricostruzione del modello e nessuna apertura di connessione. Il default
precedente e il blocco delle scritture rimangono invariati.

## Fase 2 — Navigazione del ramo relations e JOIN ordinari

**Lavoro:** portare la sequenza legacy getFieldAlias/_findRelationAlias/
_getRelationAlias nel punto di risoluzione del compilatore:

1. partire da `table.relations`, con il suo cursore e l'alias SQL corrente;
2. leggere il nodo `@relazione` e il relativo joiner;
3. orientare sorgente/destinazione da mode O/M e many_relation/one_relation;
4. risolvere colonne e composite sugli oggetti, usando i loro nomi fisici;
5. costruire il LEFT JOIN nel piano e avanzare nel sottoalbero lazy;
6. riutilizzare il JOIN solo per lo stesso percorso nello stesso contesto.

Identità dei JOIN: mantenere i discriminanti legacy percorso/alias di partenza;
non unificare due percorsi perché arrivano alla stessa tabella. La chiave interna
può essere rappresentata diversamente solo con prove che conservino tali distinzioni.
Usare la medesima risoluzione in SELECT, WHERE, ORDER BY, GROUP BY e HAVING.

**Verifiche:** due FK verso la stessa tabella, ripetizione dello stesso percorso,
autoreferenze e cicli strutturali, attraversamento fra package, forward→inverse
e inverse→forward, chiavi composte, nomi fisici rimappati, target assente.
Separare la moltiplicazione delle righe da DISTINCT e aggregazione Python.

**Uscita:** navigazione ordinaria sul relation tree, con gli stessi oggetti del
modello, senza un elenco parallelo di Relation. Gli attributi speciali del joiner
non ancora raccordati restano esplicitamente non supportati, non ignorati.

## Fase 3 — Alias, formule SQL, var_* e metodi già disponibili

**Lavoro:** distinguere colonne fisiche, virtuali e composite dai contenitori
e dal tag. AliasColumnWrapper conserva attributi ereditati/override e origine:
non basta sostituire l'alias con il target perdendo nome, dtype o static.

Riutilizzare gli helper di normalizzazione già presenti (_formula_definition,
_subquery_definition, estrazione var_*), spostandoli in una responsabilità
condivisa soltanto se necessario. Nessuna ricostruzione di un Column descrittore.
Conservare dipendenze, rilevazione dei cicli, #THIS e valutazione per scope.

Per sql_formula=True cercare il metodo sulla SqlTable proprietaria del campo,
anche dopo un JOIN; copiare gli attributi, chiamare il metodo, poi leggere
select_* e var_*. Adeguare i due metodi sys_fields già presenti su SqlTable
all'enumerazione di virtual_columns; non aggiungere trigger o diagnostica.

**Limite esplicito:** il nuovo collegamento non applica x_table_class o mixin.
Il compilatore può invocare metodi già disponibili, ma questo piano non decide
come caricare contributi applicativi. Test con metodi installati esplicitamente
nella fixture provano il binding, non un sistema di mixin di produzione.
I casi che richiedono quel caricamento restano aperti fino alla relativa decisione.

**Verifiche:** SQL/alias annidati, cicli, proprietario di self, metodo assente,
mutazioni locali ad attr, parametri omonimi fra formule e fra alias della stessa
tabella. Cache per compilazione, valutazione nuova alla chiamata successiva.

## Fase 4 — Sottoquery native e famiglie di formula

**Lavoro:** portare select, exists, select_*, subQueryColumn e bagItemColumn
attraverso la stessa risoluzione del modello. Conservare i default legacy già
verificati: sottoquery senza pkey/ordine impliciti, include draft/deleted e
ignorePartition salvo dichiarazione contraria. Non trasformarle in JOIN.

Per i riferimenti stringa subquery_* il proprietario è la tabella radice della
SELECT corrente; per sql_formula_* è la tabella proprietaria della colonna.
La correlazione #THIS conserva il contesto/alias esterno corretto anche quando
esso deve aggiungere un JOIN. Le clausole locali restano nello scope locale.

**Alias, decisione acquisita nel piano 79:** usare il prefisso legacy
`aliasPrefix = '%s_t' % alias` dalla tabella proprietaria esterna: per esempio
`t0_t0`, `t0_t1`, oppure `t1_t0` se la proprietaria è `t1`. Ripetere la regola
negli annidamenti; il prefisso non proviene da `_Bindings.namespace` né dal
contatore dei parametri. Le sottoquery sorelle rispettano gli scope legacy,
senza inventare un vincolo di unicità globale degli alias.

Parametri: _Bindings resta il riferimento da verificare. Un allocatore della
singola compilazione evita collisioni; origine e visibilità dei valori restano
separate fra query, formule e sottoquery. Il formatter del driver viene applicato
al prodotto finale, senza sostituzioni testuali su SQL già preparato.

**Verifiche:** sottoquery sorelle e annidate con parametri omonimi, stesso
dizionario riutilizzato, correlazioni via @, NULL, EXISTS, errore di cardinalità
scalare; prefissi dalla proprietaria effettiva e alias invariati cambiando soltanto
i nomi dei parametri. JSON/XML su PostgreSQL e bagItemColumn conservano le capacità e i rifiuti
SQLite esistenti. Niente aggregatore implicito, nuova sintassi o variante XML.

## Fase 5 — Options di lettura, wildcard e macro

**Options:** leggere attributi e nodi già espansi del nuovo albero; non eseguire
di nuovo sys_fields o altre options. Portare filtri draft/logical deletion e
partition nel perimetro concordato. Per partition vale il valore corrente
scalare: uguaglianza se presente, nessun filtro se assente e non required,
errore se assente e required; ignorePartition disattiva il filtro.
Nessuna nuova convenzione current_/allowed_ o chiave d'ambiente.

**Wildcard:** fisiche in ordine del modello, virtuali statiche, regola bagFields
già verificata. Non omettere silenziosamente una statica non compilabile.
Composites e pyColumn non diventano colonne SQL scalari per comodità.

**Macro, capitolo distinto:** [stato e contratti nel rapporto 64](64-compiler-macros.md).
Raccordare soltanto #IN_RANGE, #PERIOD, #THIS e #nome delle select_nome già
supportate, rispettando i contesti ammessi da ciascuna. Preservare :env_nome
come parametro distinto da #ENV. Nessuna riesecuzione dei resolver strutturali
alla compilazione: usare i valori renderizzati e lo snapshot dell'ambiente query.

**Verifiche:** tutte le clausole ammesse, scope annidati, input generati dalle
macro in collisione con parametri espliciti, cambio ambiente fra compilazioni,
immutabilità delle dichiarazioni e stessa query riutilizzata in thread distinti.

## Fase 6 — Accettazione e confronto completo

Eseguire i test portati dai rapporti 60–69 sul nuovo ingresso, oltre alla
regressione del percorso precedente. Mantenere i manifest di provenienza legacy.
Per ogni famiglia: prova di compilazione senza I/O e, separatamente, prova
dei risultati su database temporaneo quando necessaria per cardinalità/NULL.

Censire tutte le colonne dei 74 modelli per famiglia: successo, rinvio già
deciso, dipendenza ancora aperta o regressione. Non dichiarare «74 modelli
compilabili» perché passano solo le SELECT sulle colonne fisiche, e non usare
il successo del JSON migration come prova del compilatore.

Confrontare SQL, valori/tipi dei kwargs e metadati. Eventuali differenze di
alias interni o placeholder vanno rese esplicite con una corrispondenza biunivoca;
non normalizzare predicati, valori, JOIN, ordine o cardinalità per nascondere
differenze. L'esecuzione comparata completa il controllo semantico.

Verificare che nessuna chiamata a resolve_model/prepare_source/expand_options,
bridge legacy o connessione avvenga durante compile. Verificare stabilità del
JSON migration e degli oggetti prima/dopo compilazioni ripetute.

Controlli di costo mirati: contare visite ai percorsi e JOIN duplicati su query
con riferimenti ripetuti, controllare che l'albero lazy non venga espanso tutto.
Nessuna cache globale sul modello o ottimizzazione speculativa per ottenere
un benchmark migliore. Suite completa, Ruff, mypy e documentazione aggiornata.

**Uscita:** copertura del perimetro deliberato documentata caso per caso. Le
decisioni ancora aperte non diventano successi; il passaggio del default e la
rimozione del vecchio percorso richiedono una successiva revisione esplicita.

## Decisioni da non prendere implicitamente

1. **Many e default legacy:** DISTINCT implicito, exploding rows, pkey nascoste,
   aggregazione dei risultati e count. Il rapporto 63 descrive la divergenza
   attuale, non prova un'autorizzazione generale a conservarla. Preparare esempi
   minimi con/senza DISTINCT e chiedere prima di cambiare la semantica.
2. **JOIN oltre il caso ordinario:** controlli di unicità, case_insensitive
   (legacy confronta 'Y'), chiavi virtuali/weak su formule, cnd/join_on/between,
   ignore_tenant e condizioni aggiuntive. Classificare contro firme e decisioni
   acquisite; non abilitare tutto perché i dati sono conservati nel joiner.
3. **Metodi applicativi:** composizione, precedenze e override dei mixin restano
   una decisione propria. Non trasformare x_table_class, proxy o __init_subclass__
   nella soluzione definitiva dentro il raccordo del compilatore.
4. **RuntimeModel:** il compilatore e i metodi che leggono self.model devono
   vedere lo stesso modello effettivo. Le cache locali e la separazione fra
   struttura/stato SQL preparano quel requisito, ma non implementano un overlay.
   Non basta cambiare compiler.model; nessuna API RuntimeModel viene fissata qui.

Questi punti non bloccano la SELECT minima. I gate interessati devono però
mostrarli prima di dichiarare la parità completa.

Restano rinviati: query concatenate, operatori UNION/INTERSECT/EXCEPT, esecuzione
pyColumn, #PREF, system_records, locked_record e diagnostica fuori perimetro.
Le virtualRelation GEP restano dichiarazioni: ask/var_* non autorizzano ora
nuova compilazione; inverse automatiche, limit/order_by e one_one sulle virtuali
restano esclusi. Non si aggiungono #ENV, BAG/BAGCOLS, macro full-text/vettoriali,
varianti, SQLGlot nel core, LATERAL, aggregazione automatica dei many o fusione
delle sottoquery come conseguenza di questo piano.
