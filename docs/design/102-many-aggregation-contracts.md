# 102 — Contratti delle aggregazioni e verifica XML Bag

16 ottobre 2026. Solo test, fixture e documentazione. **Nessun handler o modifica
al compilatore, agli adapter, al renderer, al fetch o alle scritture.**
Decisioni di riferimento: [101](101-many-aggregation-decisions.md).

## Esito

| Verifica | Risultato |
| --- | --- |
| Nuova suite, SQLite e PostgreSQL, catalogo GenroPy reale disponibile | 24 passed, 93 xfailed, 5 skipped |
| Stessa suite con `--runxfail` | 24 passed, 93 failed attesi, 5 skipped |
| Regressioni relazioni, star, formule/statiche e Bag | 346 passed, 2 deselected |
| Ambiente core isolato, senza GenroPy, escluso PostgreSQL | 16 passed, 45 xfailed, 7 skipped, 54 deselected |

I 24 verdi verificano il formato XML, il round-trip dei tipi e le fixture sul
percorso esistente. **Non indicano aggregazioni implementate.** I 5 skip sono
quattro casi di produzione XML esclusi su SQLite e il controllo di rifiuto
SQLite escluso su PostgreSQL. I due deselect riguardano lo stesso test DML
preesistente sui due dialetti: le scritture restano fuori perimetro.

Il [riepilogo macchina](evidence/many-aggregation-contracts/baseline.json)
registra tutti i casi e gli errori della baseline senza xfail:

| Contratti mancanti | Causa concreta attuale |
| --- | --- |
| 81 | `many_aggr not yet supported` |
| 7 | `many_order_by not yet supported` |
| 4 | La chiamata sulla virtualRelation non viene risolta; `$total` viene cercato sulla customer (`Unknown column app.customer.total`) |
| 1 | SQLite rifiuta già la richiesta, ma per l'assenza generale di `many_aggr`; manca il rifiuto che identifica la capability `to_xml` |

Sono `xfail(strict=True)` limitati alla classe dell'errore osservato: gli errori
SQL, delle fixture e le asserzioni sui risultati non sono mascherati come
assenza di handler. Le virtualRelation hanno una classificazione distinta.
Un contratto che passa diventa XPASS e rende rossa la suite, richiedendo di
rimuovere l'xfail. La baseline `--runxfail` verifica le cause effettive.

Nella prova isolata i 7 skip sono quattro casi XML SQLite e tre round-trip
che richiedono il catalogo opzionale. Ruff e `git diff --check` passano;
verificati anche i link locali dei documenti. Nessun file sotto `src/` modificato.

## Copertura dei contratti

I test sono in [tests/many_aggregations](../../tests/many_aggregations).

- Count, sum, avg, min, max; più argomenti indipendenti, `AS` per argomento,
  alias automatici e misti; a parità di alias prevale l'ultima dichiarazione.
- Espressioni aritmetiche e CASE, formulaColumn e loro dipendenze/`var_*`, alias
  di colonne e campi attraversati con una relazione verso uno.
- Join con separatore e placeholder; NULL e stringa vuota vengono sostituiti,
  conservando le posizioni. Il placeholder omesso è `''`, il testo `'null'`
  non ha significato SQL speciale. Il nome automatico non include i separatori.
- Nessuna riga correlata: count zero, numerici NULL, join stringa vuota,
  JSON array vuoto, XML Bag vuota. Una riga presente con codice NULL resta una
  riga e usa il placeholder: non equivale all'insieme vuoto.
- Ordine base automatico, override `.order_by(...)`, ordinamento per campi non
  selezionati, ordine comune a join/JSON e isolamento fra due chiamate diverse.
- JSON con selezione esplicita, alias, formule e relazioni; selezione implicita
  confrontata con `query('*')`, comprese le statiche.
- XML con etichette `r_0`, `r_1`, … nell'ordine della raccolta, senza richiedere
  la pkey; NULL distinto da stringa vuota, colonne tipizzate, formule, relazioni,
  selezione implicita confrontata con la query e Bag vuota.
- Contesto raggiunto attraverso una relazione verso uno prima della many;
  virtualRelation verso molti con filtro semplice e con `var_*` correlato.
  Nessun test inventa semantiche per derivazioni o valori `ask` ancora aperti.
- Nessuna moltiplicazione delle righe esterne, riuso della query, binding di
  formula isolato dall'omonimo binding esterno e compilazione senza I/O.
- Rifiuto delle proiezioni many nude e capability XML assente su SQLite.

