# Specifica di un compiler SQL nuovo con sintassi Genro legacy

Versione 0.1 — 29 settembre 2026 — specifica ricavata dal codice, da validare
con il corpus differenziale prima di dichiarare compatibilità completa.

**Ruolo nel progetto:** dopo la definizione degli obiettivi di lungo termine,
questa specifica descrive il contratto del frontend/adattatore legacy, non
impone tutti i comportamenti storici all'API nativa. La
[proposta architetturale](../genro-sql-target-architecture.md) comprende modello
da database e applicazioni legacy, sintassi moderna, lettura e scrittura con
priorità PostgreSQL. Le anomalie restano decisioni del profilo di compatibilità.

**Eccezione già decisa:** `aggregateRows` viene eliminato anche dal bridge.
Le descrizioni del vecchio raggruppamento Python sono documentazione storica
per migrare gli usi, non requisiti di emulazione. Prevalgono CAR-10 e CAR-11
sui requisiti generali di equivalenza per i casi che dipendono da tale meccanismo.

Baseline immutabile: `genropy/genropy` commit
`e12f2ce54245e57e48371ae0f47e928e0d55b960`.
Il presente documento descrive quella baseline, non ogni branch sperimentale.
`compiler_next` coincide ancora con `compiler` secondo la normalizzazione del
test upstream. Non è necessario riprodurne l'implementazione per sostituirlo.

Documenti complementari:

- [Casi di conformità e dataset di riferimento](compatibility-cases.md).
- [Analisi di codice e conversazioni](../legacy-sql-compiler-analysis.md).
- [Inventario precedente](../../roadmap/02_legacy_compiler_query.md), utile come
  materiale storico: in caso di divergenza fa fede la baseline qui indicata.

## 1. Obiettivo, significato di equivalenza e perimetro

**OBJ-01.** Il nuovo compiler accetta le query Genro esistenti senza obbligare
chi le scrive a cambiare `$colonna`, percorsi `@relazione`, formule, parametri,
macro e opzioni documentati di seguito.

**OBJ-02.** Equivalenza significa stessi valori, NULL, molteplicità delle righe,
nomi delle colonne, ordinamento quando richiesto, filtri e parametri. Include
il contratto dei metadati consumati da selection/record. Non richiede stessi
spazi, parentesi ridondanti, numeri degli alias SQL interni o piano esecutivo.

**OBJ-03.** Senza ORDER BY l'ordine delle righe non è un requisito di equivalenza.
Con chiavi di ordinamento non univoche non è definito l'ordine fra pari merito.
I confronti devono conservare i duplicati: confrontare insiemi sarebbe errato.

**OBJ-04.** La forma SQL equivalente è valida soltanto se conserva anche
cardinalità, semantica dei NULL, parametri, lock e comportamento del dialetto.
Una trasformazione LEFT JOIN → INNER JOIN non è una semplice normalizzazione.

**OBJ-05.** Il perimetro principale comprende SELECT e lettura record. INSERT,
UPDATE, DELETE, trigger, transazioni, migrazioni e salvataggio dei record-cluster
restano fuori dal compiler; i contratti di confine sono comunque esplicitati.

**OBJ-06.** La grammatica è ibrida: SQL del dialetto ospite più riferimenti e
costrutti Genro. Un elenco finito di funzioni SQL non descrive tutto il legacy.
Il compiler nuovo deve conservare un percorso per espressioni SQL del dialetto.

Legenda dei requisiti:

| Stato | Interpretazione |
|---|---|
| **L** | Comportamento ricavato dall'implementazione legacy; è il valore predefinito delle sezioni descrittive. |
| **A** | Anomalia, limite o comportamento accidentale. Va caratterizzato; non è automaticamente una regola da perpetuare. |
| **N** | Proposta progettuale per il compiler nuovo; non descrive una funzionalità legacy. |
| **F** | Estensione futura, esclusa dal traguardo di equivalenza. |

Gli ID permettono di collegare implementazione, test e decisioni. Un caso A
richiede una scelta registrata: emulazione, errore esplicito o correzione con
migrazione. Il documento non assume che tali scelte siano già approvate.

## 2. API di ingresso e valori predefiniti

### 2.1 Query pubblica

**API-01.** Punto di ingresso equivalente a `db.table('pkg.table').query(...)`.
`db.query(table=..., ...)` delega alla tabella. Il nome logico della tabella
viene risolto sul modello; non è un frammento FROM arbitrario.

| Argomento | Default pubblico / semantica |
|---|---|
| `columns` | `None`/vuoto diventa `*` in `SqlQuery`. |
| `where` | Nessun filtro esplicito; restano i filtri impliciti. |
| `order_by` | Se assente, può intervenire l'ordinamento di tabella. |
| `distinct` | Assente/falso: nessuna richiesta esplicita, ma può essere aggiunto automaticamente. |
| `limit`, `offset` | Assenti; applicazione demandata all'adapter. |
| `group_by`, `having` | Assenti; `group_by='*'` ha significato speciale. |
| `for_update` | `False`; può essere anche una modalità testuale del lock. |
| `relationDict` | Mappa opzionale simbolo → percorso. |
| `sqlparams` | Binding nominali; gli argomenti aggiuntivi sono uniti a questa mappa. |
| `bagFields` | `False` in `SqlQuery`; passa anche attraverso gli extra della tabella. |
| `joinConditions` | Condizioni aggiuntive di join. |
| `sqlContextName` | Contesto propagato alle selezioni/relazioni, non una clausola SQL. |
| `excludeLogicalDeleted` | `True`; supporta anche `False` e `'mark'`. |
| `excludeDraft` | `True`. |
| `ignorePartition` | `False`. |
| `subtable` | Assente; possibili default di contesto e modello. |
| `addPkeyColumn` | `True`, effettivo soltanto se la tabella ha una pkey. |
| `ignoreTableOrderBy` | `False`. |
| `locale` | Facoltativo; attenzione ai punti che leggono invece `db.locale`. |
| `_storename` | Store; può essere ereditato dal package e dall'ambiente. |
| `checkPermissions` | Contesto per i consumatori dei risultati; non applica da solo filtri SQL nel compiler. |
| `aliasPrefix` | Default effettivo `'t'`. |
| `mode` | Accettato dal wrapper tabella; non determina una diversa compilazione in questo percorso. |

**API-02.** Gli extra della query confluiscono nei binding e prevalgono sui valori
omonimi di `sqlparams`. Le opzioni riservate non diventano automaticamente bind.

**API-03.** La compilazione è lazy e memorizzata nella singola `SqlQuery`.
`sqltext` può produrre effetti sui parametri generati anche senza eseguire SQL.
Un nuovo servizio puro può avere un'altra struttura interna, ma il wrapper deve
conservare il contratto osservabile.

**API-04.** `for_update` abilita anche `bagFields` nel wrapper `SqlQuery`.

**API-05.** La chiamata interna `compiledQuery(columns='')` non applica lo stesso
default del wrapper pubblico: non va usata come prova del comportamento di
`table.query(columns=None)`.

**API-06.** `setJoinCondition(...)`, `queryCompile(...)`, `sqlWhereFromBag(...)`,
`whereFromDict(...)` e il percorso record costituiscono ulteriori ingressi
compatibili descritti nelle rispettive sezioni.

**API-07.** `db.queryCompile(...)` restituisce soltanto testo SQL, costruendo
una query attraverso l'API della tabella. Gli extra vengono poi memorizzati
nell'ambiente con nomi isolati e i relativi placeholder riscritti in `:env_*`.
Non è la stessa API di `query(...).compiled`, che mantiene anche metadati e
parametri. Il nuovo wrapper deve conservare i parametri della query annidata
anche quando il consumatore storico chiede soltanto SQL.

### 2.2 Contratto di uscita

**OUT-01.** Il risultato di compilazione deve esporre, direttamente o tramite
adattatore, SQL e binding; nomi e ordine delle colonne; dipendenze dal modello
e dall'ambiente; metadati per gli elaboratori successivi.

| Campo legacy | Informazione da conservare |
|---|---|
| `maintable`, `maintable_as` | Identità SQL e alias della tabella principale. |
| `columns`, `joins`, `where`, `group_by`, `having`, `order_by` | Clausole finali o rappresentazione equivalente. |
| `distinct`, `limit`, `offset`, `for_update` | Modificatori della SELECT. |
| `relationDict` | Simboli e percorsi risolti; comprende normalmente `pkey`. |
| `aliasDict` | Associazione fra alias espliciti e corpi delle espressioni, usata dai risultati. |
| `explodingColumns` | Colonne interessate da navigazioni many. |
| `aggregateDict` | Descrittore storico del raggruppamento rimosso; non richiesto come contratto di uscita nuovo. |
| `pyColumns` | Campi e callback Python da elaborare dopo il fetch. |
| `evaluateBagColumns` | Coppie nome campo / espansione in colonne. |
| `encryptedColumns` | Nomi e modalità dei campi da decifrare. |
| `resultmap` | Struttura e metadati del record. |

