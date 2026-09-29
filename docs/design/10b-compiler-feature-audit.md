# 10b — Audit funzionale del compiler: legacy, profilo attuale e obiettivi

## Conclusione e perimetro

Il compiler attuale realizza un profilo PostgreSQL ristretto e utilizzabile, ma
**non è ancora un compiler con sintassi equivalente al legacy**. La presenza di
`db.table(...).query(...).fetch()` risolve il ciclo applicativo fondamentale, non
l'equivalenza della grammatica, delle proiezioni o della cardinalità.

Le differenze più urgenti per codice applicativo reale sono percorsi relazionali
multi-hop, parametri collettivi, alias e wildcard, default della primary key,
formule con subquery correlate, GROUP BY/HAVING/DISTINCT e conteggi. Le nuove
virtualRelation e le funzioni sui percorsi del GEP costituiscono un contratto
ulteriore: non sono già implementate dalla presenza di `Relation` e `formula`.

Questo documento è un audit interno, non una promessa dell'API pubblica. Non
modifica runtime o compiler. `aggregateRows` resta eliminato per decisione di
prodotto; esecuzione sincrona confermata, store/tenant fuori da questo incremento.

Baseline verificata il 29 settembre 2026:

- Legacy locale: `fa35e5adfa6ad1b269f3a22a9b12c4c1ee6513ea`.
- genro-sql: HEAD `b023a9bb25f3135ad1a10fb17a485eac27cf4237`; include
  `for_update` e application handles. Questo incremento modifica solo documenti
  e sonde di audit, non il codice del prodotto.
- GEP locali: documenti in stato **Discussion**, letti come proposte, senza
  considerarli prova dell'implementazione upstream o del contenuto corrente
  delle discussioni GitHub. Nessuna discussione remota è stata riletta.

## Mappa delle evidenze

Nelle tabelle `LC:273` significa il file LC qui definito, riga 273. I numeri
riferiscono alla baseline sopra; metodo e comportamento permettono di ritrovare
il riferimento anche dopo ulteriori modifiche.

| Sigla | File |
|---|---|
| LC | `/Users/gporcari/Sviluppo/Genropy/genropy/gnrpy/gnr/sql/gnrsqldata/compiler.py` |
| LQ | `/Users/gporcari/Sviluppo/Genropy/genropy/gnrpy/gnr/sql/gnrsqldata/query.py` |
| LU | `/Users/gporcari/Sviluppo/Genropy/genropy/gnrpy/gnr/sql/gnrsqlutils.py` |
| LM | `/Users/gporcari/Sviluppo/Genropy/genropy/gnrpy/gnr/sql/gnrsqlmodel/table.py` |
| LP | `/Users/gporcari/Sviluppo/Genropy/genropy/gnrpy/gnr/sql/adapters/gnrpostgres.py` |
| LB | `/Users/gporcari/Sviluppo/Genropy/genropy/gnrpy/gnr/sql/adapters/_gnrbaseadapter.py` |
| NC | `src/genro_sql/compiler.py` |
| NQ | `src/genro_sql/query_plan.py` |
| ND | `src/genro_sql/dialects/postgres.py` |
| NP | `src/genro_sql/drivers/psycopg.py` |
| NA | `src/genro_sql/application_table.py` |
| G1 | `/Users/gporcari/Sviluppo/Genropy/genropy_meta/gep/GEP-0001-relation-aggregates.md` |
| G2 | `/Users/gporcari/Sviluppo/Genropy/genropy_meta/gep/GEP-0002-many-relations.md` |

**Supportato** indica il caso specifico, non l'intera famiglia SQL.
**Parziale** indica una capacità presente con semantica o superficie diversa.
**Assente** indica nessun contratto dedicato; il passaggio di SQL scritto a mano
non cambia questa classificazione. **Rifiutato** indica un controllo esplicito
o una grammatica che non accetta la forma richiesta.

## Come lavora effettivamente il legacy

