# 57 — Refactor legacy e conversazioni SQL archaeology

14 ottobre 2026. Indagine richiesta prima di implementare il
[piano 56](56-read-compiler-plan.md). Lettura dei sorgenti Git e delle
conversazioni locali; nessuna modifica del compilatore GenroPy o Asqueel.
Non sono state rieseguite le suite dei branch: le verifiche statiche sotto
non attestano la correttezza end-to-end degli esperimenti.

## Risultato per il nostro obiettivo

I branch contengono precedenti concreti per separare risoluzione delle colonne,
alias, relazioni e sottoquery. Non costituiscono però un'implementazione pronta
di `query(...).query(...)` con relazioni accessibili dalla proiezione.
Nei cinque rami v2, v3, v4, compiler-simplify e compiler_next_step_1 esaminati,
la classe `SqlQuery` non dichiara un metodo `query`: verifica eseguita con AST.

Il punto da recuperare è il contesto del modello durante la compilazione,
prima di ridurre tutto a testo SQL. Le classi sperimentali non impongono nomi
o API ad Asqueel; alcune mescolano separazione architetturale e cambiamenti di
semantica che non fanno parte del lavoro concordato.

## Branch verificati

Riferimenti letti dal clone GenroPy con `git show`, senza checkout. Le date
sono dei commit di testa locali. Non sono stati effettuati fetch o verifiche
GitHub live sullo stato delle PR.

| Riferimento | Commit | Contenuto utile e limite |
| --- | --- | --- |
| `sql_review/subquery_refactor_v2` | `68f35b99c440df3658d275f3403f10962a953be6`, 19 febbraio | `CompiledColumn`, `ColumnCompiler`, `AliasManager`, `SubqueryEntry`; rendering differito. Stato ancora condiviso; aggregazione automatica dei percorsi many |
| `origin/feature/subquery_refactor_v3` | `67bba0e59183f6df2b3463064c9feb2c21be225e`, 19 febbraio | `SqlCompiledSubQuery`, preprocessing formule, conversione sottoquery → join e query composte; non la stessa decomposizione di v2 |
| `sql_review/subquery_refactor_v3_merged` | `19da337f4632cc69897c9373aa263dcb49abc293`, 26 febbraio | Continuazione con `sql_aggregate`; il nome del ramo non certifica l'integrazione nel develop corrente |
| `sql_review/subquery_refactor_v4` | `38d210c376abaa390619c2b16985318921d6dd1d`, 28 febbraio | `normalize_subquery_dict`, separazione di collegamento e filtro; parser limitato e modifica in-place |
| `sql_review/compiler-simplify` | `13b891883487e8948921eb6694e14f8e51bc464d`, 27 febbraio | Copia `compiler_new`, albero relazioni esteso alle virtuali, selezione tramite `use_new_compiler`; commit WIP |
| `compiler_next_step_1` | `12cfdcce86337119591b6c8247e7166d831c08b9`, 22 settembre | Copia indipendente e test che consentono la futura divergenza; corpi dei metodi ancora uguali al legacy dello stesso commit |

Le classi principali sono in `gnrpy/gnr/sql/gnrsqldata/compiler.py` dei
rispettivi riferimenti. Le eccezioni sono `compiler_new.py`, `compiler_next.py`
e `subquery_utils.py`. Il precedente della UNION è già verificato nel piano 56.

### v2: separazione utile, origine delle colonne ancora insufficiente

`ColumnCompiler.compile(fieldpath, curr, basealias, parent)` attraversa l'albero
delle relazioni, risolve il campo sul modello e genera i join necessari.
`AliasManager` identifica i join tramite percorso e alias di partenza: due
relazioni verso la stessa tabella non vanno fuse solo per destinazione.

`CompiledColumn` prevede `sql_expression`, `is_many`, `dtype`, `aggregator`,
`field_key`. Tuttavia i rami fisico/formula restituiscono `CompiledColumn(expr)`:
quei campi non sono una descrizione completa e popolata dell'origine. Inoltre
`getFieldAlias` restituisce solo `.sql_expression`, ricopiando `_curr`, `_alias`
e `_curr_tblobj` dal collaboratore al compilatore principale.
L'estrazione di una classe non ha quindi eliminato gli effetti collaterali e
non risolve già il nostro `@customer_id.name` dopo una SELECT derivata.

`SubqueryEntry` rimanda il rendering tramite segnaposto testuali. Il file
`projects/test_invoice/tests/test_torture_compiler.py` dichiara due `xfail`:

- `test_sales_from_local_state_join_mode`: correlazione via `#THIS.@relation`
  che richiederebbe LATERAL;
- `test_customer_all_formulas`: segnaposto residuo quando una formula dipende
  da `#THIS.top_product_id`.

Test letti, non rieseguiti. Non dimostrano supporto a LATERAL; forniscono casi
per verificare dipendenze e assenza di residui nel SQL finale.
La conversione automatica dei percorsi many in aggregati scelti dal tipo è un
mutamento semantico: non viene acquisita come parte necessaria del refactor.

### v3/v4: sottoquery compilata e riscrittura in join sono distinte

`SqlCompiledSubQuery` conserva clausole prima del rendering. Le funzioni
`_handleFormulaColumn`, `_preprocessFormula` e `_compiledSubQuery` separano
parte della gestione di formule e binding dal metodo principale.

