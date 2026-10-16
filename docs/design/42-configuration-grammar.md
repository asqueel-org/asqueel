# 42 — Grammatica di configurazione del modello, prima specifica completa

**Decisione successiva sui timestamp:** i timestamp di sistema sono DHZ;
la convenzione di scrittura nel DB è UTC. Per ora nessuna opzione
`timestamp_type` o `use_timezone`. Prevale sui punti ancora aperti citati sotto.
La baseline salvata del corpus usa già use_timezone=True (report 45).

12 ottobre 2026. **Specifica obiettivo da revisionare, non API già implementata.**
L'utente ha incaricato di completare autonomamente le firme usando il legacy,
il contratto del migratore e tutti i package di `test_invoice_pg`.
Le decisioni esplicite del [contratto 40](40-model-and-operation-recipes.md)
restano vincolanti; le scelte aggiuntive qui fissate sono la proposta redazionale
per chiudere le alternative. Non certificano compatibilità runtime.
La [grammatica pubblicata](../grammar.md) continua a descrivere il codice attuale.

L'implementazione e il percorso verso la prossima release sono organizzati nel
[piano 44](44-core-release-plan.md), con verifiche distinte per modello completo,
migrations, operazioni e distribuzione.

**Correzione successiva:** il [report 49](49-grammar-corrections-and-audit.md)
ritira le aggiunte non concordate e distingue origine legacy, proposte di firma
e decisioni esplicite. Prevale sui contratti runtime proposti in questo testo.

**Decisione successiva sugli schemi:** [report 50](50-schemas-from-packages.md).
La configurazione dichiara solo package; gli schemi SQL vengono dedotti.

## 1. Criterio di completezza

La configurazione deve esprimere **tutto il modello** di `test_invoice_pg`:
`gnrcore:sys`, `gnrcore:adm`, `invc`. `adm` richiede `sys`, già presente.
Il [censimento di accettazione](43-test-invoice-model-coverage.md) comprende
75 modelli di tabella attesi e un contributo inter-package, tipi applicativi,
comportamenti e definizioni ereditate. Non basta esportare le tabelle `invc`.

Tre risultati distinti:

1. source componibile e serializzabile, con provenienza dei contributi;
2. modello risolto: tutti gli oggetti, anche virtuali e comportamentali;
3. proiezione fisica normalizzata per `asqueel-migration`.

Un attributo senza effetto DDL resta nel modello. Una dichiarazione non certifica un comportamento eseguibile. La grammatica
non impone provider inventati per le funzioni del legacy; il futuro rendering
dovrà segnalare gli effetti non implementati.
I rinvii espliciti sono nel [registro 41](41-deferred-features.md): `toolColumn`
e, dal 13 ottobre, l'implementazione dei record di sistema e di `release`.
Le firme `system_records` e `release` sotto riportate restano proposte non approvate.

## 2. Convenzioni comuni

Le firme seguenti usano `UNSET` per «non specificato» nei contributi.
I default descritti si applicano **dopo** la composizione; richiamare
`pkg.table('customer')` non reimposta i suoi attributi ai default.
`None` è un valore esplicito ammesso solo nei campi nullable; `False` disabilita
un'opzione; non sono sinonimi di `UNSET`. Liste e mappe sono copiate in ingresso.

`Name` è un identificatore logico non vuoto, senza `.`, `@`, `$` o separatori
di percorso. I nomi SQL espliciti sono singoli identificatori, sempre quotati
dal dialetto; non vengono interpretati come frammenti SQL. Riferimenti:
`package.table`, `package.table.column`; `table.column` è relativo al package
di dichiarazione. `@relation.column` è un percorso, `$column` un campo locale.

`Columns` accetta sequenza ordinata di nomi o stringa separata da virgole,
normalizzata a tupla. `Expr` è un'espressione strutturata oppure testo del
linguaggio Asqueel **proveniente da configurazione server fidata**. SQL specifico
del dialetto può essere conservato in questo profilo. Le ricette remote delle
operazioni hanno invece il contratto chiuso del documento 40: niente SQL libero.

Gli attributi descrittivi sono piatti: `name_long`, `name_short`, `comment`
e attributi con namespace espresso nel nome, per esempio `foo_bar_color='xx'`.
Non esistono un attributo-dizionario o un elemento `metadata`, né un contenitore
`x_ui`. Le firme con `**meta`/`**extra` conservano gli attributi con prefisso;
chi li usa estrae il gruppo tramite `extract_kwargs` di genro-toolbox.
`foo=True` estrae `bar_color`, `foo_bar=True` estrae `color`.
I prefissi strutturali già definiti conservano il proprio significato e perimetro.
Testi `!!` del legacy si conservano come valori traducibili.

La grammatica usa firme tipizzate. Estensioni tramite classi e costruttori
sono previste dal contratto 40; registro, versionamento e binding dei provider
non sono stati decisi. Le estensioni SQL del DB sono un'altra cosa.
Il core espone la grammatica anche per il montaggio in altri builder; la
riscrittura delle keyword `validate_*` resta locale ad Asqueel.

## 3. DB, connessioni e package; schemi dedotti

```python
from genro_bag.resolvers import EnvResolver

db = source.db('test_invoice_pg', implementation='postgresql')
db.connection('main', database='test_invoice_pg', host=EnvResolver('PGHOST'),
              user=EnvResolver('PGUSER'), password=EnvResolver('PGPASSWORD'))
packages = db.packages()
sys = packages.package('sys', sqlschema='sys', sqlprefix=True)
adm = packages.package('adm', sqlschema='adm', sqlprefix=True)
invc = packages.package('invc', sqlschema='invc', sqlprefix=True)
adm.options().requires('sys')
```

