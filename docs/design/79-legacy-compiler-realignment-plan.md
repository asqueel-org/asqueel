# 79 — Riallineamento del compilatore agli algoritmi legacy

**Aggiornamento del riferimento, 15 ottobre 2026:** il [censimento 95](95-develop-reference-audit.md) fissa
GenroPy develop `95da66ee64b0c789dbb6b35254011d83ce1911c5` per i prossimi
raccordi. I rapporti R0–R4 sotto conservano il riferimento e gli esiti storici;
non certificano i fix successivi. Per stato operativo e prossimi passi prevalgono
il piano 86 e il rapporto 95. Nessun nuovo fix implementato da questo audit.

**Decisione corrente, 15 ottobre 2026 — piano per fasi legacy:**
[diagramma e piano 86](86-legacy-compiler-logical-phases.md).
La sostituzione di QueryPlan/Fragment comprende da subito la risoluzione delle
relazioni sul nuovo albero: la SELECT fisica da sola non valida l’architettura.
Contenitore equivalente a SqlCompiledQuery, clausole SQL e kwargs separati,
assemblaggio e preparazione agli adapter. Binding PostgreSQL invariato:
ClientCursor ritirato; il parametro tra apici è un errore d’uso e non un requisito.
Piano operativo in cinque fasi, con riferimenti legacy e prove di chiusura.
Obiettivo vincolante: reimplementazione chiara e leggibile dello stesso algoritmo,
senza variazioni non concordate; ricorsione e ordine delle operazioni preservati.
Fase 1 verificata nel [rapporto 87](87-legacy-rewrite-phase1-baseline.md):
144 test legacy passati e 2 skip, 148 SELECT fisiche equivalenti; censite
144 relazioni native. Sul nuovo albero il raccordo relazionale manca ancora.
Contratti e differenze fissati; compilatore invariato, fase 2 non iniziata.
Le note successive conservano lo storico dei passi precedenti.

**Istruzione vincolante successiva:** il legacy è la specifica. Le aggiunte
non concordate non sono più una coda di proposte da sottoporre all'utente:
vanno escluse dal raccordo. In particolare non esiste la sintassi `$"nome"`:
i riferimenti sono `$campo` e `@relazione.campo`. Valgono gli algoritmi legacy
anche per le altre forme lessicali e i controlli che il nuovo scanner aveva
aggiunto. Chiedere soltanto davanti a un impedimento concreto, con codice e
prova del problema. R1–R3 sono completate; niente avvio anticipato di relations.
Le tabelle di differenze sotto documentano la storia del confronto, non nuove
scelte aperte sulla sintassi. Gli adapter restano responsabili della preparazione.

15 ottobre 2026. **Piano aggiornato dopo la verifica R4.** Il confronto del
[rapporto 78](78-scanner-legacy-comparison.md) non giustifica la sostituzione
complessiva degli algoritmi legacy. Prima di proseguire con le relazioni,
recuperare le compatibilità perse, escludendo le aggiunte non concordate.
Questo piano precede la fase 2 del [piano 76](76-hierarchical-compiler-plan.md)
e ne corregge l'indicazione di riutilizzare automaticamente lo scanner.

**Avanzamento:** R0 completata nel [rapporto 80](80-legacy-realignment-r0-contracts.md).
R1 completata nel [rapporto 81](81-legacy-realignment-r1.md): raccolta, risoluzione
e sostituzione legacy sulla SELECT fisica del nuovo albero.
R2 completata nel [rapporto 82](82-legacy-realignment-r2.md): proiezioni conservate
come nel legacy ed embedFieldPars sul WHERE.
R3 completata nel [rapporto 83](83-legacy-realignment-r3.md): preparazione comune,
adapter e adattamento psycopg 3 basato sull’algoritmo postgres3 già nel legacy.
R4 verificata nel [rapporto 84](84-legacy-realignment-r4.md), accettazione ancora
aperta per binding PostgreSQL. I residui nel renderer sono eliminati nel
[rapporto 85](85-legacy-renderer-and-postgres-binding.md): 3.944 test passati,
13 saltati; proposta ClientCursor isolata, non applicata. Prestazioni rimisurate.
R5 non avviata. Verifica storica di R3: **3.918 test superati, 13 saltati**;
100 confronti R3 sul riferimento senza differenze, otto snapshot confrontati,
24 verifiche d’integrazione e 148 SELECT native senza differenze.

