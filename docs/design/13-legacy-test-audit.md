# 13 — Audit dei test SQL legacy e distanza dal prodotto attuale

Data: 29 settembre 2026. Analisi interna, non manuale utente.

## Conclusione

Il nuovo nucleo non è ancora equivalente al livello SQL legacy di Genropy. Esistono già una
base sincrona, configurazione con grammatiche e rendering a oggetti, query con
path to-one, aliasColumn, formule SQL e sottoquery correlate, CRUD PostgreSQL,
environment e policy sulle righe. Manca ancora una parte sostanziale dei
contratti che rendono questi elementi un sistema applicativo coerente.

L'obiettivo non può essere «aggiungere qualche formula»: deve comprendere
modello navigabile, linguaggio delle query, forma dei risultati e ciclo delle
scritture. Il legacy resta il riferimento; una limitazione attuale non è una
decisione di esclusione. Le priorità in [14](14-legacy-target-and-stages.md)
sono proposte, non nuovi accordi sul comportamento.

## Perimetro e attendibilità

- Baseline nuova: `2bed211d5c0c2144e4669b9259114757db12e65d`.
- Legacy: `fa35e5adfa6ad1b269f3a22a9b12c4c1ee6513ea`.
- Letti i corpi dei file Python del nucleo `gnrpy/tests/sql`, inclusi helper e
  fixture, e `gnrpy/tests/app/test_gnrsqlappdb.py`: **37 file, 968 definizioni
  di test, 12.578 righe originali**. La lettura normalizzata AST conserva
  istruzioni e docstring; non equivale a un controllo riga per riga dei commenti.
- [Indice di ogni test con link alla sorgente](evidence/legacy-sql-tests-index.md),
  [inventario con hash, righe, classi e decorator](evidence/legacy-sql-tests.json),
  [generatore riproducibile](evidence/catalog_legacy_sql_tests.py).
- Sono definizioni sorgente, **non 968 casi raccolti o superati**. Ereditarietà,
  parametrizzazione, skip e nomi delle classi cambiano il numero eseguibile.
- La suite legacy **non è stata eseguita in questo audit**. Alcune fixture
  creano/eliminano database dai nomi fissi e alcune prove dipendono dall'ordine.
  Serve un ambiente isolato prima di usarle come oracle eseguibili.
- La working copy legacy ha modifiche in `projects/test_invoice/packages/invc/model/`
  (`customer.py`, `invoice.py`, `invoice_row.py`). Non sono state modificate qui.
  Per confronti dinamici riproducibili occorre fissare anche la versione delle fixture.
- I test non esauriscono le specifiche: GEP sulle virtual relation, conversazioni,
  applicativi e sorgenti restano necessari. Non si afferma di aver letto tutti
  i test del framework web, tutti i package o ogni applicazione legacy.

Ricerca supplementare nei test app/core/web: verificati i casi pertinenti di
`test_instance_bag_mode.py` (nomi delle virtuali e statiche con entrambe le Bag),
`test_native_bag_data_regressions.py` (selection grid),
`test_bag_tytx_transport.py` (serializzazione dei resolver SQL) e
`th_view_hiddencolumns_test.py` (required_columns attraverso path).
Questi casi non sono compresi nel conteggio 968. I test di localizzazione,
API applicative e task non costituiscono da soli prove del compiler.

### Qualità degli oracle

