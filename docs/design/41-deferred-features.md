# 41 — Funzionalità rinviate

Aggiornato il **13 ottobre 2026**. Registro dei rinvii esplicitamente decisi
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
