# 95 — Riferimento develop e censimento dei fix legacy

15 ottobre 2026. **Audit iniziale: analisi e documentazione, senza modifiche
all'implementazione o ai test del prodotto.** Gli esiti sotto fotografano
quell'audit; gli interventi successivi sono annotati in fondo. Segue la replica alla review e aggiorna il
[piano 86](86-legacy-compiler-logical-phases.md).

## Riferimento fissato

Per i prossimi raccordi il riferimento è GenroPy **`95da66ee64b0c789dbb6b35254011d83ce1911c5`**,
commit del 15 ottobre 2026, corrispondente a `origin/develop` nel repository
locale esaminato. È un riferimento immutabile: non significa seguire
automaticamente ogni aggiornamento futuro del branch. Nessun fetch effettuato.
Le decisioni dell'utente sul perimetro e sulle divergenze restano prevalenti.

Il precedente `fa35e5adfa6ad1b269f3a22a9b12c4c1ee6513ea` è il merge di develop
in genro_integration del 14 settembre; non è antenato del nuovo riferimento.
L'antenato comune è `ee1b8a43db03cc4cec2bd30a2f375c1ec554937d`.
Ho verificato che `gnrpy/gnr/sql` in quell'antenato e nel vecchio riferimento
ha contenuto identico. L'intervallo antenato comune → nuovo riferimento contiene
**24 commit che toccano quel percorso: 19 non-merge e 5 merge**.

I cinque merge non mostrano risoluzioni aggiuntive nel diff combinato di
`gnr/sql`: non sono cinque fix ulteriori da implementare.
Nel nuovo riferimento `compiler.py` e `compiler_next.py` risultano uguali
dopo la normalizzazione usata dal test legacy di sincronizzazione (docstring
del modulo, nome della classe, righe vuote). Non emerge un diverso algoritmo
da scegliere fra questi due file. Gli altri branch sperimentali già censiti
rimangono materiale di confronto, non nuove specifiche.

I vecchi oracoli e i rapporti di esecuzione **restano associati al vecchio SHA**.
Non vengono rigenerati né rinominati come prove di develop. La precedente
baseline verde non certifica i fix successivi.

## Censimento dei 19 commit non-merge

🟢 = comportamento pertinente già presente; 🟡 = differenza da raccordare o
decidere; ⚪ = fuori dal percorso SELECT attuale, senza riaprirne il perimetro.
Gli stati misti separano parti diverse dello stesso commit. Non indicano che
l'intero commit sia stato portato.

I percorsi dei test legacy sotto sono relativi a `gnrpy/tests/sql/` al nuovo
riferimento; il [registro completo](evidence/develop-reference-audit/commits.json)
conserva SHA interi, genitori, file modificati e nomi dei test aggiunti.

