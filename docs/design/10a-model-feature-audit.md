# Audit delle funzionalità del modello: dichiarazione ed esecuzione

## Conclusione

`aliasColumn` è un requisito fondamentale mancante, non un dettaglio cosmetico:
la grammatica lo accetta, ma il modello operativo lo rifiuta. Il problema riguarda
anche `subQueryColumn`, `pyColumn` e le forme `select`/`exists` di `formulaColumn`.
Il nuovo strato applicativo configura correttamente oggetti vivi, ma passa ancora
attraverso quel resolver: il renderer a oggetti non completa automaticamente la
semantica delle dichiarazioni.

Occorre valutare ogni funzionalità attraverso quattro passaggi distinti:
dichiarazione, risoluzione del modello, compilazione, esecuzione. La possibilità
di serializzare una dichiarazione o conservarne gli attributi non dimostra che
il comportamento sia implementato.

## Perimetro e fonti

Audit del 29 settembre 2026, sul legacy alla revisione
`fa35e5adfa6ad1b269f3a22a9b12c4c1ee6513ea` e sul nuovo repository alla revisione
`b023a9bb25f3135ad1a10fb17a485eac27cf4237`, che include lo strato applicativo
e gli hook update/delete. Non sono stati modificati sorgenti durante questo audit.

Nelle citazioni `L:` indica un percorso relativo a
`/Users/gporcari/Sviluppo/Genropy/genropy`; `N:` un percorso relativo a questo
repository. I numeri identificano righe dei sorgenti letti. L'analisi comprende
letture mirate di model, columns, table, obj, containers e resolvers legacy,
controlli sul compiler/fetch e alcuni modelli applicativi. Non costituisce un
censimento di tutte le applicazioni, adapter o estensioni legacy.

I tre file modificati localmente sotto `projects/test_invoice` non sono usati
come prova di diffusione nei modelli reali: gli esempi sottostanti provengono da
`projects/gnrcore`. Per subtables e subQueryColumn le conclusioni si basano sul
sorgente del motore; la ricerca mirata non ha trovato esempi gnrcore sufficienti
a dimostrarne la diffusione applicativa.

## Matrice della copertura attuale

Legenda: **sì** = percorso presente; **parziale** = sottoinsieme esplicito;
**no** = manca o viene rifiutato. La colonna esecuzione indica il percorso
raggiungibile nel codice, non una nuova prova PostgreSQL effettuata in questo audit.

| Funzionalità | Dichiarazione nuova | Resolve/model | Compiler | Esecuzione e proiezione fisica |
| --- | --- | --- | --- | --- |
| Colonna fisica | Sì | Sì, dtype/naming/UI | Lettura e DML | Sessione nativa e DDL |
| aliasColumn | Sì, relation_path | **No: errore** | Nessuna semantica alias dedicata | Non raggiungibile dal modello dichiarato |
| formulaColumn con sql_formula | Sì | Sì, formula testuale | Espansione ricorsiva, cicli, riferimenti | Lettura SQL; scrittura vietata; esclusa DDL |
| formulaColumn con select/exists | Sì, tipizzati stringa | **No: errore** | Nessun sottopiano dedicato | Non raggiungibile |
| Formula con var_/select_ e macro legacy | Non equivalente; extras richiedono x_ | Solo SQL testuale | Non espande i contratti legacy | Non compatibile per semplice copia |
| subQueryColumn | Sì, query stringa/mode | **No: errore** | Nessuna correlazione/aggregazione strutturata | Non raggiungibile |
| pyColumn | Sì | **No: errore** | Nessun piano post-fetch | Nessuna valutazione Python delle colonne |
| Relazione uscente to-one semplice/composita | Sì | Sì, target univoco | LEFT JOIN riusabile in SELECT | Lettura; DDL FK solo se richiesto |
| Relazione inversa/back_reference | Attributo dichiarabile | Solo metadata/validazione nomi | Nessuna relazione inversa generata | Nessuna navigazione inversa operativa |
| Relazione case_insensitive | Attributo dichiarabile | **No: errore** | Non implementata | Non raggiungibile |
| Virtual relation/join condition | Non esiste equivalente completo | x_virtualRelation rifiutato | Chiavi formula rifiutate | Non raggiungibile |
| Alias di tabella/percorso | Nessun elemento dedicato | No | No espansione tableAlias | No |
| Subtable filtro nominato | Nessun elemento dedicato | x_subtable rifiutato | No | No |
| Subtable con maintable/discriminatore | Nessun elemento dedicato | No | No | Nessun mapping condiviso equivalente |
| Naming fisico | x_sql_schema/prefix/name | Sì, risolto staticamente | Identifier fisici comuni | Usato anche nella proiezione DDL |
| UI e identità colonna | x_ui/x_identity e overlay resolve | Sì | ResultColumn trasporta UI/source | Disponibili a lettura e oggetti; escluse DDL |
| Partition/draft/deletion logici | Attributi x_ del profilo nativo | Sì, RowPolicies | Guard e predicati | Non equivalgono alle partition fisiche SQL |

