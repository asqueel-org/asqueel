# Asqueel moderno — dossier di analisi e progettazione

**16 ottobre 2026 — percorso unico delle letture nel worktree dedicato:**
[Rapporto 98](98-single-read-path.md). Gli ingressi operativi usano DbModel e
QueryCompiler gerarchico; eliminati il vecchio compilatore, QueryPlan/Fragment e
le copie SqlColumn/SqlRelation. Record e lock verificati su SQLite/PostgreSQL.
**3.200 test passati, 8 skip nel perimetro letture**. Le scritture restano al
lavoro separato; questo risultato non dichiara verde la suite generale.

**Aggiornamento 15 ottobre 2026 — campi condivisi dalle options verificati:**
[Rapporto 94](94-shared-option-fields.md). Le 12 differenze d'ordine sono accettate;
non richiedono riallineamento. Verificati tipo, attributi, relazioni e unicità dei
campi condivisi, incluso `invc.product_group._row_count`. **366 test passati**
nel gruppo mirato, inclusi 19 nuovi contratti e le verifiche sui 74 modelli.
Nessuna modifica alla produzione; aggiunti test e documentazione.

**Aggiornamento 15 ottobre 2026 — options prima delle dichiarazioni:**
[Rapporto 93](93-options-first-object-renderer.md). Il renderer gerarchico
consuma prima le options sulla copia privata della source, conservandole sugli
oggetti senza ripeterne gli effetti. Compilatore invariato. I due contratti `star`
ora passano senza xfail; 62/74 ordini fisici identici al legacy, 12 differenze
residue interne alle espansioni documentate separatamente. JSON migration
invariato sui 74 modelli. Le note successive conservano lo storico.

**Aggiornamento 15 ottobre 2026 — fetch e count eseguibili sul nuovo albero:**
[Rapporto 92](92-hierarchical-fetch-count.md). Terminali reali sul database
proprietario, righe Toolbox NamedList, ambiente corrente e transazione condivisa.
Count interpreta il risultato secondo il legacy; nessun handler verso molti.
Record, Selection e scritture gerarchiche restano fuori perimetro.
**5.147 test passati, 21 skip, 2 xfail preesistenti**. Ruff e Sphinx passano;
JSON migration invariato sui 74 modelli. Le note successive conservano lo storico.

**Aggiornamento 15 ottobre 2026 — count compilato sul nuovo albero:**
[Rapporto 91](91-legacy-tree-count.md). Stesso ramo legacy negli otto snapshot:
COUNT(*) per query semplici, chiavi di GROUP BY, proiezione conservata per
DISTINCT; ordinamento eliminato. SQL e kwargs senza esecuzione sul nuovo albero.
Nessun handler verso molti. **4.915 test passati, 21 skip, 2 xfail preesistenti**;
Ruff e Sphinx passano, JSON migration invariato sui 74 modelli. Le note successive
sono storiche.

**Stato corrente, 15 ottobre 2026 — fase 2 completata:**
[Rapporto 88](88-legacy-rewrite-phase2.md), [piano 86](86-legacy-compiler-logical-phases.md).
Nuovo percorso con SqlCompiledQuery, relazioni verso uno e adapter; nessuna
dipendenza da QueryPlan/Fragment. Verso molti: riconoscimento di
`@relazione.operazione(...)`, lookup `getattr` di `many_*`, errore esplicito se
manca. Nessun handler implementato; niente exploding rows o DISTINCT implicito.
314 confronti SQL/kwargs equivalenti al legacy; 4.290 test della suite passati,
13 skip e 24 xfail previsti; altri 20 test di esecuzione sui due database e
4 contratti ON aggiunti e verificati. JSON migration invariato sui 74 modelli.
Ruff passa; mypy conserva due errori preesistenti del renderer precedente.
Prossimo passo: fase 3, formule e sottoquery. Le note successive sono storiche.

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

**Stato corrente, 14 ottobre 2026 — R3 completata:**
[rapporto 83](83-legacy-realignment-r3.md), [piano 79](79-legacy-compiler-realignment-plan.md).
Preparazione SQL/kwargs negli adapter secondo il legacy, senza I/O implicito.
Psycopg 3 usa l’espansione IN dell’adapter legacy postgres3, con protocollo nominato.
**3.918 test superati, 13 saltati**; 100 confronti sul riferimento, 24 verifiche
d’integrazione e 148 SELECT native senza differenze. Otto snapshot confrontati.
Il prossimo passo è R4, prima delle relazioni. Nomi generati, collisioni ed errori
affidati al driver mantengono i contratti legacy documentati nel rapporto.
Le note successive conservano lo storico dei passi precedenti.

