# Corpus di conformità per il compiler nuovo

Companion della [specifica](legacy-compatible-spec.md), versione 0.1.
Questa è una matrice di test da realizzare, non un resoconto di test superati.
I risultati numerici del dataset base sono controllabili con SQL diretto; i
comportamenti ambigui del legacy devono essere catturati dall'oracle fissato.

Il corpus verifica il profilo di compatibilità descritto nella
[proposta architetturale](../asqueel-target-architecture.md). Non richiede
all'API nativa di riprodurre i difetti legacy. Il progetto completo richiederà
anche corpus specifici per importazione del modello e scritture/transazioni.

Decisione acquisita: `aggregateRows` non è emulato. I casi L26 e C37–C39
verificano la migrazione e l'assenza di ricomposizione automatica dopo il fetch,
non l'uguaglianza con gli output errati del vecchio raggruppamento.

## 1. Protocollo dei casi

Ogni test concreto deve registrare:

1. ID del caso e requisiti coperti.
2. Versione del modello, dataset e dialetto/driver.
3. Ingresso completo: tabella, opzioni query, binding, ambiente e consumer.
4. Uscita attesa: colonne ordinate, righe con duplicati, tipi, parametri generati
   e metadati rilevanti, oppure categoria di errore.
5. Risultato baseline, risultato nuovo e differenza classificata.

Nelle tabelle, «oracle» indica un risultato legacy da acquisire, non un
risultato già accertato. «Decisione Axx» indica un difetto/limite per cui la
specifica richiede una scelta esplicita. Le denominazioni di campi sono logiche.

Per i casi di pura proiezione si assumono `addPkeyColumn=False`,
`ignoreTableOrderBy=True`, filtri impliciti disabilitati e nessun contesto extra,
salvo indicazione diversa. Le query delle policy dichiarano invece ogni opzione.
I test di risultati ordinano esplicitamente oppure confrontano multinsiemi.

## 2. Modello minimo riproducibile

Package logico `spec`; mappatura fisica scelta dall'adapter.

| Tabella | Colonne principali |
|---|---|
| customer | id pkey testuale; name testo; region testo; info X/Bag. |
| invoice | id pkey; customer_id FK nullable; total numerico nullable; day data; draft boolean nullable; deleted_at timestamp nullable. |
| row | id pkey; invoice_id FK; quantity intero nullable; price numerico nullable. |
| note | id pkey; customer_id FK; body testo. |

Relazioni: invoice → customer attraverso `@customer_id`; inversa customer
`@invoices`; row → invoice `@invoice_id`; inversa invoice `@rows`;
note → customer e inversa customer `@notes`.

Metadati: invoice.logicalDeletionField=`deleted_at`, draftField=`draft`.
Ordine predefinito, partizioni e subtable si attivano solo nei gruppi di test
dedicati. Nessuna delle altre tabelle ha politiche implicite nel dataset base.

### 2.1 Dati

| customer.id | name | region |
|---|---|---|
| C0 | Zero | N |
| C1 | Uno | N |
| C2 | Due | S |
| C3 | Tre | S |

| invoice.id | customer_id | total | day | draft | deleted_at |
|---|---|---:|---|---|---|
| I1 | C1 | 100 | 2026-01-01 | FALSE | NULL |
| I2 | C1 | 100 | 2026-01-02 | FALSE | NULL |
| I3 | C1 | 50 | 2026-01-03 | TRUE | NULL |
| I4 | C2 | 200 | 2026-01-04 | FALSE | 2026-02-01 00:00:00 |
| I5 | C2 | NULL | 2026-01-05 | NULL | NULL |
| I6 | NULL | 30 | 2026-01-06 | FALSE | NULL |

| row.id | invoice_id | quantity | price |
|---|---|---:|---:|
| R11 | I1 | 1 | 10 |
| R12 | I1 | 1 | 10 |
| R21 | I2 | 2 | 20 |
| R22 | I2 | NULL | 30 |
| R23 | I2 | 0 | 0 |
| R31 | I3 | 5 | 10 |
| R41 | I4 | 4 | 50 |
| R51 | I5 | 3 | NULL |
| R61 | I6 | 1 | 30 |

Note N1 e N2 appartengono a C1 e hanno lo stesso body `uguale`.
Per info usare una Bag con foglie `city='Roma'`, `nested.zip='00100'`,
una foglia NULL e caratteri non ASCII; un altro customer ha info NULL.

Risposte matematiche indipendenti dall'oracle legacy:

- Fatture totali: 6; con policy invoice predefinite: I1, I2, I5, I6, quindi 4.
- Per C1, senza filtri sulle fatture: 3 fatture, somma total=250.
- Per C1: 6 righe fattura, somma quantity=9; COUNT(quantity)=5.
- Per C1, SUM(total) sul join fatture-righe=550; SUM(DISTINCT total)=150.
- LEFT JOIN customer-invoice non deduplicato: 7 righe.
- LEFT JOIN customer-invoice-row non deduplicato: 10 righe.
- Clienti con almeno una riga quantity>0: C1 e C2; righe del join che
  soddisfano quel predicato: 6. Sono due conteggi diversi.
