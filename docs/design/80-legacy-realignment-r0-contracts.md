# 80 — R0: contratti legacy, test fissati e decisioni aperte

**Nota successiva:** questo rapporto conserva la fotografia di R0. L’istruzione
vincolante è ora applicare il legacy e togliere le aggiunte non concordate, senza
riproporle come decisioni. R1 è completata nel [rapporto 81](81-legacy-realignment-r1.md).
Le matrici e le impronte R0 non vengono riscritte dopo le modifiche autorizzate.

14 ottobre 2026. **R0 completata; nessuna modifica al compilatore.**
Il [piano 79](79-legacy-compiler-realignment-plan.md) ha ora una
[matrice completa](evidence/legacy-realignment-r0/matrix.md) dei 71 casi / 132
osservazioni del rapporto 78, riferimenti verificati ai test e agli algoritmi,
e un elenco esplicito dei conflitti con i test attuali. Nessun miglioramento
è approvato da questo censimento. R1 e il raccordo relations non sono iniziati.

**Decisione successiva al censimento:** mantenere la delega legacy agli adapter,
separando preparazione ed esecuzione, come registrato nel piano 79. M1 rimane
aperta nel gruppo adapter. Successivamente M2/M3 sono state chiuse mantenendo
il comportamento legacy per commenti e stringhe, con template ed escape legacy,
senza protezioni aggiuntive. Codice e test restano da riallineare.
Le evidenze JSON di R0 restano la fotografia del censimento, senza riscrivere
risultati o attribuire approvazioni retroattive ai miglioramenti.

## Contratto di riferimento

La base resta GenroPy `fa35e5adfa6ad1b269f3a22a9b12c4c1ee6513ea`. Per ogni
algoritmo sono registrati percorso, definizione, righe e hash sorgente/AST negli
otto snapshot: [algorithm-anchors.json](evidence/legacy-realignment-r0/algorithm-anchors.json).
I branch non diventano fonti normative alternative e non sono stati rieseguiti
integralmente in R0.

Il contratto Asqueel già richiesto resta **SQL e kwargs senza esecuzione**,
con accesso al nuovo albero effettivo, senza conversione in ResolvedModel.
Portare la preparazione necessaria degli argomenti dal confine legacy di
esecuzione non autorizza a portare connessioni, fetch o lifecycle.

Sono fissati come riferimento da mantenere/recuperare:

| Contratto | Regola legacy | Verifica fissata |
| --- | --- | --- |
| Risoluzione | `updateFieldDict` raccoglie riferimenti distinti; `getFieldAlias` li risolve; `templateReplace` sostituisce, anche dopo riferimenti aggiunti dall'espansione | Corpus fisico e profilo di chiamate del rapporto 78; prove specifiche del ciclo ancora da portare in R1/R5 |
| Proiezioni | Split e normalizzazione di `compiledQuery`; alias implicito con `colToAs`; ultima proiezione in caso di AS duplicato | `expression_no_alias`, `duplicate_alias`, alias quotati e CAST |
| Parametri simbolici | `embedFieldPars` sul WHERE prima di `updateFieldDict`; `$campo` / `@relazione` riconosciuti diventano riferimenti | Quattro test originali `TestEmbedFieldPars` e tre sonde adattate |
| Parametri ordinari | Valori tipizzati, nomi completi anche Unicode; escape iniziale `\$` / `\@` evita l'interpretazione simbolica ed è rimosso in preparazione | `unicode_param`, `bound_escaped_field`, valori ripetuti/Decimal/NULL e sonda legacy con date |
| Dialetti | PostgreSQL `REGEXP → ~*`; SQLite `ILIKE → LIKE` | `regexp_operator`, `sqlite_ilike_operator`; letterali contenenti queste parole restano una decisione distinta |
| Stato | Distinguere riferimenti, alias SQL e parametri; nessun doppio mangling o stato SQL sul modello condiviso | Test attuali di riuso/assenza di conversione e provenienza legacy; verifiche annidate nella fase sottoquery |

