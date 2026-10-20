# 77 — Fase 0 e SELECT minima sul modello gerarchico

14 ottobre 2026. Completate le fasi 0 e 1 del [piano 76](76-hierarchical-compiler-plan.md).
Il nuovo albero produce SQL e kwargs con la firma query esistente, senza esecuzione.
Il renderer predefinito rimane `objects`; il percorso nuovo è ancora esplicito.

## Fase 0: contratti e differenze

La baseline generale precedente è quella del rapporto 75: 2.300 passati,
13 saltati. All'inizio di questo passo la selezione native_compiler più binding
ha dato 487 passati e 13 errori di setup PostgreSQL: il sandbox impediva la
connessione loopback. Non erano regressioni né skip. La suite completa è stata
poi eseguita con accesso al PostgreSQL locale delle fixture.

La [sonda legacy](probes/test_legacy_minimal_select.py) compila senza connessioni
sugli otto snapshot del rapporto 59: **6 passati per snapshot**, 48 complessivi.
Questo esercita il compilatore predefinito di ogni snapshot, non tutti i factory
alternativi. Non si rieseguono qui tutte le suite legacy di formule e relazioni.

| Contratto | Riferimento legacy e copertura esistente | Esito nel nuovo percorso |
| --- | --- | --- |
| Colonne fisiche e nomi SQL | getFieldAlias, ramo finale alias + adapted_sqlname; TestPhysicalColumns.single_column e multiple_columns, PG/SQLite | Portate le query dei quattro test; asserzioni di compilazione, nomi e proiezioni |
| AS, CASE, COALESCE, WHERE, ordine, limite/offset | compiledQuery: raccolta riferimenti, risoluzione, sostituzione, clausole; sonda su tutti gli snapshot | Supportati usando oggetti gerarchici, scanner e piano esistenti |
| Date, Decimal, None e placeholder | sqlparams legacy; test_compile_only e test_compiler Asqueel | Conservati i tipi; parametri/input_parameters coerenti, nessuna interpolazione dei valori |
| Riuso e mangling | Stato locale del compilatore; _Bindings e contratti già portati | Un contesto per compilazione, collection e collisioni, ambiente riletto; nessuno stato SQL nel modello |
| Pkey aggiunta automaticamente | Legacy addPkeyColumn=True; checklist 58: da decidere | Nessuna decisione nuova: proiezioni esplicite come nel contratto Asqueel corrente. La sonda legacy usa addPkeyColumn=False per rendere il confronto equivalente |
| Alias automatici di espressioni, $pkey simbolico, group_by='*' | Convenzioni legacy non tutte raccordate | Non acquisiti: AS esplicito per espressioni; $pkey non è introdotto come pseudocolonna |
| Ordine predefinito della tabella | compiledQuery usa order_by della tabella se non c'è un ordine esplicito | Da raccordare/decidere come indicato nella checklist 58; errore esplicito quando richiesto implicitamente. Trovato su 11 tabelle native |
| Draft, cancellazione logica, partition | Rapporti 65 e 75; marcatori prodotti dalle options | Rinviati alla fase 5 del raccordo: se richiesti, errore. Sono utilizzabili i bypass già esistenti excludeDraft=False, excludeLogicalDeleted=False, ignorePartition=True |
| JOIN e inverse ordinarie | getFieldAlias → _findRelationAlias → _getRelationAlias; rapporto 63 | Fase 2; nessun fallback a Relation del modello precedente |
| Alias/formule/var_*, metodi | Rapporti 60–62, 67 e manifest della baseline 59 | Fase 3; errore esplicito se una virtuale/composita viene usata |
| Sottoquery/select_*/subQueryColumn/bagItemColumn | Rapporti 61, 66, 67, 69 | Fase 4; scope separati da preservare nel porting |
| Star, macro, options e filtri | Rapporti 64–65 | Fase 5; non abilitati incidentalmente dal riuso del compilatore |
| DISTINCT esplicito, GROUP BY/HAVING, FOR UPDATE e count | Già coperti nel percorso precedente; non inclusi nella SELECT minima | Non abilitati sul nuovo percorso in questo incremento |
| DISTINCT implicito, righe esplose, condizioni JOIN speciali | Gate del piano 76 | Nessuna decisione implicita; riesaminare prima della semantica interessata |
| Mixin e RuntimeModel | Decisioni separate nel piano 76 | Nessun caricamento, overlay o nuova API |
| Query concatenate/operatori, pyColumn, #PREF e altri rinvii | Documento 41 e piano 76 | Rimangono rinviati |

Il port dei quattro test fisici conserva le richieste originarie, ma non finge
che un test compile-only verifichi `len(rows)==5/3` e contenuti delle righe:
quelle asserzioni restano nella baseline runtime originale del rapporto 59.
La sonda aggiuntiva congela SQL, valori NULL, tipi e parametri; il confronto
fra i due percorsi Asqueel verifica anche tutti i metadati ResultColumn.

