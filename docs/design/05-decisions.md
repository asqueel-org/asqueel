# 05 — Decisioni acquisite e questioni aperte

## Vincoli acquisiti, da non rimettere fra le alternative

- PostgreSQL è prioritario in lettura e scrittura; altri dialetti possono essere parziali.
- SQLite è un adapter richiesto esplicitamente dall'utente, non una semplice
  raccomandazione. Prevedere dialetto dati e driver con prove proprie;
  riutilizzare l'adapter SQLite del migratore, già dotato dei quattro backend
  PostgreSQL, SQLite, MySQL e SQL Server. Verificare il collegamento con Asqueel
  e registrare le capacità e le differenze rispetto a PostgreSQL.
- Modello ottenibile dal DB e da package/applicazioni legacy, oltre alla via nativa.
- Componenti/mixin di adattamento legacy sono ammessi.
- aggregateRows e la ricomposizione Python implicita sono eliminati anche nel bridge.
- Informazioni UI nel modello o in entità parallele collegate alla medesima colonna.
- VirtualRelation della proposta GEP incluse nell'obiettivo.
- View, trigger e funzioni native previsti in prospettiva, con supporto del migratore.
- Subtable, scope partition e partizioni fisiche devono essere distinti.
- Schema come prefisso del nome tabella e mapping legacy devono essere supportati.

Aggiornamento del perimetro iniziale: la V1 è destinata ad applicazioni nuove,
con nucleo e runtime **sincroni**. L’implementazione async è successiva, ma
la sua praticabilità va tutelata fin da ora: preferire scelte portabili e
registrare ogni ostacolo concreto secondo il [criterio 26](26-async-portability.md).
La configurazione tramite grammatiche deve produrre oggetti vivi: `db` è la
radice e l'utilizzo applicativo passa da `db.table(...).query(...).fetch()`.
La logica del legacy guida lifecycle, responsabilità e contratti applicativi;
non è soltanto un riferimento sintattico del compiler. Store e tenant possono
seguire; partition, draft e cancellazione logica restano nel perimetro acquisito.

La [revisione architetturale 09](09-legacy-object-api-review.md) distingue il
nucleo tecnico già implementato dal livello prodotto ancora mancante. I report
di consegna precedenti non certificano il completamento di quel livello.

## Costrutti Genro nella compilazione — accordo del 30 settembre 2026

`#` seguito da un nome maiuscolo, come `#IN_RANGE`, identifica un costrutto
proprio del linguaggio Genro, riconosciuto ed elaborato durante la compilazione.
Si conserva questa sintassi con un'implementazione interna strutturata: non si
riduce il contratto a una sostituzione testuale preliminare.

L'elaborazione può generare SQL, preparare parametri, risolvere riferimenti al
contesto o predisporre trasformazioni del risultato dopo la lettura. Esempi:
`#IN_RANGE`, `#PERIOD`, `#THIS`, `#BAG`. Il compiler può quindi predisporre una
trasformazione senza eseguirla nella fase di compilazione.

Questo accordo definisce il significato della sintassi e l'impostazione del
compiler; non certifica l'implementazione di tutte le macro legacy e non cambia
le priorità di consegna. Non impone inoltre il maiuscolo a ogni uso storico di
`#`: i riferimenti alle sottoquery nominate, come `#nome`, restano distinti.

## Conoscenza e destinazione di ogni contratto legacy — 30 settembre 2026

Requisito esplicito dell'utente: ogni singolo aspetto di Asqueel legacy deve
essere conosciuto prima di decidere come trattarlo. Per ogni comportamento
occorre indicare se viene implementato nel nucleo con la stessa semantica,
implementato diversamente con adattamento di compatibilità, oppure delegato
all'adapter legacy. L'adapter di compatibilità è distinto dagli adapter di
dialetto SQL e non deve essere un contenitore di comportamenti non analizzati.