| Evidenza | Limite da considerare |
|---|---|
| Test con righe reali PG/SQLite, confronti con query dirette | Miglior punto di partenza per casi di conformità; richiedono fixture fissate. |
| Test del modello e mock del compiler/adapter | Provano forma e contratto locale; non esecuzione SQL né interoperabilità reale. |
| `ToDo`, `GeneralSqlMigrationCode` in migration | Classi senza prefisso Test, normalmente non raccolte da pytest; il progetto non configura un diverso `python_classes`. |
| `xtest_*`, `_broken_test_*` | Non diventano copertura attiva per il solo fatto di essere nel file. |
| `test_SqlTableObj_indexes` | Contiene un confronto senza assert: non certifica gli indici attesi. |
| `test_gnrbaseadapter.test_insert` e placeholder | Un corpo pass non verifica il comportamento. |
| Alcuni test pyColumn, bagItem, PERIOD | Verificano presenza della chiave, lunghezza o tipo, non sempre il valore calcolato. |
| Benchmark relazioni/compiler | Misurano tempi, senza soglia di regressione; non dimostrano che il nuovo sia più veloce. |
| Adapter importabili e macro vettoriali con mock | Non provano tutti i backend né un server pgvector operativo. |
| SQLite boolean rewrite | Uno skip su eccezione ampia può nascondere un errore di preparazione o esecuzione. |

Non sono emerse definizioni di test sovrascritte da metodi omonimi nel corpus.

## Matrice dei contratti

Legenda stato: **parziale** = esiste un sottoinsieme operativo; **manca** =
contratto non consegnato nel nuovo runtime; **diverge** = comportamento osservabile
attuale diverso, senza presumere che sia approvato; **da verificare** = non basta
l'evidenza per concludere. I riferimenti indicano i file nell'indice, che contiene
nomi e righe di ogni caso. Le precedenti consegne [11](11-alias-columns-delivery.md)
e [12](12-correlated-formulas-delivery.md) precisano i sottoinsiemi già implementati.

### Modello, identità e relazioni

| ID | Contratto emerso | Stato e conseguenza | Fonti principali |
|---|---|---|---|
| LT01 | Dichiarazioni table/column riaperte e arricchite da package/mixin; configurazione separata dagli oggetti vivi | Parziale: rendering nativo presente; non equivale al caricamento e composizione dei package legacy. Servono casi di precedenza e aggiornamento. | a_structure_load, b_structure_build |
| LT02 | Identità logica package.table separata da schema SQL, sqlname, sqlfullname e prefisso tabella | Parziale: mapping fisico presente. Verificare default e roundtrip espliciti; `alfa.alfa_recipe` compare nelle migrazioni. | model_structure, gnrsqlmigration |
| LT03 | Metadati colonna, caption, dtype/size, readonly, reserved, UI; alias eredita dal target con override locale | Parziale: alias e configurazione presenti; non tutta l'introspezione legacy. I metadati devono essere accessibili anche attraverso path. | model_structure, b_structure_build |
| LT04 | `table.column('@customer_id.state')`, `$name`, originalColumn, relatedTable/relatedColumn | Diverge: compiler sa percorrere relazioni to-one; SqlTable.column accetta solo il nome locale e altrimenti alza ValueError. | model_structure, b_structure_build |
| LT05 | Grafo relations con FK, inverse, colonne fisiche e virtuali relazionali; joiner, cardinalità e dipendenze | Manca la superficie equivalente navigabile. Non basta un elenco di JOIN. | model_structure, relations_thread_safe |
| LT06 | `resolveRelationPath`, `fullRelationPath`, `getTableJoinerPath`, aliasTable di un percorso intero | Manca; un nome alternativo di una relazione singola non copre aliasTable multi-hop. | model_structure, compiler_coverage |
| LT07 | Formula che produce una FK, joinColumn condizionale e path attraverso tali relazioni | Manca il contratto completo. Una virtuale con relazione deve conservare i propri attributi, senza ereditare quelli della precedente colonna fisica. | model_structure, compiler_coverage |
| LT08 | compositeColumn come identità serializzata e relazione multicomponente | Parziale: PK e relazioni composite native non equivalgono alla colonna virtuale JSON array legacy. | composite_column, gnrsqlmigration |
| LT09 | Colonne fisiche, virtuali statiche/dinamiche, composte; selezione `*` regolata da categorie | Diverge: il nuovo SELECT `*` comprende le colonne risolte, senza riprodurre l'intera classificazione legacy. DML RETURNING `*` è fisico. | model_structure, instance_bag_mode |
| LT10 | Subtable: condizioni, parametri, negazione, unione/intersezione, `*`, context_subtables e indicatori sintetici | Manca; accettare `subtable='*'` in una formula non implementa le subtables. | e_query, compiler_coverage, model_structure |

