# 23 — CLI, registro locale e console Python

Consegna locale del 30 settembre 2026. Implementa il percorso SQL discusso con
l'utente; non introduce la sottoapplicazione Genropy né chiude F1.

**Current status:** this report records the original PostgreSQL delivery, now
released in 0.2.0. Release 0.3.0 also provides SQLite runtime and CLI migration
support through the existing SQLite migration adapter. Its constraints are
documented in the [SQLite guide](../guide/sqlite.md). The PostgreSQL-only limits
and 584-test count below are historical; the current baseline is 618 passing
tests. See the [operational plan](15-operational-plan.md) for remaining work.

## Contratto consegnato

- Una cartella con `configure.py` può essere registrata tramite un nome simbolico.
  Il registro usa `~/.asqueel/databases/<nome>.json`, rilocabile con
  `ASQUEEL_HOME`, sul modello delle schede locali di Kajenn. Salva soltanto il
  percorso assoluto; sorgenti e credenziali rimangono nel loro contesto.
- `AsqueelDb("gestionale")` risolve la scheda e carica la ricetta tramite
  `ConfigHandler`. Restano disponibili classi, istanze e file; si aggiungono
  cartelle e riferimenti standard `module:Class`. Le ricette su file usano
  import assoluti; la radice del package Python contenente la ricetta viene
  resa importabile durante il caricamento, senza discovery di schemi/tabelle.
- La grammatica del DB contiene una sola sezione `connection`. `name` è il nome
  del database fisico; non è il nome di una connessione. Host, porta, utente e
  password sono attributi diretti, risolti dal normale `ConfigHandler` con
  `EnvResolver`, non resolver annidati in dizionari. I parametri precedenti
  `conninfo/connect_kwargs` restano compatibili, ma non si mescolano con la
  nuova sezione. La sintassi Builders effettiva è `db = root.db()` seguito da
  `db.connection(...)`.
- La singola configurazione alimenta anche le sessioni runtime nominate già
  implementate: non si elimina il loro isolamento transazionale.
- CLI standard `argparse`, entry point `asqueel` e `python -m asqueel`:
  `register`, `list`, `unregister`, `check`, `db plan`, `db apply`, `shell`.
- `shell` usa la console Python standard con `db` disponibile. Commit esplicito;
  uscita normale o `SystemExit` chiude il DB e annulla le scritture pendenti.
  Non viene configurato un file persistente di cronologia.
- `db plan/apply` proietta il modello fisico e usa `PgDatabase/SqlMigrator`
  esistenti. Il nome fisico viene dalle impostazioni di connessione, non dal
  nome simbolico o dall'etichetta della radice della ricetta. Dopo apply viene
  eseguito un confronto nuovo. Nessun codice DDL duplicato nella CLI.

## Punto di ingresso Python

`AsqueelDb` è la classe pubblica configurata, derivata da `SqlDatabase`.
L'uso ordinario è `db = AsqueelDb("gestionale")`, seguito da operazioni su
`db.table(...)`, commit/rollback espliciti e `db.close()`. Le tabelle e la loro
logica appartengono a questa stessa istanza, senza proxy o copia di un altro DB.
`build_database(...)` resta una factory compatibile che restituisce `AsqueelDb`.
CLI, guida ed esempi usano il nome pubblico e l'accesso diretto.

## Limiti espliciti

Il runtime della CLI è attualmente PostgreSQL. SQLite è richiesto e pianificato;
le migrazioni dei quattro backend sono già presenti nel migratore e non sono
reimplementate da questa consegna. La gestione strutturale riguarda gli schemi
fisici rappresentati dalle tabelle proiettate; un modello senza tabelle gestite
non avvia migrazioni.

`--allow-removals` abilita le rimozioni supportate dal migratore: attualmente
colonne. Gli handler di rimozione di tabelle, indici, relazioni e vincoli sono
no-op. Un risultato senza comandi non certifica uguaglianza su oggetti ignorati.
Gli schemi estranei non sono gestiti. Le modifiche diverse dalle rimozioni
possono comunque incidere sui dati; `plan` mostra SQL senza applicarlo.

Gli errori arbitrari di configurazione/driver non vengono stampati integralmente
per evitare di esporre valori risolti delle credenziali. Gli errori di migrazione
mostrano, quando disponibili, gli indicatori di rollback e stato parziale.

## Verifiche

- Suite completa su PostgreSQL 17 isolato: **584 superati**, nessuno saltato o
  xfail, copertura **95%**.
- Accettazione: registrazione, check offline, piano di creazione senza effetti,
  creazione di un database assente con due schemi/sei tabelle, scritture e join
  fra schemi, formula numerica, REPL con commit e rollback all'uscita, successivo
  piano senza comandi; opt-in delle rimozioni di colonne e preservazione di
  tabelle/schema estranei secondo il contratto del migratore.
- Costruttore `AsqueelDb` verificato come classe reale, istanza proprietaria
  delle tabelle, sottoclassabile e compatibile con la factory precedente.
- Test subprocess da una directory diversa dal progetto e test delle
  credenziali/resolver, sovrapposizione delle ricette, nomi invalidi e duplicati.
- Ruff, mypy (35 file sorgente), Sphinx con warning come errori; wheel e
  console script verificati in ambiente temporaneo.

La documentazione d'uso è in [CLI](../guide/cli.md); l'esempio eseguibile è
`examples/two_schemas`. Nessun database utente, registro personale, commit,
push o rilascio viene modificato da queste verifiche.