Il censimento dei test è una fonte, non una dimostrazione di completezza.
L'analisi deve comprendere sorgenti, API, default, opzioni, effetti collaterali,
errori, lifecycle, estensioni, consumer applicativi, GEP e conversazioni pertinenti.
Ogni area non studiata resta esplicitamente «da analizzare». Un requisito
rinviato non è un requisito escluso né implicitamente delegato.

Ogni diversa semantica o esclusione richiede una decisione esplicita. Restano
valide le decisioni già acquisite: aggregateRows non viene reintrodotto nemmeno
nell'adapter; i bisogni coperti vanno ricondotti a raccolte esplicite. La semantica
partition esplicita concordata non viene annullata dal ponte di compatibilità.

## Decisioni da chiudere al momento opportuno

Ogni voce indica una raccomandazione, non un consenso già acquisito. Non è
necessario rispondere a tutte prima di iniziare: il piano indica quando diventano vincolanti.

### D-01 — Dominio e applicazione campione

**Scelta:** database e package/app rappresentativi, accesso e ambiente di prova.
**Raccomandazione:** iniziare dal dominio cliente/fattura/righe del corpus,
poi un'app reale con subtable, policy e almeno un hook di scrittura.
**Tradeoff:** dominio piccolo dà risposte esatte; app reale rivela accoppiamenti nascosti.
**Da chiudere:** P0. Non usare un database di produzione come fixture modificabile.

### D-02 — Versioni server e driver

**Scelta:** minimo PostgreSQL, driver e matrice delle estensioni.
**Raccomandazione:** un solo driver iniziale con contratto completo; ampliare
dopo la prima prova verticale. Rispettare le versioni stabili dell'ecosistema
Genro quando si aggiornano dipendenze, verificandole al momento dell'implementazione.
**Tradeoff:** più varianti aumentano immediatamente la matrice dei comportamenti.
**Da chiudere:** prima di P3; i documenti PostgreSQL 18 non impongono quella versione minima.

### D-03 — Identità e forma del modello

**Scelta:** formato sorgente, identità persistenti, descrittori runtime e versionamento.
**Raccomandazione:** identità distinta dai nomi, source serializzabile e vista
runtime risolta; provenienza per contributo, oggetti fisici separati dai semantici.
**Tradeoff:** più struttura iniziale, minore ambiguità di rename/import/cache.
**Da chiudere:** P1, prima di fissare i formati di esportazione.

### D-04 — Grammatiche e composizione

**Scelta:** dove montare grammatiche e come dichiarare override/rimozioni.
**Raccomandazione:** vocabolario SQL fondamentale comune, estensioni distribuite
quando cambiano gli elementi; merge per famiglia con conflitti espliciti.
**Vincolo aggiornato:** risolvere la grammatica effettiva di ogni nodo e integrare
il rendering a oggetti; i limiti attuali di validatore/emitter sono lavoro da
correggere, non motivi per rinviare questo contratto.
**Da chiudere:** P1 dopo un prototipo che coinvolga anche validatori ed emitter.

### D-05 — UI e profili

**Scelta:** forma concreta dei metadati inline/paralleli, namespace ed editor provider.
**Raccomandazione:** stessa vista risolta, profili per contesto, layout di schermata
separato; nessuna dipendenza obbligatoria da widget nel compiler.
**Tradeoff:** permettere tutte le forme senza precedenze chiare crea duplicazioni.
**Da chiudere:** contratto in P1, integrazione reale GUI in P5.

### D-06 — Frontend nativo delle query

**Scelta:** sintassi testuale iniziale, API strutturata e nomi delle operazioni.
**Raccomandazione:** mantenere riferimenti familiari, un solo resolver, QuerySpec
esplicito e result plan; niente secondo motore semantico per Bag o oggetti Python.
**Vincolo aggiornato:** il percorso DB → tabella → query → fetch appartiene alla
prima verticale del prodotto. Non è un adapter legacy opzionale; occorre
verificare tempi di compilazione, ambiente, sessione e forma dei risultati.
**Da chiudere:** forma minima in P1/P3; estensioni in P4 con esempi comparativi.

