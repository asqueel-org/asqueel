# Asqueel legacy, compiler e grammatiche distribuite

Analisi del 29 settembre 2026. Riferimenti: `asqueel` ad
`adba5d52174d166c59b4b364c9721b2e92837c5c`; legacy `origin/develop` ad
`e12f2ce54245e57e48371ae0f47e928e0d55b960`. Il checkout legacy locale era più
vecchio: per questa analisi sono stati letti i file del riferimento remoto,
senza cambiare branch o modificare quel checkout.

Il [dossier organizzato](design/README.md) collega questa ricostruzione storica
ai finding, agli obiettivi e al piano del nuovo Asqueel.

## Conclusioni

1. Il compiler legacy risolve espressioni Genro attraverso il modello runtime,
   costruisce join e clausole, e lascia all'adapter la composizione SQL finale.
   Non è un parser SQL completo con AST tipizzato.
2. Il `compiler_next` presente su develop è ancora una copia indipendente del
   compiler legacy. Il nuovo punto di selezione è operativo; la nuova grammatica
   degli aggregati descritta nei GEP non è implementata in quella copia.
3. Il nostro schema usa una grammatica unica composta da quattro mixin.
   Non usa né grammatiche montate dinamicamente come ConfigBuilder, né la
   composizione delle ricette attraverso `ConfigHandler(parents=...)`.
4. Builders 0.27 permette montaggi annidati conservando gli indirizzi per nome:
   lo abbiamo verificato. Il commento in `SqlBuilder` che esclude questa
   possibilità è troppo categorico e non giustifica da solo l'architettura.

## Mappa del legacy

| Componente | Responsabilità e collegamento |
|---|---|
| `GnrSqlDb` | Adapter, connessioni, ambiente, transazioni, accesso a tabelle e modello, esecuzione SQL. |
| `DbModelSrc` | Albero dichiarativo: package, tabelle, colonne fisiche e virtuali, relazioni e metadati applicativi. |
| `DbModel.build()` | Esegue `config_db`, personalizzazioni di package e `config_db_custom`, applica mixin, costruisce gli oggetti runtime, registra le relazioni. |
| Modello runtime e resolver | Risolvono colonne, alias, formule, nomi SQL, percorsi di relazione e cardinalità; forniscono il contesto semantico al compiler. |
| API della tabella | Query, record e operazioni di scrittura, con regole e hook applicativi. Il compiler delle SELECT non esaurisce questo livello. |
| `SqlQuery` / `SqlRecord` | Preparano la compilazione, conservano il risultato compilato ed eseguono SQL parametrizzato. Record ha un percorso di compilazione dedicato. |
| `SqlQueryCompiler` | Risolve espressioni e relazioni, genera alias e join, completa le clausole, conserva metadati per i risultati. |
| Adapter / traduttore WHERE | Dialetto SQL e operatori; traduzione della query Bag usata anche dall'interfaccia. |
| `SqlSelection` | Risultati, metadati, selezioni e aggregazione Python opzionale delle righe esplose. |
| Apphandler e griglie | Raccolgono campi, filtri, varianti e parametri; consumano anche metadati non fisici. |

La sostituzione della dichiarazione del modello deve preservare il contratto
con i consumatori runtime. Un JSON corretto per le migrazioni non basta a
dimostrare equivalenza con il modello ORM legacy.

## Come funziona il compiler

Esempio concettuale: una query su fatture chiede `$number`,
`@customer_id.name` e una formula virtuale, con `where='$total > :minimum'`.

1. `SqlQuery.compileQuery()` sceglie la classe tramite `queryCompilerClass(db)`
   e le passa modello della tabella, parametri e condizioni di join.
2. `compiledQuery()` prepara proiezioni e clausole: espansioni wildcard e macro,
   filtri di ambiente/partizione/subtable, cancellazione logica e altri criteri
   dipendenti dalle opzioni della query e del modello.
3. `updateFieldDict()` e `getFieldAlias()` riconoscono riferimenti `$campo` e
   `@relazione.campo`, li risolvono sul modello e li sostituiscono con espressioni
   SQL. La risoluzione ha effetti sul contesto: registra anche alias e join.
4. `_getRelationAlias()` percorre le relazioni, riusa gli alias già assegnati e
   costruisce i join, normalmente LEFT JOIN, con condizioni e cardinalità.
   Le navigazioni many possono moltiplicare le righe e vengono tracciate.
5. Le colonne virtuali non sono tutte uguali: un alias rimanda a un altro
   percorso; una formula produce SQL; `select`/`exists` possono compilare
   sottoquery correlate; una `pyColumn` richiede elaborazione Python successiva.
   `#THIS` consente alle sottoquery di riferirsi alla riga esterna.
6. Il risultato è un `SqlCompiledQuery`: clausole SQL più metadati, fra cui
   dizionari di alias/relazioni, colonne esplosive e informazioni di aggregazione.
   `get_sqltext()` chiama `adapter.compileSql()`.
7. `SqlQuery` esegue SQL con parametri separati; fetch/selection possono elaborare
   colonne Python, Bag e altri valori. L'aggregazione delle righe esplose è un
   comportamento ulteriore, non la normale semantica di ogni SELECT.

