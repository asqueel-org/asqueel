# 88 — Fase 2: contenitore SQL e relazioni verso uno

15 ottobre 2026. **Fase 2 completata nel perimetro concordato.**
Riferimento: [piano 86](86-legacy-compiler-logical-phases.md),
[baseline indipendente 87](87-legacy-rewrite-phase1-baseline.md).

## Decisione che cambia il perimetro

Dopo la baseline l'utente ha escluso per ora la compilazione delle relazioni
verso molti tramite JOIN. Non vengono portati exploding rows, DISTINCT implicito,
colonne nascoste di ordinamento o count legati a quel meccanismo.

È riconosciuta la forma `@invoices.operazione(argomenti)`, anche dopo un percorso
verso uno. Il compilatore individua relazione, nome e argomenti testuali, con
parentesi annidate, poi cerca `getattr(self, 'many_' + operation, None)`.
Se manca l'handler solleva `UnsupportedFeatureError` con `not yet supported`.
**Non esiste alcun handler `many_*`**, neanche uno stub. Gli esempi sum, calc,
first e last verificano soltanto riconoscimento e dispatch: non fissano semantica,
default, ordinamenti o firme pubbliche definitive. Anche un nome non ancora
previsto segue lo stesso riconoscimento e rifiuto.

La navigazione semplice `@invoices.total` è esplicitamente non supportata.
Una relazione inversa dichiarata `one_one` resta invece verso uno: il criterio
è la cardinalità descritta dal joiner, non il nome della direzione.

Le due inverse deboli del legacy `invc.invoice.@last_invoice` e
`invc.product.@first_in_invoice` non sono state corrette. Nel percorso precedente
e nel riferimento restano i limiti documentati; nel nuovo percorso ricadono
nel rifiuto generale verso molti, prima del vecchio KeyError.

## Implementazione e corrispondenze

| Riferimento `fa35e5ad` | Nuovo percorso | Cosa viene conservato |
| --- | --- | --- |
| `SqlCompiledQuery`, `get_sqltext` | `sql_compiled_query.SqlCompiledQuery` | Clausole stringa, JOIN ordinate, relationDict e aliasDict; delega dell'assemblaggio all'adapter |
| `compiledQuery` | `_TreeContext.select_plan` | Seed pkey, normalizzazione, raccolta dei riferimenti, embedFieldPars nel WHERE, risoluzione e sostituzione |
| `getFieldAlias` | `_TreeContext.get_field_alias` | Navigazione, campo fisico, ricorsione delle aliasColumn semplici |
| `_findRelationAlias` | `_find_relation_alias` | Attraversamento ricorsivo del vero ramo `DbTableObj.relations` |
| `_getRelationAlias` | `_get_relation_alias` | Chiave composta da percorso fisico e alias di partenza; allocazione prima della risoluzione ON; riuso, direzioni verso uno e chiavi composte |
| `updateFieldDict`, `embedFieldPars`, split/template | Helper esistenti in `_legacy_sql.py` | Algoritmi invariati |
| `adapter.compileSql` | `PostgresDialect.compile_sql`, override SQLite | Assemblaggio di clausole già risolte; quoting e differenze di dialetto negli adapter |
| Preparazione dei parametri | `TreeQueryCompiler.compile_plan` → `driver.prepare_sql` | Una preparazione finale; SQL e kwargs separati, senza esecuzione |

Il nuovo compilatore non eredita `_Context`/`_SelectCompiler` e non passa per
QueryPlan, Fragment o SqlStatement. I test ne impediscono esplicitamente l'uso.
Il compilatore precedente e il suo renderer restano disponibili e invariati;
non esiste un fallback. Nessun grafo relazionale alternativo o cache SQL sul
modello. RuntimeModel, mixin e driver non cambiano.

Gli attributi delle chiavi composte si leggono dalla grammatica nativa esistente
(`columns`, equivalente legacy `composed_of`); non viene aggiunto un mapper
strutturale parallelo. Le condizioni ON vengono elaborate localmente, senza
scrivere `cnd` sul joiner condiviso. Il relativo test controlla anche i riferimenti
aggiunti dall'ON e il prefisso del percorso quando la relazione è annidata.

Il contenitore conserva kwargs e metadati del risultato come dati separati dalle
clausole; non conserva modello, connessione o contesto. Snapshot dell'ambiente,
parametri espliciti e riutilizzo della query mantengono i contratti precedenti.
L'aliasDict usa le stesse chiavi quotate del legacy. Gli alias delle tabelle
rimangono `t0`, `t1`, ecc.; in questa fase non sono introdotti mangler nuovi.

## Verifiche

