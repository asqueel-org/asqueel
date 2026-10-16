# 111 — Consegna letture e stato per la prima versione riunificata

Fotografia del **16 ottobre 2026**, dopo il raccordo di `table=`.
Questo report aggiorna la consegna 99: le aggregazioni e le virtualRelation sono
ora implementate nel perimetro concordato. La fusione con le scritture non è
ancora certificata. Il report non autorizza nuove sintassi o recuperi impliciti
delle funzionalità rinviate.

## Obiettivo attuale

L'utente chiede di riunificare letture e scritture e ottenere una prima versione
operativa per un progetto nuovo. La compatibilità integrale con GenroPy non è
un requisito per questa prima versione. Prima si verifica l'integrazione, poi
si fissa il perimetro effettivamente utilizzabile, con esempi e limiti espliciti.
Il lavoro corrente consegna commit e stato; non esegue la fusione, non cambia
versione e non pubblica.

## Basi e stato Git rilevati

| Fronte | Branch e commit | Stato della consegna |
| --- | --- | --- |
| Letture | `codex/core-single-read-path`, codice `d1c61490e4d637f7925df375fbed007ba619b2df` | Include tutte le aggregazioni, derivazioni, forma diretta, correzione AS, test ed evidenze. Il commit documentale che contiene questo report è successivo e va incluso nella consegna. |
| Scritture | `plan/write-cycle`, HEAD `1995fe4e9b18656778a19ac7db65594adce770d2` | Fusione aperta di `531d87b29c477450794bc448e64d263cbda59d0e`; Git segnala conflitti risolti e modifiche staged, ma manca il commit di fusione. Nessun intervento effettuato da questa sessione sul worktree del writer. |

Worktree letture: `/Users/gporcari/Sviluppo/asqueel/asqueel-read-path`.
Worktree scritture: `/Users/gporcari/Sviluppo/asqueel/asqueel/worktrees/write-cycle`.
Base comune dei due fronti prima di questa consegna:
`e96f0c14c27ab3366b7240de67c713b5712c4a50`.

Il merge già aperto nel writer contiene le letture precedenti alle aggregazioni.
Non basta concluderlo per acquisire `d1c6149`. Prima di integrare bisogna rileggere
HEAD, MERGE_HEAD, index e working tree: questa è una fotografia, non un invito
a scartare o sovrascrivere eventuale lavoro successivo.
I commit di questa consegna sono locali; nessun push è stato eseguito.

## Letture: stato verificato

| Stato | Funzionalità |
| --- | --- |
| 🟢 | Modello gerarchico unico, opzioni espanse, ramo relations; eliminato il percorso di lettura duplicato. |
| 🟢 | SQL e kwargs separati, adapter, riferimenti `$campo` e `@relazione.campo`, alias e scope dei parametri distinti. |
| 🟢 | Relazioni verso uno, alias con relazione weak ereditata e precedenza della relazione esplicita. |
| 🟢 | Formule SQL e da metodo, dipendenze, `var_*`, select/exists/select_*, subQueryColumn nel profilo supportato. |
| 🟢 | WHERE, ORDER BY, GROUP BY/HAVING, DISTINCT, LIMIT/OFFSET, `*`, statiche, filtri impliciti concordati. |
| 🟢 | `fetch()` con NamedList modificabili per nome/posizione; `count()`; `record()` dict/Bag nel profilo supportato; lock PostgreSQL/SQLite. |
| 🟢 | `.aggr(count/sum/avg/min/max/join/to_json/to_xml)`, espressioni, formule e campi in relazione; alias concordati, collisioni con prevalenza dell'ultimo. |
| 🟢 | Ordine base e `.order_by()`; placeholder join per NULL/stringa vuota; risultati senza righe concordati. |
| 🟢 | JSON su PostgreSQL/SQLite; XML compatibile con Bag su PostgreSQL, senza fallback SQLite. |
| 🟢 | VirtualRelation con condition/var_*, derivazioni in AND e scope distinti per livello; `table=` con condition obbligatoria. |
| 🟢 | Correzione AS tramite splitter esistente: due CAST nella proiezione conservati; XML senza obbligo di alias esplicito. |

Le aggregazioni verso molti sono una grammatica Asqueel approvata: non vengono
attribuite al legacy. Si riusano gli algoritmi già portati per riferimenti,
correlazioni, sottoquery, mangler e delega agli adapter.