`LQ:143` conserva opzioni e parametri, normalizza columns assente a `*` e abilita
`bagFields` anche per `for_update`. `LQ:220` compila al primo accesso e mantiene
il compilato; `LQ:241` esegue e applica trasformazioni Python, decrittazione e Bag.

`LC:831` normalizza colonne, espande wildcard, aggiunge default e condizioni,
registra riferimenti e li risolve. `LC:273` decide fra campo fisico, alias di
relazione, formula, select/exists e py_method. `LC:507` costruisce LEFT JOIN,
registra i percorsi che moltiplicano righe e consente condizioni aggiuntive.
Infine `LC:1045` circa sostituisce riferimenti e applica DISTINCT automatico
quando rileva join many-side. Non è un AST SQL completo: molte trasformazioni
sono regex e sostituzioni testuali, con effetti sullo stato del compiler e
dell'ambiente. Le annotazioni REVIEW presenti nei sorgenti non sostituiscono
l'esame dei rami eseguibili.

Nel nuovo flusso `NA:105` ricompila a ogni terminale, `NC:438` costruisce un
`QueryPlan`, `ND:133` genera SQL e `NP:24` formatta i bind. Le tre responsabilità
sono separate, ma `Fragment` contiene ancora SQL opaco insieme a identificatori
e parametri strutturati. Non rappresenta scope SQL, aggregati o subquery come
nodi distinti. Questa separazione è una base utile, non un parser completo.

`LU:14` e `LU:123` sono ModelExtractor e SqlModelChecker: riguardano estrazione
schema e DDL, non la grammatica query. Per parametri e rendering le prove
pertinenti sono gli adapter, in particolare `LB:208` e `LP:147`.

## Matrice dettagliata della sintassi e delle relazioni

