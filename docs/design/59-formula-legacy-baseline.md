# 59 — Censimento formule e baseline legacy

14 ottobre 2026. Eseguiti censimento, baseline legacy e verifica del supporto
Asqueel, senza modificare il compilatore o introdurre sintassi.

**Conclusione:** il riferimento legacy corrente e `compiler_next_step_1`
superano le suite selezionate. I refactor di febbraio non sono tutti verdi.
Asqueel supera 197 test del proprio profilo, ma **nessuna delle 462 formulaColumn
dei package nativi attraversa ancora il raccordo alla compilazione**.
Non significa che il motore non sappia compilare una formula: il percorso
di basso livello e quello delle dichiarazioni native sono distinti.

## Perimetro e inventario

Snapshot ottenuti con `git archive`, senza checkout o modifiche al repository
GenroPy. Le modifiche locali ai tre modelli invc non sono state incluse.
I riferimenti completi sono nell'[inventario](evidence/formula-baseline/inventory.json).

| Riferimento | Commit | Moduli selezionati | Definizioni di test |
| --- | --- | ---: | ---: |
| Legacy di riferimento | `fa35e5adfa6ad1b269f3a22a9b12c4c1ee6513ea` | 7 | 568 |
| feature/compound_query, commit dei test | `4c075f7adac55c05f2dad555b2b1277449388944` | 1 | 19 |
| sql_review/subquery_refactor_v2 | `68f35b99c440df3658d275f3403f10962a953be6` | 8 | 154 |
| origin/feature/subquery_refactor_v3 | `67bba0e59183f6df2b3463064c9feb2c21be225e` | 6 | 104 |
| sql_review/subquery_refactor_v3_merged | `19da337f4632cc69897c9373aa263dcb49abc293` | 10 | 519 |
| sql_review/subquery_refactor_v4 | `38d210c376abaa390619c2b16985318921d6dd1d` | 11 | 533 |
| sql_review/compiler-simplify | `13b891883487e8948921eb6694e14f8e51bc464d` | 5 | 434 |
| compiler_next_step_1 | `12cfdcce86337119591b6c8247e7166d831c08b9` | 9 | 587 |

La ricerca comprende file Python di test con riferimenti alle dichiarazioni,
macro o correlazioni, e moduli dedicati a compiler/sottoquery/query. È stata
controllata anche sull'intero albero Git: nessun test corrispondente ai criteri
fuori dalle directory estratte. Nell'inventario restano anche i candidati
applicativi/DDL non selezionati per questa baseline, marcati esplicitamente.
Non è una promessa di copertura di ogni test dell'intero framework GenroPy.

Sono **816 versioni distinte di definizioni di test**, considerando percorso,
nome e hash, in 26 versioni distinte di moduli selezionati. Non sono 816 test
indipendenti di sola formula: includono casi di supporto, ereditarietà,
parametrizzazione e differenze fra revisioni. I numeri di esecuzione sotto
contano invece i casi effettivamente raccolti da pytest.

Famiglie comprese: formule SQL/scalari, select/exists, formule concatenate,
var_* scalari e liste, select_* nominati, metodi sql_formula, alias, subQueryColumn,
pyColumn, bagItemColumn, compositeColumn, joinColumn, macro, static, WHERE e
ORDER BY sulle formule, navigazione profonda, SQL aggregato e varianti sperimentali
lazy/JOIN dei branch. Queste ultime sono osservate, non approvate per Asqueel.

## Baseline con fixture SQL originali

| Riferimento | Passati | Falliti | Saltati | Errori di setup finali |
| --- | ---: | ---: | ---: | ---: |
| Legacy | 645 | 0 | 10 | 0 |
| Compound, corpus query pertinente | 57 | 0 | 0 | 0 |
| v2, corpus query pertinente | 57 | 0 | 0 | 0 |
| v3, corpus query pertinente | 57 | 0 | 0 | 0 |
| v3 merged | 447 | 15 | 10 | 0 |
| v4 | 447 | 15 | 10 | 0 |
| compiler-simplify, selezione predefinita | 265 | 197 | 10 | 0 |
| compiler_next_step_1 | 746 | 0 | 10 | 0 |

Le suite non sono identiche fra revisioni: v2/v3 non contengono ancora la
successiva `test_compiler_coverage.py` sotto gnrpy/tests/sql. Non confrontare
le percentuali come se fossero lo stesso corpus. La composizione degli operatori
ha inoltre la sonda separata del [piano 56](56-read-compiler-plan.md).

Isolando `test_compiler_coverage.py`:

- Legacy: **294 passati, 9 saltati**.
- Next: **296 passati, 9 saltati**; inoltre i **97 casi** del modulo factory
  passano, includendo il corpus di confronto fra compiler legacy e next.
- v3 merged e v4: **222 passati, 4 falliti, 9 saltati** ciascuno.
- Simplify: **44 passati, 182 falliti, 9 saltati**. La prova aggiuntiva con
  `use_new_compiler=True`, attivato nelle fixture con il flag già esistente,
  dà gli stessi conteggi. Non è quindi un candidato già pronto al porting.

