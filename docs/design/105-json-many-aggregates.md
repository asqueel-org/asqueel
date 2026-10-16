# 105 — to_json sulle relazioni verso molti

**Aggiornamento successivo:** nel [passo 107](107-outer-as-projections.md),
CAST senza AS esterno riceve il nome dal flattener, comune a SELECT/JSON/XML.
Il testo e i risultati sotto documentano il passo JSON precedente.

16 ottobre 2026. Implementazione del contratto JSON approvato in
[101](101-many-aggregation-decisions.md), dopo
[join e ordinamento](104-join-ordered-many-aggregates.md).

## Risultato

```text
@invoices.aggr(to_json())
@invoices.order_by('$qty DESC, $id').aggr(
    join($code, ',', '-') AS codes,
    to_json($id AS number, $double_total, @vat_id.rate AS rate) AS invoices
)
```

`to_json` produce in SQL un array di oggetti. Le colonne e i nomi dei campi
seguono la proiezione della query; l'AS esterno nomina la colonna contenente
l'array. Senza argomenti si usa `*`, comprese le colonne statiche già espanse
dalla query. L'alias automatico senza argomenti resta `_invoices_json`.

Colonne fisiche, formule, alias colonna, relazioni verso uno, espressioni e
parametri passano dalla SELECT figlia esistente. Gli alias duplicati conservano
la regola dell'ultima dichiarazione, sia nella proiezione interna sia fra le
colonne aggregate esterne. Non si introducono nomi alternativi o rinomine.

L'ordine base della tabella raggiunta è automatico; `.order_by(...)` lo
sostituisce. Sono ammessi campi di ordinamento non selezionati, formule e
relazioni. L'ordine esterno resta indipendente. In assenza di ordine dichiarato
non viene inventato un criterio. Le righe della query esterna non si moltiplicano.

Senza righe correlate il risultato SQL è `[]`. NULL e stringa vuota rimangono
valori distinti nei singoli oggetti: il placeholder appartiene soltanto a join.
Il JSON viene costruito dal database; non si aggiungono conversioni nel fetch.
Restano le rappresentazioni DB-API native: psycopg decodifica JSONB, SQLite
restituisce il testo JSON. I contratti confrontano il contenuto JSON dei due.

## Raccordo e algoritmi riusati

- `_many_aggregates` riconosce `to_json` e passa la selezione a `many_aggr`.
  Non espande autonomamente colonne o formule.
- La correlazione e i filtri delle virtualRelation semplici usano il raccordo
  già verificato nei passi 103–104. `subquery` crea il contesto figlio e riusa
  `select_plan`, `expand_columns`, `FieldReferences` e `projection_columns`.
- Il contesto figlio mantiene il mangler dei parametri separato dagli alias
  SQL. La proiezione differita impedisce una nuova sostituzione nel padre.
- PostgreSQL riusa `aggregate_sql_subquery`: `jsonb_agg(row_to_json(...))` sul
  SELECT ordinato, con COALESCE a `[]` soltanto per il nuovo `to_json`.
- SQLite usa `json_group_array(json_object(...))` sul SELECT ordinato. Oggetti
  costruiti dopo l'ordinamento evitano di perdere l'informazione JSON fra
  proiezione interna e aggregazione. Senza righe json_group_array produce `[]`.

SQLite ricava i nomi dalla proiezione SQL effettiva usando `split_sql`, lo
splitter già portato dal legacy. Non può basarsi soltanto sui metadati opzionali:
le query legacy con alias dichiarati come CamelCase possono non averli.
Conserva la grafia degli alias e, per espressioni senza alias esplicito, il
nome assegnato da SQLite al testo dell'espressione. I casi già presenti in
`test_legacy_projections_parameters` sono confrontati con la query ordinaria.
Non si modifica la proiezione legacy né si normalizzano diversamente i nomi.

Il precedente `subQueryColumn(mode='json')` mantiene il suo comportamento:
nessuna modifica al risultato vuoto PostgreSQL o alla capability SQLite.
Il nuovo wrapper è dedicato al contratto `to_json` approvato. Nessun intervento
su renderer, scritture, dipendenze o contenitori runtime.

## Verifiche

La suite dedicata su PostgreSQL e SQLite, compreso il catalogo Bag opzionale,
dà **177 passed, 5 skipped, 4 xfailed**. Passano i dieci contratti JSON prima
xfail; i 28 casi aggiuntivi coprono espressioni, tipi numerici e testo, NULL e
vuoti, codifica dei valori parametrizzati, alias interni/esterni duplicati,
star esplicita, formule e ordinamento con mangler locali, query riusabili,
modello invariato, virtualRelation e percorsi con prefisso verso uno.

I quattro xfail rimasti riguardano `to_xml` su PostgreSQL. Il rifiuto di XML
su SQLite resta un test positivo; gli skip rispettano le capability concordate.

La regressione completa delle letture dà **4435 passed, 21 skipped,
16 deselected, 4 xfailed** in 202,20 secondi. Ruff, mypy (58 file) e
`git diff --check` passano. Il confronto AST conferma che i metodi preesistenti
degli adapter e l’algoritmo della proiezione legacy sono invariati. Risultati
registrati nell'[evidenza del passo](evidence/many-aggregation-contracts/json.json).
Il manifesto di esclusione delle scritture resta invariato.

## Resta aperto

`to_xml` compatibile con Bag su PostgreSQL. Restano separati i limiti già
espliciti su ask, derivazioni di virtualRelation, forma diretta `table=` e join
many con condizioni speciali. Questo passo non ne modifica la semantica.