| Commit | Effetto e test legacy | Riscontro Asqueel e disposizione |
| --- | --- | --- |
| `cdc70698ff` | Distingue selezione assente e vuota in batchUpdate/touchRecords; `test_batch_update_guard.py` | ⚪ Queste API non sono implementate. Conservare i contratti per il futuro fronte scritture, inclusi pkey `0`, stringhe vuote e liste con spazi. Nessun cambio ai filtri SELECT. |
| `5ddb6813dc` | Binding mancanti → NULL nel percorso execute e correzione della condizione nel cursore SQLite; `test_missing_sql_parameters.py` | 🟡 Non recepito per i parametri ordinari. `drivers/sql.py:prepare_arguments` costruisce un dict senza default. Raccordo prioritario nella preparazione comune e nel passaggio al driver, mantenendo separati SQL e kwargs. |
| `51e4b7af3f` | Separa output_mode dalla cardinalità mode nei resolver record/selection; `test_resolver_output_mode.py` | ⚪ Asqueel non ha quei resolver di record/selection. I resolver di configurazione esistenti non sono il componente interessato. |
| `3be912d2e6` | Completa relationDict in compiledRecordQuery per JOIN da colonne virtuali; `test_compiler_coverage.py::TestVirtualRelationColumn` | ⚪ Il record gerarchico è esplicitamente non raccordato in `SqlTable.record`; non esiste un suo compiledRecordQuery da correggere ora. La SELECT usa già risoluzione ricorsiva dei riferimenti e il contratto `formula_relation`. Portare i due test record quando si apre quel percorso; non dichiararli già superati. |
| `6fbd80e9f2` | VACUUM FULL su connessione autocommit; `test_vacuum.py` | ⚪ Nessuna API vacuum da raccordare nel core attuale. È manutenzione/esecuzione, non compilazione SELECT. |
| `48dd2f8174` | Rifiuta moduli model che non dichiarano la tabella corrispondente al filename; `test_model_table_naming.py` | ⚪ Asqueel non importa automaticamente moduli config_db indicizzati per filename come il loader legacy. La source dichiara esplicitamente le tabelle. Conservare il test se si introdurrà quel loader, senza aggiungerlo ora. |
| `ebe3dedbed` | Copia del compiler e factory selezionabile, più proxy applicativo; `test_compiler_factory.py`, `test_compiler_next_sync.py` | ⚪ Non importare switch XML o proxy web. La convivenza dei percorsi Asqueel ha già un contratto distinto. Usare la copia come confronto algoritmico verificato. |
| `233e06b236` | Where translator: valore None di op_in trasformato in lista vuota; `test_empty_in_filter.py` | ⚪ Wherebag non portata. Non trasformare automaticamente ogni parametro None di un SQL `IN` in una lista: il fix legacy appartiene a `GnrWhereTranslator.op_in`. |
| `d3243913e7` | Condizione globale di setJoinCondition attraversa raccolta e sostituzione dei campi; `test_compiler_coverage.py::TestJoinConditions` | ⚪ `joinConditions` è rifiutato dall'API attuale. Non confondere questo wildcard della condizione con `*` delle colonne. I test restano disponibili per il futuro raccordo. |
| `f60cfb983e` | Stesso fix della riga precedente nel compiler_next; test di sincronizzazione | ⚪ Stesso perimetro; non è un secondo comportamento da aggiungere. |
| `ead219ffae` | Sposta la selezione del compiler nel flag experimental; `test_compiler_factory.py` | ⚪ Configurazione dell'applicazione GenroPy, non nuova opzione Asqueel. |
| `ee2a507247` | Errori di conversione dei valori wherebag diventano eccezioni tipizzate; `test_invalid_filter_value.py` | ⚪ La conversione è in storeArgs/innerFromBag, assenti qui. Nessuna nuova coercizione dei kwargs o gerarchia di eccezioni da introdurre nel compilatore. |
| `2213cfd7c3` | Motivi di protezione/invalidità costruiti tramite string_join dell'adapter; `test_string_join.py`, `test_gnrbaseadapter.py` | 🟢 Equivalente già presente: `SqlTable._sql_reasons` delega a `dialect.concat_non_null`; PostgreSQL usa array_to_string e SQLite concatenazione che salta NULL. Verificata anche una SELECT sul nuovo albero in SQLite. Non significa che siano portati system_records o le scritture del test legacy. |
| `3c581d9d26` | Trigger gerarchici: cicli, cancellati, old_record, radici; anche correzioni strutturali in gnrdbo; `test_hierarchical_trigger.py` | ⚪ Trigger, manutenzione e varianti runtime rinviati. 🟢 La parte strutturale pertinente è già rappresentata: `model_expansion.hierarchy` usa nomi puliti per `_h_sortcol`, verifica id e rifiuta counter con scope relativo. La regola `:unique` legacy è rappresentata dalla grammatica nativa già adottata, non reintrodotta come sintassi. |
| `ba377674f7` | Espande #THIS prima di updateFieldDict nella formula SQL; `test_compiler_coverage.py::TestFormulaSqlThisRelation` | 🟡 Non recepito: `TreeQueryCompiler` scopre ancora i riferimenti prima di espandere #THIS. Riprodotto su entrambi i dialetti senza esecuzione. Primo fix da portare. Il WHERE delle sottoquery ha già un test distinto che passa. |
| `a659df9d36` | Ridefinire il tipo di virtuale elimina gli attributi del tipo precedente; `test_virtual_column_redefinition.py` | 🟡 Differenza di contratto: il builder Asqueel rifiuta alias→formula e formula→alias con ValueError. Occorre decidere l'override fra tipi virtuali prima di cambiare builder/composizione. Non estendere implicitamente il cambio a fisica↔virtuale, che ha un contratto di rifiuto esistente. |
| `600f347ef3` | UNIQUE: nomi reali, schema degli indici, indici semplici/partial/espressioni e convergenza indexed(unique=True); `test_gnrsqlmigration.py`, casi 13a–13g | 🟡 Lavoro separato in asqueel-migration. Il suo command_builder ricostruisce ancora il nome nel ramo di rimozione unique. Portare l'intero gruppo di contratti: correggere solo il nome DROP non copre il commit. Nessun DDL applicato in questo audit. |
| `4699eafd21` | SqlTable.exception nomina la chiave sconosciuta anziché sollevare None; `d_table_test.py` | ⚪ Asqueel non ha il registry EXCEPTIONS né quella factory. Non introdurli per portare il fix; gli errori correnti non passano da quel lookup. |
| `170495f80a` | Cerca la virtuale nella tabella destinataria quando si dichiara tramite colgroup; `test_virtual_column_redefinition.py` | 🟢 Nuove aliasColumn e formulaColumn tramite colgroup funzionano e compilano. 🟡 Il cambio di tipo nello stesso gruppo resta rifiutato come nella riga a659df9d36. Non è un ulteriore bug autonomo del renderer. |

