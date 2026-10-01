# Handoff — completamento query Asqueel

## Richiesta e prossimo passo

L'utente ha chiesto un piano per verificare i problemi concreti e aumentare la
copertura funzionale legacy, privilegiando la completezza della sintassi rispetto
alla sola correzione della documentazione. Il piano è pronto; l'ultima richiesta
è preparare questo handoff. L'implementazione del piano non è iniziata.

Alla ripresa, leggere il piano 30 e partire dal passo 1: diagnosi e contratti
legacy eseguibili, prima di implementare IN/NOT IN, DISTINCT, GROUP BY/HAVING e
count. Non ripartire da una riscrittura della documentazione, da ottimizzazioni o
da un refactoring generale. Non chiedere nuovamente scelte già stabilite sotto.

## Repository e consegna

- Repository: `/Users/gporcari/Sviluppo/asqueel/asqueel`, ramo `main`.
- HEAD e origin/main verificati: `90984fb`.
- Versione sorgente: **0.4.0**, senza tag/pubblicazione di questa versione.
- Ultima suite completa: **683 test passati**, PostgreSQL e SQLite, copertura 95%.
  Ruff, mypy (39 file), Sphinx con warning come errori e demo nelle due modalità
  passati. Queste verifiche precedono le sole modifiche di pianificazione.
- Modifiche locali non committate: `docs/design/15-operational-plan.md`,
  `docs/design/README.md`; nuovo `docs/design/30-query-completion-plan.md` e questo
  handoff. Preservarle. Il piano non è ancora su origin/main.
- Nessun workflow `.phased` attivo: il riferimento è il piano operativo nei docs.
- Nessun nuovo task o trasferimento di checkout è stato creato con questo handoff.

## Documenti da leggere

1. `docs/design/30-query-completion-plan.md`: piano dettagliato in sei passi,
   contratti, ambito e criteri di chiusura.
2. `docs/design/05-decisions.md`: scelte accettate, comprese scritture raw.
3. `docs/design/15-operational-plan.md`: F0–F10; questo lavoro è un incremento F3
   con prerequisiti F2 mirati, non la chiusura integrale di F2/F3.
4. `docs/design/26-async-portability.md`: vincoli per una futura implementazione async.
5. `docs/design/29-review-corrections.md`: difetti corretti e residui della review.
6. `temp/analisi_2026-10-01.md`: analisi esterna, riferita al precedente `ccfbc64`.
   Le misure prestazionali non sono state riprodotte in questa conversazione.
   Le azioni suggerite sono proposte da verificare, non decisioni dell'utente.

## Stato funzionale e decisioni vincolanti

- Unico percorso execute, nessun commit implicito. Non introdurre Session,
  transaction() o nuovi context manager transazionali.
- DB/modello condivisibili; currentEnv e connessioni nominate isolati per thread.
  tempEnv modifica solo il contesto. Cleanup della richiesta posseduto dall'app.
- Eccezioni callback non gestite arrivano all'app e interrompono la sequenza.
  Un postcommit fallito non annulla il commit; niente continuazione automatica
  delle callback né eliminazione forzata delle residue per il solo errore Python.
- Errore SQL: rollback automatico del lavoro pendente. Errore Python nel ciclo
  di scrittura: rollback obbligatorio prima del riuso. Esito commit incerto:
  niente retry automatico.
- Niente Babel obbligatorio o validazione locale; locale/workdate sono contesto.
- insert accetta un record; update/delete richiedono sempre esattamente un record
  e una pkey, indipendentemente dalla presenza di hook. Zero/multipli sollevano
  RecordNotFoundError/RecordMultipleRowsError prima degli hook.
- raw_update/raw_delete ammettono filtri multi-riga. raw_insert accetta un
  dizionario o lista di dizionari. Nessun metodo Many aggiuntivo.
- Raw salta i trigger Python di tabella, mantiene hook DB, policy e vincoli SQL.
  Hook DB per ogni raw insert; una volta per raw update/delete, senza snapshot
  old_record. Delete con where esplicito fornisce record=None; per chiave fornisce
  una mappa chiave. Raw update fornisce solo valori da aggiornare.
