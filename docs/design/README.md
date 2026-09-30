# Asqueel moderno — dossier di analisi e progettazione

Stesura: 29 settembre 2026. Il dossier separa osservazioni sul software,
requisiti acquisiti e proposte. Non avvia un'implementazione né una migrazione.

## Revisione corrente

La [consegna 23](23-cli-and-named-configurations.md) aggiunge CLI, registro
`~/.asqueel`, sezione connection con EnvResolver e console Python. Il percorso
configurazione → creazione DB → query/scritture → piano vuoto è verificato su
PostgreSQL. SQLite resta richiesto; si riuseranno i suoi adapter di migrazione.

Il [compito collaterale 22](22-legacy-package-translation.md) avvia lo studio
della traduzione di package Genropy in dichiarazioni Python del modello nuovo.
Configurazione ed equivalente Pythonico del package restano scelte aperte;
la priorità principale resta sulle funzionalità DB.

Il [riesame degli errori Python 20](20-python-error-lifecycle.md) confronta hook
e callback con il legacy su PostgreSQL, registra le differenze di retry/rollback
e corregge difetti nativi di attribuzione e cleanup. Il controllo dei chiamanti
conferma che il salvataggio legacy normale non committa in presenza di errori;
il [riesame dei chiamanti 21](21-recovery-callers.md) verifica nove scenari per
backend di recupero esplicito e identifica il rischio del logger senza rollback.
La protezione nativa resta invariata; retry delle callback e altri percorsi
applicativi delimitati nel riesame restano aperti.
F1 rimane aperta, anche per il completamento della localizzazione.

La [consegna F1 — sessioni](17-f1-sessions-delivery.md) introduce connessioni
nominate persistenti, rollback SQL automatico e currentEnv/tempEnv applicativi.
Include oracle legacy su PostgreSQL e 532 test superati; distingue ciò che resta
aperto, in particolare localizzazione completa e code pending F4.

Il [piano operativo 15](15-operational-plan.md) traduce l’audit in fasi F0–F10,
dipendenze, criteri di accettazione e traguardi V1–V4. È pianificazione,
non avvio dell’implementazione.

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
