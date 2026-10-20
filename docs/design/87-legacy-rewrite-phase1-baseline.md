# 87 — Riscrittura legacy, fase 1: contratti e baseline

15 ottobre 2026. Fase 1 del [piano 86](86-legacy-compiler-logical-phases.md)
completata. **Nessuna modifica al compilatore, agli adapter o al modello.**
La fase 2 non è iniziata. Il riferimento resta `fa35e5ad`, non il comportamento
del precedente compilatore Asqueel né quello di un branch sperimentale.

## Esito

| Verifica | Esito |
| --- | --- |
| Test originali legacy, fixture originali SQLite/PostgreSQL | **144 passati, 2 saltati** |
| Contratti riprodotti nuovamente sul codice legacy senza I/O | **62 passati** |
| Nuovi contratti sul compilatore gerarchico | **4 passati, 58 xfail stretti** per funzionalità ancora mancanti |
| Regressione esistente su albero, migration e inverse | **1.853 passati**, oltre ai 4 nuovi contratti fisici |
| SELECT fisiche dei 74 modelli, due dialetti | **148/148** con stesso SQL e kwargs nel vecchio e nel nuovo percorso |
| Relazioni dichiarate: 72 dirette e 72 inverse, due dialetti | Legacy **284/288** compilate; precedente Asqueel **266/288**; gerarchico **0/288**, bloccate esplicitamente |

Gli xfail non sono successi: il test conserva l'SQL atteso dal legacy e ammette
soltanto l'eccezione già identificata per la funzionalità mancante. Un'eccezione
diversa fallisce; quando il port funziona il marker va rimosso, senza rigenerare
l'oracolo dal nuovo compilatore. Per `count` manca attualmente il metodo del
compilatore gerarchico; negli altri casi si incontra `UnsupportedFeatureError`.

I quattro errori del legacy sono due inverse su chiavi formula, ripetute sui
due dialetti: `invc.invoice.@last_invoice` e `invc.product.@first_in_invoice`.
Il riferimento genera rispettivamente `KeyError('last_invoice_id')` e
`KeyError('first_product_id')`. Sono limiti osservati sulle relazioni realmente
dichiarate, non nuovi casi inventati né comportamenti da correggere in questa fase.

## Provenienza e perimetro delle prove

I test originali sono selezionati da `gnrpy/tests/sql/test_compiler_coverage.py`
e `test_composite_column.py`, senza modificarne corpi o fixture. Il manifesto
registra **138 definizioni**, che pytest espande in **146 casi**. I due skip
sono quelli originali su EXISTS/SQLite. La fixture crea un server PostgreSQL
temporaneo e database dedicati; importa i CSV originali e provvede alla pulizia.
I test joinColumn descrivono il riferimento delle condizioni ON: non autorizzano
a sostituire le dichiarazioni native GEP con la vecchia grammatica.

La sonda differenziale esegue **498 compilazioni per percorso**:

- 74 tabelle × 2 dialetti: tutte le colonne fisiche dichiarate;
- 144 relazioni × 2 dialetti: attraversamento di ciascun nodo del ramo relations;
- 31 richieste mirate × 2 dialetti: riuso, profondità, inverse, chiavi composte,
  formule, sottoquery, parametri, macro, grouping e default.

Le richieste mirate sono adattamenti espliciti dei test originali, non copie
verbatim. Il relativo riferimento è scritto accanto a ogni caso. Per isolare
le relazioni disattivano esplicitamente filtri impliciti e aggiunta legacy della
pkey; i due casi `default_*` conservano invece i default originali. L'ordine
aggiunto alle prove con LIMIT rende confrontabili le righe. La raccolta nativa
è derivata dal modello congelato, non dal corpus storico dello scanner.

Le 31 richieste mirate sono anche eseguite in SQLite in memoria: dieci tabelle
con dati congelati. Otto CSV sono quelli già usati dai test nativi; `price_year`
e `price_year_note` provengono dallo snapshot legacy. **31/31 esecuzioni legacy
riescono**. Il precedente Asqueel ne compila ed esegue 28; il gerarchico 2.
Questa sonda non esegue PostgreSQL: le verifiche PostgreSQL sono i test originali
e quelli di regressione delle inverse, separati dalla compilazione.

I tre package sono tutti presenti: **sys 16 tabelle, adm 40, invc 18**.
Restano esclusi `sys.locked_record` e i quattro nodi relazionali dei due
joinColumn sostituiti con le dichiarazioni GEP già concordate. Le 144 relazioni
corrispondono al registro ordinario verificato nei test dell'albero.

## Contratti fissati