**OUT-02.** `additional_joins` è un dettaglio di accumulo legacy: ciò che conta
è che i join effettivi e le loro dipendenze siano corretti. Non occorre mantenere
due liste nella nuova implementazione.

## 3. Lessico e struttura delle espressioni

### 3.1 Notazione di riferimento

Questa grammatica descrive i costrutti Genro principali; `sql_fragment` è un
frammento valido per il dialetto, non un non-terminale completamente definito qui.

```ebnf
local_field      = "$", name ;
relation_hop     = "@", name ;
relation_field   = relation_hop, { ".", relation_hop }, ".", name ;
bind             = ":", name ;
outer_field      = "#THIS.", model_path ;
projection       = sql_fragment, [ " AS ", output_alias ] ;
projection_list  = projection, { ",", projection } ;
wildcard         = "*" | "*", expansion_spec ;
```

**LEX-01.** `$name` indica una colonna logica fisica o virtuale della tabella
corrente. Non è un nome fisico SQL né un bind.

**LEX-02.** `@customer_id.name` attraversa una relazione; più salti sono ammessi:
`@invoice_id.@customer_id.name`. La direzione e la cardinalità dipendono dal
modello, non dal nome o dalla posizione del token.

**LEX-03.** Una foglia può essere una colonna virtuale. Un segmento intermedio
può essere un alias di tabella, espanso nel percorso definito dal modello.

**LEX-04.** `:name` indica normalmente un parametro. Il prefisso `env_` e i
parametri che contengono riferimenti a campi hanno regole specifiche (§6).

**LEX-05.** La baseline riconosce `$` con `\w+` e le relazioni con una classe
lessicale più larga che comprende `.`, `@`, `:`. Questa permissività non prova
che ogni combinazione sia risolvibile dal modello. Non inventare una sintassi
speciale per `:` nei percorsi senza un caso reale verificato.

**LEX-06.** Un identificatore senza `$` o `@` resta normalmente SQL opaco.
`columns='name'` non equivale contrattualmente a `columns='$name'`.
Helper come `columnsFromString` possono aggiungere `$` prima del compiler.

**LEX-07.** Comma nella lista SELECT separa elementi soltanto al livello esterno:
funzioni, sottoespressioni, array e stringhe possono contenere virgole.
Il legacy usa uno splitter consapevole di parentesi tonde, quadre e apici.

**LEX-08.** Vanno distinti `*` di espansione iniziale, moltiplicazione e `COUNT(*)`.
Soltanto una proiezione il cui testo inizia con `*` segue l'espansione Genro.

**LEX-09.** Sono ammessi SQL ordinario, funzioni del dialetto, CASE, cast,
aritmetica, predicati, sottoquery SQL testuali, finestre e `FILTER (WHERE ...)`.
Accettare il frammento non rende la funzione portabile su ogni database.

**LEX-10 — A.** Le sostituzioni regex legacy non costituiscono un lexer SQL
completo: apici, commenti, dollar quoting PostgreSQL, cast `::`, escape e alias
contenenti `AS` richiedono caratterizzazione. Il nuovo lexer deve avere test
espliciti per ciascuna forma; non assumere equivalenza automatica.

**LEX-11 — N.** Separare token SQL opachi dai riferimenti Genro, conservando
posizione nel testo, ambito e origine. Non sostituire riferimenti dentro stringhe
o commenti nel nuovo profilo regolare. Eventuali dipendenze da tale comportamento
legacy devono essere isolate come anomalie di compatibilità.

## 4. Proiezioni, wildcard e alias

**SEL-01.** `*` espande le colonne fisiche nell'ordine del modello più le colonne
virtuali statiche. Le virtuali non statiche richiedono richiesta esplicita.

**SEL-02.** Le colonne fisiche `dtype='X'` sono escluse dallo star principale
quando `bagFields=False`. Una richiesta esplicita della colonna rimane possibile.

**SEL-03.** `*@relation` e `*@relation.@other` espandono i campi non-relazione
della tabella raggiunta. Non sono JOIN autonomi: generano riferimenti da risolvere.

**SEL-04.** `*@relation.prefix` seleziona le chiavi della relazione che iniziano
con quel prefisso. Questo ramo non applica lo stesso filtro `bagFields` di
`starColumns` della tabella principale: verificare separatamente i campi X.

**SEL-05 — A.** `*prefix` sulla tabella principale è documentato come filtro,
ma il ramo effettivo restituisce `starColumns(bagFields)` senza usare il prefisso.
La nuova implementazione deve registrare esplicitamente se corregge il caso.

**SEL-06.** `*virtual_name`, quando il nome identifica una virtuale, usa la sua
`sql_formula` come specifica di espansione. Non equivale a selezionare quella
formula come scalare.

**SEL-07.** `*@relation.(key,a,b)` espande la lista esplicita e genera un
`aggregateDict`: il primo campo è la chiave del sottoinsieme strutturato;
ogni campo conserva gruppo di destinazione, nome interno e colonna pivot.
Questa descrizione è storica: gli usi che richiedono ricomposizione delle righe
devono migrare a raccolte/proiezioni strutturate esplicite, senza aggregateRows.

**SEL-08.** Per `$name` semplice, l'alias implicito è `name`. Per un percorso o
un'espressione, `colToAs` sostituisce ogni carattere non-word con `_`; se il
risultato inizia con una cifra, aggiunge `_` davanti.

**SEL-09.** Esempi: `@customer_id.name` → `_customer_id_name`;
`@invoice_id.@customer_id.name` → `_invoice_id__customer_id_name`.
Questi alias sono nomi pubblici dei risultati e richiedono compatibilità.

**SEL-10.** `expression AS alias` prevale sul nome implicito. Il corpo viene
registrato in `aliasDict`; il renderer applica le regole di quoting del dialetto.

**SEL-11 — A.** La normalizzazione legacy converte esattamente `' as '` in
`' AS '`, elimina newline e comprime parzialmente spazi. Non è un parser
case-insensitive generale di AS. CAST e AS interni possono interferire con lo
split sul primo `' AS '`: includerli nel corpus, non prescrivere il bug.

**SEL-12 — A.** Proiezioni testualmente duplicate vengono eliminate; alias
duplicati collidono in una mappa ordinata e l'ultimo corpo prevale. Non si può
sostituire questo comportamento con un errore senza una decisione esplicita.

**SEL-13.** Il compiler aggiunge la pkey con alias `pkey` nelle query non
aggregate se `addPkeyColumn=True` e il modello ha una pkey. Il campo originale
può quindi comparire anche con il proprio nome.

**SEL-14.** Il simbolo `$pkey` è normalmente mappato alla vera chiave primaria
attraverso `relationDict`; non implica una colonna fisica chiamata `pkey`.
Una mappa già fornita può definire quel simbolo.

**SEL-15 — A.** La decisione iniziale di aggiungere pkey usa `distinct` e
`group_by`, prima del riconoscimento testuale di SUM/COUNT nelle proiezioni.
Non inferire che tutte le query con funzioni aggregate sopprimano correttamente
la pkey. `group_by='*'` è il marcatore legacy per aggregati senza chiavi di gruppo.

## 5. Risoluzione sul modello e join

### 5.1 Contratto del modello

**MOD-01.** Risolvere un riferimento richiede tabella logica, nome fisico completo,
mapper colonne → nomi SQL, dtype e metadati delle colonne, pkey, virtuali,
alias di tabella e relazioni in entrambe le direzioni.

**MOD-02.** Ogni relazione deve esporre lato one e lato many con i rispettivi
campi, direzione corrente, `one_one`, eventuali componenti composite,
condizioni, natura virtuale e politica tenant.

**MOD-03.** Devono essere disponibili virtuali statiche, dinamiche, locali e
varianti di query. Il compiler non deve dipendere dal formato di dichiarazione
schema: un adapter del modello può leggere sia source legacy sia nuovo builder.

**MOD-04.** Servono inoltre politiche di partizione, subtable, cancellazione
logica, draft, ordine di tabella, ambiente, preferenze e callback di formule.
Un catalogo fisico delle migrazioni non soddisfa da solo questo contratto.

**MOD-05 — N.** Rendere espliciti versione del modello e contesto di risoluzione.
Le personalizzazioni e le grammatiche in cascata devono produrre lo stesso
contratto semantico, senza imporre un particolare `ConfigHandler` al compiler.

**MOD-06 — Decisione acquisita.** Ogni colonna ha un'identità comune alla
definizione tecnica/semantica e alle informazioni d'interfaccia. Queste ultime
sono dichiarabili nella colonna o in un descrittore parallelo collegato, con
accesso unificato ai metadati risolti. Nessuna duplicazione indipendente di tipo,
formula o vincoli. Vedere il contratto di composizione e UI nella
[proposta architetturale, §4.4](../genro-sql-target-architecture.md).

