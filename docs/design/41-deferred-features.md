# 41 — Funzionalità rinviate

Aggiornato il **16 ottobre 2026**. Registro dei rinvii esplicitamente decisi
durante la definizione del core. Il rinvio non è una rimozione definitiva.
Le funzionalità ancora da discutere o da implementare non entrano in questo
elenco automaticamente: restano nei rispettivi contratti e piani.

## R-01 — `toolColumn`

**Decisione:** omessa per ora dalla grammatica obiettivo e dal lavoro corrente
sul modello, su indicazione dell'utente del 12 ottobre 2026.

**Funzione nel legacy:** colonna virtuale che costruisce un collegamento a uno
strumento associato al record. Una formula SQL genera HTML con un URL della
forma `<external_host>/_tools/<tool>?record_pointer=<record_pointer>`:
un elemento `<a>` con testo o icona, oppure `<img>` per `dtype='P'`.

**Riferimenti verificati:** repository GenroPy,
`gnrpy/gnr/sql/gnrsqlmodel/model.py`, metodo `toolColumn`, e
`gnrpy/gnr/sql/gnrsqlmodel/helpers.py`, funzione `toolFormula`.
La [revisione comparativa](../review/asqueel-vs-genropy-it.html) registra un
uso applicativo; la [proposta 0001](../proposals/0001-model-and-expressions.md)
ne riportava il contratto come aperto.

**Alla ripresa:** decidere se conservare la forma legacy o descrivere nel
modello il riferimento allo strumento e affidare l'HTML alla UI. Quest'ultima
è una possibilità discussa, non una soluzione approvata. Nessun adapter o
comportamento sostitutivo è stato deciso con questo rinvio.

## R-02 — Record di sistema (`sysrecords` / `system_records`)

**Decisione del 13 ottobre 2026:** per ora la funzione non viene implementata.
Sono rinviate l'espansione strutturale e la gestione dei record di sistema.
La proposta di ricondurre la firma a `sys_fields(sysrecords=...)` non è stata
approvata né applicata. La dichiarazione `system_records` già presente nel
codice resta soltanto una proposta grammaticale, non una funzione implementata.

**Conferma successiva del 13 ottobre:** system_records resta fuori perimetro;
si valuterà in futuro se reintrodurre il concetto. Asqueel deve avvicinarsi al
legacy nel perimetro concordato, non sostituire ora GenroPy integralmente.
Gli scarti strutturali sono accettati come divergenze da documentare (52, D-01).
**Decisione successiva:** `sys_fields(syscode=True)` è approvata e implementata
per la sola colonna `__syscode`, A size `:20`, indicizzata e UNIQUE. È un flag
False per default. Non riattiva system_records, i relativi virtuali, la
rilevazione di metodi sysRecord_* o la creazione/gestione dei record.

**Riferimento legacy:** `gnrpy/gnr/app/gnrdbo.py`, `sysFields`, ramo `sysrecords`:
attivazione esplicita o rilevamento dei metodi `sysRecord_*`; aggiunta di
`__syscode`, `__protected_by_syscode` e `__invalid_by_duplicate_sysrecord`.
La creazione dei record è separata, nei metodi `sysRecord` e `createSysRecords`.

**Alla ripresa:** ripartire dal legacy e dal presente rinvio, senza assumere
concordati i parametri `records`, `masterfield`, `tag` della proposta precedente.

## R-03 — Versionamento dei dati (`release`)

**Decisione del 13 ottobre 2026:** funzione rinviata, inclusa l'espansione
automatica della colonna `__release`. La firma proposta `release(handlers=...)`
non è approvata; la dichiarazione presente nel codice non esegue trasformazioni.

**Riferimento legacy:** `gnrpy/gnr/app/gnrdbo.py`, `sysFields`, aggiunge
`__release` di tipo L quando rileva metodi `_release_*`. In
`gnrpy/gnr/sql/gnrsqltable/utils.py`, `getReleases` e
`updateRecordsToLastRelease_raw` gestiscono separatamente le trasformazioni
dei dati e l'aggiornamento della versione dei record.

**Alla ripresa:** ripartire dal legacy e distinguere la dichiarazione strutturale
dall'esecuzione delle trasformazioni, senza assumere necessario `handlers`.


## R-04 — Alias di tabella (`aliasTable`)

**Decisione del 13 ottobre 2026:** per ora `aliasTable` esce dalla grammatica.
**Chiarimento dell’utente:** `virtualRelation` resta, compresa la forma
`virtualRelation(name, relation=...)`. È esclusa soltanto la firma `aliasTable`.

**Riferimento legacy:** `gnrpy/gnr/sql/gnrsqlmodel/model.py`, metodo
`aliasTable(name, relation_path, **kwargs)`. In `invc/invoice_row.py`, l'alias
`customer` abbrevia `@invoice_id.@customer_id`; non crea una tabella fisica.

