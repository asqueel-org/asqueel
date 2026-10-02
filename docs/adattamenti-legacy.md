# Adattamenti legacy

Questo documento raccoglie i comportamenti SQL di Genropy legacy da considerare
nell'integrazione con Asqueel: quelli già disponibili, quelli non portati e i
punti di estensione ancora necessari. Non descrive un adapter legacy già
implementato e non promette compatibilità completa.

Il livello di integrazione Genropy è distinto dall'adapter del backend SQL:
composizione dei package, regole applicative e notifiche non devono finire nel
driver PostgreSQL o SQLite.

## Riferimenti e stato

Confronto effettuato il 30 settembre 2026 sul legacy alla revisione
`fa35e5adfa6ad1b269f3a22a9b12c4c1ee6513ea` e sul codice Asqueel ora
pubblicato nella versione `0.3.0` (`5c9c09f`). I comportamenti indicati come
non portati o da verificare restano aperti anche dopo questa release.

Fonti legacy, relative alla radice del repository Genropy:

- `gnrpy/gnr/sql/gnrsqltable/crud.py`: comandi di tabella, trigger dei campi e dei package.
- `gnrpy/gnr/sql/gnrsql/write.py`: orchestrazione delle scritture e `_onDbChange`.
- `gnrpy/gnr/sql/adapters/_gnrbaseadapter.py`: costruzione SQL e invocazione dell'esecutore.
- `gnrpy/gnr/sql/gnrsql/execute.py`, `connections.py`, `env.py`, `helpers.py`:
  esecuzione, connessioni e ambiente temporaneo.
- `gnrpy/gnr/sql/gnrsql/transactions.py`: commit, rollback e callback differite.

Fonti Asqueel: `src/asqueel/application.py`, `application_table.py`,
`environment.py`, `compiler.py` e `runtime.py` (che possiede direttamente
il lifecycle delle connessioni, senza un’entità Session).

## Percorso delle operazioni

Nel legacy una scrittura ordinaria segue questo percorso:

```text
table.insert(record)
  → db.insert(table, record)
      → controlli e hook precedenti
      → adapter.insert(table, record)
          → preparazione SQL e parametri
          → db.execute(...)
      → _onDbChange
      → hook successivi
```

`update` e `delete` seguono la stessa divisione delle responsabilità, con una
sequenza propria. I metodi `raw_insert`, `raw_update` e `raw_delete` saltano il
ciclo ordinario dei controlli e dei trigger, ma chiamano ancora `_onDbChange`
con `_raw=True`. Raw non significa quindi assenza di effetti applicativi.

Nell'adapter base legacy `insertMany` costituisce un'eccezione: usa direttamente
`cursor.executemany()`, senza attraversare `db.execute()`.

In Asqueel i metodi di tabella ora delegano a `db.insert/update/delete` e alle
varianti `db.raw_insert/raw_update/raw_delete`. Il DB orchestra gli hook,
il compiler prepara la query e `db.execute()` è il passaggio comune al driver.
Anche `Database` e `PostgresDatabase` usano lo stesso esecutore e completamento
esplicito; il precedente runtime con transazioni automatiche è stato rimosso.

I punti comuni sono `onWriting`, `onExecutingWrite`, `_onDbChange` e `onWritten`:
prima dei trigger, prima di SQL, dopo SQL e dopo i trigger successivi.
Ricevono tabella, evento I/U/D, record, eventuale `old_record` e flag raw.
I raw saltano i sei trigger di tabella ma mantengono questi punti, la pila delle
scritture, le policy native e i controlli sugli errori. Non sono ancora
un'emulazione completa del raw Genropy.

Nel contratto corrente Asqueel `update` e `delete` richiedono sempre un record,
anche senza override dei trigger. `raw_update` e `raw_delete` accettano filtri
multi-riga senza caricare ogni record; gli hook DB ricevono i valori forniti
all'update o la chiave/record forniti al delete, non snapshot completi.
Per delete con filtro esplicito ricevono `record=None`; `old_record` è assente.
Gli hook DB sono chiamati una volta per comando raw update/delete, non per riga.