| Contratto | Riferimento e prova | Cosa si conserva |
| --- | --- | --- |
| Raccolta e sostituzione | `compiledQuery`, `updateFieldDict`, `embedFieldPars`; casi physical, CASE/COALESCE, symbolic_relation_parameter | Ordine legacy; parametri simbolici trattati nel WHERE, kwargs separati |
| Percorso e JOIN | `getFieldAlias`, `_findRelationAlias`, `_getRelationAlias`; navigazione diretta, due/tre livelli | Lettura del ramo relations; alias `t0`, `t1`, ecc. nel loro contesto |
| Riuso | `reuse_across_clauses`, `alias_and_direct_reuse`, `inverse_reuse` | Una JOIN per lo stesso percorso/alias; tracciamento exploding anche al riuso |
| Percorsi differenti | `composite_two_paths`, `different_paths_same_table` | Non fondere JOIN solo perché raggiungono la stessa tabella |
| Chiavi composte | 14 test originali e due contratti mirati | Tutte le coppie della chiave nell'ON; navigazione successiva al target |
| Inverse e DISTINCT | `TestDistinctExploding`, `TestExplodingFastPath` | Preservare DISTINCT implicito e colonne d'ordine aggiunte nel punto originale |
| Count | `TestCompiledQueryOptions`, due contratti mirati | Separare SQL prodotto e valore numerico estratto; non sostituire l'algoritmo perché un conteggio coincide |
| Formule e ricorsione | `TestFormulaChain`, `TestFormulaSelect`, `TestNamedSubQuery`, formula_relation | Dipendenze, JOIN introdotte dalle formule, contesto delle sottoquery e correlazioni |
| `var_*` | `TestVarParameters`, formula_parameters | Identità dei binding locali e valori; nessuna confusione con alias delle tabelle |
| Clausole | `TestGroupByHaving`, `TestCompiledQueryOptions`, star e macro_range | Ordine delle espansioni, grouping e macro del perimetro concordato |
| Default | default_pkey, default_inverse | Registrare la differenza senza nasconderla con opzioni di fixture |
| Compilazione senza I/O e riuso | Guardie di connessione/esecuzione e ricompilazione delle richieste | SQL e kwargs disponibili senza DB; nessuna contaminazione osservata fra compilazioni |

Il replay dei contratti verifica anche il numero delle JOIN, tutte le componenti
dell'ON composto, il tracciamento delle due colonne exploding, la colonna nascosta
di ordinamento e la risoluzione del parametro simbolico. Il ciclo di completamento
dei riferimenti e la ricorsione restano quelli dei metodi originali: non sono
sostituiti da una nuova analisi delle dipendenze.

## Differenze concrete da conoscere prima del port

1. **Il nuovo albero non è ancora raccordato alle relazioni.** Tutti i 288
   attraversamenti si fermano al blocco esplicito. La struttura esiste: i test
   del registro e delle viste relazionali passano. Va portato il resolver legacy,
   non costruito un altro grafo.
2. **Alias automatici del precedente Asqueel.** Il legacy produce
   `_customer_id_account_name`; il vecchio percorso produce
   `customer_id_account_name`. Su più livelli cambia anche la sequenza degli
   underscore. I valori possono coincidere, ma cambia l'accesso per nome.
3. **Parametri che indicano campi.** Con `where='$customer_id=:other'` e
   `other='@customer_id.id'`, il legacy sostituisce il riferimento con il campo
   della JOIN; il precedente Asqueel confronta con la stringa. Nella prova:
   **5 righe legacy, 0 nel precedente Asqueel**. Il gerarchico si ferma prima,
   sulla relazione non raccordata. Non va esteso il comportamento a clausole
   diverse da quelle previste dal legacy.
4. **DISTINCT e colonne nascoste.** Sulle inverse il legacy, con distinct
   assente/None, può aggiungere DISTINCT e `__ord_col_N`. Il vecchio percorso
   non lo fa. Nelle prove con ordinamento si osserva anche una diversa struttura
   della riga; questo non significa automaticamente valori dei campi errati.
   Il rapporto 63 descriveva i limiti del port precedente: non costituisce una
   decisione dell'utente che autorizzi a derogare al riferimento.
5. **Count: numeri uguali non certificano l'algoritmo.** I due casi mirati
   restituiscono **3428** e **256** in entrambi i percorsi eseguibili, ma uno
   ottiene il risultato contando le righe della SELECT distinta legacy, l'altro
   attraverso una SELECT di conteggio Asqueel. Il gerarchico non offre ancora
   la compilazione count. Le forme SQL sono registrate separatamente dal numero.
6. **Default e `*`.** Il legacy aggiunge `pkey AS pkey` nel caso non aggregato;
   il precedente Asqueel no. L'espansione `*` presenta un ordine delle colonne
   diverso. `group_by='*'` funziona nel riferimento ed è rifiutato dal vecchio
   percorso. Nel nuovo albero queste parti sono ancora bloccate.
7. **Chiavi formula e inverse private.** Il vecchio percorso rifiuta chiavi
   virtuali e non trova alcune inverse private presenti nel registro legacy.
   La navigazione forward `@last_invoice_id` funziona nel riferimento; le due
   inverse su chiavi formula sopra elencate falliscono anche lì. Non confondere
   i due problemi né correggere il secondo incidentalmente.
8. **Nomi dei parametri locali.** Il legacy usa qui anche prefissi contenenti
   `id()`; il vecchio Asqueel usa nomi come `f1_high_label`. Nei casi `var_*`
   confrontiamo corrispondenza univoca placeholder/valore e isolamento, non
   imponiamo indirizzi di memoria come contratto pubblico. Alias delle tabelle
   e mangler restano distinti, come già deciso.

