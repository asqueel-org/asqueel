# 109 — Derivazioni delle virtualRelation verso molti

16 ottobre 2026. Decisione approvata: le condizioni dei livelli si compongono
in AND; i `var_*` hanno nomi manglizzati distinti per ciascun livello e utilizzo.
Non si applica una precedenza tra dichiarazioni omonime. `ask` resta
[rinviato](108-deferred-virtual-relation-ask.md).

## Contratto ed esempio

```python
tbl.virtualRelation('above_minimum', relation='@invoices',
    condition='$total>:var_limit', var_limit='$id * 15')
tbl.virtualRelation('within_window', relation='@above_minimum',
    condition='$total<:var_limit', var_limit='$id * 35')
```

```text
@within_window.aggr(count() AS n, sum($total) AS amount)
```

Per il cliente con id 1 si aggregano le fatture con totale maggiore di 15 e
minore di 35. Ogni condizione resta tra parentesi, anche quando contiene OR.
Una derivazione senza condizione conserva i filtri della base. Una catena può
comprendere più livelli: si raggiunge la relazione ordinaria verso molti,
si compongono correlazione e filtri e solo dopo si applica l'aggregazione.
Non si aggiunge una SELECT per ogni livello di derivazione.

Nella grammatica esistente i `var_*` delle virtualRelation sono **espressioni
SQL della riga sorgente**, mentre `$campo` e `@relazione.campo` nelle condizioni
appartengono alla destinazione. Questa distinzione rimane invariata: non si
introduce una nuova grammatica di valori scalari. Le espressioni possono usare
formule e parametri della query con la risoluzione già esistente.

## Raccordo al compilatore esistente

- La ricerca della virtualRelation usa i nodi del modello gerarchico. La catena
  viene percorsa fino al joiner ordinario; si conserva il contesto sorgente di
  ogni dichiarazione, anche attraversando un percorso verso uno.
- Ogni condizione con `var_*` usati riceve un `SqlBindings.child(..., 'v')`.
  L'allocatore e `substitute` esistenti assegnano nomi distinti; non è stato
  introdotto un altro mangler e `_sql_bindings.py` non cambia.
- Dopo la manglizzazione, ciascun riferimento locale viene sostituito con la
  propria espressione risolta sulla sorgente. Il binding temporaneo viene
  consumato: il testo dell'espressione non rimane nei kwargs come valore DB-API.
  I parametri effettivi e quelli delle formule conservano i propri scope.
- Solo dopo questa espansione indipendente si combinano le condizioni in AND.
  Alias SQL e mangler restano separati; modello e parametri del chiamante non
  vengono modificati.
- Correlazione, compilazione delle sottoquery e aggregati riusano il percorso
  esistente. La traduzione di join/JSON/XML resta agli adapter.

Le virtualRelation non erano implementate nel legacy: questa composizione è
la decisione esplicita dell'utente, non un algoritmo attribuito al legacy.
Il riuso riguarda gli algoritmi già portati di risoluzione dei riferimenti,
compilazione delle sottoquery e manglizzazione.

**Aggiornamento successivo:** il [passo 110](110-direct-virtual-relations.md)
raccorda anche `table=` con `condition` obbligatoria. I risultati sotto restano
la fotografia di questo passo.

## Limiti al termine del passo 109

- `ask` non è supportato, anche se presente in un livello di base.
- La forma diretta `table=` resta da raccordare. Non viene introdotta in questo
  passo né trasformata in un'abbreviazione verso uno.
- Restano esclusi i joiner verso molti con condizioni custom non ancora raccordate.
- L'uso di `.aggr()` resta limitato alle proiezioni. Non si ripristinano righe
  esplose o JOIN esterne verso molti.
- `to_xml` resta disponibile soltanto su PostgreSQL.
- Catene cicliche e basi inesistenti producono un errore esplicito.

## Verifiche

`tests/many_aggregations/test_virtual_derivations.py` verifica su PostgreSQL e
SQLite: filtri in AND con OR parentetici, tre livelli, livello senza condizione,
nomi `var_*` uguali e confine `var_limit`/`var_limit2`, formule e parametri esterni,
utilizzi ripetuti, isolamento dal parametro omonimo della query, contesto sorgente
dopo percorsi verso uno, assenza di I/O durante la compilazione e immutabilità
del modello. Copre risultati numerici, join e JSON ordinati e XML su PostgreSQL;
verifica inoltre rifiuto di ask, cicli e relazione inesistente.

Baseline SQLite prima del raccordo: **11 failed, 1 passed, 1 skipped** (13 casi
PostgreSQL esclusi da quella baseline). Dopo il raccordo, i nuovi contratti danno
**25 passed, 1 skipped** sui due dialetti. La regressione mirata con aggregazioni,
formule e grammatica virtualRelation dà **290 passed, 21 skipped**; la sola suite
aggregazioni dà **237 passed, 21 skipped**, con catalogo Bag disponibile.

Regressione completa delle letture: **4491 passed, 41 skipped, 16 deselected**,
nessun xfail, in 176,72 secondi. Ruff e mypy passano (59 file sorgente), così
come `git diff --check`. Risultati registrati nell'
[evidenza del passo](evidence/many-aggregation-contracts/derivations.json).
Manifesto delle letture invariato; nessun intervento sulle scritture.