- C0 e C3 devono sopravvivere a una navigazione LEFT senza filtro sul target.

I test del compiler devono esplicitare DISTINCT/pkey/policy: questi numeri
non sono automaticamente il risultato di ogni API GenroPy che esprime un join.

### 2.2 Estensioni del modello per gruppi dedicati

| Estensione | Scopo |
|---|---|
| invoice.customer_name alias di `@customer_id.name` | AliasColumn su relazione O. |
| invoice.double_total formula `$total*2` | Formula locale e NULL. |
| invoice.total_chain formula `$double_total+1` | Dipendenze fra formule. |
| invoice.row_count select `COUNT(*)`, correlato a `#THIS.id` | Sottoquery scalare. |
| invoice.has_rows exists sulla tabella row | EXISTS correlato. |
| invoice.first_row select ordinato con limit=1 | Ordine/limite di sottoquery. |
| invoice.total_label formula CASE con `var_threshold` | Binding di formula e varianti. |
| customer.primary_contact e billing_contact verso una stessa tabella contact | Join distinti sullo stesso target. |
| staff.manager_id verso staff | Self join e riuso dei percorsi. |
| coppia tabella code/translation con chiave composta (namespace, code) | Join composito, arità e NULL. |
| colonna con nome fisico diverso dal nome logico | Mapper e quoting. |
| colonna cifrata Q e pyColumn con callback reale | Contratti dei risultati. |
| colonne TSV e VEC PostgreSQL | Macro specifiche. |

Le formule sono dichiarazioni del modello di test; non si aggiungono alla
grammatica testuale nuove funzioni con questi nomi.

## 3. Lessico, SQL opaco, proiezioni e alias

| Caso | Ingresso / variazione | Risultato o proprietà richiesta |
|---|---|---|
| L01 | invoice, columns=`$id,$total` | Due colonne id/total, sei righe senza policy. |
| L02 | `$id AS invoice_id,$total as amount` | Alias espliciti preservati, entrambe le forme previste. |
| L03 | AS con maiuscole miste, tab, newline | Oracle e decisione A03; separare ampliamento parser da compatibilità. |
| L04 | `$id` logico mappato a un diverso nome fisico | Identificatore fisico nel SQL, alias logico nel risultato. |
| L05 | `COALESCE($total,0)` | I5 diventa 0; nessuna alterazione degli altri valori. |
| L06 | `CASE WHEN $total IS NULL THEN 1 ELSE 0 END AS missing` | I5=1, altri=0. |
| L07 | Espressione con virgola in stringa e funzione annidata | Una sola proiezione, non uno split sulle virgole interne. |
| L08 | Array SQL e parentesi quadre con virgole, PostgreSQL | Conservazione del frammento e split corretto. |
| L09 | Stringa contenente `$id` e `@customer_id.name` | Oracle; nuovo lexer/decisione A02. |
| L10 | Commento SQL con token asqueel | Oracle; nessun riferimento accidentale nel profilo nuovo regolare. |
| L11 | Dollar quoting PostgreSQL e cast `::numeric` | Oracle per legacy, lexer del dialetto verificato. |
| L12 | Apici raddoppiati, backslash e stringa non chiusa | Risultato oppure diagnostica lessicale controllata. |
| L13 | `CAST($total AS TEXT) AS text_total` | CAST interno distinto dall'alias esterno; caratterizzare A03. |
| L14 | `$id,$id` | Deduplicazione legacy osservata. |
| L15 | `$id AS x,$total AS x` | Oracle ultimo alias prevalente; decisione A03. |
| L16 | Due percorsi che collidono dopo colToAs | Collisione rilevata/caratterizzata, mai perdita inconsapevole. |
| L17 | `1 AS one`, espressione che inizia con cifra senza AS | Alias esplicito/implicito secondo SEL. |
| L18 | Nome SQL bare `total` confrontato con `$total` | Nessuna equivalenza presunta fra SQL opaco e modello. |
| L19 | `*` con virtuale statica e non statica | Fisiche + statica; non statica assente. |
| L20 | `*`, bagFields False/True | Colonna X esclusa/inclusa sulla tabella principale. |
| L21 | `$info` esplicito con bagFields=False | Campo presente. |
| L22 | `*tot` principale | Oracle espande tutto; decisione A01. |
| L23 | `*@customer_id` | Campi della tabella correlata e alias corretti. |
| L24 | `*@customer_id.na` | Solo campi del target con quel prefisso. |
| L25 | `*@customer_id` con campo X e bagFields=False | Caratterizzare differenza rispetto allo star principale. |
| L26 | `*@invoices.(id,total)` con richiesta di raccolta | Migrazione a raccolta esplicita; nessun pivot automatico Python tramite aggregateDict. |
| L27 | `*virtual_expansion` | Espansione guidata dalla formula della virtuale. |
| L28 | `columns=None` via query pubblica e `columns=''` interno | Default diversi esplicitamente verificati. |
| L29 | pkey reale chiamata code e riferimento `$pkey` | Risoluzione verso code e nome pubblico previsto. |
| L30 | addPkeyColumn True/False; tabella senza pkey | Aggiunta condizionale senza colonna inventata. |

