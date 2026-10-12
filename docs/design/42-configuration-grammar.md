# 42 — Grammatica di configurazione del modello, prima specifica completa

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

Un attributo senza effetto DDL resta nel modello. Un comportamento richiesto
senza provider provoca un errore nominativo: non diventa un metadato inerte.
`toolColumn` resta l'unico rinvio esplicito nel [registro 41](41-deferred-features.md).

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

Ogni elemento nominato ammette metadati comuni: `name_long`, `name_short`,
`comment`, `x_ui` (mappa JSON) e `metadata` (mappe JSON con namespace).
La firma `**meta` nelle tabelle seguenti significa **questo elenco chiuso**,
non accettazione di kwargs arbitrari. I metadati non introducono comportamento.
Testi `!!` del legacy si conservano come valori traducibili.

La grammatica è un registro di firme tipizzate: un provider aggiunge nomi,
validatore, costruttore, versione e dipendenze. Una collisione con firme
registrate è un errore. Le estensioni SQL del DB sono un'altra cosa.
Il core espone la grammatica anche per il montaggio in altri builder; la
riscrittura delle keyword `validate_*` resta locale ad Asqueel.

## 3. DB, connessioni, schemi e package

```python
db = source.db('test_invoice_pg', implementation='postgresql')
db.connection('main', database='test_invoice_pg', host=resolver('db.host'),
              user=resolver('db.user'), password=resolver('db.password'))
schemas = db.schemas()
schemas.schema('sys')
schemas.schema('adm')
schemas.schema('invc')
packages = db.packages()
sys = packages.package('sys', sqlschema='sys', sqlprefix=True)
adm = packages.package('adm', sqlschema='adm', sqlprefix=True)
invc = packages.package('invc', sqlschema='invc', sqlprefix=True)
adm.options().requires('sys')
```

Esempio di sintassi obiettivo; `resolver` indica un riferimento a un resolver
registrato dall'host. Non leggere o incorporare credenziali per costruire il modello.

| Firma | Default e regole |
| --- | --- |
| `source.db(name, *, implementation, **meta)` | Un DB per source; `name` identità logica, `database` nome fisico della connessione. Dialetto richiesto. |
| `db.connection(name='main', *, database=UNSET, dsn=UNSET, host=UNSET, port=UNSET, user=UNSET, password=UNSET)` | Connessioni nominate, stesso dialetto del DB. DSN e campi di connessione non possono essere definiti insieme. Resolver ammessi sui valori. Nessuna connessione aperta durante build/render. |
| `db.schemas()`, `db.packages()`, `db.extensions()`, `node.options()` | Contenitori singleton, accesso ripetuto idempotente. |
| `schemas.schema(name, *, sqlname=None, **meta)` | `sqlname=None` usa `name`; schema di default del dialetto sempre disponibile. Gli altri vanno dichiarati. |
| `packages.package(name, *, sqlschema=None, sqlprefix=True, **meta)` | `sqlschema` riferisce lo schema logico; `None` seleziona quello di default. |
| `extensions.extension(name)` | Nome di estensione SQL; richiede capability del dialetto. Nessun import Python. |
| `pkg.table(name, *, pkey=UNSET, name_long=UNSET, name_short=UNSET, name_plural=UNSET, caption_field=UNSET, sqlname=None, sqlschema=None, **table_meta)` | I quattro attributi descrittivi sono sempre previsti nella grammatica della tabella. `sqlschema=None` eredita solo il mapping fisico del package. `sqlname` esplicito è il nome SQL completo della tabella. |

`sqlprefix=True` produce `<package>_<table>`, `False` produce `<table>`, una
stringa non vuota produce `<prefisso>_<table>`. Il separatore è aggiunto una
sola volta dal core; prefissi terminanti in `_` e stringa vuota sono rifiutati
per evitare due notazioni della stessa configurazione. Un `sqlname` esplicito
non riceve prefissi. Nessuna collisione fisica è ammessa, neppure fra package.