La conversione in join resta una strategia sperimentale: riconosce una
correlazione testuale, aggiunge una chiave alla proiezione e può cambiare GROUP
BY. `_condense_subqueries` raggruppa per tabella e WHERE; `_identity_hash`
considera tabella, WHERE con sostituzioni testuali dei valori e GROUP BY.
Non assumere che bastino per l'equivalenza: ordine, limite, binding e altre
clausole richiedono verifiche specifiche. Questa ottimizzazione non entra nel piano.

In v4 `normalize_subquery_dict` trasforma in-place la forma iniziale
`$fk=#THIS.id AND ...` in `join_to`, `join_from`, `join_condition`, rimuovendo
WHERE. Usa una regex, non una risoluzione generale dei predicati. Questi nomi
sono un esperimento del branch, non nuove firme approvate per Asqueel.

### compiler-simplify e compiler_next

`compiler-simplify` inserisce tutte le virtuali nell'albero delle relazioni,
inclusi gli attributi corretti della virtuale quando porta una relazione.
Conferma il bisogno di interrogare un modello completo durante la compilazione;
non risolve la ricostruzione dell'origine dalla stringa SQL finale.

In `compiler_next_step_1` la verifica AST dei corpi di tutti i metodi di
`SqlQueryCompiler` e `SqlQueryCompilerNext`, escludendo le docstring, non trova
differenze o metodi aggiunti. `test_compiler_next_sync.py` verifica separazione
delle classi e superficie dei metodi, rinviando al corpus di confronto SQL per
la parità del comportamento. Il percorso alternativo consente il lavoro futuro:
non prova che il nuovo compilatore semantico sia già realizzato.

## Conversazioni recuperate

Fonti lette direttamente dall'archivio delle sessioni, oltre ai riassunti in
`docs/legacy-sql-compiler-analysis.md`:

- **SQL archaeology**, sessione `2dbca0a1-399f-48cd-b01f-4d8ad9b701e3`,
  settembre, progetto locale `sql-archaeology-cc8c6d`. Il messaggio utente del
  20 settembre alle 08:22 UTC richiede espressioni utilizzabili ovunque, anche
  ridisegnando il compilatore. La discussione precisa un risolutore coerente per
  colonne, filtri, ordinamento e altre clausole. I messaggi successivi separano
  aggregati, relazioni filtrate e attivazione del percorso alternativo.
- **Alt-compiler apphandler fase 6**, sessione
  `0cd4ee6b-45ab-4d3a-8f54-9899d42aef16`, 21 settembre. Distingue operazioni di
  riga da aggregazioni su relazioni; richiede di leggere le GEP in successione
  temporale, senza retrodatare decisioni successive. Il refactor applicativo
  e i proxy di tabella hanno uno scopo distinto dal compilatore SQL.
- Sessione `f123535c-6f2e-47f6-ac10-159487db5ec3`, richiamata dall'analisi del
  29 settembre: discussione dell'istanza separata e dei flag sotto experimental.
  Riguarda l'adozione del percorso alternativo, non SELECT concatenate già pronte.

Della sessione iniziale `genropy-sql-archaeology-decd9f` il percorso locale
contiene residui di strumenti, ma non il transcript principale: non viene
presentata come riletta integralmente. Il seguito SQL archaeology sopra è
disponibile e contiene la discussione pertinente.

I dialoghi documentano intenzioni ed evoluzione delle scelte. Non autorizzano
oggi variant, aggregazioni automatiche, nuovi flag, runtime columns o grammatiche.
Prevalgono le decisioni di questa chat.

## Collegamento con Asqueel attuale

Esistono già `Projection.column` e `ResultColumn.source`: `_Context.projection`
popola l'origine per riferimenti diretti e path con l'identità della colonna,
o con `table.key + '.' + column.name`. Le espressioni calcolate non ricevono
automaticamente un'origine riconoscibile.

Questa è la prima base da verificare per la catena, prima di aggiungere strutture
interne. Il dato source da solo non la implementa: `QueryPlan.table` è ancora un
`TableRef` fisico e `_Context.related` costruisce join usando campi del modello
fisico. Occorre risolvere il nome esposto dalla query derivata mantenendo il
riferimento alla relazione originale.

Per `customer_id` proiettato, il passaggio atteso è:

1. riconoscere il campo esposto nel livello corrente;
2. risalire al campo e alla relazione del modello tramite la sua origine;
3. usare nella condizione di join **alias e nome esposto del FROM derivato**,
   non l'alias fisico racchiuso nella SELECT interna;
4. risolvere `name` sulla tabella destinazione;
5. produrre il piano completo e solo alla fine SQL e kwargs.

La stessa risoluzione deve servire le clausole già supportate. Origini ambigue
dopo espressioni, alias o set operator restano da trattare esplicitamente.

## Conseguenze sul piano, senza ampliarne il perimetro

- Prima del passo 3, verificare le informazioni già conservate nelle proiezioni
  e rendere esplicite quelle eventualmente mancanti al caso acquisito.
- Usare lo stesso percorso di risoluzione nelle clausole e nei livelli annidati,
  distinguendo modello di origine e scope SQL.
- Recuperare i casi applicabili: doppie relazioni verso la stessa tabella,
  formule raggiunte attraverso relazioni, dipendenze annidate e binding omonimi.
- Non importare automaticamente aggregatori per dtype, riscritture sottoquery
  → join, LATERAL, deduplicazione delle sottoquery o segnaposto testuali.
- Verificare SQL e kwargs completi senza accessi al DB durante la compilazione.
  L'ispezione storica non sostituisce i test sul futuro percorso Asqueel.