`raw_insert` accetta un dizionario o una lista di dizionari. La lista esegue
INSERT attraverso execute nella stessa transazione, mantenendo gli hook DB per
ciascun record e saltando i trigger di tabella. Non usa il percorso cursor diretto
del vecchio insertMany, non committa fra record e non espone un metodo Many separato.

## Ciclo di scrittura e comportamenti da adattare

| Comportamento legacy | Stato in Asqueel | Adattamento necessario |
|---|---|---|
| `checkPkey`, `protect_validate`, `protect_update`, `protect_delete` e controllo `deletable` | Esistono controlli nativi di compilazione e scrittura, ma non questo protocollo di metodi. | Mappare le protezioni legacy senza confonderle con i vincoli SQL; verificare ordine e accesso a `old_record`. |
| Trigger di tabella `onInserting/onInserted`, `onUpdating/onUpdated`, `onDeleting/onDeleted` | Disponibili come `trigger_on*` su `SqlTable`. | Collegare la logica della tabella e verificare firme, mutazioni, ritorni ed errori. |
| `_doFieldTriggers` | Nessun dispatcher equivalente. | Tradurre le dichiarazioni dei campi e preservare ordine e argomenti dei callback. |
| `_doExternalPkgTriggers` e `avoid_trigger_<package>` | Nessun dispatcher dei package equivalente. | Introdurre composizione e selezione nel livello Genropy; non assumere che basti importare i moduli. |
| `dbo_onInserting`, `dbo_onUpdating`, `dbo_onDeleting` | Non invocati dal ciclo nativo. | Prevedere il richiamo nella posizione corretta, se richiesto dall'integrazione. |
| `trigger_assignCounters`, `trigger_releaseCounters` | Protocollo non portato. | Definire assegnazione, rilascio e comportamento su rollback; una sequence SQL non è automaticamente equivalente. |
| `protect_draft` durante l'inserimento | Non portato. | Distinguere questa regola dalle policy native di visibilità delle bozze. |
| `updateRelated`, `deleteRelated` | Nessun ciclo Python equivalente. | Separare le azioni SQL delle FK dalle operazioni applicative sui collegati e dai loro trigger. |
| `_onDbChange`, totalizzatori, `onLogChange`, change log e notifiche | Punto `_onDbChange` disponibile anche per raw; servizi applicativi non portati. | Collegare totalizzatori, log e notifiche al punto comune; decidere quali effetti differire al commit. |
| `raw_insert/raw_update/raw_delete` | API presenti su tabella e DB; non equivalenti a tutto il contratto legacy. | Adattare le differenze di firma e ritorno; i raw saltano i trigger di tabella, mantenendo hook DB, policy ed errori. |
| `currentTrigger`, parent e livello della chiamata | Pila presente e isolata per thread. | Verificare le informazioni richieste dai chiamanti legacy e dalle scritture annidate. |
| `deferToCommit`, `deferAfterCommit`, `deferredRaise` | Disponibili per connessione nominata. | Contratti verificati nel profilo F1; eccezioni propagate, nessun retry automatico. Cleanup delle richieste e adattamenti dei chiamanti nel rapporto 27. |
| `onDbCommitted` e notifiche applicative del commit | Nessun hook equivalente completo. | Collegare l'integrazione applicativa al completamento, distinguendo errore prima e dopo il commit effettivo. |

### L'ordine è parte del contratto

Per l'insert legacy: chiave e validazione → trigger di campo → trigger di tabella
→ trigger dei package → contatori → `dbo_onInserting` → protezione bozza → SQL
→ `_onDbChange` → trigger successivi di campo, tabella e package.

Per l'update: protezioni → trigger precedenti di campo, tabella e package →
`dbo_onUpdating` → contatori → SQL → `updateRelated` → `_onDbChange` → trigger
successivi di campo, tabella e package.