Un path ha almeno tre usi da rendere coerenti: trovare una colonna e i suoi
metadati, compilare SQL e navigare un record/una relazione. `@customer_id.state`
parte dalla FK customer_id; un attraversamento successivo può essere
`@customer_id.@state_id.name`. Serve anche la direzione inversa, con cardinalità
many esplicita. I test che ricompattano righe esplose non autorizzano a
reintrodurre aggregateRows, già escluso dall'utente.

### Query, compiler e risultati

| ID | Contratto emerso | Stato e conseguenza | Fonti principali |
|---|---|---|---|
| LT11 | Proiezioni, filtri, ordine, limit/offset, path multi-hop e alias espliciti | Parziale operativo; non descriverlo come compiler legacy completo. | e_query, compiler_coverage |
| LT12 | Alias automatici dei risultati relazionali, colonna pkey aggiunta e ordinamento di tabella | Diverge: legacy usa ad esempio `_person_id_name`; nuovo `person_id_name`, niente pkey implicita/table order equivalente. Cambiano le chiavi lette dalle app. | e_query, h_query_surface |
| LT13 | `count()` con query normali, distinct e raggruppamenti | Manca: il terminale nuovo solleva UnsupportedFeatureError. COUNT esplicito non sostituisce automaticamente tutti questi casi. | e_query, h_query_surface |
| LT14 | DISTINCT, GROUP BY, HAVING, group_by='*', joinConditions e relationDict | Manca la superficie equivalente; coprire anche interazioni e conteggi, non solo rendering delle clausole. | e_query, compiler_coverage |
| LT15 | `IN :values` / NOT IN con tuple/list/set, senza espandere stringhe scalari | Diverge: nuovo binding non espande collezioni. ANY PostgreSQL è un'alternativa, non equivalenza di sintassi. | e_query, gnrbaseadapter, evidence/native_binding_probes.json |
| LT16 | Wildcard su path come `*@movie_id`, bagFields e virtual_columns | Manca la semantica completa, incluse collisioni e nomi delle colonne risultanti. | e_query, compiler_coverage |
| LT17 | aliasColumn, formula SQL, alias di formula, catene e cicli | Parziale già consegnato. Le espressioni SQL CASE, window, FILTER ecc. possono passare come frammenti: non dichiararle mancanti solo perché prive di wrapper. | compiler_coverage, consegna 11 |
| LT18 | select/exists, sottoquery nominate, #THIS, parametri locali e correlazione multi-hop | Parziale già consegnato; restano provider `sql_formula=True`, subquery_*, var_* e varianti. | compiler_coverage, consegna 12 |
| LT19 | subQueryColumn con raccolte JSON/XML; Bag e valori calcolati Python | Manca: scalar subquery non equivale a una raccolta tipizzata; pyColumn e bagItemColumn richiedono pipeline e valori verificabili. | compiler_coverage, model_structure |
| LT20 | Macro registrabili IN_RANGE/PERIOD/PREF/THIS/BAG/BAGCOLS, override/priorità; TS e vector PG | Manca un sistema equivalente; distinguere macro core, package e funzionalità PG opzionali. | macro_registration, vecquery_macro |
| LT21 | Parametri interpretati come riferimenti a campi (`embedFieldPars`) | Diverge: nuovo li tratta come dati. Occorre concordare il confine tra riferimenti intenzionali e input esterno, senza introdurre sostituzioni indiscriminate. | compiler_coverage |
| LT22 | Riga accessibile per indice e per nome, cursor, fetchPkeys/AsDict/AsBag/AsJson/Grouped | Parziale: fetch restituisce dict ordinari; i terminali legacy non sono tutti presenti. | e_query, h_query_surface |
| LT23 | Record lazy, condizioni keyword, ignoreMissing/ignoreDuplicate, output Bag/dict/json/newrecord | Parziale: nuovo record lazy con cache/refresh, un solo record e output dict; non equivalente al Record legacy. | h_record_surface, d_table |
| LT24 | Selection: output, sort/filter/apply, append/extend, chiavi, sum, metadata e freeze/thaw | Manca; selection() rifiutato. Separare primitive dati da output UI senza presumere che questi ultimi siano cancellati. | f_selection, h_selection_surface |
| LT25 | Resolver relazionali one/many e serializzazione; Bag X e suffisso ::X | Manca il ponte equivalente. Bag non viene resa thread-safe da questi test. | h_record_surface, selection_x_typing, bag_tytx_transport |