Esempio di compatibilità da recuperare, **non di miglioramento da approvare**:

```python
where = '$quantity > :threshold'
sqlparams = {'threshold': '$unit_price'}
```

Nel legacy il confronto è fra due colonne. Asqueel oggi passa una stringa come
valore. La sonda `bound_literal_field` non autorizza a mantenere questa differenza:
la sua aspettativa era intenzionalmente quella del valore letterale, mentre il
contratto legacy è quello simbolico. Su PostgreSQL il confronto testo/numerico
di quella sonda può quindi fallire correttamente rispetto alla convenzione;
non va cambiato l'oracolo per chiamare quel caso una regressione legacy.

Gli escape `$$`, `\:` e `%%` restano documentati come convenzioni legacy.
Il loro recupero va coordinato con M3: non si possono contemporaneamente promettere
la sostituzione legacy e l'immutabilità di tutti i letterali. Nessuna scelta nuova
è stata presa. `:codicè` è una compatibilità da recuperare; `$città` fallisce
in entrambi i percorsi e rimane un limite comune, non una regressione dimostrata.

## Test e osservazioni congelati

[contracts.json](evidence/legacy-realignment-r0/contracts.json) contiene per ogni
caso richiesta, origine, contratto, fase, decisioni, riferimenti ai test originali
quando presenti e osservazioni separate per dialetto. SQL integrale e dati del
rapporto 78 rimangono immutati; gli indici e gli hash collegano ogni osservazione
al suo record originale. Valori, tipi, kwargs, mutazioni degli input ed errori
sono conservati, senza ridurli a un generico «passa».

| Classificazione primaria | Casi | Significato |
| --- | ---: | --- |
| Compatibilità confermata nel contratto osservato | 24 | Risultati/alias uguali, oppure rifiuto del campo inesistente; non equivalenza completa dell'API |
| Compatibilità legacy da recuperare | 9 | Alias, parametri simbolici locali, escape iniziale, Unicode dei parametri e operatori |
| Decisione aperta | 33 | Nessuna approvazione implicita del comportamento corrente |
| Dipendenza da fasi successive | 4 | Relazioni, parametro simbolico `@` e macro IN_RANGE sul nuovo albero |
| Limite comune | 1 | `$città`: nessuno dei due percorsi lo completa correttamente |

Sono conteggi di casi selezionati, non percentuali di compatibilità. La decisione
D3 sui kwargs/input è trasversale anche ai casi con righe uguali. I risultati del
corpus esteso riguardano il modello precedente; non certificano relazioni o macro
sul nuovo albero. `literal_relation`, se si conserva la sostituzione legacy nei
letterali, dipende a sua volta dal raccordo relations.

Sono fissate [19 definizioni originali](evidence/legacy-realignment-r0/legacy-tests.json):

- 4 `TestPhysicalColumns`: colonna singola/multiple, PostgreSQL e SQLite.
- 4 `TestEmbedFieldPars`: campo locale/relazione, PostgreSQL e SQLite.
- 2 `TestExpandInRange`: dipendenza della futura fase macro.
- 9 metodi `BaseQuerySurface`: SQL/parametri, compilato, ordine, predicati,
  limit/offset, AS e relazione. La base è ereditata dalle classi dei due dialetti.

Sono **definizioni**, non 19 nuovi test eseguiti. Presenza verificata negli otto
snapshot: legacy 19, compound/v2/v3 9 ciascuno, v3_merged/v4/simplify 13 ciascuno,
next 19. L'assenza è registrata, non trattata come successo o skip runtime.

Le sonde del corpus non sono copie integrali dei test originali: per esempio
`embed_column_gt/le` conservano i predicati ma proiettano id su quattro righe
sintetiche, mentre l'originale confronta conteggi sul progetto test_invoice.
Per alias impliciti, escape e casi limite senza un test originale collegato,
la fonte è l'algoritmo più la sonda dichiarata, non un test legacy inventato.

