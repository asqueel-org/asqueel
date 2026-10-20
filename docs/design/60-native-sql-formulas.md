# 60 — Raccordo delle formule SQL native

14 ottobre 2026. Primo incremento del passo 5 del [piano 56](56-read-compiler-plan.md),
successivo alla [baseline 59](59-formula-legacy-baseline.md).

**Implementati e verificati:** formule SQL native, dipendenze fra formule SQL,
alias e `var_*`. Nessuna nuova sintassi, nessun metodo/provider introdotto.
La compilazione continua a produrre SQL e parametri senza eseguire query.
Il passo completo sulle formule resta aperto per le famiglie elencate sotto.

## Legame con gli algoritmi legacy

Riferimenti congelati e commit sono nell'[inventario precedente](evidence/formula-baseline/inventory.json).
In questo incremento sono stati riletti i seguenti punti di
`gnrpy/gnr/sql/gnrsqldata/compiler.py`:

| Riferimento | Algoritmo conservato | Scelta nella riscrittura |
| --- | --- | --- |
| Legacy `fa35e5a`, `getFieldAlias`, ramo formule, righe 390–440 | Espressione dal modello, estrazione `var_`, risoluzione ricorsiva dei campi e dei percorsi, parentesi intorno al risultato | Riuso di `_formula_definition`, `field`, `related`, scanner ed espressioni già presenti in Asqueel |
| v2 `68f35b9`, `_handle_formula`, riga 345 e seguenti | Distinguere la gestione della formula dalla compilazione dei riferimenti | Normalizzazione della dichiarazione e scope dei parametri separati; nessuna conversione automatica a JOIN importata |
| v4 `38d210c`, `_preprocessFormula`, righe 773–791 | Valori locali in `sqlparams`, nomi separati per formula | Allocatore esistente, condiviso da tutti gli scope di una compilazione; niente prefissi basati su `id()` |
| simplify `13b8918` e next `12cfdcc`, ramo `sql_formula_var` | Identità distinta dei parametri di ciascuna formula | Nessuna scrittura in `currentEnv`; snapshot e binding restano distinti |

La modifica motivata riguarda lo stato: il legacy usa anche `currentEnv` e
l'identità Python della colonna per il mangling; Asqueel deve poter ricompilare
la stessa richiesta con un altro modello o ambiente. I valori restano locali,
ma i nomi sono deterministici a parità di modello, query e ambiente.
Non viene cambiata la sintassi né adottato il planner sperimentale dei branch.

## Struttura del codice e confini

- `_Bindings`, estratto dal precedente `_Context`, possiede disponibilità dei
  valori, allocazione dei nomi, parametri effettivi e provenienza degli input.
  Riusa `member_name`, `expand_collection` e `parameter_use`; non introduce
  un secondo algoritmo di sostituzione delle liste o formattazione dei binding.
- `_Context` mantiene tabella, alias SQL, JOIN e risoluzione dei riferimenti.
  Uno scope formula non crea un nuovo SELECT né cambia gli alias di tabella.
  Solo una sottoquery crea il proprio contesto SQL.
- Gli usi scalare/collezione sono associati a `(scope, nome originale)`, non
  a una stringa concatenata: il parametro esterno `f1_items` non può confondersi
  con `items` locale alla formula `f1`. Tutti i nomi emessi condividono lo stesso
  insieme di prenotazioni, inclusi parametri generati dalle policy e PERIOD.
- Una formula referenziata usa i propri `var_*` e gli input della query;
  non eredita i locali della formula che la richiama. Due percorsi verso la
  stessa tabella hanno alias e binding distinti. Ripetere lo stesso percorso
  riusa JOIN e binding scalari. Gli alias seguono il target senza copiarne gli
  attributi operativi (`var_*`, definizioni SQL, marker di compilazione).
- Definizioni normalizzate e scope sono memorizzati soltanto durante una
  compilazione. Non viene memorizzato SQL espanso sul modello, né modificata
  la source. L'espansione ricorsiva e la protezione dai cicli sono quelle esistenti.
- `var_*` usa `extract_kwargs`. Lo spelling `parameters` già presente nella
  grammatica è mantenuto; nomi duplicati fra le due forme sono errori espliciti.
  Una stringa locale come `'$id'` rimane un valore: `embedFieldPars` resta da decidere.

Per il futuro **RuntimeModel** è verificata la compilazione con un nuovo
`ResolvedModel`, senza contaminare il precedente. Non è implementato un overlay,
un context manager o un'invalidazione di cache runtime. Queste API vanno ancora
raccordate al legacy; il test copre solo il confine già disponibile.

Il dialetto continua a scegliere scanner, quoting, rendering, lista vuota e
formattazione dei parametri. Le espressioni SQL applicative non vengono
traspilate: INTERVAL, GREATEST e funzioni specifiche PostgreSQL mantengono i
propri limiti. Nessun costrutto alternativo è stato inventato per SQLite.

## Test portati e regressioni