Per il delete: controllo di cancellabilità e protezione → trigger precedenti
di campo, tabella e package → `deleteRelated` → `dbo_onDeleting` → SQL →
`_onDbChange` → trigger successivi di campo, tabella e package → rilascio contatori.

Comporre tutto dentro uno dei sei hook nativi non garantisce automaticamente
questo ordine. Se serve un punto intermedio oggi assente, va registrato come
requisito del nucleo; non va dichiarato già risolto dall'integrazione legacy.

## Record, risultati e selezioni

Nel legacy `table.insert(record)` restituisce il record passato, che il ciclo
può modificare. Asqueel copia i valori in ingresso e restituisce `QueryResult`;
i valori SQL restituiti vengono riportati sul record interno prima dell'hook
successivo. L'integrazione deve decidere esplicitamente come adattare il risultato
e le mutazioni osservabili dal chiamante.

Con hook di update/delete personalizzati, Asqueel legge e blocca un singolo
record; per l'update costruisce il record completo e passa una copia di
`old_record` agli hook. Senza quegli hook può eseguire una scrittura su più righe.
Non equiparare quindi un update con predicato a un ciclo legacy sui record.

## Ambiente e connessioni

Il modello d'uso da mantenere è `tempEnv` come modificatore generico:

```python
with db.tempEnv(connectionName="system", user="scheduler"):
    db.table("adm.log").insert(record)
    db.commit()
```

Il frammento presuppone una tabella applicativa `adm.log` e un record valido;
non è una ricetta autonoma. I comandi restano gli stessi e selezionano la
connessione attraverso l'ambiente. `tempEnv` non conclude la transazione;
il ripristino segue la semantica legacy descritta nella [guida ambiente](guide/environment.md).

Il legacy mantiene connessioni per thread e per coppia `(storename,
connectionName)`. Asqueel ora isola ambiente e connessioni nominate per thread,
ma non implementa il cambio di store. Un nome di connessione separa il lavoro
transazionale; non è il nome di un database differente.

Il contesto pubblico `with db.connection:` e l'API `transaction()` sono stati
rimossi. Si seleziona il contesto con `tempEnv` e si completa con `commit/rollback`.
Il nome `connection` resta nella grammatica di configurazione, non come contesto
transazionale del DB runtime.

SQLite percorre lo stesso ciclo delle scritture e degli hook. La riserva di
scrittura riguarda i file collegati, non le singole righe; i servizi legacy
non devono assumere identica concorrenza fra PostgreSQL e SQLite.

## Espansione delle colonne nella SELECT