## I cinque merge

| Merge | Fix incorporato | Disposizione |
| --- | --- | --- |
| `aabc11c37a` | `51e4b7af3f`, resolver output_mode | Stesso rinvio del fix; nessuna azione aggiuntiva. |
| `d6c7e81bb8` | `233e06b236`, wherebag IN vuoto | Stesso rinvio del fix; nessuna azione aggiuntiva. |
| `15cb7215f2` | `2213cfd7c3`, motivi tramite adapter | Stesso riscontro positivo; nessuna azione aggiuntiva. |
| `a89bf5c272` | `a659df9d36`, cambio tipo virtuale | Stessa differenza di contratto; nessuna decisione aggiuntiva. |
| `8e4cd1cc17` | `3c581d9d26`, gerarchiche | Stessa distinzione fra struttura e runtime. |

## Controllo oltre il filtro gnr/sql

Il filtro sui soli file SQL non basta. Ho letto anche le parti dei commit
pertinenti in `gnr/app/gnrdbo.py`: qui si trovano sia i chiamanti di string_join
sia la correzione strutturale di `_h_sortcol`.
La ricerca nello stesso intervallo su `gnrpy/tests/sql` restituisce altri
sette commit, già inclusi nel registro:

- `a19c015024`: parametrizza i test delle joinConditions su entrambi i compiler;
  usare questa versione dei test quando si riprende quella funzionalità.
- `8b5a976997` e merge `a62786df58`: traduzione degli errori dei contatori
  applicativi; runtime contatori rinviato.
- `b24d2eaa5e` e `ccb4c81115`: rollback della connessione di sistema dopo
  letture applicative senza scritture; non esiste il corrispondente runtime
  adm/sys in Asqueel. Non cambiare incidentalmente le transazioni di fetch.
- `904fb7b112`: sincronizzazione utenti esterni adm; fuori perimetro.
- **`95da66ee64`**: Bag.getLeaves esclude anche le cartelle annidate;
  `TestExpandBag.test_bagcols_nested_leaves_only_pg/sqlite` verifica #BAGCOLS.
  Il nuovo percorso rifiuta esplicitamente #BAGCOLS e ha test per quel rifiuto:
  il fix va conservato per quell'eventuale porting, senza attivare la macro ora.

Questo è un audit delimitato a SQL, relativi test e dipendenze toccate dai fix,
non un censimento di ogni modifica GenroPy o Toolbox nel mese.

## Verifiche e limiti

- [Controlli del riferimento](evidence/develop-reference-audit/reference-checks.json):
  contenuto SQL vecchio riferimento/antenato comune identico; sincronizzazione
  dei due compiler di develop verificata sui sorgenti fissati.
- [Sonde ripetibili](evidence/develop-reference-audit/probe.py) e
  [risultati](evidence/develop-reference-audit/probes.json): #THIS con relazione
  fallisce in compilazione su SQLite e PostgreSQL; alias↔formula fallisce sia
  sulla tabella sia attraverso colgroup; nuove virtuali nel gruppo funzionano.
  La preparazione mantiene assente root_fkey con None/{}; su SQLite la SELECT
  fallisce, mentre il parametro esplicito None restituisce vero. Su PostgreSQL
  è verificata la preparazione, non l'esecuzione. La SELECT delle reasons sul
  nuovo albero SQLite restituisce stringa vuota per regola falsa, nome della
  regola se vera e NULL in assenza di regole, come previsto.
- **111 test Asqueel esistenti passati**, senza skip, in
  `test_phase3_formulas.py`, `test_phase4_macros.py`,
  `test_release_model_source.py`, `test_release_composition.py`.
  [Log](evidence/develop-reference-audit/tests.log).