Fonti nuove principali: `N:src/genro_sql/elements.py:258`, `:275`, `:295`, `:312`,
`:390`; `N:src/genro_sql/model.py:32`, `:45`, `:54`, `:63`, `:105`;
`N:src/genro_sql/compiler.py:292`, `:308`, `:410`, `:479`;
`N:src/genro_sql/projection.py:11`, `:43`, `:146`.

## Prove riproducibili sul percorso dichiarazione → compiler

Prova offline effettivamente eseguita: creare `SqlBuilder`, una tabella `p.t`
con PK `id`, aggiungere una virtuale `v` a `table.virtual_columns()`, chiamare
`resolve_model(builder)` e poi `PostgresCompiler(model).select('p.t', columns='$v')`.

| Dichiarazione di v | Risultato osservato |
| --- | --- |
| aliasColumn(relation_path='@other_id.name') | UnsupportedFeatureError: p.t.v: aliasColumn |
| formulaColumn(sql_formula='$id + 1', dtype='I') | SELECT ("t0"."id" + 1) AS "v" FROM "p"."t" AS "t0" |
| formulaColumn(select='SELECT 1') | UnsupportedFeatureError: p.t.v: formulaColumn |
| subQueryColumn(query='SELECT 1') | UnsupportedFeatureError: p.t.v: subQueryColumn |
| pyColumn(py_method='calc') | UnsupportedFeatureError: p.t.v: pyColumn |

L'alias della prova viene rifiutato prima della validazione del target: dimostra
il blocco sul tipo, non la correttezza del percorso di relazione dell'esempio.
Non è stata avviata una connessione per queste prove.

## Alias: contratto fondamentale da completare

Nel legacy `aliasColumn()` crea una virtual column con `relation_path`.
`DbTableObj.column()` distingue colonna fisica, virtuale e percorso di relazione;
per un alias risolve la colonna di destinazione e restituisce un
`AliasColumnWrapper`. Il wrapper parte dagli attributi della destinazione e applica
quelli dell'alias, delegando altre proprietà all'oggetto originale. Il compiler
espande il percorso relativo al contesto della tabella corrente.

Fonti: `L:gnrpy/gnr/sql/gnrsqlmodel/model.py:1027`;
`L:gnrpy/gnr/sql/gnrsqlmodel/table.py:514`, `:599`;
`L:gnrpy/gnr/sql/gnrsqlmodel/columns.py:342`;
`L:gnrpy/gnr/sql/gnrsqldata/compiler.py:373`.

Esempi reali: `adm.user_tag` dichiara alias `user` e `fullname` su `@user_id`;
`sys.task_execution` espone `task_table` e `task_name` su `@task_id`.
Fonti: `L:projects/gnrcore/packages/adm/model/user_tag.py:14`;
`L:projects/gnrcore/packages/sys/model/task_execution.py:24`.

Non basta convertirlo in una stringa formula e considerare il lavoro terminato.
Il contratto minimo nativo deve definire:

- Identità propria dell'alias e provenienza della colonna bersaglio.
- Ereditarietà di dtype, dimensioni e UI, con override dell'alias e overlay finale.
- Percorsi to-one su più livelli, errori per destinazioni mancanti e cicli.
- LEFT JOIN e comportamento NULL quando manca la riga collegata.
- Riutilizzo dello stesso join per alias e riferimento diretto equivalente.
- Accesso uniforme in SELECT, WHERE, ORDER BY e attraverso SqlColumn.
- Sola lettura e assenza dalla proiezione DDL, senza dipendere dal fatto che una
  virtuale possieda necessariamente `formula is not None`.

Quest'ultimo punto è trasversale: attualmente SqlColumn decide il percorso di
configurazione usando proprio `model.formula`; il compiler e la proiezione usano
lo stesso discriminante per distinguere fisico e virtuale. Introdurre altri tipi
richiede un contratto esplicito, non solo un nuovo ramo nel parser.
Fonti: `N:src/genro_sql/application_table.py:67`;
`N:src/genro_sql/compiler.py:295`, `:485`;
`N:src/genro_sql/projection.py:43`.

## Formule e subquery: non confondere testo SQL e specifica strutturata

Il legacy consente sql_formula, select, exists e template `select_<nome>`;
una specifica di subquery può essere un dizionario o il nome di un metodo che
produce quel dizionario. Supporta correlazione `#THIS`, cast e variabili locali
`var_`; una formula `True` può chiamare `sql_formula_<campo>`.

Fonti: `L:gnrpy/gnr/sql/gnrsqlmodel/model.py:1231`;
`L:gnrpy/gnr/sql/gnrsqldata/compiler.py:390` fino al ramo Python a `:440`.

Non sono solo possibilità teoriche: `adm.group.group_tags` usa `select_tg` e
`#THIS.code`; `adm.userobject.system_userobject` usa `var_scode`.
Fonti: `L:projects/gnrcore/packages/adm/model/group.py:18`;
`L:projects/gnrcore/packages/adm/model/userobject.py:34`.

Nel nuovo modello è operativo solo sql_formula testuale. I riferimenti Genro,
i parametri e le relazioni possono passare attraverso il resolver delle
espressioni; questo non equivale al linguaggio di macro legacy. Conservare
`x_select_*` o `x_var_*` come metadata non attiva le relative funzioni.

`subQueryColumn` legacy traduce `mode='json'` in jsonb_agg/row_to_json e `mode='xml'`
in xmlagg con cast a testo; le altre modalità passano a select/subquery_aggr.
Il nuovo elemento tipizza query come stringa: già la forma della dichiarazione
non rappresenta direttamente quel contratto a dizionario.
Fonti: `L:gnrpy/gnr/sql/gnrsqlmodel/model.py:1184`;
`N:src/genro_sql/elements.py:295`.

I requisiti prossimi devono comprendere scalar subquery ed EXISTS correlati,
con contratto esplicito per cardinalità, parametri senza collisioni e metadati
risultato. Le aggregazioni JSON possono seguire su quella stessa infrastruttura;
non occorre reintrodurre `aggregateRows` o la ricomposizione implicita di righe
esplose. È preferibile una singola espressione SQL che restituisce la struttura
richiesta per ogni riga principale.

Attenzione alla compatibilità dei filtri: nelle subquery legacy il compiler
imposta di default ignorePartition=True, excludeDraft=False,
excludeLogicalDeleted=False e subtable='*'. Non copiare questi bypass come
scelta nativa implicita: occorre decidere e testare la politica della query
annidata e offrire adattamento legacy separato.
Fonte: `L:gnrpy/gnr/sql/gnrsqldata/compiler.py:410`.

## Colonne Python: richiedono un piano di valutazione

Il legacy assegna il metodo predefinito `pyColumn_<nome>`, emette NULL nel SELECT
e registra il metodo nella query compilata. Dopo il fetch, handlePyColumns
invoca il metodo per ogni riga e scrive il risultato. Non si tratta di una
funzione SQL né del semplice possesso di un metodo nella sottoclasse SqlTable.

