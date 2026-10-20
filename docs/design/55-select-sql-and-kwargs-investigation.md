# 55 — Indagine: query legacy → SELECT e kwargs

13 ottobre 2026. Baseline: core 0.6.0 integrato in main con c2ee40a,
stesso contenuto del branch locale dea700e. Indagine e prove, nessuna modifica
al core. Prevale la scelta successiva al documento 54: mantenere per ora la
chiamata query legacy e rinviare la grammatica Builder delle clausole.

**Aggiornamento 14 ottobre:** il [piano 56](56-read-compiler-plan.md) include
gli operatori del branch legacy `feature/compound_query`: `+` UNION, `|` UNION
ALL, `&` INTERSECT, `-` EXCEPT. Registra le verifiche PostgreSQL di riuso e
raggruppamento e dettaglia la sequenza operativa seguente. Nessun porting nel core.
Include inoltre la decisione successiva `query(...).query(...)` come SELECT
FROM SELECT, con join esterni tramite relazioni dei campi esposti, per esempio
`@customer_id.name` quando la query interna proietta `customer_id`.

## Obiettivo acquisito

L'uscita richiesta è una **stringa SQL SELECT e un dizionario di kwargs**, con
nomi coerenti con i placeholder dopo il mangling. La compilazione deve poter
avvenire senza eseguire la query. Il primo percorso di lavoro riguarda le
letture; scritture, nuova grammatica query e nuovo formato AST non sono inclusi.

La richiesta si esprime con columns, where, order_by, group_by, having,
limit/offset e parametri, conservando la sintassi legacy $campo, @relazione.campo,
AS ed espressioni SQL. Per il trasporto si valuterà la serializzazione degli
argomenti con JSON/TYTX; la coppia SQL/kwargs viene prodotta nell'ambiente
destinatario. Non si decide qui un codec o il trasferimento di callback Python.

## Risultato principale: l'uscita esiste già

In Asqueel è già possibile ottenere insieme SQL e parametri senza I/O:

```python
q = db.table('invc.invoice').query(
    columns='COALESCE($total, 0) AS value, '
            'CASE WHEN $total > :threshold THEN :high ELSE :low END AS category',
    threshold=100, high='alto', low='basso',
)
compiled = q.compiled
sql = compiled.sql
kwargs = dict(compiled.params)
```

Acquisire compiled **una volta sola**, perché ogni accesso ricompila usando
l'ambiente corrente. Non occorre inventare un nuovo compilatore pubblico o
un nuovo contenitore per offrire questa uscita. Un eventuale metodo di
comodità come il legacy test() sarebbe una scelta di API da discutere.

La stringa attuale è già pronta per il driver: PostgreSQL/psycopg usa
`%(nome)s`, SQLite usa `:nome`. Le date rimangono date nel dizionario in memoria,
non stringhe interpolate nel SQL. La compilazione non verifica però tutti i
tipi o la validità semantica delle espressioni sul server.

## Percorso legacy verificato

Riferimenti relativi al checkout GenroPy, sotto gnrpy/gnr/sql:

| Passaggio | Implementazione e comportamento |
| --- | --- |
| Raccolta della richiesta | gnrsqldata/query.py, SqlQuery.__init__: querypars per le clausole, sqlparams aggiornato con kwargs |
| Compilazione | SqlQuery.compileQuery → SqlQueryCompiler.compiledQuery; nel legacy compiled è memorizzato dopo il primo accesso |
| Risoluzione | gnrsqldata/compiler.py, getFieldAlias: nomi fisici, relazioni, alias, formule, select/exists, select_* e #THIS |
| SQL | SqlCompiledQuery.get_sqltext → adapter.compileSql |
| Estrazione senza esecuzione | SqlQuery.test restituisce (self.sqltext, self.sqlparams) |
| Completamento per il driver | gnrsql/execute.py: aggiunge env_* e workdate; adapter.prepareSqlText converte i placeholder ed espande raccolte |

Il dettaglio cruciale è che **query.test() nel legacy non raccoglie da solo
tutto ciò che farà execute()**. Alcuni valori dell'ambiente e adattamenti del
driver arrivano dopo. Per il nostro obiettivo dobbiamo consegnare una coppia
coerente e completa, non soltanto copiare il nome di quel metodo.

### Mangling legacy e meccanismi già presenti in Asqueel

- I var_* delle formule vengono rinominati dal legacy con un prefisso basato
  su id(fldalias), colonna corrente e nome; i valori vengono depositati in
  currentEnv e il testo usa placeholder env_*.
