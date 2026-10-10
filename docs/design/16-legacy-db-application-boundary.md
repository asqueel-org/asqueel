# 16 — Revisione dei percorsi: GnrSqlDb, GnrSqlAppDb e applicazione

30 settembre 2026. Prima sezione della revisione per percorsi di esecuzione.
Analisi statica delle implementazioni: nessun test di esecuzione aggiunto e
nessuna pretesa di completamento dell'intero censimento legacy.
Baseline legacy: `fa35e5adfa6ad1b269f3a22a9b12c4c1ee6513ea`.

## Risultato

Occorre distinguere il database autonomo dall'integrazione con un'applicazione.
Nel legacy `GnrSqlAppDb` estende `GnrSqlDb`: non è un secondo compiler e non è
un adapter di dialect. Il nuovo `SqlDatabase`, malgrado il modulo si chiami
`application.py`, non implementa ancora un equivalente di questo collegamento:
possiede configurazione, modello, compiler, tabelle e una Session, ma non un
contratto di integrazione con app, risorse, permessi, eventi e provider dinamici.

Un'articolazione analoga è la proposta da perseguire, mantenendo aperti nomi
e dettagli del contratto finché le dipendenze non siano censite. Il suggerimento
dell'utente «probabilmente qualcosa di simile» non viene trasformato in una
scelta definitiva di classi, ereditarietà o protocollo.

## Fonti lette e confini della lettura

- `gnr/sql/gnrsql/db.py`: composizione dei mixin, inizializzazione e riferimenti all'app.
- `gnr/app/gnrapp.py:306`: intero corpo di GnrSqlAppDb, fino a _getUserConfiguration.
- `gnr/app/gnrapp.py:1041`: costruzione db, installazione mixin, startup.
- `gnr/app/gnrapp.py:1746`: hook applicativi base e ingresso import da DB esterno.
- `gnr/web/gnrwebapp.py:64`: notifyDbUpdate, sottoscrizioni, notifyDbEvent,
  onDbCommitted e compressione eventi.
- `gnr/sql/gnrsql/connections.py`, `transactions.py`: percorsi di connessioni,
  commit, code deferred, eventi pendenti e rollback già letti nel riesame.
- `gnr/sql/gnrsql/write.py:294`: dipendenza dai permessi dell'app nel delete.
- Nuovo `src/asqueel/application.py`: responsabilità attuali di SqlDatabase.

I provider chiamati da questi metodi, la gestione completa degli store,
le risorse di tabella e tutti i consumer esterni richiedono ancora approfondimento.
Le righe indicano la posizione nella baseline, non una promessa di stabilità futura.

## Percorso di costruzione

1. L'app prepara gli attributi del DB, imposta `application=self` e applica
   l'eventuale configurazione DSN.
2. Costruisce GnrSqlAppDb; l'app è obbligatoria per questa sottoclasse.
3. Il costruttore base crea modello/adapter e chiama `self.registerMacros()`:
   entra quindi nell'override della sottoclasse prima che l'assegnazione
   `application.db = ...` sia completata.
4. L'override registra macro base/dialect, poi quelle app e infine quelle dei
   package. Il broadcast passa il db esplicitamente per questo motivo.
5. L'app carica packageMixin/tableMixin, inizializza inTransactionDaemon,
   notifica onDbStarting e invoca db.startup().
6. Completa la localizzazione e l'inizializzazione applicativa.

Contratto da preservare: un'estensione non può presumere disponibili servizi
non ancora inizializzati. Il rendering moderno deve rendere esplicite queste
fasi; non basta aggiungere un parametro application al costruttore attuale.

## Inventario delle responsabilità aggiunte dalla sottoclasse

Destinazioni sotto proposte: devono essere verificate sul comportamento, non
considerate decisioni di esclusione. «Compatibilità» indica il ponte Genropy,
non l'adapter PostgreSQL.

| ID | Membri legacy | Comportamento osservato | Destinazione proposta |
|---|---|---|---|
| APP01 | __init__ | Rifiuta application assente. | Livello DB collegato all'app; nucleo avviabile senza app. |
| APP02 | stores_handler, dbstores, auxstores | Handler lazy e store derivati dall'app. | Collegamento configurazione app; gestione connessioni nel nucleo. Dettagli store rinviati, non dimenticati. |
| APP03 | tenant_table, multidb_config, storetable | Legge attributi dei package e conserva configurazione multidb. | Integrazione app/configurazione con capacità store/tenant futura. |
| APP04 | debug, localizer | Delega servizi all'app. | Servizi applicativi; fallback standalone definito. |
| APP05 | registerMacros | Estende registrazione base/dialect e chiama i package. | Estensioni del compiler; bootstrap e provider applicativi nel livello app. |
| APP06 | checkTransactionWritable | Riserva tabelle transazionali al daemon; forced_transaction bypass; attributo table con fallback package. | Policy applicativa su hook di scrittura del nucleo. Non confondere con transazione DB implicita. |
| APP07 | insert, update, delete | Controllo → metodo base → evento applicativo, salvo systemDbEvent. | CRUD nel nucleo; controlli/eventi nel livello app. |
| APP08 | raw_insert, raw_update, raw_delete | Anche raw passa per controllo e notifica app. | Conservare il contratto raw nel ponte; non assumere che significhi «nessun evento». |
| APP09 | notifyDbUpdate, onDbCommitted | Delegano all'app. | Punti di integrazione stabili, con semantica transazionale nel nucleo. |
| APP10 | getResource | Carica risorsa via site e le associa site/table/db. | Provider risorse applicativo; convenzioni Genropy nel ponte. |
| APP11 | getFromStore, currentPage | Legge pageStore e pagina corrente. | Integrazione web/compatibilità, nessuna pagina richiesta dal nucleo. |
| APP12 | quickThermo, thermoMessage | Delega progressi alla pagina; fallback senza pagina. | Servizio progressi applicativo con bridge web. |
| APP13 | currentUser | Prima environment user, poi utente della pagina. | Contesto utente applicativo; precedenza da conservare nel ponte. |
| APP14 | localVirtualColumns | Metodi formulacolumn_* della pagina, metadati e maintable; risultati singoli/multipli. | Provider di colonne dinamiche; scoperta metodi di pagina nel ponte. |
| APP15 | customVirtualColumns | Legge definizioni da adm.userobject, evitando ricorsione sulla stessa tabella. | Provider applicativo; repository adm nel ponte Genropy. |
| APP16 | _getUserConfiguration | Delega ad adm.user_config se presente. | Provider configurazione utente; convenzioni adm nel ponte. |