### Environment, transazioni e scritture

| ID | Contratto emerso | Stato e conseguenza | Fonti principali |
|---|---|---|---|
| LT26 | currentEnv modificabile, tempEnv, workdate/locale, connectionName e store | Parziale/diverge: snapshot nativo e scope temporaneo, senza tutta la mutabilità/default legacy; store/tenant rinviati per accordo. | gnrsql, gnrsqlappdb |
| LT27 | Transazione implicita, commit esplicito, rollback automatico su errore SQL | Avvio implicito già presente; diverge il recupero errore: nuovo stato rollback-only fino a rollback, legacy execute chiama rollback prima di rilanciare. | gnrsql/execute.py, nuovo session.py |
| LT28 | deferToCommit/deferAfterCommit e notifica solo al commit | Mancano code e lifecycle equivalente. Definire ordine, deduplicazione, fallimenti e pulizia dopo rollback. | d_table, db_notify |
| LT29 | Insert/update/delete e raw/bulk, chiavi generate, old_record e trigger applicativi | Parziale: CRUD e sei hook presenti; non sono tutta la pipeline legacy. | d_table, hierarchical_trigger, write_record_cluster |
| LT30 | Record cluster: relazioni invalide None, recupero mode dal modello, FK propagata | Manca. Riguarda scritture correlate atomiche, non solo output Bag. | write_record_cluster |
| LT31 | Gerarchie, contatori, percorsi parent e `_h_count` | Manca; l'ordine counter prima di derivare la gerarchia è un contratto osservabile. | hierarchical_trigger |
| LT32 | Draft NULL/False visibili, logical delete e mark, checkDuplicate | Policy base presenti; verificare servizi duplicati/unique con righe archiviate. Visibilità query e vincolo DB non sono la stessa cosa. | sqlite_boolean_rewrite, check_duplicate |
| LT33 | Partition su colonna o relazione, current/allowed/context | Profilo esplicito nativo concordato: falsy validi, [] nessuna riga, contesto richiesto assente errore salvo bypass esplicito. Non recuperare il bypass implicito legacy. | compiler_coverage, test nativi policy |
| LT34 | Cifratura R/Q/X, decifratura risultato e alias, masking per dialect | Manca. I test non dimostrano ricerca automatica con plaintext su Q: alcuni cifrano il parametro prima della query. | encrypted_columns, gnrbaseadapter |
| LT35 | LISTEN/NOTIFY, payload minimo/variazioni, dispatch e listener | Manca il sistema equivalente; distinguere eventi del runtime e servizio listener applicativo. | db_notify, gnrlistener |

La correzione sulle transazioni è concreta: l'utente non deve essere obbligato
a introdurre `with db.transaction()` per il normale lavoro applicativo.
L'avvio implicito è già nel nuovo SqlDatabase. **Automatico non significa commit
ad ogni istruzione**: legacy execute ha autocommit=False e il commit può essere
esplicito o governato dall'applicazione. La classe Database di basso livello
nuova ha invece una convenience per singola istruzione: non va confusa con
SqlDatabase nella documentazione. Il rollback legacy verificato è quello
nell'execute SQL; non si estende questa conclusione a ogni eccezione Python
sollevata da un hook senza analizzarne il relativo chiamante.