## Differenze da decidere, una alla volta

La tabella seguente fotografa le decisioni **aperte alla chiusura di R0**,
anche quando il beneficio è misurato. Per lo stato successivo prevalgono
l'aggiornamento in apertura e il piano 79: M2/M3 chiuse sul comportamento legacy.
Il mantenimento nel percorso attuale durante il confronto non equivale alla
sua approvazione per il raccordo. M1–M5 mantengono gli identificativi del piano.

| ID | Caso concreto | Legacy / attuale | Decisione richiesta |
| --- | --- | --- | --- |
| M1 | `id IN :ids AND id <> :ids0`, con `[1,2]` e `3` | Su SQLite il legacy sovrascrive `ids0`: torna solo 2; attuale torna 1 e 2 | Conservare la prevenzione delle collisioni nel binding? Non riguarda lo scanner |
| M2 | Commento `/* $missing :unused */` | Il legacy cerca nomi nel commento; l'attuale li protegge. Senza newline dopo `--` cambia anche l'assemblaggio | Escludere i commenti in tutti gli stadi interessati, compreso il formatter? |
| M3 | Literal `'$id'`, `':id'`, `$$`, `\:` e percentuali | Il legacy applica convenzioni di template/binding/escape; l'attuale tende a conservare il contenuto SQL | Quale contratto dei letterali mantenere? Presentare gli escape correlati prima di scegliere |
| M4 | `$id As code` | Nel caso legacy produce un secondo AS invalido; l'attuale riconosce `As` | Accettare questa tolleranza, distinta dagli alias impliciti? |
| M5 | `where='$id=:missing'` senza valore | Legacy fallisce nel driver; attuale durante la compilazione | Mantenere la diagnosi anticipata? |
| D1 | `$"odd name"` | Non funziona nella sonda legacy; funziona nell'attuale | Mantenere questa estensione dei riferimenti logici? Non confonderla con `AS "display name"`, già compatibile |
| D2 | Dollar quote/tagged dollar quote/E-string PostgreSQL | I casi del corpus funzionano nell'attuale, non nel legacy | Decidere le forme singolarmente e le interazioni con M3; nessuna approvazione generale di sintassi aggiuntive |
| D3 | `sqlparams={'id':1, 'unused':99}` | Legacy conserva l'inutilizzato, aggiunge `jc_kwargs` e modifica il mapping non vuoto; attuale restituisce i soli parametri usati e conserva l'input | Separare le decisioni su kwargs restituiti, input del chiamante e stato runtime; non copiare incidentalmente execute |
| D4 | Stringa/commento non chiusi | Entrambi falliscono, ma stadio e diagnostica differiscono | Quali controlli anticipati mantenere? Non richiedere accidentalmente gli stessi messaggi interni GenroPy |
| D5 | `where='$id=1; SELECT 2'` | Legacy compila; attuale rifiuta il separatore. Sonda mai eseguita | Mantenere questo controllo nel compilatore? Separarlo dal check SQL opzionale discusso in precedenza |

M3 comprende interazioni da mostrare insieme per comprenderle, non un via libera
a ogni protezione lessicale. D3 richiede a sua volta risposte distinte: eliminare
kwargs inutilizzati non implica una decisione sulla mutazione dell'input.
R0 non introduce nuovi flag, nuove firme o un controllo SQLGlot nel core.

## Conflitti con i test Asqueel attuali

Sono registrate 15 definizioni, con righe e hash, in `conflicting_current_tests`
di contracts.json. Le asserzioni non sono state modificate. Esempi:

- `test_missing_parameters_and_duplicate_aliases` mescola tre contratti:
  errore anticipato (M5), alias duplicati e obbligo di AS. Gli ultimi due
  contrastano con il ripristino legacy già previsto in R2.
