# 49 — Correzioni e verifica delle aggiunte alla grammatica

**Decisione successiva:** [schemi dedotti dai package](50-schemas-from-packages.md);
nessuna dichiarazione schemas nella nuova configurazione.

12 ottobre 2026. Richiesta dell'utente: togliere la dichiarazione di variabili
DB introdotta dall'assistente, usare EnvResolver e resolver esistenti, incluso
BagCbResolver per valori calcolati; controllare le altre aggiunte non concordate.
**Perimetro: source e grammatica. Nessun nuovo rendering a oggetti vivi.**

## Correzioni effettuate

| Aggiunta dell'assistente | Riscontro e correzione |
| --- | --- |
| `db.options().context(...)` | Mai concordata, nessun equivalente dichiarativo necessario nel legacy. Rimossa da elementi, dispatch, grammatica generata ed esempi. Le vecchie source con questo nodo sono rifiutate. |
| `partition(..., context='...')`, `tenant(context='...')` | Introducevano un contratto aggiuntivo di nomi ambiente. Rimossi i parametri; partition conserva il campo e riceve `value`, anche EnvResolver/BagCbResolver. Tenant può dichiarare il solo flag presente nel legacy. |
| Provider obbligatori per audit, tenant, retention, broadcast, archive, enabled_when, attachments, numbering e cifratura | Il legacy non richiede questi nomi. Tolto l'obbligo; nessun nome fittizio nell'esempio. Il parametro facoltativo già esposto resta una proposta di binding, non un registro implementato o deciso. |
| Sintassi di versione dei provider, per esempio `@1` | Nessuna decisione né necessità verificata. Rimossi contratto, validatore specifico ed esempi; le stringhe eventualmente fornite restano opache. |
| `column.generation(type='uuid'/'manual'/'sequence')` | Il documento 40 lasciava aperti i casi ulteriori e confermava UUID in sys_fields. Rimossa l'API separata e il suo contratto proposto. Rimane sys_fields(id={'type': 'uuid'}). |
| Rifiuto dei resolver come oggetti non JSON | Incompatibile con l'indicazione dell'utente. I payload dati ammettono BagResolver senza chiamarlo; un callback viene racchiuso in BagCbResolver. Non aggiunti nuovi resolver Asqueel. |
| `invc.invoice_atc`, `invc.settings`, schema `business`, assenza di adm, requires sys su invc | Esempi inventati, non test_invoice_pg. Sostituiti con selezione di tabelle dei tre package reali e mapping sys/adm/invc. L'allegato reale è adm.htmltemplate_atc; la dipendenza verificata è adm → sys. |
| Gerarchia product_type su code; audit/retention/archive sull'invoice | Attribuzioni dell'esempio non verificate. Ripristinata la gerarchia legacy su description e tolte le options aggiunte per mostrare il catalogo. |

`value` è il parametro minimo per fornire direttamente il valore/resolver della
partition secondo l'ultima indicazione; non è un nuovo registro. Il suo uso
applicativo e la risoluzione sono della prossima fase.

## Provenienza delle famiglie rimaste

Fonti: [decisioni 40](40-model-and-operation-recipes.md),
[censimento 43](43-test-invoice-model-coverage.md),
[inventario AST](evidence/test-invoice-model-inventory.json) e sorgenti GenroPy.
Il checkout legacy è `/Users/gporcari/Sviluppo/Genropy/genropy`.