Il limite architetturale è l'intreccio fra riconoscimento testuale, risoluzione
semantica, costruzione dei join e preparazione dei risultati. Aggiungere una
funzione di percorso non consiste soltanto nell'accettare una nuova regex:
bisogna comprenderne cardinalità, tipo, ambito e dipendenze.

## Tre sviluppi da non confondere

| Filone | Stato e significato |
|---|---|
| Esperimenti `compiler_new`, v2/v3 e `sq_as_join` | Lavori precedenti su alias, subquery, compound query e riscrittura delle sottoquery come join. Sono documentati nella roadmap locale; non descrivono automaticamente il compiler su develop. La PR #544 risulta ancora aperta. |
| `compiler_next` di settembre | Copia indipendente selezionabile per istanza. La PR #1361 ha introdotto il percorso alternativo; #1409 ha spostato il flag sotto `experimental`. |
| Nuova grammatica GEP / compiler di `asqueel` | Proposta di funzioni sui percorsi e relazioni nominate; la roadmap di questo repository propone inoltre source query → rappresentazione SQL → renderer. Non sono componenti già consegnati dal nostro schema builder. |

Configurazione attuale del legacy:

```xml
<experimental>
    <db next_sql_compiler="True"/>
</experimental>
```

Senza flag, o senza application in modalità standalone, resta il compiler
legacy. Il vecchio attributo `sql_compiler="next"` non è il contratto attuale.
Il selettore viene usato sia dalle query sia dai record.

