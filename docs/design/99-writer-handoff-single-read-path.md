# 99 — Messaggio per il writer: base e contratti di fusione

16 ottobre 2026. Testo da passare alla sessione scritture; preparato, non inviato.
La checklist aggiornata è [58](58-compiler-checklist.md); il dettaglio delle API
condivise è [97](97-read-write-contracts.md).

---

Il percorso unico delle letture è pronto come base per il raccordo.

**Branch:** `codex/core-single-read-path`.
**Commit:** `e96f0c14c27ab3366b7240de67c713b5712c4a50`
(`refactor: converge reads on the hierarchical model`).
**Worktree locale:** `/Users/gporcari/Sviluppo/asqueel/asqueel-read-path`.
Il commit è locale: non è stato eseguito push, merge o pubblicazione.
Le modifiche documentali successive non cambiano la base operativa indicata.

Integra questo commit nel tuo branch preservando il lavoro già svolto; non serve
ripartire da zero o ripristinare le API eliminate. La costruzione del modello e
le letture non hanno più il vecchio percorso parallelo.

## Contratti da verificare nella fusione

1. **Modello unico.** `table.model` è il DbTableObj dell'albero. I nomi operativi
   delle tabelle sono qualificati `package.table`. Usa `model.columns` per le
   fisiche, `model.virtual_columns` per le virtuali; i compositi sono separati.
   Le colonne espongono `sqlname`, `dtype`, `attributes`; la tabella `sqlschema`,
   `sqlname` e pkey logica. Verificare che il raccordo legga gli attributi conservati
   (`default`, `defaultFrom`, `sql_value`, onInserting…onDeleted, trigger_table)
   senza reintrodurre `.config` o descrittori paralleli. Qui se ne certifica la
   disponibilità nel modello, non l'esecuzione dei comportamenti DML.
2. **Relazioni.** Il ramo `relations` è l'autorità; ricava le inverse dal joiner
   con `mode == 'M'`, come concordato, senza un nuovo accessor `relations_many`.
   `onDelete`/`onUpdate` applicativi sono distinti da `onDelete_sql`/`onUpdate_sql`.
   La presenza dell'inversa nel modello non abilita la JOIN verso molti nelle letture.
3. **Preparazione ed esecuzione.** Usa
   `db.driver.prepare_sql(sql, kwargs, db.environment.snapshot())` per ottenere
   `CompiledQuery`, poi `db.execute(compiled)` sulla stessa istanza di database.
   SQL e kwargs restano separati. `SqlCompiledQuery` è il contenitore delle
   clausole SELECT; il writer non deve ricostruirlo per il DML.
   QueryPlan, Fragment, SqlStatement e il vecchio `driver.prepare` sono eliminati.
4. **Record.** Disponibile
   `table.record(pkey, for_update=True, ignoreMissing=True).output('dict' | 'record')`.
   Record legge le colonne fisiche, con X per default e senza virtuali statiche;
   non applica per default i filtri query di draft/cancellazione logica/partition.
   Missing con ignoreMissing restituisce dict/Bag vuota; senza flag solleva errore.
   Più righe sono errore. Il risultato è lazy e memorizzato; `refresh()` rilegge.
   L'output dict è una copia; output record è una Bag, X convertite in Bag,
   senza resolver di relazione o pyColumn.
5. **Query con lock e proiezione.** È mantenuta la regola legacy
   `bagFields or for_update`: `*` include X anche con bagFields=False.
   Tuttavia `*` include anche virtuali statiche. Per avere esattamente tutte le
   colonne fisiche costruisci la proiezione da `table.model.columns`.
   Una proiezione esplicita non viene allargata. Usare le firme attuali
   `exclude_draft=False`, `exclude_logical_deleted=False`, `ignore_partition=True`
   quando servono quei bypass; nessuna rinomina camelCase anticipata.
6. **Connessione e transazione.** La lettura con lock usa lo stesso database,
   connessione e transazione del chiamante. PostgreSQL usa FOR UPDATE OF t0.
   SQLite usa BEGIN IMMEDIATE senza transazione aperta; se già aperta, un UPDATE
   senza righe acquisisce il lock senza modificare dati o fare commit.
   Il raccordo è nel driver/runtime di esecuzione: non duplicarlo nel DML.
   Ripetere sul branch fuso contesa con seconda connessione, rilascio al rollback
   e assenza di commit impliciti, oltre ai test degli utilizzatori del record.
7. **Risultati.** fetch restituisce righe NamedList di Toolbox, modificabili e
   accessibili per nome e posizione su entrambi i dialetti. Non introdurre un
   contenitore diverso. Ogni fetch esegue nuovamente, diversamente dalla cache
   esplicita di SqlRecord.
8. **Perimetro.** Nessun nuovo sistema di mixin/RuntimeModel; nessun handler
   many_* implementato. Il compilatore delle letture non ospita DML.
   `writes.py`, `triggers.py` e `runtime.py` sono rimasti invariati rispetto alla
   base della sessione letture. Il vecchio DML nel compilatore è stato rimosso
   secondo l'accordo con la tua sessione.

## Verifiche disponibili e da ripetere

Sul commit: **4.253 passati, 12 skip, 16 deselected**, PostgreSQL e SQLite;
Ruff, mypy, build documentazione e wheel isolata verificati. Struttura e JSON
migration confrontati per tutti i 74 modelli; migration 0.2.2 installata da PyPI.
Non è una certificazione dei risultati di ogni formula del corpus nativo.

Comando delle sole letture:

```sh
PYTHONPATH=src python -m pytest @tests/read_path/pytest.args --no-cov -q --tb=short
```

Il manifest esclude 27 file dipendenti dalle scritture e 16 casi nei file misti.
Il dettaglio è in
[evidence/single-read-path/writer-tests.json](evidence/single-read-path/writer-tests.json).
I test DML sono conservati per il tuo raccordo, non coperti da shim o skip globali.

**Dopo la fusione:** verificare i contratti sopra su entrambi i dialetti,
eseguire l'intera suite senza queste esclusioni e controllare la CI.
Le lacune/rinvii delle letture sono censiti nel documento 58; non vanno
compensati reintroducendo il compilatore o il modello eliminati.