- I test dei 19 fix legacy sono stati censiti e confrontati con i componenti
  interessati; **non è stata eseguita qui la suite GenroPy di develop**.
  Nessuna pretesa di nuova baseline integrale o di equivalenza completa.
  Nessuna connessione PostgreSQL o migrazione in questo audit.

## Piano dei prossimi interventi, da eseguire uno alla volta

1. **#THIS nelle formule SQL.** Portare il contratto del test legacy sul nuovo
   albero, senza aggiungere l'override dinamico di colonne usato dal suo fixture.
   Mostrare il fallimento; riprendere l'ordine del fix `ba377674f7`; verificare
   risultato, JOIN riusate, dipendenze e sottoquery su entrambi i dialetti.
   Alias e mangler restano distinti; nessun handler many.
2. **Binding mancanti.** Portare la matrice `None`, `{}`, valore esplicito None,
   valori falsy e precedenza ambiente del test `5ddb6813dc`. Confrontare l'intera
   catena preparazione→driver: copiare semplicemente defaultdict non basta se
   viene poi convertito in dict. Conservare input immutati e compilazione senza
   connessione; verificare fetch/count ed esecuzione diretta sui due dialetti.
3. **Cambio di tipo delle colonne virtuali.** Prima dell'implementazione,
   presentare il conflitto concreto con il rifiuto attuale. Se approvato,
   portare pulizia degli attributi, conservazione dei metadati e instradamento
   colgroup; non cambiare le regole fisica↔virtuale per analogia.
4. **Migration in lavoro separato.** Riprodurre e portare i casi 13a–13g del
   commit `600f347ef3`, con nomi reali, schemi e convergenza; verificare anche
   il confine del JSON prodotto dal core, senza spostare DDL nel compilatore.
5. **Riprendere i rimanenti punti della review** e poi la verifica di release:
   limiti ILIKE dei due percorsi, documentazione dei parametri simbolici,
   distribuzione/dipendenze e mypy. Nessuna modifica automatica delle convenzioni
   `%%` e `\:` né delle inverse del vecchio profilo.

La correzione `:ids`/`:ids2` con `\b` è già stata autorizzata e verificata nel
passo precedente (132 test): non appartiene ai 24 commit e non è un nuovo fix
eseguito da questo audit. Le collisioni dei nomi generati sono un altro problema.
Questo piano non autorizza in blocco gli interventi: il presente passo si chiude
con analisi e documentazione, mantenendo i limiti concordati.

## Raccordo successivo approvato: cambio di tipo delle virtuali

Adottati i contratti di `a659df9d36` e `170495f80a`: alias↔formula sulla
tabella, tramite `colgroup` e fra contributi ordinati. Il nodo cambia tipo
senza duplicazioni; gli attributi che definiscono il tipo precedente vengono
rimossi, quelli accessori non ridefiniti restano. Gruppo e posizione restano
stabili, anche quando il contributo indipendente numera diversamente il gruppo.
La composizione lavora su copie delle ricette.

La stessa pulizia è raccordata alle dichiarazioni native già esistenti
`subQueryColumn`, `pyColumn` e `bagItemColumn`. I loro selettori nativi
(`query`, `py_method`/`method`, `bagcolumn`/`itempath`) sono distinti dagli
attributi accessori. Come nel legacy, non si cancellano indiscriminatamente
`required_columns`, `mode`, `parameters`, `select_*` o `var_*`.
Gli attributi conservati e già ammessi dalla firma precedente restano validi
anche quando la firma nuova non li dichiara; questo non introduce nuovi
argomenti nelle firme pubbliche.

Regole invariate: conflitti fra dichiarazioni dello stesso tipo e rifiuto
fisica↔virtuale. Nessuna modifica al compilatore o al renderer.

Contratti portati in `tests/test_virtual_column_redefinition.py`; risultati
SQL verificati su SQLite e PostgreSQL in
`tests/native_formulas/test_tree_virtual_redefinition.py`.
La verifica del JSON per migration resta quella sui 74 modelli nativi in
`tests/object_tree/test_migration.py`, con confronto agli oracoli esistenti.

Verifica del raccordo: **2.691 test passati** (2.613 nella regressione source,
albero, modello e risultati SQL; 78 nella validazione e nelle grammatiche).
I nuovi contratti sono 47 sulla source/composizione e 8 di esecuzione sui due
dialetti. Ruff e controllo whitespace superati. Nessun compilatore modificato.
