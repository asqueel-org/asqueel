# 58 — Checklist del compilatore e stato corrente

**Aggiornamento 15 ottobre 2026 — campi condivisi dalle options verificati:**
[Rapporto 94](94-shared-option-fields.md). Le 12 differenze d'ordine sono accettate;
non richiedono riallineamento. Verificati tipo, attributi, relazioni e unicità dei
campi condivisi, incluso `invc.product_group._row_count`. **366 test passati**
nel gruppo mirato, inclusi 19 nuovi contratti e le verifiche sui 74 modelli.
Nessuna modifica alla produzione; aggiunti test e documentazione.

**Aggiornamento 15 ottobre 2026 — options prima delle dichiarazioni:**
[Rapporto 93](93-options-first-object-renderer.md). Il renderer gerarchico
consuma prima le options sulla copia privata della source, conservandole sugli
oggetti senza ripeterne gli effetti. Compilatore invariato. I due contratti `star`
ora passano senza xfail; 62/74 ordini fisici identici al legacy, 12 differenze
residue interne alle espansioni documentate separatamente. JSON migration
invariato sui 74 modelli. Le note successive conservano lo storico.

**Decisione 15 ottobre 2026 — wildcard:** restano soltanto `*` e le colonne
esplicite (incluse espressioni e percorsi di relazione già supportati).
I wildcard avanzati escono dalla TODO: [cose non portate, R-11](41-deferred-features.md#r-11--wildcard-avanzati).
Nessuna modifica al compilatore. Il confronto dell'ordine delle colonne di `*`
e l'intervento nel renderer sono ora documentati nel [rapporto 93](93-options-first-object-renderer.md).

**Aggiornamento 15 ottobre 2026 — fetch e count eseguibili sul nuovo albero:**
[Rapporto 92](92-hierarchical-fetch-count.md). Terminali reali sul database
proprietario, righe Toolbox NamedList, ambiente corrente e transazione condivisa.
Count interpreta il risultato secondo il legacy; nessun handler verso molti.
Record, Selection e scritture gerarchiche restano fuori perimetro.
**5.147 test passati, 21 skip, 2 xfail preesistenti**. Ruff e Sphinx passano;
JSON migration invariato sui 74 modelli. Le note successive conservano lo storico.

**Aggiornamento 15 ottobre 2026 — count compilato sul nuovo albero:**
[Rapporto 91](91-legacy-tree-count.md). Stesso ramo legacy negli otto snapshot:
COUNT(*) per query semplici, chiavi di GROUP BY, proiezione conservata per
DISTINCT; ordinamento eliminato. SQL e kwargs senza esecuzione sul nuovo albero.
Nessun handler verso molti. **4.915 test passati, 21 skip, 2 xfail preesistenti**;
Ruff e Sphinx passano, JSON migration invariato sui 74 modelli. Le note successive
sono storiche.

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

**Stato corrente, 15 ottobre 2026 — renderer riallineato dopo R4:**
[rapporto 85](85-legacy-renderer-and-postgres-binding.md), [piano 79](79-legacy-compiler-realignment-plan.md).
Eliminate le scansioni dal renderer condiviso; assemblaggio e WHERE seguono il
legacy. **3.944 test passati, 13 saltati**, 148 SELECT fisiche e JSON migration
invariato. Scomparse le quattro differenze del renderer nel corpus R4.
Binding PostgreSQL invariato: proposta ClientCursor provata su otto SELECT,
da discutere prima dell’adozione. Collisione IN separata e invariata.
R5/relazioni non avviata. Misure aggiornate e limiti nel rapporto.
Le note successive conservano lo storico dei passi precedenti.

**Stato corrente, 15 ottobre 2026 — verifica R4 eseguita, accettazione aperta:**
[rapporto 84](84-legacy-realignment-r4.md), [piano 79](79-legacy-compiler-realignment-plan.md).
**3.918 test superati, 13 saltati**; 15 prove legacy, 148 SELECT fisiche e JSON
migration dei 74 modelli verificati. Confronto integrato sui tre compilatori:
82/84 casi eseguiti da entrambi con stessi risultati sul nuovo albero.
Restano la differenza di binding PostgreSQL, la collisione postgres3 già nota
e residui dello scanner nel renderer condiviso. SELECT ordinaria più rapida del
legacy; 100 proiezioni ripetute ancora 2,3–2,6 volte più lente. Nessuna modifica
agli algoritmi; R5/relazioni non avviata. Dettagli e misure nel rapporto.
Le note successive conservano lo storico dei passi precedenti.

**Stato corrente, 14 ottobre 2026 — R3 completata:**
[rapporto 83](83-legacy-realignment-r3.md), [piano 79](79-legacy-compiler-realignment-plan.md).
Preparazione SQL/kwargs negli adapter secondo il legacy, senza I/O implicito.
Psycopg 3 usa l’espansione IN dell’adapter legacy postgres3, con protocollo nominato.
**3.918 test superati, 13 saltati**; 100 confronti sul riferimento, 24 verifiche
d’integrazione e 148 SELECT native senza differenze. Otto snapshot confrontati.
Il prossimo passo è R4, prima delle relazioni. Nomi generati, collisioni ed errori
affidati al driver mantengono i contratti legacy documentati nel rapporto.
Le note successive conservano lo storico dei passi precedenti.

**Stato corrente, 14 ottobre 2026 — R2 completata nel perimetro locale:**
[rapporto 82](82-legacy-realignment-r2.md), [piano 79](79-legacy-compiler-realignment-plan.md).
Proiezioni conservate come nel legacy ed embedFieldPars sul WHERE, senza nuove
sintassi. **3.791 test superati, 13 saltati**; quattro test legacy originali
superati, 624 confronti sugli otto snapshot e 148 SELECT native senza differenze.
Prossimo passo R3: preparazione negli adapter, poi R4 prima delle relazioni.
Le note successive conservano lo storico dei passi precedenti.

**R1 completata sul nuovo albero:** [rapporto 81](81-legacy-realignment-r1.md).
Raccolta, risoluzione e sostituzione dei campi ora seguono il legacy. Restano
R2 (proiezioni/parametri), R3 (adapter) e R4 (verifica integrata), prima del
raccordo relations. **3.681 test superati, 13 saltati**; nessuna nuova sintassi.
Le disponibilità del vecchio percorso elencate sotto non equivalgono al port
sul nuovo albero né alla parità con il legacy.

**R0 completata:** [contratti, test e decisioni aperte](80-legacy-realignment-r0-contracts.md).
Nessuna implementazione riallineata in questo passo; le disponibilità sotto
rimangono quelle del percorso precedente e non equivalgono ad approvazione.

**Priorità corrente:** il [piano 79](79-legacy-compiler-realignment-plan.md)
precede il raccordo relations. Le voci disponibili qui descrivono l'attuale
implementazione: non certificano la compatibilità legacy, messa in discussione
dal [confronto 78](78-scanner-legacy-comparison.md), né approvano le divergenze.

**Distinzione dei percorsi, 14 ottobre 2026:** le disponibilità indicate sotto
riguardano il compilatore sul modello precedente. Sul nuovo DbModel è ora
raccordata la sola SELECT fisica minima (fasi 0–1 del
[piano 76](76-hierarchical-compiler-plan.md), [rapporto 77](77-hierarchical-minimal-select.md)).
Relazioni, formule, options e macro restano da raccordare. Nessuna esecuzione,
nessun nuovo comportamento per mixin o RuntimeModel.

Aggiornamento: 14 ottobre 2026, dopo il passo 1 del [piano 56](56-read-compiler-plan.md).
Priorità successivamente acquisita: copertura delle formule attraverso tutti
i test legacy del compilatore. Censimento e baseline eseguiti nel
[rapporto 59](59-formula-legacy-baseline.md); primo raccordo SQL/alias/var_*
verificato nel [rapporto 60](60-native-sql-formulas.md) e raccordo select/exists/select_*
nel [rapporto 61](61-native-subqueries.md), seguiti dai metodi nel
[rapporto 62](62-native-method-formulas.md); porting completo ancora aperto. Sintassi
più amichevoli solo come futuro affiancamento da discutere; nessuna nuova firma.
Questa lista censisce il lavoro; non autorizza nuove firme o il port automatico
di tutte le funzionalità legacy. Il riferimento resta il legacy, con le
divergenze già concordate. Nessuna implementazione cambia con questo documento.

Obiettivo delle letture: **query + modello completo + ambiente → SQL e kwargs
pronti per il driver, senza esecuzione**. Il modello è quello già renderizzato:
il compilatore non ricostruisce la source e non riespande le options strutturali.

`[x]` significa disponibile nel perimetro specificato. `[ ]` indica lavoro
aperto: le etichette **parziale**, **da fare**, **da decidere** e **rinviato**
distinguono implementazioni incomplete da decisioni non ancora prese.
Il supporto sul modello risolto di basso livello non certifica quello di tutte
le dichiarazioni della grammatica nativa.
Le inverse ordinarie e le cinque child_count native sono raccordate nel
[rapporto 63](63-native-inverse-relations.md).

## 1. Contratto di compilazione e parametri

- [x] Ottenere insieme `compiled.sql` e `dict(compiled.params)` da un solo
  accesso a `query.compiled`, senza connessioni o esecuzione.
- [x] Riutilizzare il percorso risoluzione → piano → dialetto → driver,
  mantenendo separati identificatori SQL e valori.
- [x] Conservare i tipi Python dei valori, inclusi date, Decimal e NULL;
  segnalare parametri mancanti e non inoltrare quelli inutilizzati.
- [x] Gestire `:nome`, `:env_nome`, snapshot dell'ambiente e precedenza dei
  parametri espliciti; ricompilare la query con l'ambiente corrente.
- [x] Gestire IN/NOT IN con collection, raccolte vuote, NULL e collisioni
  dei nomi; supportare il percorso PostgreSQL `ANY` già verificato.
- [x] Isolare i parametri delle sottoquery già supportate e preservare gli
  argomenti originali quando una query viene riutilizzata.
- [x] Proteggere stringhe, commenti, identificatori quotati, cast `::` e
  dollar quote; preparare placeholder e percentuali per il driver scelto.
- [x] Estese le garanzie ai binding delle formule native SQL e var_*.
- [ ] **Rinviato:** estendere queste garanzie a catene e
  composizioni, compresi parametri omonimi e riuso della stessa query nei rami.
- [ ] **Da decidere:** comportamento legacy `embedFieldPars`, in cui un
  parametro può rappresentare `$campo` o `@relazione.campo`. Oggi è un valore
  stringa: non trasformarlo implicitamente in SQL.

## 2. Colonne e clausole della SELECT

- [x] Risolvere tabella/package/schema e nomi fisici dal modello.
- [x] Risolvere `$campo`, nomi quotati, `AS` e proiezioni esplicite;
  conservare origine e informazioni delle colonne quando note.
- [x] Accettare espressioni SQL fidate, per esempio CASE, COALESCE, CAST,
  COUNT e SUM, con parametri separati. Non è una validazione SQL universale.
- [x] Compilare WHERE, ORDER BY, LIMIT e OFFSET espliciti.
- [x] Compilare DISTINCT, GROUP BY e HAVING espliciti, con i controlli
  sulle combinazioni già supportate.
- [x] Produrre il piano/SQL di conteggio per query semplici, distinte e
  raggruppate. Il compilatore ha `plan_count`/`count`; il terminale applicativo
  `q.count()` esegue e non va confuso con l'estrazione senza I/O.
- [x] Compilare FOR UPDATE nel profilo supportato, senza acquisire lock
  durante la compilazione.
- [x] `*`: fisiche seguite dalle virtuali statiche, `bagFields=False` esclude
  le fisiche X. Verificato sui due dialetti: 73/74 tabelle compilabili;
  `adm.htmltemplate_atc` resta bloccata da pyColumn statiche (rapporto 65).
- [ ] **Da decidere dopo confronto legacy:** pkey implicita, ordine di
  tabella, alias automatici di espressioni e relazioni, `group_by='*'`.
- [ ] **Da valutare, non acquisito:** DISTINCT ON, IN su tuple di colonne, convenzioni REGEXP e ulteriori
  opzioni di lock. L'assenza di un'opzione dedicata non impedisce sempre SQL
  esplicito, ma non ne certifica il supporto strutturato.

## 3. Options del modello e filtri impliciti

- [x] Compilare le policy del precedente modello risolto: draft,
  cancellazione logica e partition, con le esclusioni esplicite supportate.
- [x] Raccordati i marcatori nativi di sys_fields e partition scalare.
  Valore assente opzionale: nessun filtro; required: errore; ignorePartition: bypass.
  Insiemi ammessi non ancora acquisiti per la option nativa.
- [x] Filtri effettivi verificati sulle 74 tabelle native, PostgreSQL e SQLite:
  66 con cancellazione logica, una con draft, due con partition (rapporto 65).
- [x] Verificati i default delle sottoquery: ignorePartition True,
  excludeDraft/excludeLogicalDeleted False, con override espliciti.
- [x] JOIN ordinari: i filtri root non si propagano alle tabelle collegate,
  come nel percorso legacy verificato. I FROM derivati appartengono al passo 3.

## 4. Relazioni e JOIN

- [x] Percorrere relazioni ordinarie to-one, anche su più passaggi,
  riutilizzando lo stesso JOIN quando il percorso ricorre nelle clausole.
- [x] Collegare chiavi fisiche anche composte, verificando nel modello
  l'unicità del target; distinguere relazioni diverse verso la stessa tabella.
- [x] Raccordate le inverse ordinarie su chiavi fisiche, con LEFT JOIN e riuso
  per percorso. Verificati cardinalità, chiavi composte e cinque child_count native.
- [ ] **Separato:** DISTINCT implicito e aggregazione runtime del legacy;
  nessuna deduplicazione o aggregazione automatica introdotta con le inverse.
- [ ] **Parziale, passo 6:** censire e tradurre le dichiarazioni di join
  già ammesse, incluse joinColumn e condizioni previste dalla grammatica;
  oggi la navigazione implementata usa uguaglianze fra chiavi fisiche.
- [ ] **Da fare, passo 6:** tradurre virtualRelation secondo la grammatica
  acquisita: relazione di base, condizione, `var_*`, `ask` e derivazioni ammesse.
  Rispettare i namespace provvisori `:var_*`, `:ask_*`, `:env_*`, senza
  trasformare `ask` in un'interazione UI del compilatore.
- [ ] **Da decidere nel caso concreto:** chiavi virtuali nei join e ulteriori
  condizioni legacy non ancora tradotte. Nessuna nuova firma implicita.

## 5. Formule e sottoquery dichiarate nel modello

La verifica va fatta **per tipo di colonna e per forma della formula**, non
con una sola voce generica. Tutte le dichiarazioni sotto sono conservate
nel modello; questo non significa che tutte arrivino già al SQL.

| Tipo / forma | Stato della compilazione | Lavoro aperto |
| --- | --- | --- |
| `formulaColumn(sql_formula='...')` / `expression` | Raccordo nativo SQL completato, incluse dipendenze SQL, da metodi e percorsi to-one | Restano relazioni non supportate e macro non implementate |
| `formulaColumn(select=...)` | Raccordata anche la dichiarazione nativa; clausole/default comuni e inverse ordinarie | Restano casi dipendenti da virtualRelation; nessuna scelta automatica della prima riga |
| `formulaColumn(exists=...)` | Raccordo nativo, correlazione e binding verificati su PostgreSQL/SQLite | Restano eventuali dipendenze non supportate |
| Formula con `select_<nome>` / sottoquery nominate | Dichiarazioni native e riferimenti stringa a subquery_* raccordati; più sottoquery con scope distinti | RuntimeModel ancora aperto; costrutti sperimentali non abilitati |
| Formula con `var_*` / parametri locali | Binding locali compilati, isolati per formula e alias della riga | Estendere la verifica ai futuri operatori e al RuntimeModel |
| `formulaColumn(sql_formula=True)` / formula fornita da metodo | Raccordata a sql_formula_<nome>(attr) sulla tabella applicativa; attributi locali e due metodi sys_fields verificati | Integrare il modello effettivo quando sarà disponibile RuntimeModel; nessun registro nuovo |
| `aliasColumn(relation_path=...)` | Compilabile sui percorsi forward/inversi ordinari, anche con target formula SQL nativa o da metodo | Anche target sottoquery supportato; resta virtualRelation |
| `subQueryColumn(query=..., mode=...)` | Query dict raccordata; riferimenti stringa per semplice/JSON. 3/3 native compilano su PostgreSQL | XML richiede il dict come nel legacy; JSON/XML non tradotti per SQLite. `mode=None` resta il default; altri mode non generano aggregati impliciti |
| `bagItemColumn(bagcolumn=..., itempath=...)` | Raccordata su PostgreSQL: XPath parametrizzato, cast legacy e tipi custom risolti. 3/3 native compilano (rapporto 69) | SQLite rifiuta esplicitamente l’estrazione; nessun codec XML/Python o macro BAG/BAGCOLS aggiunto |
| `pyColumn(py_method=... / method=...)` | Dichiarazione e dipendenze conservate; calcolo non implementato | Non convertirla in SQL: l'eventuale preparazione degli input va distinta dal calcolo Python, che appartiene alla fase dei risultati |
| `compositeColumn(columns=...)` | Componenti e vincoli multicolonna già modellati; join su chiavi fisiche composte supportati | Non è una formula scalare né una nuova colonna fisica; un'eventuale proiezione come valore unico richiede un contratto, non una concatenazione inventata |

Per tutte le forme SQL restano da verificare anche dtype, `static` e inclusione
in `*`, alias di risultato, scope di `$`/`@`/`#THIS`, macro consentite, cicli,
collisioni e due usi della stessa dichiarazione. La presenza di SQL libero
nella query non sostituisce il supporto alla corrispondente colonna del modello.

- [x] Espandere formule SQL e alias nel modello risolto già supportato,
  seguire i riferimenti e rifiutare cicli.
- [x] Compilare sottoquery scalari/EXISTS, correlazioni `#THIS`, sottoquery
  nominate e cast nel percorso di basso livello già supportato.
- [x] Collegare formule SQL e alias della grammatica nativa al percorso
  esistente, senza riesaminare la source.
- [x] Tradurre `var_*` e isolare i binding locali,
  anche per due usi della stessa formula e per formule su tabelle correlate.
- [x] Collegare select/exists/select_* nativi, GROUP BY/HAVING/DISTINCT,
  correlazioni e default legacy; cardinalità verificata sul database.
- [x] Raccordate subQueryColumn con query dict: semplice, JSON/XML, dipendenze,
  alias, var_* e clausole comuni; sette test legacy verdi (rapporto 66).
- [x] Raccordate bagItemColumn native: estrazione XPath, attributi/posizioni, cast,
  alias, dipendenze e sottoquery con binding separati; test legacy e valori
  controllati PostgreSQL verificati ([rapporto 69](69-native-bag-items.md)).
- [ ] **Parziale, passo 6:** risolvere le dipendenze da virtualRelation senza
  importare le sintassi sperimentali. Inverse ordinarie raccordate.
- [x] Verificate dipendenze SQL, cicli, errori espliciti e scope dei parametri.
- [x] Verificate le dipendenze native da sottoquery nel perimetro del rapporto 61.
- [x] Raccordati i metodi sql_formula_<nome>(attr), comprese dipendenze, alias,
  var_* e select_* modificati nella copia locale degli attributi.
- [x] Formule e alias statici verificati tramite `*`; nessuna esclusione silenziosa
  delle statiche non compilabili. pyColumn rimane aperta (rapporto 65).
- [x] Riferimenti stringa a subquery_* sulla tabella della SELECT corrente,
  inclusi scope annidati e metodi forniti dalle formule SQL (rapporto 67).
- [ ] **Aperto:** integrazione del RuntimeModel. Non aggiungere provider o nuovi resolver. pyColumn e
  trasformazioni Python dei risultati non sono automaticamente traducibili in SQL.

## 6. Macro legacy

Sintassi, stato, limiti e TODO sono nel capitolo separato
[64 — Macro del compilatore](64-compiler-macros.md).
`#PREF` resta escluso dal lavoro corrente secondo il registro dei rinvii.

## 7. Query concatenate: SELECT FROM SELECT — rinviate

**Decisione del 14 ottobre 2026:** i passi 3 e 4 aspettano. Le firme e il
confronto legacy restano documentati, ma non sono nel lavoro corrente
([registro 41, R-09](41-deferred-features.md#r-09--query-concatenate-e-operatori-fra-query)).

- [ ] **Rinviato, passo 3:** `q.query(...).query(...)`, usando la query
  precedente come FROM e vedendo solo le colonne che essa espone.
- [ ] **Alla ripresa:** preservare l'origine delle colonne e consentire un JOIN
  esterno come `@customer_id.name` quando `customer_id` è stato proiettato.
- [ ] **Alla ripresa:** mantenere al proprio livello filtri, aggregazioni,
  ordinamenti e limiti, con alias/binding distinti e riuso senza mutazioni.
- [ ] **Da decidere alla ripresa:** chiavi rinominate, origini ambigue, colonne non esposte
  necessarie al join e innesto su risultati composti. Non aggiungere colonne
  nascoste né indovinare relazioni dal nome.

## 8. Operatori fra query della stessa tabella — rinviati

- [ ] **Rinviato, passo 4:** `+` UNION, `|` UNION ALL, `&` INTERSECT,
  `-` EXCEPT secondo la firma legacy acquisita.
- [ ] **Alla ripresa:** preservare parentesi e ordine degli operandi, oltre
  all'ambito di ORDER BY/LIMIT/OFFSET delle singole foglie.
- [ ] **Alla ripresa:** controllare compatibilità delle proiezioni e del contesto,
  senza cast o riallineamenti inventati; produrre una sola coppia SQL/kwargs.
- [ ] **Alla ripresa:** coprire riuso, rami ripetuti, NULL, duplicati, insiemi vuoti
  e collisioni; correggere i difetti legacy riprodotti nel piano 56.
- [ ] **Da verificare alla ripresa:** limiti del dialetto SQLite e clausole incompatibili.
  PostgreSQL resta il riferimento richiesto.

## 9. Controllo opzionale per fonti non fidate

- [x] Prova isolata SQLGlot documentata: distinguere CASE/COALESCE lecite
  da scritture, anche DELETE dentro una CTE.
- [ ] **Rinviato:** definire e integrare il check finale attivabile a richiesta,
  tenendo conto di tutti i rami, CTE, funzioni consentite e placeholder.
  La direzione è acquisita, la firma e la policy completa no.
- [ ] **Da verificare in quel lavoro:** SELECT e operatori leciti, query che
  invocano funzioni con effetti e limiti del controllo statico. Il compilatore
  corrente accetta SQL fidato: non è già una sandbox per SQL dal browser.

## 10. Fronte scritture, successivo alle letture

- [x] Esistono primitive di compilazione INSERT/UPDATE/DELETE con valori
  separati, RETURNING e nomi fisici; esistono anche soft-delete/restore nel
  profilo supportato. Non partiamo da zero su questo fronte.
- [ ] **Rinviato:** fare il raccordo e la verifica sistematica rispetto al
  modello nativo e alle convenzioni legacy, prima di dichiarare il fronte
  scritture completo. DML con attraversamento di relazioni resta non supportato.

Trigger Python, generazione dei valori di sistema durante una scrittura,
validazioni operative, transazioni ed esecuzione appartengono al runtime;
non sono lavoro SQL del compilatore, anche se il flusso di scrittura li usa.
La generazione del JSON migrations è un altro percorso, già consegnato.

## 11. Verifica e criteri di completamento

- [x] Risultati fetch/execute/RETURNING raccordati a NamedList di Toolbox 0.18.0:
  accesso per nome/posizione e righe modificabili, senza un contenitore nuovo.
  record.output('dict') conserva il dict (rapporto 68).
- [x] Ultima suite completa: **1940 passati, 13 saltati**, inclusi PostgreSQL
  e SQLite; verifiche nel [rapporto 68](68-named-list-fetch.md).
  Questi numeri non
  significano che tutte le funzionalità legacy siano coperte.
- [x] Test dedicati impediscono connessioni ed esecuzione nella compilazione.
- [ ] **Da fare, passo 7:** matrice aggiornata delle dichiarazioni native,
  con SQL, kwargs e risultati attesi verificati sulle fixture PostgreSQL.
- [ ] **Da fare:** coprire formule, options, sottoquery e relazioni di tutti
  i package dei 74 modelli, distinguendo esplicitamente le esclusioni.
- [ ] **Rinviato con i passi 3–4:** verificare catene e composizioni insieme a formule,
  collection e ambiente, non soltanto le funzionalità isolate.
- [ ] **Da fare:** aggiornare esempi e limiti dopo ogni incremento; ogni
  divergenza dal legacy deve avere una decisione o una motivazione verificata.

La sonda del documento 55 compilava le proiezioni fisiche di **74/74** tabelle,
ma `*` solo su **3/74**. È una baseline precedente al passo 1, non una nuova
misura né una certificazione delle letture native. Il passo 1 non ha corretto
il collegamento delle options, delle formule native o di `*`.

La sonda aggiornata del rapporto 66 compila **460/462 formulaColumn**,
**45/46 aliasColumn** e **3/3 subQueryColumn** su PostgreSQL.
Le 134 formule da metodo e le 134 dipendenti ora compilano.
Compilano anche le cinque child_count con inverse. Le due formule ancora bloccate
richiedono un valore di ambiente assente nella sonda (1) e `#PREF` (1).
Il caso `#PREF` è ora un'esclusione concordata dal perimetro corrente (R-08),
non un'attività da implementare per chiuderlo; il conteggio storico resta invariato.
È un censimento di compilazione, non una verifica dei risultati di tutte
le formule sui dati.

## Posizione nel piano e confini

| Passo del piano 56 | Stato |
| --- | --- |
| 1. Contratto SQL/kwargs, riuso e macro di filtro | Completato |
| 2. Options native, filtri e `*` | Completato nel perimetro del rapporto 65; pyColumn escluse |
| 3. SELECT FROM SELECT con relazioni esterne | Rinviato per decisione dell’utente (R-09) |
| 4. UNION / UNION ALL / INTERSECT / EXCEPT | Rinviato per decisione dell’utente (R-09) |
| 5. Formule native e var_* | SQL, metodi, alias e parametri locali raccordati; corpus completo ancora aperto |
| 6. Sottoquery e relazioni concordate | select/exists/select_* e inverse ordinarie raccordati; restano altre colonne e relazioni |
| 7. Verifica integrata e documentazione | Da completare sul perimetro attivo; catene/composizioni rinviate |

**Il numero di passi chiusi non misura la percentuale del compilatore:** il motore
di base esisteva già e i passi hanno dimensioni diverse. Il risultato attuale
è una compilazione di query singole utilizzabile nel profilo supportato;
la copertura dell'intero modello nativo resta incompleta.

Restano fuori dal lavoro corrente: nuova grammatica Builder/wherebag,
nuovi codec JSON/TYTX, variant, tableAlias, aggregateRows, system_records,
locked records e diagnostics rinviati. Sulle virtualRelation non si
reintroducono inverse, generazione automatica delle inverse, limit, order_by
o one_one. Le proposte GEP di aggregazione automatica e gli esperimenti di
ottimizzazione/LATERAL non diventano requisiti approvati con questa lista.

Fonti operative: [indagine 55](55-select-sql-and-kwargs-investigation.md),
[piano 56](56-read-compiler-plan.md), [riesame 57](57-legacy-compiler-refactoring-review.md),
[grammatica 42](42-configuration-grammar.md), [check SQL 54](54-query-recipe-and-sql-check.md),
`src/asqueel/compiler.py` e test del compilatore. L'[audit 10b](10b-compiler-feature-audit.md)
è una fonte storica delle lacune, non la fotografia aggiornata del codice.
