# 89 — Fase 3: formule e sottoquery sul nuovo albero

15 ottobre 2026. **Fase 3 completata nel perimetro concordato.**
Riferimenti: [piano 86](86-legacy-compiler-logical-phases.md),
[contratti 87](87-legacy-rewrite-phase1-baseline.md),
[fase 2](88-legacy-rewrite-phase2.md).

## Risultato

Il compilatore gerarchico risolve formule SQL, dipendenze e alias, formule da
metodo, `var_*`, `select`, `exists`, `select_*`, `subQueryColumn` e riferimenti
stringa ai metodi `subquery_*`. Produce SQL e kwargs senza eseguire query.
Le formule possono introdurre JOIN verso uno, riferirsi ad altre formule oppure
compilare SELECT figlie. Queste usano lo stesso algoritmo e il ramo `relations`
del modello effettivo. Non si passa dal compilatore precedente.

Le operazioni verso molti conservano il riconoscimento e il lookup con `getattr`
di `many_*`, anche dentro formule appartenenti a una tabella raggiunta tramite
relazione. **Nessun handler è implementato.** Nessuna conversione automatica di
sottoquery in JOIN, nessun exploding rows o DISTINCT implicito.

## Algoritmi mantenuti e responsabilità

| Riferimento | Raccordo sul nuovo albero |
| --- | --- |
| `fa35e5ad`, `getFieldAlias`, ramo virtuali | `get_field_alias` naviga le relazioni e ricorre su alias/formule; `formula` raccoglie e risolve le dipendenze rispetto alla tabella proprietaria |
| `sql_formula_<nome>(attr)` | `formula_definition` chiama il metodo della tabella proprietaria prima di estrarre `select_*` e `var_*`; copia locale degli attributi |
| `getFieldAlias`, ramo `select_dict` | `subquery` copia la dichiarazione, risolve `#THIS` nel padre e ricompila con un nuovo `_TreeContext` |
| Riferimento stringa `subquery_<nome>()` | Lookup sulla tabella radice della SELECT corrente, come nel legacy; nessun fallback sulla tabella proprietaria della formula |
| `aliasPrefix = '%s_t' % alias` | Alias SQL `t0_t0`, `t1_t0`, `t0_t0_t0`, ecc.; JOIN della figlia locali alla figlia, correlazione nel padre |
| `mangle` dei branch compound/v2/v3/v4 | Sostituzione regex `(:)(\w+)(\W|$)`, con scope testuali separati e allocatore già usato dal port nativo |
| `queryCompile` / adapter `compileSql` | La SELECT figlia restituisce SQL con placeholder nominati; preparazione del driver una sola volta, sul SQL completo |
| `subQueryColumn` già portata | Wrapping scalare e aggregati JSON/XML delegati all'adapter; PostgreSQL supportato, SQLite rifiuta JSON/XML |
| `asTranslator` dell'adapter legacy | Quoting degli alias di risultato distinto dalla validazione dei nomi fisici |

Sono riesaminati il ramo normativo `getFieldAlias` e `_compiledSubQuery` del v4:
quest'ultimo separa esplicitamente `aliasPrefix` e mangler della sottoquery.
Non vengono importati joiner sperimentali, deduplicazione tramite hash, fusione
delle sottoquery o altre semantiche dei branch. L'ordine metodo → attributi →
select/var resta quello normativo, anche dove i branch lo avevano cambiato.
I **106 hash AST** dei riferimenti degli otto snapshot corrispondono alla
ricognizione del piano; [verifica](evidence/legacy-rewrite-phase3/invariants.json).

### Alias e parametri

`SqlBindings` contiene soltanto valori, nomi e stato locale di allocazione.
Non contiene frammenti SQL strutturati, modello, connessione o resolver nuovi.
Riusa le regole di scope del port nativo: prefissi deterministici `fN_` per le
formule e `sN_` per le sottoquery, collisioni evitate rispetto ai nomi già occupati.
Le formule dipendenti hanno i propri locali; le SELECT figlie ereditano i valori
visibili e possono sostituirli localmente. I parametri del chiamante non vengono
confusi con quelli introdotti dalla compilazione.

Questo è il contratto di isolamento già adottato, non un nuovo comportamento:
non si riproducono gli identificatori di processo né le scritture in currentEnv
del legacy. Gli alias SQL non dipendono dal contatore dei parametri. Le SELECT
sorelle possono riusare lo stesso alias SQL nei rispettivi scope mantenendo
kwargs diversi. La sostituzione dell'espressione della formula avviene prima di
inserire il SQL figlio, evitando di manglizzare nuovamente i locali della figlia.

Sono verificati omonimi fra chiamante, formula, dipendenza e due sottoquery;
parametro lista IN e parametro scalare con lo stesso nome; alias annidati;
ricompilazione; ambiente temporaneo e mapping restituiti dai metodi invariati.
Le definizioni sono lette nuovamente a ogni compilazione: nessuna cache sul modello.

### Casi concreti completati

- Le quattro compilazioni verso uno rinviate nella fase 2 per le chiavi formula
  `last_invoice_id` e `first_product_id` ora equivalgono al riferimento. Le due
  inverse deboli restano escluse dal contratto verso molti, come concordato.