Fonti: `L:gnrpy/gnr/sql/gnrsqlmodel/model.py:1264`;
`L:gnrpy/gnr/sql/gnrsqldata/compiler.py:440`;
`L:gnrpy/gnr/sql/gnrsqldata/query.py:257`.

Esempi reali includono `sys.calendar.holiday`, `sys.external_token.external_url`
e `adm.userobject.resource_status`, quest'ultimo con required_columns='$data'.
Fonti: `L:projects/gnrcore/packages/sys/model/calendar.py:43`;
`L:projects/gnrcore/packages/sys/model/external_token.py:28`;
`L:projects/gnrcore/packages/adm/model/userobject.py:35`.

Per il nativo vanno definiti dipendenze/proiezioni necessarie, ordine e cicli,
modalità di errore, costo per riga e possibile protocollo batch. WHERE/ORDER BY
SQL su un valore disponibile solo dopo il fetch devono essere rifiutati o avere
un comportamento separato esplicito. Servono test sia su query.fetch() sia su
record.output(), preservando il profilo a dizionari. L'audit non ha ricostruito
l'intero algoritmo legacy di required_columns: non se ne promette equivalenza.

## Relazioni: il grafo operativo è ancora ridotto

Il legacy costruisce entrambi i versi del grafo e RelationTreeResolver espone
colonne e resolver annidati per relazioni many-to-one e one-to-many. La relazione
porta separatamente onDelete Python e onDelete_sql, oltre a nomi, condizioni,
store e informazioni di caricamento. VirtualColumn può registrare una relazione
virtuale; joinColumn può costruire un relation_path dal relativo join.

Fonti: `L:gnrpy/gnr/sql/gnrsqlmodel/model.py:181`, `:267`, `:298`;
`L:gnrpy/gnr/sql/gnrsqlmodel/resolvers.py:102`;
`L:gnrpy/gnr/sql/gnrsqlmodel/columns.py:266`.

Nel nuovo modello Relation conserva nome, tabella target e coppie di colonne.
Il resolver richiede un target univoco; il compiler genera JOIN in SELECT,
ma non consente relation paths nel DML. `back_reference` viene controllato per
collisioni e conservato nella dichiarazione, senza creare una Relation inversa.
`one_one` non va presentato come dimostrazione di unicità della chiave sorgente:
non esiste in quel flag un contratto operativo completo di cardinalità.

Fonti: `N:src/genro_sql/contracts.py:78`;
`N:src/genro_sql/model.py:105`;
`N:src/genro_sql/validators.py:350`;
`N:src/genro_sql/compiler.py:308`.

Relazioni senza FK fisica sono già possibili: foreign_key=False non significa
assenza di navigabilità. Questo è diverso da virtual relation con chiavi
calcolate o condizione custom, attualmente rifiutate. La nuova GEP sulle virtual
relation richiede un confronto dedicato: questo audit non certifica equivalenza
alla GEP sulla sola base dei nomi degli attributi legacy.

Priorità: descrivere cardinalità e provenienza nel modello, rendere consultabile
il grafo inverso, definire navigazione to-many mediante query/EXISTS/aggregazione
esplicita. Non trasformare automaticamente ogni relazione inversa in un join che
moltiplica le righe e poi tentare di ripararle con aggregateRows.

## Subtable, naming e partition sono concetti diversi

Il legacy usa subtable per almeno due meccanismi:

1. Una condizione nominata sulla stessa tabella, con parametri condition_*.
2. Una tabella logica di package collegata a maintable: copia dichiarazioni,
   aggiunge discriminatore __subtable e definisce filtri di default.

Il compiler combina subtables nominate con `&`, `|`, `!`, considera il contesto,
il default_subtable e l'esclusione esplicita `'*'`. Il naming fisico della
subtable può riferirsi alla maintable. Non è una partizione fisica PostgreSQL.