| Famiglia | Evidenza |
| --- | --- |
| db, connection, schemas, packages, options; quattro attributi table | Decisioni esplicite del documento 40 e della conversazione. Options ammesse ai vari livelli non implica funzioni nuove approvate per ciascun livello. |
| sys_fields, UUID 22 e campi standard | Decisioni 40; gnrpy/gnr/app/gnrdbo.py sysFields; algoritmo gnrpy/gnr/core/gnrlang.py getUuid. |
| validation e validate_* | Decisione esplicita sull'embedding locale; invc/customer.py. |
| hierarchical, auto_counter, dynamic_fields, relative_index | gnrdbo.py sysFields, sysFields_counter, sysFields_df, sysFields_relidx; invc/product_type.py e invoice_row.py. hdepth, root_id e linked_to esistono nel legacy. |
| record_hash, full_update, protection, diagnostics, system_records, release | gnrdbo.py sysFields e helper, documentati nell'analisi 34. md5 su adm/user.py; metodi sysRecord_* e _release_* nel legacy. |
| pkey_from | pkey_columns: sys/service.py, adm/counter.py e altri. È una chiave testuale derivata, distinta dalle chiavi composite SQL. |
| audit | sys/widget.py, audit lazy; non l'invoice del precedente esempio. |
| partition | invc/customer.py partition_state e invc/invoice.py partition_customer_state. |
| tenant | adm/counter.py multi_tenant=True. Nessuna variabile tenant_id necessaria da dichiarare sul DB. |
| retention | sys/error.py (__ins_ts, 60), sys/task_execution.py (__ins_ts, 180). |
| broadcast, archive, enabled_when | adm/userobject.py broadcast/archivable; adm/connection.py e served_page.py checkpref. |
| attachments | adm/htmltemplate_atc.py eredita AttachmentTable; gnrdbo.py contiene l'espansione legacy. |
| numbering | invc/invoice.py counter_inv_number; l'esempio conserva il relativo dizionario. |
| type, requires, macro | invc/main.py custom_type_money/perc e registerMacros/addMacro; adm/main.py required_packages. Il bisogno legacy è verificato, la nuova firma macro e il suo binding restano proposte. |
| relation, weak_relation, virtualRelation, alias/formule/sottoquery, composite, indici | Costruzioni presenti nell'inventario 43; relations e virtual relations richieste esplicitamente. Le forme nuove sono adattamenti di sintassi, non comportamenti già verificati. |
| behavior | Il bisogno di collegare i metodi della Table esiste nel legacy; la firma dichiarativa è una proposta. Registro, import, versione e precedenza degli hook non sono decisioni acquisite. |
| metadata/x_ui, normalize, encryption, colgroup | Il legacy ha metadati UI, validate_case, encrypted e group_*; la loro collocazione nelle nuove sezioni è proposta nel 42, non una decisione nominativa dell'utente. |

## Proposte da non presentare come decisioni

La richiesta di formulare una grammatica finale da rivedere autorizzava una
proposta concreta, non a etichettarne ogni dettaglio come già concordato.
Restano da rivedere: nomi delle sezioni adattate dal legacy, parametri dei
provider facoltativi, firme macro/behavior, precedenza dei default e hook,
normalizzazione distinta da validation, policy di errore pkey_from e dettagli
delle virtual relations. Non è stato introdotto codice che ne esegua gli effetti.

Anche il default DHZ proposto in sys_fields non era una decisione sulla timezone:
la scelta resta aperta nel documento 40. L'esempio specifica DH e user_upd=False
per mostrare il profilo legacy, senza attribuire quel profilo a tutti i modelli.
Il default user_upd=True di Asqueel è invece una decisione esplicita e resta.

## Resolver e limiti della verifica

EnvResolver legge l'ambiente del processo, non automaticamente currentEnv.
Per currentEnv/workdate applicativi l'host passa un callback a BagCbResolver.
La source conserva entrambi senza leggere credenziali o chiamare il callback.
Non si serializza automaticamente codice Python: il round-trip JSON dei dati
puri non dimostra la trasferibilità dei callback. La fase delle ricette remote
dovrà stabilire il binding usando le capacità già disponibili.

L'[esempio corretto](../../examples/model_grammar/configure.py) usa solo nomi di
tabelle dell'inventario, ma seleziona dichiarazioni per la revisione: non è il
porting integrale delle 75 tabelle. Riferimenti a tabelle non mostrate sono
intenzionali e non vengono risolti in questa fase. Etichette italiane e nomi
delle variabili di processo sono scelte illustrative, non estratti di credenziali.

Le prove impediscono l'esecuzione di resolver durante build, clone e composizione,
verificano rifiuto delle API ritirate anche in source importate, dichiarazioni
senza provider fittizi e appartenenza delle tabelle all'inventario. Restano i
controlli di firme chiuse, payload, composizione e grammar export.

Esito: **1000 test superati, 1 saltato**, inclusi i test PostgreSQL locali;
Ruff superato e mypy senza errori nei 50 file sorgente nell’ambiente di verifica.