### Verifiche disponibili

- Suite completa del perimetro letture: **4531 passed, 42 skipped, 16 deselected**
  e due fallimenti documentali, risolti rigenerando `docs/grammar.md` con il
  generatore esistente. Rieseguiti tutti i sei test dei due moduli documentali:
  **6 passed**. Esiti finali combinati: **4533 passed, 42 skipped**, nessun
  fallimento o xfail residuo; non è un singolo run da 4533 passed.
- Aggregazioni, formule e grammatica virtualRelation: **332 passed, 22 skipped**.
  Sola suite aggregazioni: **274 passed, 22 skipped**, con catalogo Bag disponibile.
- Il passo table= aggiunge **37 passed, 1 skip di dialetto**, più cinque nuovi
  casi di validazione della grammatica.
- Ruff e mypy: passano; mypy verifica 59 file sorgente nell'ambiente con le
  dipendenze corrette. Verifica ripetuta alla consegna e negli hook del commit.
- La struttura dei 74 modelli e il JSON migration hanno i confronti documentati
  nei passi precedenti e i relativi test nella suite letture. Non equivale a
  verificare il risultato di ogni formula del corpus su dati reali.
- Scritture escluse dal manifesto delle letture come concordato. Nessuna CI
  unificata, installazione della futura release o prova end-to-end CRUD sul
  branch riunificato è certificata da questi numeri.

Evidenza riproducibile: [table=](evidence/many-aggregation-contracts/direct-table.json).
Dettagli e contratti: [101](101-many-aggregation-decisions.md),
[107](107-outer-as-projections.md), [109](109-derived-virtual-relations.md),
[110](110-direct-virtual-relations.md).

## Scritture: codice presente, integrazione ancora da verificare

Ispezione in sola lettura del branch del writer:

- `write_compiler.py`: compilatore DML dedicato sul modello gerarchico, insert,
  insert_many, update, delete, operazioni su selezione e lock di tabella.
- `table_crud.py`, `db_write.py`, `table_triggers.py`: ciclo di scrittura,
  generazione pkey, trigger/protezioni e azioni sui record correlati.
- `application_table.py`: comandi `sql_insert/sql_update/sql_delete` e terminali
  di query `sql_update/sql_delete`, accanto alle letture del modello unico.