Fonti: `L:gnrpy/gnr/sql/gnrsqlmodel/model.py:672`, `:691`, `:767`;
`L:gnrpy/gnr/sql/gnrsqlmodel/containers.py:56`;
`L:gnrpy/gnr/sql/gnrsqldata/compiler.py:955`, `:970`;
`L:gnrpy/gnr/sql/gnrsqlmodel/table.py:147`.

Il nativo non dichiara subtables e rifiuta x_subtable. RowPolicies tratta le
partizioni logiche d'accesso, non recupera i due contratti sopra. Occorre prima
supportare i filtri nominati con composizione e parametri sicuri, poi decidere
scrittura/discriminatore e identità delle tabelle logiche condivise. Le partition
fisiche PostgreSQL richiedono un capitolo DDL separato.

Il naming legacy applica per default il prefisso package alla tabella, permette
sqlprefix=False/custom, schema di package/tabella e tenant schema runtime.
Il nativo distingue logical schema e x_sql_schema, prefix esplicito e x_sql_name;
non applica automaticamente il prefisso legacy. Questo è un cambiamento
intenzionale da adattare, non una compatibilità implicita. Import, compiler e
migrazione devono continuare a condividere il mapping risolto.

Fonti: `L:gnrpy/gnr/sql/gnrsqlmodel/obj.py:200`;
`L:gnrpy/gnr/sql/gnrsqlmodel/table.py:151`;
`N:src/genro_sql/model.py:84`;
`N:src/genro_sql/contracts.py:104`.

## Grammatica, configurazione e UI: cosa è già utile

SqlDatabaseConfig/ConfigHandler e il renderer a oggetti risolvono configurazione
e default effettivi prima di pubblicare il database operativo. Questo passaggio
è reale e riutilizzabile; non è una ragione per tollerare dichiarazioni prive di
semantica. I quattro tipi virtuali della grammatica devono avere capability
riconoscibili, diagnosi anticipata e prove fino al risultato.

Fonti: `N:src/genro_sql/configuration.py:32`, `:70`;
`N:src/genro_sql/object_renderer.py:14`.

Il nuovo modello mantiene attributi, identità e provenance; UI inline e overlay
hanno precedenza esplicita. La UI non può sovrascrivere dtype/formula/constraint.
È una buona base, ma per alias mancano ereditarietà della metadata target e doppia
provenienza. I metadata name_long/name_short legacy non vengono automaticamente
tradotti tutti in x_ui: l'adattatore deve dichiarare quella mappa.
Fonti: `N:src/genro_sql/model.py:18`, `:72`;
`N:src/genro_sql/contracts.py:59`.

## Priorità operative proposte

**Fondamentali del modello, prima di dichiarare una prima versione completa:**

- Alias to-one end-to-end, inclusi metadata, cicli, sola lettura e DDL corretto.
- Discriminante esplicito per tipo di colonna e capacità delle espressioni.
- Contratto di cardinalità e grafo relazionale, distinguendo FK da navigazione.
- Scalar subquery/EXISTS con correlazione e politica di visibilità esplicita.
- Filtri nominati/subtable semplice, se il modello deve rappresentare le viste
  logiche usate dalle applicazioni; senza simulare partition fisiche.

**Subito dopo, sullo stesso disegno:** aggregazioni JSON SQL esplicite, colonne
Python con dipendenze e batch, virtual relation secondo specifica verificata,
subtable con maintable/discriminatore e adattamento delle formule legacy comuni.
Non sono un contenitore generico «V2»: ciascuno richiede un contratto, un esempio
applicativo e un test di accettazione prima di stabilire la release.

**Separati dal recupero del modello:** Selection/Bag, macro UI o preferenze
ambientali complete, routing store/tenant, DDL per view/trigger/funzioni e
partition fisiche. Possono essere pianificati in seguito senza bloccare alias e
le altre primitive fondamentali.

L'accettazione di ogni nuova primitiva deve coprire dichiarazione → modello →
compiler → risultati, più esclusione o rappresentazione corretta nella migrazione.
Un test di grammatica o un esempio che stampa SQL non basta a dichiarare
compatibilità operativa con il legacy.