Si usano i resolver esistenti di genro-bag: `EnvResolver` per variabili di
processo, `BagCbResolver` per valori calcolati o letti dall'ambiente applicativo.
La source li conserva senza risolverli. Non occorre dichiarare un registro di
variabili nel DB. Un callback Python locale non diventa codice trasferibile
tramite JSON; serializzazione e binding remoto restano da definire.

| Firma | Default e regole |
| --- | --- |
| `source.db(name, *, implementation, **meta)` | Un DB per source; `name` identità logica, `database` nome fisico della connessione. Dialetto richiesto. |
| `db.connection(name='main', *, database=UNSET, dsn=UNSET, host=UNSET, port=UNSET, user=UNSET, password=UNSET)` | Connessioni nominate, stesso dialetto del DB. DSN e campi di connessione non possono essere definiti insieme. Resolver ammessi sui valori. Nessuna connessione aperta durante build/render. |
| `db.packages()`, `db.extensions()`, `node.options()` | Contenitori singleton, accesso ripetuto idempotente. |
| `packages.package(name, *, sqlschema=None, sqlprefix=True, **meta)` | `sqlschema` è direttamente il nome fisico, senza dichiarazione separata; `None` seleziona il default del dialetto. |
| `extensions.extension(name)` | Nome di estensione SQL; richiede capability del dialetto. Nessun import Python. |
| `pkg.table(name, *, pkey=UNSET, name_long=UNSET, name_short=UNSET, name_plural=UNSET, caption_field=UNSET, sqlname=None, sqlschema=None, **table_meta)` | I quattro attributi descrittivi sono sempre previsti nella grammatica della tabella. `sqlschema=None` eredita il mapping fisico del package; un override sceglie uno schema dedotto da un altro package. `sqlname` esplicito è il nome SQL completo della tabella. |

`sqlprefix=True` produce `<package>_<table>`, `False` produce `<table>`, una
stringa non vuota produce `<prefisso>_<table>`. Il separatore è aggiunto una
sola volta dal core; prefissi terminanti in `_` e stringa vuota sono rifiutati
per evitare due notazioni della stessa configurazione. Un `sqlname` esplicito
non riceve prefissi. Nessuna collisione fisica è ammessa, neppure fra package.

Il nome fisico completo è risolto prima delle FK. Gli schemi sono dedotti e deduplicati dai package, inclusi quelli vuoti.
Non esiste più un alias logico di schema distinto dal suo nome fisico. `db.table('invc.customer')` risolve il nome
logico; `db.package('invc')` e `db.schema('invc')` restituiscono oggetti diversi.
L'accesso runtime espone attributi in sola lettura; non torna alla source.

### Options per livello

| Livello | Vocabolario base proposto |
| --- | --- |
| DB | Contenitore options; nessuna option descrittiva dedicata |
| Connection | `driver(**parameters)` con vocabolario del driver selezionato |
| Package | `requires(*packages)`; `type(name, *, dtype, size=None, **column_defaults)` |
| Table | Catalogo §§5–9 |

Non c'è ereditarietà implicita delle options DB/package sulle tabelle.
`requires` valida dipendenze presenti nel modello; discovery e caricamento sono
responsabilità dell'host. I tipi locali hanno nomi qualificati; il nome breve
si risolve nel package, non in package arbitrari. La dichiarazione di macro
è esclusa dalla grammatica strutturale: nel legacy registerMacros/addMacro
appartengono alla configurazione del compilatore delle query, separata da
config_db. Le formule possono conservare riferimenti a macro senza espanderli.

`connection(options={...})` dell'API attuale si traduce in
`connection.options().driver(...)`. Non mantenere due dizionari con precedenze
implicite. La configurazione delle connessioni resta un artefatto amministrativo
separato dal modello trasferibile e dalle ricette delle operazioni: nell'export
pubblico compaiono solo identità e riferimenti ai resolver, mai segreti risolti.

## 4. Composizione dei contributi e oggetti

L'host passa un elenco ordinato di contributi identificati. Dentro un contributo
una seconda dichiarazione dello stesso elemento può completare attributi non
impostati; valori differenti per lo stesso attributo sono un errore. Tra
contributi prevale l'ultimo attributo **esplicitamente** impostato. Ripetere
un'opzione la aggiorna, non duplica colonne o hook. Liste sostituite interamente;
dict di personalizzazione dei campi e sezioni validation si uniscono per chiave.
Gli attributi con prefisso si compongono singolarmente, come gli altri attributi piatti.

`option(False)` disabilita l'opzione nel modello finale: le colonne che essa
genererebbe non vengono generate. Non rimuove una colonna dichiarata manualmente.
Le funzioni con parametri nominati usano `enabled=False`. La riattivazione usa
gli attributi espliciti accumulati; per ripartire dai default si usa
`options.reset('nome')`, che cancella la configurazione accumulata di quell'opzione.

Ordine: composizione → default → espansione options → risoluzione
tipi/riferimenti → validazione → oggetti. Le espansioni possono creare colonne
usate da dichiarazioni precedenti. Nessuna dipendenza dall'ordine fra
`sys_fields`, `hierarchical`, `auto_counter`. Cicli fra espansioni sono errori.

Un oggetto generato può essere completato con attributi compatibili; nome,
tipo e invarianti richiesti dall'opzione non possono essere alterati. Un cambio
di tipo di nodo, target incompatibili, gruppi duplicati incoerenti e nomi SQL
in conflitto danno errore con percorso e provenienza dei contributi.
Nessuna soppressione silenziosa di nodi che non entrano nel DDL.

Le classi applicative espongono `configure(self, pkg)`. Un contributo
`adm/model/_packages/sys/task.py` riceve il package **sys**:

```python
def configure(self, pkg):
    task = pkg.table('task')
    task.column('user_id').relation('adm.user.id', on_delete='raise')
```

La dichiarazione `behavior(...)` è ritirata insieme ai parametri `provider`.
Grammatica e traduzione non richiedono di anticipare il collegamento di classi,
metodi esecutivi o hook.
Un valore calcolato si può dichiarare con `BagCbResolver`, senza inventare un
registro di funzioni; costruire la source non esegue il callback.

## 5. Tabelle, colonne fisiche e validation

**Confermato nella revisione:** ogni tabella prevede come attributi standard
`name_long`, `name_short`, `name_plural` e `caption_field`, espliciti nella
firma di `pkg.table(...)`, senza passare da options o estensioni.
Nei contributi possono essere omessi (`UNSET`) per conservare i valori già
dichiarati, secondo le regole di composizione.

```python
tbl = pkg.table(
    'customer',
    pkey='id',
    name_long='Cliente',
    name_short='Cli.',
    name_plural='Clienti',
    caption_field='account_name',
)
```

`table_meta` aggiunge ai metadati comuni rimanenti:
`rowcaption`, `newrecord_caption`, `order_by`, `lookup=False`, `tabletype=None`.
Questi sono metadati tipizzati; `caption_field`/`order_by` si validano sul modello.
pkey_columns e pkey_columns_joiner restano attributi della tabella, come nel
legacy. La collocazione degli altri attributi va verificata singolarmente
secondo la regola di precedenza del legacy.

```text
tbl.column(name, dtype=None, *, size=None, sqlname=None,
           notnull=False, unique=False, indexed=False, sqldefault=None,
           sql_type=None, generated_expression=None, extra_sql=None,
           default=UNSET, default_from=None, sql_value=None,
           read_only=False, unmodifiable=False, group=None, **meta)
```

- `dtype=None`: `A` con size, altrimenti `T`; una relazione può inferire il tipo
  dal target quando non esplicitato. Tipo/size espliciti incompatibili sono errori.
- Codici fisici del checkout migratore: `A B C D DH DHZ DT H HZ I L M N O P R T
  TSV VEC X Z jsonb serial serial4`. `X` conserva la semantica Bag/XML, non JSON.
  Gli alias di package (es. `money`, `perc`) si espandono prima della proiezione.
- `size` conserva le notazioni legacy: lunghezza fissa `22`, massima `:50`,
  precisione e scala `14,2`. Normalizzazione secondo il migratore, validata per
  dtype; non interpretare `validate_len` come size SQL.
- `default` è un valore applicativo tipizzato; `default_from` un percorso nel
  modello; sono alternativi. `sqldefault` è default SQL. Non convertirli l'uno
  nell'altro. `sql_value` calcola il valore persistito nel piano di scrittura,
  con binding del record, e non è una generated column SQL.
- `generated_expression`, `sql_type`, `extra_sql` sono dichiarazioni server
  fidate vincolate al dialetto. Le combinazioni SQL illegali sono rifiutate.
- `read_only` esclude l'assegnazione applicativa ordinaria; `unmodifiable`
  permette l'inserimento ma impedisce modifiche successive. Hook interni restano
  soggetti ai contratti dell'opzione. I flags UI non sostituiscono questi controlli.
- `indexed=True` genera un indice semplice se non coperto da PK/UNIQUE/indice
  con lo stesso prefisso iniziale. `unique=True` produce un vincolo UNIQUE.

```python
col.validation(notnull=True, len='2:40')
# Stessa sezione, incorporata dalla sola grammatica Asqueel:
tbl.column('account_name', validate_notnull=True, validate_len='2:40')
```

**Decisione del 13 ottobre:** l'oggetto colonna espone `validations`, un dict
con i parametri dichiarati. La source conserva gli attributi `validate_*` piatti;
la traduzione li raggruppa con `@extract_kwargs(validate=True)`, togliendo solo
il prefisso. La forma esplicita `.validation(**rules)` resta disponibile:

```python
tbl.column('code', validate_notnull=True, validate_case='U',
           validate_notnull_error='Obbligatorio')
# Equivalente:
tbl.column('code').validation(notnull=True, case='U', notnull_error='Obbligatorio')
# Oggetto risultante:
column.validations == {'notnull': True, 'case': 'U', 'notnull_error': 'Obbligatorio'}
```

Controlli, trasformazioni e messaggi restano insieme. La sezione `normalize`
è rimossa; `*_error` mantiene il nome legacy, senza convertirlo in `messages`. I valori case (upper/u,
lower/l, title/t, capitalize/c, anche maiuscoli) sono conservati senza conversioni.
La costruzione/traduzione non esegue controlli né trasformazioni sui record;
validate_notnull non produce automaticamente un vincolo NOT NULL nel JSON DDL.
Le regex sono dati della regola, non espressioni da interpretare come Python
per validare la grammatica. La vista dict è separata dalla source e una sua
modifica non cambia il modello già tradotto.

**exist e nodup, 13 ottobre:** nel legacy usano bool o str.
Il nome legacy è `exist`, non `exists`; il nome SQL `exists` delle formule
resta distinto. La grammatica non impone questi nomi né questi tipi. `exist=False`/`nodup=False`, stringhe vuote e
riferimenti a campi sono conservati esattamente come dichiarati. Non vengono
risolti contro il modello durante questa traduzione.

```python
tbl.column('code', validate_exist='other.table.code', validate_nodup=True,
           validate_nodup_relative='parent_id', validate_nodup_error='Duplicato')
# Equivalente:
tbl.column('code').validation(exist='other.table.code', nodup=True,
                              nodup_relative='parent_id', nodup_error='Duplicato')
```