| ID | Caso | Stato attuale | Differenza ed evidenza |
|---|---|---|---|
| C01 | `$column` fisica | Supportato | `LC:709`, `LC:453`; `NC:292`, `NC:340`. Identificatori fisici passano al dialect, valori al driver. |
| C02 | `$"display name"`, Unicode e nomi fisici con `%` | Supportato nel profilo nuovo | `NC:90`, `NC:340`, `ND:98`, `NP:24`. Estensione esplicita moderna; non dedurre equivalenza dalla regex legacy. |
| C03 | `@customer.name` to-one | Supportato | `LC:507`; `NC:308`. LEFT JOIN riutilizzato, target obbligatoriamente univoco anche nei modelli manuali. |
| C04 | Legacy `@customer.@country.name` | Rifiutato | `LC:273`, `LC:456`; `_PATH` in `NC:25` ammette un solo `@` iniziale. Nuova forma `@customer.country.name` funziona ma è una sintassi diversa. |
| C05 | Chiave relazionale composta fisica | Supportato con limiti | `LC:586` circa usa composed_of; `NC:321` associa tuple di campi e verifica unicità target. Non implementa una compositeColumn virtuale legacy. |
| C06 | To-many e inversa automatica | Rifiutato/assente | `LC:559` e `LC:663` marcano row explosion; `NC:327` rifiuta target non univoco. Nessun inferimento di inverse nel resolver del compiler. |
| C07 | `aliasColumn(relation_path=...)` | Rifiutato nel modello; valore esprimibile diversamente | `LC:372` risolve relazione ricorsivamente. `NC:292` accetta formula stringa, quindi una formula `@customer.name` può esprimere il valore, ma non legge un attributo relation_path né attua quel protocollo del modello. `src/genro_sql/model.py:63` rifiuta aliasColumn in risoluzione (probe root confermato). |
| C08 | Alias di tabella/relazione per percorsi | Assente | `LC:488` espande table_aliases; `NC:314` cerca esclusivamente table.relations. |
| C09 | `cnd`, `join_on`, between, case_insensitive | Assente | Rami `LC:604`; nuovo ON solo uguaglianze fra chiavi fisiche `NC:330`. Attributi descrittivi non diventano condizioni. |
| C10 | Query setJoinCondition/one_one/$tbl | Rifiutato/assente | `LQ:194`, `LC:670`; `NA:33` rifiuta joinConditions/sqlContextName e non offre il metodo. |
| C11 | Chiave formula/virtuale in JOIN | Rifiutato | `LC:631` supporta ramo virtual; `NC:332` rifiuta formula join keys. Una relazione senza FK fisica fra colonne fisiche univoche non equivale a questa capacità. |
| C12 | `AS alias` e `AS "alias con spazi"` | Supportato | `LC:1001`; `NC:98`, `NC:377`. Il parser protegge CAST interno e letterali. Duplicati rifiutati, non sovrascritti. |
| C13 | Alias implicito di espressione SQL | Rifiutato | Legacy genera nome con colToAs `LC:1008`; nuovo richiede AS per espressioni `NC:405`. |
| C14 | Alias implicito di relazione | Parziale | Legacy appiattisce il percorso via colToAs `LC:735`; nuovo rimuove @ e sostituisce punti `NC:403`. Per `@customer.name`: legacy `_customer_name`, nuovo `customer_name` (legacy `gnrsql/query.py:361`). Consumatori per nome non sono automaticamente compatibili. |
| C15 | `*` | Parziale | `LM:479`: colonne fisiche, X escluse salvo bagFields, più sole virtuali statiche. `NC:385`: tutte le columns risolte, formule comprese, senza distinzione static/dynamic o filtro X. |
| C16 | `*prefix_`, `*@rel`, `*@rel.prefix_` | Assente/rifiutato | `LC:744` dichiara questa famiglia; `NC:385` espande solo `*` esatto. Inoltre il ramo root di LC restituisce starColumns senza filtrare prefix: non copiare una promessa documentale senza test. |
| C17 | `*@rel.(a,b,c)` | Rifiutato | `LC:776` popola aggregateDict. Nessun equivalente; il ritorno a regroup Python contraddirebbe la rimozione aggregateRows. |
| C18 | Primary key aggiunta come `pkey` | Assente, opzione rifiutata | `LC:895`, `LC:941`, default `LQ:151`; `NA:35` rifiuta addPkeyColumn. `*` può includere id ma non crea la colonna di output pkey. |
| C19 | order_by di tabella | Assente, override legacy rifiutato | `LC:891` applica default salvo aggregate; `NC:453` usa solo ordine passato. `NA:35` rifiuta ignoreTableOrderBy. Rischio ordine/paginazione differente senza errore. |

## Formule, subquery, funzioni e macro

