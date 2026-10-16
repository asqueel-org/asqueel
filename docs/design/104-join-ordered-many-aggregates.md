# 104 — join e ordine delle aggregazioni verso molti

16 ottobre 2026. Implementazione del secondo perimetro approvato in
[101](101-many-aggregation-decisions.md), dopo gli aggregati numerici del
[passo 103](103-numeric-many-aggregates.md).

## Comportamento verificato

```text
@invoices.aggr(join($code, ',') AS codes)
@invoices.order_by('$qty DESC, $id').aggr(
    join($code, ',', '-empty-') AS codes,
    count() AS n,
    sum($total) AS total
)
```

- L'ordine base della tabella correlata si applica automaticamente; `.order_by`
  lo sostituisce. I campi di ordinamento possono essere non selezionati,
  formule o riferimenti verso uno. Si riusa la sintassi di ordinamento della query.
- Senza ordine base né override non si introduce un ordine convenzionale.
  L'ordine della query esterna rimane indipendente da quello della raccolta.
- NULL e stringa vuota vengono sostituiti nella singola riga con il placeholder,
  che vale `''` se omesso. Spazi e testo `'null'` non ricevono significati speciali.
  Le posizioni e i separatori rimangono presenti. Senza righe il risultato è `''`.
- L'alias automatico è `_invoices_code_join`, senza separatore o placeholder.
  `AS` prevale; in caso di alias duplicato rimane l'ultima dichiarazione.
- Le espressioni di join usano formule, `var_*`, alias e relazioni già risolti
  dalla SELECT. Le virtualRelation semplici filtrate e i percorsi verso uno
  che precedono una many usano lo stesso raccordo del passo numerico.

## Riuso degli algoritmi

Il legacy distingue la concatenazione nei suoi adapter: `string_agg` in
`_gnrbaseadapter.py:942` e `group_concat` in `gnrsqlite.py:394` dello snapshot
`fa35e5ad` già censito. Manteniamo questa delega; la grammatica `.aggr()` e
la semantica di placeholder/ordine sono le decisioni nuove approvate in 101.

Il percorso è: riconoscimento della chiamata e del modificatore `.order_by` →
`many_aggr` → relazione e correlazione `#THIS` → `subquery` → `select_plan`
figlia → adapter. La catena non introduce una grammatica generale di metodi:
`order_by` è soltanto il modificatore concordato che precede `aggr`.

Per join la SELECT figlia proietta valore e separatore, applica filtri e ordine,
poi l'adapter avvolge quel SELECT con l'aggregazione di stringhe. Il valore è
normalizzato con `COALESCE(NULLIF(CAST(espressione AS text), ''), placeholder)`;
un COALESCE esterno produce `''` per l'insieme vuoto. Il wrapper non aggiunge
JOIN o altri passaggi che riordinino le righe della SELECT figlia.

La forma riusa il wrapper di sottoquery già presente per le raccolte delle
subQueryColumn, lasciandone invariato il comportamento. Non dipende dalla
sintassi ORDER BY interna a group_concat delle versioni recenti di SQLite.
Per count e aggregati numerici l'ordine non cambia il risultato: non viene
aggiunto un ORDER BY di colonne non raggruppate alla SELECT aggregata.

`_many_aggregates.py` sostituisce il nome precedente `_numeric_aggregates.py`,
ora troppo restrittivo. Riusa `split_sql` e `col_to_as`; il compilatore conserva
il registro locale delle proiezioni differite. SQL delle figlie e parametri
manglizzati non vengono analizzati di nuovo nel padre. I mangler e gli alias
SQL restano separati. Nessun cambiamento a renderer o scritture.

## Verifiche

La suite dedicata, su PostgreSQL e SQLite e con il catalogo Bag opzionale,
restituisce **139 passed, 14 xfailed, 5 skipped**. I 20 contratti di join/ordine
prima xfail passano; altri 28 casi verificano formule e relazioni dentro
espressioni e ordinamento, ordine su campi non selezionati, parametri locali
isolati, virtualRelation, prefissi verso uno e assenza di ordine inventato.

I 14 xfail rimasti riguardano soltanto `to_json`/`to_xml`, incluso il contratto
misto join+JSON. Restano rigorosi: errori SQL o risultati errati non sono
accettati come funzionalità non implementate. Gli skip di dialetto rispettano
l'assenza concordata di XML su SQLite.

La suite completa delle letture dà **4397 passed, 21 skipped, 16 deselected,
14 xfailed** in 211,45 secondi. Ruff, mypy (58 file) e `git diff --check` passano.
Il confronto AST conferma che i metodi preesistenti degli adapter sono invariati:
si aggiunge soltanto il wrapper SELECT `join_sql_subquery`. Risultati registrati
nell'[evidenza del passo](evidence/many-aggregation-contracts/join-order.json).
Il manifesto delle letture continua a escludere le scritture.

## Perimetro successivo

Restano da implementare `to_json` e `to_xml` nei dialetti concordati.
Ask, derivazioni fra virtualRelation, forma diretta `table=` e join many con
condizioni speciali mantengono i limiti espliciti del passo 103. Nessun fallback,
nuovo handler di aggregazione o comportamento di scrittura viene introdotto.