Si conservano i parametri legacy con prefisso `exist_`/`nodup_`, inclusi
messaggi, `_if`, `_warning`, `_iswarning`, `nodup_relative`, `nodup_condition`
e i parametri di query `nodup_*`. Nel legacy nodup inoltra questi ultimi al
conteggio: qui rimangono solo dati nel dict. Nessuna query, nessun UNIQUE/FK
implicito, nessun nuovo esecutore.

**Semplificazione concordata, 13 ottobre:** `validation(**rules)` conserva
nomi e valori senza un vocabolario chiuso e senza controlli sui tipi delle
singole regole. Vale anche per le source importate. L'embedding `validate_*`
toglie soltanto il prefisso. Non si inseriscono default, non si correggono
nomi e non si interpretano i valori. Le regole saranno esaminate quando
verranno usate: non occorre decidere ora una firma per ciascuna di esse.

**Differenza dal legacy approvata il 13 ottobre:** nel legacy `values` è un
attributo della colonna per le scelte disponibili, usato dai widget. In Asqueel
si sceglie invece `validate_values`, equivalente a `validation(values=...)`:
la dichiarazione dei valori ammessi appartiene a `column.validations['values']`.

```python
tbl.column('stato', validate_values='B:Bozza,C:Confermato,A:Annullato')
# Equivalente:
tbl.column('stato').validation(values='B:Bozza,C:Confermato,A:Annullato')
# Oggetto risultante:
column.validations == {'values': 'B:Bozza,C:Confermato,A:Annullato'}
```

Per ora si conserva il valore dichiarato senza interpretarlo. L'esecuzione
della regola e l'uso da parte dei widget saranno decisi quando serviranno;
questa scelta non introduce vincoli SQL né un vocabolario chiuso di validation.

`col.encryption(mode='X'|'R'|'Q')` registra i modi presenti in
`invc.customer`. La traduzione conserva il modo e la colonna fisica; non
definisce esecutori crittografici o collegamenti a provider.

## 6. Sys fields e generazione delle chiavi

```python
tbl = pkg.table('customer', pkey='id')
tbl.options().sys_fields(
    id=dict(type='uuid'), ins=True, upd=True,
    user_ins=True, user_upd=True, ldel=True, draft=False, syscode=False,
    group='zzz', group_name='System')
```

`sys_fields(enabled=False)` disattiva tutta l'opzione mantenendone la configurazione;
`enabled=True` la riattiva. `sys_fields()` usa questi default. `id=True` equivale al dict indicato, `False`
non aggiunge la colonna. `type` è enum di generazione, non dtype SQL; per ora
l'unico membro di questo enum del campo di sistema è `uuid`. Nessun `custom`.
Senza sys_fields la tabella deve dichiarare la propria pkey; con `id=True`,
`pkey` omessa diventa `id`. Una pkey esplicitamente diversa resta tale: il campo
`id`, se richiesto, è una colonna ordinaria con generatore.

| Opzione | Colonna fisica / default proposto |
| --- | --- |
| `id` | `id`, `A`, size `22`, UUID legacy, assegnazione prima dell'INSERT |
| `ins`, `upd` | `__ins_ts`, `__mod_ts`, `DHZ`, indicizzate; UTC dal contesto server |
| `user_ins`, `user_upd` | `__ins_user`, `__mod_user`, `T`; identità autenticata server oppure NULL |
| `ldel` | `__del_ts`, `DHZ`, indicizzata; inizialmente NULL |
| `draft` | `__is_draft`, `B`, indicizzata, inizialmente False |
| `syscode=False` | Se True aggiunge `__syscode`, `A`, size `:20`, indicizzata e UNIQUE; nessuna assegnazione automatica |

**Deciso il 13 ottobre:** `syscode` è un flag booleano indipendente da
system_records, che resta fuori perimetro. L'espansione avviene al render,
senza modificare la source, creare record o generare i virtuali di protezione
e invalidità dei record di sistema. La colonna resta nullable se non è una PK.
Tipo, size, indexed e UNIQUE incompatibili su una colonna già dichiarata
producono errore anziché essere sovrascritti. `syscode=False` non rimuove una
colonna esplicita; `enabled=False` disattiva anche questa espansione.

Per gli altri campi i dict accettano `name_long`, `name_short`, `comment`, `group`,
`indexed`; soltanto `id` accetta anche `type`.
Nomi, dtype, size del generatore, regole di assegnazione e contesto utente
non sono personalizzabili attraverso questi dict. `__record_pointer` è una
formula del modello anche con `id=False`, costruita dalla pkey effettiva.

Algoritmo UUID identico al legacy, senza dipendenza runtime da GenroPy:

```python
thread_id = str(_thread.get_ident())
uuid_bytes = uuid.uuid3(uuid.uuid1(), thread_id).bytes
value = base64.urlsafe_b64encode(uuid_bytes)[:22].replace(b'-', b'_').decode()
```

La generazione UUID concordata resta in `sys_fields(id={'type': 'uuid'})` e
appartiene all'esecuzione. La firma separata `column.generation` è stata ritirata:
`manual`, `sequence` e la precedenza rispetto a `new_pkey_value` non erano
decisioni acquisite (contratto 40). Non fissare ora un nuovo oggetto Generation.

`table(..., pkey_columns='campo1,campo2', pkey_columns_joiner=None)` conserva
gli attributi legacy per una singola chiave testuale persistita. Il separatore
assente o vuoto equivale a `_` nel legacy, che salta i valori None.
La grammatica conserva i dati senza calcolare la chiave o normalizzare i nomi
dei campi. `pkey_from` e il parametro `missing` sono ritirati.