| ID | Caso | Stato attuale | Differenza ed evidenza |
|---|---|---|---|
| F01 | Formula SQL stringa `$a + $b` | Supportato | `LC:390`, `NC:292`: ricorsione nello scope della tabella proprietaria, parentesi; nuovo rifiuta cicli. |
| F02 | Formula sulla tabella correlata | Supportato entro to-one | `NC:308` passa tabella e alias risolti a field; non usare questo fatto per promettere scope di subquery. |
| F03 | `sql_formula=True` e metodo sql_formula_name | Assente | `LC:395` chiama codice tabella; `NC:340` richiede espressione stringa, nessun dispatch callback. |
| F04 | Formula `select=dict(...)`, `exists=dict(...)` | Assente | `LC:399` crea queryCompile e wrapper; `NQ:80` non ha nodi subquery, `NC:292` legge solo column.formula. |
| F05 | `#THIS.field` e correlazione | Rifiutato | `LC:310`, `LC:417`; `NC:369` rifiuta macro. Mancano scope interno/esterno distinti. |
| F06 | `select_name`, `#name`, subquery_name() e cast | Assente/rifiutato | `LC:397–420` compone sottoquery nominate; nessun protocollo nel nuovo resolver. |
| F07 | SQL manuale `EXISTS(SELECT...) AS present` | Parziale | Può attraversare Fragment se valido, ma `$field` è risolto sempre nello scope Genro corrente. Alias fisici e correlazione scritti a mano restano responsabilità dello sviluppatore. Non è F04. |
| F08 | `py_method` | Assente | `LC:440` produce NULL e registra postprocessing, `LQ:256` esegue callback; nuovo fetch restituisce valori driver senza pipeline equivalente. |
| F09 | `var_*`, formule varianti e parametri isolati | Assente | `LC:427` scrive currentEnv e rinomina bind per virtuale/colonna. Nuovo binding è per piano, non namespace per variante. |
| F10 | `#ENV`, `#PREF` | Rifiutato | `LC:314`, `LC:320`; `NC:369`. `:env_name` moderno è bind di valore e non metodo env_name/preferenza o SQL literal interpolato. |
| F11 | `#IN_RANGE` | Rifiutato | `LC:1309` tratta NULL e limiti inclusivi; riscrivibile con SQL trusted, senza macro equivalente. |
| F12 | `#PERIOD` | Rifiutato | `LC:1341` decodifica locale/workdate e muta params; nessun calendario/decoder nella compilazione nuova. |
| F13 | `#BAG`, `#BAGCOLS` | Rifiutato | `LC:1274`, `LC:1291` registrano trasformazioni dei risultati. Dtype X presente non certifica codec o espansione. |
| F14 | TSQUERY/TSRANK/TSHEADLINE/VECQUERY/VECRANK | Rifiutato | `LC:239`, `LC:421`, `LC:962`, `LC:1094` delegano macro adapter. SQL PostgreSQL equivalente scritto a mano non equivale alla macro. |
| F15 | Funzioni SQL scalari, CASE, CAST, window | Parziale | Passaggio come SQL trusted con AS, `NC:340`, `NC:377`. Nessuna validazione generale degli argomenti, tipo inferito o portabilità inter-dialect. |
| F16 | GEP `@invoices.sum($total)`, count(), to_array/to_json | Assente/rifiutato | `G1:14`, `G1:127` richiedono funzioni di percorso con granularità propria. `_PATH` termina prima della parentesi; nessun nodo aggregato relazionale. |
| F17 | manyRelation filtrata / nuova virtualRelation | Assente | `G2:14`, `G2:44`; Relation fisica del nuovo resolver non include query derivata, binding sorgente-destinazione, filtro nominato o cardinalità garantita da limit. |

## Aggregazione, parametri e ciclo di esecuzione