L’esempio nativo usa `virtualRelation`. Il ponte dalla source legacy espansa
continua a tradurre `table_aliases` in questa forma. Il JSON fisico per
migrations non è interessato dal rinvio della firma `aliasTable`.
`aliasColumn` e i join condizionali sono costrutti distinti: questo rinvio
non li esclude. La firma dei join condizionali resta da rivedere con il legacy.


## R-05 — Inverse delle relazioni virtuali

**Decisione del 13 ottobre 2026:** rinviate. Rimosso `inverse` dalla firma di
`virtualRelation` e rimossa la generazione automatica della relazione inversa.
Non si introducono `reverse_name`, `reverse_one_one` o altre firme sostitutive.
Le inverse delle relazioni ordinarie restano invariate.

**Riferimento:** [revisione della GEP 2, §6](https://github.com/genropy/genropy_meta/issues/1#issuecomment-5803053743).
La discussione parla di generazione su richiesta a partire dai termini che
collegano sorgente e destinazione. Per i filtri lascia aperto se vietare
l'inversa o registrarla senza filtro; non formalizza il parametro `inverse`.

**Alla ripresa:** decidere firma e semantica a partire da questa discussione.
Il ponte legacy conserva `relation_name` come metadato della dichiarazione,
senza trasformarlo in un'inversa virtuale del modello.


## R-06 — Limit, order_by e one_one su virtualRelation

**Decisione del 13 ottobre 2026:** rinviati ed esclusi dalla grammatica di
`virtualRelation`. È una differenza esplicitamente approvata rispetto alla
[revisione della GEP 2](https://github.com/genropy/genropy_meta/issues/1#issuecomment-5803053743),
che li includeva. La precedente decisione «limit richiede order_by» è superata
dalla rimozione di entrambi; non serve ora decidere come derivare da una
relazione già limitata.

Il costrutto conserva collegamento, filtri, binding var_* e ask. Selezione dei
primi N, ordinamento e dichiarazione di cardinalità one_one sulla relazione
virtuale restano fuori perimetro. Query e subQueryColumn non cambiano, così
come one_one sulle relazioni ordinarie.

Le source dirette o importate con questi attributi vengono rifiutate anche
se valorizzati a None/False. Il ponte dalla source legacy espansa conserva
one_one nel solo metadata legacy, senza promuoverlo ad attributo nativo della
virtualRelation. Il JSON fisico per migrations non è interessato.

**Alla ripresa:** ripartire dalla GEP e da questa semplificazione concordata,
senza presumere approvate selezioni per record, propagazioni di cardinalità o
regole di composizione dei limiti.


## R-07 — Diagnostica e invalidità configurabili sulla tabella

**Decisione del 13 ottobre 2026:** `diagnostic`, `invalidFields` e
`invalidRelations` non sono portati in questa fase. Saranno riconsiderati
come opzioni di tabella. La firma proposta `diagnostics(rules=...,
invalid_fields=..., invalid_relations=...)` non era stata concordata ed è
rimossa dalla grammatica attiva, non mantenuta come contratto futuro.

**Riferimento legacy:** `gnrpy/gnr/app/gnrdbo.py`, `GnrDboTable.sysFields`:
`diagnostic` è un attributo di tabella e aggiunge `__warnings` e `__errors`;
`invalidFields` e `invalidRelations` sono parametri distinti, che aggiungono
`__invalid_fields` quando richiesto e la formula `__is_invalid`.
Nessuna di queste attivazioni compare nei package di `test_invoice_pg`
auditati nel rapporto 52.

Questi rami opzionali restano fuori dall'espansione. Il rinvio non riguarda
le quattro virtuali di base che il legacy aggiunge sempre con sysFields
(`__protecting_reasons`, `__is_protected_row`, `__invalid_reasons`,
`__is_invalid_row`), già censite separatamente.

**Alla ripresa:** riesaminare i singoli flag legacy e decidere le firme di
tabella; non presumere approvati il raggruppamento diagnostics o rules.

## R-08 — Macro `#PREF`

**Decisione del 14 ottobre 2026:** annotata tra le funzionalità legacy non
portate; esclusa dal lavoro corrente sul compilatore.

**Funzione nel legacy:** `#PREF(path, default)` legge una preferenza del
package della tabella durante la compilazione. `expandPref` in
`gnrpy/gnr/sql/gnrsqldata/compiler.py` chiama
`curr_tblobj.pkg.getPreference(path, default)` e inserisce nel SQL il valore
convertito in stringa.

**Caso concreto:** `invc.invoice_row.adjusted_total` dichiara
`$line_total * #PREF(markup_rate,1)`. La dichiarazione resta conservata nel
modello, ma la sua compilazione resta esplicitamente non supportata. Non si
sostituisce la macro con il default né con un nuovo meccanismo di preferenze.
Nel censimento delle 462 formule questa è un'esclusione concordata, non una
funzionalità ancora da completare nel perimetro corrente.

**Alla ripresa:** riesaminare il contratto delle preferenze del package e
l'espansione legacy, senza presumere approvata un'API sostitutiva.

## R-09 — Query concatenate e operatori fra query

**Decisione del 14 ottobre 2026:** rinviare per ora entrambi i fronti:

- concatenazione `q.query(...).query(...)` come SELECT FROM SELECT, compresi
  i JOIN esterni attraverso le colonne proiettate;
- operatori `+` UNION, `|` UNION ALL, `&` INTERSECT e `-` EXCEPT.

Il rinvio riguarda i passi 3 e 4 del piano 56 e le relative verifiche combinate.
Non revoca le firme già concordate, non elimina l'indagine legacy e non
riguarda le sottoquery delle formule `select`, `exists`, `select_*` già portate.
Questi due fronti non bloccano il completamento della query singola.

**Alla ripresa:** riutilizzare il piano 56 e il riesame dei branch nel rapporto
57, verificando nuovamente le premesse sul compilatore allora disponibile.


## R-10 — Compilazione delle relazioni verso molti sul nuovo albero

**Aggiornamento del 16 ottobre 2026:** non portare le JOIN verso molti,
le righe esplose e il DISTINCT implicito del legacy. Il percorso di lettura
è ormai unico; count e aggregati numerici sono implementati nel
[passo 103](103-numeric-many-aggregates.md), join e ordine nel
[passo 104](104-join-ordered-many-aggregates.md), JSON nel
[passo 105](105-json-many-aggregates.md), XML Bag PostgreSQL nel
[passo 106](106-xml-many-aggregates.md).

Si riconosce `@relazione.operazione(argomenti)` e si cerca l'handler `many_*`
tramite getattr. L’handler `many_aggr` compila count/sum/avg/min/max, join, to_json e to_xml, con ordine base
o override `.order_by(...)`; XML è disponibile solo su PostgreSQL. La sintassi concordata
usa **soltanto `.aggr(...)`** come aggregazione, con `count`, `sum`, `avg`,
`min`, `max`, `join`, `to_json` e `to_xml` al suo interno, espressioni e risultati
su più colonne con alias. `to_xml` produce XML compatibile con Bag; `join`
prevede un placeholder per valore vuoto, di default `''`. L’ordine base della
tabella si applica automaticamente e `.order_by(...)` lo sostituisce. Vale per
relazioni ordinarie e virtualRelation verso molti: niente proiezioni nude.

Decisioni e punti ancora aperti sono nel
[documento 101](101-many-aggregation-decisions.md). I precedenti esempi di metodi
diretti sum/calc/first/last non definiscono la grammatica attuale. Prima/ultima
riga ordinata restano rinviate; XML Bag è implementato su PostgreSQL.
LATERAL è un'eventuale tecnica SQL,
non una firma pubblica approvata.

**Alla ripresa:** i contratti approvati delle aggregazioni passano, senza xfail
([rapporto 106](106-xml-many-aggregates.md)). `to_xml` è disponibile su PostgreSQL; SQLite non ha la capability,
senza fallback. `to_json` è implementato su entrambi.
Non introdurre aggregazioni automatiche né importare il meccanismo exploding.
Il [rapporto della fase 2](88-legacy-rewrite-phase2.md) conserva l'evidenza storica.


## R-11 — Wildcard avanzati

**Decisione del 15 ottobre 2026:** mantenere soltanto `*` e le colonne esplicite.
Escludere dalla TODO i wildcard per prefisso o percorso di relazione: non sono
necessari per chiudere il perimetro corrente del compilatore.
Restano disponibili le espressioni e i riferimenti espliciti già supportati,
compresi `$campo` e i percorsi `@relazione.campo` verso uno.

**Non portati:** `*@relazione`, `*@relazione.prefisso_`,
`*@relazione.(campo1,campo2)` e la variante `*prefisso_` descritta nel legacy.
Quest'ultima richiede una precisazione: il ramo locale di `expandMultipleColumns`
nel riferimento esaminato restituisce tutte le star columns, senza filtrare
il prefisso. Non si assume il docstring come comportamento implementato.

**Evidenza:** la ricerca Sourcerer ha trovato usi delle forme avanzate nei test
e nella documentazione, senza evidenza applicativa nei risultati esaminati.
La ricerca letterale `*@` è completa nell'indice consultato; quella più generale
sui prefissi è parziale e non esclude costruzioni dinamiche. Dettagli e limiti
nel [censimento](evidence/wildcard-usage/sourcerer.json).
La decisione privilegia la semplicità e non dipende da una pretesa assenza
assoluta di usi nel legacy.

**Effetto:** nessuna modifica al codice; sul nuovo albero rimane il rifiuto
esplicito delle forme avanzate. Un eventuale recupero richiederà un'esigenza
concreta e una nuova decisione, senza reintroduzione automatica durante il port.


## R-12 — ask nelle virtualRelation

**Decisione del 16 ottobre 2026:** per ora non serve. Escluso dalla TODO attiva
delle letture e delle aggregazioni. Dichiarazione, contesto e punti da riprendere
sono conservati nel [documento separato 108](108-deferred-virtual-relation-ask.md).
Nessuna modifica al codice: la grammatica conserva la dichiarazione, mentre
il compilatore continua a rifiutarne l'uso nelle aggregazioni.