## 4. Relazioni e condizioni di join

| Caso | Ingresso / variazione | Risultato o proprietà richiesta |
|---|---|---|
| J01 | invoice: `$id,@customer_id.name` | I6 resta presente con nome NULL. |
| J02 | row: `@invoice_id.@customer_id.name` | Due salti; R61 ha nome NULL. |
| J03 | Due campi dello stesso percorso | Un join riusato; valori coerenti. |
| J04 | Percorso comune in SELECT, WHERE e ORDER BY | Riuso del contesto senza join duplicati. |
| J05 | primary_contact e billing_contact verso contact | Due alias indipendenti, valori distinti. |
| J06 | staff → manager → manager | Self join con scope distinti, assenza di cicli di compilazione spurii. |
| J07 | customer: `$id,@invoices.total` | Many, DISTINCT automatico e pkey secondo opzioni; confrontare multinsiemi. |
| J08 | Due many indipendenti invoices/notes | Prodotto delle cardinalità prima della deduplicazione; nessuna aggregazione implicita nuova. |
| J09 | Many soltanto nel WHERE | Tracciamento e conteggio secondo oracle; non convertire automaticamente in EXISTS. |
| J10 | Many soltanto in ORDER BY | Join necessario e gestione DISTINCT/colonne ordine. |
| J11 | aliasTable che espande due hop | Stesso target del percorso esplicito. |
| J12 | Relazione su formula virtuale | ON contiene l'espressione della formula e le sue dipendenze. |
| J13 | Join composito valido | Uguaglianza di tutte le componenti, ordine corretto. |
| J14 | Composite target assente o arità diversa | Errore del modello o decisione A10. |
| J15 | `cnd` e FK standard insieme | cnd segue precedenza, non aggiunta automatica dell'uguaglianza FK. |
| J16 | `join_on` e `cnd` entrambi definiti | join_on prevale. |
| J17 | cnd con relazione aggiuntiva | Dipendenze risolte e ordine join valido. |
| J18 | cnd a due hop dalla tabella principale | Riferimenti riferiti allo scope corretto. |
| J19 | case_insensitive='Y' con codici mixed case | Oracle reale e decisione A10. |
| J20 | between con valore esattamente high | Escluso, a differenza di IN_RANGE. |
| J21 | Extra ON `$tbl.total>:minimum` | Parametro bind e alias target corretti. |
| J22 | Extra ON che esclude tutti i figli di C1 | C1 rimane nella query LEFT se nessun WHERE sul target lo elimina. |
| J23 | joinConditions per nome e per coppia | Lookup verificato per i due ingressi; non assumere fallback. |
| J24 | Extra ON one_one=True | Cambia metadata di esplosione, non i vincoli fisici. |
| J25 | `*_*` senza WHERE iniziale | Condizione applicata e token risolti. |
| J26 | `*_*` con token relazione | Join generato anche se non compare nella SELECT. |
| J27 | `jc_*='@invoices*:condizione'` | Wrapper decodifica condizione e flag one_one. |
| J28 | Stesso modello in due tenant, ignore_tenant variabile | Nomi target corretti e nessun riuso del tenant sbagliato. |
| J29 | Relazione/aliasTable inesistente | Categoria di errore e percorso. |
| J30 | FK NULL e chiave non trovata senza vincolo fisico | Semantica LEFT e propagazione NULL. |

## 5. Parametri, formule e sottoquery