Il nome fisico completo è risolto prima delle FK. Package e schemi sono oggetti
distinti e sopravvivono anche vuoti. `db.table('invc.customer')` risolve il nome
logico; `db.package('invc')` e `db.schema('invc')` restituiscono oggetti diversi.
L'accesso runtime espone attributi in sola lettura; non torna alla source.

### Options per livello

| Livello | Vocabolario base proposto |
| --- | --- |
| DB | `context(name, dtype, *, required=False, default=None)`; `macro(name, *, handler, parameters)`; `metadata(namespace, values)` |
| Connection | `driver(**parameters)` con vocabolario del driver selezionato; `metadata(namespace, values)` |
| Schema | `metadata(namespace, values)`; ulteriori funzioni tramite provider dichiarati |
| Package | `requires(*packages)`; `type(name, *, dtype, size=None, **column_defaults)`; `macro(name, *, handler, parameters)`; `metadata(namespace, values)` |
| Table | Catalogo §§5–9; `metadata(namespace, values)` |

Non c'è ereditarietà implicita delle options DB/schema/package sulle tabelle.
`requires` valida dipendenze presenti nel modello; discovery e caricamento sono
responsabilità dell'host. Un macro-handler è un riferimento simbolico registrato
sul server, mai codice da eseguire ricevuto dal client. Tipi e macro locali hanno
nomi qualificati; il nome breve si risolve nel package, non in package arbitrari.

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
Per `metadata`/`x_ui` merge per namespace/chiave, senza merge ricorsivo arbitrario.

`option(False)` disabilita l'opzione nel modello finale: le colonne che essa
genererebbe non vengono generate. Non rimuove una colonna dichiarata manualmente.
Le funzioni con parametri nominati usano `enabled=False`. La riattivazione usa
gli attributi espliciti accumulati; per ripartire dai default si usa
`options.reset('nome')`, che cancella la configurazione accumulata di quell'opzione.

Ordine: composizione → default → espansione options/provider → risoluzione
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

I metodi applicativi si collegano con `tbl.options().behavior('registry.key')`.
Il registro risolve una classe server con metodi nominati (`new_pkey_value`,
default, hook e calcoli); il modello serializza il riferimento e i contratti,
non l'istanza Python. Nessun import arbitrario indotto dalla deserializzazione.

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
Gli attributi legacy con effetti (audit, partition, pkey_columns, ecc.) sono
options esplicite, secondo la matrice del documento 43.

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

Vocabolario validation: `notnull: bool`, `len: int | 'min:max'`, `min`, `max`
(valori confrontabili col dtype), `regex: str`, `email: bool`, `values: list`,
`nodup: bool`, `exists: ColumnRef`, `messages: dict[rule,str]`.
`len` conta caratteri Unicode, estremi inclusivi; `:max`/`min:` ammessi.
Valore NULL salta gli altri controlli salvo `notnull`; stringa vuota è mancante
per `notnull`. `validate_notnull_error` si normalizza a `messages['notnull']`.
Regole sconosciute, intervalli invertiti e flags di tipo scorretto sono errori.

`col.normalize(case='upper'|'lower'|'title'|None, trim=False)` separa trasformazioni
e controlli; `validate_case` è alias di compatibilità locale per `normalize.case`.
`values` legacy con etichette si separa in valori ammessi e metadati UI.
`nodup`/`exists` richiedono server; `nodup` non promette unicità concorrente senza
UNIQUE. Ogni regola esporta capability e versione. Il client Gramlot esegue solo
quelle supportate con uguale semantica (incluso profilo regex); tutte sono
rieseguite sul server. Non esportare callback Python/JavaScript come validation.

