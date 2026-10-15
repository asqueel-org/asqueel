# 61 — Sottoquery native select, exists e select_*

14 ottobre 2026. Continuazione del [raccordo SQL/var_*](60-native-sql-formulas.md),
nel passo 6 del [piano del compilatore](56-read-compiler-plan.md).

**Raccordate le dichiarazioni native `select`, `exists` e `select_*`**, usando
la normalizzazione e il compilatore già presenti. Nessuna nuova firma o
sintassi sperimentale. L'obiettivo resta SQL e kwargs, senza I/O durante la
compilazione; i test di accettazione eseguono poi il risultato per verificarlo.

## Algoritmi confrontati e scelte

I commit congelati sono nell'[inventario legacy](evidence/formula-baseline/inventory.json).
I percorsi seguenti sono relativi a `gnrpy/gnr/sql/gnrsqldata/`.

| Riferimento | Punto esaminato | Riuso / confine |
| --- | --- | --- |
| Legacy `fa35e5a` | `compiler.py`, ramo `getFieldAlias`, righe 395–424 | Definizione dal modello, select/exists e nomi `select_*`, correlazione `#THIS`, cast, default di visibilità e assenza di pkey/ordine impliciti |
| v2 `68f35b9` | `_compiled_sub_query`, righe 547–595; mangler del compilatore, righe 1027–1045 | Ogni sottoquery riceve un proprio scope; i parametri confluiscono nella query esterna dopo essere stati distinti |
| v4 `38d210c` | `_preprocess_subqueryes`, righe 696–733; `_compiledSubQuery`, righe 800–842 | Stessa separazione dei mangler; non importati conversione a JOIN, fusione tramite hash o rendering lazy |
| v4 | `subquery_utils.py::normalize_subquery_dict` | Letta la conversione in-place verso join_to/join_from/join_condition; non adottata: introdurrebbe sintassi e trasformazioni non concordate |
| simplify `13b8918`, next `12cfdcc` | Rami select/exists/select_* del compilatore e test del corpus | Continuità del percorso inline; le dichiarazioni non diventano oggetti runtime nuovi |

Gli esperimenti v2/v4 sono utili per separare proprietà della query e scope dei
parametri. Non viene ripreso il calcolo di identità delle sottoquery attraverso
sostituzioni testuali dei valori nel WHERE: non serve al raccordo e rischierebbe
di confondere equivalenza SQL, valori e scope. Nessuna deduplicazione delle
sottoquery o aggregazione automatica è stata introdotta.

## Implementazione

`_formula_definition` normalizza anche le dichiarazioni native, quando richieste
dal compilatore. `_Context.subquery` continua a gestire correlazione, scope del
figlio, proiezione scalare/EXISTS e cast. Riferimenti a metodi restano errori
espliciti; lo spelling alternativo `subqueries` non viene abilitato da questo passo.

La costruzione della SELECT è stata estratta dal precedente `plan_select` in
`_Context.select_plan`, usato sia dalla query principale sia dai figli.
Rimangono un solo algoritmo e gli stessi controlli per WHERE, GROUP BY, HAVING,
DISTINCT, ORDER BY, LIMIT/OFFSET e policy. Non sono stati ricopiati questi
algoritmi in un compilatore parallelo delle sottoquery.

Per i mangler resta `_Bindings`: i nomi emessi sono prenotati nell'allocatore
comune; valori e usi scalare/lista mantengono la propria origine. Alias SQL e
parametri locali sono responsabilità separate. Il figlio conosce il contesto
esterno per `#THIS`; le sue relazioni usano invece gli alias del figlio.
Una relazione dopo `#THIS` aggiunge il JOIN al contesto proprietario esterno.
Non vengono modificati source, definizioni, modello o `currentEnv`.

Le sottoquery sono renderizzate dal dialetto in frammenti strutturati. La
formattazione dei binding del driver avviene una sola volta alla fine: è
verificato anche il caso di `%` e riferimenti dentro stringhe/commenti.

## Default riallineati al legacy

| Opzione nella sottoquery | Default |
| --- | --- |
| ignorePartition / ignore_partition | **True** |
| excludeDraft / exclude_draft | False |
| excludeLogicalDeleted / exclude_logical_deleted | False |
| addPkeyColumn | False |
| ignoreTableOrderBy | True |
| subtable | `*` |

**Correzione di comportamento rispetto al precedente percorso Asqueel:**
prima la sottoquery applicava implicitamente la partition. Ora segue il legacy
sia nei package nativi sia nel percorso schema/table. Per richiedere quel filtro
occorre dichiarare `ignorePartition=False`; il contesto richiesto viene allora
verificato. Il default della SELECT principale rimane invariato.

Una fixture di accettazione DISTINCT richiedeva conteggi partizionati:
ora lo dichiara esplicitamente. Le sue asserzioni non sono cambiate.
Gli altri test verificano separatamente il default legacy e gli override.
Questo non completa il raccordo delle options native alle policy: i test di
policy usano le dichiarazioni `x_partition` e i marker già supportati.