`compositeColumn(..., columns=...)` invece rappresenta componenti SQL distinte;
non concatena valori persistiti. `table.pkey` è sempre un solo nome logico;
`table.pkeys` espone le componenti fisiche ordinate.

Ordine di default, normalizzazione, hook, generazione e validation, condivisione
del timestamp per operazione e comportamento RAW/bulk restano da definire nella
fase lettura/scrittura. La sequenza precedentemente indicata qui era una proposta,
non un contratto acquisito.

I timestamp di sistema sono DHZ, con scrittura in UTC come convenzione
decisa. Nessun parametro per scegliere DH/DHZ in questa fase. La traduzione
del modello stabilisce il tipo; non implementa il ciclo delle scritture.

`delete` resta fisica. Soft-delete e restore sono operazioni esplicite;
letture ordinarie escludono le righe con `__del_ts` valorizzato e richiedono
un'opzione esplicita autorizzata per includerle. I draft non sono esclusi
implicitamente: filtri pubblicazione sono policy applicative esplicite.
Queste scelte aggiuntive sono proposte operative, non risultati di test runtime.

## 7. Options comportamentali richieste dai modelli

**Stato implementativo, 13 ottobre:** il render espande le options strutturali
concordate e conserva le altre negli oggetti ([piano 51](51-source-to-live-objects-plan.md),
fasi 2–3). Restano esclusi gli effetti applicativi e i rinvii del registro 41.
Le firme effettive e i payload di disattivazione sono nella [grammatica generata](../grammar.md).

Tutte le seguenti opzioni entrano nel modello risolto e dichiarano gli oggetti
generati. Le funzioni ammettono `enabled=False`; i default
interni si applicano solo quando l'opzione viene attivata. Formule e nomi di
metodi restano dati; la costruzione degli oggetti non esegue tali metodi.
La grammatica non contiene
chiavi provider né riferimenti generici a esecutori futuri.

| Firma obiettivo | Effetto e riferimento concreto |
| --- | --- |
| `hierarchical(columns=(), *, parent='parent_id', root_id=False, virtual_roots=False, linked_to=None, depth=None, caption_field=None)` | Parent FK, `hierarchical_pkey`, `_parent_h_pkey`, coppie `hierarchical_<campo>`/`_parent_h_<campo>`, `child_count`, `hlevel`; la manutenzione dei discendenti resta alla futura esecuzione. `invc.product_type/product_group`, `adm.htag/menu`, `sys.widget`. |
| `auto_counter(scope=(), *, field='_row_count')` | `L`, ordine fra fratelli; scope può essere una FK, es. invoice_id. Con gerarchia scope parent e campi `_h_count`, `_parent_h_count`, `_h_sortcol`. La configurazione non alloca valori. |
| `relative_index(relation, *, field='_relidx')` | Indice relativo alla relazione e contributo differito al lato collegato; controparte del legacy relidx. |
| `dynamic_fields(*, templates=None)` | Genera `df_fields` X, `df_fbcolumns` L, `df_custom_templates` X, `df_colswidth` T; `subfields` della colonna diventa `col.dynamic_fields(source=ColumnRef)`. |
| `record_hash(*, field='__rec_md5', columns=None, algorithm='md5')` | Hash applicativo per confronto record, non sicurezza; rappresentazione legacy per preservare valori esistenti, esclude il campo hash e i campi di sistema. `adm.user`. |
| `full_update(*, field='__full_mod_ts')` | Timestamp DHZ per aggiornamenti anche del contenuto correlato dichiarato dal comportamento. Non attivo per default. |
| `audit(mode='full'|'lazy', *, version_field='__version')` | Campo versione L e dichiarazione del modo audit, incluso `sys.widget` lazy. |
| `system_records(...)` | Rinviata, firma non approvata (41, R-02). Il render rifiuta l'attivazione. Per la sola colonna indicizzata UNIQUE usare sys_fields(syscode=True). |
| `protection(*, rules=(), tag=None)` | Con tag: __protection_tag e __protected_by_tag come nel legacy. Rules è solo conservato, senza inferire espansioni. I quattro virtuali di base appartengono a sys_fields. |
| `release(...)` | Rinviata, firma non approvata (41, R-03); il render rifiuta l'attivazione. |
| `partition(name, *, field, value=None, required=False)` | Filtro/policy logica legata al contesto server; non partizionamento SQL. `customer.state` e `invoice.customer_state` usano un valore o un resolver esistente; preservare NULL e override autorizzati secondo policy dichiarata. |
| `tenant(*, field=None)` | Flag multi-tenant; copre `adm.counter.multi_tenant`. Non implica una nuova colonna fisica. |
| `retention(*, field, days)` | Registra politica `sys.error/task_execution`; scheduler esterno, nessuna cancellazione durante costruzione/migration. |
| `broadcast(*columns)` | Eventi di modifica, es. `adm.userobject`; dichiarazione senza invio di eventi. |
| `archive()` | Esportazione/archiviazione e contributi correlati, compresi file allegati. |
| `enabled_when(*, preference)` | Registra `checkpref` come capability applicativa, senza far scomparire lo schema fisico al cambiare di una preferenza. |
| `attachments(*, master)` | Espansione di AttachmentTable: colonne, FK, virtuali, counter e collegamento del master. `adm.htmltemplate_atc` non è una tabella vuota. |
| `numbering(field, *, parameters=None)` | Descrive il contatore applicativo, es. `counter_inv_number`; non confonderlo con `_row_count`. |

I nomi di metodi e le formule legacy sono conservati come dati; il render
non cerca o invoca metodi applicativi. System_records e release restano rinviati.
Diagnostica configurabile e invalidFields/invalidRelations non sono portati
in questa fase; la precedente firma diagnostics è rimossa (41, R-07).

