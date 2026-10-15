# Handoff — modello, compilatore e scritture Asqueel

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

**Stato corrente, 15 ottobre 2026 — raccordo richiesto della fase 4 verificato:**
[Rapporto 90](90-legacy-rewrite-phase4.md). Raccordati options native, filtri,
star, macro già portate e bagItemColumn sul nuovo albero; pkey automatica opt-in
con `addPkeyColumn=True`, default False. Nessun handler many_*.
148 prove di visibilità sui 74 modelli; JSON migration invariato. Riusata con
approvazione esplicita la correzione IN_RANGE per limiti NULL su PostgreSQL.
Ordine star diverso per le colonne sys_fields preesistenti nell'albero registrato
separatamente. **4.801 test passati, 21 skip, 2 xfail** per tale ordine; Ruff e
Sphinx passano, mypy conserva i due errori preesistenti. Alla data di questo
rapporto count e wildcard avanzati erano aperti; gli aggiornamenti in testa
registrano il raccordo del count e l’esclusione dei wildcard avanzati.
Le note successive sono storiche.

**Stato corrente, 15 ottobre 2026 — fase 3 completata:**
[Rapporto 89](89-legacy-rewrite-phase3.md), [piano 86](86-legacy-compiler-logical-phases.md).
Sul nuovo albero sono raccordate formule SQL e da metodo, alias, dipendenze,
var_*, select/exists/select_*, subQueryColumn e metodi subquery_*.
Ricorsione legacy, alias SQL e mangler separati, unica preparazione finale
SQL/kwargs. Nessun handler many_*; RuntimeModel e mixin restano separati.
334 richieste supportate confrontate con il legacy (332 SQL/kwargs equivalenti,
2 con normalizzazione dei nomi locali dipendenti da id nel riferimento).
**4.516 test passati, 21 skip, 10 xfail previsti**. JSON migration invariato
sui 74 modelli; Ruff e Sphinx passano, mypy conserva due errori preesistenti.
Prossimo passo: fase 4, options/filtri, star, macro, bagItemColumn e clausole
esterne rimanenti. Nessun cambio del compilatore predefinito o delle scritture.
Le note successive sono storiche; la fase 2 resta nel [rapporto 88](88-legacy-rewrite-phase2.md).

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

**Stato corrente, 14 ottobre 2026 — R1 completata:**
[rapporto 81](81-legacy-realignment-r1.md), [piano aggiornato](79-legacy-compiler-realignment-plan.md).
SELECT fisica sul nuovo albero: algoritmi legacy per raccolta, risoluzione e
sostituzione dei riferimenti; preparazione delegata una sola volta, senza I/O.
Rimosse dal raccordo le estensioni lessicali non concordate. **3.681 test superati,
13 saltati**; 148 SELECT native confrontate con GenroPy, 10.584 confronti degli
helper su otto snapshot senza differenze. Prossimo passo R2, poi R3/R4 prima
delle relazioni. Adapter ancora da riallineare integralmente; nessuna parità
complessiva dichiarata. Il legacy è la specifica: domande solo per impedimenti
concreti. Le note seguenti descrivono i passi precedenti, non lo stato corrente.

**Alias delle sottoquery, decisione acquisita:** seguire il legacy anche nei
prefissi: `aliasPrefix = '%s_t' % alias` dalla proprietaria esterna, per esempio
`t0_t0`, `t0_t1`, oppure `t1_t0`. Alias delle tabelle separati dai namespace e
dagli allocatori dei parametri; nessun prefisso derivato da `_Bindings.namespace`.
Annotati contratto e verifiche nei piani 79 e 76. Solo documenti, codice invariato.

**Decisione sugli adapter, 14 ottobre 2026:** mantenere la delega legacy:
risoluzione del modello nel compilatore, `adapter.compileSql` per assemblare
SQL, preparazione comune e `adapter.prepareSqlText` separate dall'esecuzione.
Quoting/alias/macro restano delegati anche durante la compilazione. Nessuna
ramificazione SQLite/PostgreSQL nel nucleo. [Piano 79 aggiornato](79-legacy-compiler-realignment-plan.md).
Solo documenti: M1 resta aperta per gli adapter. **M2/M3 chiuse sul legacy**:
commenti e stringhe seguono template, sostituzioni ed escape legacy, senza
protezioni aggiuntive. Nessuna estensione lessicale approvata. R1 non iniziata.

**R0 completata, 14 ottobre 2026:** [rapporto 80](80-legacy-realignment-r0-contracts.md).
Classificati 71 casi / 132 osservazioni; fissate 19 definizioni legacy e 15
test attuali con conflitti/decisioni pendenti. Verifiche: 294 test Asqueel e
6 prove legacy compile-only superati. Nessuna modifica al compilatore o ai test
esistenti, nessun miglioramento approvato. R1 non avviata. La proposta iniziale
di discutere M1 è stata ricollocata nel gruppo adapter dalla decisione sopra.

**Priorità corrente, 14 ottobre 2026:** [piano 79](79-legacy-compiler-realignment-plan.md)
per riallineare il compilatore agli algoritmi legacy prima di proseguire con
relations. Il [confronto 78](78-scanner-legacy-comparison.md) ha evidenziato
compatibilità perse e vantaggi solo circoscritti del percorso attuale.
Ripristino e miglioramenti sono separati; questi ultimi si decidono uno alla
volta prima di implementarli. Solo documentazione in questo passo.

**SELECT minima gerarchica, 14 ottobre 2026:** completate le fasi 0 e 1 del
[piano 76](76-hierarchical-compiler-plan.md), nel
[rapporto 77](77-hierarchical-minimal-select.md). Query fisiche → SQL e kwargs,
nessuna esecuzione o conversione in ResolvedModel. Confrontati gli otto snapshot
legacy e verificata uguaglianza con il precedente compilatore sulle 74 tabelle,
sia PostgreSQL sia SQLite, nel perimetro esplicito. Il default resta invariato.
Prima della navigazione legacy del ramo relations viene ora il piano 79.
Formule, filtri impliciti,
star e macro ancora da raccordare al nuovo albero; mixin/RuntimeModel separati.
Le sezioni successive descrivono gli incrementi precedenti.

**JSON migration gerarchico, 14 ottobre 2026:** completata la fase 5 del piano 70.
to_physical_builder accetta DbModel direttamente, senza ResolvedModel intermedio.
JSON identico su tutti i 74 modelli, rispetto al percorso precedente e al legacy
nel perimetro ammesso. Verificati 789 colonne, 58 FK, 282 indici e ciclo PostgreSQL
temporaneo applicazione/introspezione/seconda diff vuota, anche dopo evoluzione.
Compilatore non modificato; default e decisioni sui mixin restano separati.
[Rapporto 75](75-hierarchical-migration-json.md).

