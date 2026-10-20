# 62 — Formule native fornite da metodi

14 ottobre 2026. Raccordo di `formulaColumn(sql_formula=True)` al metodo
`sql_formula_<nome>(attr)` della tabella, dopo i rapporti [60](60-native-sql-formulas.md)
e [61](61-native-subqueries.md). Nessuna nuova sintassi o registro di handler.

## Confronto con il legacy e i branch

Riferimenti congelati nell'[inventario](evidence/formula-baseline/inventory.json).

| Riferimento | Algoritmo esaminato | Scelta mantenuta |
| --- | --- | --- |
| Legacy `fa35e5a`, `gnrsqldata/compiler.py:390–431` | Copia degli attributi; chiamata sulla tabella proprietaria; poi select_* e var_* | La formula del metodo entra nello stesso percorso delle formule SQL dichiarate |
| v2 `68f35b9`, `_handle_formula:345–365` | Copia profonda degli attributi e metodo sulla tabella proprietaria | Copia modificabile anche per liste e mapping delle dichiarazioni esistenti; nessuna mutazione del modello congelato |
| v4 `38d210c`, `_handleFormulaColumn:495–512` | Stessa chiamata, prima del preprocessamento SQL | Nessun secondo compilatore o sostituzione manuale dei placeholder |
| v4, `gnrsql/runtime_model.py` e `gnrsqlmodel/table.py::_withRuntimeColumns` | Overlay temporaneo di colonne e relazioni; la risoluzione del metodo resta sulla tabella | Valutazione e cache limitate alla compilazione; nessuna formula espansa salvata nella colonna |

Controllati anche v3/v3 merged (riga 503), simplify (405), next (396) e
compound (449): la convenzione di chiamata è la stessa. v3 segue l'ordine
di v2/v4; simplify, next e compound seguono quello del riferimento legacy.

Nel legacy di riferimento `var_*` viene estratto **dopo** la chiamata al metodo.
v2/v4 lo estraggono prima. Manteniamo il comportamento del riferimento: un
metodo può impostare i propri `var_*` e modificare i propri `select_*` nella
copia di `attr`. Test dedicati verificano questa differenza fra gli algoritmi.
Le ottimizzazioni sperimentali JOIN/LATERAL e lazy non sono adottate.

## Implementazione e proprietà

- `SqlDatabase` collega internamente il compilatore al grafo delle tabelle già
  costruito. Il metodo viene cercato sulla tabella proprietaria, anche quando
  raggiunta tramite alias, JOIN o sottoquery. Si usa `x_table_class`, già esistente.
- Il render conserva `sql_formula=True` come dichiarazione, anche nel vecchio
  ingresso tramite schema. La chiamata avviene alla compilazione della query.
- `_Context.formula_definition` normalizza il risultato con `_formula_definition`;
  `_Context.formula_scope` usa gli attributi risultanti. Scanner, dipendenze,
  cicli, macro, sottoquery, dialetto e mangler sono quelli già presenti.
- Il metodo restituisce SQL non vuoto. Metodo assente, risultato non valido e
  cicli sono errori espliciti; le eccezioni applicative non vengono mascherate.
  Il compilatore usato da solo, senza una tabella applicativa, non inventa un
  oggetto su cui eseguire i metodi.
- Una definizione viene valutata una volta per colonna nella singola compilazione;
  SQL e binding restano distinti per alias e scope. La compilazione successiva
  rivaluta il metodo. Le modifiche locali ad `attr` non raggiungono source,
  modello o ambiente. Il metodo applicativo deve costruire SQL senza I/O:
  è codice Python fidato, non codice eseguito in una sandbox.

## Metodi già richiesti dai sys_fields

Le 134 dichiarazioni del censimento sono 67 `__protecting_reasons` e 67
`__invalid_reasons`. I due metodi di `gnr/app/gnrdbo.py:641–667` sono raccordati
su `SqlTable`, usando le colonne virtuali già dichiarate:

- protezioni: `protectionColumn` non NULL e colonne `__protected_by_*` vere;
- invalidità: colonne `__invalid_by_*` vere;
- nessuna regola dichiarata: SQL NULL;
- regole presenti ma nessuna attiva: stringa vuota;
- più regole attive: nomi separati da virgola, nell'ordine delle dichiarazioni.

Si leggono sia `protectionColumn` sia il nome conservato `x_legacy_protectionColumn`.
PostgreSQL mantiene `array_to_string(ARRAY[...], ',')`; SQLite rende lo stesso
risultato con concatenazione, COALESCE e substr. La scelta appartiene al
dialetto. Nomi con apici o virgole sono verificati, senza rimuovere caratteri
dal valore. Non vengono implementati controlli di scrittura, diagnostics,
system_records o locked records.

## RuntimeModel: considerato, ancora da implementare

Letti anche i test v4 `test_runtime_model.py`: visibilità nel blocco, ripristino,
riuso e tabelle multiple. Non sono dichiarati portati: la relativa API non è
ancora implementata. I controlli attuali verificano nuova compilazione dopo un
cambio della dichiarazione risolta, ambiente corrente e due thread sulla stessa
query. Non certificano un overlay RuntimeModel completo.

Il futuro raccordo deve fornire **lo stesso modello effettivo** alla navigazione
del compilatore e alla tabella vista dal metodo, inclusa l'enumerazione delle
colonne nei due metodi di sistema. Cambiare soltanto `compiler.model` non basta
per metodi che leggono `self.model`. Nessuna classe proxy, nuova firma o
invalidazione globale viene anticipata qui.

## Test ed evidenze

- Due test `TestSqlFormulaTrueDelegate` portati senza modifiche al corpo o alle
  asserzioni. Sono presenti identici nei riferimenti legacy e next; v2/v3 non
  hanno il modulo, v3 merged/v4/simplify non hanno questa classe. Provenienza e
  hash AST in `tests/native_formulas/legacy-method-formulas-manifest.json`.
- Test aggiuntivi senza I/O: metodi su tabelle correlate, alias, dipendenze,
  select_* modificati dal metodo, parametri omonimi nei diversi scope, liste,
  riuso, errori, cicli, ambiente, thread e sostituzione della dichiarazione.
- Test sui risultati PostgreSQL e SQLite: NULL/stringa vuota, più motivi,
  protezione non NULL anche se vuota, nomi quotati, dipendenze da metodi,
  WHERE/ORDER BY, sottoquery nominate e isolamento dei parametri.

La sonda sui 74 modelli nativi passa da **187 a 455/462 formulaColumn**;
le 134 formule da metodo e le 134 dipendenti sono compilabili. Alias invariati:
**45/46**. Restano cinque formule dipendenti da inverse, una con valore
`env_user_id` assente nella sonda e una con `#PREF`. Restano inoltre le famiglie
subQueryColumn, bagItemColumn, pyColumn e l'alias su virtualRelation.
La sonda non certifica i risultati di tutte le formule sui dati.

Suite completa: **1592 superati e 9 saltati**. Esiti e controlli statici sono registrati nelle
[evidenze](evidence/native-method-formulas/results.json); il
[censimento](evidence/native-method-formulas/coverage.json) conserva il dettaglio.