**MOD-07 — Decisione acquisita.** La mappatura fisica supporta prefissi delle
tabelle derivati dallo schema logico, distinti dallo schema SQL. Nel bridge
preservare `sqlprefix` di package (True/nome package, False/nessuno, stringa
personalizzata), `sqlname` esplicito e riferimento SQL della maintable.
Compiler, scritture e migratore consumano la stessa mappa risolta, senza
dedurre i nomi dalla sintassi logica del percorso.

### 5.2 Navigazione

**JOIN-01.** Una colonna fisica si risolve in alias tabella + nome SQL adattato.
Un errore di risoluzione non deve trasformarla silenziosamente in SQL opaco.

**JOIN-02.** In direzione O si raggiunge il lato one dal many. In direzione M si
raggiunge il many dal one. M è potenzialmente esplosiva salvo `one_one=True`.

**JOIN-03.** Le navigazioni implicite di questa baseline generano LEFT JOIN.
La molteplicità non si corregge convertendole automaticamente in INNER JOIN.

**JOIN-04.** Il medesimo percorso dal medesimo contesto riusa il join.
Due relazioni diverse verso la stessa tabella, oppure lo stesso target da
percorsi diversi, devono poter avere alias indipendenti.

**JOIN-05.** Gli alias interni hanno prefisso di default `t`, iniziando da `t0`.
`aliasPrefix` personalizza il prefisso. Il nuovo allocatore deve soprattutto
garantire assenza di collisioni fra query e sottoquery correlate.

**JOIN-06.** Un aliasTable espande il percorso dichiarato senza introdurre un
join aggiuntivo distinto dalla navigazione reale.

**JOIN-07.** Il nome fisico della tabella target rispetta il tenant e l'eventuale
`ignore_tenant` della relazione.

**JOIN-08.** Join semplice: uguaglianza fra colonna sorgente e colonna target.
Join composito: congiunzione delle uguaglianze delle componenti, nel loro ordine.

**JOIN-09 — A/N.** Il legacy richiede una colonna composta anche sul target,
ma usa `zip` sulle componenti. Nel nuovo modello validare anche uguale arità e
tipi compatibili; caratterizzare l'eventuale accettazione di lunghezze diverse.

**JOIN-10.** Precedenza delle forme ON nella baseline: `join_on` sovrascrive
`cnd`; poi `cnd`, `between`, `case_insensitive=='Y'`, uguaglianze fisiche o
composite, infine collegamento virtuale tramite espressione sorgente.

**JOIN-11.** `cnd`/`join_on` sono condizioni complete alternative alla condizione
standard, non filtri che vengono sempre aggiunti alla FK. Sono risolti anche
eventuali campi e relazioni referenziati nella condizione.

**JOIN-12.** In un percorso annidato i riferimenti della condizione devono essere
interpretati rispetto al contesto corretto della navigazione. Il legacy qualifica
testualmente i token con il percorso padre; il nuovo compiler può usare scope.

**JOIN-13.** Una relazione virtuale legacy può partire da una colonna virtuale:
la sua espressione deve comparire nella condizione, non un nome di colonna fisica
inesistente. Non confondere questa funzionalità con il futuro `virtualRelation`.

**JOIN-14.** La modalità case-insensitive intende confrontare i due lati con
LOWER. Il ramo presenta un possibile nome target non inizializzato: è un caso A
da provare su fixture reale prima di fissare la compatibilità del difetto.

### 5.3 Condizioni aggiuntive per query

**JOIN-15.** Un elemento di `joinConditions` contiene `condition`, `params` e
`one_one`. Si può registrare per nome relazione oppure per coppia target/from
con punti convertiti in underscore.

**JOIN-16.** Il lookup attuale usa la chiave relazione quando fornita; non
effettua automaticamente un secondo lookup sulla coppia se quella manca.
Le due forme devono essere collaudate nei rispettivi punti di chiamata.

**JOIN-17.** `$tbl` nella condizione aggiuntiva rappresenta l'alias del target.
La condizione è aggiunta con AND all'ON, e i suoi parametri entrano nella mappa
dei binding. Supporta anche parametri che rappresentano campi (§6).

**JOIN-18.** `one_one=True` su una condizione aggiuntiva sopprime il tracciamento
many nel percorso applicabile. Non crea un vincolo di unicità nel database.

**JOIN-19.** La chiave `*_*` identifica la condizione sulla tabella principale:
finisce nel WHERE anche se il chiamante non ha fornito un WHERE iniziale.
I suoi `$campo` e `@relazione.campo` devono essere risolti.

**JOIN-20.** Il wrapper tabella accetta extra `jc_*` con valore testuale
`relazione:condizione`; un `*` finale nel nome relazione dichiara one_one.
È un adattamento di ingresso da preservare o migrare esplicitamente, non una
nuova produzione del parser SQL. La baseline lo analizza nel wrapper tabella.

## 6. Parametri, binding e ambiente

**PAR-01.** I valori ordinari sono trasportati separatamente dal SQL.
Stringhe, numeri, Decimal, booleani, date, timestamp, bytes e NULL vanno
preservati nei rispettivi tipi fino all'adapter/driver.

**PAR-02.** Il medesimo `:name` può comparire più volte. Non confondere nomi
con prefisso comune (`:id` e `:id2`).

**PAR-03.** Liste, tuple e set vengono espansi dagli adapter che usano
`adaptTupleListSet` in placeholder individuali. L'ordine dei set non è stabile;
non è una proprietà da usare per nomi pubblici o snapshot.

**PAR-04.** La forma usuale per una collezione è `$id IN :ids`; il renderer
inserisce le parentesi necessarie. Non aggiungerle due volte.

**PAR-05 — A.** Collezioni vuote, `IN NULL`, tuple contenenti NULL e `NOT IN`
hanno semantiche diverse e possono avere adattamenti specifici del driver.
Non dedurre una regola globale dal solo base adapter, che genera anche `()`.
Vanno caratterizzati per ogni adapter incluso nella release.

**PAR-06.** Nel WHERE e nelle condizioni aggiuntive di join, un valore stringa
che inizia con `$` o `@` ed è riconosciuto come campo viene inserito come
riferimento, anziché inviato come valore. Esempio: `where='$a=:other',
other='$b'` confronta due colonne.

**PAR-07.** Per le stringhe letterali che iniziano con tali caratteri il legacy
ammette escape `\$` e `\@`; l'esecutore rimuove la barra prima del binding.
Il percorso di embedding tratta anche bytes decodificabili.

**PAR-08.** L'escape `\:` nel testo SQL viene protetto durante l'adattamento dei
placeholder e ripristinato dopo. Cast e stringhe contenenti due punti vanno
coperti con test del dialetto, senza sostituzioni indiscriminate.

**PAR-09.** `:env_name` viene risolto da `currentEnv['name']` all'esecuzione.
I parametri espliciti prevalgono sui corrispondenti valori d'ambiente.
`env_workdate` ha fallback a `db.workdate`; `env_storename` partecipa alla
selezione dello store.

**PAR-10.** I nomi creati da formule `var_*`, periodi e sottoquery devono restare
isolati fra istanze della stessa formula. Il legacy usa anche identità Python
non deterministiche; il nuovo compiler può usare un allocatore deterministico
purché preservi valori e separazione degli scope.

**PAR-11.** I parametri non usati possono rimanere nella mappa legacy, insieme
allo stato delle macro. La nuova API può separarli, ma l'adattatore non deve
perdere binding necessari o inviare al driver metadati come se fossero valori.

**PAR-12 — N/A.** Definire errore esplicito per binding assente. Il legacy passa
attraverso un `defaultdict(None)` e diversi driver: l'effetto preciso non è un
contratto uniforme dimostrato. Registrare i casi in cui il nuovo errore differisce.

## 7. Colonne virtuali e sottoquery

**VIR-01.** La ricerca della colonna fisica precede il fallback alle virtuali.
Una virtuale non definita deve dare un errore di campo mancante nella query.

**VIR-02.** `aliasColumn(relation_path=...)` risolve ricorsivamente il percorso
nel contesto della tabella che possiede l'alias. Un alias di colonna non è un AS.

**VIR-03.** `sql_formula` è un'espressione SQL estesa con riferimenti Genro.
Può usare altre virtuali, relazioni, funzioni e sottoquery nominate.
La formula espansa è racchiusa in parentesi.

**VIR-04.** `sql_formula=True` richiede la callback
`sql_formula_<nome>(attributes)` della tabella che possiede la formula.
La compilazione deve ricevere il risultato del provider prima della risoluzione.

**VIR-05.** Una formula con `select=dict(...)` genera una sottoquery scalare;
`exists=dict(...)` genera un predicato EXISTS. Se esiste una formula esplicita,
i placeholder `#nome` sono alimentati dagli attributi `select_nome`.