| Caso | Ingresso / variazione | Risultato o proprietà richiesta |
|---|---|---|
| P01 | `$total>:minimum`, minimum=90 | I1,I2,I4 senza policy; parametro separato dal SQL. |
| P02 | Due usi di :minimum | Un valore coerente in entrambe le posizioni. |
| P03 | :id e :id2 | Nessuna sostituzione parziale del nome. |
| P04 | sqlparams e kwargs con stesso nome | Precedenza kwargs. |
| P05 | Stringa con apice, Unicode e bytes | Valore intatto dopo adattamento previsto. |
| P06 | Decimal, date, timestamp timezone, bool, NULL | Tipo e valore conservati. |
| P07 | `$id IN :ids`, lista/tuple/set | Collezione espansa dal driver con stessi membri. |
| P08 | Lista vuota, None, lista con NULL, NOT IN | Risultati distinti per dialetto, decisione A12. |
| P09 | `$total=:other`, other='$double_total' | Confronto con espressione, non con stringa. |
| P10 | Parametro che contiene percorso @ riconoscibile | Navigazione incorporata nel WHERE. |
| P11 | Valore letterale `\$id`/`\@invoices.total` | Valore bind senza barra; nessuna navigazione. |
| P12 | Parametro-campo nella SELECT/HAVING | Oracle del contesto non coperto dall'embedding. |
| P13 | :env_workdate, :env_user, parametro esplicito omonimo | Ambiente e precedenza esplicita corretti. |
| P14 | Binding mancante | Oracle driver e decisione PAR-12. |
| P15 | `\:` nel SQL e cast del dialetto | Protezione durante la conversione dei placeholder. |
| V01 | `$customer_name` e `@customer_id.name` | Stessi valori; nomi output distinti secondo richiesta. |
| V02 | `$double_total` | I1=200, I3=100, I5=NULL. |
| V03 | `$total_chain` | I1=201, I5=NULL; dipendenza transitiva. |
| V04 | Formula riferita tramite relazione | Risoluzione relativa alla tabella proprietaria. |
| V05 | Formula callback sql_formula=True | Callback riceve attributi e restituisce espressione risolta. |
| V06 | Formula senza definizione valida | GnrSqlInvalidVirtualColumn o mappatura equivalente. |
| V07 | Ciclo fra due alias/formule | Errore nuovo descrittivo; caratterizzare errore legacy. |
| V08 | row_count correlato per I1/I2/I5 | 2,3,1; nessun join esplosivo esterno richiesto. |
| V09 | has_rows e fattura senza righe aggiunta alla fixture | True/False corretti. |
| V10 | Sottoquery scalare che produce più righe | Errore/semantica del dialetto, nessun LIMIT 1 implicito. |
| V11 | first_row con ordine e limit=1 | Riga deterministica usando id come tie-break. |
| V12 | Formula con due select_nome | Sostituzione di entrambi senza collisione. |
| V13 | select_nome via subquery_<nome>() | Provider e tabella su cui viene cercato verificati. |
| V14 | Select con cast | Tipo e NULL della sottoquery preservati. |
| V15 | #THIS.id dentro formula raggiunta a due hop | Correlazione col proprietario corretto, non sempre t0. |
| V16 | Due sottoquery annidate con parametri omonimi | Scope isolati e nessun binding sovrascritto. |
| V17 | Default delle policy nella sottoquery | Include draft/deleted salvo override, anche se la query esterna li esclude. |
| V18 | var_threshold su due varianti dello stesso campo | Risultati distinti e binding isolati. |
| V19 | sqlparams[nome]={field:base,...} | Variante risolta; struttura non inviata come normale valore driver. |
| V20 | Virtuale dichiarata e variante con stesso nome | Dichiarazione ha precedenza. |
| V21 | pyColumn con callback reale | SQL NULL e risultato Python finale; metadata callback. |
| V22 | pyColumn con AS, su relazione, in WHERE | Caratterizzazione per consumer, senza promettere esecuzione SQL della callback. |
| V23 | compositeColumn proiettata e usata per join | Valore rappresentato distinto dalle componenti di confronto. |
| V24 | bagItemColumn con conversione dtype | Valore estratto e tipo su dialetto supportato. |
| V25 | subQueryColumn json/xml, zero/una/molte righe | Valore, NULL e tipo corretti; DISTINCT compatibile dove previsto. |
| V26 | Formula dinamica/locale e variante di modello | ModelProvider include definizioni del contesto giusto. |

## 6. Macro