`col.encryption(mode='X'|'R'|'Q', *, provider)` rappresenta i modi già presenti
in `invc.customer`. Il provider dichiara trasformazioni in scrittura/lettura,
ricerca, formato persistito e dipendenze; deve rispettare il contratto legacy
del modo scelto. Chiavi e materiale crittografico sono risolti solo sul server.
Il modello registra il modo; il DDL vede la colonna fisica risultante. Non
promettere portabilità fra provider solo perché usano la stessa lettera.

## 6. Sys fields e generazione delle chiavi

```python
tbl = pkg.table('customer', pkey='id')
tbl.options().sys_fields(
    id=dict(type='uuid'), ins=True, upd=True,
    user_ins=True, user_upd=True, ldel=True, draft=False,
    timestamp_type='DHZ', group='zzz', group_name='System')
```

`sys_fields()` usa questi default. `id=True` equivale al dict indicato, `False`
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

I dict dei campi accettano `name_long`, `name_short`, `comment`, `group`,
`x_ui`, `metadata`, `indexed`; soltanto `id` accetta anche `type`.
Nomi, dtype, size del generatore, regole di assegnazione e contesto utente
non sono personalizzabili attraverso questi dict. `__record_pointer` è una
formula del modello anche con `id=False`, costruita dalla pkey effettiva.

Algoritmo UUID identico al legacy, senza dipendenza runtime da GenroPy:

```python
thread_id = str(_thread.get_ident())
uuid_bytes = uuid.uuid3(uuid.uuid1(), thread_id).bytes
value = base64.urlsafe_b64encode(uuid_bytes)[:22].replace(b'-', b'_').decode()
```

Una chiave fornita non viene sostituita. La generazione avviene in esecuzione,
mai durante build, render o compilazione della ricetta. Per una pkey mancante,
`new_pkey_value(self, record)` registrato dal comportamento applicativo precede
il generatore dichiarato; senza hook/generatore si produce errore. I tipi
numerici non attivano implicitamente `MAX()+1`; `serial` usa il server SQL.
Le tabelle legacy con id manuale senza sys_fields richiedono un generatore
esplicito: `col.generation(type='uuid')`; `type='manual'` richiede input,
`type='sequence', sequence=None` delega a una sequence/default DB dichiarato.
`id.type='uuid'` si normalizza allo stesso oggetto Generation della colonna.

`tbl.options().pkey_from(columns, *, joiner='_', missing='error')` genera una
**singola chiave testuale persistita**. `missing='skip'` riproduce il caso legacy
che salta i valori None; non garantisce assenza di collisioni, controllate dalla
PK. I riferimenti `$campo` sono normalizzati; non modificare i valori esistenti
al cambio di sintassi. Questa opzione è alternativa a un generatore sulla pkey.
Per `adm.user_config`, il comportamento `new_pkey_value` sostituisce `pkeyValue`.

`compositeColumn(..., columns=...)` invece rappresenta componenti SQL distinte;
non concatena valori persistiti. `table.pkey` è sempre un solo nome logico;
`table.pkeys` espone le componenti fisiche ordinate.

Ordine di scrittura obiettivo: default → normalizzazione → hook applicativi
before → calcoli e generazione → validation e invarianti → SQL → hook after.
Le modifiche dei before vengono validate; gli after restano nella transazione.
Gli aggiornamenti automatici usano un timestamp coerente per operazione.
`timestamp_type='DHZ'` è il nuovo default; `'DH'` è ammesso esplicitamente per
rappresentare gli schemi legacy configurati senza timezone. In quel profilo
il provider deve dichiarare la timezone usata per convertire a valori naive;
il cambio di tipo non è una normalizzazione innocua dei dati già persistiti.
RAW salta default/hook/validation applicativi, richiede record fisici completi,
non genera UUID; restano vincoli DB e autorizzazione dell'esecutore. Un'API bulk
RECORD applica il medesimo ciclo RECORD, non un bypass RAW accidentale.