**VIR-06.** Ogni select contiene almeno `table` e `where` nel percorso attuale,
più opzioni query come `columns`, `order_by`, `limit`, `group_by`, `having` e bind.
Non assumere che omettere WHERE venga accettato in tutte le forme.

**VIR-07.** La definizione di un select nominato può essere una stringa che
identifica un metodo `subquery_<nome>()`. Nella baseline il metodo è cercato
sulla tabella principale del compiler: distinguere questo caso dal provider
`sql_formula_*` della tabella raggiunta.

**VIR-08.** `cast` della definizione select applica un CAST alla sottoquery
racchiusa in parentesi. Tipo SQL e sintassi del cast dipendono dal dialetto.

**VIR-09.** Default interni dei select virtuali:
`ignorePartition=True`, `excludeDraft=False`, `excludeLogicalDeleted=False`,
`subtable='*'`. Inoltre vengono richiesti `addPkeyColumn=False` e
`ignoreTableOrderBy=True`. Sono diversi dai default della query pubblica.

**VIR-10.** `#THIS.field` nel WHERE della sottoquery identifica un campo della
riga esterna, relativo alla tabella proprietaria della formula e al suo alias
nel percorso corrente. Sono possibili anche percorsi di relazione.

**VIR-11.** Le formule possono contenere più sottoquery nominate, annidate e
riutilizzate. Isolare alias e parametri senza cambiare la correlazione.
Una sottoquery scalare con più righe conserva la semantica/errore del database:
non introdurre implicitamente `LIMIT 1`.

**VIR-12.** `var_name=value` su una formula sostituisce `:name` con un binding
ambientale isolato. È un valore del modello/variante, non automaticamente
un'espressione che legge la riga esterna.

**VIR-13.** Se una virtuale richiesta non è dichiarata, `sqlparams[nome]` può
contenere una definizione di variante: `field` identifica la virtuale base e
gli altri attributi la personalizzano. Le virtuali dichiarate hanno precedenza.
Questa struttura non è un bind da inviare direttamente al driver.

**VIR-14.** `py_method` produce NULL nel SQL e registra un elaboratore Python.
Il wrapper valuta il metodo per riga dopo il fetch. Il compiler non deve fingere
che una pyColumn sia una funzione SQL utilizzabile nei predicati con lo stesso
risultato Python. Alias e navigazioni di pyColumn richiedono caratterizzazione.

**VIR-15.** Le virtuali senza `relation_path`, formula, select, exists o py_method
validi producono un errore distinto dal campo inesistente.

**VIR-16.** `compositeColumn` è una virtuale con componenti fisiche e formula
generata dal modello. Per il join servono le componenti, non il confronto della
sola rappresentazione testuale del composto.

**VIR-17.** `bagItemColumn`, `joinColumn`, `toolColumn` e altre scorciatoie del
modello devono essere abbassate a descrittori/formule riconosciuti. La loro
costruzione appartiene al modello, non necessariamente al parser del compiler.

**VIR-18.** `subQueryColumn(mode='json')` nella baseline usa aggregazione jsonb
di record; `mode='xml'` aggrega XML e lo converte in testo. Queste forme sono
generate dal modello e sono sensibili al dialetto. Preservare tipo e valori,
inclusa l'assenza di righe, senza sostituire NULL con collezioni vuote arbitrariamente.

**VIR-19 — N.** Rilevare cicli fra formule e alias con un errore che mostri
il percorso di dipendenza. Non è sufficiente affidarsi alla ricorsione Python.

## 8. Macro e contesti di espansione

Non tutte le macro sono valide ovunque. La seguente matrice è quella dei punti
di espansione del compiler; non include macro già elaborate da un produttore
di formule prima di arrivarvi.

| Macro | SELECT diretto | WHERE query | ORDER BY | Formula virtuale | ON dichiarato |
|---|---|---|---|---|---|
| `#IN_RANGE` | No | Sì | No | Sì | Sì, ramo `cnd` |
| `#PERIOD` | No | Sì | No | No | No |
| `#BAG`, `#BAGCOLS` | Sì | No | No | Nessuna espansione dedicata | No |
| `#ENV`, `#PREF` | No | No | No | Sì | No |
| `#THIS` | No | Solo WHERE del select virtuale correlato | No | Sì | Nessuna espansione generale |
| `#TSQUERY`, `#VECQUERY` | No | Sì, adapter pertinente | No | Nessuna espansione diretta dedicata | No |
| `#TSRANK`, `#VECRANK` | Sì | No | Sì | Sì | No |
| `#TSHEADLINE` | Sì | No | No | Sì | No |

**MAC-01.** GROUP BY e HAVING non hanno un passaggio generale di espansione
macro; possono tuttavia riferirsi a una virtuale che ne contiene. Analogamente
WHERE record non ha automaticamente la pipeline macro di WHERE query.

**MAC-02.** L'ordine di espansione è significativo: le macro di ricerca nel
WHERE preparano il contesto usato dalle macro di ranking nelle colonne e
nell'ordinamento.

### 8.1 Intervalli e periodi

**MAC-03.** `#IN_RANGE(value, low, high)` ammette gli operandi riconosciuti dalla
regex legacy: riferimenti a campi/percorso/parametri o token semplici, non
un generico albero di espressioni con funzioni annidate.

| Low | High | Espansione logica |
|---|---|---|
| NULL | NULL | Vero, anche se value è NULL. |
| NULL | Presente | `value <= high`. |
| Presente | NULL | `value >= low`. |
| Presente | Presente | `value >= low AND value <= high`. |

**MAC-04.** Quando value è NULL e un estremo è presente, restano le regole SQL
a tre valori. Non sostituire UNKNOWN con TRUE.

**MAC-05.** Il vecchio attributo di relazione `between='value;low;high'` usa
invece l'estremo superiore esclusivo `<`. Non unificare silenziosamente le due
forme in un compiler che dichiara equivalenza.

**MAC-06.** `#PERIOD(field, :period)` o `#PERIOD(field, period)` interpreta il
valore del parametro con `decodeDatePeriod`, `db.workdate` e `db.locale`.
Emette uguaglianza per un giorno, BETWEEN inclusivo per un intervallo,
`>=` o `<=` per intervalli aperti, TRUE se non ci sono estremi.

**MAC-07.** I binding generati sono `<period>_from` e `<period>_to` quando
necessari. La sovrapposizione con binding del chiamante va caratterizzata.

**MAC-08.** Il linguaggio dei periodi è una dipendenza a sé: date ISO e locali,
anno, mese, trimestre, nomi di giorni/mesi, oggi/ieri/domani, settimana e mese
relativi, offset, intervalli con `;` e parole localizzate from/to/no period.
Per compatibilità conviene conservare il decoder o importarne il corpus
completo; non sostituirlo con un parser ISO dichiarandolo equivalente.

### 8.2 Bag, ambiente e preferenze

**MAC-09.** `#BAG($field) [AS alias]` seleziona il valore e registra conversione
in Bag dopo il fetch. L'alias determina quale campo elaborare.

**MAC-10.** `#BAGCOLS($field) [AS alias]` converte in Bag e aggiunge campi per le
foglie, con nome `<alias>_<leafpath>` e punti convertiti in underscore; il campo
originario viene impostato a None. È una trasformazione di risultato.

**MAC-11.** `#ENV(name[, other])` nelle formule cerca prima `name` nell'ambiente,
poi `other` come chiave d'ambiente; se non trovato, cerca `env_<name>()` sulla
tabella `other`, se specificata, oppure sulla tabella proprietaria.

**MAC-12 — A.** I valori d'ambiente sono inseriti come testo fra apici senza un
vero binding; il fallback finale è il testo `Not found <name>`, potenzialmente
SQL invalido. Nel compiler nuovo parametrizzare i valori e rendere esplicito
l'errore, registrando la differenza rispetto al comportamento accidentale.

**MAC-13.** `#PREF(path[, default])` legge la preferenza del package della
tabella proprietaria e ne inserisce la rappresentazione testuale nella formula.
La distinzione fra valore e frammento SQL deve essere resa esplicita nel nuovo
contratto dei provider.

### 8.3 Ricerca testuale PostgreSQL

**MAC-14.** `#TSQUERY[_code]($tsv, :text[, :language])`; gli argomenti possono
essere riferimenti ammessi `$`/`@` e, dove previsto, `:`. Il linguaggio di
default è `simple`; la macro usa `websearch_to_tsquery` e l'operatore `@@`.

**MAC-15.** Il canale omesso si chiama `current`; con `_code` si possono
mantenere ricerche distinte. Il contesto conserva vettore, testo e lingua.
Più dichiarazioni nello stesso canale richiedono un test della precedenza.

**MAC-16.** `#TSRANK[_code]` ammette forma senza argomenti o pesi/normalizzazione
nella forma prevista dalla regex. I default sono pesi `[0.1,0.2,0.4,1.0]` e
normalizzazione 8. Serve un canale TSQUERY compatibile.