Le virtuali di base di protezione/invalidità e record_pointer prima aggiunte da
sysFields non vanno perse: il profilo di traduzione le configura esplicitamente.
Il core non deve cercare convenzioni GenroPy in ogni classe applicativa.

La traduzione deve completare tutti gli effetti strutturali delle options
prima della proiezione DDL. Non richiede handler di storage, audit o altre
funzioni esecutive. Gli effetti non ancora traducibili vanno segnalati.

## 8. Colonne virtuali, gruppi e subtable

| Firma | Semantica |
| --- | --- |
| `formulaColumn(name, expression=None, *, select=None, exists=None, dtype=None, static=False, parameters=None, subqueries=None, handler=None, group=None, **meta)` | Una sola sorgente principale expression/select/exists/handler. Subqueries nominate componibili nell'espressione; parametri tipizzati legati allo scope. `sql_formula` alias di migrazione per expression, non seconda sorgente. |
| `aliasColumn(name, relation_path, *, dtype=None, static=False, group=None, **meta)` | Percorso verso colonna fisica o virtuale; eredita metadati target salvo override esplicito; rileva cicli. |
| `subQueryColumn(name, query=None, mode=None, dtype=None, group=None, **meta)` | Firma legacy confermata: query facoltativa nella source, mode senza enum chiusa, dtype e metadati di colonna. Query e mode sono conservati senza espansione SQL. |
| `pyColumn(name, *, method=None, required_columns=(), dtype=None, static=False, group=None, **meta)` | Nome del metodo e dipendenze esplicite come dati del modello; la dichiarazione non esegue il metodo né lo rende automaticamente traducibile in SQL. |
| `compositeColumn(name, columns, *, unique=False, static=True, group=None, **meta)` | Identità serializzata strutturalmente, componenti ordinate; PK/UNIQUE/FK multicolonna senza colonna SQL aggiuntiva. |
| `bagItemColumn(name, *, bagcolumn, itempath, dtype=None, group=None, **meta)` | Estrazione Bag/XML tipizzata; itempath è un percorso dati, non XPath SQL interpolato. |
| `colgroup(name, *, name_long=None, **col_defaults)` | Gruppo unico ordinato, default `col_*` dalle firme delle colonne; handle reindirizza i costruttori alla tabella. |
| `subtable(name, *, condition, parameters=None, **meta)` | Sottoinsieme logico della stessa tabella; niente tabella SQL. Filtri si compongono con policy. |

**Decisione del 13 ottobre — subQueryColumn:** mantenere la firma legacy:
query=None, mode=None e attributi di colonna, incluso dtype. Il default non è
`'scalar'`. Il legacy tratta specificamente json/xml e conserva gli altri
valori di mode in subquery_aggr: non si introduce un enum chiuso. La source
può ricevere query in un contributo successivo. La sua struttura interna è
il prossimo punto da rivedere; quanto segue resta proposta, non nuovo contratto
approvato dalla sola conferma di questa firma.

Esempio reale di invc.invoice, conservato come dichiarazione:

```python
tbl.subQueryColumn('max_row_price',
    query=dict(table='invc.invoice_row', columns='MAX($unit_price)',
               where='$invoice_id=#THIS.id'),
    dtype='N', name_long='Max Row Price')
```

Per le sottoquery: `query(table, *, columns=(), where=None, group_by=(),
having=None, order_by=(), limit=None, offset=None, distinct=False,
parameters=None)`. Anche dict con queste sole chiavi è ammesso. #THIS riferisce
il record esterno; `$` e `@` si risolvono nella tabella della query. I
`select_<nome>` legacy si normalizzano a `subqueries[nome]`; `var_<nome>` a
`parameters[nome]`, conservando valori e binding di contesto. I nomi di
sottoquery non sono i nomi delle macro registrate.

Una scalar deve produrre al massimo una riga: aggregate globale, unicità,
limit 1 ordinato oppure controllo d'errore in esecuzione. GROUP BY non garantisce
questa proprietà: `invc.invoice.duplicate_products` richiede una riscrittura a
conteggio dei gruppi o un errore esplicito, non scegliere una riga arbitraria.
JSON/XML rappresentano collezioni ordinate quando order_by è presente;
collezione vuota → contenitore vuoto, scalar vuota → NULL, exists vuota → False.

Le formule legacy SQL e le macro, incluse quelle del package, sono preservabili
nel profilo server fidato; compilazione/dialetto vengono verificati nel terzo
passo. `formulaColumn(sql_formula=True)` richiede ancora una scelta di binding;
non implica un nuovo registro di handler.
Il compilatore rifiuta capability mancanti, non converte testo SQL alla cieca.
`static` regola l'inclusione predefinita nel record, non la persistenza SQL.

## 9. Relations e virtual relations

### Relazioni basate su colonne

```text
col.relation(to, *, name=None, inverse=None, one_one=False,
             indexed=True, on_delete_sql=None, on_update_sql='cascade',
             deferrable=False, initially_deferred=False,
             on_delete=None, on_update=None, on_duplicate=None, **relation_meta)
col.weak_relation(to, *, name=None, inverse=None, one_one=False,
                  indexed=True, on_delete=None, on_update=None,
                  on_duplicate=None, **relation_meta)
```

`name=None` usa il nome colonna; `inverse=None` non pubblica un alias inverso,
ma il modello mantiene il collegamento inverso per dipendenze e ciclo scritture.
`relation_meta` aggiunge `one_name`, `many_name`, `one_group`, `many_group` ai
metadati comuni. `inverse` corrisponde al legacy `relation_name`, non al nome
della FK SQL. `constraint_name` è un ulteriore parametro solo di `relation`.