La compilazione usa l'API pubblica `query(...).compiled`. L'SQL restituito è
eseguito direttamente dalla DB-API su fixture isolate: il test non ricostruisce
aggregazioni in Python e non può passare grazie a elaborazioni dopo il fetch.
Su PostgreSQL si usano tabelle temporanee della sola connessione; su SQLite un
database in memoria. Nessuna API di scrittura Asqueel viene usata o modificata.

Gli alias automatici delle espressioni restano vincolati al flattener esistente;
i contratti numerici sulle espressioni usano alias espliciti, senza inventare
un ulteriore esempio di normalizzazione. Nessun ordinamento viene imposto al
caso in cui manchino sia ordine base sia override.

## Formato XML verificato

Il riferimento è **genro-bag 0.27.0**, tramite il profilo tipizzato già esistente:

```python
bag.to_xml(legacy_mode=True, catalog=GnrClassCatalog())
Bag.from_xml(xml, legacy_mode=True, catalog=GnrClassCatalog())
```

La fixture [rows.xml](../../tests/many_aggregations/data/rows.xml) è prodotta dal
serializer reale, non da un serializer scritto per questi test. Versione e
hash delle sorgenti e delle fixture sono in
[provenance.json](../../tests/many_aggregations/data/provenance.json).

- Radice `GenRoBag`; ogni riga è un nodo `r_N` contenente i campi selezionati.
- Stringa vuota: elemento senza testo, senza marcatore di NULL.
- NULL: elemento senza testo con `_T="NN"`.
- Marcatori verificati: `L` intero, `N` Decimal, `R` float, `B` booleano,
  `D` data, `H` ora e `DHZ` datetime con timezone.
- Testo con `<`, `&`, `>` e virgolette: escaping XML e recupero del testo
  originale dal parser.
- Bag vuota: elemento radice `GenRoBag` senza nodi riga. Dichiarazione XML,
  indentazione e forma autochiusa non costituiscono un vincolo di byte esatti.

Due test PostgreSQL eseguono un **esempio SQL fisso** con `xmlelement` e
`xmlattributes`: il risultato coincide strutturalmente con il serializer e
viene riletto da Bag conservando valori e tipi. Non c'è un generatore SQL
riutilizzabile, né una traduzione della grammatica nel codice dei test.
Le etichette dinamiche della raccolta e la compilazione completa restano lavoro
successivo: l'esempio SQL verifica solo la compatibilità del formato.

### Limite del codec da tenere distinto dal compilatore

Il normale `Bag.to_xml()` della versione installata non è il profilo tipizzato:
produce frammenti senza radice aggiuntiva, non conserva i marcatori dei tipi e
non distingue NULL da stringa vuota. Con due nodi radice, il tentativo diretto
di rilettura del frammento produce `SAXParseException: junk after document element`.

Il profilo `legacy_mode=True` richiede un catalogo iniettato oppure il modulo
opzionale `gnr.core.gnrclasses`. Nell'ambiente isolato del core, senza GenroPy,
solleva `LegacyCodecDependencyError`. I round-trip sono stati verificati con il
catalogo GenroPy reale nell'ambiente di confronto già esistente. In sua assenza
si saltano solo i test che richiedono quel catalogo; i test sul wire congelato
e il confronto XML PostgreSQL restano eseguibili.

**Non è stata aggiunta una dipendenza GenroPy al core.** La decisione resta
produrre XML compatibile in SQL e restituire XML, senza conversione in Bag nel
fetch. La presenza del catalogo è necessaria per questi test di rilettura
opzionali, non per generare il futuro SQL.

## Riproduzione

Dalla radice del worktree, con un ambiente di test del progetto:

```sh
PYTHONPATH=src python -m pytest tests/many_aggregations -q -o addopts=
PYTHONPATH=src python -m pytest tests/many_aggregations -q -o addopts= --runxfail
```

PostgreSQL usa i parametri di `tests.native_support.postgres_dsn`; i test sono
marcati `postgresql`. Per soli SQLite e controlli locali usare `-m 'not postgresql'`.
Per ripetere anche i round-trip tipizzati, rendere disponibile GenroPy con le
sue dipendenze nell'ambiente di confronto, senza installarlo nel core.

Il [probe di congelamento](probes/freeze_aggregation_bag_xml.py) rigenera le
fixture dal serializer esistente. Non rigenerarle per nascondere una divergenza:
prima verificare il cambiamento del formato o della versione della dipendenza.