- La lista raw_insert usa INSERT in sequenza attraverso execute, nella stessa
  transazione; aggrega risultati/rowcount, nessun commit intermedio. Non è una
  implementazione executemany/COPY. Lista vuota: nessun SQL o hook.
- SQLite è un backend effettivo nel profilo documentato, non parità completa.
  BEGIN IMMEDIATE e limiti FK della migrazione non vanno cambiati di nascosto.
- Non convertire a ContextVar solo per dichiarare pronto async: dizionari mutabili,
  ownership, hook, I/O e cancellazione richiedono contratti specifici.

## Correzioni già consegnate

- `e812bad`: eliminazione strutturale di Session; lifecycle sul Database, registro
  di connessioni come dati. Test in `tests/application_connections`.
- `960b638`: versione 0.4.0.
- `ccfbc64`: FK composite conservate nella proiezione tramite nome effettivo della
  relazione; ereditarietà backend connection → db; demo e prime correzioni docs.
- `90984fb`: separazione scritture per record/raw descritta sopra, con test reali.

## Punti di ingresso per il nuovo lavoro

- `src/asqueel/application_table.py`: SqlQuery.compiled ricompila al terminale;
  count attualmente solleva UnsupportedFeatureError.
- `src/asqueel/compiler.py`: plan_select/select, _Context.expression/projection,
  policy e binding. Raggruppamento/distinct non sono ancora opzioni supportate.
- `src/asqueel/query_plan.py`: rappresentazione strutturata del piano.
- `src/asqueel/dialects/postgres.py`, `sqlite.py`: rendering e lessico.
- `src/asqueel/drivers/sql.py`: parametri delle query SQL dirette.
- Non aggiungere una seconda implementazione SQL scollegata dal piano.

Legacy disponibile in sola lettura:
`/Users/gporcari/Sviluppo/Genropy/genropy`, revision di riferimento
`fa35e5adfa6ad1b269f3a22a9b12c4c1ee6513ea` (ricontrollare prima degli oracle).
File: `gnrpy/gnr/sql/gnrsqldata/query.py` (count, compileQuery),
`gnrpy/gnr/sql/gnrsqldata/compiler.py` (compiledQuery), `gnrpy/gnr/sql/adapters/`.
Il count legacy può contare gruppi in Python dopo fetch: confrontare il risultato
osservabile, ma il nuovo terminale deve contare nel DB senza scaricare i gruppi.
Limit/offset, NULL, liste vuote e forme speciali vanno verificati, non presunti.

## Verifiche e ambiente disponibili

Percorsi temporanei da verificare alla ripresa, non dipendenze permanenti:

- Python/test/Ruff/mypy: `/tmp/asqueel-release-smoke/bin/`.
- Sphinx: `/tmp/genro-sql-docs-venv/bin/python`.
- `/tmp/asqueel-review-check.sh`: PostgreSQL 17 temporaneo, porta 55584,
  suite completa e demo; arresta il server alla fine. Leggerlo prima dell'uso.
- `/tmp/asqueel-final-push.sh`: PostgreSQL temporaneo e git push origin main;
  esegue il pre-push completo. Non usarlo come semplice comando di test.
- Import sorgenti: `PYTHONPATH=src`. La venv del repository non è la venv verificata.
- Documentazione: Sphinx `-W --keep-going`, output fuori dal repository.
  Un primo download dell'inventario Python può richiedere accesso rete.
- Server PostgreSQL e mutazioni Git possono richiedere escalation del sandbox.

Non usare i conteggi storici come esito di nuove modifiche: ripetere i controlli
appropriati. Non pubblicare tag o pacchetti come effetto implicito della fase.

## Stile e metodo

Rispondere in italiano conciso. Distinguere fatto, verificato, progettato e aperto.
L'utente pretende che “chiuso” significhi completo rispetto al contratto dichiarato.
Niente strumenti inventati, approvazioni ripetute o nuove astrazioni senza bisogno.
Non avviare subagent salvo autorizzazione esplicita. Non confondere una build docs
riuscita con verifica della verità delle guide. Conservare evidenze dei contratti
legacy, decisioni e rischi async durante l'implementazione.