| Caso | Ingresso / variazione | Risultato o proprietà richiesta |
|---|---|---|
| M01 | IN_RANGE, entrambi limiti presenti, value agli estremi | Entrambi inclusi. |
| M02 | IN_RANGE con un limite NULL | Solo confronto con l'estremo presente. |
| M03 | IN_RANGE con entrambi NULL e value NULL | Vero. |
| M04 | IN_RANGE con value NULL e un limite presente | UNKNOWN nel predicato, quindi non selezionato dal WHERE. |
| M05 | IN_RANGE nella formula e nel cnd | Espansione nei contesti previsti. |
| M06 | IN_RANGE con funzione annidata come operando | Oracle della regex; eventuale ampliamento esplicito. |
| M07 | PERIOD un giorno | Uguaglianza e solo bind _from necessario. |
| M08 | PERIOD intervallo, solo inizio, solo fine, nessun periodo | BETWEEN / >= / <= / TRUE e binding corretti. |
| M09 | PERIOD con workdate fissata e locale it/en | Date attese indipendenti dal giorno del test. |
| M10 | PERIOD mese/trimestre/anno, offset, intervallo anno nuovo | Confronto con decoder baseline e casi limite calendario. |
| M11 | PERIOD e parametri _from/_to già presenti | Oracle collisione e politica nuova documentata. |
| M12 | BAG con alias | Oggetto Bag nel campo con quell'alias. |
| M13 | BAGCOLS con foglie annidate | Campi alias_city, alias_nested_zip e sorgente None. |
| M14 | BAG con NULL, vuoto e serializzazione invalida | Oracle di conversione/errore, non solo SQL. |
| M15 | ENV valore presente, fallback, metodo, assente | Quattro rami e decisione A08. |
| M16 | ENV/PREF con valore che contiene apici | Binding/diagnostica nuovi e compatibilità dichiarata. |
| M17 | PREF package proprietario raggiunto via relazione | Preferenza del package corretto. |
| M18 | Ogni macro fuori dai contesti ammessi | Nessuna espansione accidentale; oracle/diagnostica. |
| M19 | TSQUERY corrente + TSRANK + TSHEADLINE | Ricerca, ordinamento e highlight sullo stesso canale. |
| M20 | Due canali TSQUERY distinti | Nessuna contaminazione del contesto. |
| M21 | TSRANK default, pesi espliciti, normalization=0 | PostgreSQL reale, decisione A14 per forme problematiche. |
| M22 | TSRANK senza TSQUERY; TSHEADLINE senza canale | Errore rank / stringa vuota headline secondo contratto. |
| M23 | TSQUERY con lingua parametro/campo | Casting regconfig e valori corretti. |
| M24 | VECQUERY senza soglia | Filtra NULL, non distanza. |
| M25 | VECRANK con vettori uguali, ortogonali, opposti | Similarità secondo operatore del database, non interpretazione della query string. |
| M26 | Due canali vector e rank senza canale | Isolamento e errore contestuale. |
| M27 | Macro registrata con override di nome esistente | Precedenza del dispatcher. |
| M28 | Macro custom registrata fuori dalla lista invocata | Oracle non-espansione e scelta del nuovo contratto. |
| M29 | TSRANK/TSHEADLINE con operandi espliciti nel secondo trasformatore | Oracle psycopg2 e confronto con postgres3/postgres8000; decisione A18. |
| M30 | Rank diretto vs rank dentro formula virtuale | Controllare assenza di token asqueel irrisolti nel SQL finale e risultati reali. |

## 7. Clausole, policy, count e cardinalità

| Caso | Ingresso / variazione | Risultato o proprietà richiesta |
|---|---|---|
| C01 | invoice query con default pubblici | I1,I2,I5,I6; 4 righe. |
| C02 | excludeDraft=False, logical deletion esclusa | 5 fatture, esclusa solo I4. |
| C03 | excludeLogicalDeleted=False, draft esclusi | 5 fatture, esclusa solo I3. |
| C04 | Entrambe le esclusioni False | 6 fatture. |
| C05 | excludeLogicalDeleted='mark', draft esclusi | I4 presente con timestamp in _isdeleted, I3 assente. |
| C06 | mark con count/group/distinct | Campo aggiuntivo secondo condizioni precise del compiler. |
| C07 | draft NULL | I5 inclusa dal filtro IS NOT TRUE. |
| C08 | customer con navigazione invoices | Policy invoice non applicate automaticamente al target. |
| C09 | Partizione N, ignorePartition False/True | Filtro provider attivato/disattivato. |
| C10 | Due condizioni env e WHERE con OR | Parentesi preservate; AND fra contributi. |
| C11 | subtable esplicita vs contesto vs default | Precedenza secondo POL-04. |
| C12 | subtable='*' | Nessun filtro subtable. |
| C13 | subtable A&B, A|B, !A | Risultati booleani verificati. |
| C14 | Nomi subtable sovrapposti | Oracle e decisione A16. |
| C15 | Default ordine di tabella vs ordine esplicito | Precedenza e ignoreTableOrderBy. |
| C16 | `$customer_id,SUM($total)` con GROUP BY | C1=250,C2=200, NULL=30 senza policy; NULL dei gruppi preservati. |
| C17 | group_by='*', columns='SUM($total) AS total' | Un risultato 480 senza pkey/default order, nessun GROUP BY emesso. |
| C18 | SUM senza group_by='*', addPkeyColumn default | Oracle della pkey anticipata, decisione A04. |
| C19 | AVG/MIN/MAX e funzioni custom aggregate | Inferenza legacy caratterizzata; nuovo piano esplicito. |
| C20 | HAVING SUM($total)>200 | Solo gruppo C1 nel dataset non filtrato. |
| C21 | Window LAG/ROW_NUMBER con PARTITION BY | Nessun raggruppamento implicito della query esterna. |
| C22 | FILTER (WHERE ...) su aggregate | Filtro locale all'aggregato preservato. |
| C23 | DISTINCT esplicito vs automatico vs False | Valori/duplicati e decisione A05. |
| C24 | DISTINCT automatico e ordine non proiettato | __ord_col_N, colonne extra e effetto sulla deduplica. |
| C25 | Alias ordine bare e `$alias` | Distinguere SQL alias e lookup nel modello. |
| C26 | limit=2, offset=1 con ordine univoco | Finestra esatta del risultato SQL. |
| C27 | limit=0 intero e '0' stringa | Oracle e decisione A11. |
| C28 | count semplice senza policy | 6. |
| C29 | count con policy pubbliche | 4. |
| C30 | count GROUP BY customer_id, policy disabilitate | 3 gruppi incluso NULL, senza limit/offset. |
| C31 | count DISTINCT total, policy disabilitate | 5 valori incluso NULL, se la proiezione è solo total. |
| C32 | count con many in WHERE, quantity>0 | Confrontare 6 righe join e 2 clienti; registrare risultato oracle. |
| C33 | count con many in proiezione | Verificare se la compilazione count elimina il join non più richiesto. |
| C34 | count con LIMIT/OFFSET | Risultato oracle completo; non assumere conteggio totale senza limiti. |
| C35 | customer C1: SUM(@invoices.total) con secondo hop | 550 se il SQL aggrega il join di fatture e righe; non 250 automaticamente. |
| C36 | SUM(DISTINCT totale) sul medesimo insieme C1 | 150: dimostra che non risolve il doppio conteggio per identità. |
| C37 | selection(_aggregateRows=True), totali uguali | Diagnostica di migrazione, anche via bridge; aggregato SQL esplicito su C1 restituisce 250 senza deduplica per valore. |
| C38 | Vecchia aggregazione con alias e due hop | Migrazione ad aggregati/raccolte espliciti con dtype e alias corretti; nessuna ricomposizione Python. |
| C39 | Vecchia aggregazione combinata con LIMIT | Dichiarare scope di aggregato e limite; verificare assenza di somme su un sottoinsieme fetchato implicitamente. |
| C40 | Due compilazioni con ambienti diversi | Nessuna contaminazione di tenant, filtri o varianti. |