`delete` resta fisica. Soft-delete e restore sono operazioni esplicite;
letture ordinarie escludono le righe con `__del_ts` valorizzato e richiedono
un'opzione esplicita autorizzata per includerle. I draft non sono esclusi
implicitamente: filtri pubblicazione sono policy applicative esplicite.
Queste scelte aggiuntive sono proposte operative, non risultati di test runtime.

## 7. Options comportamentali richieste dai modelli

Tutte le seguenti opzioni entrano nel modello risolto e dichiarano gli oggetti
generati. Le funzioni salvo `behavior` ammettono `enabled=False`; i default
interni si applicano solo quando l'opzione viene attivata. Gli effetti richiesti
devono essere realizzati dal core o da un provider registrato, mai ignorati.

| Firma obiettivo | Effetto e riferimento concreto |
| --- | --- |
| `behavior(reference)` | Collega metodi applicativi registrati, default e trigger Python; non trigger SQL. |
| `hierarchical(columns=(), *, parent='parent_id', root_id=False, virtual_roots=False, linked_to=None, depth=None, caption_field=None)` | Parent FK, `hierarchical_pkey`, `_parent_h_pkey`, coppie `hierarchical_<campo>`/`_parent_h_<campo>`, `child_count`, `hlevel`; manutenzione discendenti, rifiuto cicli. `invc.product_type/product_group`, `adm.htag/menu`, `sys.widget`. |
| `auto_counter(scope=(), *, field='_row_count')` | `L`, ordine fra fratelli; scope può essere una FK, es. invoice_id. Con gerarchia scope parent e campi `_h_count`, `_parent_h_count`, `_h_sortcol`. Allocazione concorrente protetta, non MAX senza lock. |
| `relative_index(relation, *, field='_relidx')` | Indice relativo alla relazione e contributo differito al lato collegato; controparte del legacy relidx. |
| `dynamic_fields(*, templates=None)` | Genera `df_fields` X, `df_fbcolumns` L, `df_custom_templates` X, `df_colswidth` T; `subfields` della colonna diventa `col.dynamic_fields(source=ColumnRef)`. |
| `record_hash(*, field='__rec_md5', columns=None, algorithm='md5')` | Hash applicativo per confronto record, non sicurezza; codec legacy del provider per preservare valori esistenti, esclude il campo hash e i campi di sistema. `adm.user`. |
| `full_update(*, field='__full_mod_ts')` | Timestamp DHZ per aggiornamenti anche del contenuto correlato dichiarato dal comportamento. Non attivo per default. |
| `audit(mode='full'|'lazy', *, version_field='__version', provider)` | Versione L e integrazione audit, incluso `sys.widget` lazy; backend nominato. |
| `system_records(*, records, masterfield=None, tag='superadmin')` | `__syscode` A `:20` UNIQUE, protezione associata; records è mappa codice→valori o riferimenti registrati. `adm.language/xgroup/htag`; `adm.install_checklist` dichiara invece `__syscode` direttamente. Non inserisce dati al render né nel JSON DDL. |
| `protection(*, rules=(), tag=None)` | Espressioni/callback registrati e virtuali `__protecting_reasons`, `__is_protected_row`; nessuna esecuzione remota di codice. |
| `diagnostics(*, rules=(), invalid_fields=False, invalid_relations=())` | Reasons/flags virtuali; quando richiesti `__warnings`, `__errors`, `__invalid_fields` fisici e aggregazione delle relazioni. |
| `release(*, handlers)` | `__release` L e riferimenti alle trasformazioni `_release_*`. |
| `partition(name, *, field, context, required=False)` | Filtro/policy logica legata al contesto server; non partizionamento SQL. `customer.state` e `invoice.customer_state` condividono `invc_state`; preservare NULL e override autorizzati secondo policy dichiarata. |
| `tenant(*, context, field=None, provider)` | Scope tenant esplicito, risolto dal server; copre `adm.counter.multi_tenant`. Non inventa una colonna se il provider legacy usa store/schema. |
| `retention(*, field, days, provider)` | Registra politica `sys.error/task_execution`; scheduler esterno, nessuna cancellazione durante costruzione/migration. |
| `broadcast(*columns, provider)` | Eventi di modifica, es. `adm.userobject`; consegna esterna dopo commit, non invio dalla configurazione. |
| `archive(*, provider)` | Esportazione/archiviazione e contributi correlati, compresi file allegati. |
| `enabled_when(*, preference, provider)` | Registra `checkpref` come capability applicativa, senza far scomparire lo schema fisico al cambiare di una preferenza. |
| `attachments(*, master, provider)` | Espansione di AttachmentTable: colonne, FK, virtuali, counter e collegamento del master. `adm.htmltemplate_atc` non è una tabella vuota. |
| `numbering(field, *, provider, parameters=None)` | Descrive il contatore applicativo, es. `counter_inv_number`; non confonderlo con `_row_count`. |