- gnrsql/query.py::queryCompile fa un passaggio analogo per kwargs locali alle
  sottoquery, con un prefisso basato su id(kwargs).
- #PERIOD può aggiungere parametri *_from e *_to. Le funzioni dipendenti
  dall'ambiente non equivalgono a normali kwargs già pronti.
- L'adapter legacy espande list/tuple/set in parametri numerati e poi converte
  :nome nel formato del driver. Asqueel possiede già una gestione delle
  collection con casi vuoti e collisioni verificati: non va sostituita senza
  considerare le decisioni precedenti su IN/NOT IN e ANY.

Nel core attuale _Context gestisce uno spazio condiviso dei nomi, scope delle
sottoquery, parametri di ambiente e collection. Per esempio, con ids=['a','b']
e un parametro ids_0 già presente, produce ids_1 e ids_2 per la lista e conserva
ids_0. Due sottoquery possono usare entrambe threshold senza sovrascriversi;
la prova ha prodotto _s1_threshold, s2_threshold, threshold e s1_threshold con
quattro valori distinti. Non serve rinominare i parametri semplici se non c'è
una collisione o uno scope da distinguere.

**Indicazione tecnica da confermare nell'implementazione:** riusare questa
allocazione anche per i binding delle dichiarazioni native, conservando la
semantica legacy senza trasferire id Python o valori temporanei nascosti in
currentEnv. I nomi interni non sono una nuova firma pubblica. Va verificato
esplicitamente il comportamento quando il parametro rappresenta un campo.

## Percorso Asqueel attuale

```text
SqlTable.query
  → SqlQuery (clausole e parametri copiati)
  → QueryCompiler.plan_select (risoluzione sul modello)
  → QueryPlan / Fragment / Parameter
  → dialect.render (SqlStatement)
  → driver.prepare (CompiledQuery.sql e .params)
```

I piani interni esistono già e non implicano una nuova grammatica pubblica.
Il formatter prepara i binding senza aprire connessioni. Il parser lessicale
attuale protegge stringhe, commenti, identificatori quotati, dollar quoting e
cast :: durante la sostituzione di riferimenti e parametri. Non è un controllo
di sicurezza del SQL arbitrario; l'ipotesi SQLGlot resta separata (documento 54).

## Prove sul corpus nativo e limiti

Sonda locale in /tmp/asqueel-query-audit/probe.py, con risultati in
/tmp/asqueel-query-audit/results.json. Sono state vietate le connessioni tramite
patch di psycopg.connect e sqlite3.connect. Non è stato eseguito il SQL prodotto.

| Prova | Esito |
| --- | --- |
| Proiezione esplicita di tutte le colonne fisiche, opzioni query predefinite | Compila per 74 tabelle su 74 |
| Query predefinita con * | Compila per 3 tabelle; fallisce per 71 |
| Virtuali compilate singolarmente, disabilitando esplicitamente le policy per isolare la colonna | 39 alias compilano; 7 alias, 462 formule, 12 pyColumn, 3 subQueryColumn e 3 bagItemColumn falliscono |
| CASE/COALESCE scritte direttamente nella query | Compilano e producono i kwargs corretti |
| Relazione diretta, IN con collisione, IN vuoto, env_workdate, GROUP BY/HAVING | Compilano nei casi provati |
| Scope di due sottoquery sul modello di basso livello già supportato | Nomi distinti anche in collisione con parametri esterni |
| Formula di modello, formula var_*, formula correlata, virtualRelation e relazione inversa | Rifiutate dal percorso nativo nei casi provati |

Questo misura la compilabilità, **non** la correttezza dei risultati sul DB o
la parità completa con il legacy. La prova con env_workdate restituisce un
datetime.date nel dizionario; il JSON diagnostico lo rappresenta come testo e
registra separatamente i tipi. Non è un nuovo codec della query.

Verifiche esistenti ripetute: tests/native_compiler, test_plans e test delle
collection del primo workflow: **171 pass, 1 skip**, inclusi casi PostgreSQL in
schemi temporanei e SQLite. Il primo tentativo sandbox aveva bloccato le
connessioni PostgreSQL; la ripetizione con accesso locale autorizzato è passata.

## Lacune da risolvere prima di dichiarare complete le letture