**Decisione successiva a R0:** confermata la delega agli adapter del legacy,
separando la preparazione di SQL/kwargs dall'esecuzione. Il dettaglio sotto
aggiorna le responsabilità di R1–R3. M1 resta nel lavoro sugli adapter di R3: non è una domanda preliminare per R1.

**M2 e M3 chiuse sul comportamento legacy:** per commenti e stringhe SQL
mantenere gli algoritmi legacy, comprese le convenzioni di template ed escape.
Non portare protezioni aggiuntive del contenuto come miglioramento del raccordo.
La scelta non approva le estensioni lessicali D1/D2 né gli altri miglioramenti.
R1 riallinea la sostituzione dei campi; la preparazione dei parametri resta da
completare in R2/R3. Il precedente compilatore conserva il proprio percorso.

**Alias delle sottoquery:** confermata anche qui la convenzione legacy.
Gli alias delle tabelle sono determinati dal contesto SQL proprietario,
separatamente dai namespace e dagli allocatori dei parametri.

## Regole e perimetro

- Il riferimento corrente è GenroPy develop
  `95da66ee64b0c789dbb6b35254011d83ce1911c5`, secondo il rapporto 95.
  `fa35e5adfa6ad1b269f3a22a9b12c4c1ee6513ea` resta il riferimento storico
  degli oracoli R0–R4. Gli snapshot sperimentali restano confronti, non
  autorizzazioni a cambiare algoritmo; impronte storiche nel rapporto 78.
- Obiettivo: query sul nuovo albero → SQL e kwargs pronti per il driver,
  senza connessione o esecuzione. Nessuna nuova sintassi o opzione pubblica.
- Riprendere gli algoritmi e il loro ordine, adattando l'accesso agli oggetti.
  Non convertire DbModel in ResolvedModel e non ricostruire la source.
- Non introdurre scostamenti migliorativi. Chiedere soltanto per un impedimento
  concreto al porting fedele; un test Asqueel verde non autorizza una deviazione.
- Mantenere disponibile il percorso attuale durante il lavoro; renderer
  predefinito, scritture, migration, mixin e RuntimeModel restano separati.
  Query concatenate, operatori e altre funzionalità rinviate restano rinviati.
- Non introdurre un framework di compatibilità o un flag «legacy/moderno».
  Le responsabilità da separare sono quelle già presenti negli algoritmi.

## Decisione acquisita — delega agli adapter e preparazione senza esecuzione

Richiesta esplicita dell'utente: mantenere la stessa delega agli adapter del
legacy, separando la preparazione di SQL e kwargs dall'esecuzione.

| Responsabilità | Riferimento legacy | Raccordo previsto |
| --- | --- | --- |
| Risolvere modello, colonne, relazioni, formule e clausole | `SqlQueryCompiler.compiledQuery` e relativi helper | Riprendere gli algoritmi sul nuovo albero; mantenere le chiamate all'adapter per quoting, alias e macro dove già previste |
| Assemblare il SQL specifico del database | `SqlCompiledQuery.get_sqltext` delega a `adapter.compileSql` | Conservare questa delega, senza ramificazioni per SQLite/PostgreSQL nel nucleo di risoluzione |
| Preparare SQL e kwargs per il driver | Preparazione comune in `execute`, poi `adapter.prepareSqlText` | Separare questi passaggi dall'esecuzione, mantenendo ordine e responsabilità; espansione delle collection, segnaposto e operatori specifici restano nell'adapter |
| Eseguire il SQL preparato | Cursore/driver chiamato da `execute` | Passaggio successivo e distinto, non richiesto per ottenere SQL e kwargs |

Il compilatore legacy non era privo di dipendenze dall'adapter: lo consultava
anche durante la risoluzione. Non sostituire quella delega con un compilatore
astrattamente indipendente dal database né spostare tutto nell'ultima stampa SQL.
Dialetti, formatter e QueryPlan attuali sono riutilizzabili solo se rispettano
questa distribuzione delle responsabilità; non fissano un'architettura alternativa.

La preparazione deve essere richiamabile senza aprire connessioni, creare cursori
o eseguire statement. Non deve ripetere il mangling: il risultato preparato non
attraversa una seconda volta la stessa preparazione prima del driver. Non si
introducono qui nuove firme pubbliche o un nuovo framework di adapter.