**MAC-17 — A.** Il ramo dei pesi espliciti inserisce il gruppo regex direttamente
nel SQL. Non assumere che ogni forma documentata produca un ARRAY valido:
è un caso di collaudo PostgreSQL, distinto dai default.

**MAC-18.** `#TSHEADLINE[_code]($text[, 'config'])` usa lo stesso canale per
lingua/query e applica `ts_headline`; senza contesto restituisce stringa SQL vuota.
La configurazione predefinita usa `<mark>`, `</mark>`, limiti 20/5 parole,
99 frammenti e `<hr/>` come separatore.

### 8.4 Ricerca vettoriale PostgreSQL

**MAC-19.** `#VECQUERY[_code]($embedding, :target)` registra vettore e target;
come predicato emette soltanto `embedding IS NOT NULL`. Non applica da sola
una soglia di somiglianza.

**MAC-20.** `#VECRANK[_code]` restituisce `1 - distanza_coseno`, implementata
dal dialetto con `<=>` e cast del target a vector. Richiede il canale VECQUERY.

**MAC-21.** L'assenza del canale rank oggi può diventare KeyError; il nuovo
compiler può produrre una diagnostica specifica, senza inventare un punteggio.

### 8.5 Estendibilità

**MAC-22.** Il registry delle macro e la loro invocazione sono contratti diversi.
Una macro registrata non viene necessariamente espansa: il compiler chiama
gruppi nominati e fissi nei punti indicati dalla matrice.

**MAC-23.** Nel dispatcher, una registrazione di istanza prevale sul gestore
della classe adapter; un nome non conosciuto è lasciato invariato. Il compiler
nuovo deve definire separatamente fasi, contesti e precedenze delle estensioni.

### 8.6 Secondo percorso full-text nell'adapter psycopg2

**MAC-24.** `gnrpostgres.py` contiene anche `TsVectorCompiler`, invocato sul SQL
finale dall'adapter psycopg2. Riconosce forme con operandi espliciti:

```text
#TSQUERY(tsvector, :query[, :language])
#TSRANK(tsvector, :query[, :language][, [weights]][, normalization])
#TSHEADLINE(textfield, :query[, :language][, 'config'])
```

In questo passaggio i riferimenti possono essere già nomi SQL qualificati e
quotati. La forma non coincide con TSRANK/TSHEADLINE basati sul canale della
sezione precedente; l'assenza di pesi in questo ramo produce NULL nel relativo
argomento e il default headline usa MaxFragments=3. Non è un contratto comune
a tutti i driver PostgreSQL: i renderer postgres3/postgres8000 esaminati non
chiamano questo secondo trasformatore.

**MAC-25 — A.** Le due famiglie possono interferire: il primo dispatcher può
riconoscere soltanto una parte di una forma destinata al trasformatore finale.
Inoltre le macro rank espanse dopo la sostituzione dei campi possono
reintrodurre riferimenti `$`/`@` conservati nel contesto. Occorrono test end-to-end
per driver, sia in proiezione diretta sia attraverso formula virtuale. I test
unitari di `test_vecquery_macro.py` verificano il solo expander, non certificano
che il SQL finale sia eseguibile.

## 9. WHERE, GROUP BY, HAVING e ORDER BY

**CLA-01.** `$campo` e `@percorso` sono risolti in tutte e cinque le clausole
principali: SELECT, WHERE, GROUP BY, HAVING, ORDER BY.

**CLA-02.** WHERE e HAVING preservano operatori SQL, parentesi, AND/OR/NOT,
EXISTS, IN, LIKE, confronti e semantica dei NULL del dialetto.
Il compiler non converte automaticamente `= NULL` in `IS NULL` nel SQL opaco.

**CLA-03.** GROUP BY mantiene la lista espressa dal chiamante. Non raggruppare
automaticamente ogni colonna non aggregata: cambierebbe la query.

**CLA-04.** `group_by='*'` dichiara query aggregata senza emettere GROUP BY.
Serve anche a impedire pkey aggiunta e ordine predefinito della tabella.

**CLA-05.** HAVING è indipendente da WHERE. Non spostare predicati fra i due
senza una dimostrazione semantica.

**CLA-06.** ORDER BY accetta liste, espressioni, direzioni e costrutti del
dialetto, compresi alias SQL quando supportati. Nessuna garanzia che `$alias`
di proiezione sia una colonna del modello: `$` continua a indicare il modello.

**CLA-07.** Il default `table.attributes['order_by']` si applica se l'ordine
richiesto è falsy, `ignoreTableOrderBy=False` e la query non è inizialmente
aggregata secondo distinct/group_by.

**CLA-08.** LIMIT/OFFSET si applicano al risultato SQL, prima di eventuale
aggregazione Python nel vecchio sistema. Nel nuovo l'aggregazione Python è
rimossa; limiti della query esterna e limiti delle raccolte devono essere
dichiarati nei rispettivi scope, senza conservare la ricomposizione post-fetch.

**CLA-09 — A.** Nel base adapter i valori falsy non emettono la clausola:
`limit=0` intero non significa necessariamente zero righe; la stringa `'0'`
segue un altro ramo. Definire una scelta di compatibilità esplicita.

**CLA-10.** Le finestre SQL e FILTER sono espressioni del dialetto; devono
conservare PARTITION BY, ORDER BY e frame interni senza confonderli con quelli
della query esterna. Non inferire aggregazione della query da ogni funzione.

## 10. Filtri impliciti e contesto

**POL-01.** Il WHERE finale combina con AND: WHERE esplicito, condizioni di
ambiente, partizione, subtable, cancellazione logica, draft e condizione `*_*`.
Ogni contributo va raggruppato per preservarne AND/OR interni.

**POL-02.** Le condizioni d'ambiente sono cercate sotto il prefisso
`env_<pkg_table>_condition_`; sono frammenti di filtro, non semplici valori.

**POL-03.** La partizione viene fornita dal modello/tabella tramite
`getPartitionCondition(ignorePartition=...)`. Il compiler non può ricavarla
soltanto dal catalogo delle colonne.

Nella baseline: current_<path> truthy → uguaglianza; altrimenti allowed_<path>
truthy → campo NULL oppure IN nella lista; altrimenti eventuale percorso
`__allowed_partition IS TRUE`. Il provider sceglie la prima dichiarazione
partition_* e può non produrre una condizione. Liste vuote, current falsy e
dimensioni multiple vanno caratterizzati. È una policy logica, distinta dal
partizionamento fisico PostgreSQL e dalle autorizzazioni del database.

**POL-04.** Precedenza subtable: argomento esplicito truthy, contesto
`context_subtables` della tabella, default della tabella. `'*'` disabilita
l'applicazione delle condizioni subtable.

**POL-05.** Espressioni subtable combinano nomi con `&`, `|`, `!`; i nomi
vengono risolti a condizioni che possono aggiungere parametri. Il vecchio
algoritmo è testuale: nomi sovrapposti e precedenza sono casi A da caratterizzare.

Il modello legacy distingue subtable di tabella (condizione nominata più
virtuale booleana) e subtable di package (specializzazione con maintable,
sql_inherited e __subtable). La seconda non è una partizione fisica né una
view SQL. Importazione, default e scritture richiedono il contratto dedicato
nella [proposta architetturale, §5.2](../genro-sql-target-architecture.md).

**POL-06.** Se esiste `logicalDeletionField`, `excludeLogicalDeleted is True`
aggiunge `field IS NULL`. `False` include tutti; `'mark'` aggiunge `_isdeleted`
nelle query non aggregate/non-count invece di escludere le righe.

**POL-07.** `_isdeleted` contiene il valore del campo di cancellazione, non
necessariamente un booleano. Non cambiarne tipo implicitamente.

**POL-08.** Se esiste `draftField`, `excludeDraft is True` aggiunge
`field IS NOT TRUE`: include FALSE e NULL.

**POL-09.** Questi filtri riguardano la tabella della query corrente. Non
applicarli automaticamente a ogni tabella navigata se il legacy non lo fa.
Le sottoquery virtuali hanno default propri (§7).

**POL-10.** Con store `'*'` o lista testuale separata da virgole viene aggiunta
`'_STORENAME_' AS _dbstore_`. L'esecutore sostituisce il valore per connessione.
Distribuzione delle query e fusione dei risultati appartengono all'esecutore.

**POL-11 — N.** Ogni piano riutilizzabile deve dichiarare dipendenze da tenant,
store, locale, workdate, condizioni, varianti e modello. Vietato riutilizzare
un SQL che incorpora il contesto di un'altra richiesta.

## 11. Cardinalità, DISTINCT e count

**CAR-01.** Una relazione many può moltiplicare le righe anche se compare solo
nel filtro o nell'ordinamento. Il tracciamento non si limita alla SELECT.