## Quale algoritmo viene riusato

Il riferimento per il campo fisico è il ritorno di getFieldAlias nel legacy,
`gnrsqldata/compiler.py:454`: alias della tabella e nome SQL della colonna.
Lo stesso ramo è presente in compound:505, v3/merged:489, v4:490,
simplify:461 e next:454. In v2 ColumnCompiler.compile separa quel lavoro,
mentre AliasManager governa gli alias; non si importa la conversione automatica
dei many in aggregazioni. Riferimenti e commit completi nel rapporto 76.

Nel nuovo codice `_TreeContext.field` legge direttamente DbColumnObj.sqlname;
`table_ref` usa DbTableObj.sqlschema/sqlname. Gli identificatori vengono quotati
dal dialetto già presente. Non si ricostruiscono ResolvedModel, Table o Column.
Il ramo relations non viene ancora attraversato per generare JOIN.

Non è una copia integrale del compilatore legacy. Si mantiene il contratto
Asqueel già verificato per scanner, Identifier/Parameter, _Bindings, QueryPlan,
dialetti e formatter. Motivo: non rimanglizzare SQL già trasformato e non
sostituire queste parti con il mangling regex/object-id dei branch sperimentali.

`_SelectCompiler` raccoglie i tre metodi già esistenti select, plan_select e
compile_plan. Sono estratti senza modifiche algoritmiche. Nel contesto esistente,
la proiezione delega soltanto lettura dei metadati ed espansione star a metodi
separati; sul nuovo modello star è ancora rifiutato. La verifica AST delle parti
riusate è in [algorithm-reuse.json](evidence/hierarchical-select/algorithm-reuse.json).
Non è una prova di equivalenza dell'intero compilatore: i test la completano
nel perimetro indicato.

Il compiler nuovo è creato al primo accesso a db.compiler: il solo binding
del database continua a non creare un compilatore. Tabelle, colonne, options,
relazioni e proiezione migration restano gli oggetti già costruiti dal renderer.
`query.execute/fetch/count` sul nuovo albero sono ancora rifiutati prima dell'I/O.
Le scritture e record rimangono bloccati. Nessun metodo viene installato come mixin.

## Utilizzo nel perimetro minimo

```python
from asqueel import SqlDatabase, SqlDatabaseConfig
from asqueel.configuration import _owned_handler

source = SqlDatabaseConfig()
root = source.source.db('example', implementation='postgresql')
pkg = root.packages().package('sales', sqlschema='sales', sqlprefix=True)
table = pkg.table('invoice', pkey='id')
table.column('id', dtype='L')
table.column('total', dtype='N')

model = source.render(mode='objects_tree')
# Il binding esplicito esistente; _owned_handler resta un helper interno.
with SqlDatabase(model=model, config=_owned_handler(source)) as db:
    query = db.table('sales.invoice').query(
        columns='$id AS code, COALESCE($total,0) AS amount',
        where='$total >= :minimum', minimum=100,
        order_by='$total DESC, $id', limit=3)
    compiled = query.compiled
    sql, kwargs = compiled.sql, dict(compiled.params)
```

La chiamata non connette e non esegue SQL. Nel census di test_invoice_pg si
elencano esplicitamente tutte le colonne fisiche, si specifica un ordine e si
disattivano esplicitamente i filtri non ancora portati. Questa è una verifica
mirata del raccordo, non una raccomandazione a disattivarli nell'applicazione.

## Verifiche

- Sonda legacy: 6 casi × 8 snapshot, PostgreSQL/SQLite, con execute, socket e
  sqlite3.connect vietati. SQL e parametri del riferimento conservati nelle evidenze.
- 209 test della SELECT gerarchica, inclusa uguaglianza integrale CompiledQuery
  sulle 74 tabelle **per entrambi i dialetti**; 789 colonne fisiche per dialetto.
- 80 test del binding: identità degli oggetti, nessuna ricostruzione e nessuna I/O.
- Nessun ripiego verso resolve_model/QueryCompiler precedente; compilazione anche
  dopo distacco della source; attributi e ramo relations non mutati.
- Nomi quotati e mapping SQL, CASE/COALESCE/CAST, stringhe/commenti protetti,
  collection vuote, parametri mancanti, riuso e collisioni; errori per i passi rinviati.
- Suite completa: **2.507 passati, 13 saltati**. Dopo l'ultima rifinitura che
  riusa column_ui e i due casi di guardia aggiunti: **289 passati** nella suite
  SELECT/binding sullo stato finale (209 + 80). Non si sommano questi conteggi.
- Ruff sui file toccati e mypy sui 57 moduli sorgente.

Comandi, risultati finali e impronte dei file sono in
[verification.json](evidence/hierarchical-select/verification.json).
Il prossimo passo rimane la fase 2: navigazione del ramo relations secondo gli
algoritmi legacy, con i gate semantici del piano 76 ancora aperti.