Questa decisione **non approva M1** né gli altri miglioramenti: colloca la
collisione nell'espansione delle collection nel livello che già la gestiva.
Seguire il legacy nel rispettivo livello; chiedere soltanto per impedimenti concreti.

## Decisione acquisita — alias delle sottoquery come nel legacy

Seguire `aliasCode(n)` e la costruzione di `aliasPrefix` nel ramo sottoquery di
`getFieldAlias` del riferimento legacy: `aliasPrefix = '%s_t' % alias`, dove
`alias` è quello della tabella proprietaria nel contesto esterno.

- Nella SELECT principale: `t0`, `t1`, `t2`, ecc.
- Sottoquery riferita alla tabella esterna `t0`: prefisso `t0_t`, quindi
  `t0_t0` per la radice e `t0_t1`, `t0_t2`, ecc. per le JOIN locali.
- Se la proprietaria esterna è `t1`, usare `t1_t0`, `t1_t1`, ecc.; non assumere
  sempre la radice della SELECT esterna. L'annidamento ripete la stessa regola.

Non derivare questi alias dal namespace di `_Bindings` o dal suo contatore.
Nomi/valori dei parametri e loro mangler rimangono separati, con i rispettivi
scope. La decisione sugli alias non approva un nuovo mangling dei parametri.
Non imporre unicità globale agli alias di sottoquery sorelle: seguire gli scope
SQL e il riuso consentito dall'algoritmo legacy.

Nel raccordo delle sottoquery verificare prefissi dalla proprietaria reale,
JOIN locali, correlazioni `#THIS`, sottoquery sorelle/annidate e parametri omonimi.
A parità di struttura SQL, cambiare i nomi dei parametri non deve modificare
gli alias delle tabelle. Nessuna implementazione in questo aggiornamento.

## Sequenza di lavoro

### R0 — Fissare contratti e provenienza dei test

Usare il corpus esistente di 71 casi / 132 prove e i test legacy originali
censiti, mantenendo distinti originali, adattamenti e sonde nuove. Non alterare
le evidenze del rapporto 78: i nuovi risultati avranno un confronto separato.

Produrre una matrice per caso con riferimento legacy, comportamento attuale,
risultato richiesto, fase responsabile e stato della decisione. Classificare:
compatibilità da recuperare, divergenza già concordata, miglioramento candidato,
dipendenza ancora aperta o funzionalità rinviata. Le aspettative «SQL letterale»
delle sonde non sostituiscono automaticamente le convenzioni GenroPy.

**Uscita:** ogni differenza ha una destinazione verificabile. I conflitti con
test attuali sono elencati; niente cancellazioni, xfail o aspettative indebolite
per far passare il port. Le prove dei comportamenti candidati restano visibili.

### R1 — Ripristinare il nucleo di risoluzione legacy — completata

Seguire `compiledQuery`: raccolta attraverso `updateFieldDict`, mappa dei
riferimenti distinti, risoluzione attraverso `getFieldAlias`, sostituzione
attraverso `templateReplace`. Conservare il ciclo che risolve anche i nuovi
riferimenti introdotti durante l'espansione e la distinzione safe/strict delle
clausole; non risolvere ripetutamente un campo per ogni occorrenza testuale.

Iniziare dalle colonne fisiche sul nuovo albero, usando nomi SQL e schema degli
oggetti effettivi. Verificare le utilità già disponibili prima di duplicare
quelle legacy: un equivalente è riutilizzabile solo con lo stesso contratto.
Non portare parti del templating estranee all'uso SQL.
Conservare le deleghe legacy all'adapter per nomi, alias e macro: l'assenza di
ramificazioni per database non significa eliminare quelle chiamate.

Stato e mappe appartengono alla singola compilazione. Riferimenti alle colonne,
alias di tabella e parametri restano distinti; non scrivere stato SQL sul modello
condiviso. Nessun secondo mangling di SQL già preparato. Prima di cambiare helper
condivisi, censire anche i chiamanti del vecchio compilatore e delle scritture.

