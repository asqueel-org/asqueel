# 107 — AS esterno nelle proiezioni e rimozione del limite XML

16 ottobre 2026. Correzione approvata dopo il confronto sul limite di `to_xml`:
la ricerca dell'alias deve distinguere AS esterno da AS dentro un'espressione.
Non si introduce un parser o una sintassi diversa.

## Correzione

I due controlli testuali del percorso SELECT usano ora `split_sql(column, ' AS ')`,
lo splitter già portato dal legacy. Lo splitter separa fuori da parentesi e
virgolette; il suo algoritmo rimane invariato.

- `projection_columns`: se manca AS esterno, assegna il nome con il flattener
  `col_to_as` già esistente. Se l'alias è esplicito, lo conserva. Il dizionario
  ordinato continua a mantenere l'ultima dichiarazione per alias uguali.
- `select_plan`: registra in `aliasDict` soltanto gli alias esterni, senza
  inserire frammenti di tipo come `NUMERIC)`.
- Il wrapper XML riceve dalla SELECT le colonne già nominate, anche per CAST.
  È rimosso il rifiuto che richiedeva AS esplicito a chi chiama `to_xml`.

Esempio senza alias dichiarati:

```text
CAST($id AS NUMERIC), CAST($total AS NUMERIC)
```

La SELECT conserva entrambe le colonne:

```sql
CAST("t0"."id" AS NUMERIC) AS "CAST__id_AS_NUMERIC_",
CAST("t0"."total" AS NUMERIC) AS "CAST__total_AS_NUMERIC_"
```

I nomi sono quelli del flattener esistente. Un alias esplicito continua a
prevalere. Funziona anche la proiezione aggregata:

```text
@invoices.aggr(
    to_xml(CAST($id AS NUMERIC), CAST($total AS NUMERIC)) AS invoices
)
```

L'XML Bag conserva i due nomi attraverso `_tag` quando la normalizzazione XML
li modifica. Sono verificati valori, tipo Decimal e nomi dopo la rilettura Bag.
SQLite continua a rifiutare to_xml; SELECT e to_json con CAST sono verificati
su entrambi i dialetti.

## Differenza esplicita dal legacy

Il codice legacy cercava la sottostringa ` AS ` e divideva alla prima occorrenza,
senza distinguere il livello delle parentesi. L'oracolo R2 registra:

- un CAST senza alias lasciato senza un nome esplicito;
- due CAST allo stesso tipo ridotti all'ultimo, perché entrambi venivano
  registrati con il falso alias `NUMERIC)`;
- un caso già presente nel corpus con AS dentro una stringa, anch'esso scambiato
  per alias. Anche questo ora riceve il nome dal flattener, perché lo splitter
  esistente rispetta le virgolette.

`tests/oracles/legacy_r2.json` resta invariato. I test mantengono il confronto
con il legacy e identificano esplicitamente le tre differenze autorizzate.
Il test SQLite che prima attendeva un solo valore da due CAST ora li richiede
entrambi. Non si cambia la risoluzione dei riferimenti, il mangler, il quoting
SQL o la gestione di forme SQL non valide.

La correzione è nel percorso comune delle proiezioni: vale per SELECT,
sottoquery, JSON e XML. Non esistono eccezioni del flattener dedicate a XML.

## Verifiche

Le aggregazioni e le regressioni mirate di proiezioni/risoluzione legacy danno
**347 passed, 20 skipped**, su PostgreSQL e SQLite, con catalogo Bag disponibile.
La sola suite aggregazioni dà **212 passed, 20 skipped**, senza xfail.

I nuovi casi verificano CAST singolo, due CAST allo stesso tipo, CAST annidato,
alias espliciti distinti, collisione esplicita con prevalenza dell'ultimo,
nomi del cursore e metadati, aliasDict senza falsi alias interni, JSON con due
CAST, XML senza alias espliciti e round-trip dei due campi con Bag.
Gli skip rispettano la capability XML assente su SQLite.

Suite completa delle letture: **4466 passed, 40 skipped, 16 deselected**, nessun
xfail, in 254,47 secondi. Ruff e mypy passano (59 file sorgente);
`git diff --check` passa. Risultati registrati nell'
[evidenza del passo](evidence/many-aggregation-contracts/outer-as.json).
Il manifesto di esclusione delle scritture rimane invariato. Nessun intervento
su scritture, renderer o dipendenze.