**CAR-02.** Nel percorso non aggregato, la presenza di una navigazione many
può attivare DISTINCT automatico. Il risultato rimane una SELECT DISTINCT delle
proiezioni, non necessariamente una riga per pkey.

**CAR-03.** `distinct=True` forza DISTINCT. La baseline normalizza ogni valore
falsy a stringa vuota: `distinct=False` non è un interruttore affidabile per
disabilitare il DISTINCT automatico.

**CAR-04.** Una stringa truthy passata come distinct viene ridotta a DISTINCT;
non costituisce supporto pubblico a `DISTINCT ON (...)`.

**CAR-05.** Per DISTINCT automatico con ORDER BY, il legacy può aggiungere
colonne `__ord_col_N` per espressioni non presenti nella proiezione. Conservare
il contratto di risultato oppure adattarlo al confine, perché aggiungere colonne
può cambiare sia la deduplicazione sia ciò che vede il chiamante.

**CAR-06 — A.** Il rilevamento legacy di aggregati cerca testualmente SUM/COUNT;
non comprende in modo uniforme AVG/MIN/MAX, finestre e funzioni personalizzate.
Non usare questo limite come modello semantico della nuova implementazione.

**CAR-07.** `count()` avvia una compilazione specifica e rimuove ORDER BY:
con GROUP BY seleziona le chiavi di gruppo; con DISTINCT conserva le proiezioni;
altrimenti genera `count(*) AS gnr_row_count`.

**CAR-08.** Il wrapper count interpreta l'unica cella `gnr_row_count` come numero;
negli altri casi conta le righe restituite. Con store multipli somma i conteggi.
LIMIT/OFFSET non sono rimossi automaticamente dal percorso osservato.

**CAR-09 — A.** Il ramo commentato come count di pkey distinte su join esplosivi
non basta a garantire quel comportamento: il riconoscimento di COUNT modifica
prima lo stato aggregate. I test upstream esaminati su questo caso verificano
principalmente `n > 0`. Il corpus nuovo deve fissare conteggi esatti per combinazioni
di many, count, distinct, group_by e limiti.

**CAR-10 — Decisione acquisita.** Eliminare `_aggregateRows`/`aggregateRows`
e il raggruppamento automatico per pkey dopo il fetch, sia nel nucleo sia negli
adattatori legacy. Nessuna deduplica per valore o aggregazione implicita Python
deve correggere la molteplicità prodotta dai join. Una richiesta di attivare
il vecchio comportamento deve produrre una diagnostica di migrazione.

**CAR-11 — Decisione acquisita.** Migrare ogni uso dichiarando l'intenzione:
aggregato SQL sulla relazione, raccolta strutturata esplicita o risultato a righe
espanse. I risultati numericamente errati del legacy servono come regressioni
da evitare, non come oracle da emulare. La serializzazione Bag/JSON non deve
reintrodurre il meccanismo sotto un altro nome.

**CAR-12.** Il nuovo compiler non deve reinterpretare `SUM(@invoices.total)`
come aggregato correlato per relazione: nel legacy è SQL applicato al join.
La futura sintassi `@invoices.sum($total)` è distinta e non ambigua (§19).

## 12. Query Bag e filtri da dizionario

**BAG-01.** La query Bag è un secondo linguaggio di ingresso da mantenere se
si vuole compatibilità con l'editor delle query. Non è automaticamente accettata
come oggetto dal parametro testuale `where`: passa dal traduttore dedicato.

**BAG-02.** Ogni nodo condizione contiene valore e attributi `column`, `op`,
`jc`, `not`, facoltativamente `parname`, `value_caption`, `encrypted`.
Un valore Bag rappresenta un gruppo annidato.

**BAG-03.** `jc` è il connettivo fra condizioni, normalizzato in maiuscolo;
il primo contributo effettivo non ha connettivo iniziale. `not='not'` applica
negazione a condizione o gruppo. Un booleano True non è lo stesso valore legacy.

**BAG-04.** Le righe senza colonna o operatore vengono ignorate. Una colonna
indicata ma inesistente genera errore `not_existing_column`.

**BAG-05.** Il tipo viene dal modello. Valori testuali numerici e altri tipi
vengono convertiti tramite il catalogo dei tipi. Un errore di conversione deve
risultare distinguibile da un errore SQL e riportare campo e valore.

**BAG-06.** Un valore `'?name'` viene letto da sqlArgs. Quando il valore è None
e c'è `value_caption`, il legacy può prelevare e consumare il parametro con
quel nome. Non confondere questi meccanismi con il placeholder SQL `:name`.

**BAG-07.** `parname` esplicito o nome derivato dalla colonna determina il bind;
ripetizioni generano suffissi. Occorre evitare collisioni con i bind esistenti
nel nuovo allocatore, preservando i valori nel wrapper compatibile.

**BAG-08.** Per modalità cifratura Q il valore del filtro viene cifrato prima
del binding; sono trattate anche liste. È responsabilità del traduttore/provider,
non una riscrittura SQL da omettere.

### 12.1 Operatori del traduttore base

| Operatore | Semantica iniziale prima delle trasformazioni adapter |
|---|---|
| `equal` | Uguaglianza; se value è lista, diventa `in`. |
| `greater`, `greatereq`, `less`, `lesseq` | `>`, `>=`, `<`, `<=`. |
| `between` | Due valori separati da `;`, limiti inclusivi, binding `_from`/`_to`. |
| `isnull` | IS NULL. |
| `istrue`, `isfalse` | IS TRUE / IS FALSE. |
| `nullorempty` | IS NULL oppure stringa vuota; per L/N/M/R solo IS NULL. |
| `in` | Collezione; stringa suddivisa su virgole; None convertito a lista vuota. |
| `startswithchars` | LIKE con wildcard finale. |
| `startswith` | ILIKE con wildcard finale. |
| `contains` | ILIKE con wildcard iniziale e finale. |
| `wordstart` | Regex case-insensitive con inizio parola e escape parziale. |
| `regex` | Operatore regex case-insensitive del dialetto. |
| `fulltext` | TSQUERY costruita usando `tsvColumn` e `tsvLanguage` del modello. |

**BAG-09.** Gli operatori possono avere override adapter e callback custom.
`endswith`/`notcontains` compaiono in preparazioni testuali ma non hanno per
questo un gestore nel traduttore base. Non prometterli senza provider.

**BAG-10.** Per ricerche testuali su dtype non A/T la baseline può applicare
CAST a text. L'attributo `unaccent` modifica i template supportati dall'adapter.
Le wildcard contenute nel valore non sono universalmente escape automatici.

**BAG-11.** Per D/DH/DHZ, valori periodo possono cambiare l'operatore; i timestamp
sono filtrati tramite `date(column)` nel traduttore base. Per greater/greatereq
si usa l'estremo finale di un periodo; per less/lesseq quello iniziale.
L'equivalenza richiede test anche su timezone e confini del giorno.

**BAG-12.** `whereFromDict` interpreta suffissi del tipo `field_op` e
`field_not_op`, default equal, con colonne custom e dtype eventuale. I nomi di
campo contenenti underscore e suffissi uguali a operatori sono casi ambigui
da includere nel corpus.

**BAG-13 — N.** Il traduttore Bag e il parser testuale devono convergere sul
medesimo resolver semantico. Questo è essenziale anche per le future funzioni
sulle relazioni: il vecchio traduttore cerca una colonna prima di produrre SQL.

## 13. Lettura di record singoli

L'ingresso `SqlRecord` accetta `pkey`, `where`, `lazy`, `eager`, `relationDict`,
`sqlparams`, `ignoreMissing=False`, `ignoreDuplicate=False`, `bagFields=True`,
`for_update=False`, `joinConditions`, `sqlContextName`, `virtual_columns`,
`_storename`, `checkPermissions`, `aliasPrefix` ed extra di selezione.

**REC-01.** `compiledRecordQuery` è un ingresso distinto; seleziona le colonne
fisiche del record con alias strutturali, normalmente `t0_<nome>`.
Non basta una query ordinaria con LIMIT 1 per emularlo.

**REC-02.** `bagFields` ha default True nel percorso record. False esclude i
campi X dalla proiezione e dalla struttura interessata.

**REC-03.** `resultmap` contiene metadati per campi e relazioni, associazione
all'alias di risultato e modalità `DynItemOne`, `DynItemOneOne`, `DynItemMany`.

**REC-04.** Le relazioni registrate nel resultmap non implicano tutte un join
immediato. Le modalità lazy/eager e la successiva risoluzione sono responsabilità
condivisa con `SqlRecord` e i resolver; non attribuire alla sola SELECT il loro
intero comportamento.

**REC-05.** `virtual_columns` accetta lista o stringa separata da virgole;
vengono aggiunte le virtuali statiche e rimossi duplicati/prefissi `$`.
La baseline ignora virtuali sconosciute in questa lista, mentre una virtuale
sconosciuta richiesta nella query ordinaria dà errore.

