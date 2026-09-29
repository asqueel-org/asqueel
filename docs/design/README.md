# Genro SQL moderno — dossier di analisi e progettazione

Stesura: 29 settembre 2026. Il dossier separa osservazioni sul software,
requisiti acquisiti e proposte. Non avvia un'implementazione né una migrazione.

## Revisione corrente

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
- [Proposta architetturale estesa](../genro-sql-target-architecture.md): esempi,
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