**Uscita:** SELECT fisica, WHERE e ORDER BY seguono la sequenza legacy; prove
sui riferimenti ripetuti, riuso della query, immutabilità del modello e assenza
di I/O. Per commenti e letterali vale la decisione M2/M3: comportamento legacy,
senza conservare implicitamente le protezioni aggiuntive dello scanner attuale.

Risultato e prove: [rapporto 81](81-legacy-realignment-r1.md). Il nucleo non usa
più lo scanner attuale per scoprire e sostituire i riferimenti. La preparazione
degli adapter esistenti usa ancora quel tokenizer: non è parità completa R3.

### R2 — Recuperare proiezioni e convenzioni dei parametri — completata nel perimetro locale

**Esito:** [rapporto 82](82-legacy-realignment-r2.md). Proiezioni con AS conservate
integralmente e chiave dei duplicati dal primo AS, come in compiledQuery. CAST
senza alias esterno non viene più rifiutato. Se i nomi dei risultati dipendono
dal database, si usa la descrizione del cursore già prevista dai driver; non
si inventano alias. Nessuna abilitazione della fetch sul nuovo albero.

Portato embedFieldPars con riconoscimento di colonne/virtuali/relazioni, bytes
e confini dei nomi. La risoluzione SQL di virtuali e relazioni rimane R5.
I contratti Unicode/escape sono fissati al confine del piano: la preparazione
finale dei valori e dei placeholder resta R3. Le istruzioni seguenti descrivono
il contratto del passo, non lavoro locale ancora da iniziare.

Verificare la normalizzazione/suddivisione delle proiezioni di `compiledQuery`
e la costruzione degli alias tramite `colToAs`. Recuperare gli alias impliciti
per espressioni, per esempio `$amount * 2`, e la regola legacy dell'ultima
proiezione per AS duplicato; il rifiuto attuale non è una decisione acquisita.

Portare `embedFieldPars` nel punto legacy: sul WHERE, prima di `updateFieldDict`.
Un parametro `threshold='$unit_price'` rappresenta il campo se il modello lo
riconosce; non estendere questa interpretazione arbitrariamente alle clausole
o a qualunque stringa. Portare i test `TestEmbedFieldPars` con la loro provenienza.

Fissare i casi di parametro Unicode e delle convenzioni di escape `\$`, `\@`,
`\:`, `$$` e percentuali, rispettando lo stadio in cui operano: `$$` appartiene
al template; gli adattamenti dei valori e del protocollo restano nel passaggio
separato di preparazione R3. Non trasferire nel nucleo gli adattamenti che il
legacy delegava a `execute`/adapter. Il risultato complessivo resta SQL/kwargs
preparati, senza importare esecuzione, connessioni o lifecycle.

**Uscita:** valori, alias e kwargs corrispondono al contratto legacy sui casi
locali. Il recupero di `@customer_id.id` come valore simbolico è tracciato ma
non dichiarato concluso: sul nuovo albero dipende dalla fase relations.
Le convenzioni di escape seguono il legacy, secondo la decisione M3; i test
attuali che richiedono protezioni aggiuntive vanno distinti e riallineati.

### R3 — Raccordare la delega agli adapter e separare la preparazione — completata

**Esito:** [rapporto 83](83-legacy-realignment-r3.md). Recuperati preparazione dei
valori, escape, Unicode, cast, operatori e collection. PostgreSQL usa l’espansione
IN del legacy postgres3 perché psycopg 3 non accetta la tupla unica del vecchio
adapter psycopg2; il formato finale rimane SQL e kwargs nominati separati.
I nomi generati e le collisioni seguono gli algoritmi legacy: nessuna correzione
M1 introdotta. La preparazione non elimina kwargs inutilizzati e non anticipa
l’errore del driver per un parametro ordinario mancante. SQL testuale e nuovo
albero usano questo percorso; il formatter del precedente compilatore rimane
separato. Le istruzioni seguenti restano il contratto di riferimento del passo.

Conservare i due passaggi legacy distinti: assemblaggio della SELECT attraverso
`adapter.compileSql`, poi preparazione attraverso `adapter.prepareSqlText` e
le trasformazioni comuni che la circondavano in `execute`. Rendere disponibile
questo percorso senza passare dall'esecuzione. Non spostare l'espansione delle
liste o la scelta del protocollo dei parametri nel nucleo del compilatore.