**REC-06 — A.** `virtual_columns=False` viene normalizzato prima del gestore:
non è una garanzia di esclusione delle virtuali statiche.

**REC-07.** Una relazione O su colonna virtuale può richiedere selezione della
colonna virtuale sorgente e risoluzione di dipendenze nelle condizioni.

**REC-08.** Il WHERE record risolve campi e relazioni, ma non esegue tutta la
pipeline macro e filtri impliciti di `compiledQuery`. Non aggiungerli per
simmetria senza considerare l'API record che prepara l'ingresso.

**REC-09.** Lock e metadati di cifratura fanno parte del risultato. Errori
record inesistente/non univoco e creazione dei resolver restano nel wrapper.

**REC-10.** Precedenza per costruire il filtro record: WHERE esplicito truthy;
altrimenti pkey non None con `$pkey=:pkey`; altrimenti uguaglianze sui parametri
che corrispondono a colonne della tabella. Un WHERE vuoto al momento di eseguire
produce RecordSelectionError, non una SELECT indiscriminata del primo record.

**REC-11.** Le chiavi composte serializzate, nella forma riconosciuta dal
modello, vengono decomposte in parametri prima della compilazione record.
Gli extra sono uniti a sqlparams. Il filtro costruito automaticamente dal
wrapper usa nomi e alias testuali: mappature SQL personalizzate e aliasPrefix
non predefiniti richiedono test specifici.

**REC-12.** `ignoreMissing` e `ignoreDuplicate` regolano il trattamento delle
righe assenti/multiple nel wrapper. Il caso multiplo può tentare di scartare
duplicati logicamente cancellati prima di decidere: non sostituirlo con un
LIMIT 1 incondizionato nel compiler.

## 14. Dialetti e preparazione all'esecuzione

**DIA-01.** Separare identificatori, alias, tipi SQL, espressioni e parametri.
Schema, tabella e colonne devono usare il mapper/adattamento del dialetto.

**DIA-02.** Il renderer assembla SELECT, FROM, join, WHERE, GROUP BY, HAVING,
ORDER BY, paginazione e lock nell'ordine richiesto dal database.

**DIA-03.** PostgreSQL, SQLite, MySQL e MSSQL non sono equivalenti per funzioni,
JSON/XML, full-text, vector, regex, booleani, cast, concatenazione e lock.
Il supporto deve essere dichiarato per funzionalità e adapter, non per solo
nome generico «SQL».

**DIA-04.** Nel percorso SQLite osservato, ILIKE viene adattato a LIKE, `~*`
a REGEXP e alcuni confronti booleani vengono riscritti. Il lock FOR UPDATE è
omesso. Queste sono responsabilità dell'adapter, non del parser Genro.

**DIA-05.** Il base adapter rende un lock del tipo FOR UPDATE OF alias e può
aggiungere una modalità testuale. MySQL e altri adapter hanno override.
MSSQL ha una propria compilazione con TOP: non esportare quel SQL ad altri dialetti.

**DIA-06.** Lo stile nominale `:name` è la forma logica Genro; il driver può
richiedere una conversione successiva. Il SQL restituito dal compiler e quello
effettivamente eseguito non sono sempre identici.

**DIA-07 — N.** Per funzioni non supportate dal dialetto, distinguere errore di
capability da errore di sintassi. Il passthrough SQL conserva comunque la
responsabilità del chiamante per i costrutti specifici non interpretati.

**DIA-08.** CTE, UNION, INTERSECT, EXCEPT, FROM derivati e join espliciti non
sono opzioni autonome di questa API SELECT legacy. Possono esistere in SQL
opaco o in altri rami sperimentali; non sono requisiti di questa superficie.

**DIA-09.** Anche fra driver PostgreSQL cambia l'adattamento dei parametri:
psycopg2 conserva collezioni come tuple e converte i placeholder a pyformat;
postgres3 espande collezioni non vuote nei contesti IN riconosciuti e prepara
placeholder per il proprio wrapper; postgres8000 segue un altro percorso.
Le riscritture delle collezioni vuote in TRUE/FALSE usano pattern specifici
degli alias e vanno provate anche con `aliasPrefix` personalizzato. «Supporta
PostgreSQL» non dimostra equivalenza fra i tre driver.

## 15. Risultati e metadati da non perdere

**RES-01.** Le righe mantengono nomi e posizione delle colonne; l'adattatore
legacy può esporre anche accesso indicizzato e dizionario tramite GnrDictRow.
Il compiler non deve imporre un diverso contenitore ai consumatori.

**RES-02.** Dtype, formato, etichette, attributi applicativi e provenienza della
colonna sono usati da `_prepColAttrs`, GUI e aggregatori. Un AS deve conservare
la possibilità di risalire all'espressione/colonna originale.

Il nuovo result plan conserva identità d'origine e metadati UI risolti sia
per dichiarazioni inline sia parallele. Le espressioni derivate espongono
metadati propri coerenti con tipo e scrivibilità; l'alias di output non sostituisce
l'identità della colonna. La lettura dei metadati non reintroduce aggregateRows.

**RES-03.** Il percorso fetch ordinario applica pyColumn, decifratura e conversione
Bag. Altri percorsi, inclusi multistore e cursor diretti, possono avere differenze:
la compatibilità end-to-end va verificata per ciascuna API, senza ascrivere al
compiler trasformazioni effettuate soltanto da un wrapper.

**RES-04.** La rilevazione attuale di campi cifrati nella query è basata su nomi
di output riconducibili alle colonne principali. Alias e colonne correlate sono
casi da caratterizzare; non dichiarare supporto universale dalla presenza della mappa.

**RES-05.** `fetch`, `selection`, `fetchPkeys`, `count`, `record` e fetch
multistore sono osservatori diversi. Il corpus deve confrontare almeno quelli
coinvolti nella release del nuovo compiler.

## 16. Errori e diagnostica

**ERR-01.** Distinguere almeno campo inesistente, relazione inesistente,
virtuale invalida, modello composito incoerente, conversione filtro fallita,
parametro mancante, macro senza contesto e funzionalità non supportata.

**ERR-02.** Il wrapper compatibile deve mappare dove necessario a
`GnrSqlMissingField`, `GnrSqlInvalidVirtualColumn`, `GnrSqlException` o alle
eccezioni tabella `not_existing_column`/`invalid_filter_value`.
Identità e attributi dell'errore possono essere un contratto dei chiamanti;
non è richiesta per default l'identità di ogni messaggio testuale.

**ERR-03 — N.** Una diagnostica nuova dovrebbe riportare clausola, span del
testo, tabella, percorso risolto fin lì e catena di formule. Non mascherare un
errore di modello trasformando il riferimento in identificatore SQL grezzo.

**ERR-04.** L'errore del driver per SQL opaco invalido rimane distinguibile dagli
errori rilevati prima dell'esecuzione. Non promettere un parser completo del
dialetto se si conserva un percorso opaco.

## 17. Registro iniziale delle anomalie e delle decisioni

Questa tabella è parte della specifica: ciascun elemento impedisce di usare
«equivalente» senza precisare il comportamento scelto.

| ID | Caso da caratterizzare | Decisione proposta, non ancora approvata |
|---|---|---|
| A01 | `*prefix` principale ignora il prefisso | Emulazione nel profilo legacy; sintassi regolare corretta separata. |
| A02 | Regex sostituiscono dentro contesti SQL non analizzati | Lexer corretto; inventario dei casi applicativi incompatibili. |
| A03 | Split AS e alias duplicati/collidenti | Confronto corpus; errore esplicito solo dove concordato. |
| A04 | Pkey/default order prima del riconoscimento SUM/COUNT | Wrapper di compatibilità; stato semantico esplicito nel nucleo. |
| A05 | False non disabilita auto-DISTINCT | Preservare nella vecchia API; eventuale nuova opzione distinta. |
| A06 | Count con many, group e limiti | Stabilire risultati numerici mediante oracle, non commenti. |
| A07 | `_aggregateRows` deduplica valori legittimi | DECISO: rimuovere anche dal bridge; migrare a semantica esplicita e aggregati SQL. |
| A08 | `#ENV`/`#PREF` inseriscono testo e fallback fragili | Provider che distingue valori e SQL fidato; binding per valori. |
| A09 | `var_*` e `queryCompile` generano nomi basati su id | Scope deterministici preservando separazione e valori. |
| A10 | Case-insensitive join e composite di arità diversa | Fixture reali; correggere con migrazione degli eventuali casi. |
| A11 | `limit=0` falsy, record unknown virtual ignorata | Emulazione nel wrapper oppure rottura documentata. |
| A12 | Empty IN, NULL e adattamenti driver | Matrice reale per adapter; nessuna generalizzazione prematura. |
| A13 | Macro custom registrata ma non invocata | Contratto di fase esplicito; distinguere ampliamento dalla compatibilità. |
| A14 | Rank con pesi espliciti/canale assente | Test PostgreSQL; diagnostica mirata. |
| A15 | Parametri-campo riconosciuti solo in alcuni contesti | Preservare il confine nell'API legacy, esplicitarli nell'IR nuova. |
| A16 | Merge testuale subtable e nomi sovrapposti | Parser delle condizioni subtable con confronto dell'oracle. |
| A17 | Cifratura/pyColumn con alias, relazioni o multistore | Test per API di consumo, non soltanto compilazione. |
| A18 | Macro full-text duplicate e rank dopo sostituzione campi | Corpus end-to-end per driver, forma diretta e virtuale. |
| A19 | Record con aliasPrefix o nomi fisici personalizzati | Confrontare filtro automatico, FROM, alias strutturali e resultmap. |