Queste differenze **non sono state corrette**. Non vengono considerate scelte
approvate solo perché già presenti nel compilatore Asqueel. La fase successiva
deve seguire il legacy nel perimetro del piano; eventuali impedimenti concreti
vanno esposti prima di scegliere un comportamento alternativo.

## Confronto degli otto snapshot

Stesse 31 richieste, stesso modello congelato e stessi dati; compilazione su
due dialetti, esecuzione SQLite. Non sono le suite proprie di ciascun branch.

| Snapshot | Compilazioni riuscite / 62 | Esecuzioni riuscite / 31 | Stesse righe e colonne del riferimento / 31 |
| --- | ---: | ---: | ---: |
| legacy | 62 | 31 | 31 |
| compound | 62 | 30 | 29 |
| v2 | 60 | 19 | 19 |
| v3 | 58 | 28 | 27 |
| v3 merged | 58 | 28 | 28 |
| v4 | 58 | 28 | 28 |
| simplify | 62 | 21 | 21 |
| next | 62 | 31 | 31 |

Nei branch precedenti manca l'espansione della macro IN_RANGE del riferimento;
v3/merged/v4 falliscono i due casi composti. V2 ha SQL incompatibile con SQLite
per alcuni percorsi many e due esecuzioni interrotte al limite di cinque secondi.
Simplify emette riferimenti a colonne fisiche inesistenti al posto di alcune
formule. Compound/v3 differiscono anche in default_inverse. Questi esiti
rafforzano la scelta di non importare automaticamente gli algoritmi sperimentali.
Non sono benchmark: il timeout impedisce solo che una sonda blocchi la baseline.

## Confronti, adattamenti ed esclusioni

L'oracolo conserva SQL, kwargs, clausole, JOIN, relationDict, aliasDict e
explodingColumns legacy. Conserva anche righe e nomi restituiti dalle esecuzioni
SQLite mirate. I confronti SQL ignorano soltanto gli spazi di impaginazione e
la quotatura già nota dell'alias base `AS t0`. L'audit aggiunto da `execute`,
successivo alla compilazione, è separato; `jc_kwargs` è registrato ma escluso
dal confronto dei binding SQL. I nomi locali dipendenti dal processo vengono
confrontati per corrispondenza dei binding nel solo caso `formula_parameters`.
Le differenze nei nomi di risultato, DISTINCT o colonne aggiunte non sono normalizzate.

Restano fuori: pyColumn in esecuzione, #PREF, table alias, query concatenate,
operatori, system_records e locked_record. Per le virtualRelation valgono la
GEP e le divergenze già concordate: niente inverse automatiche, order_by/limit
o cardinalità virtuale reintrodotti indirettamente. Partition rimane scalare;
nessuna nuova chiave di ambiente. Binding PostgreSQL e collisione collection
restano come deciso in R3/85; il caso del placeholder tra apici non è riproposto.

## Artefatti e riproduzione

- [Evidenze, manifesti e log](evidence/legacy-rewrite-phase1/).
- [Test originali e provenienza](evidence/legacy-rewrite-phase1/original-tests.json).
- [Confronto completo dei tre percorsi](evidence/legacy-rewrite-phase1/legacy-comparison.json).
- [Oracolo indipendente](../../tests/oracles/legacy_rewrite_phase1.json).
- [Contratti del percorso gerarchico](../../tests/object_tree/test_legacy_rewrite_contracts.py).
- [Replay contro il codice legacy](probes/test_rewrite_phase1_reference.py).

Dalla radice del repository, con gli snapshot già censiti in `/tmp/asqueel-formula-baseline`:

```sh
venv/bin/python docs/design/probes/rewrite_phase1_original.py \
  --output-directory docs/design/evidence/legacy-rewrite-phase1
PYTHONPATH=src:. venv/bin/python docs/design/probes/rewrite_phase1_compare.py \
  --output-directory docs/design/evidence/legacy-rewrite-phase1 --execute-sqlite
PYTHONPATH=src:.:docs/design/probes venv/bin/python -m pytest -q -o addopts= \
  docs/design/probes/test_rewrite_phase1_reference.py \
  tests/object_tree/test_legacy_rewrite_contracts.py
```

`--freeze-contracts` rigenera l'oracolo **solo dal riferimento legacy**; non è
necessario per eseguire i test. `--label LABEL --legacy-only --focused-only`
esegue la stessa sonda su un altro snapshot. Le dipendenze storiche restano
nell'ambiente di prova, non sono aggiunte al progetto.

Il log della regressione estesa precede l'aggiunta dei quattro casi composti
parametrizzati nel nuovo test; il log finale dei contratti li include. I 1.853
test di regressione esistenti non comprendono i nuovi contratti, evitando di
contare due volte i quattro casi fisici. Le impronte di verifica documentano
che codice di produzione, esempi e artefatti migration non sono cambiati.