**Collegamento tabella/modello, 14 ottobre 2026:** implementato il primo raccordo
DbTableObj ↔ SqlTable ↔ SqlDatabase sul nuovo albero. `.dbtable` viene creata
prima dei figli come nel legacy; il database riusa quelle istanze e `column()`
restituisce gli oggetti del modello. Il fallback a `.model` resta attivo.
Il renderer offline continua a restituire DbModel; il collegamento operativo
è esplicito tramite SqlDatabase. Compilazione e scritture su questo percorso
sono rifiutate esplicitamente; il default precedente resta funzionante.
Mixin, namespace e RuntimeModel ancora da decidere; JSON migration completato
successivamente nel rapporto 75. [Rapporto 74](74-hierarchical-table-binding.md).

**Renderer gerarchico alternativo, 14 ottobre 2026:** implementato il percorso
`objects_tree` usando la walk generica e costruendo gli oggetti in finalize.
Ramo globale relations e viste lazy confrontati con il legacy: 144 nodi
ordinari identici; 74 modelli, 789 colonne fisiche e 526 virtuali.
Il renderer corrente resta il default; compilatore ed esecuzione SQL non sono
raccordati al nuovo albero. La proiezione JSON è ora completata nel rapporto 75.
[Piano 70](70-hierarchical-object-renderer-plan.md) e
[rapporto 71](71-hierarchical-object-renderer.md) distinguono verifiche e limiti.
I risultati SQL precedenti non certificano fedeltà architetturale del compilatore.