Il bridge legacy deve rendere esplicite le funzioni prima attivate cercando
metodi (`sysRecord_*`, `_release_*`, formule `True`, defaultValues, trigger).
Le tre famiglie protection/diagnostics/record_pointer prima aggiunte da
sysFields non vanno perse: il profilo di traduzione le configura esplicitamente.
Il core non deve cercare convenzioni GenroPy in ogni classe applicativa.

Gli handler esterni (storage, preference, cifratura, audit, ecc.) sono contratti
richiesti dal modello; implementare le app `sys`/`adm` non è compito del core.
La build per sola ispezione può elencare capability non disponibili, ma non
marcare quel modello eseguibile. La proiezione DDL richiede tutte le espansioni
fisiche risolte; non può saltare un provider che genera colonne.

## 8. Colonne virtuali, gruppi e subtable

| Firma | Semantica |
| --- | --- |
| `formulaColumn(name, expression=None, *, select=None, exists=None, dtype=None, static=False, parameters=None, subqueries=None, handler=None, group=None, **meta)` | Una sola sorgente principale expression/select/exists/handler. Subqueries nominate componibili nell'espressione; parametri tipizzati legati allo scope. `sql_formula` alias di migrazione per expression, non seconda sorgente. |
| `aliasColumn(name, relation_path, *, dtype=None, static=False, group=None, **meta)` | Percorso verso colonna fisica o virtuale; eredita metadati target salvo override esplicito; rileva cicli. |
| `subQueryColumn(name, query, *, mode='scalar', dtype=None, group=None, **meta)` | `scalar`, `json`, `xml`; query strutturata con colonne, where, group_by, having, order_by, limit, offset, distinct, parametri. |
| `pyColumn(name, *, method=None, required_columns=(), dtype=None, static=False, group=None, **meta)` | Default method `pyColumn_<name>`, riferimento al behavior; dipendenze esplicite, solo post-fetch salvo provider che compili. Non filtrabile/ordinabile SQL per magia. |
| `compositeColumn(name, columns, *, unique=False, static=True, group=None, **meta)` | Identità serializzata strutturalmente, componenti ordinate; PK/UNIQUE/FK multicolonna senza colonna SQL aggiuntiva. |
| `bagItemColumn(name, *, bagcolumn, itempath, dtype=None, group=None, **meta)` | Estrazione Bag/XML tipizzata; itempath è un percorso dati, non XPath SQL interpolato. |
| `colgroup(name, *, name_long=None, **col_defaults)` | Gruppo unico ordinato, default `col_*` dalle firme delle colonne e x_ui; handle reindirizza i costruttori alla tabella. |
| `subtable(name, *, condition, parameters=None, **meta)` | Sottoinsieme logico della stessa tabella; niente tabella SQL. Filtri si compongono con policy. |

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
passo. `formulaColumn(sql_formula=True)` diventa handler registrato esplicito.
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

`relation` crea FK; target fisico PK/UNIQUE e componenti compatibili obbligatori.
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