- Commit recenti: `2cbdc1a` (compilatore DML), `a77d304` (comandi sql_*),
  `3b3aff4` (ciclo), `4c910ba` (raccordo su tabella/database), `1995fe4`
  (conclusione di un'altra connessione nominata durante una scrittura).
- Esistono i test `tests/write_compiler/test_write_compiler.py` e
  `tests/write_compiler/test_write_cycle.py`.

Questa sessione non ha eseguito quei test nel worktree del writer e non ne
certifica il risultato. Non bisogna confondere la presenza di API/test con
l'avvenuta verifica dell'integrazione.

## Contratti da verificare nella riunificazione

1. **Modello unico.** `SqlTable.model` è DbTableObj: colonne fisiche in `columns`,
   virtuali in `virtual_columns`, attributi preservati. Ramo `relations` unico;
   le inverse del writer si ricavano dai joiner `mode == 'M'`. Nessun modello
   parallelo o ripristino del compilatore eliminato.
2. **Compilatori distinti, esecuzione comune.** Il DML resta nel compilatore del
   writer. Il contenitore eseguibile è `CompiledQuery`, ottenuto con
   `db.driver.prepare_sql(sql, kwargs, db.environment.snapshot())` e passato a
   `db.execute(compiled)`. `SqlCompiledQuery` raccoglie le clausole SELECT.
3. **Record e lock.** `record(..., for_update=True, ignoreMissing=True)` e output
   dict/record devono restare sulla connessione/transazione della scrittura.
   Record legge fisiche e X; le query con lock includono X in `*`, ma `*` include
   anche virtuali statiche. Per sole fisiche il writer costruisce la proiezione
   da `table.model.columns`.
4. **API e dati.** Verificare i terminali del writer che consumano query, i nomi
   delle opzioni effettivi e le chiavi composte. Non rinominare automaticamente
   tutte le firme durante il merge: prima censire gli eventuali conflitti.
5. **Ciclo completo.** Sui due dialetti verificare insert → record/query → update
   → rilettura → delete → rilettura, generazione pkey, attributi, relazioni,
   trigger/protezioni, rollback e commit. Ripetere i test di lock e delle
   connessioni nominate senza introdurre commit impliciti.
6. **Regressione unica.** Eseguire tutti i test senza il manifesto che esclude
   il writer. Attribuire i fallimenti: bug, vecchio test da riallineare o
   funzionalità fuori perimetro. Non eliminarli né saltarli solo per rendere
   verde la suite; non reintrodurre API eliminate per soddisfare vecchi test.

Il documento [97](97-read-write-contracts.md) resta il dettaglio dei contratti
originari. Il punto 8 del [99](99-writer-handoff-single-read-path.md), che parlava
di assenza degli handler many, è storico e superato dai passi 101–110.

## Prima versione operativa: criteri di chiusura proposti

Il perimetro finale va fissato dopo la prova integrata. Per un progetto nuovo,
la verifica dovrebbe coprire:

- Installazione da wheel in ambiente pulito, con dipendenze pubblicate e
  `asqueel-migration>=0.2.2,<0.3`, senza repository migration locale.
- Configurazione di un piccolo progetto da zero, costruzione del modello,
  JSON migration, applicazione dello schema e verifica della convergenza.
- Ciclo CRUD e letture sullo stesso database, con transazioni esplicite;
  relazioni, formule e aggregazioni comprese nel profilo dichiarato.
- PostgreSQL e SQLite con le rispettive capability documentate, compreso il
  limite XML di SQLite. Nessuna promessa di equivalenza oltre i contratti testati.
- Un esempio eseguibile del progetto e documentazione di configurazione,
  transazioni, letture, scritture, migrazioni e limiti che corrisponda alle API
  realmente verificate.
- Suite unificata, controlli statici, documentazione e installazione verificati.
  Versione, release notes e pubblicazione si decidono sulla base del risultato;
  non viene promesso ora un numero di versione né una compatibilità legacy totale.

## Backlog che non va trasformato automaticamente in requisito di release

Restano da valutare: matrice completa dei risultati delle formule native,
copertura dei join dichiarativi/custom, macro #ENV/full-text/vettoriali/BAG,
Selection e output estesi, composite come valore di proiezione, ulteriori
opzioni query/sottoquery. RuntimeModel e composizione dei mixin restano un
fronte distinto. Dettaglio nella [checklist 58](58-compiler-checklist.md).

I rinvii già decisi rimangono tali, incluso [ask](108-deferred-virtual-relation-ask.md).
Il progetto nuovo usa il perimetro verificato: non occorre completare tutti i
contratti legacy per dichiarare operativa una prima versione.

## Prompt di prosecuzione

> Obiettivo: riunificare letture e scritture di Asqueel e poi definire una prima
> versione operativa per un progetto nuovo, senza pretendere compatibilità
> completa con GenroPy. Leggi questo report 111 e i contratti 97.
>
> Le letture sono su `codex/core-single-read-path`; il codice completo è nel
> commit `d1c61490e4d637f7925df375fbed007ba619b2df`. Includi anche il successivo
> commit documentale di consegna. Il writer era su `plan/write-cycle`, HEAD
> `1995fe4e9b18656778a19ac7db65594adce770d2`, con merge aperto di `531d87b`:
> prima controlla lo stato attuale e preserva le risoluzioni staged. Non fare
> reset, abort o sovrascritture del suo lavoro. Se un'altra sessione lo sta
> modificando, concorda prima la consegna della sua base stabile.
>
> Esegui l'integrazione in un worktree dedicato. Mantieni modello gerarchico
> unico, DML separato dal compilatore delle letture, esecuzione comune con
> CompiledQuery e prepare_sql/execute. Conserva NamedList, record, lock e
> transazioni secondo i contratti verificati. Non reintrodurre compatibilità
> provvisorie, vecchi descrittori o comportamenti non concordati.
>
> Verifica PostgreSQL e SQLite con la suite completa senza esclusioni del
> writer e con un progetto di esempio da configurazione/migration a CRUD,
> query, formule e aggregazioni. Attribuisci ogni fallimento prima di cambiare
> codice o test. Poi documenta il perimetro della prima versione usabile,
> capability, limiti, dipendenze e istruzioni riproducibili. Le funzionalità
> legacy mancanti e i rinvii non diventano requisiti impliciti di questa release.
> Non pubblicare né fare push finché non richiesto.