Sulle colonne virtuali `.relation(...)` è weak per default; una FK fisica
sulla virtuale resta vietata. L'alias senza relazione esplicita eredita nel renderer
la destinazione della relazione della colonna riferita, come weak; una relazione
esplicita prevale, anche quando un altro alias dipende da essa. Non eredita nomi
inversi, cardinalità inversa o azioni del ciclo record appartenenti alla colonna
originaria. Nessuna modifica della source e nessun indice/FK aggiunto per l'alias.

Per le dichiarazioni fisiche il profilo esistente di `relation` crea FK;
target fisico PK/UNIQUE e componenti compatibili obbligatori.
`weak_relation` non crea FK e accetta anche sorgenti virtuali scalari: il target
è dichiarato logicamente unico, assunzione da validare dall'applicazione.
Condizioni arbitrarie appartengono a virtualRelation, non a weak_relation.
`indexed=True` crea gli indici sorgente necessari e, per weak, anche target
fisico se non coperto. Non indicizzare una formula come fosse una colonna fisica.

Azioni SQL: `cascade`, `restrict`, `no_action`, `set_null`, `set_default`;
il producer le converte ai token uppercase del migratore. `None` non dichiara
un'azione SQL. `initially_deferred` richiede `deferrable`; legacy deferred=True
si traduce in entrambi True. `on_delete/on_update`: azioni applicative
`raise`, `cascade`, `set_null`, `ignore`, attuate dal ciclo RECORD. `on_duplicate`:
`copy`, `ignore`, `raise`; legacy False→ignore. Non proiettare queste azioni in
SQL per somiglianza del nome. Un runtime senza il ciclo richiesto deve rifiutarle.

`one_one=True` dichiara cardinalità al massimo uno sul lato inverso;
non aggiunge implicitamente UNIQUE alterando lo schema esistente. Se manca una
prova strutturale, la lettura scalare deve rilevare più righe e fallire.
L'autore può dichiarare UNIQUE per far rispettare la cardinalità dal database.
Questo è rilevante per `adm.htmltemplate` e `adm.group`.

### Relazioni virtuali di tabella