| ID | Caso | Stato attuale | Differenza ed evidenza |
|---|---|---|---|
| Q01 | COUNT/SUM SQL espliciti con AS | Parziale | `NC:340` passa SQL. `COUNT(*) AS n` compila senza pkey implicita; nessun concetto di aggregato nel piano. |
| Q02 | group_by/having | Rifiutato | `LC:831`, `LC:1046`; `NA:33` e opzioni sconosciute `NC:443`. QueryPlan non ha campi dedicati. |
| Q03 | group_by='*' | Rifiutato | `LC:888` segnala aggregazione senza GROUP BY SQL. Non sostituibile con una colonna chiamata `*` o default moderno. |
| Q04 | distinct esplicito / automatico | Rifiutato/assente | `LC:1050`; nuovo non ha DISTINCT strutturale né row explosion. Inserire DISTINCT in SQL opaco non crea un contratto distinto. |
| Q05 | `.count()` | Rifiutato | `LQ:557` ha ramo gruppi/distinct/plain/multistore; `NA:130` richiede aggregate esplicito. Il risultato COUNT è una riga, non quel terminale scalare. |
| Q06 | AggregateRows/explodingColumns | Rifiutato intenzionalmente | Vecchio flusso registrato in `LC:663`, descritto `G1:51`; `NA:33`, `NC:354` lo escludono. Non reintrodurre dedup dtype-based mascherato da selection. |
| Q07 | Parametri scalari :name | Supportato | `NC:140`, `NP:24`; quoting identificatori distinto dai bind. Le espressioni sono codice trusted, i valori restano dati. |
| Q08 | `IN :ids` con lista/tuple/set | Parziale, non equivalente | Legacy `LP:147` converte liste/set in tuple e tratta alcuni vuoti; nuovo conserva un solo Parameter con valore collezione, non espande IN. Compilazione riuscita non prova SQL psycopg3 eseguibile. |
| Q09 | `:param` il cui valore è `$column`/`@relation.field` | Cambiato intenzionalmente | `LC:802` embedFieldPars converte certi valori in sintassi; `NC:140` li mantiene dati. Non ripristinare interpolazione implicita senza API strutturata esplicita. |
| Q10 | `:env_name` | Supportato con semantica nuova | Snapshot per piano `NC:434`, binding `NC:140`; espliciti prevalgono. `NA:105` ricompila ai terminali; legacy LQ:220 conserva il compilato. |
| Q11 | Commenti, stringhe, dollarquote, ::, percentuali | Supportato nel profilo lexer | `ND:15` circa lexer, `NC:340`, `NP:24`: token protetti e escaping del protocollo. Non implica parser SQL o sandbox per SQL trusted. |
| Q12 | REGEXP portabile legacy | Assente | `LP:166` riscrive REGEXP in ~*. Nuovo dialect non riscrive operatori testuali arbitrari; usare operatore PostgreSQL esplicito. |
| Q13 | limit/offset | Supportato | `NC:460`, `ND:214`: interi non negativi, bool rifiutati. Nessun ordine stabile inferito automaticamente. |
| Q14 | for_update | Supportato con scelta più precisa | `LC:1101`; `ND:140`, `ND:220`: bool rigoroso, solo SELECT, capability e `FOR UPDATE OF` alias root. Aggregate/window incompatibili restano errori SQL del server. |
| Q15 | Draft e cancellazione logica root | Supportato | `LC:984`; `NC:263`. IS NOT TRUE e IS NULL; mark restituisce tombstone effettivo. Non filtra automaticamente target dei JOIN. |
| Q16 | Mark su formule/aggregati | Rifiutato | `NC:279` richiede proiezioni fisiche; legacy omette mark se aggregate/count. Stesso parametro non garantisce stessa forma risultato. |
| Q17 | Partition e missing context | Supportato con semantica deliberatamente stretta | `NC:190`, `NC:206`: missing entrambi errore, current/allowed intersezione, [] FALSE, NULL esplicito, scope multipli AND. Non è sinonimo di subtable o partizionamento fisico. |
| Q18 | subtable e condizioni env arbitrarie | Rifiutato/assente | `LC:953`, `LC:964`, `NA:35`; nessun parsing sottotabelle &/\|/! o env_*_condition nel nuovo profilo. |
| Q19 | fetch e metadata | Parziale | `LQ:241` postprocessa, selection arricchisce; `NA:123`, `NP:75` restituiscono dict e ResultColumn. Alias, dtype formule opache, pkey e codec differiscono. |
| Q20 | Record query e lazy/eager/Bag | Parziale | Legacy compiler dedicato `LC:1106`; moderno `NA:134` usa query con controllo cardinalità e cache, solo output dict. Non ricrea resultmap o resolver relazionali. |

## Prove mirate eseguite in questo audit

Eseguite offline con PostgresCompiler su tre Table manuali, senza server e senza
modificare sorgenti o introdurre test permanenti:

1. `@mid.@leaf.id` fallisce con `ValueError: Computed SQL expressions require an explicit AS alias`.
2. `@mid.leaf.id` genera due LEFT JOIN e proietta `t2.id` come `mid_leaf_id`.
3. `columns='*'` su id + formula calc genera entrambe, calc come `(t0.id+1)`.
4. `COUNT(*) AS n` genera una SELECT aggregata senza colonne extra.
5. `$id IN :ids` con `[1,2]` genera `... IN %(ids)s`, parametro ancora lista.
6. `$id=:field` con `field='$id'` conserva `$id` come valore bind, senza trasformarlo in riferimento.

