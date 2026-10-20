# 91 — Count sul nuovo albero

Aggiornamento successivo: i terminali di esecuzione fetch/count sono ora raccordati;
vedi il [rapporto 92](92-hierarchical-fetch-count.md). Questo rapporto conserva
lo stato del precedente passo di sola compilazione.

15 ottobre 2026. Raccordato il ramo di compilazione count usando
`SqlCompiledQuery`, SQL e kwargs separati e una sola preparazione finale negli
adapter. Nessuna nuova sintassi, nessun handler `many_*`.

## Algoritmo di riferimento

`SqlQueryCompiler.compiledQuery` del legacy `fa35e5ad`, righe 939–946:

1. L'espansione di star precede il ramo count.
2. Count elimina sempre l'ordinamento.
3. Con GROUP BY, sostituisce le proiezioni con le colonne di raggruppamento.
4. Con DISTINCT, mantiene la proiezione originale.
5. Altrimenti usa `count(*) AS "gnr_row_count"`.
6. Prosegue nel normale percorso di filtri, riferimenti, formule, JOIN,
   sostituzione e assemblaggio. Non aggiunge la pkey né `_isdeleted`.

Il ramo ha lo stesso AST negli otto snapshot esaminati: legacy, compound, v2,
v3, v3_merged, v4, simplify e next. File, righe, hash e codice sono registrati in
[evidence/legacy-tree-count/branches.json](evidence/legacy-tree-count/branches.json).

I corpi dei test portati sono verificati con hash AST nel
[manifest dei test](evidence/legacy-tree-count/ported-tests.json); nei branch
che li contengono sono identici, le assenze sono registrate esplicitamente.

Il compilatore non introduce un `SELECT count(*) FROM (...)`: nel legacy il
terminale `SqlQuery.count` conta le righe per GROUP BY e DISTINCT; per il caso
semplice legge `gnr_row_count`. Questa distinzione viene conservata.

## Raccordo

`TreeQueryCompiler.plan_count` restituisce `SqlCompiledQuery`;
`TreeQueryCompiler.count` restituisce il consueto `CompiledQuery` con SQL e kwargs
preparati. Il ramo count sta nello stesso contesto della SELECT e riusa la
risoluzione del ramo relations e gli scope delle formule. La query originale e
il modello non vengono modificati. I parametri di ambiente vengono riletti a
ogni compilazione e la preparazione del driver avviene una sola volta.

L'esecuzione tramite `SqlQuery.count()` sulla tabella gerarchica resta disabilitata,
come fetch: questo incremento riguarda il compilatore. I test eseguono il SQL
compilato tramite una connessione separata e interpretano il risultato con le
stesse due regole del terminale legacy. Il vecchio compilatore resta invariato.

### Semantiche conservate, non corrette incidentalmente

- Una proiezione aggregata senza DISTINCT/GROUP BY viene sostituita da COUNT(*):
  non si impone la regola aggiuntiva `count() == len(fetch())`.
- `group_by='*'` viene normalizzato prima del ramo count, come nel legacy.
- LIMIT/OFFSET rimangono nelle clausole. Per esempio OFFSET può eliminare la
  singola riga di COUNT(*). Non si importa il rifiuto di paginazione del vecchio
  compilatore Asqueel, che non era l'algoritmo legacy.
- Le proiezioni sostituite dal count semplice non producono JOIN. Le relazioni
  verso uno in WHERE, GROUP BY, HAVING e DISTINCT seguono il percorso ordinario.
- Le chiamate verso molti vengono riconosciute e rifiutate se manca `many_*`.
  Nessuna implementazione di aggregatori o di righe esplose.

## Test e prove

- **8 test originali legacy**: conteggio customer, draft, GROUP BY e DISTINCT,
  su SQLite e PostgreSQL. Eseguiti nel legacy e portati senza cambiare i corpi.
- **46 contratti congelati** esclusivamente dal legacy, prima di modificare il
  compilatore: 23 casi per dialetto. SQL e kwargs confrontati, ammettendo solo
  layout e quoting già concordato degli alias tabella.
- Gli stessi 46 casi eseguiti su entrambi i database, confrontando righe, nomi
  delle colonne e conteggio interpretato come nel legacy.
- Rifiuto delle operazioni verso molti, pkey automatica esclusa, riuso della
  query, binding locale e snapshot d'ambiente; compilazione senza I/O su tutti
  i **74 modelli per entrambi i dialetti**, comprese le tabelle con pyColumn
  statiche che il count semplice non deve valutare.
- Il supporto di test condiviso ora usa il vero compilatore count del nuovo
  albero; non simula più count tramite `len(fetch())`.

La baseline precedente al raccordo è di 56 fallimenti per il metodo count assente,
conservati in [baseline.log](evidence/legacy-tree-count/baseline.log).
Prove: [contratti](evidence/legacy-tree-count/contracts.log),
[test originali](evidence/legacy-tree-count/original-tests.log),
[esecuzione](evidence/legacy-tree-count/runtime.log),
[regressione completa](evidence/legacy-tree-count/full-suite.log).

## Esito finale

**4.915 test passati, 21 skip, 2 xfail**, nessun fallimento inatteso (200,20 secondi).
I due xfail preesistenti riguardano l'ordine di star per sys_fields, non count.
Le verifiche mirate comprendono 60 test senza I/O e 74 test di esecuzione
(46 confronti, 8 corpi originali portati, 20 regressioni options/Bag).
Ruff e Sphinx con warning come errori passano. Mypy mantiene esclusivamente i due
errori già noti in dialects/postgres.py, righe 127 e 367. JSON migration identico
sui 74 modelli. Nessun commit, bump o push in questo incremento.