Non viene inserito LIMIT 1. Una sottoquery scalare deve proiettare una colonna;
il numero di righe dipende dal SQL e dai dati. PostgreSQL solleva un errore se
le righe sono più di una; SQLite mantiene il proprio comportamento. Un
`select_*` dentro `ARRAY(...)` può invece produrre più righe, sempre con una
colonna. Non vengono aggiunti array, JSON, aggregazioni o default di cardinalità.

## Test e provenienza

`tests/native_formulas/test_legacy_subqueries.py` porta **39 casi** da
`gnrpy/tests/sql/test_compiler_coverage.py`: **34 superati e 5 skip originali**.
Sono coperti conteggi, somme, select ordinati con limit, EXISTS, formule
dipendenti, sottoquery nominate, CASE/COALESCE con più select, GROUP BY/HAVING,
ARRAY e STRING_AGG PostgreSQL, WHERE/ORDER BY e query combinate.

Il [manifesto](../../tests/native_formulas/legacy-subqueries-manifest.json)
registra commit, righe, hash originali/portati e corrispondenze nei branch.
Le asserzioni sono state confrontate via AST e conservate. Un solo test adatta
`readColumns` e la pkey implicita alle API già disponibili: query/fetch scalare
e `$id AS pkey`; non cambia il compilatore per introdurre quelle convenzioni.

Le definizioni selezionate coincidono nei riferimenti legacy, v3 merged, v4,
simplify e next. Non sono cinque corpus indipendenti. I test sperimentali
eager/lazy, inline/JOIN e RuntimeModel di v2/v4 sono stati esaminati, ma non
vengono dichiarati portati né simulati disattivando i loro flag.

Altre verifiche:

- 36 casi compile-only sui due dialetti, vietando connessioni ed esecuzione:
  annidamento, proprietario di `#THIS`, JOIN interni/esterni, alias, parametri
  omonimi e collezioni, riuso, ambiente, cicli, limiti e clausole non ammesse.
- 12 casi PostgreSQL di accettazione della stessa suite sui percorsi schema
  e package: risultati, dtype, correlazioni, policy, cast, cardinalità ed errori.
- Quattro casi sui dati originali verificano conteggi/somme/righe vuote ed
  EXISTS su PostgreSQL e SQLite. Gli skip SQLite del legacy restano storici:
  non descrivono un limite di EXISTS in Asqueel.

La fixture ora conserva anche i nomi fisici degli schemi: alcune formule legacy
contengono SQL esplicito come `invc.invc_invoice_note`. PostgreSQL usa un database
temporaneo dedicato, eliminato al termine; SQLite file temporanei. Non è stato
riscritto il SQL applicativo per adattarlo agli schemi di test. Gli otto CSV e
le dichiarazioni dei modelli rimangono quelli del corpus precedente.

Suite completa: **1.553 superati, 9 saltati**, senza errori o fallimenti.
Ruff, mypy e Sphinx con warning trattati come errori superati; esiti per test
e hash dei sorgenti sono in
[results.json](evidence/native-subqueries/results.json).

## Copertura dei 74 modelli nativi

La [sonda senza I/O](evidence/native-subqueries/coverage.json) passa da
**159 a 187 formulaColumn** compilabili e da **44 a 45 aliasColumn**.
Tra le dichiarazioni dirette, compilano 16 select su 21 e tutti e 2 gli exists;
compilano inoltre le cinque formule con select_* e le relative dipendenze.

Restano cinque select che richiedono relazioni inverse, non ancora supportate:
`sys.widget.child_count`, `adm.htag.child_count`, `adm.menu.child_count`,
`invc.product_group.child_count`, `invc.product_type.child_count`.
Le altre formule bloccate sono 134 metodi, 134 dipendenze da metodi,
un parametro d'ambiente mancante nella sonda e `#PREF`.
L'alias residuo dipende da virtualRelation. subQueryColumn, bagItemColumn,
pyColumn e RuntimeModel restano nei rispettivi passi del piano.

La compilazione di tutte le dichiarazioni supportate non certifica i risultati
su tutti i dati di ogni package. In particolare la cardinalità di select scalari
non aggregati, o con GROUP BY, resta una proprietà della dichiarazione e dei dati.
Non viene corretta inventando un LIMIT o trasformando la query in JOIN.

## Riproduzione

```sh
PYTHONPATH=src:../asqueel-migration/src venv/bin/python -m pytest -q -o addopts='' tests/native_formulas tests/native_compiler/test_native_subqueries.py tests/application_integration/test_formula_subqueries.py
PYTHONPATH=src:../asqueel-migration/src venv/bin/python -m pytest -q -o addopts=''
PYTHONPATH=src:. venv/bin/python docs/design/probes/native_formula_coverage.py --output /tmp/native-subqueries.json
```

Il percorso sibling di migration serve alla configurazione locale di test,
non introduce dipendenze nel compilatore. Il port non richiede il checkout legacy.