La prova 5 locale verifica la mancanza di espansione. Separatamente il root ha
eseguito [native_binding_probes.py](evidence/native_binding_probes.py), con
[risultati PostgreSQL](evidence/native_binding_probes.json): `IN :ids` fallisce
con SyntaxError (42601) per lista, tuple e lista vuota; `IN (:ids)` con lista
fallisce con UndefinedFunction (42883); `= ANY(:ids)` con `[1,2]` restituisce
id 1 e 2, con `[]` nessuna riga. Il JSON serializza la tuple come array; la
distinzione del tipo originale è nello script. Non è stata eseguita la stessa
query sul legacy: questo è un test del nuovo profilo, non un oracle comparativo.

Ulteriori probe root: [script delle funzionalità](evidence/native_feature_probes.py)
e [risultati](evidence/native_feature_probes.json) distinguono errori alla
risoluzione del modello, costruzione query e compilazione terminale.
`aliasColumn`, select/exists, subQueryColumn e pyColumn falliscono già nella
risoluzione: non vanno descritti come capacità operative solo perché esiste
il nodo Builders. Formule stringa e catene di formule compilano.

Le osservazioni legacy sono letture dei rami della baseline: non è stato
eseguito un confronto end-to-end completo fra i due stack.

## Esempi applicativi reali e proposte reperite

Root applicativo: `/Users/gporcari/Sviluppo/Genropy/genropy/projects/gnrcore/packages`.
Questi esempi provano che le funzionalità sono richieste da codice locale;
non certificano che tutto quel codice sia esercitato in produzione.

| Fonte | Caso concreto | Impatto sul profilo moderno |
|---|---|---|
| `adm/model/connection.py:18` | aliasColumn user_fullname via @userid.fullname | Serve mapping semantico dell'alias di modello, non solo formula SQL testuale. |
| `adm/model/api_token.py:30` | formula select su token_tag con #THIS.id | Subquery correlata reale, oggi assente. |
| `adm/model/user.py:51` | string_agg dei gruppi, correlazione e confronto con campo esterno | Aggregato per riga root; un JOIN + SUM generale non è equivalente. |
| `adm/model/notification.py:28` | EXISTS manuale con :env_user_id e #THIS.id | Anche SQL quasi interamente manuale usa scope legacy e macro, oggi rifiutata. |
| `adm/model/group.py:19` | select_tg nominata | La formula non è soltanto un'unica stringa SQL. |
| `sys/model/calendar.py:30` | formula con aggr dinamico e legame #THIS.date | Occorrono dichiarazione derivata e correlazione, non solo SQL function passthrough. |
| `sys/model/task.py:50` | select correlata task_execution su stato temporale | Filtri interni e lifecycle task dipendono dal risultato per root. |
| `adm/model/counter.py:435` | query group_by su campo scelto | GROUP BY è una necessità applicativa concreta, non soltanto reporting futuro. |

`G1:59` descrive il dataset 13 fatture/43 righe e i difetti della deduplicazione
Python e del DISTINCT implicito: dati e risultati numerici sono evidenza del
documento, non misure rieseguite qui. Il contratto proposto impone una subquery
correlata per aggregato di relazione, mantiene la granularità e permette più
relazioni nella stessa SELECT. `G2:44` propone relazioni filtrate nominate,
condizione nel JOIN o nella subquery e parametri `:env_*`.

La ricerca locale ha trovato GEP 1 e 2 ma non un documento autonomo denominato
virtualRelation né la discussione integrale dell'issue 1. Le specifiche già
raccolte in `docs/design/04-objectives.md:95` e `05-decisions.md:93` vanno tenute
come fonte separata per la proposta più recente. Non dedurre che manyRelation
GEP 2 esaurisca virtualRelation, né presentare il vecchio attributo `virtual`
di LC come l'implementazione della nuova proposta.