Fonti: [PR #1361](https://github.com/genropy/genropy/pull/1361),
[PR #1409](https://github.com/genropy/genropy/pull/1409),
[PR #544](https://github.com/genropy/genropy/pull/544).

## Cosa emerge dalle conversazioni

Sono stati letti i dialoghi locali pertinenti di luglio e settembre, i GEP in
`genropy_meta`, le discussioni GitHub e le roadmap SQL. Le intenzioni espresse
nei dialoghi sono distinte qui dal codice effettivamente presente.

- **6–10 luglio, sviluppo builders/SQL:** sostituire la source legacy,
  preservare metadati applicativi e colonne virtuali, ricostruire un modello
  runtime equivalente; ottenere proiezioni per DDL, migrazione e reverse
  engineering; affrontare poi il compiler. `sysFields` è un helper, non una
  primitiva obbligatoria della grammatica. Sono richieste collezioni esplicite.
- **20–23 settembre, SQL archaeology:** formula, variant e trasformazioni ad
  hoc esprimono un bisogno comune. Una funzione sul percorso deve funzionare
  anche nei filtri e nell'ordinamento, non soltanto nella lista delle colonne.
  Il percorso alternativo deve permettere evoluzione senza cambiare il
  comportamento del compiler legacy quando il flag è spento.
- **24 settembre, compiler sperimentale:** configurazione sotto `experimental`
  e possibilità di collaudare il percorso nuovo su un'istanza dedicata.
- **Discussione sulle relazioni:** preferenza per il nome unico
  `virtualRelation`, rispetto alla separazione reverseRelation/relationView.
  È una proposta nella discussione, non una API già disponibile su develop.

Riferimenti locali dei dialoghi: sessioni Claude
`ce254e4b-4c8c-49ae-a635-12536130ad35`,
`17c579ff-74b4-48d5-8d7b-169d2ba9d34d`,
`26b5ad69-afbc-44c4-9652-2be5dff3cc12`,
`2dbca0a1-399f-48cd-b01f-4d8ad9b701e3`,
`f123535c-6f2e-47f6-ac10-159487db5ec3`.

### Aggregati: il problema è l'insieme di righe su cui si calcola

Cliente → fatture → righe di fattura: un join piatto ripete il totale della
fattura per ogni sua riga. Sommarlo dopo il join dà il risultato sbagliato.
Deduplicare per valore perde invece fatture diverse con lo stesso totale.
`SUM(DISTINCT totale)` non risolve il problema generale.

[Issue #1354](https://github.com/genropy/genropy/issues/1354) documenta anche
perdita di righe con DISTINCT, alias non aggregati, perdita del dtype al secondo
salto e un parametro non consumato. I numeri del caso `test_invoice` sono
riproduzioni riportate nell'issue; non sono stati rieseguiti in questa analisi.

Il [GEP 1](https://github.com/genropy/genropy_meta/blob/main/gep/GEP-0001-relation-aggregates.md)
propone espressioni come:

```text
@invoices.count()
@invoices.sum($total)
@invoices.@rows.sum($quantity)
```

Ogni aggregato opera sulla relazione appropriata e restituisce uno scalare per
riga esterna, inizialmente tramite sottoquery correlata. Una sottoquery correlata
non implica di per sé N+1 chiamate al database: può essere parte di un unico SQL;
il costo di esecuzione va misurato sui piani reali.

Il GEP comprende anche funzioni sulla singola riga, template e usi nelle altre
clausole. La query Bag dell'interfaccia deve condividere la risoluzione delle
espressioni: oggi interroga il modello per risolvere il nome di colonna.

### Relazioni virtuali: proposta ancora da consolidare

Il GEP 2 iniziale usa `manyRelation`. La successiva
[discussione #1](https://github.com/genropy/genropy_meta/issues/1) propone
`virtualRelation` con una relazione di base oppure una tabella destinazione,
condizione espressa nel contesto della destinazione e binding `var_*` verso la
riga sorgente. Include relazioni filtrate e selezioni ordinate/limitate.

Restano contratti rilevanti: distinzione fra predicato di collegamento e filtro,
cardinalità reale, NULL, ordine deterministico per `limit=1`, cicli, composizione,
parametri e cache. Le relazioni virtuali sono proposte come sola lettura e non
devono diventare automaticamente FK o vincoli di migrazione. L'uso di `var_*`
come espressioni della riga sorgente è una semantica nuova, non un comportamento
da attribuire ai binding legacy già esistenti.

## Abbiamo usato le grammatiche in cascata?

Occorre distinguere tre meccanismi:

| Meccanismo | Nel nostro SQL attuale |
|---|---|
| Gerarchia di elementi tramite `sub_tags` e collezioni | Sì: db → schemas → schema → tables → table → columns, ecc. |
| Grammatica distribuita tramite `_meta={"subbuilder": "app:grammar"}` o riferimento equivalente | No. `SqlBuilder` compone `DbElements`, `SchemaElements`, `TableElements`, `ColumnElements` in un unico vocabolario. |
| Ricette sovrapposte tramite `ConfigHandler(..., parents=[...])` | No. I moduli `config_db` degli esempi compongono una ricetta, senza quel meccanismo di merge. |

ConfigBuilder dimostra il secondo meccanismo: il contenitore definisce il
layout e l'oggetto montato espone la grammatica del proprio sottoalbero.
ConfigHandler aggiunge il terzo: merge per chiave/attributo e lettura con
precedenza valori scritti → default di firma → default della chiamata → errore.
Le due funzionalità sono distinte.

**Verifica eseguita con Builders 0.27:** un builder radice monta una grammatica
schema; questa monta una grammatica tabella; la tabella dichiara colonne.
`source.get_node('db.schemas.public.tables.invoice.columns.id')` trova la
colonna corretta. I montaggi non comportano quindi necessariamente la perdita
degli indirizzi per nome.

Il prototipo non dimostra ancora compatibilità completa con `SqlSourceBag`,
validazione SQL, metadati di proiezione, serializzazione delle classi montate,
default e merge fra ricette. Va evitato di trasformare un controllo di
indirizzamento in una promessa di integrazione già pronta.

## Implicazioni per questo repository

La base attuale è utile: dichiarazioni strutturate, collezioni esplicite,
validazione e proiezione verso il migratore. Mancano però il compiler query e
un modello runtime equivalente a quello consumato dal legacy.

Prima di adottare il builder come sostituto di `DbModelSrc`, servono contratti per:

1. Risoluzione dei nomi logici/fisici, grafo delle relazioni, inverse,
   cardinalità, alias, formule e metadati delle colonne virtuali.
2. Estensione delle dichiarazioni per package, tabella e personalizzazione;
   precedenza e conflitti fra contributi devono essere espliciti.
3. Metadati applicativi: i dialoghi di luglio chiedono di preservare attributi
   arbitrari; la validazione canonica attuale richiede il prefisso `x_` per gli
   extra. È una divergenza da risolvere con inventario e regola di migrazione.
4. Separazione fra relazioni semantiche e vincoli fisici: una relazione utile al
   compiler non deve necessariamente produrre una foreign key.
5. Un resolver semantico riusabile da compiler testuale, query Bag e interfaccia;
   non una grammatica degli aggregati implementata separatamente in ogni punto.

Proposta di ordine del lavoro: prima fissare questi contratti e un piccolo
modello campione cliente/fattura/righe; poi verificare montaggi e composizione
contro gli stessi output del builder attuale; infine introdurre risoluzione
semantica e compilazione degli aggregati per relazione. Il dialetto ConfigBuilder
non va trapiantato letteralmente nel modello SQL: sono i meccanismi di Builders
per grammatica distribuita e composizione a essere riutilizzabili.

## Verifiche e limiti

- Fonti legacy lette da develop aggiornato, non dal solo snapshot `genropy-sql`
  di luglio, che non comprende gli sviluppi di settembre.
- Confronto dei due moduli compiler eseguito con la normalizzazione del test
  upstream: esclusi docstring del modulo, righe vuote e differenza del nome della
  classe. Esito: uguali.
- Prototipo con due montaggi annidati eseguito sull'ambiente Builders 0.27.
  Esito: percorso per nome conservato.
- Nessuna modifica al codice di produzione o al checkout legacy; nessun test
  completo del runtime legacy o benchmark SQL eseguito per questa analisi.
- Il materiale consultato comprende codice, roadmap, conversazioni locali
  reperite e discussioni collegate; non costituisce un inventario esaustivo di
  ogni conversazione o applicazione cliente.