I 10 skip del corpus esteso sono tutti espliciti: limiti SQLite su EXISTS,
GREATEST, INTERVAL e full_virtual_columns. Non sono errori di connessione
mascherati come successi.

I 15 fallimenti v3 merged/v4 riguardano `KeyError: product_year_key`, nella
navigazione di colonne composte e nei relativi test strutturali. Simplify
fallisce soprattutto nella risoluzione di alias/campi: per esempio richiede
`t0.account_name`, `t0.unit_price` o `t0.line_total` sulla tabella sbagliata.
Sono fallimenti delle revisioni legacy eseguite, non regressioni Asqueel.

## Test applicativi dei branch, fixture isolate

I test in `projects/test_invoice/tests` puntavano a un'istanza personale
PostgreSQL. Non è stata usata. È stata sostituita **solo la fixture app/db**
nelle copie temporanee, con un server `testing.postgresql` privato, porta e
directory temporanee, database UUID e cleanup in finally. Nessuna asserzione
o sorgente del test è stata cambiata; confronto byte per byte con Git effettuato.

| Riferimento | Passati | Falliti | Xfail dichiarati | Errori di setup finali |
| --- | ---: | ---: | ---: | ---: |
| v2 | 124 | 4 | 7 | 0 |
| v3 | 85 | 0 | 0 | 0 |
| v3 merged | 85 | 0 | 0 | 0 |
| v4 | 99 | 0 | 0 | 0 |

**Limite dei dati:** i branch v2/v3 contengono solo 8 CSV e si aspettavano dati
aggiuntivi nel database personale. Per la prova isolata sono stati usati i
18 CSV congelati della revisione legacy di riferimento, mantenendo solo tabelle
e colonne presenti nel modello del branch. Il [manifest dei dati](evidence/formula-baseline/project-data.json)
registra righe e omissioni. Questo è un confronto con fixture adattate, non
la riproduzione del dataset personale originale. In particolare sono caricate
3200 customer, 256 invoice e 803 invoice_row. Nessun test è stato indebolito
per adattarsi ai dati disponibili.

I quattro fallimenti v2 sono distinti:

1. `test_intersect_high_volume_high_value`: attende clienti con oltre 20
   fatture e oltre 30.000 di fatturato; il risultato sui CSV è vuoto.
2. `test_where_n_invoices_gt`: attende almeno un cliente con oltre 25 fatture.
3. `test_where_gt_order_desc`: attende clienti con oltre 15 fatture.
4. `test_state_full_torture`: il compiler cerca `code` su `invc.customer` e
   solleva `GnrSqlMissingField`; è un problema di risoluzione, non la stessa
   assenza di righe dei primi tre casi.

I primi tre restano differenze di fixture da colmare, non prove di un difetto
del compiler. I sette xfail originali riguardano sei casi di placeholder non
risolti con `#THIS` su formule annidate e un caso di correlazione che il ramo
indica come bisognoso di LATERAL. Non valgono come test superati. Dei 124 passati
v2, **25 sono benchmark**: attestano esecuzione, non equivalenza dei risultati.

Problemi di allestimento risolti prima della misura finale: dipendenza storica
WebOb assente; `db_attrs` non ancora supportato da v2/v3, sostituito nella fixture
con il loro `custom_config` esistente. Il controllo del backend impedisce di
scambiare SQLite per PostgreSQL. Il primo harness è stato bloccato dalla revisione
automatica; quello eseguito crea direttamente il server privato, senza fallback
a credenziali o database dell'utente.

## Formule: confronto puntuale con Asqueel

Eseguiti **197 test Asqueel, tutti superati**, da `tests/native_compiler/`,
formula_bindings, formula_subqueries, alias_columns, legacy_alias_oracle e
legacy_formula_declarations. È il corpus Asqueel esistente, non il porting
automatico dei test legacy sopra. Alcuni casi usano il modello di basso livello.

In parallelo ogni virtuale dei **74 modelli nativi** è stata compilata
singolarmente, vietando connect/execute e disattivando i filtri per isolare
la capacità della colonna. Risultati completi: [native-columns.json](evidence/formula-baseline/native-columns.json).

| Dichiarazione nativa | Totale | Compila | Bloccata |
| --- | ---: | ---: | ---: |
| formulaColumn | 462 | 0 | 462 |
| aliasColumn | 46 | 39 | 7 |
| subQueryColumn | 3 | 0 | 3 |
| bagItemColumn | 3 | 0 | 3 |
| pyColumn | 12 | 0 | 12 |

Le formule si dividono, dando precedenza a select/exists quando presenti, in
**305 SQL, 134 delegate con sql_formula=True, 21 select e 2 exists**.
Le 134 delegate sono metodi che producono la formula SQL nel legacy: non vanno
confuse con le 12 pyColumn, che richiedono calcolo Python del risultato.