Decisioni del 1 ottobre 2026 per il [piano 32](https://github.com/asqueel-org/asqueel/blob/main/docs/design/32-expression-resolver-plan.md).
Descrivono il contratto da implementare, non il comportamento attuale di
Asqueel: oggi `*` comprende anche formule e alias (`compiler.py:568-571`).
Fonte legacy: `gnrsqldata/compiler.py` `expandMultipleColumns` e
`gnrsqlmodel/table.py` `starColumns` su `origin/develop` (`51e4270c54`).

| Forma | Legacy | Asqueel | Motivo |
|---|---|---|---|
| `*` | Colonne fisiche in ordine di dichiarazione, escluse le `dtype='X'` se `bagFields` è falso; poi le virtuali con `static=True`. `bagFields` è falso nelle query, vero nei record. | Identico. | — |
| `*prefix_` sulla tabella principale | Il prefisso viene ignorato: stesso risultato di `*`. Dal 2009 al 2020 filtrava per prefisso; il commit `87e8c97018` (2020-10-19) ha perso il filtro. | Non supportato: errore esplicito. | Forma superflua: nessun caso d'uso la giustifica. Dal 2020 ogni `*prefix_` restituisce `*`, quindi sostituirla con `*` non cambia il risultato dei chiamanti esistenti. Proposta di rimozione nel legacy: [genropy/genropy#1504](https://github.com/genropy/genropy/issues/1504). |
| `*nome`, con `nome` colonna virtuale | La `sql_formula` di `nome` viene espansa al posto di `nome`; se inizia con `@` ricade in `*@rel.(a,b)` con `nome` come etichetta. Con una formula che non inizia con `@` restituisce `*`. | Non supportato: errore esplicito. | Serve solo al meccanismo `*@rel.(a,b)` (riga seguente). |
| `*@rel.(a,b,...)` | Seleziona `@rel.a`, `@rel.b` con join che moltiplica le righe; `aggregateDict` e `_aggregateRows` le riuniscono per pkey in un dizionario per la cella `_subtable` della griglia (commit `6e009b97d9`, 2012). | Non supportato: errore esplicito. | GEP 1 §3 (nessun uso trovato, nessun test) e §9.6 (rimozione). Sostituto: `@rel.to_json($a, $b)` del GEP 1, compilato come subquery correlata, senza moltiplicare le righe. |
| `*@rel`, `*@rel1.@rel2` | `@rel.col` per ogni colonna fisica della tabella raggiunta, comprese le `dtype='X'`, senza virtuali; su una relazione lato molti moltiplica le righe. Presente dal primo import (`731268058f`, 2009). | Non supportato: errore esplicito. | [genropy/genropy#623](https://github.com/genropy/genropy/issues/623): nessun uso nei progetti indicizzati, solo nei test del framework (`h_query_surface_test.py:275`, `test_compiler_factory.py`); proposta di deprecazione. |
| `*@rel.prefix_` | Le colonne di `*@rel` il cui nome inizia con `prefix_`. Presente dal primo import (`731268058f`, 2009). | Non supportato: errore esplicito. | [genropy/genropy#623](https://github.com/genropy/genropy/issues/623): nessun uso nei progetti indicizzati; nessun uso trovato neppure nei test del framework. |

Nomi automatici: un path senza `AS` prende il nome di `colToAs` (ogni carattere
non alfanumerico diventa `_`, `_` iniziale davanti a una cifra), identico al
legacy: `@customer_id.name` → `_customer_id_name`. Motivo: client e server del
framework ricalcolano il nome con la stessa regola (`genro_grid.js:1370`,
`:1861`, `genro_dlg.js:1047`, `apphandler/export.py:283`, `batch/btcexport.py:71`).
Asqueel oggi produce `customer_name` (R33): va allineato.

Restano da decidere la modalità count e la colonna `pkey` aggiunta.

## Criterio per i prossimi adattamenti

Per ogni comportamento portato, registrare il punto d'ingresso, l'ordine,
i dati disponibili, gli effetti nei percorsi normale/raw e le conseguenze di
un errore. Verificare anche hook annidati, connessioni nominate e rollback.

Il livello Genropy può introdurre comportamenti mancanti solo dove il nucleo
rende disponibile il punto di estensione necessario. La mappa non costituisce
una promessa di portare indistintamente ogni funzionalità legacy.

Per il lavoro sui package vedere anche
[Traduzione dei package legacy](https://github.com/asqueel-org/asqueel/blob/main/docs/design/22-legacy-package-translation.md).

## Request lifecycle and caller recovery — local F1 completion

The application instance that owns a request initializes `currentEnv` once on
first `db` access, then closes all of its worker’s named connections and clears
context at request completion, including errors. Use `closeConnection()` for a
DB shared across consecutive requests; clearing environment alone is insufficient.

The F1 closure report (`docs/design/27-f1-request-lifecycle-closure.md`) records tested
adaptation duties for the logger, older mail importer, batch success/error logs,
SMTP queue removal, extension DDL and directory visitors. A caught database
write failure requires rollback or request termination before further writes.
Successful external effects, such as sending mail, require application
reconciliation; SQL rollback cannot undo them. No service implementation or
multi-store compatibility is claimed by those bounded tests.

Unlike the published 0.3.0 handler, the local after-commit handler propagates a
Python exception without automatically clearing unreached callbacks. The
application’s rollback/close clears them; deliberate subsequent work in the
same context can reach them. SQL failures retain automatic rollback semantics.