## 8. Query Bag, record e risultati

| Caso | Ingresso / variazione | Risultato o proprietà richiesta |
|---|---|---|
| B01 | Bag: total greater 90 | Valore convertito e stesse righe di P01. |
| B02 | Gruppi annidati AND/OR/NOT | Precedenza conservata e parità con WHERE testuale equivalente. |
| B03 | Prima riga vuota, seconda con jc=AND | Nessun connettivo iniziale spurio. |
| B04 | not='not' vs not=True | Oracle dei due ingressi diversi. |
| B05 | Valore '?threshold' e value_caption | Prelievo dei parametri e consumo dove previsto. |
| B06 | Campo ripetuto e parname esplicito | Bind distinti, collisioni caratterizzate. |
| B07 | equal con lista | Operatore IN. |
| B08 | Tutti gli operatori base | Un caso positivo, negativo e NULL per ciascuno. |
| B09 | contains su numerico; unaccent su testo | Cast/template adapter corretti. |
| B10 | Giorno, periodo e timestamp con timezone | Data e operatore risultanti secondo BAG-11. |
| B11 | Numero invalido e colonna inesistente | Due categorie di errore distinte. |
| B12 | Op custom, op ignoto, endswith senza provider | Callback o errore; nessun supporto inventato. |
| B13 | Campo encrypted Q, valore scalare/lista | Cifratura prima del binding. |
| B14 | whereFromDict, suffissi op/not e underscore nel campo | Parsing del nome verificato. |
| R01 | record customer C1, fisiche e Bag | Alias strutturali e resultmap. |
| R02 | record con bagFields=False | Campo X escluso secondo contratto. |
| R03 | Record, virtual_columns stringa/lista | Stesse virtuali, deduplicazione e aggiunta statiche. |
| R04 | virtual_columns sconosciuta/False | Comportamento diverso dalla query esplicita, decisione A11. |
| R05 | Record relazioni O/M/one_one | Tre modalità DynItem corrette. |
| R06 | Record relazione su colonna virtuale | Dipendenze e placeholder nell'ON risolti. |
| R07 | Macro WHERE record vs WHERE query | Differenza della pipeline verificata. |
| R08 | for_update query/record, True e modalità testuale | SQL e comportamento lock per adapter supportato. |
| R09 | Record zero righe e record non univoco | Wrapper produce errori/risultati attesi. |
| R10 | Relazioni lazy/eager | Verificare caricamenti reali senza attribuire tutto alla SELECT iniziale. |
| R11 | pkey, WHERE ed extra simultanei | Precedenza WHERE → pkey → parametri-campo. |
| R12 | Pkey composta serializzata; pkey=0 | Decomposizione e distinzione fra None e valore falsy. |
| R13 | Nessun criterio; ignoreMissing/ignoreDuplicate | Errori del wrapper e trattamento duplicati cancellati. |
| R14 | Record con aliasPrefix e nomi SQL personalizzati | Filtro, FROM, alias di output e resultmap coerenti; decisione A19. |
| O01 | fetch vs cursor vs selection | Trasformazioni effettive per ogni consumer. |
| O02 | PyColumn + Bag + cifratura nello stesso risultato | Ordine e nomi dei postprocessor coerenti. |
| O03 | Colonna cifrata con AS e via relazione | Oracle/decisione A17. |
| O04 | Metadati dtype/label di alias e formula | GUI/selection ricevono informazioni equivalenti. |
| O05 | Due store con stesso pkey | _dbstore_ distingue origine; non deduplicare fra store per sola pkey. |
| O06 | count multistore | Somma dei conteggi secondo wrapper. |
| O07 | pyColumn/Bag su fetch multistore | Oracle della differenza di percorso, non supposizione di parità. |