**Stato corrente, 14 ottobre 2026 — R2 completata nel perimetro locale:**
[rapporto 82](82-legacy-realignment-r2.md), [piano 79](79-legacy-compiler-realignment-plan.md).
Proiezioni conservate come nel legacy ed embedFieldPars sul WHERE, senza nuove
sintassi. **3.791 test superati, 13 saltati**; quattro test legacy originali
superati, 624 confronti sugli otto snapshot e 148 SELECT native senza differenze.
Prossimo passo R3: preparazione negli adapter, poi R4 prima delle relazioni.
Le note successive conservano lo storico dei passi precedenti.

**Stato corrente — R1 completata, 14 ottobre 2026:**
[rapporto 81](81-legacy-realignment-r1.md). Ripristinati gli algoritmi legacy di
risoluzione sulla SELECT fisica del nuovo albero. **3.681 test superati, 13 saltati**.
Restano R2–R4 prima delle relazioni; le aggiunte non concordate sono escluse
dal raccordo, senza riproporle come decisioni. Le voci successive sono storiche.

Stesura: 29 settembre 2026. Il dossier separa osservazioni sul software,
requisiti acquisiti e proposte. Non avvia un'implementazione né una migrazione.

## Revisione corrente

**Delega legacy agli adapter confermata, 14 ottobre 2026:**
[piano 79 aggiornato](79-legacy-compiler-realignment-plan.md). Assemblaggio SQL
e preparazione dei parametri restano delegati come nel legacy; la preparazione
è separata dall'esecuzione. Nessuna modifica al core. Collisioni delle collection
da discutere negli adapter. M2/M3 chiuse: commenti e stringhe mantengono il
comportamento legacy, senza protezioni aggiuntive; codice ancora da riallineare.

**Contratti legacy fissati, 14 ottobre 2026:**
[rapporto 80 — R0](80-legacy-realignment-r0-contracts.md). Matrice completa dei
71 casi / 132 osservazioni, riferimenti ai test negli otto snapshot e conflitti
con i test Asqueel espliciti. 294 test Asqueel e 6 prove legacy compile-only
superati; compilatore invariato e miglioramenti ancora da decidere.

**Riallineamento del compilatore, 14 ottobre 2026:**
[piano 79](79-legacy-compiler-realignment-plan.md), basato sul
[confronto misurato 78](78-scanner-legacy-comparison.md). Recuperare gli algoritmi
e le compatibilità legacy prima di proseguire con relations; miglioramenti
discussi e decisi singolarmente prima dell'implementazione. Solo piano.

**SELECT minima sul nuovo albero, 14 ottobre 2026:**
[rapporto 77](77-hierarchical-minimal-select.md). Completate fasi 0 e 1 del piano 76:
query fisiche → SQL e kwargs senza I/O. Confronto legacy su otto snapshot e
parità delle proiezioni esplicite su 74 tabelle, PostgreSQL e SQLite.
Raccordo relations ancora da fare; mixin e RuntimeModel separati.

**Piano compilatore sul nuovo albero, 14 ottobre 2026:**
[piano 76](76-hierarchical-compiler-plan.md). Confrontati gli algoritmi legacy
e gli otto snapshot già esaminati; previsto il port della navigazione
getFieldAlias → _findRelationAlias → _getRelationAlias sul ramo relations,
con riuso verificato di piano SQL, dialetti e binding. Baseline, SELECT minima,
JOIN, formule, sottoquery, options/macro e accettazione sono passi separati.
Pianificazione iniziale; fasi 0 e 1 ora completate nel rapporto 77. Mixin, RuntimeModel e differenze
semantiche non concordate sono gate espliciti; nessuna nuova sintassi.

