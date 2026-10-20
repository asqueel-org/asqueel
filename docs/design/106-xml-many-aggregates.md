# 106 — to_xml compatibile con Bag su PostgreSQL

**Aggiornamento successivo:** il [passo 107](107-outer-as-projections.md)
corregge la ricerca di AS nelle proiezioni e rimuove il limite iniziale su AS
esplicito in to_xml. I risultati sotto conservano la verifica di questo passo.

16 ottobre 2026. Implementazione del contratto XML approvato in
[101](101-many-aggregation-decisions.md), verificato contro il
[formato congelato 102](102-many-aggregation-contracts.md).

## Risultato

```text
@invoices.aggr(to_xml())
@invoices.order_by('$qty DESC, $id').aggr(
    to_xml($code, $double_total AS amount, @vat_id.rate AS rate) AS invoices
)
```

Il risultato è testo XML con radice `GenRoBag`. Le righe sono etichettate
`r_0`, `r_1`, … nell'ordine della raccolta, senza richiedere la primary key
nella selezione. Senza righe si produce una radice Bag vuota.

Colonne esplicite, formule, alias, relazioni e parametri passano dalla stessa
SELECT figlia di join e to_json. Senza argomenti vale `*`, comprese le statiche;
l'alias automatico è `_invoices_xml`. AS prevale e gli alias duplicati mantengono
l'ultima dichiarazione. Ordine base, override `.order_by(...)`, campi di ordine
non selezionati e indipendenza dall'ordine esterno mantengono i contratti esistenti.

NULL produce `_T="NN"`, distinto dalla stringa vuota. I tipi numerici, booleani
e temporali usano i codici del catalogo Bag; i valori di testo sono protetti
dai costruttori XML PostgreSQL. I nomi dei campi sono normalizzati come nel
codec Bag installato, con `_tag` quando serve conservare l'alias originale.

SQLite rifiuta `to_xml` esplicitamente: nessun fallback. Il fetch continua a
restituire XML e non costruisce oggetti Bag. Non si aggiunge una dipendenza
GenroPy al core; il catalogo reale serve solo ai test opzionali di rilettura.

## Riuso e traduzione SQL

Il raccordo riusa `many_aggr`, la correlazione `#THIS`, `subquery`, `select_plan`,
`projection_columns`, `FieldReferences`, `SqlBindings` e la preparazione driver.
Alias SQL e mangler restano separati. Il compilatore delega il formato XML
all'adapter, come per JSON e join; non modifica renderer o runtime delle scritture.

La costruzione PostgreSQL è isolata in `dialects/_bag_xml.py`:

1. La SELECT figlia già ordinata alimenta direttamente il wrapper, senza JOIN
   che possano riordinare o moltiplicare le righe.
2. `row_number() OVER () - 1` assegna il numero posizionale. `xmlelement` e
   `xmlattributes` costruiscono i campi tipizzati; `xmlconcat` li raccoglie.
3. Le sole etichette numeriche generate entrano nel testo dei tag `r_N`;
   `xmlparse` lo converte in XML. I valori rimangono nei costruttori XML,
   senza concatenare testo utente non protetto nei tag.
4. `xmlagg(... ORDER BY n)` conserva la sequenza e `xmlelement("GenRoBag", ...)`
   produce la radice anche in assenza di righe.

La normalizzazione dei nomi è ripresa da `genro_bag._legacy_codec` 0.27.0;
i codici tipo dal catalogo usato nell'oracolo. Il tipo viene letto con
`pg_typeof` sul risultato SQL, anche per le espressioni prive di dtype nel
modello. `to_json(valore) #>> '{}'` fornisce testo scalare e date ISO; per i
booleani si mantiene la grafia Bag `True`/`False`. La timezone rimane quella
della sessione PostgreSQL: il compilatore non la cambia.

Il vecchio `subQueryColumn(mode='xml')` e i metodi preesistenti degli adapter
rimangono invariati. Il suo formato XML non viene sostituito con il nuovo
contratto Bag delle aggregazioni.

## Verifiche

La suite dedicata su PostgreSQL e SQLite, con il catalogo Bag reale disponibile,
dà **190 passed, 14 skipped, nessun xfail**. I quattro contratti XML prima
xfail passano; nove test PostgreSQL aggiuntivi verificano il SQL compilato.
I 14 skip sono le verifiche di produzione XML escluse su SQLite e il controllo
di rifiuto SQLite escluso su PostgreSQL.

L'XML compilato coincide strutturalmente con il campione congelato per testo,
NULL, stringa vuota, interi, Decimal, reali, booleani, date, ore e timestamp
con timezone. Il parser Bag ripristina valori e tipi Python. La connessione
di test viene temporaneamente impostata a UTC per il confronto con l'oracolo
UTC e poi ripristinata; il comportamento del prodotto resta invariato.

Sono coperti anche star/statiche, formule e relazioni, collisioni degli alias,
normalizzazione e ripristino dei nomi, ordine comune a join/JSON/XML, parametri
locali isolati, riuso della query, modello invariato, virtualRelation filtrate,
percorso verso uno prima della many e distinzione fra una riga NULL e zero righe.

La suite completa delle letture dà **4445 passed, 33 skipped, 16 deselected,
nessun xfail** in 199,72 secondi. Gli skip aggiuntivi riguardano XML su SQLite
e i round-trip che richiedono il catalogo opzionale, eseguiti nella suite
dedicata. Ruff, mypy (59 file) e `git diff --check` passano. Il confronto AST
conferma invariati i metodi preesistenti degli adapter e la proiezione legacy.
Risultati registrati nell'[evidenza del passo](evidence/many-aggregation-contracts/xml.json).
Il manifesto delle letture continua a escludere le scritture.

## Limiti espliciti

- Il limite iniziale sulle espressioni prive di alias esplicito è rimosso
  dal [passo 107](107-outer-as-projections.md): si usa il flattener già esistente.
- I tipi certificati sono quelli dell'oracolo e dei round-trip sopra; non si
  dichiara copertura di ogni tipo PostgreSQL o dei suoi tipi definiti dall'utente.
- Restano separati i limiti già concordati di ask, derivazioni di virtualRelation,
  forma diretta `table=` e join many con condizioni speciali.
