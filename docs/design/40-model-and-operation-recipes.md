# 40 — Modello, proiezione fisica e ricette delle operazioni

**Regola vincolante:** il legacy prevale per nomi, firme e significato. Uno
scostamento richiede una motivazione concreta e l'approvazione dell'utente
prima dell'applicazione. Restano valide le differenze già concordate, fra cui
DHZ/UTC. Perimetro attuale: grammatica e traduzione, senza anticipare esecuzione.

Data: **12 ottobre 2026**. Stato: decisioni della conversazione di ripresa e
contratti ancora da chiudere. Questo documento non certifica implementazioni.

**Seguito della sessione:** su incarico dell'utente, la
[specifica 42](42-configuration-grammar.md) completa autonomamente la proposta
delle firme rimaste aperte, includendo relations e virtual relations.
Il requisito di espressività è coprire tutti i package di `test_invoice_pg`,
documentati nella [matrice 43](43-test-invoice-model-coverage.md).
Le ulteriori scelte del 42 sono proposte concrete da revisionare, distinte
dagli accordi espliciti registrati qui; l'elenco finale delle domande conserva
il punto di partenza della discussione, non richiede di ripartire da zero.

## Fonti e precedenza

Le decisioni del 6 ottobre su sezioni DB, package, options e personalizzazioni
sono raccolte nella [revisione della configurazione, §§7–10](../review/configurazione-e-grammatiche-it.html#options)
e sono state richiamate e confermate nella conversazione del 12 ottobre.
Qui vengono riportate nel dossier Markdown insieme alle nuove decisioni sulle
operazioni trasferibili. Per questi temi aggiornano la
[proposta 0001](../proposals/0001-model-and-expressions.md) e i piani precedenti.
Le firme del [demo](../review/esempi/demo_grammar.py) sono illustrative:
non costituiscono da sole un'approvazione di parametri e default.

## Sequenza acquisita

1. **Definire il modello:** grammatica, configurazione, composizione, render e
   oggetti, considerando il significato completo delle dichiarazioni.
2. **Verificare le migrations:** proiettare dagli oggetti il JSON normalizzato
   richiesto da `asqueel-migration` e verificare la struttura fisica risultante.
3. **Definire lettura e scrittura:** ricette delle operazioni, serializzazione,
   ricostruzione, compilazione ed esecuzione, con record, policy e trigger.

Il modello completo è il perimetro dell'analisi. L'assenza di effetti SQL non
esclude un elemento: virtuali, gruppi, metadati, subtable e comportamenti delle
options devono essere considerati. Questo non approva automaticamente i
dettagli ancora Proposed/Open né impone di implementarli tutti insieme.

I rinvii espliciti sono raccolti nel [registro 41](41-deferred-features.md).
Il 12 ottobre è stato deciso di omettere per ora `toolColumn`; le altre voci
aperte non vengono rinviate automaticamente.

## Struttura del modello — Deciso

| Sezione della radice `db` | Responsabilità |
| --- | --- |
| `connection` | Collegamento al database fisico; valori esterni tramite resolver. |
| `packages` | Gruppi logici di tabelle; ogni package stabilisce `sqlschema` e `sqlprefix`. |
| `extensions` | Estensioni del database. |
| `options` | Funzioni facoltative del database intero. |

Decisione aggiornata: gli schemi fisici sono dedotti dai package, come nel
legacy. Non si dichiara una sezione schemas, né options di schema separate.
Package e schema fisico restano distinti. Più package possono usare lo stesso
sqlschema; anche un package senza tabelle contribuisce il proprio schema.
Il prefisso predefinito è il nome del
package; lo schema predefinito viene dal dialetto. Firme, rappresentazione
dell'assenza di prefisso e regole complete sugli override restano da chiudere.

La dichiarazione di una tabella riceve il **package**:

Nella revisione della sintassi è stato inoltre confermato che `table` prevede
sempre gli attributi standard `name_long`, `name_short`, `name_plural` e
`caption_field`, direttamente nella dichiarazione e non nelle options.

```python
class ProductTypeModel:
    def configure(self, pkg):
        tbl = pkg.table('product_type', pkey='id')
        tbl.column('description')
        opts = tbl.options()
        opts.sys_fields(draft={'name_long': 'Bozza'}, ldel=False)
        opts.hierarchical('description')
        opts.auto_counter('parent_id')
        return tbl
```

È sintassi obiettivo, non un esempio eseguibile con l'API corrente. Le chiamate
mostrano la collocazione delle funzioni; non fissano tutti i loro default.
I contenitori interni delle tabelle non cambiano il contratto pubblico
`configure(self, pkg)` / `pkg.table(...)`.

## Options e composizione — Deciso

- `options` è una sezione di funzioni facoltative, ammessa sotto `db`,
  `connection`, `package` e `table`. La possibilità di options su
  package è stata confermata; la precedente sezione schema è superata dalla
  decisione successiva di dedurre gli schemi dai package.
  Le funzioni valide dipendono dalla grammatica del
  livello; la sezione comune non rende ogni opzione valida ovunque.
  Questo non decide quali funzioni aggiungere ai package, né implica
  ereditarietà automatica delle loro options sulle tabelle.
- Ogni opzione ha firma tipizzata e documentazione. Un'opzione sconosciuta è
  un errore. La grammatica si estende per aggiunta, conservando le ricette base.
- Un'opzione produce le colonne e i comportamenti necessari. Per i parametri
  che generano colonne: `False` disabilita, `True` usa gli standard, un `dict`
  personalizza gli attributi consentiti. Il dict non cambia il nome della
  colonna o gli attributi indispensabili alla funzione.
- Le personalizzazioni sono contributi ordinati ("foglietti") sulla ricetta:
  un contributo successivo può completare o correggere anche le options.
  Il core applica l'elenco e gestisce contratto ed errori; il framework decide
  discovery, ubicazione, livelli e ordine dei contributi.
- Una classe che estende la grammatica fornisce anche i costruttori delle
  parti aggiunte. Le options esterne seguono questo stesso contratto.
- Tutti i contributi precedono un'unica render; dopo la render la fonte di
  verità sono gli oggetti, senza accesso alla ricetta sorgente.

Il dizionario `connection(options=...)` dell'API attuale contiene parametri
del driver. Non è l'implementazione della futura sezione
`connection.options()`; il loro raccordo richiede una decisione esplicita.

## Validazioni di colonna ed embedding locale — Deciso il 12 ottobre

La colonna ammette una sezione `validation` con una propria grammatica.
Asqueel offre anche la forma compatta legacy con attributi `validate_*`:
le due forme producono la stessa sezione nella source, soggetta alla stessa
validazione grammaticale.

```python
tbl.column('code', validate_len='2:20', validate_notnull=True)

# Forma equivalente, alternativa alla precedente:
tbl.column('code').validation(len='2:20', notnull=True)
```

Il prefisso `validate_` instrada i parametri alla grammatica `validation`;
un parametro sconosciuto, per esempio `validate_lne`, è un errore.
L'embedding viene realizzato **nel core Asqueel**. La sua eventuale
generalizzazione in Builders verrà valutata successivamente e non costituisce
un prerequisito né un incarico di modifica a Builders.

Le regole sono dichiarazioni del modello, esportabili a Gramlot per essere
eseguite anche localmente sul client. Gli esecutori client e server devono
condividerne la semantica; il server mantiene i controlli autorevoli.
Le regole che dipendono da dati o logica esclusivamente server richiedono
un'esecuzione server. Questo contratto non certifica implementazioni già
presenti in Asqueel o Gramlot.

La regola `validation(notnull=True)` non va confusa con il vincolo fisico
`column(notnull=True)`: la prima riguarda la validazione del valore, il secondo
la struttura SQL. Non è stata decisa una propagazione automatica fra i due.

**Decisione del 13 ottobre:** forma embedded e sezione esplicita alimentano
lo stesso dizionario `column.validations`. Il prefisso `validate_` viene tolto;
chiavi e valori restano quelli dichiarati, compresi `case` e `notnull_error`.
Controlli e trasformazioni non vengono separati: eliminata `normalize`.
I messaggi mantengono le chiavi legacy `*_error`, senza un dizionario `messages`.
La traduzione non esegue le regole e non aggiunge controlli non dichiarati.

**Semplificazione successiva, 13 ottobre:** per ora si salvano soltanto i
parametri. `validation(**rules)` non impone un vocabolario né tipi specifici:
nomi e valori restano dichiarazioni da interpretare quando saranno usate.
Ordine di esecuzione, default, trigger e percorsi RECORD/RAW appartengono
alla fase delle operazioni.

**Eccezione al legacy approvata il 13 ottobre — values:** il legacy usa
`column(values=...)` come attributo per le scelte dei widget. Asqueel usa
`column(validate_values=...)`, equivalente a `column.validation(values=...)`,
e conserva la dichiarazione in `column.validations['values']`. Per ora nessuna
interpretazione o esecuzione della regola e nessun vincolo SQL implicito.

## Generazione della primary key nella source — 12 ottobre

**Deciso, dopo la revisione della collocazione:** per il campo di sistema `id`,
la modalità di generazione si configura dentro `sys_fields`:

```python
tbl = pkg.table('customer', pkey='id')
tbl.options().sys_fields(id=dict(type='uuid'))
```

Il default è **`id=True`**, con UUID testuale compatto di **22 caratteri**.
Le seguenti sono forme alternative equivalenti per la configurazione di `id`:

```python
opts.sys_fields()
opts.sys_fields(id=True)
opts.sys_fields(id=dict(type='uuid'))
```

Sono alternative, non tre dichiarazioni da eseguire insieme. `id=False`
disabilita l'aggiunta di questo campo da parte di `sys_fields`. Gli altri
default di `sys_fields` non vengono fissati da questa equivalenza.

L'opzione aggiunge la colonna `id` e il comportamento che genera una chiave
quando manca. `pkey='id'` identifica la chiave della tabella; `type='uuid'` è
un parametro funzionale della configurazione di `id`, non il dtype SQL né un
override arbitrario dei metadati interni della colonna. Restano ammesse le
personalizzazioni descrittive previste dal contratto delle options.

La generazione appartiene all'esecuzione, non alla costruzione, serializzazione
o compilazione della ricetta. **Deciso:** usare lo stesso algoritmo di
`getUuid()` del legacy, verificato in
`gnrpy/gnr/core/gnrlang.py:165` del checkout GenroPy il 12 ottobre:

```python
thread_id = str(_thread.get_ident())
uuid_bytes = uuid.uuid3(uuid.uuid1(), thread_id).bytes
value = base64.urlsafe_b64encode(uuid_bytes)[:22].replace(b'-', b'_').decode()
```

UUID3 con un nuovo UUID1 come namespace e l'id del thread come nome; codifica
base64 URL-safe, primi 22 caratteri e sostituzione di `-` con `_`. Il risultato
è una stringa di 22 caratteri nell'alfabeto `A-Z`, `a-z`, `0-9`, `_`, senza
padding. Anche la sostituzione è parte del contratto: non sostituire con UUID4
o una diversa codifica compatta. L'uso dello stesso algoritmo non richiede una
dipendenza runtime da GenroPy né importa le altre strategie di `pkeyValue`.

La precedente collocazione `table(..., pkey_type=...)` è **superata per il
campo di sistema `id`**; non va implementata in parallelo per questo caso.
Anche l'ipotesi `options().pkey_generator(...)` è superata. Il valore `custom`
è stato ritirato dall'elenco deciso. Il nome convenzionale concordato per il
metodo applicativo resta `new_pkey_value(self, record)`, che restituisce la
chiave da assegnare: il collegamento e la precedenza rispetto alle strategie
standard richiedono ancora una decisione. Nessun codice Python viene trasferito
nella ricetta. Queste decisioni non certificano l'implementazione dell'API.

**Da chiudere:** gli altri valori di `id.type` e il loro vocabolario enumerato,
il generatore di una chiave applicativa dichiarata senza `sys_fields`, dtype
fisico esatto, conflitti con una colonna già dichiarata o una diversa pkey,
chiavi già fornite o vuote, composite, generazione DB e percorsi RAW/batch.
Restano diagnostiche dei generatori e ordine rispetto agli hook. `sequence`
e `manual` erano proposte e non sono diventati valori approvati con questa
revisione.

Il [dossier 39](39-primary-key-analysis.md) descrive il meccanismo legacy
`checkPkey → newPkeyValue → pkeyValue`; il nuovo contratto non ne eredita
automaticamente le strategie implicite. La [issue core 12](https://github.com/asqueel-org/asqueel/issues/12)
resta un requisito consumer da soddisfare, non prova di una funzione rilasciata.

## Altri campi di sys_fields — decisioni e punti aperti

`id` è definito sopra. Il vocabolario già individuato comprende timestamp,
utente, cancellazione logica e bozza. La tabella distingue i default legacy,
verificati in `gnrpy/gnr/app/gnrdbo.py`, dalle decisioni per Asqueel:

| Parametro Asqueel | Colonna | Funzione | Default legacy | Default Asqueel deciso |
| --- | --- | --- | --- | --- |
| `ins` | `__ins_ts` | Data/ora inserimento. | `True` | `True` |
| `upd` | `__mod_ts` | Data/ora ultima modifica, valorizzata anche all'inserimento. | `True` | `True` |
| `ldel` | `__del_ts` | Data/ora cancellazione logica. | `True` | `True` |
| `user_ins` | `__ins_user` | Utente che inserisce. | Configurabile, altrimenti `True` | `True` |
| `user_upd` | `__mod_user` | Utente che modifica, valorizzato anche all'inserimento. | Configurabile, altrimenti `False` | `True` |
| `draft` | `__is_draft` | Stato di bozza (`draftField` nel legacy). | `False` | `False` |

Per i parametri sopra i default di attivazione sono decisi. Restano tipo, attributi personalizzabili, indici,
fonte e momento di assegnazione, comportamento con valori già forniti e RAW.
In particolare: timezone dei timestamp, rappresentazione dell'identità utente,
integrazione delle policy draft/soft-delete e dei relativi comandi di scrittura.

**Deciso il 12 ottobre:** `ins=True` e `upd=True` sono i default, conservando i nomi
`__ins_ts` e `__mod_ts` e l'assegnazione di entrambi all'inserimento; `upd` viene
poi aggiornato alle modifiche. Restano da chiudere timezone, tipo fisico,
eventuale uso di un unico istante per entrambi i campi, indici, override dei
valori forniti, ordine dei trigger e comportamento RAW. Questi dettagli non
sono impliciti nell'approvazione dei default.

**Deciso il 12 ottobre — campi utente:** `user_ins=True` e `user_upd=True`
sono entrambi attivi per default. `__ins_user` viene assegnato all'inserimento;
`__mod_user` all'inserimento e alle modifiche. I valori provengono dall'ambiente
autenticato del server. In assenza di utente, il valore è `NULL`, per consentire
processi e script senza identità utente. L'attivazione standard di `user_upd`
è una scelta esplicita diversa dal default legacy.

Restano da definire chiave dell'ambiente, rappresentazione dell'utente e dtype
fisico, eventuale relazione a una tabella utenti, trattamento dei valori forniti,
ordine dei trigger e percorsi RAW. Le regole di esecuzione client non possono
attribuire l'identità autenticata del server. L'approvazione è documentale:
questi default non sono ancora implementati.

**Deciso il 12 ottobre — cancellazione logica e bozza:** `ldel=True` aggiunge
`__del_ts` per cancellazione logica e ripristino. La cancellazione logica è
un'operazione esplicita; `delete()` mantiene la cancellazione fisica, senza
conversione automatica per la presenza del campo. `draft=False` non aggiunge
un campo bozza per default; `draft=True` aggiunge `__is_draft` e abilita la
relativa policy. Attivare la funzione bozza non decide che ogni nuovo record
nasca in bozza: default del valore e transizioni restano da definire.

Riepilogo dei default di attivazione decisi, senza fissare la firma completa
o i dettagli ancora aperti:

```python
opts.sys_fields(
    id=True, ins=True, upd=True,
    user_ins=True, user_upd=True,
    ldel=True, draft=False,
)
```

Restano per `ldel` tipo/timezone, indici e dettagli delle operazioni di
cancellazione logica/ripristino; per `draft` valore iniziale, nullabilità,
transizioni e controlli applicativi. Propagazione ai record correlati e
comportamento RAW vanno definiti con il lifecycle, non dedotti dai flag.

L'[analisi 34](34-sysfields-analysis.md) censisce anche `full_upd`, `md5`,
protezioni, campi invalidi/diagnostica, record di sistema, release, audit,
riferimento al record e altri campi generati. Restano da valutare senza
escluderli automaticamente o includerli tutti in `sys_fields`. Contatori e
gerarchie hanno già le proprie options. Il rinvio di `toolColumn` non decide
da solo il destino di `__record_pointer`.

## Proiezione verso il migratore — Deciso

Il core produce dagli oggetti il **JSON normalizzato `structure-1.0`** già
accettato da `asqueel-migration`, distinto dal suo formato human JSON.
Le factory e il validatore del migratore definiscono il contratto fisico;
non se ne introduce uno concorrente.

La proiezione comprende schemi, tabelle, colonne, chiavi, vincoli, indici ed
estensioni supportate. I package determinano il mapping fisico. Le options
contribuiscono attraverso gli effetti fisici già presenti negli oggetti;
metadati semantici e trigger Python restano nel core. Una composite rimane un
oggetto del modello anche quando proietta un UNIQUE o una chiave multicolonna.

Il criterio di accettazione da realizzare è un modello con package distinti
anche sullo stesso schema, prefissi, relazione tra package e colonne generate
da options: JSON serializzabile e validato, applicazione al DB di prova e
confronto successivo senza differenze residue nel profilo supportato. Verificare
anche schemi vuoti ed estensioni, senza perderli nella proiezione dalle tabelle.

## Ricette delle operazioni — Deciso il 12 ottobre

- Ogni operazione sul DB è prima una struttura dichiarativa. Il requisito
  riguarda l'architettura delle operazioni, incluse SELECT/INSERT/UPDATE/DELETE;
  il catalogo completo degli elementi verrà definito nel terzo passo.
- Costruzione, compilazione ed esecuzione sono separate. Costruire o
  serializzare una ricetta non esegue l'operazione sul database.
- La struttura può essere renderizzata in JSON o XML, trasferita e ricostruita
  su un'altra macchina. Anche il browser può costruirla e inviarla al server.
- I riferimenti logici vengono risolti sul modello del destinatario. La
  compilazione genera SQL e parametri per il dialetto di destinazione; un piano
  di scrittura può includere più statement e passaggi applicativi.
- Il formato conserva il significato dei valori tipizzati e delle operazioni.
  Non richiede di trasferire connessioni, istanze runtime o codice Python.
- L'esecutore conserva RECORD/RAW, trigger, policy e invarianti transazionali.
  La serializzazione non introduce commit impliciti o bypass degli hook.

### Ricette ricevute dal client — Deciso

La grammatica remota è chiusa e validata: riferimenti risolti sul modello,
operatori e funzioni ammessi, valori separati dal codice e passati come
parametri. Non ammette SQL arbitrario, inclusi frammenti in filtri, proiezioni
o ordinamenti. JSON/XML da soli non proteggono dalla SQL injection.

Il client può riferirsi a una formula dichiarata dal modello server; questo
non lo autorizza a dichiarare SQL libero. Il pass-through SQL proposto per
espressioni applicative fidate non è ammesso nell'ingresso remoto.
Validità strutturale e autorizzazione sono distinte: il server controlla
permessi e policy e usa il proprio contesto autenticato. Una ricetta non può
autoattribuirsi identità, tenant, privilegi o facoltà di bypass.

Restano da chiudere codec dei valori, versione del formato, compatibilità del
modello, binding dei parametri e del contesto, errori, risultati e confini
delle unità di lavoro remote. Non è stata scelta un'API HTTP/MCP o una libreria
browser. Il JSON delle operazioni e quello delle migrations sono contratti
distinti; non si usa il secondo come formato delle query.

## Primo blocco da chiudere: firme di db, packages e options

La gerarchia e le responsabilità sopra sono acquisite. Si chiudono ora le
firme, una decisione alla volta, senza riaprire quelle responsabilità.

**Proposta iniziale, non ancora approvata:** per la selezione fisica del package,
`package(name, sqlschema=None, sqlprefix=True)`:

- `sqlschema=None`: schema predefinito del dialetto;
- `sqlprefix=True`: nome del package come prefisso;
- `sqlprefix=False`: nessun prefisso;
- `sqlprefix='testo'`: prefisso personalizzato; precisare la regola del
  separatore nel nome SQL e della stringa vuota prima di implementare.

**Questioni successive aperte:**

1. Disponibilità implicita dello schema predefinito, validazione degli altri
   schemi e override fisici di tabella.
2. Firma di `db` e `connection`, conservazione dei resolver e raccordo con
   `connection(options=...)` corrente.
3. Firme di `schema` e metadati di package; accesso agli oggetti risultanti.
4. Accesso ripetuto a un contenitore singleton e regole precise di merge,
   disattivazione e conflitto fra contributi successivi.
5. Vocabolario delle options per livello e firma di `sys_fields`, inclusa la
   pkey generata. Le altre funzioni vanno censite prima di decidere il rinvio.

Nessuna firma proposta in questa sezione è una decisione acquisita.

## Correzione della grammatica — 12 ottobre, revisione successiva

Per valori esterni e calcolati si usano i resolver esistenti (`EnvResolver`,
`BagCbResolver`), conservati nella source senza esecuzione anticipata. Nessun
registro aggiuntivo di variabili nel DB. La costruzione di oggetti vivi resta
alla fase successiva. Il [report 49](49-grammar-corrections-and-audit.md) registra
le rimozioni e la verifica delle aggiunte rispetto alle decisioni e al legacy.

## Schemi dedotti dai package — decisione successiva

L’utente ritira la sezione di dichiarazione degli schemi: ogni package indica
il nome fisico con sqlschema; assente, si usa il default del dialetto. Non
servono authorization, alias o metadati/options di schema indipendenti.
Gli schemi restano nella proiezione fisica richiesta da asqueel-migration.
Dettagli e verifiche nel [report 50](50-schemas-from-packages.md).

## Timestamp di sistema — decisione successiva

I timestamp generati dalle options usano DHZ. La convenzione di scrittura
nel database è UTC. Per ora non si espone né timestamp_type su sys_fields
né use_timezone sul DB: un’eventuale opzione sarà valutata in seguito.
Questa decisione chiude la scelta di tipo/timezone lasciata aperta sopra;
non implementa né anticipa il ciclo delle scritture. Le colonne dichiarate
esplicitamente mantengono il proprio dtype.

Il file dell’istanza test_invoice_pg non esplicita use_timezone, ma la baseline
salvata per i confronti è stata acquisita con use_timezone=True (report 45
e tests/oracles/test_invoice_pg/manifest.json). Non va quindi descritta
come una baseline DH.

## Chiave testuale derivata — decisione successiva

Si mantengono gli attributi legacy della tabella pkey_columns e
pkey_columns_joiner. Ritirata l'opzione pkey_from e la sua policy missing.
La grammatica conserva la stringa dei campi nell'ordine dichiarato e
l'eventuale separatore; non calcola una chiave. Nel legacy il separatore
assente o vuoto equivale a underscore e i valori None vengono saltati.
Questa dichiarazione non trasforma pkey in una chiave SQL multicolonna.

## Macro — confine confermato il 13 ottobre

La registrazione e l'espansione delle macro SQL appartengono alla compilazione
delle query, non alla struttura del modello. Nel legacy invc/main.py separa
registerMacros da config_db; addMacro in gnrsql/db.py configura le compilazioni.
Rimossa quindi options().macro dalla grammatica strutturale e dall'export.
Restano le espressioni del modello che contengono riferimenti a macro:
conservarle non richiede registrare o eseguire macro durante la traduzione
strutturale. Nessuna nuova API del compilatore è definita in questa revisione.

## exist e nodup — grammatica, 13 ottobre

Conservare le dichiarazioni, senza implementarne l'uso. Il nome legacy è
exist, non exists; nel legacy exist e nodup usano bool o str, senza imporre
questa restrizione nel dizionario dichiarativo. Il prefisso validate_
viene tolto per produrre column.validations, mantenendo valori, parametri e
messaggi legacy (exist_* e nodup_*). Nessuna risoluzione del campo di confronto,
ricerca sul DB o deduzione di vincoli fisici durante la traduzione.


## VirtualRelation — semplificazione rispetto alla GEP, 13 ottobre

Per decisione dell'utente limit, order_by e one_one sono rinviati ed esclusi
dalla firma di virtualRelation (41, R-06). Restano relation/table, condition,
var_*, ask e i metadati; inverse è già fuori perimetro (R-05). La selezione
ordinata e limitata non fa parte di questa dichiarazione. Gli altri costrutti,
incluse query, subQueryColumn e relazioni ordinarie, restano invariati.