## 18. Architettura proposta per implementare da zero — N

Questa sezione suggerisce una struttura; non impone di copiare classi o flusso
del vecchio compiler.

```text
API legacy / query Bag / nuova API
          ↓ adattamento ingresso
QuerySpec + espressioni con riferimenti Genro
          ↓ risoluzione su ModelProvider e contesto
Piano semantico: scope, colonne, relazioni, tipi, cardinalità, parametri
          ↓ applicazione politiche e lowering
Piano SQL per dialetto + piano metadati/postprocessing
          ↓ rendering
SQL + binding + descrittori dei risultati + dipendenze
```

**NEW-01.** Un `QuerySpec` esplicito conserva la differenza fra argomento omesso,
False, stringa vuota e valore effettivo dove la compatibilità lo richiede.

**NEW-02.** Nodi minimi delle espressioni: SQL opaco segmentato, riferimento
locale, percorso relazione, parametro, riferimento esterno, chiamata macro,
formula risolta, sottoquery, alias di risultato.

**NEW-03.** Non è necessario iniziare da un parser completo di ogni dialetto.
È però necessario un lexer affidabile, confini di espressione e scope; i token
Genro presenti nel SQL opaco devono essere identificati senza alterare letterali.

**NEW-04.** Il `ModelProvider` risolve i contratti MOD senza esporre le classi
legacy. Un primo provider può adattare il modello esistente; un secondo può
consumare il modello prodotto da genro-sql e da grammatiche distribuite.

**NEW-05.** Il piano dei join identifica percorso, scope, condizioni e cardinalità;
ordina le dipendenze e non deduplica join soltanto perché condividono la tabella.

**NEW-06.** Il binder gestisce scope annidati, valori ambientali e macro, lista
parametri e parametri-campo. Non usa `currentEnv` come contenitore implicito
obbligatorio per tutta la compilazione.

**NEW-07.** Gli alias pubblici legacy vengono conservati al confine; gli alias
interni possono essere deterministici. Collisioni fra nomi pubblici hanno una
politica dichiarata, non un effetto collaterale della struttura dati.

**NEW-08.** Il result plan registra nome, dtype, origine, cardinalità, conversioni
e callback per ogni proiezione. Non ricostruisce queste informazioni analizzando
il SQL finale o indovinando dal nome dell'alias.

**NEW-09.** Il wrapper di compatibilità contiene le anomalie da emulare. Il
nucleo semantico non deve dipendere da controlli come «il testo contiene sum(».

**NEW-10.** Niente riscritture di ottimizzazione prima dell'equivalenza semantica:
subquery → join aggregato/LATERAL richiede prova su cardinalità, NULL, filtri,
limiti, lock e SQL volatile. Le prestazioni vanno misurate separatamente.

## 19. Estensioni fuori dal traguardo legacy — F

- `@invoices.sum($total)`, `@invoices.count()` e funzioni sui percorsi.
- Aggregati annidati con scope esplicito per ciascuna relazione.
- `template`, `to_array`, `to_json` nella nuova grammatica dei GEP.
- `virtualRelation` secondo la nuova proposta GEP: requisito del modello
  obiettivo già acquisito, distinto dal contratto della baseline legacy.
  Il nome manyRelation appartiene alla proposta precedente.
- Nuove primitive query per UNION/CTE/join espliciti, se richieste.
- Sostituzione dei many join con EXISTS come nuova semantica implicita.

L'architettura dovrebbe permetterle, ma non attribuirle al linguaggio legacy.
Soprattutto, la nuova forma di aggregato per relazione non deve cambiare
retroattivamente il significato delle espressioni SQL già in uso.

## 20. Criteri per dichiarare la sostituzione pronta

**ACC-01.** Ogni requisito applicabile ha un caso verificato o una limitazione
esplicita. Gli ID A hanno una decisione registrata e test che la rendono visibile.

**ACC-02.** Confronto differenziale sullo stesso modello e dataset fra compiler
baseline e nuovo: risultati, duplicati, ordinamento, alias, dtype, parametri,
filtri, metadati e categorie di errore. Il SQL può differire internamente.

**ACC-03.** SQLite per il sottoinsieme portabile e PostgreSQL per quello
PostgreSQL, includendo funzionalità realmente abilitate. Per altri adapter
serve una matrice dedicata prima di rivendicarne la compatibilità.

**ACC-04.** Usare dati avversi piccoli con risposte note e query reali del corpus
applicativo. Test che verificano soltanto «è una lista» o «count > 0» non
dimostrano equivalenza delle aggregazioni.

**ACC-05.** Separare test di parsing/risoluzione, test di compilazione e test
con database reale. Nessun mock dello stack può certificare semantica SQL.

**ACC-06.** Il nuovo compiler resta selezionabile con rollback al precedente;
la scelta del compiler per query e record deve essere coerente. Nessuna
esecuzione doppia automatica di query con lock o callback con effetti collaterali.

## 21. Fonti e grado di verifica

Root delle fonti: [Genropy alla baseline](https://github.com/genropy/genropy/tree/e12f2ce54245e57e48371ae0f47e928e0d55b960/gnrpy).
I percorsi seguenti sono relativi a `gnrpy/` e identificano i punti da usare come
oracle, senza dipendere dalle righe variabili di un branch.

| Fonte | Simboli / sezioni coperte |
|---|---|
| `gnr/sql/gnrsqldata/compiler.py` | `compiledQuery`, `getFieldAlias`, `_getRelationAlias`, `expand*`, `compiledRecordQuery`: LEX–REC. |
| `gnr/sql/gnrsqldata/query.py` | `SqlQuery.__init__`, `compileQuery`, `count`, `selection`, elaborazione risultati: API, CAR, RES. |
| `gnr/sql/gnrsqldata/record.py` | Wrapper e resolver del record: confine REC. |
| `gnr/sql/gnrsqltable/query.py` | API tabella, `jc_*`, query Bag e helper dei campi. |
| `gnr/sql/gnrsql/query.py` | `queryCompile`, `colToAs`, passaggio dei parametri ambientali. |
| `gnr/sql/gnrsql/execute.py` | Binding env, escape, store, adattamento al driver. |
| `gnr/sql/gnrsqlmodel/model.py` | Dichiarazioni virtuali, composite, subQueryColumn, costruzione modello. |
| `gnr/sql/gnrsqlmodel/table.py` | `getVirtualColumn`, `virtual_columns`, `starColumns`. |
| `gnr/sql/adapters/_gnrbaseadapter.py` | Dispatcher macro, renderer SELECT, liste bind, `GnrWhereTranslator`. |
| `gnr/sql/adapters/_gnrbasepostgresadapter.py` | Macro TS/VEC e comportamento PostgreSQL condiviso. |
| `gnr/sql/adapters/gnrpostgres.py`, `gnrpostgres3.py`, `gnrpostgres8000.py` | Placeholder, liste e secondo trasformatore full-text specifico di psycopg2. |
| `gnr/sql/adapters/gnrsqlite.py`, `gnrmysql.py`, `gnrmssql.py` | Differenze di rendering e traduzione considerate. |
| `gnr/core/gnrstring.py`, `gnrdate.py` | Split delle espressioni e linguaggio dei periodi. |
| `tests/sql/test_compiler_coverage.py` | Corpus runtime di query, virtuali, relazioni, macro, policy e record. |
| `tests/sql/test_compiler_simulation.py` | Navigazioni multi-hop su modello reale. |
| `tests/sql/test_vecquery_macro.py`, `test_macro_registration.py` | Macro vettoriali e registry. |
| `tests/sql/h_query_surface_test.py`, `e_query_test.py` | Superficie query e consumer. |

Questa versione è stata confrontata con il sorgente e con le famiglie di test
pertinenti; non deriva dall'esecuzione completa del corpus legacy. I casi del
documento complementare sono specifiche di test da implementare, non test già
superati. Compatibilità totale dei dialetti, inventario di tutte le applicazioni,
edge case lessicali e risultati esatti dei comportamenti A restano da certificare.