- `test_scanner_preserves_literals_comments_and_cast` mescola commenti (M2),
  letterali (M3), cast compatibile e kwargs (D3). Un solo test verde non approva
  tutto il blocco; quando si interverrà andranno distinti gli aspetti.
- I test di nomi logici quotati coinvolgono anche INSERT/UPDATE/DELETE:
  cambiare helper condivisi può incidere sulle scritture, pur lavorando sulla SELECT.
- `test_unavailable_features_fail_explicitly` contiene sia limiti intenzionali
  del nuovo albero sia rifiuti da riallineare/decidere. Non rimuovere il test in blocco.

Non risultano nuove divergenze approvate in questo passo. Le decisioni di ambito
già prese (nessuna esecuzione, feature rinviate, mixin/RuntimeModel separati)
non autorizzano automaticamente differenze nella grammatica delle espressioni.

## Copertura ancora da completare nelle fasi implementative

Il corpus non dimostra ogni ramo dell'algoritmo. Restano espliciti i test da
portare/integrare con il rispettivo incremento, senza ampliare la sintassi:

| Fase | Verifica richiesta oltre alle osservazioni già fissate |
| --- | --- |
| R1 | Mappe per riferimenti distinti; stessa colonna in più clausole; sostituzione safe/strict; isolamento di compilazioni successive |
| R2 | embedFieldPars limitato al WHERE; valore `$inesistente` non riconosciuto resta valore; bytes e `\@` secondo gli algoritmi originali; combinazioni di escape decise in M3 |
| R3 | Tipi/date/Decimal senza doppia preparazione; coppie operatore/letterale; DBAPI psycopg2/3; booleani SQLite, tuple/set oltre alle liste del corpus |
| R5 | Nuovi riferimenti prodotti dalle formule; embed di `@` attraverso il ramo relations; parametri omonimi in formule/sottoquery e macro |

Non sono test già superati né nuovi comportamenti approvati: sono lacune della
prova da chiudere rispetto agli algoritmi citati. Pkey implicita, ordine di tabella,
DISTINCT/exploding e le altre questioni del piano 76 restano aperte; il corpus
disabilita la pkey implicita nel legacy per confrontare proiezioni esplicite.

## Verifiche eseguite in R0

- **294 test Asqueel superati**, selezione invariata dei tre moduli compiler,
  compile_only e object_tree/minimal_select, in 4,11 s.
- **6 prove legacy di sola compilazione superate**, sonda già esistente
  `test_legacy_minimal_select.py`, in 0,50 s. Sono adattamenti, non la riesecuzione
  delle 19 definizioni runtime originali. Connessioni/esecuzione vietate dalla fixture.
- Catalogo verificato: 71 casi univoci, tutti i 132 record/dialetti coperti,
  riferimenti alle definizioni esistenti, hash verificati, nessun miglioramento approvato.
- **232 file Python di produzione/test/esempi invariati** rispetto alla baseline
  del rapporto 78; congelati anche risultati e sonde del confronto. Ruff superato
  per la nuova utilità di catalogazione. Nessun nuovo benchmark o confronto SQL
  con esecuzione in questa fase.

Log e verifiche sono nella [cartella R0](evidence/legacy-realignment-r0/verification.json).
Il controllo riproducibile del catalogo, dalla root del repository, è:

```sh
venv/bin/python docs/design/probes/freeze_legacy_contracts.py --check
```

Il controllo richiede gli otto snapshot in `/tmp/asqueel-formula-baseline`;
commit, percorsi e hash restano salvati per ricostruirli. Non apre database.
La proposta iniziale di discutere M1 è stata separata dal lavoro sul nucleo:
le collisioni nell'espansione delle collection riguardano gli adapter e restano
da decidere. M2/M3 sono state poi chiuse mantenendo il comportamento legacy
per commenti e stringhe SQL, senza protezioni aggiuntive.
R1 non parte automaticamente dalla chiusura documentale di R0.