### 8.1 Nuovo contratto dei metadati d'interfaccia

Questi casi verificano un requisito del modello nuovo, non un comportamento
da confrontare soltanto con l'oracle legacy.

| Caso | Ingresso / variazione | Risultato o proprietà richiesta |
|---|---|---|
| U01 | Stessa colonna con UI inline oppure parallela | Stessi metadati risolti e stessa identità d'origine. |
| U02 | Descrittore UI riferito a colonna assente | Errore di validazione con provenienza del riferimento. |
| U03 | Override di package/app/istanza e profilo form/griglia | Precedenza dichiarata, conflitti rilevati e provenienza leggibile. |
| U04 | Rename o reimportazione del modello | Collegamento mantenuto tramite identità; ambiguità segnalate senza perdita degli arricchimenti UI. |
| U05 | Modifica di sola label/widget | Nessun DDL; piano SQL invariato se non cambiano proprietà semantiche. |
| U06 | Alias di campo e aggregato derivato | Provenienza conservata; tipo, formato ed editabilità del risultato coerenti. |
| U07 | Modello senza UI e runtime senza framework grafico | Compilazione ed esecuzione funzionano senza dipendenze UI. |
| U08 | Import legacy con formati, label ed extra sconosciuti | Informazioni raccolte sulla colonna o sul descrittore collegato, senza perdita silenziosa. |
| U09 | Campo nascosto/read-only nell'UI | Autorizzazioni e validazioni del runtime restano governate dai contratti di dominio. |

### 8.2 VirtualRelation del modello nuovo

Anche questi casi verificano un contratto nuovo, non l'equivalenza con una
funzionalità della baseline legacy.

| Caso | Ingresso / variazione | Risultato o proprietà richiesta |
|---|---|---|
| VR01 | Relazione filtrata derivata con relation= | Stesso collegamento della base, filtro applicato all'insieme target. |
| VR02 | Collegamento senza FK tramite table= e var_* | Campi di B e binding di A risolti in scope distinti. |
| VR03 | table= senza un predicato di collegamento | Diagnostica del modello, nessun prodotto cartesiano accidentale. |
| VR04 | last_invoice con ordine totale e limit=1 | Al massimo una fattura per sorgente; sorgenti senza fatture preservate nella navigazione LEFT. |
| VR05 | Aggregato su virtualRelation filtrata | Risultato SQL sull'insieme corretto, senza aggregateRows. |
| VR06 | Derivazioni cicliche e predicati con OR | Cicli rifiutati; struttura booleana preservata nella classificazione dei predicati. |
| VR07 | Salvataggio cluster e proiezione migrazioni | Relazione virtuale esclusa dalle scritture correlate e dai vincoli fisici automatici. |
| VR08 | UI, ask e due binding/ambienti differenti | Metadati disponibili e contesti isolati, senza riuso improprio del piano. |

## 9. Matrice dialetti e regressioni

### 9.0 Mappatura dei nomi fisici

| Caso | Ingresso / variazione | Risultato o proprietà richiesta |
|---|---|---|
| NM01 | Schema nativo, prefisso oppure entrambi | Stessa identità logica; nomi SQL secondo la politica dichiarata. |
| NM02 | sqlprefix True/False/stringa e sqlname esplicito | Mappatura legacy preservata; override sqlname prevalente. |
| NM03 | FK/join, DML e migrazione con nomi prefissati | Tutti i consumer usano la medesima mappa. |
| NM04 | Tenant diverso e subtable con maintable | Schema e riferimento fisico corretti, senza duplicare prefissi o creare una nuova tabella per errore. |
| NM05 | Import di nomi con underscore e cambio del prefisso | Nessuna inferenza ambigua; rename esplicito e identità/UI preservate. |
| NM06 | Collisioni e nomi oltre il limite del dialetto | Diagnostica prima dell'esecuzione, senza troncamenti silenziosi. |

### 9.1 Subtable e scope: casi da aggiungere al corpus runtime

| Caso | Ingresso / variazione | Risultato o proprietà richiesta |
|---|---|---|
| SP01 | Subtable di tabella con condition_* | Filtro parametrizzato, virtuale booleana e metadati preservati. |
| SP02 | Subtable di package con maintable | Nomi SQL, campi/relazioni ereditati, __subtable e default corretti; nessuna tabella/view fisica inventata. |
| SP03 | Subtable='*' insieme a partizione logica | Disabilitato solo il filtro subtable. |
| SP04 | current e allowed entrambi presenti | Precedenza current secondo baseline. |
| SP05 | allowed con campo NULL | NULL ammesso nel ramo legacy; comportamento dichiarato nel nuovo profilo. |
| SP06 | current falsy, allowed vuoto e fallback __allowed_partition | Oracle esatto e decisione sul profilo nuovo, senza attribuire garanzie di autorizzazione inesistenti. |
| SP07 | Più attributi partition_* e subtable di package | Caratterizzare prima dimensione ed esclusione dall'eredità degli attributi partition_*. |
| SP08 | INSERT/UPDATE/DELETE tramite specializzazione | Discriminatore, appartenenza, filtri e hook verificati, oltre alle SELECT. |
| SP09 | Scope logico, tenant e partizioni fisiche insieme | Identità distinte e bypass circoscritti; nessun DDL per un semplice scope logico. |