### D-07 — Profilo legacy e anomalie

**Scelta:** quali ingressi/consumer supportare e quali anomalie emulare.
**Raccomandazione:** perimetro misurabile e diagnostiche; adapter sottili deleganti.
**Vincolo:** A07/aggregateRows è già risolta con rimozione. Non è riapribile
come opzione per «completare la compatibilità».
**Da chiudere:** perimetro iniziale in P0, comportamenti specifici prima di P5.

### D-08 — Dettagli delle virtualRelation e aggregati

**Scelta:** derivazione da relazioni limitate, inverse filtrate, namespace ask,
forma di raccolte, ordine, default sugli insiemi vuoti e aggregati annidati.
**Raccomandazione:** NULL SQL espliciti, order totale per limit=1, sola lettura
e binding di sorgente/target distinti; non sovraccaricare SUM come concatenazione.
**Tradeoff:** sintassi compatta può nascondere la cardinalità o lo scope.
**Da chiudere:** P4, prima delle implementazioni che dipendono dal singolo punto.

### D-09 — Scritture e hook

**Scelta:** transazioni, callback, record-cluster, bulk, errori e concorrenza.
**Raccomandazione:** primitive SQL e operazioni di dominio esplicite, niente
transaction manager concorrenti nello stesso flusso; un ordine documentato degli hook.
**Tradeoff:** supportare tutto il legacy subito renderebbe il primo prototipo troppo ampio.
**Da chiudere:** primitive in P3, contratti di dominio prima di P5.

### D-10 — Obiettivi prestazionali

**Scelta:** carichi, dataset, cardinalità, metriche e limiti accettabili.
**Raccomandazione:** prima baseline e correttezza, poi obiettivi per compilazione,
query count, DB, p95 e memoria. Niente soglie arbitrarie nel dossier.
**Tradeoff:** un solo dataset uniforme favorisce ottimizzazioni poco generalizzabili.
**Da chiudere:** prima di P6; raccogliere misure già da P3.

### D-11 — Oggetti nativi e migrazioni evolute

**Scelta:** formato versionato e ordine delle famiglie da implementare.
**Raccomandazione:** contratto predisposto in P1; implementazione differita,
con dipendenze esplicite, preservazione SQL, capability e test end-to-end.
Materialized view e procedure distinte dalle funzioni richiedono una scelta di perimetro.
**Tradeoff:** un campo SQL libero da solo non gestisce identità, diff e dipendenze.
**Da chiudere:** formato prima di P7, caratteristiche precise all'avvio dei sottointerventi.

### D-12 — Dialetti ulteriori e rilascio

**Acquisito:** SQLite è richiesto come backend aggiuntivo.
**Scelta residua:** packaging del bridge, profili pubblici, requisiti di supporto
e calendario di consegna. Ulteriori backend in base all'utilizzo reale.
Un adapter deve dichiarare ciò che non supporta.
**Tradeoff:** copertura nominale larga senza test reali dà falsa portabilità.
**Da chiudere:** sottoinsieme iniziale in P0, matrice di rilascio in P8.

## Accepted update — locale context without validation

The user chose no locale validation, catalogue or mandatory Babel dependency.
Keep date/locale values as context and document the difference from legacy
default-locale validation. See [contract 24](24-workdate-locale-contract.md).

## Clarified update — callback error ownership (1 October 2026)

A callback handles recoverable failures using try/except when needed. Normal
return allows dispatch to continue; an escaping exception interrupts dispatch
and reaches the caller. The completed SQL commit remains durable. No automatic
continue-on-error or error aggregation. Application request cleanup owns queue lifetime: rollback/close clears pending
callbacks. No forced queue disposal solely for a Python postcommit exception;
see [delivery 27](27-f1-request-lifecycle-closure.md).