| Verifica | Risultato |
| --- | --- |
| Suite completa `pytest tests` | **4.290 passati, 13 skip, 24 xfail previsti** |
| Relazioni, dispatcher, condizioni ON e replay originale | **384 passati**: 322 contratti della fase e 62 replay legacy |
| Esecuzione separata di 10 SELECT su PostgreSQL e SQLite | **20 passati**, stessi valori e nomi delle colonne del SQL legacy congelato |
| Confronto completo su 498 richieste per compilatore | **314 supportate** dal nuovo percorso, SQL e kwargs uguali al riferimento |
| SELECT fisiche dei 74 modelli | **148 equivalenti**, due dialetti |
| 144 relazioni native, due dialetti | 146 compilazioni verso uno equivalenti; 138 rifiuti verso molti attesi; 4 rinvii per formule nella chiave |
| ON con nuovi riferimenti e qualificazione del padre | **4 confronti** SQL/kwargs equivalenti; risultati SQLite uguali |
| JSON migration | **74 modelli**, struttura identica all'artefatto precedente |
| Riferimenti ai branch sperimentali | **106 hash AST verificati**, sorgenti invariati rispetto al confronto della fase 1 |
| Ruff `src tests scripts` | Passa |
| Documentazione Sphinx, warning come errori | Passa |
| Mypy | **2 errori preesistenti** nel renderer precedente; nessun errore nuovo |

Le quattro prove ON e le venti prove di esecuzione sono state aggiunte dopo la
suite completa e verificate separatamente. I conteggi delle righe non vanno
sommati: alcune selezioni rieseguono test già presenti nella suite.

I 24 xfail restano stretti e riguardano formule, sottoquery, macro, star, default
e altre clausole delle fasi successive. I casi verso molti sono invece prove
di rifiuto esplicito, non xfail da rendere verdi introducendo righe esplose.
I due riferimenti **verso uno** basati su `last_invoice_id` e `first_product_id`
richiedono le formule della fase 3: non sono spacciati per implementati.

La guida pubblica delle query descrive ora le relazioni verso uno sul nuovo
albero. I due rimandi al rapporto interno R3 sono download espliciti: le note
di design non sono pagine della documentazione pubblicata.

Gli errori mypy sono `Identifier(str | None)` e metadati `ResultColumn | None`
nel renderer QueryPlan preesistente. La verifica tramite shadow-file usa copie
degli adapter anteriori alla fase 2, validate contro gli hash iniziali, e
riproduce esattamente i due errori. Nessuna correzione collaterale al vecchio
percorso è stata inserita.

I CSV `price_year` e `price_year_note` sono copie byte-per-byte del progetto
legacy già usato nella baseline, ora disponibili nei test portabili. Gli oracoli
SQL non sono stati prodotti dal nuovo compilatore: le 144 relazioni derivano
dall'evidenza congelata della fase 1; il piccolo oracolo ON è prodotto dal
compilatore originale con adattamento di fixture esplicitato nel probe.

## Evidenze e riproduzione

- [Confronto completo](evidence/legacy-rewrite-phase2/legacy-comparison.json)
- [Verifica di sorgenti, fixture e migration](evidence/legacy-rewrite-phase2/verification.json)
- [Suite completa](evidence/legacy-rewrite-phase2/asqueel-tests.log)
- [Contratti e replay](evidence/legacy-rewrite-phase2/relations-tests.log)
- [Esecuzione sui due database](evidence/legacy-rewrite-phase2/execution-tests.log)
- [Condizioni ON](evidence/legacy-rewrite-phase2/join-conditions.json)
- [Mypy attuale](evidence/legacy-rewrite-phase2/mypy.log) e
  [riproduzione preesistente](evidence/legacy-rewrite-phase2/mypy-existing.log)

```sh
PYTHONPATH=src:../asqueel-migration/src venv/bin/python -m pytest tests -q -o addopts=
PYTHONPATH=src:.:docs/design/probes venv/bin/python -m pytest \
  tests/object_tree/test_phase2_relations.py \
  docs/design/probes/test_rewrite_phase1_reference.py -q -o addopts=
PYTHONPATH=src:../asqueel-migration/src venv/bin/python -m pytest \
  tests/native_formulas/test_tree_phase2_results.py -q -o addopts=
PYTHONPATH=src:.:docs/design/probes venv/bin/python \
  docs/design/probes/rewrite_phase2_join_conditions.py
```

## Prossimo passo

Fase 3: raccordare formule e sottoquery nel nuovo contesto, rispettando il
perimetro aggiornato. Le operazioni a molti attendono la definizione del primo
handler; il loro riconoscimento non ne autorizza l'implementazione. Filtri
impliciti, star e clausole ancora escluse restano alla fase 4. La fase 2 non
abilita fetch/esecuzione sul nuovo albero.