Recuperare `REGEXP → ~*` PostgreSQL e `ILIKE → LIKE` SQLite, confrontando
`prepareSqlText` e la preparazione degli argomenti legacy. Verificare cast,
IN/NOT IN, liste vuote, NULL, percentuali, parametri ripetuti e valori tipizzati.

Separare l'algoritmo dall'adattamento obbligato al driver: il legacy usa
psycopg2, Asqueel psycopg 3. Non copiare il binding delle tuple senza verificarne
il supporto. Documentare ogni adattamento necessario; se cambia il significato
pubblico, presentarlo prima di implementarlo. Non confondere la traduzione
dell'operatore con la decisione di proteggere stringhe e commenti.

**Uscita:** SQL eseguibile e kwargs corretti per PostgreSQL e SQLite, verificati
su dati temporanei separatamente dalle prove di compilazione senza I/O.
Non richiedere uguaglianza cosmetica del SQL o segnaposto incompatibili con il
driver; confrontare valori, tipi, nomi dei risultati e corrispondenza dei binding.
Collisioni e kwargs inutilizzati seguono il legacy, senza aggiunte non concordate.
Verificare le deleghe con adapter controllati e accesso a connessioni/cursori
vietato: preparazione una sola volta, stesso ordine legacy e nessuna esecuzione.
I test delle collisioni restano nel gruppo adapter/binding, non diventano una
condizione per approvare l'algoritmo di risoluzione dei campi.

### R4 — Verifica integrata eseguita; accettazione non chiusa

**Raccordo successivo, rapporto 85:** renderer senza scanner e assemblaggio
legacy verificati; le quattro differenze relative sono eliminate. Il binding
resta invariato e la proposta ClientCursor è da discutere. Non avviare R5.

**Prima verifica del 15 ottobre:** verifiche e benchmark completati nel rapporto 84,
senza modifiche a produzione/test/esempi. Restano differenze concrete di binding
PostgreSQL e scanner nel renderer condiviso; costi delle proiezioni numerose
misurati e profilati. R5 non avviata. Il mandato originale segue.

Rieseguire il corpus comune e i test legacy pertinenti, la SELECT fisica sulle
74 tabelle e la regressione del compilatore precedente. Includere le scritture
nei controlli dei componenti condivisi, senza estenderne il perimetro funzionale.
Verificare che modello, options e JSON migration non siano cambiati.

Ripetere i benchmark del rapporto 78: stessi dati, query nuove, warmup e round,
SQL/kwargs prima dell'esecuzione. Misurare separatamente vecchio percorso e nuovo
albero, includendo SELECT ordinaria, riferimenti ripetuti e CASE. Il ripristino
della risoluzione dei riferimenti distinti è recupero dell'algoritmo legacy,
non una nuova cache da inventare. Il conteggio delle risoluzioni deve riflettere
i riferimenti distinti per contesto, non le loro ripetizioni nel testo.

**Uscita:** rapporto prima/dopo con compatibilità recuperate, differenze residue,
decisioni esplicite e costi misurati. Nessuna dichiarazione di parità completa
basata soltanto sui test fisici o sulle 294 prove di regressione del rapporto 78.
Un rallentamento significativo ancora presente va spiegato prima di procedere;
non fissare soglie arbitrarie né attribuire al solo scanner il costo della pipeline.

### R5 — Riprendere il piano gerarchico, senza saltare dipendenze

Dopo la verifica R4, riprendere le fasi 2–6 del piano 76:

1. `getFieldAlias → _findRelationAlias → _getRelationAlias` sul ramo relations,
   con joiner O/M, identità dei percorsi e alias distinti; completare qui i test
   `embedFieldPars` con riferimenti `@` sul nuovo albero.
2. Alias di modello, formule SQL, dipendenze, `var_*` e metodi già disponibili,
   mantenendo l'ordine legacy: metodo prima dell'estrazione di `var_*`.
3. Sottoquery e correlazioni: alias derivati dal proprietario secondo il legacy,
   separati dai mangler dei parametri; nessuna contaminazione fra query
   sorelle/annidate e nessuna trasformazione arbitraria in JOIN.
4. Options di lettura, filtri impliciti, `*` e macro già nel perimetro deciso.
5. Accettazione per famiglia sui 74 modelli e relativi test legacy.

