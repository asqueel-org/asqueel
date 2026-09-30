# 18 — Ripresa del lavoro interrotto sui trigger e sul commit

Verifica del 30 settembre 2026. HEAD resta `2bed211`; modifiche non committate.
Chat esaminata: «Verifica se tutto è pushato», turno interrotto dopo modifiche a
application, application_table, session, exports e nuovo modulo triggers.
La chat aveva ricevuto richiesta di procedere verificando il legacy.

## Stato recuperato

- Il lavoro precedente su documentazione, audit legacy e sessioni F1 è presente.
- La nuova parte introduce currentTrigger, parent/level e code prima/dopo commit.
  È una bozza interrotta: non era accompagnata da nuovi test o oracle.
- Gli asset in docs/brand provengono dalla distinta chat di naming; non fanno
  parte della modifica al lifecycle e non sono stati modificati da questa revisione.
- Non sono stati eseguiti commit, push o rimozioni durante la ripresa.

## Difetti riprodotti

Le [prove diagnostiche](evidence/takeover_deferred_probes.py) usano il driver in
memoria dei test, senza connessioni esterne. Eseguire dalla radice con
`PYTHONPATH=. python docs/design/evidence/takeover_deferred_probes.py`.
Non sostituiscono test di accettazione con assert e confronto legacy.

| Problema | Evidenza | Conseguenza |
|---|---|---|
| Registrazione deferred negli hook bloccata | `_check_boundary()` rifiuta la registrazione durante `_write_operation()` | Il caso d'uso principale di deferToCommit non funziona. |
| Eccezione pre-commit nel context manager | Uscita con `_pending=True`, nessuna chiamata rollback | Il blocco transazionale fallito lascia aperto il lavoro pendente. |
| Errore SQL catturato nella callback pre-commit | Una callback after viene eseguita, zero commit fisici, outcome rolled_back | Il chiamante può ricevere un effetto post-commit senza alcun commit riuscito. |
| Contesto della callback | `onCommittingStep` risulta None | Divergenza dal contesto applicativo impostato dal legacy. |

Questo è il rilievo storico prima delle correzioni. I quattro difetti sono stati
risolti e verificati nella [consegna 19](19-deferred-lifecycle-fixes.md).

## Confronto con il legacy

Sorgenti consultati in Genropy, commit `fa35e5adfa6ad1b269f3a22a9b12c4c1ee6513ea`:
`gnrpy/gnr/sql/gnrsql/transactions.py` e `gnrpy/gnr/sql/gnrsql/helpers.py`.

- Le callback sono raggruppate per connectionKey; blocchi ordinati, ordine di
  inserimento nel blocco, deduplicazione per identità callable e deferredId.
- Il legacy tratta un deferredId falso come assente; la bozza tratta così solo None.
  La differenza richiede un caso esplicito, non una modifica tacita al contratto.
- deferredCommitRecursion controlla la ri-registrazione della stessa callback.
- commit attiva onCommittingStep per entrambe le code e chiama onDbCommitted.
- Lo stack descrive la catena causale delle scritture; le code descrivono una
  transazione. Non dedurre dal loro collegamento che abbiano identico ambito.
- La pulizia dello stack in finally della bozza migliora il percorso di errore;
  va verificata e registrata, senza attribuirla al comportamento storico.

## Verifiche effettuate

- 51 test esistenti di sessione e table: superati. Non coprono le nuove code.
- Ruff sui quattro moduli interessati: superato.
- Mypy su src/asqueel: superato, 32 file (note preesistenti sui corpi non annotati).
- Quattro prove mirate: riproducono i problemi sopra.
- Nessuna nuova dichiarazione di equivalenza legacy o di accettazione PostgreSQL.

## Priorità di completamento

Chiudere F1 prima di F2: registrazione dagli hook, parent/level e ripristino,
ordine/deduplicazione/ricorsione, isolamento dei nomi, callback che generano SQL,
errori catturati e propagati, rollback e commit incerto. I callback after non
possono trasformare un rollback in un successo o annunciare un commit inesistente.
Confrontare i contratti con oracle legacy prima di accettare differenze.
Restano anche la localizzazione completa e il comportamento degli errori Python.
La successiva F4 integra record ed eventi con questo nucleo già verificato.