## Priorità e gate proposti

### P1 — Contratto di compatibilità osservabile

Prima di dichiarare equivalenza sintattica occorre decidere e testare:

- Percorsi canonici `@rel.@rel2.field`, eventuale alias compatibile senza @,
  segmenti quotati e messaggi di errore per percorsi incompleti.
- IN/NOT IN collezioni: liste vuote, NULL, duplicati, tipi non supportati,
  eventuale alternativa PostgreSQL ANY; niente sostituzioni regex su letterali.
- Proiezioni: alias default, pkey aggiunta solo nel profilo compatibile,
  collisioni pkey/id, wildcard X e virtuali, ordine di output e metadata.
- Ordine di tabella: default esplicito o comportamento solo compatibile;
  paginazione deve avere test su ordine stabile, non soltanto SQL snapshot.
- GROUP BY/HAVING/DISTINCT come campi del piano, count come terminale con
  definizione di righe/gruppi e relazione con limit/offset, non riscritture ad hoc.

### P1 — Scope per formule correlate e virtualRelation

Introdurre scope interno/esterno e alias allocator, con nodi strutturati per
subquery e correlazione. Prima del renderer fissare: policy della tabella
interna, parametri isolati per due varianti della stessa formula, cardinalità
zero/uno/molti, cast e NULL. Il legacy applica default interni particolari in
`LC:414` (ignorePartition=True, draft/deleted inclusi, subtable='*'): copiarli
silenziosamente nel moderno sarebbe una decisione di visibilità dei dati,
non un dettaglio di rendering.

La nuova virtualRelation deve entrare in questo contratto senza essere ridotta
a FK senza constraint. Aggregati su due rami many devono conservare la propria
granularità: mai tornare a DISTINCT seguito da aggregateRows.

### P2 — Macro e trasformazioni selezionate

Inventariare chiamanti e frequenze prima di implementare tutte le macro.
IN_RANGE e PERIOD richiedono semantica documentata; ENV/PREF non devono ricreare
interpolazione pericolosa di valori. Bag, py_method e decrittazione appartengono
anche al contratto dei risultati e non si risolvono aggiungendo un token al lexer.

### Matrice minima dei test semantici successivi

| Gate | Dataset e asserzione richiesta |
|---|---|
| T01 Percorsi | Tre tabelle to-one, riuso join fra formula/where/order, alias di relazione e percorso legacy a due @. |
| T02 Cardinalità | Due relazioni many con duplicati di valore: SUM per ramo corretta, nessuna moltiplicazione incrociata, zero aggregateRows. |
| T03 Parametri | IN e NOT IN per []/[1]/[1,1]/[None]/[1,None], stringhe contenenti :name, cast ::, bind list esplicito ANY distinto da IN. |
| T04 Proiezioni | Root con PK nominata code, colonna reale pkey, formula statica/dinamica e X: nomi, ordine e dtype esatti per ciascun profilo. |
| T05 Aggregati | COUNT(*) vs COUNT(nullable), COUNT DISTINCT, gruppi NULL, HAVING, DISTINCT con order/pagination; terminale count con contratto esplicito. |
| T06 Correlazione | Stessi nomi id nei due scope, due formule su stessa relazione con parametri diversi, formule annidate, collisioni alias e bind. |
| T07 Policy interne | Root visibile e target draft/deleted/fuori partition: risultato atteso per ogni politica interna esplicita. |
| T08 Macro | Limiti range NULL/inclusivi, periodo singolo/aperto/locale/workdate, stringhe con macro che restano letterali. |
| T09 Lock | SELECT to-one con FOR UPDATE OF root; seconda connessione verifica effettivo blocco root e assenza lock aggiunto sul target. |
| T10 Risultati | Alias rinominato conserva source identity; formula SQL opaca non inventa dtype; Bag e postprocessor dichiarati separatamente. |
| T11 Lazy/env | Stessa query riusata in due ambienti, SQL ispezionato prima del fetch, parametri espliciti prioritari, record cache e refresh distinti. |
| T12 Errori | Callback/formule/select e opzioni importate non implementate rifiutate o diagnosticate: nessuna dichiarazione ignorata che generi un risultato plausibile ma diverso. |