### Dialetti, struttura e migrazioni

| ID | Contratto emerso | Stato e conseguenza | Fonti principali |
|---|---|---|---|
| LT36 | Adapter dati: parametri, tipi, cursor, funzioni, differenze boolean/cast/locking | Separazione compiler/dialetto/driver presente, PostgreSQL primario. Importare otto adapter non prova otto implementazioni funzionanti. | adapterinheritance, gnrbaseadapter, sqlite_boolean_rewrite |
| LT37 | Estrarre DB, configurare modello, diff/apply e secondo diff vuoto | Profilo strutturale nativo limitato; verificare roundtrip senza perdita e rifiuti espliciti. Il migratore completo è responsabilità anche di sqlmigration, non tutto di asqueel. | gnrsqlmigration, gnrsqlutils |
| LT38 | PK/FK/unique compositi, indici GIN/TSV, deferrable e ordine DDL | Requisiti di integrazione con sqlmigration: colonna prima di PK/index/FK, conservare unique indipendenti, nomi dei constraint corretti. Audit corrente non certifica il repo sqlmigration. | gnrsqlmigration |
| LT39 | Conversioni con dati, force/backup e protezione dalle perdite | Non copiare automaticamente comportamenti distruttivi. Legacy prova default che blocca conversioni incompatibili popolate, force che converte invalidi in NULL, backup che conserva originali. | gnrsqlmigration |
| LT40 | Extension già installata non rimossa/reinstallata; idempotenza | Da includere negli acceptance di migrazione. I test legacy backup saltano talvolta il secondo diff perché le colonne di backup risultano estranee al modello. | gnrsqlmigration |
| LT41 | Connessione irraggiungibile distinta da database inesistente, eccezioni diagnostiche | Definire contratto adapter/driver e diagnostica; i test legacy sono in parte mock. | connection_error, gnrexceptions |
| LT42 | Prestazioni di risoluzione relazioni, cache, lock su errore | Manca un confronto quantitativo affidabile. Test lock assicura rilascio dopo eccezione, non sicurezza concorrente globale della Bag. | relations_benchmark, relations_thread_safe, compiler_simulation |

## Cosa questi test non decidono

1. **Virtual relation della nuova GEP**: i test di formula-FK e joinColumn
   forniscono contratti utili, ma non certificano tutta la nuova proposta.
2. **Partition fisiche** PostgreSQL, subtable logiche e isolamento applicativo
   per partition sono tre problemi distinti; non marcarli risolti insieme.
3. **View, funzioni e trigger nativi** restano obiettivi richiesti: nei test letti
   non c'è una suite sufficiente per importazione, dipendenze, diff e lifecycle.
4. **Metadati UI** devono restare associati alla colonna o a un'entità collegata,
   come richiesto; la forma finale della grammar UI richiede casi reali.
5. **Prestazioni**: nessuna promessa di velocità rispetto al legacy deriva da
   questa lettura. Servono dataset, piani SQL e soglie ripetibili.
6. **aggregateRows** resta escluso. Le prove legacy che ne dipendono vanno
   trasformate in contratti di raccolte/cardinalità esplicite, non trasposte.

## Come rendere l'audit eseguibile

Per ciascun LT: scegliere test legacy significativi, fissare fixture e risultati,
aggiungere un caso equivalente sul nuovo nucleo e registrare una sola delle
conclusioni: conforme, parziale, mancante, differenza approvata, decisione aperta.
Confrontare valori, nomi e tipi dei risultati, effetti persistiti e numero delle
righe; non richiedere SQL testualmente identico quando è semanticamente equivalente.
Per gli oracle deboli aggiungere dati non banali e risultati esatti. Non attribuire
un test passato finché non è stato davvero eseguito.

