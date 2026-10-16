# 103 — Primo handler aggr: count e aggregati numerici

16 ottobre 2026. Implementazione del primo perimetro approvato in
[101](101-many-aggregation-decisions.md), verificato dai
[contratti 102](102-many-aggregation-contracts.md).

## Funzionalità

Sono compilate le proiezioni `.aggr(count(), sum(...), avg(...), min(...), max(...))`.
Ogni argomento numerico produce una colonna indipendente, con alias esplicito
oppure automatico. Per alias uguali prevale l'ultima dichiarazione, usando il
dizionario ordinato delle proiezioni già portato dal legacy.

```text
@invoices.aggr(count(), sum($total AS total_sum, $qty AS quantity_sum))
@invoices.aggr(sum($total * $qty) AS amount, avg($adjusted) AS adjusted_mean)
@invoices.aggr(sum(@vat_id.rate) AS taxes)
```

Gli argomenti possono contenere formule, dipendenze di formule, `var_*`, alias
colonna, riferimenti verso uno ed espressioni SQL già ammesse. Senza righe
correlate count restituisce 0 e gli altri aggregati NULL. La cardinalità della
query esterna rimane invariata.

Le virtualRelation basate su una relazione ordinaria verso molti supportano
la condizione semplice e `var_*` come espressioni della riga sorgente. La
risoluzione legge la dichiarazione conservata nell'albero e il joiner esistente;
non modifica la source, il renderer o il registro delle relazioni.

## Algoritmi riusati

Riferimenti riesaminati: ramo `select_dict` di `getFieldAlias` in
`fa35e5ad` e `_compiled_sub_query` dello snapshot sperimentale v2 già censito
nel [rapporto 89](89-legacy-rewrite-phase3.md). Il primo risolve `#THIS` nel
padre e compila ricorsivamente la SELECT figlia; il secondo distingue
esplicitamente il prefisso degli alias SQL dal mangler dei parametri.

| Compito | Implementazione riusata |
| --- | --- |
| Separare argomenti e `AS` fuori dalle parentesi | `split_sql`, port di `gnrstring.split` |
| Nomi automatici | `col_to_as` e `as_translator` dell'adapter |
| Alias duplicati: ultima dichiarazione | `projection_columns`, invariato |
| Percorsi verso uno prima della many | `_find_relation_alias` / `_get_relation_alias` |
| Correlazione con la riga esterna | joiner many/one e sostituzione `#THIS` di `subquery` |
| Formule, alias, relazioni e macro nelle espressioni | `FieldReferences` / `get_field_alias` / `formula` |
| SELECT figlia e SQL finale | `subquery` → nuovo `_TreeContext` → `select_plan` → adapter |
| Parametri locali e del chiamante | `SqlBindings.child`, invariato; preparazione driver una sola volta |

La parte nuova è limitata al riconoscimento degli aggregati approvati e al
raccordo della relazione con quel percorso. `_numeric_aggregates.py` restituisce
espressioni scalari e nomi; non risolve campi né compila SQL per un dialetto.

Gli aggregati sono registrati nel contesto locale e risolti insieme ai
riferimenti della proiezione. In questo modo SQL e parametri delle sottoquery
non attraversano di nuovo la raccolta dei campi e il mangler esterni. Non
vengono introdotti AST, QueryPlan, Fragment o descrittori del modello paralleli.

Si produce **una sottoquery scalare correlata per colonna risultante**. È il
riuso diretto del percorso esistente, comune a PostgreSQL e SQLite. Non si
introducono LATERAL, fusione delle sottoquery, hash di deduplicazione, JOIN
che esplodono le righe o DISTINCT impliciti. Il costo di più sottoquery resta
visibile; non sono rivendicati miglioramenti di prestazioni non misurati.

Le SELECT aggregate numeriche non richiedono l'ordinamento delle righe interne;
riusano il comportamento delle sottoquery legacy che ignora l'ordine di tabella.
La catena esplicita `.order_by(...).aggr(...)` resta al passo degli aggregati
sensibili all'ordine: non viene accettata e poi ignorata.

## Verifiche

La suite delle aggregazioni sui due dialetti, compreso il catalogo Bag opzionale,
restituisce **91 passed, 34 xfailed, 5 skipped**. Dei contratti della baseline,
58 relativi a count/numerici passano ora; passa anche il rifiuto esplicito
`to_xml` su SQLite. I nuovi controlli verificano parametri distinti della stessa
famiglia di formule, riuso della query, modello invariato e nessuna estensione
implicita della tupla a espressioni o clausole non approvate.

Gli xfail rimanenti riguardano join, JSON/XML e ordinamento esplicito: restano
rigorosi. Il [rapporto 102](102-many-aggregation-contracts.md) e la sua evidenza
conservano la baseline precedente, senza riscriverla.

Le regressioni mirate di relazioni, formule e star danno **386 passed,
2 deselected** (il test DML escluso sui due dialetti). La suite completa delle
letture, con il manifesto di esclusione delle scritture già concordato, dà
**4349 passed, 21 skipped, 16 deselected, 34 xfailed** in 190,69 secondi.
Gli skip comprendono i round-trip che richiedono il catalogo GenroPy opzionale,
verificati invece nella suite dedicata. Mypy passa su 58 file; Ruff e
`git diff --check` passano. Risultati e casi sono nell'
[evidenza della fase numerica](evidence/many-aggregation-contracts/numeric.json).

## Limiti mantenuti

- `join`, `to_json`, `to_xml`, `.order_by(...)` non sono implementati in questo
  passo. SQLite continua a rifiutare `to_xml`; nessun fallback.
- `aggr` è una proiezione: non viene trasformata implicitamente in un valore
  scalare utilizzabile in WHERE/COALESCE, né si applica un solo `AS` a più risultati.
- Ask, derivazioni fra virtualRelation e forma diretta `table=` non ricevono
  semantiche nuove. I casi non raccordati sono rifiutati esplicitamente.
- Le many con condizioni di join speciali `join_on`/`cnd`/`between` non sono
  assimilate silenziosamente alle relazioni per uguaglianza.
- Nessun intervento su scritture, runtime delle scritture o loro API condivise.