### 9.2 Oggetti nativi: corpus prospettico del migratore

| Caso | Ingresso / variazione | Risultato o proprietà richiesta |
|---|---|---|
| DB01 | View con funzione e tabelle dipendenti | Introspezione/creazione ordinate e query corrette dopo la migrazione. |
| DB02 | Funzioni sovraccaricate e modifica di firma/corpo | Identità per firma e piano corretto di sostituzione/ricreazione. |
| DB03 | Trigger DML insieme a hook Python | Effetti non duplicati, fasi ed errori/rollback verificati anche su bulk. |
| DB04 | Event trigger DDL | Capability separata da trigger DML; nessun no-op silenzioso dichiarato come supporto. |
| DB05 | Round-trip e rimozione con dipendenze esterne | Secondo diff vuoto quando previsto; dipendenze non gestite segnalate senza CASCADE implicito. |
| DB06 | Partizioni fisiche, attach/detach e dati ai limiti | DDL, routing e conservazione dei dati verificati su PostgreSQL reale. |

Questi casi DB descrivono lavoro futuro: non attestano capability del migratore
attuale. La matrice seguente riguarda il traguardo di esecuzione dei dialetti.

| Famiglia | SQLite | PostgreSQL | Altri adapter |
|---|---|---|---|
| Colonne, relazioni, filtri, query Bag comuni | Obbligatoria | Obbligatoria | Obbligatoria prima di dichiarare supporto. |
| Formula SQL standard/portabile | Verificare funzioni effettive | Verificare funzioni effettive | Per capability. |
| JSON/XML di subQueryColumn legacy | Non presumere portabilità | Obbligatoria | Provider o errore capability. |
| TSQUERY/TSRANK/TSHEADLINE | Fuori dal sottoinsieme PostgreSQL | Obbligatoria | Implementazione dedicata, se promessa. |
| VECQUERY/VECRANK | Fuori dal sottoinsieme PostgreSQL | Con estensione vector reale | Implementazione dedicata, se promessa. |
| Lock | Verificare omissione legacy | Verificare in transazione | Semantica specifica. |
| Liste vuote/NULL/regex/cast | Obbligatoria | Obbligatoria | Obbligatoria per driver. |

Regressioni ulteriori: ripetere la compilazione, compilare query concorrenti
con ambienti distinti, usare lo stesso modello in più tenant, variare il
prefisso alias, formulare due volte lo stesso campo con varianti diverse,
serializzare il risultato compilato se questa sarà un'API supportata.

## 10. Corpus upstream e criterio di copertura

Importare o adattare i test applicabili da:

- `tests/sql/test_compiler_coverage.py`: famiglie di formule, alias, CASE,
  COALESCE, funzioni SQL, window/FILTER, subquery, composite, pyColumn, Bag,
  relazioni, partizioni, subtable, macro, record e joinConditions.
- `tests/sql/test_compiler_simulation.py`: percorsi reali multi-hop.
- `tests/sql/e_query_test.py` e `h_query_surface_test.py`: API e risultati.
- `tests/sql/test_macro_registration.py` e `test_vecquery_macro.py`: registry
  e macro specialistiche.
- Test del decoder date e dei singoli adapter per il confine non contenuto
  nel compiler stesso.

Non basta trasferire le asserzioni deboli: dove il test upstream verifica
soltanto il tipo del risultato o la presenza di almeno una riga, aggiungere
una risposta esatta sul dataset piccolo.

Ogni query reale importata deve conservare anche definizioni delle virtuali,
relazioni, policy e contesto necessari. Una stringa SQL da sola non è un caso
di conformità GenroPy completo.

Le prestazioni costituiscono una suite separata: numero di query, volume righe,
tempo di compilazione, piano DB, consumo memoria e costo del postprocessing.
Nessun miglioramento prestazionale può compensare un valore o una cardinalità
diversi senza una modifica di contratto dichiarata.

## 11. Verifica eseguita durante la stesura

I 16 controlli numerici principali del dataset sono stati eseguiti con SQL
diretto su SQLite in memoria: conteggi con/senza policy, gruppi, valori distinti,
molteplicità dei LEFT JOIN e somme prima/dopo il join. Tutti concordano con i
valori riportati. Questa verifica controlla il dataset di specifica: non esegue
il compiler GenroPy e non certifica alcuna implementazione nuova.