**Priorità aggiornata, 14 ottobre 2026:** SELECT FROM SELECT e operatori fra
query sono rinviati per decisione dell’utente ([R-09](41-deferred-features.md#r-09--query-concatenate-e-operatori-fra-query)).
Il lavoro corrente riguarda il modello gerarchico alternativo; il compilatore resta separato.

**bagItemColumn e guide connessioni, 14 ottobre 2026:** [rapporto 69](69-native-bag-items.md).
Raccordo PostgreSQL con XPath parametrizzato, cast e tipi custom legacy;
3/3 colonne native compilano. Confrontati otto snapshot e portati 15 test legacy,
con prove aggiuntive su valori e isolamento dei parametri. SQLite non emulato.
Guide CLI/configurazione riallineate alle connessioni nominate già implementate.

**Fetch e Toolbox 0.18.0, 14 ottobre 2026:** [rapporto 68](68-named-list-fetch.md).
Porting NamedList verificato con otto test legacy. I due driver restituiscono
direttamente quel contenitore per fetch/execute/RETURNING, con nomi, posizioni
e valori modificabili. record.output('dict') conserva il dict. Dipendenza,
lock ed esempi aggiornati; suite **1940 superati, 13 saltati**.

**Metodi subquery_*, 14 ottobre 2026:** [rapporto 67](67-native-subquery-methods.md).
Riferimenti stringa raccordati a metodi senza argomenti sulla root della SELECT
corrente, come nel legacy. Il risultato mapping usa il compilatore comune.
Confrontati otto snapshot con sette nuove prove di contratto; nessun test storico
dedicato trovato. Suite **1922 superati, 13 saltati**. XML richiede ancora il dict;
RuntimeModel, query concatenate e operatori restano separati/rinviati.

**subQueryColumn native, 14 ottobre 2026:** [rapporto 66](66-native-subquery-columns.md).
Raccordate query dict semplici su PostgreSQL/SQLite e JSON/XML su PostgreSQL,
riusando piano SELECT e scope esistenti. Sette test legacy verdi e 3/3 colonne
native compilabili; suite **1870 superati, 13 saltati**. Riferimenti stringa a
metodi di sottoquery ancora aperti; nessuna traduzione JSON/XML inventata per
SQLite, nessun DISTINCT automatico. Query concatenate e operatori restano rinviati.

**Options native e wildcard, 14 ottobre 2026:** [rapporto 65](65-native-options-and-star.md).
Passo 2 chiuso: marcatori sys_fields, partition scalare confermata, espansione
fisiche/statiche e bagFields. Filtri verificati sui dati di tutte le 74 tabelle,
PostgreSQL e SQLite. `*` compila su 73/74; adm.htmltemplate_atc richiede pyColumn
statiche ancora non supportate. Insiemi ammessi della partition rinviati;
nessuna nuova convenzione di ambiente o comportamento sulle scritture.
Suite: **1840 superati, 9 saltati**; Ruff, mypy e Sphinx strict superati.

**Decisione del 14 ottobre 2026:** `#PREF` è tra le funzionalità legacy non
portate, esclusa dal lavoro corrente: [registro 41, R-08](41-deferred-features.md#r-08--macro-pref).
La formula `invc.invoice_row.adjusted_total` resta conservata e non compilabile;
non viene introdotta alcuna sostituzione automatica. I censimenti sotto
mantengono i numeri rilevati, con questo caso classificato come esclusione concordata.

**Inverse ordinarie, 14 ottobre 2026:** [rapporto 63](63-native-inverse-relations.md).
Riusato il percorso LEFT JOIN con unicità verificata sul lato one; nessuna
nuova sintassi o aggregazione automatica. Verificate le cinque child_count su
PostgreSQL e SQLite, preservando formule e cardinalità della query esterna.
Sonda a **460/462 formule e 45/46 alias**; suite **1633 superati, 9 saltati**.
Restano #PREF, un valore di ambiente assente nella sonda, virtualRelation,
altre famiglie di colonne e RuntimeModel. Gli incrementi sotto sono storici.

**Formule da metodo, 14 ottobre 2026:** [rapporto 62](62-native-method-formulas.md).
`sql_formula=True` invoca il metodo legacy sulla tabella tramite la classe
applicativa già esistente. Attributi modificabili locali alla compilazione,
var_* e select_* nel percorso comune, nessuna nuova sintassi. Raccordati i due
metodi di sistema: sonda a **455/462 formule e 45/46 alias** compilabili.
RuntimeModel studiato ma ancora da implementare; restano inverse, virtualRelation,
subQueryColumn, bagItemColumn e ulteriori macro. I paragrafi successivi conservano
gli esiti storici degli incrementi precedenti.

**Sottoquery native, 14 ottobre 2026:** [rapporto 61](61-native-subqueries.md).
Raccordati select/exists/select_* usando la SELECT comune anche per
GROUP BY/HAVING/DISTINCT. Default ignorePartition True riallineato al legacy;
override False disponibile. Scope separati per formule e sottoquery, nessuna
conversione automatica a JOIN. Sonda dei 74 modelli: 187 formule e 45 alias
compilabili. Restano metodi, cinque sottoquery con relazioni inverse,
subQueryColumn, altre macro, virtualRelation e RuntimeModel.

**Raccordo formule SQL native, 14 ottobre 2026:** [rapporto 60](60-native-sql-formulas.md).
Implementati SQL, dipendenze, alias e var_* senza nuove firme. Separati scope
dei parametri e alias SQL; stato limitato alla compilazione, nessuna mutazione
del modello o currentEnv. 93 test legacy passati, 3 skip originali SQLite;
sonda senza I/O: 159 formule e 44 alias compilano sui 74 modelli nativi.
Restano sottoquery native, metodi, ulteriori macro e RuntimeModel. I numeri
della baseline sotto descrivono lo stato precedente a questo raccordo.

**Baseline formule, 14 ottobre 2026:** [rapporto 59](59-formula-legacy-baseline.md).
Censiti otto riferimenti legacy; suite di riferimento 645 pass/10 skip e next
746 pass/10 skip. Fallimenti dei refactor e limiti del dataset v2 documentati.
Asqueel: 197 test del profilo esistente verdi; sulle 526 virtuali native compilano
39 alias, mentre 462 formule (incluse 134 delegate a metodi), 7 alias e gli altri
tipi restano bloccati. Priorità al raccordo delle formule e al porting dei test;
nessuna nuova sintassi o implementazione del core in questo censimento.

**SQL e kwargs senza esecuzione, 14 ottobre 2026:** completato il passo 1 del
[piano 56](56-read-compiler-plan.md). API esistente `compiled = q.compiled`,
poi `compiled.sql` e `dict(compiled.params)`. Aggiunti `#IN_RANGE` e `#PERIOD`
con algoritmi legacy e decoder già presente in Toolbox 0.17.0; differenze
motivate e limiti registrati nel piano. Suite completa: 1350 passati, 1 saltato,
con PostgreSQL e SQLite. Il prossimo passo è il raccordo delle options native
ai filtri e dell'espansione `*`; catene, operatori e formule native restano aperti.

**Refactor storici riesaminati, 14 ottobre 2026:** [rapporto 57](57-legacy-compiler-refactoring-review.md).
Letti v2/v3/v4, compiler-simplify, compiler_next_step_1 e le conversazioni locali
SQL archaeology. Utili la separazione colonne/alias e la risoluzione comune
delle relazioni; non sono già una query derivata navigabile. Nel core esiste
`ResultColumn.source`: verificarne l'uso prima di aggiungere strutture per il
passo 3 del piano 56. Nessuna adozione implicita di aggregazioni automatiche,
LATERAL o riscritture di sottoquery; suite storiche non rieseguite.

**Query concatenate, 14 ottobre 2026:** aggiunte al [piano 56](56-read-compiler-plan.md)
come passo dedicato: `query(...).query(...).query(...)` significa SELECT FROM
SELECT. Ogni livello vede la proiezione precedente e può generare join tramite
le relazioni dei campi esposti: `customer_id` → `@customer_id.name`. Conservare
l'origine del campo nel modello; non dedurre una relazione dal solo nome.
Obiettivo invariato: SQL e kwargs completi senza esecuzione. Firma acquisita,
implementazione ancora da fare; alias e origini ambigue da decidere esplicitamente.

**Composizione query, 14 ottobre 2026:** [piano del compilatore 56](56-read-compiler-plan.md).
Riferimento acquisito: branch legacy feature/compound_query, con `+` UNION,
`|` UNION ALL, `&` INTERSECT e `-` EXCEPT sulle righe proiettate. Obiettivo sempre
SQL e kwargs, senza esecuzione. Sonda isolata con metodi legacy originali e
foglie sintetiche: 50 confronti PostgreSQL, 40 conformi e 10 divergenze attese
(cache/parametri, raggruppamenti, clausole locali). Il porting deve correggerle;
nessuna implementazione degli operatori nel core. Sequenza attiva nel piano 56.

**Ripresa letture, 13 ottobre 2026:** [indagine SQL e kwargs](55-select-sql-and-kwargs-investigation.md).
Scelta corrente: query(...) nella forma legacy, compilata in SELECT e kwargs;
grammatica Builder delle clausole rinviata. Le prove compilano le proiezioni
fisiche su tutte le 74 tabelle, ma i filtri delle options native, *, formule e
altre dichiarazioni richiedono ancora il raccordo descritto nell'indagine.
Approvata la direzione del [controllo finale SQL](54-query-recipe-and-sql-check.md)
con SQLGlot per fonti non fidate; check a richiesta ipotizzato senza firma/default.
Nessuna integrazione nel core. Non anticipare scritture o variant.

**Release 0.6.0, 13 ottobre 2026:** bump del core e documentazione aggiornata;
[release notes](../guide/release-notes.md#060). Il perimetro consegnato è
source nativa → oggetti completi → JSON migrations. Compilazione delle nuove
dichiarazioni ed esecuzione dei comportamenti restano la fase successiva.

**Fasi strutturali 0–6 completate, 13 ottobre 2026:** [rapporto 53](53-native-invoice-render-and-migration.md).
Source nativa di 74 modelli (sys 16, adm 40, invc 18), oggetti completi e JSON
migrations senza source legacy espansa. 789 colonne fisiche, 526 virtuali,
58 FK, 282 indici, una UNIQUE composita. JSON uguale all'oracolo legacy dopo
la sola esclusione concordata di sys.locked_record; sei virtuali system_records
escluse dal modello. PostgreSQL: applicazione, introspezione, seconda diff vuota
e modifiche controllate verificate. Suite: 1278 pass, 1 skip; Ruff/mypy superati.
Artefatti nativi in artifacts/test_invoice_pg/native; source in examples/test_invoice_pg.
I checkpoint sotto restano cronologia; non indicano lavoro strutturale ancora aperto.

**Rinvio successivo:** diagnostic, invalidFields e invalidRelations non sono
portati; da rivedere come opzioni di tabella. La firma diagnostics è rimossa
dalla grammatica attiva: [R-07](41-deferred-features.md#r-07--diagnostica-e-invalidità-configurabili-sulla-tabella).


**Fasi 2–3 completate, 13 ottobre 2026:** espansione nativa di sys_fields,
gerarchie, contatori, dynamic_fields, full_update, record_hash, audit e
protection con tag; completamenti fra tabelle per attachments, linked_to e
relative_index. Le options restano nel modello, anche quando non generano
colonne. Nessuna esecuzione di hook, formule o scritture; nessun nuovo resolver
o registro. C-02/C-03/C-04 del rapporto 52 corrette. Verifiche: **1124 pass,
1 skip**, Ruff e mypy superati; oracoli legacy invariati. Prossimo controllo: fase 4,
relazioni e finalizzazione; poi corpus nativo e JSON dagli oggetti.

**Fase 1 del render completata, 13 ottobre 2026:** attributi piatti con namespace,
`extract_kwargs` per validate_ e `runtime_values` di Builders per i resolver.
`metadata` come contenitore/elemento è rimosso definitivamente; anche gli
attributi UI sono piatti (`x_ui_*`). Table/column leggono la configurazione dal
modello completato, indipendente dalla source. Suite: **1084 pass, 1 skip**;
Ruff/mypy superati, JSON fisico del ponte legacy invariato. Le espansioni delle
options sono state completate nell'incremento successivo descritto sopra.


**Checkpoint grammaticale del 13 ottobre 2026:** revisione intermedia prima
del render completo. Validation conserva i validate_* nel dict della colonna;
validate_values è una differenza approvata dal legacy. VirtualRelation conserva
relation/table, condition, var_* e ask; :ask_<nome> è provvisorio e rivedibile
al compilatore. Inverse, limit, order_by e one_one virtuali sono rinviati.
SubQueryColumn mantiene query=None, mode=None e dtype, come il legacy.

La base grammaticale consente di iniziare la traduzione strutturale. Restano
da verificare la finalizzazione completa, configurare tutti i 74 modelli inclusi
e verificare source nativa → oggetti completi → JSON migrations.
Il JSON di tutti i package è già verificato dal ponte legacy espanso; questo
checkpoint non attesta la parità del percorso nativo né chiude la release.
Le firme non ancora riviste e la struttura interna di query restano proposte;
eventuali lacune emerse durante il render vanno discusse, non colmate con API
non concordate. Riferimenti correnti: 41 (rinvii), 42 (grammatica), 49 (decisioni),
51 (piano del render).

**Regola vincolante:** il legacy prevale per nomi, firme e significato. Uno
scostamento richiede una motivazione concreta e l'approvazione dell'utente
prima dell'applicazione. Restano valide le differenze già concordate, fra cui
DHZ/UTC. Perimetro attuale: grammatica e traduzione, senza anticipare esecuzione.

**Piano strutturale completato:** [render dalla source agli oggetti vivi](51-source-to-live-objects-plan.md), fasi 0–6 completate.
Piano aggiornato il 13 ottobre con fasi 0–6: mappa di copertura; render di base;
espansioni locali; completamenti fra tabelle; relazioni e finalizzazione;
source nativa dei 74 modelli inclusi; JSON dagli oggetti e prova migrations.
Ogni fase ha criteri di completamento e un commit previsto. La mappa degli
effetti legacy è ora verificata nel [rapporto 52](52-invoice-render-coverage.md):
75 modelli censiti, 74 inclusi nel port nativo completo verificato.
D-01/D-02 sono risolte: system_records e sys.locked_record fuori perimetro,
con divergenze documentate; il corpus nativo comprende 74 tabelle. Asqueel non
deve ora rimpiazzare integralmente GenroPy. sys_fields(syscode=True) è stata
successivamente approvata e implementata per __syscode A :20, indicizzata e
UNIQUE, False per default; non reintroduce il concetto di system_records.
C-01/C-02/C-03/C-04 corrette; copertura nativa verificata nel rapporto 53;
compilatore escluso.

**Decisione successiva:** [schemi dedotti dai package](50-schemas-from-packages.md);
nessuna dichiarazione schemas nella nuova configurazione.

**Perimetro attuale:** grammatica e traduzione del modello. I passaggi esecutivi
descritti nel piano generale non sono requisiti da anticipare nelle firme.

**Correzione della grammatica:** vedere [audit 49](49-grammar-corrections-and-audit.md).
Resolver esistenti per valori esterni/calcolati; nessun registro di variabili DB.
Nessun parametro provider o dichiarazione behavior nella grammatica.
Render completo degli oggetti implementato e verificato secondo il piano 51.

Aggiornato il **12 ottobre 2026**. Documento di ripartenza dopo la separazione
di Asqueel Migration e Asqueel DB Manager. Questa consegna prepara il lavoro:
non implementa le funzionalità descritte e non approva automaticamente le
proposte ancora aperte.

**Aggiornamento della ripresa, 12 ottobre:** il
[contratto 40](40-model-and-operation-recipes.md) registra la struttura DB con
schemi fisici e package distinti, le options ai diversi livelli e le ricette
delle operazioni trasferibili in JSON/XML anche dal browser. Per questi temi
prevale sui riepiloghi precedenti. Si procede con modello, verifica migrations,
poi lettura/scrittura mediante ricette, compilazione ed esecuzione.

**Grammatica ora specificata:** leggere la
[specifica 42](42-configuration-grammar.md) e la
[copertura 43](43-test-invoice-model-coverage.md) prima di riaprire le firme.
L'utente ha chiesto una proposta completa e revisionabile, incluse relazioni
e virtual relations, capace di configurare **tutti** i package di
`test_invoice_pg`: sys, adm e invc. Il censimento include 75 modelli attesi
e un contributo adm→sys.task; non è una build né un collaudo delle migrations.
**Piano operativo:** il [piano 44](44-core-release-plan.md) porta la grammatica
all'implementazione e alla prossima release proposta 0.6.0. P0/P1 sono
completate ([45](45-release-baseline-and-oracle.md),
[46](46-source-configuration-progress.md), chiusura P1 `d88c822`).
Il [report 47](47-invoice-migration-json.md) documenta il JSON integrale dei tre
package: 75 tabelle, 796 colonne, 58 FK, identico all'oracolo legacy;
applicazione PostgreSQL temporanea, introspezione e seconda diff vuota.
Il bridge usa la source legacy già espansa: registro provider ed espansioni
native avanzate P2–P5 restano aperti, seguiti da compilazione e scritture.
Branch `codex/core-release-0.6`, base main `4641a0e` (0.5.2).
Nessuna migrazione dell'istanza esistente e nessun incremento di versione/tag.


**Ultimo aggiornamento:** completata la sola grammatica delle options native,
con riferimenti simbolici ai provider ([report 48](48-options-source-grammar.md)).
Per indicazione esplicita dell'utente, il prossimo passo è il rendering a oggetti
vivi; nessuna espansione/provider aggiunta in questo incremento.

## Obiettivo e confini

Riprendere Asqueel core per completare il modo di dichiarare e leggere il
modello e il percorso modello → espressioni → query plan → SQL → esecuzione,
incluse `SELECT`, `INSERT`, `UPDATE`, `DELETE` e il ciclo dei trigger Python.
Prima si chiudono i dettagli di contratto necessari al singolo incremento,
poi si implementano con prove osservabili. Non ricominciare l'analisi da zero.

| Repository | Responsabilità |
| --- | --- |
| Asqueel | Grammatica e oggetti del modello, espressioni, compilatore, query plan, dialetti/driver, runtime, record, scritture, trigger Python e proiezione dello schema verso il migratore. |
| Asqueel Migration | Validazione/diff dello schema, generazione ed esecuzione DDL, adapter di migrazione. Chat **Pulisci asqueel migration**. |
| Asqueel DB Manager | App Kajenn, OpenAPI/MCP, operazioni amministrative, backup/restore e task. Chat **Esamina il repository**, nel checkout DB Manager. |

Il core può usare direttamente il migratore senza Kajenn o DB Manager.
Un trigger **Python** appartiene al ciclo applicativo di Asqueel; un trigger
**SQL nativo** è un oggetto del database. Per il secondo, il core dovrà
definire dichiarazione e proiezione, mentre il migratore dovrà gestirne il DDL:
questo contratto futuro richiede coordinamento fra i repository.

Dettagli della separazione: [contesto e confini](../contesto-core-e-confini.md).

## Baseline da cui ripartire

- Checkout: `/Users/gporcari/Sviluppo/asqueel/asqueel`.
- Branch verificato: `chore/dbmanager-migration-compatibility`.
- HEAD verificato: `92466b90bb854cd897db5b0ff0bb327f8df9782b`.
- Versione nel `pyproject.toml`: **0.5.1**; questo dato non certifica una release pubblicata.
- [PR core 10](https://github.com/asqueel-org/asqueel/pull/10): compatibilità
  con il migratore, vincolo `>=0.1.2,<0.3` e pin sviluppo/CI a
  `a74f71b99c2b082f081f78c1671fd466cadc2d23`.
- Ultima verifica completa registrata nella sessione: **868 passati, 1 skip**,
  PostgreSQL e SQLite, copertura 95%. Non rieseguita per questo handoff.
- All'ultima verifica precedente le PR core 10, migration 18 e DB Manager 1
  erano aperte, con CI verde. Alla ripresa controllare lo stato remoto prima
  di scegliere la base del nuovo branch; non considerarne implicito il merge.

Quoting del migratore già risolto e unito nella
[PR migration 17](https://github.com/asqueel-org/asqueel-migration/pull/17).
Snapshot dell'input e separazione Kajenn sono nella
[PR migration 18](https://github.com/asqueel-org/asqueel-migration/pull/18);
il servizio è nella [PR DB Manager 1](https://github.com/asqueel-org/asqueel-dbmanager/pull/1).
Non riprendere qui quei lavori.

Preservare i file locali estranei: `assets/asqueel/social/asqueel-formulario-zio-sam.png`,
`docs/review/configurazione-e-grammatiche-it.html`, `docs/review/esempi/`.
Anche `docs/contesto-core-e-confini.md` è una nota locale non ancora committata.
Questo handoff non crea branch, commit, PR o release.

## Fonti e precedenza

Per le decisioni del 6 ottobre recuperate e quelle del 12 ottobre, leggere
prima il [contratto 40](40-model-and-operation-recipes.md). La revisione
`docs/review/configurazione-e-grammatiche-it.html` §§7–10 ne è una fonte:
è un file locale da preservare, ma contiene decisioni e va considerato.

1. [Proposal 0001 — Declaring models and writing expressions](../proposals/0001-model-and-expressions.md):
   principale raccolta dei contratti futuri. Leggere le etichette di ogni
   regola: **Decided**, **Direction decided**, **Proposed**, **Open**.
   Il testo è scritto come documentazione finale, ma dichiara esplicitamente
   che il nuovo modello non è ancora implementato.
2. [Decisioni 05](05-decisions.md): vincoli del runtime e distinzione RECORD/RAW.
3. [Piano 33](33-structure-rectification-plan.md) e
   [piano 32](32-expression-resolver-plan.md): dettagli di struttura e resolver.
   In presenza di divergenze leggere le decisioni successive della proposta,
   senza trasformare una proposta in una decisione.
4. [Piano operativo 15](15-operational-plan.md): collocazione F2/F3/F4;
   [consegna query 30](30-query-completion-plan.md), sezione Esito, per quanto già realizzato.
5. Guide [models](../guide/models.md), [writes](../guide/writes.md),
   [hooks](../guide/hooks.md), [transactions](../guide/transactions.md),
   [SQLite](../guide/sqlite.md): descrivono l'API attuale, non quella futura.

Il precedente [handoff query](HANDOFF-query-completion.md) è storico:
HEAD `90984fb`, 683 test e query da implementare non sono la baseline corrente.
Anche le baseline 845 test dei piani 32/33 sono storiche.

Esempio di divergenza da non perdere: proposta 0001 §3.5 decide che il lookup
di un nome semplice assente restituisce `None`, mentre un percorso errato
solleva un'eccezione. Non ereditare dal vecchio piano 32 una regola indiscriminata
«nome mancante = errore». Oggi `SqlTable.column()` solleva `ValueError` anche
per il nome semplice: l'adeguamento resta da fare.

## Cosa esiste già

| Area | Stato verificato nel codice |
| --- | --- |
| Dichiarazione modello | Contenitori espliciti `table.columns()`, `virtual_columns()`, `indexes()`; colonne, alias e formule/sottoquery già presenti. |
| Query | `IN/NOT IN` scalare, `DISTINCT`, `GROUP BY/HAVING`, terminale `count()`, alias, formule correlate e policy già implementati. |
| Compilazione DML | `plan_insert`, `plan_update`, `plan_delete` e relative API compilate; assegnazioni e parametri separati dal testo SQL. |
| Runtime | Profilo sincrono; connessioni nominate e ambiente isolati per thread; transazioni e callback esplicite. |
| Scritture applicative | Hook di tabella before/after, hook DB, scritture RECORD e RAW, stack causale `currentTrigger`. |
| Chiavi | Identità dichiarata e selezione per chiave; nessun generatore applicativo generale di pkey già pronto. |

Non serve riscrivere il DML da zero. Il lavoro è allineare questi percorsi
al nuovo modello e al resolver comune, completando i comportamenti mancanti.

## Modello: decisioni acquisite da attuare

- **DB e package distinti dagli schemi fisici.** `db` contiene `connection`,
  `packages`, `extensions` e `options`. Gli schemi sono dedotti dai package,
  senza sezione schemas separata. Il package seleziona
  `sqlschema` e `sqlprefix`; le tabelle vengono dichiarate con `pkg.table(...)`.
- **Build e render separati.** `configure(self, pkg)` produce la ricetta;
  gli hook di costruzione operano prima del render. A runtime rimangono gli
  oggetti, senza accesso alla sorgente. `attributes` è una copia in sola
  lettura coerente con le proprietà dell'oggetto.
- **Colonne direttamente sulla tabella.** `tbl.column`, `formulaColumn`,
  `aliasColumn`, `subQueryColumn`, `pyColumn`, `compositeColumn`; contenitori
  colonne/virtuali/indici interni, non una seconda sintassi pubblica.
  Collisione fra nomi fisici e virtuali: errore.
- **`colgroup`.** Dichiarazione unica, ordine di dichiarazione, appartenenza
  tramite gruppo oppure `colgroup=`, default `col_*`, UI separata in `x_ui_*`.
- **Relazioni.** `relation` significa FK, `weak_relation` collegamento logico;
  target FK univoco, target weak assunto univoco. `on_update_sql` di default
  `cascade`; azioni SQL esplicite con suffisso `_sql`. `on_delete/on_update`
  sono azioni Python da introdurre con il ciclo dei record correlati:
  fino ad allora non accettarle come attributi senza effetto.
- **Indici.** Entrambe le relazioni indicizzano la sorgente; la weak anche
  il target, salvo copertura per prefisso iniziale di PK/UNIQUE/indice esistente.
- **Chiavi composite.** Un'unica `compositeColumn`, identità serializzata JSON,
  `static=True` di default; `unique=True` proietta un UNIQUE multicolonna;
  relazione fra composite abbina i membri in ordine. `pkey` nomina una sola
  colonna fisica o composita; `pkeys` espone i membri.
- **Opzioni esplicite.** `tbl.options()` contiene `sys_fields`, `auto_counter`,
  `hierarchical`; firme tipizzate e documentazione della grammatica generata.
  L'autore chiede la funzione, l'opzione aggiunge le colonne di sistema.
  `options` è una sezione anche per DB, connessione, schema e package, con
  vocabolario per livello; non implica ereditarietà automatica ai figli.
  `False/True/dict` per le colonne generate è deciso; firme e default specifici
  restano aperti. I contributi ordinati precedono l'unica render.
- **`constraint` esce dalla grammatica prevista.** UNIQUE composito passa
  da `compositeColumn`; CHECK torna con gli oggetti SQL nativi. Importazione
  di CHECK esistenti: segnalazione e preservazione nel DB, non cancellazione.

Esempio della forma obiettivo, **non eseguibile oggi senza le modifiche**:

```python
class InvoiceModel:
    def configure(self, pkg):
        tbl = pkg.table('invoice', pkey='id')
        tbl.column('customer_id', dtype='L').relation('sales.customer.id')
        tbl.column('total', dtype='N', size='12,2')
        tbl.formulaColumn('double_total', sql_formula='$total * 2', dtype='N')
        tbl.options().sys_fields()
        return tbl
```

Per `sys_fields` è deciso il default `id=True`, equivalente a
`id=dict(type='uuid')`: UUID testuale compatto di 22 caratteri con lo stesso
algoritmo e codifica di `getUuid()` legacy, precisati nel contratto 40.
Sono decisi anche `ins=True` e `upd=True`: `__ins_ts` e `__mod_ts` vengono
valorizzati entrambi all'inserimento; alle modifiche si aggiorna `__mod_ts`.
`user_ins=True` e `user_upd=True` sono i default: `__ins_user` all'inserimento,
`__mod_user` all'inserimento e alle modifiche, dall'ambiente autenticato del
server; `NULL` se non c'è utente.
`ldel=True` aggiunge `__del_ts` per cancellazione logica/ripristino espliciti;
`delete()` resta fisico. `draft=False` omette la bozza; `draft=True` aggiunge
`__is_draft` e abilita la policy, con valore iniziale ancora da definire.
Tipi fisici esatti, timezone, dettagli esecutivi e gli altri default restano
da chiudere.

## Espressioni e compilatore: contratto da completare

Un parser e un resolver condivisi devono servire query, formule, policy e
lettura delle colonne del modello. Mantenere la pipeline
`QueryPlan → dialetto → binding del driver → execute`; niente compilatori
indipendenti per SELECT e scritture, né mutazioni del modello condiviso.

Sintassi decisa: `$col`, `@customer_id.name`, `@rel.@rel2.col`, `:param`,
`:env_name`, `#THIS.<path>`, macro maiuscole `#NAME(...)`, sottoquery nominate
minuscole `#name`. Ogni segmento intermedio di relazione richiede `@`.
I nomi delle relazioni uscenti seguono la colonna; il dettaglio delle inverse
automatiche/private resta proposto nella proposta 0001.

Decisioni specifiche:

- `#THIS` valido in un contesto correlato, inclusi i percorsi di relazione.
- `#IN_RANGE`: estremi inclusivi, estremo NULL aperto, entrambi NULL vero.
- `#PERIOD`: parametro esplicito o letterale; decodifica Python con workdate e
  locale; intervallo SQL semiaperto fino al giorno dopo l'ultimo. La proposta
  indica `genro_toolbox.dates.parse_period` 0.15.0: verificare/aggiornare la
  dipendenza prima di usarla; non presumere che l'ambiente corrente la offra.
- `*`: fisiche in ordine, Bag `dtype='X'` secondo `bagFields`, poi virtuali
  statiche; nomi automatici dei percorsi compatibili con `colToAs`.
- Nessuna colonna `pkey` aggiunta automaticamente dal core ai risultati.
  `count()` rifiuta `limit/offset`; preservare i casi plain/distinct/grouped già testati.
- Una navigazione many non deve moltiplicare silenziosamente le righe né
  richiedere un raggruppamento Python implicito.

**Ancora proposti:** funzioni `@many.COUNT/SUM/...`, macro di riga `#SUM`,
`#JSON`, `#TEMPLATE`, registry per livello/contesto e contratto dettagliato
`virtualRelation`. Il loro disegno orienta il resolver, ma non autorizza a
implementare ogni forma come già approvata. Anche pass-through SQL e
classificazione di `#THIS` come radice sono etichettati Proposed nel testo.

Rilievo concreto ancora aperto: `member_name()` in `query_plan.py` riparte da
zero per ogni elemento di una collezione; con nomi consecutivi l'allocazione
è quadratica. Sistemare l'allocatore comune ai chiamanti compiler e SQL diretto,
preservando unicità con parametri utente, ambiente, sottoquery e IN ripetuti.
Verificare la crescita su liste grandi con una misura riproducibile, evitando
test di tempo fragili. Questa ottimizzazione può essere un incremento autonomo.

## INSERT, UPDATE, DELETE e trigger: invarianti da preservare

| Percorso | Contratto attuale da mantenere |
| --- | --- |
| `insert` | Un mapping copiato; hook prima del SQL; campi fisici restituiti sovrapposti al record prima dell'after-hook; default DB ammessi. |
| `update/delete` ordinari | PK richiesta; lettura e lock di esattamente una riga, anche senza override di hook. Zero o più righe: errore prima degli hook. PostgreSQL usa `FOR UPDATE OF` la tabella base. |
| `update` | Record fisico completo con modifiche applicate; copie indipendenti di `old_record`; SQL selezionato sulla vecchia chiave anche se l'hook modifica la nuova. |
| `delete` | Cambiare il record nell'hook non cambia il selettore dell'identità bloccata. |
| RAW | Salta gli hook Python di tabella; mantiene hook DB, policy, binding, vincoli/trigger SQL e transazione. Update/delete possono riguardare zero o molte righe. |
| `raw_insert` | Mapping o lista; ordine preservato; lista vuota senza scritture; nessuna promessa di COPY/executemany o successo parziale con savepoint impliciti. |
| Filtri | Partition rispettata; draft/soft-delete di lettura non nascondono la riga da scrivere; soft-delete/restore seguono il ciclo update. |
| Compilazione | Colonne virtuali o sconosciute non assegnabili; valori come binding; WHERE vuoto/comment-only rifiutato, `TRUE` esplicito per tutti i record RAW. |
| Errori | Errore hook o cardinalità inattesa rende rollback-only l'unità di lavoro; le scritture correlate partecipano alla stessa transazione. |

Ordine attuale ordinario, dopo l'eventuale lock:
`onWriting → trigger_onInserting/Updating/Deleting → onExecutingWrite → SQL
→ ritorni sul record dove previsti → _onDbChange → trigger_onInserted/Updated/Deleted
→ onWritten`. Negli update ogni hook riceve la propria copia del vecchio record.

`currentTrigger` è uno stack causale sincrono con evento, tabella, record,
old_record, parent e level; viene ripristinato anche su eccezione. Non è lo
stack dei trigger SQL. I callback differiti operano quando lo stack della
scrittura originaria è già uscito.

Nessun commit implicito. Gli hook non possono commit/rollback/close durante
la scrittura. Un after-hook è dopo lo statement, non dopo il commit.
DB/modello condivisibili; ambiente e connessioni isolati per thread.
Non reintrodurre Session o context manager transazionali. Gli errori dei
callback propagano e fermano la sequenza; un errore post-commit non annulla
il commit. Gli effetti esterni richiedono un contratto applicativo distinto.

Restano da definire/collegare: trigger di campo generati dalle opzioni,
generazione pkey, controlli/protezioni e timestamp di concorrenza, azioni
Python sui record correlati, contatori e gerarchie. Non nasconderli nel
dialetto o nel solo compilatore SQL: sono orchestrazione applicativa.

## Decisioni da chiudere prima degli incrementi dipendenti

| Tema | Domande e fonte |
| --- | --- |
| Opzioni e colonne di sistema | Firme/default di `sys_fields`, `auto_counter`, `hierarchical`; True/False/dict è **deciso**. Dettagli di merge e registrazione delle opzioni esterne ancora aperti. Contratto 40, proposta §2.6/8, analisi 34 e 38. |
| Primary key e nuovi record | `sys_fields(id=dict(type='uuid'))`, default `id=True` con algoritmo legacy `getUuid()` e UUID testuale di 22 caratteri; supera `pkey_type` sulla tabella per il campo di sistema `id`, e `custom` è ritirato. Restano altri generatori, chiavi senza `sys_fields`, collegamento/precedenza di `new_pkey_value(self, record)`, lifecycle, RAW/batch e composite. Contratto 40; analisi 39 resta evidenza legacy. |
| Costruzione e lettura del modello | Hook supportati e ordine; composizione package; nome pubblico `column` o `get_column`. Analisi 35 e proposta §0/3.5. |
| Relazioni derivate e funzioni | Approvare il contratto proposto, inversa filtrata, `ask`, limit/ordine, alias lunghi, chiavi JSON, semantica NULL/insieme vuoto. Proposta §3.3/3.6. |
| Gerarchie | NULL e `/` nei path, copyFromParent, campi parent fisici/calcolati. Sono già decisi parent_id + path materializzati, protezione cicli, filtri bypassati nelle letture strutturali, escaping LIKE e aggiornamento del sottoalbero via trigger Python. Analisi 36. |
| Subtable e Bag | Nome/eredità/scritture delle subtable; SQL e tipo risultato di bagItemColumn. Direzione acquisita, dettagli aperti. |
| Oggetti SQL nativi | Grammatica, proiezione e capacità del migratore per trigger/funzioni/view/CHECK. Non includere DDL nativo implicitamente nel primo incremento dei trigger Python. |

Chiudere solo le domande che bloccano il prossimo incremento. Grouped view
completa, audit, record cluster, adapter GenroPy applicativo e supporto async
non diventano requisiti del primo incremento per la sola presenza nei dossier.

## Sequenza di lavoro acquisita — 12 ottobre

1. **Definire il modello completo**, partendo da DB, schemi fisici, package e
   options. L'assenza di effetti SQL non esclude un elemento dall'analisi.
2. **Verificare le migrations**, producendo dagli oggetti il JSON normalizzato
   del migratore e verificando applicazione e confronto successivo.
3. **Definire lettura e scrittura** tramite ricette serializzabili JSON/XML,
   ricostruibili su un'altra macchina, compilabili ed eseguibili. L'ingresso
   remoto usa grammatica validata senza SQL arbitrario e valori parametrizzati;
   autorizzazioni, contesto autenticato, policy e RECORD/RAW restano al server.

Dettagli e questioni ancora aperte sono nel contratto 40. Il JSON fisico e il
formato delle operazioni sono contratti distinti. Nessun workflow è avviato.

### Scomposizione precedente — riferimento storico, da riallineare

1. **Contratto minimo del modello.** Riesaminare proposta 0001, chiudere i
   dettagli necessari su opzioni/pkey/build e registrare le decisioni. Produrre
   un esempio canonico con tabella, relazione, formula, gruppo e opzioni;
   rendere esplicite le differenze incompatibili con l'API corrente.
2. **Grammatica e oggetti.** Portare dichiarazioni e render al contratto
   deciso, incluse validazione, metadati, composite e proiezione schema.
   Aggiornare grammar reference ed esempi dello stesso incremento. Eventuali
   capacità mancanti del migratore vanno coordinate, non duplicate nel core.
3. **Parser/resolver e query.** Corpus di espressioni valide/non valide,
   risoluzione condivisa e binding senza collisioni; riusare il query plan.
   Preservare le query già funzionanti; introdurre macro/relazioni derivate
   solo nel perimetro approvato. Il fix IN può precedere questo passo.
4. **DML sul nuovo modello.** Identità semplice/composita, default/returning,
   selettori, policy e assegnazioni; verificare che compilatore e API record
   concordino. Preservare la distinzione RECORD/RAW.
5. **Trigger e opzioni comportamentali.** Definire l'ordine dei nuovi hook
   di campo rispetto agli hook esistenti; collegare le funzionalità approvate
   senza aggirare lock, rollback-only, stack e callback. Gerarchie e azioni
   correlate richiedono prove di ricorsione e concorrenza dedicate.
6. **Accettazione e consegna.** Esempio end-to-end PostgreSQL/SQLite nel
   rispettivo profilo; documentazione dell'API realizzata, incompatibilità e
   limiti. Non dichiarare chiuse F2/F3/F4 in base al solo conteggio dei test.

Ogni incremento deve avere un risultato utilizzabile e verificabile. Questa
sequenza è una proposta di esecuzione, non un workflow `.phased` già avviato.

## Mappa del codice e verifiche

| Area | File e test da cui partire |
| --- | --- |
| Modello | `src/asqueel/elements.py`, `builder.py`, `model.py`, `catalog.py`, `validators.py`, `configuration.py`; `tests/native_model/`, `tests/test_grammar.py`, test della grammatica pubblica. |
| Espressioni/plan | `src/asqueel/compiler.py`, `query_plan.py`, `drivers/sql.py`; `tests/native_compiler/`, `tests/adapter_compiler/`, `tests/adapter_dialect/`. |
| Query già consegnate | `tests/test_wf_phase1_query_collections.py`, `test_wf_phase2_query_grouping.py`, `test_wf_phase3_query_count.py`, `test_wf_phase4_query_acceptance.py`. |
| Scritture/trigger | `src/asqueel/application_table.py`, `writes.py`, `triggers.py`; `tests/application_integration/test_write_hooks.py`, `test_raw_writes.py`, `test_write_lifecycle.py`. |
| Transazioni | `tests/application_connections/`, incluse callback, errori Python/SQL e connessioni per thread/nome. |

Criteri di accettazione trasversali:

- Il modello canonico si costruisce, si valida, si legge dagli oggetti e
  produce lo schema previsto senza mantenere scorciatoie verso la sorgente.
- Stessa espressione, stessa colonna e stessi binding nei contesti ammessi;
  stringhe/commenti SQL non diventano riferimenti del linguaggio; correlazioni
  e collezioni non collidono con nomi esterni né alterano cardinalità.
- Insert con default, update con cambio chiave, delete, returning con alias,
  record mancanti/multipli, input non mutato, partizioni e RAW testati realmente.
- Ordine hook, old_record, scritture annidate, cleanup dello stack e rollback
  dimostrati anche nei percorsi di errore; nessun effetto di commit introdotto.
- PostgreSQL è il riferimento principale; SQLite deve eseguire ciò che
  dichiara supportato e rifiutare esplicitamente il resto. Non simulare la
  semantica di lock PostgreSQL su SQLite.
- Test consumer del migratore sulle modifiche di schema; grammatica generata
  allineata alle firme; guide/tutorial che eseguono davvero l'API consegnata.

Comando già usato nella sessione, dalla radice del repository core, se
l'ambiente temporaneo è ancora disponibile:

```sh
PYTHONPATH=src:../asqueel-migration/src PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 /tmp/asqueel-repo-audit-env/bin/python -m pytest -q -o addopts=''
```

È un test dei checkout locali, non della sola dipendenza rilasciata. Controllare
versioni e stato dei checkout prima di confrontare i risultati. PostgreSQL
richiede il supporto di ambiente previsto dai fixture. Eseguire prima i test
pertinenti all'incremento, poi suite completa e controlli richiesti dal repo;
non trasferire al nuovo codice il vecchio risultato 868/1.

## Prompt pronto per la ripresa

> Riprendi Asqueel core leggendo `docs/design/HANDOFF-asqueel-core.md` e
> `docs/proposals/0001-model-and-expressions.md`. Migration e DB Manager
> proseguono nelle rispettive chat. Verifica branch/PR e preserva i file
> locali. Leggi il contratto 40: parti dalla struttura DB, schemi fisici,
> package e options, poi dalle firme e dai default ancora aperti. Non
> ridiscutere le decisioni già acquisite. Proponi il primo incremento concreto, chiudi solo i contratti
> che lo bloccano e prosegui secondo l'autorizzazione dell'utente. Il percorso
> deve coprire modello, proiezione JSON verso il migratore, ricette trasferibili
> delle operazioni, compilazione ed esecuzione, inclusi INSERT/UPDATE/DELETE e
> trigger Python. Conserva RECORD/RAW e transazioni; le ricette dal browser
> escludono SQL arbitrario e il server applica autorizzazioni e policy. Distingui
> implementato, deciso e proposto; non ricreare funzionalità query già presenti.

Per l'esecuzione della prossima release, integrare il prompt precedente con:

> Segui `docs/design/44-core-release-plan.md`, partendo dalla prima fase non
> completata. Usa 42 come grammatica obiettivo e 43 come copertura obbligatoria
> di sys/adm/invc. Registra prove ed esiti per fase; il censimento statico non
> prova build o migrations. Preserva le modifiche locali, riusa runtime e test
> esistenti e non dichiarare pronta la release prima dei gate P6, P9 e P11.