- Le SELECT figlie supportano le clausole già previste nelle dichiarazioni:
  ordinamento, limit/offset, GROUP BY/HAVING, DISTINCT e cast scalare. Questo
  non abilita ancora tali clausole esterne oltre il perimetro della fase 2.
- `priced_rows_pct` genera un alias interno lungo: il precedente uso della
  validazione dei nomi fisici lo rifiutava. È ripristinata la delega legacy
  `asTranslator`, che quota l'alias lasciando al DB il limite di lunghezza;
  nessuna troncatura o rinomina inventata dal compilatore. La query originale
  ora compila ed è eseguita su PostgreSQL.
- Le formule di sistema da metodo già esistenti leggono `virtual_columns` nel
  nuovo albero. Il metodo della tabella e la composizione CASE rimangono gli
  stessi; test dedicato anche con una regola dichiarata.
- XML da riferimento stringa continua a essere rifiutato: il legacy richiede
  le colonne della query nel mapping al momento della dichiarazione. Gli altri
  modi non ricevono semantiche nuove.

RuntimeModel e mixin rimangono separati. I test dei metodi associano funzioni
alla SqlTable esistente; non installano un nuovo sistema di classi o mixin.
La prova sulla dichiarazione effettiva verifica che un cambiamento sia letto
alla compilazione successiva, **non certifica un RuntimeModel completo**.

## Verifiche e provenienza dei test

| Verifica | Esito |
| --- | --- |
| Suite completa, inclusi PostgreSQL e migration | **4.516 passati, 21 skip, 10 xfail previsti** |
| Corpus formula/sottoquery sul nuovo albero + confronto dei risultati con il SQL congelato | **170 passati, 8 skip storici, 2 xfail** |
| Metodi, ricorsione, isolamento, rifiuti e unica preparazione finale | **38 passati**, entrambi i dialetti, I/O impedito |
| Confronto su 498 richieste per compilatore | **334 supportate**: 332 SQL/kwargs equivalenti dopo normalizzazione di layout e quoting alias; 2 equivalenti normalizzando soltanto l'identità dei parametri locali |
| 74 tabelle fisiche, due dialetti | **148 equivalenti** |
| 144 relazioni native, due dialetti | **150 verso uno equivalenti**, 138 verso molti rifiutate |
| Prove focalizzate sul SQL congelato | **36 esecuzioni** PostgreSQL/SQLite con stessi valori e nomi di colonna |
| JSON migration | **74 modelli**, identico al JSON nativo precedente |
| Ruff, Sphinx strict | Passano |
| Mypy | Soltanto i **2 errori preesistenti** nel renderer QueryPlan precedente |

I conteggi si sovrappongono: non sommare le righe della tabella.
[Log suite](evidence/legacy-rewrite-phase3/full-suite.log),
[risultati](evidence/legacy-rewrite-phase3/legacy-results.log),
[confronto dettagliato](evidence/legacy-rewrite-phase3/legacy-comparison.json),
[riepilogo e skip](evidence/legacy-rewrite-phase3/comparison-summary.json).

I corpi dei 144 test del corpus nativo derivato dal legacy vengono riusati senza
riscriverne le asserzioni. Fonti, hash e adattamenti precedenti restano nei
rapporti [60](60-native-sql-formulas.md), [61](61-native-subqueries.md),
[62](62-native-method-formulas.md), [66](66-native-subquery-columns.md).
Le sette prove condivise sui metodi stringa vengono riusate su entrambi i dialetti:
sono i contratti eseguiti sugli otto snapshot nel
[rapporto 67](67-native-subquery-methods.md), non test storici inesistenti.

La fixture di esecuzione della fase 3 specifica filtri disattivati e nessun
ordinamento di tabella implicito; conserva ogni ordine esplicitamente richiesto.
Il suo count di controllo conta le righe degli id restituiti. Si tratta di un
adattamento di fixture esplicito per isolare formule/sottoquery dalla fase 4:
non vengono implementati fetch/count sul percorso gerarchico. Le esecuzioni
passano SQL già compilato a una connessione separata; la compilazione sul nuovo
albero non apre connessioni. Gli oracoli legacy non sono modificati.

Gli otto skip sono ereditati dal corpus storico, inclusi cinque su EXISTS
SQLite: non indicano un nuovo rifiuto del compilatore. Il dispatch EXISTS viene
verificato separatamente anche su SQLite. I dieci xfail restanti sono otto
contratti della fase 4 (group/star/macro/default, due dialetti) e due combinazioni
JSON/XML con DISTINCT esterno. Nessun fallimento imprevisto è nascosto.

## Rimane alla fase 4

Options e filtri impliciti, espansione `*`, bagItemColumn, macro e completamento
delle clausole esterne già concordate. Le formule che ne dipendono restano
esplicitamente non supportate. Restano rinviati operatori, query concatenate,
pyColumn, #PREF e tutte le operazioni verso molti senza handler.

Il compilatore precedente, i driver, il renderer del modello e gli oracoli
rimangono invariati. Il nuovo percorso resta selezionato con `objects_tree`;
nessun cambio del default, release, commit o push in questa fase.