## Percorso scrittura → eventi → commit

`SqlAppDb.insert/update/delete` non sostituisce la pipeline del nucleo: la
circonda con controlli e notifica. Dopo il metodo base, systemDbEvent può
impedire la notifica applicativa. Le scritture raw hanno anch'esse questi wrapper.

I metodi GnrApp.notifyDbEvent/onDbCommitted base sono vuoti. La vera gestione
web sta in GnrWsgiWebApp:

1. notifyDbEvent determina una chiave eventi tramite db.connectionKey().
2. Prepara env_transaction_id se assente; valuta broadcast e sottoscrizioni.
3. Accumula tabella, tipo evento, PK/vecchia PK e campi broadcast tipizzati;
   prende autoCommit dall'environment.
4. Può invocare adm.audit indipendentemente dall'accumulo broadcast.
5. Il commit SQL del nucleo esegue le code deferred e poi onDbCommitted().
6. L'override DB delega all'app; l'app web estrae gli eventi, filtra i destinatari,
   comprime eventi ripetuti e notifica pagina locale o registro del sito.

Non bisogna confondere questa pipeline con LISTEN/NOTIFY PostgreSQL, né dedurre
che le app senza pagina non debbano produrre eventi: il codice delle sottoscrizioni
considera anche batch e task. Test necessari prima della replica: connessioni
nominate, più store, rollback, errore dopo commit, destinatari assenti, cambio PK,
insert seguito da delete, aggiornamenti ripetuti e audit che scrive altre righe.

## Asimmetrie e dipendenze da chiarire prima di implementare

- Il confine legacy non è perfettamente isolato: GnrSqlDb accetta application
  opzionale e legge configurazione/localizer; delete con deletable testuale
  chiama application.checkResourcePermission. Non assegnare responsabilità
  soltanto in base al file che le contiene.
- GnrSqlAppDb registra THIS/BAG accanto alle macro app; la collocazione storica
  della registrazione non dimostra che la loro semantica richieda un'app.
- raw_update riassegna `old_record = record or dict(record)` prima della
  notifica. Registrare il comportamento e verificarne gli effetti: non copiarlo
  né correggerlo tacitamente assumendo che sia una scelta voluta.
- Il commit base attraversa connessioni con nome attivo e può coinvolgere più
  store; onDbCommitted web usa la chiave del contesto attivo. La corrispondenza
  fra tutti gli eventi e tutti i commit richiede prove, non è certificata qui.
- Le code deferred sono per connectionKey, ma `_pendingExceptions` si trova
  nell'environment senza tale suffisso. La precedente sintesi «tutto separato
  per connessione» è un obiettivo da specificare, non un fatto dimostrato per
  ogni stato legacy. Verificare isolamento e pulizia su cambio connessione.
- rollbackAll nel sorgente letto ripulisce code deferred ed eccezioni; la
  pulizia completa degli eventi applicativi deve essere seguita nei chiamanti.
- I provider di colonne locali/custom dipendono da pagina/app: una futura cache
  del modello non deve riutilizzare definizioni fra contesti incompatibili.

## Proposta architetturale da verificare

Tre responsabilità distinte, senza fissare ora tre nuovi package:

1. **DB autonomo:** modello, compiler, connessioni nominate, environment,
   transazioni e pending work, CRUD e punti di estensione del lifecycle.
2. **DB collegato a un'app:** specializzazione analoga a GnrSqlAppDb che collega
   servizi, provider, policy, eventi e contributi dei package. Per nuove app
   non deve richiedere pagina web o tabelle adm.
3. **Compatibilità Genropy:** implementazione delle convenzioni legacy sopra
   i due livelli: pagina, site, adm, risorse, nomi dei callback e firme storiche.

L'adapter di dialect e il driver restano responsabilità diverse e sottostanti.
I test devono provare prima il DB standalone, poi il collegamento a un'app minima
senza web, infine il ponte Genropy. Tutti usano lo stesso compiler e lifecycle;
non si duplicano transazioni e code pending nel ponte.

## Conseguenze per il piano e stato della revisione

F0 deve tracciare base, override e consumer per ogni percorso. F1/F4 devono
prevedere lifecycle e punti di integrazione senza anticipare il framework web.
F2 deve distinguere modello dichiarato e contributi dinamici applicativi.
F8/F9 consegnano integrazione avanzata e ponte, ma i loro requisiti guidano
le primitive del nucleo fin dall'inizio.

Questa sezione conosce il corpo della sottoclasse e i principali passaggi
costruzione/scrittura/eventi. Restano aperti il censimento completo di provider
e chiamanti, i percorsi dettagliati di modello/query/record/selection, tutte
le diramazioni CRUD, introspezione/migrazione e la verifica eseguibile.