Le priorità indicano dipendenze semantiche, non richiedono un'importazione
integrale del legacy. Un mixin compatibile può conservare default e nomi legacy;
la compilazione moderna deve mantenere visibili scope, cardinalità, policy e
identità del risultato per evitare equivalenze soltanto apparenti.


## Riproduzione autonoma della differenza multi-hop

Questo snippet non apre connessioni e distingue i due spelling sullo stesso
modello, eliminando differenze di schema come possibile causa:

```python
from genro_sql.compiler import PostgresCompiler
from genro_sql.contracts import Column, Relation, ResolvedModel, Table

leaf = Table('leaf', schema='p', pkey=('id',), columns={'id': Column('id')})
mid = Table('mid', schema='p', pkey=('id',), columns={'id': Column('id')},
            relations={'leaf': Relation('leaf', 'p.leaf', ('id',), ('id',))})
root = Table('root', schema='p', columns={'id': Column('id')},
             relations={'mid': Relation('mid', 'p.mid', ('id',), ('id',))})
compiler = PostgresCompiler(ResolvedModel({t.key: t for t in (root, mid, leaf)}))
for expression in ('@mid.@leaf.id', '@mid.leaf.id'):
    try:
        print(expression, compiler.select('p.root', expression).sql)
    except ValueError as error:
        print(expression, type(error).__name__, str(error))
```

Risultato: la forma legacy a due `@` viene rifiutata; la seconda crea due LEFT
JOIN. Non è un problema di cardinalità: tutti i target hanno una PK dichiarata.
Con `AS result` esplicito sulla prima forma l'errore può arrivare alla risoluzione
del campo invece che alla deduzione dell'alias: cambiare il messaggio non elimina
l'incompatibilità grammaticale.

## Quattro significati distinti di alias

1. **Alias di output SQL**: `$amount AS total` dà un risultato chiamato total.
   Non dichiara una nuova colonna del modello. Il nuovo `ORDER BY total` resta
   SQL trusted; `ORDER BY $total` richiede invece una vera colonna/formula total.
   Non attribuire al legacy un'espansione generale di `$total` solo perché
   `aliasDict` conserva il nome del risultato (`LC:1016`).
2. **Alias di modello**: `aliasColumn('customer_name', relation_path=...)`
   permette `$customer_name` tramite getVirtualColumn (`LC:366`). Nel nuovo
   modello la dichiarazione è esplicitamente rifiutata (`model.py:63`), mentre
   una formula stringa con quel percorso è una rappresentazione alternativa.
3. **Alias in relationDict**: il legacy può ricevere una mappa di nomi logici a
   percorsi (`LC:118`, `LC:709`, `LC:1030`). Il caso speciale `$pkey` è popolato
   automaticamente (`LC:895`). Il nuovo ha solo lookup dei nomi del modello e
   rifiuta relationDict; `$pkey` non è sinonimo universale della primary key.
4. **Alias di percorso di tabella**: `LC:488` espande table_aliases prima di
   creare il JOIN. Non equivale né a `AS t1` SQL né a una formula del modello;
   questo meccanismo non è presente nel resolver attuale.

Gate aggiuntivo: costruire una tabella con PK code e senza colonna pkey, provare
`$pkey`, una relationDict che mappa un nome a un percorso, una aliasColumn e
`$amount AS total` con entrambe le forme di ORDER BY. Confrontare separatamente
nomi risultato, accesso via `$name` e identità della colonna: sono tre contratti.