```text
tbl.virtualRelation(name, *, relation=None, table=None,
                    condition=None, parameters=None, source_parameters=None,
                    ask=None, order_by=(), limit=None, one_one=False,
                    inverse=None, **meta)
```

- Esattamente uno fra `relation` (percorso esistente) e `table` (target logico).
  Nessuna colonna o FK SQL. Navigazione con `@name`, sola lettura.
- `source_parameters` associa un nome a un'espressione sul record sorgente;
  `parameters` contiene costanti; `ask` è mappa nome→specifica tipizzata per
  input esplicito dell'operazione. Namespace disgiunti, tutti i placeholder
  devono essere risolti; niente input che si spaccia per contesto autenticato.
- Nel target `condition` usa `$campo`, `@percorso`, `:parametro`. Per `table`
  deve esserci un legame al record sorgente. `relation` eredita il legame e
  aggiunge il filtro. Nessuna estrazione ingenua di termini da OR.
- `limit` intero positivo, ordinamento deterministico completato con PK target.
  `limit=1` restituisce zero/una riga; senza limit, `one_one=True` è un'asserzione
  con controllo di cardinalità, non una selezione arbitraria del primo match.
- Derivare da una relazione già limitata non cambia il significato del limite:
  per questa prima grammatica è errore; dichiarare esplicitamente una nuova
  relazione dal target. Cicli fra definizioni virtuali sono errori; FK cicliche
  fra tabelle restano valide.
- Inversa automatica solo per pairing puro invertibile, senza filter/ask/limit.
  Negli altri casi va dichiarata una seconda virtualRelation esplicita.
  Nessun alias inverso ingannevole su una relazione filtrata per sorgente.
- Collezioni many richiedono aggregazione/subquery/unnest esplicito in una
  proiezione scalare; non moltiplicano silenziosamente i record del chiamante.
  NULL nelle uguaglianze segue SQL; null-safe va richiesto con operatore esplicito.

Traduzione del join condizionale realmente presente in `invc.invoice`:

```python
tbl.virtualRelation('discount_tier', table='invc.discount_tier',
    condition='$customer_type_code=:customer_type AND '
              '$min_amount<=:amount AND $max_amount>:amount',
    source_parameters={'customer_type': '@customer_id.customer_type_code',
                       'amount': '$total'},
    one_one=True)
tbl.aliasColumn('discount_tier_id', '@discount_tier.id')
```

Intervalli sovrapposti causano errore di cardinalità: non sono resi univoci
da `one_one`. Il vecchio inverso `invoices_in_tier` richiede una relazione
virtuale esplicita sul tier con il pairing opposto. `aliasTable('customer',
relation_path='@invoice_id.@customer_id')` si rappresenta con
`virtualRelation('customer', relation='@invoice_id.@customer_id')`.
`joinColumn` e `aliasTable` sono quindi costrutti di traduzione, non due nuovi
tipi di colonna da introdurre nel core.

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
   adm→sys.task inclusi, con provider e nomi fisici verificati.
2. JSON/XML del modello preservano tipi, options, relazioni, metadati e binding
   simbolici; nessuna credenziale o callable serializzato.
3. Proiezione normalized validata da StructureValidator, confronto con snapshot
   legacy reale e spiegazione di ogni differenza voluta (es. user_upd=True).
4. Migrazione su DB PostgreSQL temporaneo, rilettura schema e seconda diff vuota;
   **mai** applicare direttamente DDL a test_invoice_pg per questa verifica.
5. Test negativi su typo delle options, collisioni/override, provider assenti,
   source/target composite, scalar multiriga, limiti e inverse virtuali.
6. Esecuzione delle espressioni e dei comportamenti nel passo lettura/scrittura;
   compatibilità SQLite limitata a capability dichiarate, non presunta dal JSON.

Il censimento statico allegato controlla fonti e superficie sintattica. Non
sostituisce la build, il confronto con il DB o i test delle operazioni.