1. **Filtri dalle options native.** invoice e customer conservano i campi
   __del_ts / __is_draft e la partition dichiarata, ma table.policies risulta
   vuoto. Il compilatore interpreta oggi x_partition, x_draft_field e
   x_logical_deletion_field del vecchio percorso, non le options native.
   Le SELECT provate non aggiungono questi filtri. Va raccordato il modello
   completato alle regole di lettura legacy, senza rifare espansioni della source
   o creare nuove options. Vale anche la distinzione fra environment di processo
   letto da EnvResolver e contesto applicativo disponibile al momento della query.

2. **Espansione di *.** Il legacy usa colonne fisiche (X solo con bagFields)
   e virtuali statiche. Il core attuale include tutte le virtuali, comprese
   quelle non compilabili. Non basta eliminare il blocco x_requires_compilation:
   occorre rispettare quali colonne sono richieste davvero.

3. **Espressioni del modello nativo.** Sono conservate negli attributi con
   x_requires_compilation; il percorso di basso livello usa invece formula,
   select/exists e subqueries già interpretati. Occorre tradurre le dichiarazioni
   degli oggetti al momento della compilazione, compresi var_*, scope e #THIS.
   Resta valido il requisito di non riesaminare la source.

4. **Default e firme legacy.** Il legacy aggiunge pkey AS pkey nelle query
   non aggregate (salvo addPkeyColumn=False), usa order_by della tabella e genera
   alias per espressioni senza AS. Il core non aggiunge la pkey o l'ordine della
   tabella e richiede AS sulle espressioni calcolate. Anche group_by='*' è oggi
   rifiutato. Queste sono differenze da verificare rispetto alle decisioni
   pregresse e presentare prima di modificarle; non si cambiano incidentalmente.

5. **Parametri che rappresentano campi.** embedFieldPars legacy può trattare
   comparison='$vat_total' come riferimento dentro where='$total>:comparison'.
   Oggi Asqueel lo passa come valore stringa. La prova compila, ma non ha la stessa
   semantica. Non interpretare automaticamente tutti i valori inizianti per $/@
   senza confrontare anche le regole di escape e il percorso da fonte non fidata.

6. **Sottoquery, macro e relazioni.** La base di basso livello supporta già
   correlazioni e scope, ma non tutti i parametri del corpus, per esempio
   group_by/having nelle sottoquery. Inoltre oggi il default ignore_partition
   delle sottoquery è False, mentre il ramo select/exists legacy lo imposta a
   True. Inverse ordinarie, chiavi di join virtuali e virtualRelation hanno
   blocchi espliciti; per queste ultime prevalgono GEP e semplificazioni concordate.
   Non reintrodurre aggregateRows, inverse virtuali o limit/order_by/one_one
   virtuali. Macro, funzioni Python, variant e trasformazioni dei risultati
   richiedono un censimento distinto, non una generica promessa di supporto SQL.

## Ordine proposto per il primo incremento

1. Fissare con esempi il confine SQL/kwargs: uscita pronta per il driver,
   compilazione senza I/O, valori tipizzati e copia coerente da un solo compiled.
   L'API già esistente consente di mostrarlo prima di cambiare firme.
2. Raccordare i filtri del modello nativo e * ai comportamenti legacy. Registrare
   le divergenze di default individuate e risolverle senza decisioni implicite.
3. Concatenare SELECT FROM SELECT con `.query(...)`, conservando le origini
   delle colonne esposte per risolvere anche relazioni e join nel livello esterno.
   Verificare il caso `@customer_id.name`, scope dei parametri e riuso della query.
4. Comporre le query con gli operatori legacy, preservando raggruppamenti e
   query originali, con binding distinti e una sola uscita SQL/kwargs completa.
   Il piano 56 contiene controesempi legacy verificati e criteri di chiusura.
5. Collegare le formule SQL semplici e i loro var_* alla compilazione esistente;
   verificare alias, collisioni e due usi della stessa formula nella query.
6. Completare select/exists/select_*, #THIS e binding annidati. Separare le
   parti che producono SQL da quelle che richiedono elaborazione di risultati.
7. Verificare i casi su PostgreSQL temporaneo, confrontando risultati e valori
   dei binding, oltre alla sintassi. Il controllo SQLGlot rimane un incremento
   distinto; la sua collocazione va conciliata con i placeholder del driver.

Questo è un ordine di lavoro proposto, non un'autorizzazione a nuove firme o
al port automatico di ogni caratteristica. Non sono stati modificati il
compilatore, la source nativa, le migrations o le dipendenze.