Questi passi non partono durante il riallineamento minimo. Le questioni già
aperte su pkey implicita, ordine predefinito e DISTINCT/exploding non vengono
risolte indirettamente da questo piano.

## Differenze censite: riferimento storico, non proposte di estensione

La tabella conserva i motivi del confronto. La regola successivamente precisata
è applicare il legacy, senza riproporre le aggiunte come esigenze da valutare.
Il percorso precedente resta disponibile durante il raccordo; non certifica
né impone il proprio comportamento al nuovo. Nessun flag «legacy/moderno».

Gli identificativi restano stabili, ma non indicano più una coda unica:
**M1 appartiene agli adapter (R3); M2–M5 e D1–D5 seguono il legacy nel rispettivo
passo di raccordo.** Non sono blocchi decisionali per R1. Eventuali impedimenti
effettivi devono essere dimostrati, senza spostare le responsabilità fra livelli.

| ID | Tema storico e fase competente | Evidenza e limite |
| --- | --- | --- |
| M1 | Correzione delle collisioni non introdotta — R3 segue il legacy | SQLite: `ids=[1,2]`, `ids0=3`; il legacy sovrascrive un valore. Non richiede una scelta del database nel nucleo del compilatore |
| M2 | Chiuso: mantenere il comportamento legacy nei commenti | Non introdurre la protezione aggiuntiva proposta; recuperare gli algoritmi legacy |
| M3 | Chiuso: mantenere il comportamento legacy nelle stringhe SQL | Conservare sostituzioni, template ed escape legacy; nessuna protezione aggiuntiva approvata |
| M4 | Riconoscere AS senza distinzione di maiuscole | `As` funziona nell'attuale e produce SQL invalido nel caso legacy; distinto dagli alias impliciti da recuperare |
| M5 | Segnalare parametri mancanti già alla compilazione | Diagnosi anticipata osservata; definire il contratto dell'errore senza inventare nuove API |

I riferimenti logici quotati sono un'aggiunta da eliminare dal raccordo.
Dollar quote/E-string, kwargs inutilizzati, `jc_kwargs` e input del chiamante
vanno confrontati con il legacy nel livello competente, senza estensioni.
R0 conserva la fotografia precedente; non è l'autorità per riaprire decisioni.

Per un impedimento concreto mostrare richiesta, algoritmo legacy, risultato dei
due percorsi e ragione per cui il port fedele non può procedere. Non anticipare
un'alternativa senza accordo e non usare questa eccezione per riproporre estensioni.

## Stato alla stesura

- [x] Confronto misurato e fonti disponibili: rapporto 78.
- [x] Piano e separazione tra ripristino e miglioramenti.
- [x] R0: contratti e test fissati nel rapporto 80, decisioni aperte esplicite.
- [x] Decisione architetturale: stessa delega legacy agli adapter, preparazione
  di SQL/kwargs separata dall'esecuzione; nessuna implementazione in questo passo.
- [x] Alias delle sottoquery secondo il legacy, separati dai mangler dei parametri;
  raccordo e verifiche ancora da implementare nella fase sottoquery.
- [x] R1: nucleo legacy ripristinato sulla SELECT fisica, rapporto 81.
- [x] R2: proiezioni legacy, parametri simbolici locali e contratti al confine
  dell’adapter, rapporto 82. Preparazione finale R3; riferimenti relazionali R5.
- [x] R3: preparazione legacy negli adapter, con adattamento psycopg 3
  documentato e verificato, rapporto 83.
- [x] R4: eseguire verifica integrata, benchmark e profili (rapporto 84).
- [x] R4: rimuovere i residui dello scanner dal renderer (rapporto 85).
- [x] R4: binding discusso; ClientCursor ritirato. Parametro tra apici escluso come errore d’uso (piano 86).
- [ ] R4: chiudere l’accettazione prima di R5.
- [x] M2/M3: scelto il comportamento legacy, nessun miglioramento introdotto.
- [x] Regola per tutte le aggiunte non concordate: esclusione dal raccordo,
  riferimento legacy, domande solo per impedimenti concreti.
- [ ] R5: raccordo delle famiglie successive al nuovo albero.

Le evidenze R0 restano storiche e immutate. Le nuove verifiche, i limiti e le
misure di R1 sono nel rapporto 81, R2 nel rapporto 82 e R3 nel rapporto 83;
non certificano le fasi ancora aperte.