La suite delle versioni nuove rimane necessaria ma non misura da sola la
compatibilità. Anche i vecchi rapporti 10/10a/10b/10c sono fotografie storiche:
le consegne 11/12 superano alcune lacune, non tutte.

## Integrazione del 30 settembre — connessioni nominate indipendenti

LT26–LT28 vanno letti anche come gestione di più connessioni fisiche allo stesso
DB nello stesso thread, non soltanto come futuro supporto multi-store.
`gnrsql/connections.py:_get_store_connection` usa la coppia
(storename, currentConnectionName) nella cache del thread; `tempEnv` consente
la selezione temporanea. Il cambio di contesto non conclude la transazione.
`commit()` conclude le connessioni pendenti del nome attivo, anche su più store;
`rollback()` riguarda la connessione corrente, mentre `rollbackAll()` attraversa
le connessioni pendenti del nome attivo e ripulisce le relative code deferred.
Questo non costituisce un commit distribuito atomico fra database.

Il piano F1 include ora esplicitamente il caso di due connessioni A/B allo stesso
DB, con conclusione indipendente delle transazioni e ripristino della selezione.
La precedente voce generica connectionName sottostimava questo requisito.
Fonte: lettura delle implementazioni, non nuova esecuzione della suite legacy.


## Python-error lifecycle follow-up — 30 September 2026

The [F1 error review](20-python-error-lifecycle.md) adds contracts PY01–PY06 to
LT26–LT29: 16 real-PostgreSQL scenarios for each implementation cover six write
hook positions, explicit rollback versus attempted commit, and pre/post-commit
callback failures with and without new SQL. It records the difference between
legacy continuation and native rollback-only behavior; it does not declare that
difference approved or the overall F0 inventory complete.

The [caller follow-up](21-recovery-callers.md) reviews 61 lexical candidates
from 1,648 tracked Python files and executes nine scenarios per backend using
five original caller bodies. Explicit rollback/recovery, independent logging
and handled SMTP failure agree within the fixture boundaries. A logger without
rollback persists partial failed work in legacy and blocks subsequent writes
in native Asqueel; this is a porting risk, not a newly accepted compatibility
requirement. Callback retry differences and the documented broad-catch branches
remain open.

## LT26 — date/locale context follow-up

[Contract 24](24-workdate-locale-contract.md) records source evidence, the
accepted absence of locale validation and 11 native contract cases, including
PostgreSQL/SQLite binding. The context slice is verified; Windows UI-language
lookup and application localization are not ported by this work. LT26 as a
whole and F1 remain open. Full suite: 629 passed, coverage 95%.

## LT28 — callback recovery recheck

[Report 25](25-callback-recovery.md) reruns the original legacy/native PostgreSQL
oracle and adds eight PostgreSQL/SQLite regression cases. PY02–PY04 are reproduced;
residual-queue disposition remains a decision, not a runtime defect silently
fixed. Native behavior is unchanged. Full suite: 637 passed, coverage 95%.

On 1 October 2026 callback-owned error handling was clarified: normal return
continues dispatch; an escaping exception interrupts it. Residual-queue disposal
is a separate unresolved difference; see review 25. Caller-specific error paths
from review 21 remain open.

## F1 closure — 1 October 2026

[Report 27](27-f1-request-lifecycle-closure.md) completes the bounded caller
review with nine scenarios per implementation and records concrete adapter
obligations for RC03/18/26/45/50/51. Callback propagation now leaves unreached
postcommit callbacks for application-owned recovery and cleanup; no forced
queue disposal or continue-on-error policy. Ten PostgreSQL/SQLite cases prove
request isolation on a reused DB/thread. Full suite: **650 passed**, **95% coverage**.
F1's synchronous profile is complete; F0's whole-legacy inventory is not.
