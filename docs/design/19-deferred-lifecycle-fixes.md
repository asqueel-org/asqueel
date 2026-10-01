# 19 — Correzione del lifecycle deferred e dei trigger

## Perimetro

Risolti i quattro difetti della [ripresa 18](18-interrupted-lifecycle-review.md).
Le registrazioni sono consentite dagli hook; la conclusione di una transazione
resta vietata dentro gli hook e durante una callback della stessa sessione.
Il context manager annulla il lavoro pendente anche se fallisce il pre-commit.
Un errore SQL catturato dalla callback invalida comunque il dispatch: nessuna
callback successiva può annunciare un commit inesistente. Le callback ricevono
onCommittingStep e il nome della sessione che possiede la transazione, con
ripristino dell'environment all'uscita.

Una callback after può generare una nuova transazione, completata dal loop
legacy. Un suo errore non annulla un commit già riuscito. La pulizia riguarda
soltanto il nuovo lavoro e le code residue. Commit incerto scarta la connessione
e non esegue callback after. Errori di cleanup non nascondono l'errore originale.

Lo stack conserva parent, record, old_record e livello zero-based; è ripristinato
anche dopo errori. Descrive la catena causale del DB sincrono, mentre le code sono
isolate per nome di connessione. Non si introducono store, async o eventi web.

## Evidenza legacy

[Oracle eseguibile](evidence/deferred_queue_oracle.py) e
[risultati con hash dei sorgenti](evidence/deferred_queue_oracle.json).
Sono eseguiti i metodi originali AST di TransactionMixin e la vera Bag legacy:
ordine blocchi/inserimento, deduplicazione, kwargs condivisi, ID falsi, conversione
ID a stringa e ricorsione coincidono. Il confronto copre le code, non l'intero
framework o il commit fisico del legacy. Non è un test simulato della Bag.

Il native continua a usare rollback-only per gli errori Python. La compatibilità
completa di questo comportamento resta aperta; queste correzioni non la dichiarano
risolta. Il recupero dello stack via finally e i controlli di rientranza proteggono
il runtime da stato corrotto, senza affermare che il legacy avesse tali garanzie.

## Verifica

I nuovi test sono in tests/application_connections/test_deferred.py e nei test
PostgreSQL dei write hooks. Nove casi sono falliti sulla bozza e passati dopo le
correzioni. I controlli includono osservazione da una connessione indipendente,
rollback delle scritture secondarie, connessioni nominate, errore post-commit,
commit incerto e preservazione dell'eccezione originale durante cleanup fallito.

F1 resta aperta per localizzazione completa e riesame generale degli errori
Python. L'integrazione degli eventi applicativi è distinta dal dispatch deferred.

Verifica finale: **553 test superati**, compresi PostgreSQL ed esempi della
documentazione; Ruff superato, Mypy superato su 32 file, Sphinx con warning
trattati come errori superato. Nessun commit o push in questa consegna.