`tests/native_formulas/test_legacy_sql_formulas.py` porta **96 casi** di
`gnrpy/tests/sql/test_compiler_coverage.py`: **93 passano, 3 sono gli skip
originali SQLite** per GREATEST e INTERVAL. Le 96 definizioni selezionate sono
identiche nei riferimenti legacy, v3 merged, v4, simplify e next; non sono cinque
corpus indipendenti. v2/v3 non contengono quel modulo: i test di sottoquery e
RuntimeModel dei loro progetti restano censiti nella baseline, non dichiarati portati.

Famiglie: alias e percorsi profondi, CASE, COALESCE, CONCAT, REPLACE, CAST,
UPPER/TRIM, LIKE, funzioni matematiche, LAG, formule booleane, dipendenze,
WHERE/ORDER BY, `var_*` scalari e liste, ambiente, funzioni specifiche PostgreSQL.
Le asserzioni originali sono conservate e confrontate via AST. L'unica modifica
al corpo di un test rende esplicito l'alias del risultato di un percorso
relazionale; non cambia il default del compilatore né le asserzioni.

Il [manifesto](../../tests/native_formulas/legacy-manifest.json) conserva
commit, file, righe, hash dei test originali/portati, corrispondenze dei branch,
hash dei CSV e casi rinviati nelle famiglie selezionate. Le fixture caricano gli
otto CSV originali e i 74 modelli nativi. Creano solo le otto tabelle necessarie,
su schemi PostgreSQL unici e file SQLite temporanei. Questo provisioning verifica
le letture; non sostituisce i test di migrazione o dei trigger di scrittura.

Verifiche aggiuntive:

- 28 casi compile-only sui due dialetti, con connessione/esecuzione vietate:
  scope, collisioni, alias, cicli, stringhe/commenti, ambiente immutato,
  riuso della query e sostituzione del modello.
- Due regressioni sulle sottoquery già supportate: parametri della formula
  disponibili nella sottoquery e precedenza dei suoi `sqlparams` locali.
  Questo non abilita le dichiarazioni native di sottoquery.
- Suite completa: **1.473 passati, 4 saltati**, nessun errore/fallimento;
  comprende anche modello, scritture e migrazioni. Il quarto skip preesisteva.
- Ruff su `src tests scripts` e mypy su tutti i 51 file del core: superati.
- Documentazione Sphinx con warning trattati come errori: superata.

Ambiente di esecuzione: Python 3.12.12, SQLite 3.50.4 e PostgreSQL locale 17.7.
Il risultato non certifica tutte le versioni SQLite supportate: in particolare
CONCAT richiede una versione che la implementi. Risultati per test e sonda
sono conservati in [results.json](evidence/native-formulas/results.json) e
[coverage.json](evidence/native-formulas/coverage.json).

La suite completa ha rilevato un esempio PERIOD della guida che riferiva una
colonna assente dal tutorial. L'esempio ora dichiara un modello autonomo;
è stato rieseguito con gli altri esempi, senza cambiare il compilatore per adattarlo.

## Copertura dei 74 modelli e limiti residui

La sonda compila ogni virtuale separatamente, vietando I/O. Non confronta i
risultati di ogni formula con un database e non certifica le policy implicite.

| Tipo | Prima | Dopo | Ancora bloccate |
| --- | ---: | ---: | ---: |
| formulaColumn, 462 | 0 | 159 | 303 |
| aliasColumn, 46 | 39 | 44 | 2 |
| subQueryColumn, 3 | 0 | 0 | 3 |
| bagItemColumn, 3 | 0 | 0 | 3 |
| pyColumn, 12 | 0 | 0 | 12 |

Delle 305 formule SQL testuali, 159 compilano; 134 dipendono da formule fornite
da metodi, 10 da sottoquery native, una richiede `env_user_id` e una usa `#PREF`.
Restano inoltre 134 dichiarazioni dirette `sql_formula=True`, 21 select e 2 exists.
Gli alias bloccati sono `sys.task_execution.task_active_workers` (sottoquery) e
`invc.invoice.discount_tier_id` (virtualRelation).

**Prossimo incremento:** raccordare select/exists/select_* confrontando
correlazioni, default e macro col legacy; poi le formule fornite da metodo.
Restano nel piano RuntimeModel, altre macro, policy native e `*`, catene e
operatori. Non sono approvati nuovi provider, resolver o sintassi per coprirli.

## Riproduzione

Dal repository Asqueel, con PostgreSQL disponibile come per le altre suite:

```sh
PYTHONPATH=src:../asqueel-migration/src venv/bin/python -m pytest -q -o addopts='' tests/native_formulas tests/native_compiler/test_native_formulas.py tests/native_compiler/test_subqueries.py
PYTHONPATH=src:../asqueel-migration/src venv/bin/python -m pytest -q -o addopts=''
PYTHONPATH=src:. venv/bin/python docs/design/probes/native_formula_coverage.py --output /tmp/native-formulas.json
```

Il percorso al checkout sibling di migration serve nell'ambiente locale con
versione installata precedente. Non è una nuova dipendenza del core.
I test portati non richiedono un checkout GenroPy: codice e dati sono congelati
nel repository, con la provenienza nel manifesto.