**JSON migration dal nuovo albero, 14 ottobre 2026:**
[rapporto 75](75-hierarchical-migration-json.md). I 74 modelli producono un JSON
identico al percorso precedente e all'oracolo fisico legacy nel perimetro ammesso:
789 colonne, 58 FK, 282 indici. Verificata applicazione PostgreSQL temporanea,
introspezione, seconda diff vuota ed evoluzione delle options. Fase 5 del piano 70
completata; compilatore e default invariati.

**Collegamento operativo del nuovo albero, 14 ottobre 2026:**
[rapporto 74](74-hierarchical-table-binding.md). DbTableObj crea e conserva
SqlTable in `.dbtable`; SqlDatabase può collegarsi al modello già costruito
e restituisce le medesime istanze. Colonne e relazioni restano nel modello.
Compilazione e scritture sul nuovo albero non abilitate; renderer corrente
ancora predefinito, mixin ancora aperti.

**Tabella e modello, 14 ottobre 2026:** confermata la separazione logica legacy,
con `.model` e fallback `SqlTable.__getattr__` per i membri mancanti.
Binding dei metodi preservato; scritture di attributi locali alla tabella.
Mixin e namespace restano aperti. Quel primo incremento aggiungeva soltanto il
fallback; il raccordo successivo a objects_tree è descritto nel rapporto 74.
[Decisione e perimetro](71-hierarchical-object-renderer.md#decisione-sul-collegamento-alla-tabella-operativa--14-ottobre-2026).

**Proxyclass legacy, 14 ottobre 2026:** [rapporto 73](73-legacy-proxyclasses.md).
Ricostruiti composizione, istanziazione, binding di self, fallback web e limiti
del passaggio attraverso i mixin delle tabelle. Quattro test originali e dodici
sonde superati; nessuna implementazione del meccanismo in Asqueel.

**Inventario del namespace tabella, 14 ottobre 2026:** [rapporto 72](72-table-namespace-inventory.md).
Censiti i membri delle classi legacy e degli oggetti effettivi di test_invoice_pg
per valutare unificazione e namespace model/triggers/logic. Nessuna decisione
architetturale acquisita e nessuna modifica al core in questo censimento.

**Renderer gerarchico alternativo, 14 ottobre 2026:** implementato il percorso
`objects_tree` usando la walk generica e costruendo gli oggetti in finalize.
Ramo globale relations e viste lazy confrontati con il legacy: 144 nodi
ordinari identici; 74 modelli, 789 colonne fisiche e 526 virtuali.
Il renderer corrente resta il default; compilatore ed esecuzione SQL non sono
raccordati al nuovo albero. La proiezione JSON è ora completata nel rapporto 75.
[Piano 70](70-hierarchical-object-renderer-plan.md) e
[rapporto 71](71-hierarchical-object-renderer.md) distinguono verifiche e limiti.
I risultati SQL precedenti non certificano fedeltà architetturale del compilatore.

**Priorità aggiornata, 14 ottobre 2026:** SELECT FROM SELECT e operatori fra
query sono rinviati per decisione dell’utente ([R-09](41-deferred-features.md#r-09--query-concatenate-e-operatori-fra-query)).
Il lavoro corrente riguarda il modello gerarchico alternativo; il compilatore resta separato.

**bagItemColumn e guide connessioni, 14 ottobre 2026:** [rapporto 69](69-native-bag-items.md).
Raccordo PostgreSQL con XPath parametrizzato, cast e tipi custom legacy;
3/3 colonne native compilano. Confrontati otto snapshot e portati 15 test legacy,
con prove aggiuntive su valori e isolamento dei parametri. SQLite non emulato.
Guide CLI/configurazione riallineate alle connessioni nominate già implementate.

Il [rapporto 68](68-named-list-fetch.md) raccorda fetch al NamedList pubblicato
in Toolbox 0.18.0: righe modificabili per nome/posizione su PostgreSQL e SQLite,
stesso contenitore per SQL diretto e RETURNING, record dict preservato.

Il [rapporto 67](67-native-subquery-methods.md) raccorda i riferimenti stringa
a subquery_* sulla tabella della SELECT corrente. Sette prove rieseguite sugli
otto compilatori legacy; RuntimeModel ancora separato, XML richiede il dict.

Il [rapporto 66](66-native-subquery-columns.md) raccorda subQueryColumn con query
dict: semplice su PostgreSQL/SQLite, JSON/XML su PostgreSQL, sette test legacy
superati e confronto degli otto riferimenti. Metodi di sottoquery ancora aperti.

Il [rapporto 65](65-native-options-and-star.md) chiude il passo 2: filtri nativi,
partition scalare concordata e `*` legacy; dati verificati sui 74 modelli.

Il [capitolo 64 — Macro del compilatore](64-compiler-macros.md) separa
supporto verificato, contratti ancora da valutare e funzionalità non portate.

Il [rapporto 63](63-native-inverse-relations.md) documenta le inverse ordinarie,
il confronto fra JOIN legacy e aggregazione sperimentale, e le cinque child_count sbloccate.

Il [rapporto 62](62-native-method-formulas.md) documenta le formule da metodo,
il confronto con RuntimeModel e il raccordo dei due metodi già richiesti da sys_fields.

Il [rapporto 61](61-native-subqueries.md) documenta il raccordo nativo
select/exists/select_*, con default legacy e mangler isolati.

Il [rapporto 60](60-native-sql-formulas.md) registra il primo raccordo delle
formule native: SQL, dipendenze, alias e var_*, con test portati dal legacy.

Il [rapporto 59](59-formula-legacy-baseline.md) registra il censimento e la
baseline delle formule su otto riferimenti legacy: esiti per branch, difetti
preesistenti, limiti delle fixture e confronto con le 526 virtuali native.

La [checklist 58 del compilatore](58-compiler-checklist.md) raccoglie capacità
disponibili, parti incomplete, decisioni aperte e rinvii. Stato corrente:
passo 1 del piano 56 chiuso. La priorità successivamente acquisita è portare
e superare i test legacy delle formule ora censiti; options native, filtri e `*`
sono ora raccordati nel perimetro del rapporto 65. Sintassi più amichevoli solo in seguito,
da discutere come affiancamento a quelle legacy.

**Ripresa dopo la release 0.6.0:** il percorso source → oggetti → migrations è
verificato sui 74 modelli nativi ([rapporto 53](53-native-invoice-render-and-migration.md)).
Si parte dalle letture con sintassi legacy, rinviando la grammatica Builder
delle clausole: [indagine SQL e kwargs](55-select-sql-and-kwargs-investigation.md).
Il [piano del compilatore 56](56-read-compiler-plan.md) dettaglia la sequenza
attuale e include UNION, UNION ALL, INTERSECT ed EXCEPT come nel branch legacy,
con prove PostgreSQL su riuso delle query, parametri e raggruppamenti.
Il passo 1 è completato: SQL/kwargs dalla query singola senza I/O, con
`#IN_RANGE` e `#PERIOD` derivati dal legacy e dal decoder Toolbox esistente.
Baseline storica del passo 1: 1350 passati, 1 saltato. Il passo 2 (filtri
nativi e `*`) è chiuso nel rapporto 65, con il limite pyColumn esplicitato.
Include anche `query(...).query(...)` come SELECT FROM SELECT, con join nel
livello esterno tramite le relazioni delle colonne proiettate (`@customer_id.name`).
Il [riesame 57](57-legacy-compiler-refactoring-review.md) confronta i refactor
legacy di febbraio e le conversazioni SQL archaeology con questo requisito.
Il [documento 54](54-query-recipe-and-sql-check.md) conserva le ipotesi precedenti
e la direzione del controllo finale SQL con SQLGlot, provato solo in isolamento.
Il [piano 44](44-core-release-plan.md) e i checkpoint precedenti restano
riferimenti storici; non certificano le operazioni trasferibili ancora da
implementare.

**Grammatica obiettivo completa:** la [specifica 42](42-configuration-grammar.md)
fissa firme, default, options, relazioni e proiezione migrations come proposta
concreta da revisionare. La [matrice 43](43-test-invoice-model-coverage.md)
usa tutti i package di `test_invoice_pg` (`sys`, `adm`, `invc`) come criterio
di accettazione, con censimento riproducibile. Non certifica il runtime.

**Decisioni del 12 ottobre 2026:** il
[contratto 40 — modello e ricette delle operazioni](40-model-and-operation-recipes.md)
aggiorna la struttura DB (schemi fisici, package e options), registra le ricette
trasferibili anche dal browser e distingue accordi e firme ancora proposte.
La sequenza acquisita è: definire il modello, verificare le migrations,
definire lettura/scrittura tramite ricette, compilazione ed esecuzione.

Il [registro 41 — funzionalità rinviate](41-deferred-features.md) raccoglie
le esclusioni temporanee esplicitamente concordate, a partire da `toolColumn`.

**Ripartenza del 12 ottobre 2026:** leggere prima il
[handoff Asqueel core](HANDOFF-asqueel-core.md), che distingue stato implementato,
decisioni sul modello e lavoro ancora aperto su compilatore/scritture/trigger.
L'incremento query del piano 30 è stato consegnato. Il quadro seguente conserva
la collocazione storica del dossier, non la sequenza operativa aggiornata.

Il [piano operativo 15](15-operational-plan.md) conserva il quadro generale;
per l'incremento letture corrente seguire il piano 56 sopra.
F1 è chiusa per il profilo sincrono: connessioni nominate per thread, environment,
recupero applicativo e callback sono verificati su PostgreSQL e SQLite. Il
[report 28](28-db-owned-connection-lifecycle.md) documenta la rimozione effettiva
di Session; il [report 27](27-f1-request-lifecycle-closure.md) registra i confronti legacy.
Il prossimo lavoro è il [piano query 30](30-query-completion-plan.md):
prerequisiti minimi F2 e incremento funzionale F3. F0 e F2–F10 restano aperte.
La [matrice 31](31-query-contract-matrix.md) registra prove legacy e Asqueel del
passo 1, contratti proposti e decisioni aperte su collezioni, DISTINCT, GROUP BY e count.

La [consegna 23](23-cli-and-named-configurations.md) documenta CLI, registro
`~/.asqueel` e configurazione. SQLite è disponibile nel profilo limitato
[documentato](../guide/sqlite.md), senza implicare parità fra backend.
Il [compito collaterale 22](22-legacy-package-translation.md) riguarda la futura
traduzione dei package; il bridge applicativo legacy non è implementato.
I report precedenti conservano evidenze e conteggi storici, non lo stato attuale.

L'[audit dei test SQL legacy](13-legacy-test-audit.md) censisce 37 file e 968
definizioni sorgente, distingue prove reali, mock e casi non raccolti, e collega
42 contratti alla distanza dal prodotto attuale. La [proposta di tappe](14-legacy-target-and-stages.md)
definisce il traguardo e i criteri di accettazione senza introdurre nuove decisioni.
L'[indice analitico](evidence/legacy-sql-tests-index.md) rimanda a ogni test.

Le [formule correlate select/exists](12-correlated-formulas-delivery.md) estendono
il percorso con sottoquery nominate, correlazione #THIS, scope dei parametri e
prove tratte da dichiarazioni legacy reali. Il rapporto distingue la semantica
recuperata dalle differenze deliberate sulle partition e dai requisiti aperti.

Il [completamento aliasColumn](11-alias-columns-delivery.md) implementa il primo
gruppo di requisiti del riesame: ereditarietà dei metadati, risoluzione operativa,
percorsi legacy multi-hop e prove PostgreSQL. Descrive esplicitamente i limiti
ancora aperti e la prova mirata contro la classe originale legacy.

Il [riesame della copertura reale](10-legacy-coverage-reassessment.md) corregge
la valutazione del prodotto dopo la verifica di aliasColumn e delle altre
primitive legacy. Contiene una matrice delle lacune, prove riproducibili e nuove
priorità, con approfondimenti su [modello](10a-model-feature-audit.md),
[compiler](10b-compiler-feature-audit.md) e [runtime](10c-runtime-feature-audit.md).
La copertura dei test del nuovo codice non va confusa con conformità al legacy.

La [revisione dell'architettura a oggetti](09-legacy-object-api-review.md)
riesamina il prodotto implementato rispetto al legacy e alla configurazione
con grammatiche richiesta dall'utente. Comprende quattro approfondimenti:
[modello e oggetti](09a-legacy-object-model.md),
[query/record/selection](09b-legacy-query-record-lifecycle.md),
[sessioni e scritture](09c-legacy-session-write-lifecycle.md),
[Builders e rendering a oggetti](09d-builders-configuration-and-object-rendering.md).
È analisi interna, esclusa dalla documentazione pubblica Sphinx.

## Ordine di lettura

| Documento | Contenuto |
|---|---|
| [00 — Fonti, baseline e verifiche](00-sources-and-evidence.md) | Versioni analizzate, provenienza delle evidenze, limiti e criteri di lettura. |
| [01 — Finding: modello, importazione e UI](01-findings-model.md) | Struttura attuale, grammatiche, metadati, nomi, subtable, partizioni e importatori. |
| [02 — Finding: compiler e linguaggio](02-findings-compiler.md) | Pipeline, cardinalità, anomalie, macro, GEP e contratti di compatibilità. |
| [03 — Finding: runtime, scritture e migratore](03-findings-runtime-migrations.md) | Stato del prodotto, confini operativi, difetti del migratore e oggetti nativi. |
| [04 — Obiettivi e criteri di accettazione](04-objectives.md) | Requisiti dell'utente e risultati verificabili attesi. |
| [05 — Decisioni e questioni aperte](05-decisions.md) | Decisioni acquisite, raccomandazioni e scelte da chiudere al momento opportuno. |
| [06 — Piano di massima e tracciabilità](06-outline-plan.md) | Fasi, dipendenze, risultati, verifiche e collegamenti con finding/obiettivi. |
| [07 — Proposta di versioni e agenti](07-release-proposal.md) | Perimetro V1 da concordare, versioni successive e assegnazione progressiva agli agenti. |
| [08 — Compiti degli adapter dati](08-data-adapters-plan.md) | Confini compiler/dialetto/driver, rapporto con sqlmigration e piano di estrazione dalla V1. |

L’[implementazione V1 e le verifiche](../native-v1-delivery.md) documentano il
lavoro successivo a questa analisi, senza marcare concluso l’intero piano P0–P8.
L'[estrazione degli adapter dati](../data-adapters-delivery.md) documenta il
passaggio successivo, con compiler, dialetto e driver separati.

## Come usare il dossier

- I finding hanno ID `F-M`, `F-C`, `F-R`, `F-G` e un riferimento alle fonti.
  Un finding non è necessariamente un bug: può essere un contratto utile o un limite.
- Gli obiettivi `O-xx` distinguono il risultato richiesto dalle soluzioni suggerite.
- Le decisioni `D-xx` identificano questioni aperte. I vincoli acquisiti non
  vengono rimessi in discussione come se fossero semplici alternative.
- Le fasi `P0`–`P8` sono una sequenza proposta. La numerazione non rappresenta
  stato di avanzamento; nessuna fase è dichiarata completata dal dossier.

## Documenti tecnici di dettaglio

- [Specifica del frontend legacy](../compiler/legacy-compatible-spec.md):
  requisiti puntuali di sintassi, modello, parametri e risultati.
- [Corpus di conformità](../compiler/compatibility-cases.md): casi da implementare,
  dataset e risultati di riferimento; comprende anche contratti nativi nuovi.
- [Proposta architetturale estesa](../asqueel-target-architecture.md): esempi,
  alternative di sintassi, motivazioni e prospettiva degli oggetti nativi.
- [Analisi del legacy e delle conversazioni](../legacy-sql-compiler-analysis.md):
  ricostruzione storica delle intenzioni e dei diversi compiler.
- [Allineamento dell'ecosistema](../ecosystem-alignment.md): verifiche già
  effettuate sul package attuale, da non confondere con collaudi del futuro runtime.

Per gli obiettivi e le decisioni fa riferimento questo dossier; per la semantica
puntuale del legacy resta valida la specifica, con l'eccezione già decisa della
rimozione di aggregateRows. Gli esempi delle API nuove restano proposte.

Le nuove decisioni vanno aggiornate in obiettivi/decisioni e nei relativi casi
di accettazione. Le osservazioni storiche non vanno riscritte per farle coincidere
con l'obiettivo futuro: si aggiunge una nuova evidenza o si indica il superamento.

- [Ripresa e riesame del lifecycle interrotto](18-interrupted-lifecycle-review.md):
  provenienza della bozza, difetti riprodotti e prerequisiti di chiusura F1.

- [Correzioni al lifecycle deferred](19-deferred-lifecycle-fixes.md):
  comportamento verificato, confronto legacy e limiti residui di F1.

- [Adattamenti legacy](../adattamenti-legacy.md): comportamenti SQL portati,
  differenze del ciclo di scrittura e requisiti per l’integrazione Genropy.