| Famiglia | Prova nel legacy di riferimento | Stato Asqueel e lacuna |
| --- | --- | --- |
| SQL semplici e catene | TestFormulaSql: 6 pass; TestFormulaChain: 4 pass | Motore esistente verificato, dichiarazioni dei package nativi ancora fermate da x_requires_compilation |
| select e exists | TestFormulaSelect: 11 pass/1 skip; TestExistsDict: 2 pass/1 skip | Percorso scalare/EXISTS e #THIS già supportato a basso livello; raccordare le native e le clausole mancanti |
| var_* scalari/liste | 2 + 3 pass | Namespace/binding esistenti, ma dichiarazioni native ancora da tradurre |
| select_* nominati | 4 pass | Motore presente, raccordo nativo incompleto |
| sql_formula=True | 2 pass | 134 dichiarazioni native da collegare ai metodi legacy; non inventare un registro di handler |
| Alias | 10 pass | 39 native compilano; 6 bloccate da formule target e 1 dalla virtualRelation discount_tier |
| subQueryColumn | 8 pass | Le 3 native restano dichiarazioni; completare traduzione e modi previsti |
| bagItemColumn | 4 pass | Le 3 native non hanno ancora traduzione SQL |
| pyColumn | 5 pass/1 skip | Il calcolo appartiene alla fase dei risultati, non alla sola coppia SQL/kwargs |
| Composite e joinColumn | 6 + 4 pass | Chiavi fisiche composte già supportate; non equivalgono a tutti i casi di navigazione/condizioni legacy |
| Macro | PREF: 2 pass; IN_RANGE: 2 pass; PERIOD: 10 pass | IN_RANGE/PERIOD già presenti nei contesti documentati; PREF e altri comportamenti ancora mancanti |

I sei alias bloccati da formule sono task_active_workers, tag_code su
api_token_tag e user_tag, user_fullname su connection, fullname su user_tag e
price_year_label. `invc.invoice.discount_tier_id` richiede navigazione virtuale.
I dettagli qualificati sono nel JSON; nessun alias è stato eliminato dal modello.

## Conseguenze sul lavoro successivo

1. Portare nel percorso nativo i casi SQL semplici, dipendenze, alias e var_*,
   usando gli algoritmi legacy e trasformando i casi censiti in test Asqueel.
2. Collegare select/exists/select_* con scope e correlazioni, includendo i casi
   profondi e le clausole mancanti. Tenere espliciti i bug già presenti nei refactor.
3. Affrontare separatamente i metodi sql_formula: censire i metodi effettivi
   richiesti dal corpus e confrontarne il binding legacy prima di modificarlo.
4. Completare subQueryColumn, bagItemColumn e relazioni nei limiti concordati;
   separare il lavoro sul risultato Python. Non reintrodurre implicitamente
   inverse virtuali, limit/order_by/one_one virtuali o aggregateRows.

La baseline è conclusa per le suite selezionate; **il porting dei test legacy
su Asqueel e la loro equivalenza completa restano da fare**. I tre casi v2
dipendenti dal dataset originale restano aperti. Nessuna nuova sintassi proposta.

## Riproducibilità

Script nel repository:

- [Censimento e snapshot](probes/formula_census.py).
- [Runner delle baseline](probes/run_formula_baseline.py).
- [Fixture applicativa isolata](probes/legacy_formula_project_fixture.py).
- [Flag compiler_new](probes/legacy_new_compiler_fixture.py).
- [Sonda native senza I/O](probes/native_formula_coverage.py).
- [Raccolta e verifica degli esiti](probes/summarize_formula_baseline.py).

Ambiente legacy: Python 3.12.12, PostgreSQL temporaneo 17.7, SQLite del runtime;
[dipendenze esatte](evidence/formula-baseline/legacy-environment.txt).
Import diretto dai sorgenti congelati, senza installare il pacchetto web
completo. Le dipendenze storiche mancanti sono state installate solo nel venv
temporaneo. Log estesi e JUnit: `/tmp/asqueel-formula-baseline/`.
L'[evidenza persistente per ogni test](evidence/formula-baseline/results.json)
conserva nomi, stato e motivo dei fallimenti/skip/xfail.

Esempi dalla root Asqueel, con ambiente di dipendenze già preparato:

```sh
venv/bin/python docs/design/probes/formula_census.py \
  --legacy /Users/gporcari/Sviluppo/Genropy/genropy \
  --output /tmp/asqueel-formula-baseline
venv/bin/python docs/design/probes/run_formula_baseline.py \
  --root /tmp/asqueel-formula-baseline \
  --labels legacy compound v2 v3 v3_merged v4 simplify next --suite sql
venv/bin/python docs/design/probes/run_formula_baseline.py \
  --root /tmp/asqueel-formula-baseline \
  --labels v2 v3 v3_merged v4 --suite project
PYTHONPATH=src:. venv/bin/python docs/design/probes/native_formula_coverage.py \
  --output /tmp/asqueel-formula-baseline/asqueel-native-columns.json
```

I test che richiedono PostgreSQL vanno avviati con permesso di creare un server
temporaneo. Non si usano i database personali. Ruff passa sui sei script di
supporto; integrità dei sorgenti di test selezionati verificata contro Git.