**Decisione del 13 ottobre:** riallineare la grammatica alla
[revisione della GEP 2](https://github.com/genropy/genropy_meta/issues/1#issuecomment-5803053743).
`aliasTable` è rinviato (41, R-04); `virtualRelation` resta, compresa la forma
con `relation`. Le inverse delle relazioni virtuali sono rinviate (41, R-05).
**Chiarimento del 16 ottobre:** le virtualRelation riguardano le relazioni
verso molti, non abbreviazioni di percorsi verso uno. Nelle proiezioni si usano
con il solo metodo di aggregazione `.aggr(...)`, secondo il
[documento 101](101-many-aggregation-decisions.md). Per gli alias verso uno vale
il [raccordo 100](100-alias-relation-inheritance.md).
Le raccolte `to_json` e `to_xml` seguono la selezione della query, incluse le
statiche; `to_xml` produce XML compatibile con Bag. L'ordine base della tabella
si applica automaticamente; `.order_by(...).aggr(...)` lo sostituisce nell'uso
in query, senza aggiungere `order_by` alla dichiarazione della virtualRelation.

**Semplificazione successiva approvata rispetto alla GEP:** anche `limit`,
`order_by` e `one_one` sono rinviati ed esclusi dalla firma (41, R-06).

```python
tbl.virtualRelation(name, relation=None, table=None, condition=None,
                    ask=None, **attrs)  # var_<nome> e metadati della grammatica
```

- `relation` identifica una relazione o un percorso esistente, anche virtuale.
  Può essere accompagnato da `condition` per dichiarare un filtro.
  Le derivazioni compongono le condizioni in AND tra parentesi; ciascun livello
  mantiene i propri `var_*`, manglizzati separatamente senza sovrascritture.
  Il raccordo è verificato nel [passo 109](109-derived-virtual-relations.md).
- `table` identifica la destinazione di un collegamento senza una relazione
  di partenza. Si usa in alternativa a `relation`. Richiede una `condition`
  non vuota nella source completa, dopo la composizione dei contributi. La
  condizione descrive l’intero collegamento, senza correlazioni aggiunte.
  Il raccordo è verificato nel [passo 110](110-direct-virtual-relations.md).
- In `condition`, `$campo` e `@rel.campo` appartengono alla destinazione B.
  `var_<nome>` contiene un'espressione della sorgente A e viene richiamato
  come `:var_<nome>`. Non si introduce `#THIS` in questa grammatica.
- `ask` è conservato nella dichiarazione ma rinviato dal lavoro corrente.
  Contesto, namespace provvisorio ed esempio sono nel
  [documento 108](108-deferred-virtual-relation-ask.md).
- `limit`, `order_by` e `one_one` non sono ammessi, anche nelle source
  importate. Non si dichiara una selezione dei primi N né una cardinalità
  scalare sulla virtualRelation. Query e subQueryColumn restano distinti.
- `source_parameters` e `parameters` sono rimossi dalla firma virtualRelation;
  nessuna conversione implicita di queste precedenti proposte.
- `inverse` è rimosso e non viene generata una relazione inversa virtuale.
  Questo non cambia `inverse` e la generazione delle inverse delle relazioni
  ordinarie. Non si sostituisce `inverse` con `reverse_name` o un'altra API.

I binding sono espressioni della futura riga sorgente, non valori da calcolare
al render della configurazione. Per ora source e traduzione conservano
condizione, binding e ask: nessuna query, nuova FK o vincolo.
Il collegamento dei riferimenti già presente nel modello accetta anche le
relazioni filtrate, senza eseguire o riscrivere il filtro.

Esempi dichiarativi di relazioni verso molti. Count, aggregati numerici, join, to_json e to_xml su
relazione di base con condition/var_* sono raccordati nel
[passo 106](106-xml-many-aggregates.md), incluso ordine base/override;
to_xml è disponibile solo su PostgreSQL. `ask` è rinviato (documento 108):

```python
# Relazione filtrata, dichiarata su customer:
tbl.virtualRelation('invoices_current_year', relation='@invoices',
                    condition='$year=:env_current_year')

# Collegamento diretto: non richiede una relazione ordinaria di partenza.
tbl.virtualRelation('invoices_direct', table='invc.invoice',
                    condition='$customer_id=:var_customer', var_customer='$id')
```

I precedenti esempi `virtualRelation('customer', relation='@invoice_id.@customer_id')`
e dell'alias scalare `discount_tier_id` non rappresentano usi approvati: il primo
è un'abbreviazione verso uno esclusa, il secondo non autorizza una cardinalità scalare. `table=` è compilato come
collegamento verso molti con `condition` obbligatoria e uso tramite `.aggr()`,
come descritto nel [passo 110](110-direct-virtual-relations.md).

Il ponte offline dalla source legacy espansa conserva ancora la `cnd` legacy
come espressione opaca nel suo profilo legacy: questa revisione non introduce
un riscrittore SQL generico di `cnd` verso la GEP. Conserva `relation_name`
e `one_one` nei metadati legacy senza attribuire loro effetti nella
virtualRelation e senza generare l’inversa `invoices_in_tier`.

**ask rinviato:** le decisioni provvisorie e i punti ancora aperti sono raccolti
nel [documento 108](108-deferred-virtual-relation-ask.md); non sono prerequisiti
del raccordo corrente delle virtualRelation.

La derivazione da una relazione limitata esce dal perimetro corrente insieme
a limit/order_by. Le inverse e la dichiarazione one_one restano rinviate.

## 10. Indici e proiezione verso il migratore

```text
tbl.index(name=None, *, columns, unique=False, method=None, where=None,
          tablespace=None, with_options=None)
```

`columns` è lista/stringa ordinata oppure mappa ordinata nome→None/`DESC`;
solo colonne fisiche in questa versione. Predicate e parametri avanzati sono
server-only, validati dal dialetto. `name` esplicito si proietta in `index_name`;
identità strutturale e hashing vengono dalle factory del migratore.
UNIQUE multicolonna si dichiara con compositeColumn(unique=True).
Non reintrodurre `constraint` generica come scappatoia senza grammatica.

Il producer opera **sugli oggetti risolti**, usando il contratto normalized
`format_version='1.0'` e le factory di `asqueel_migration.structures`.

| Modello risolto | Proiezione fisica |
| --- | --- |
| Database | `root.entity='db'`, entity_name del database fisico scelto; schemas/extensions/event_triggers |
| Schema, anche vuoto | Nodo schema con nome SQL; nessun package nel JSON fisico |
| Table | Nodo table e attributes.pkeys con nomi fisici ordinati separati da virgola; comment |
| Column fisica | dtype risolto, sql_type, size, notnull, sqldefault, unique, extra_sql, generated_expression, comment |
| PK | `_auto_` come notnull implicito secondo contratto producer; UNIQUE singola ridondante eliminata |
| Composite unique | Constraint multicolonna con identità prodotta dalla factory |
| Relation fisica | related_schema/table/columns risolti, azioni SQL, deferrability, constraint_name |
| Weak/virtual relation | Nessuna FK; eventuali indici fisici prodotti prima della proiezione |
| Options | Espansioni fisiche incluse; comportamenti/metadata restano nel modello |
| Virtuali/subtable/pyColumn | Nessuna colonna o tabella fisica |
| Extension | Nome estensione SQL; verifica capability del backend |

Non aggiungere chiavi private al JSON normalizzato. Il contratto corrente non
ha slot per commento schema: conservarlo nel modello ed esplicitare nel report
che non viene applicato al DB, invece di inventare un campo non consumato.
Views, CHECK arbitrari, funzioni e trigger SQL nativi richiedono un contratto
specifico successivo; preservare gli oggetti già presenti con il perimetro di
gestione del migratore, non rappresentarli come cancellazioni desiderate.

## 11. Verifiche di accettazione

La specifica è chiusa come proposta di grammatica quando ogni costruzione del
censimento ha una rappresentazione esplicita. L'implementazione è completata
solo con queste prove, ancora da realizzare:

1. Build completa dei tre package, eredità AttachmentTable e contributo
   adm→sys.task inclusi, con dichiarazioni e nomi fisici verificati.
2. JSON/XML del modello preservano tipi, options, relazioni, metadati e binding
   simbolici; nessuna credenziale o callable serializzato.
3. Proiezione normalized validata da StructureValidator, confronto con snapshot
   legacy reale e spiegazione di ogni differenza voluta (es. user_upd=True).
4. Migrazione su DB PostgreSQL temporaneo, rilettura schema e seconda diff vuota;
   **mai** applicare direttamente DDL a test_invoice_pg per questa verifica.
5. Test negativi su typo delle options, collisioni/override, parametri rimossi,
   source/target composite, scalar multiriga, limiti e inverse virtuali.
6. Esecuzione delle espressioni e dei comportamenti nel passo lettura/scrittura;
   compatibilità SQLite limitata a capability dichiarate, non presunta dal JSON.

Il censimento statico allegato controlla fonti e superficie sintattica. Non
sostituisce la build, il confronto con il DB o i test delle operazioni.
