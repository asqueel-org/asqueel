# 66 — subQueryColumn native

14 ottobre 2026. Raccordo della dichiarazione esistente al compilatore SELECT:
oggetti del modello → SQL e kwargs, senza esecuzione durante la compilazione.
Query concatenate e operatori restano rinviati secondo R-09; nessuna firma nuova.

## Confronto legacy e branch sperimentali

Snapshot e commit sono quelli dell'inventario del rapporto 59. Riferimenti e
hash degli algoritmi sono in
[legacy-comparison.json](evidence/native-subquery-columns/legacy-comparison.json).

Il legacy corrente (`gnrsqlmodel/model.py:1185–1235`) distingue tre percorsi:

- `mode=None`: virtuale con `select=query`, nel percorso scalare comune;
- `mode='json'`: SELECT esterna con `jsonb_agg(row_to_json(...))` sopra
  `select_nestedselect=query`;
- `mode='xml'`: SELECT esterna con `xmlagg(xmlelement(..., xmlforest(...)))`
  convertita a testo, sopra la stessa sottoquery nominata.

Altri mode vengono conservati come `subquery_aggr`: il percorso esaminato non
sintetizza un aggregato SQL dal loro nome. Non si introduce un default `'scalar'`
né si trasforma `mode='sum'` in SUM. `getFieldAlias` del compilatore legacy
(`gnrsqldata/compiler.py:390–440`) delega le sottoquery a queryCompile, mantenendo
correlazione `#THIS`, scope locali e default già raccordati nel rapporto 61.

`next` conserva gli stessi wrapper corretti del legacy corrente. v2, v3,
v3_merged, v4, simplify e compound hanno la versione precedente con `json_agg`
e XML non convertito a testo. Si mantiene la correzione recente: JSONB e testo
sono confrontabili in un SELECT DISTINCT. Questo non introduce DISTINCT implicito.
I refactor sperimentali non forniscono un diverso algoritmo da importare qui.

## Implementazione e differenze motivate

La dichiarazione `query` dict è normalizzata una sola volta per colonna e
compilazione con `_subquery_definition`, nella cache già esistente. Dipendenze,
alias, cicli, `var_*`, `sqlparams` e riferimenti alle relazioni usano il percorso
comune delle formule. Nessuna copia del compilatore o espansione della source.

`_Context.subquery` costruisce il medesimo QueryPlan figlio per le tre forme.
Il caso semplice conserva il controllo di una sola colonna, senza LIMIT implicito.
I casi JSON/XML consentono più proiezioni e delegano il solo wrapper al dialetto
PostgreSQL. SQLite li rifiuta esplicitamente prima dell'I/O; non viene inventata
una traduzione alternativa. Alias e parametri restano strutturati fino alla
formattazione finale del driver, con i mangler già isolati per scope.

Il wrapper XML usa gli alias delle proiezioni risolte, anziché rimuovere `$`
dalla stringa `columns` come nel legacy. Questo riusa il piano già compilato,
evita di ripetere espressioni fuori dal loro scope e gestisce formule con AS.
Per le colonne semplici di test_invoice_pg il risultato resta equivalente.
L'escaping dei nomi XML è quello di PostgreSQL: per esempio il suffisso `_xml`
diventa `_x005F_xml`, anche con il wrapper legacy originale.

ORDER BY, LIMIT/OFFSET, GROUP BY/HAVING e filtri appartengono al SELECT figlio,
prima dell'aggregazione. JSON conserva i campi NULL, XML li omette. Sorgente
vuota: NULL in entrambi i casi, senza introdurre liste o stringhe vuote.
Il decoder JSON è quello del driver già disponibile; nessun nuovo codec.

## Test ed evidenze

- **7 test legacy portati**, prima tutti falliti per capacità non supportata,
  ora tutti verdi. Le asserzioni sono conservate; soltanto il terminale
  `readColumns` della controprova MAX è sostituito dalla query equivalente con
  alias esplicito e `fetch()[0]`. Hash e provenienza:
  `tests/native_formulas/legacy-subquery-columns-manifest.json`.
- Replay dei corpi test presenti: legacy **7/7**, next **7/7**,
  v3_merged **5/5**, v4 **5/5**. I cinque test dei rami più vecchi non includono
  i due casi DISTINCT recenti: quei risultati non ne attestano il supporto.
  simplify **0/5**: tratta le virtuali come colonne fisiche inesistenti.
  v2, v3 e compound non contengono gli stessi corpi test; confronto degli
  algoritmi, senza dichiarare un replay equivalente. Log e XML sono nella
  cartella [evidence/native-subquery-columns](evidence/native-subquery-columns/legacy-comparison.json).
- **17 test di compilazione senza I/O**: semplice/JSON/XML, dipendenze,
  alias, var_*, riuso, collisioni con i parametri del chiamante, correlazione,
  sottoquery annidate, JOIN, GROUP BY/HAVING, paginazione, default/override
  delle policy, cicli ed errori espliciti. Connessione ed esecuzione dei driver
  sono vietate dalle fixture.
- **6 test sui risultati controllati**, con PostgreSQL e SQLite: confronto
  scalare, dati effettivi JSON/XML, NULL e insiemi vuoti, escaping, DISTINCT
  esplicito, parametri locali, gerarchie, JOIN e override delle policy.
  Quattro casi JSON/XML sono saltati su SQLite, con rifiuto verificato nei test
  di compilazione. Schemi di test isolati, nessun dato applicativo modificato.
- Sonda senza I/O su tutti i 74 modelli nativi, PostgreSQL: **3/3 subQueryColumn**
  compilano (`rows_json`, `notes_xml`, `max_row_price` di invc.invoice).
  Restano invariati **460/462 formule** e **45/46 alias**; i limiti di altre
  famiglie non sono chiusi da questo incremento.

Suite completa: **1870 superati, 13 saltati**. Ruff, mypy e Sphinx strict superati.
I risultati e i comandi riproducibili sono nel
[riepilogo delle verifiche](evidence/native-subquery-columns/verification.json).

## Limiti conservati

Stringhe che identificano metodi `subquery_*` restano non supportate, come nel
percorso select/select_* già esistente: vanno affrontate insieme all'ownership
dei metodi e al futuro RuntimeModel. Una query non ancora valorizzata nella
source produce un errore quando viene richiesta la compilazione della colonna.
Il cast della sorgente di righe JSON/XML è esplicitamente rifiutato; il cast
scalare conserva il percorso esistente.

Escluso dal porting `test_subquery_columns_auto_distinct_pg`: richiede il DISTINCT
automatico, già separato dal perimetro nel piano. Non sono implementati
virtualRelation, bagItemColumn, pyColumn, query concatenate o operatori.

Riproduzione della sonda:

```sh
PYTHONPATH=src:../asqueel-migration/src:. venv/bin/python \
  docs/design/probes/native_formula_coverage.py \
  --output docs/design/evidence/native-subquery-columns/native-columns.json
```
