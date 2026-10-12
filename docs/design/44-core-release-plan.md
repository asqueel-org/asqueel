# 44 — Piano di implementazione del core e prossima release

Data: 12 ottobre 2026. Stato: **P0 completata, P1 in corso**.
Target proposto: **0.6.0**, dalla baseline aggiornata 0.5.2. Il numero è una scelta
di pianificazione per il cambiamento della grammatica pubblica; versione, tag
e pubblicazione verranno aggiornati soltanto nella fase di release.

## Risultato atteso

Una release usabile nella quale si possa:

1. configurare il modello completo con DB, schemi, package, options, colonne,
   validazioni, indici, relazioni fisiche/deboli/virtuali e comportamenti;
2. costruire e ispezionare tutti i modelli di `test_invoice_pg` (`sys`, `adm`,
   `invc`), comprese espansioni ereditate e contributi fra package;
3. produrre dagli oggetti il JSON normalizzato di `asqueel-migration`, applicarlo
   a un DB temporaneo e ottenere una seconda diff vuota;
4. costruire SELECT/INSERT/UPDATE/DELETE come ricette trasferibili JSON/XML,
   compilarle ed eseguirle mantenendo binding, policy, hook e transazioni;
5. installare una distribuzione verificata, con grammatica e guide corrispondenti
   al codice, procedura di aggiornamento e compatibilità dei consumer dimostrata.

Riferimenti vincolanti: [accordi 40](40-model-and-operation-recipes.md),
[grammatica 42](42-configuration-grammar.md),
[copertura 43](43-test-invoice-model-coverage.md),
[rinvii 41](41-deferred-features.md). La revisione ha confermato per `table`
`name_long`, `name_short`, `name_plural`, `caption_field`. Relazioni e indici
seguono le firme discusse; la terna di etichette per ciascun verso di una
relazione non è stata aggiunta: restano `one_name` e `many_name`.

Questo piano coordina il lavoro corrente e prevale sulle sequenze storiche dei
piani 15/32/33; ne riusa analisi e test pertinenti senza considerarli tutti da
rifare. Le scelte ulteriori del 42 sono la base progettuale da implementare,
con eventuali correzioni motivate registrate prima di cambiare il contratto.

## Baseline verificata per scrivere il piano

- Core: HEAD `92466b90bb854cd897db5b0ff0bb327f8df9782b`, branch
  `chore/dbmanager-migration-compatibility`, pyproject 0.5.1.
- Working tree con documentazione di questa conversazione e file preesistenti:
  preservare tutto; niente reset o inclusione indiscriminata nei commit.
- `elements.py` espone ancora schema→tables e contenitori columns/virtuals;
  `configuration.py` ha già configurazione montabile e connessioni nominate.
- `contracts.py`/`model.py` hanno oggetti risolti parziali; mancano il nuovo
  assetto completo schema/package/options e alcune semantiche virtuali.
- `projection.py`, `migration.py` e renderer implementano già il collegamento
  al migratore; non costruire un secondo motore di diff/DDL.
- Query, compilatore, scritture RECORD/RAW, policy e trigger Python esistono:
  estenderli preservando le prove correnti. Non reintrodurre Session.
- `tests/test_invoice_model.py` e `test_wf_phase19_invoice_model.py` usano un
  esempio ridotto; **non** attestano la copertura del corpus 43.
- CI esistente: Python 3.11/3.12/3.13, PostgreSQL 17, profili core/routes/asgi,
  lint, tipi, docs e prove della wheel installata. Workflow publish da tag `v*`.
- 868 test/95% sono risultati storici nelle release notes, non una suite
  rieseguita per questo piano. Stato remoto e dipendenze risolte da aggiornare
  all'avvio dell'implementazione.

## Perimetro e regole di consegna

Tutta la grammatica 42 è nel piano, comprese options avanzate, validation,
metadati e virtuali senza DDL. La sola accettazione delle keyword non costituisce
implementazione: ciascuna deve avere oggetto, significato e verifica osservabile.

Per behavior esterni il core consegna protocollo, registro, binding e controlli
di capability; l'integrazione legacy consegna il raccordo dei provider necessari
al corpus. Non occorre riscrivere frontend, autenticazione, storage o scheduler
di GenroPy nel core, ma non si può dichiarare eseguibile una funzione richiesta
lasciando un handler fittizio o ignorato. Nessun import GenroPy obbligatorio per
installare/usare il core; il bridge deve restare opzionale e separato.

`toolColumn` resta esclusa per decisione esplicita. Non aggiungere a questa
release un generico DDL per view/funzioni/trigger SQL/CHECK arbitrari, già fuori
dalla grammatica 42; conservare gli oggetti DB non gestiti. Trigger Python e
azioni applicative delle relazioni sono invece inclusi. Non includere un server
HTTP o un'app browser: il contratto trasferibile deve comunque essere provato
con un produttore che non importi Asqueel e un esecutore separato.

Compatibilità proposta: una normalizzazione d'ingresso circoscritta conserva
le ricette pubbliche 0.5.1 traducibili senza ambiguità verso il nuovo modello.
Nessun doppio modello runtime. Forme ambigue o comportamenti cambiati producono
diagnostica e guida di migrazione; non cambiare silenziosamente FK, nomi fisici,
default, filtri o generatori. Il profilo legacy esplicita user_upd, timezone,
prefissi e altri valori necessari a conservare uno schema esistente.

Ogni fase termina con implementazione, prove mirate dei contratti, documenti
aggiornati e un commit coerente dopo revisione del diff. Non marcare completata
una fase con test di accettazione saltati per mancanza di DB/provider. Gli esiti
si registrano in questo piano con commit e comandi; niente vecchi conteggi
riportati come risultati nuovi. La preparazione del piano non crea commit o tag.

## Sequenza e dipendenze

| Fase | Consegna | Dipende da | Stato |
| --- | --- | --- | --- |
| P0 | Baseline, contratti e corpus riproducibile | — | Completata: report 45 |
| P1 | Source DB/schema/package/options e composizione | P0 | In corso: primo incremento nel report 46 |
| P2 | Oggetti completi e registro delle estensioni | P1 | Da fare |
| P3 | Colonne fisiche, chiavi, FK e indici | P2 | Da fare |
| P4 | Validation, colonne virtuali e virtual relations nel modello | P3 | Da fare |
| P5 | Espansioni options e modello completo dei tre package | P4 | Da fare |
| P6 | JSON del migratore e verifica PostgreSQL completa | P5 | Da fare |
| P7 | Compilazione delle espressioni e navigazioni mancanti | P6 | Da fare |
| P8 | Ricette delle operazioni, codec e compilazione separata | P7 | Da fare |
| P9 | Esecuzione dei comportamenti e ciclo delle scritture | P8 | Da fare |
| P10 | Collaudo completo e compatibilità consumer | P9 | Da fare |
| P11 | Release candidate installabile e documentazione | P10 | Da fare |
| P12 | Tag, pubblicazione e verifica della release | P11 | Da fare |

Tre traguardi verificabili: **P6 modello+migrations**, **P9 operazioni complete**,
**P11 distribuzione pronta**. Sono punti di verifica, non riduzioni automatiche
del perimetro della release se un requisito risulta difficile.

## P0 — Fissare baseline e prove indipendenti

**Esito:** [report 45](45-release-baseline-and-oracle.md). Base aggiornata a
main `4641a0e` (0.5.2), 876 test passati/1 skip; oracolo legacy indipendente
di 75 tabelle, 796 colonne fisiche e 58 FK, riproducibile in due processi.
I contratti di confine e le firme tipizzate sono fissati prima delle modifiche;
la loro validazione eseguibile appartiene alle fasi di implementazione indicate
nel report. Non confondere i cinque test dell'oracolo con prove del nuovo modello.

**Lavoro**

- Controllare HEAD, remoto e dipendenze effettive; isolare il lavoro dai file
  estranei senza perdere documentazione della conversazione.
- Eseguire la baseline pertinente, poi la suite di riferimento prima delle
  modifiche strutturali; distinguere guasti preesistenti e nuovi.
- Trasformare il censimento 43 in fixture portabili: tutti i 75 modelli attesi,
  contributo adm→sys.task, sorgenti ereditate e hash delle fonti.
- Ricavare un oracolo legacy completo in ambiente controllato: source espansa,
  proprietà del modello e snapshot fisico normalizzato senza dati/segreti.
  I conteggi AST non sostituiscono questo risultato. Una divergenza dal conteggio
  atteso va spiegata, non corretta eliminando casi dal corpus.
- Scrivere prima del codice gli esempi pubblici e i contratti di confine:
  UNSET/None/False/reset, alias legacy, id generation, RAW, one_one, default di
  filtering, serializzazione di espressioni e binding, capability dei provider.
- Tradurre le scelte ancora descrittive del 42 in schemi tipizzati per payload
  options/handler/validation; fissare formato e versionamento, senza **kwargs
  che assorbano comportamento sconosciuto.

**Uscita:** inventario dei requisiti collegato a test e fonti; fixture CI senza
percorso assoluto verso il checkout dell'autore; baseline documentata; oracolo
indipendente dal producer nuovo. Blocchi infrastrutturali sono visibili.

## P1 — Grammatica della source e contributi ordinati

**Avanzamento:** [report 46](46-source-configuration-progress.md). Implementati
package distinti dagli schemi, accessi singleton, routing diretto dalla tabella,
gruppi, options di base, connessioni nominate e composizione con reset/None.
Suite completa: 919 passati, 1 skip; Ruff e mypy verdi. Questa è una consegna
intermedia: non chiude P1 e non certifica ancora il nuovo modello risolto.
Il test storico che vietava `tbl.column(...)` è aggiornato alla decisione
esplicita del 42; conserva la prova di equivalenza dei contenitori interni.

**Lavoro:** intervenire su builder, elements e configuration. DB contiene
connection/schemas/packages/extensions/options; table riceve pkg; colonne,
virtuali e indici si dichiarano direttamente sulla tabella. Implementare
contenitori singleton, attributi standard di table, gruppi, routing interno,
resolver di connessione e options per livello. Composizione con provenienza,
default post-merge, disattivazione/reset e conflitti espliciti. Normalizzare
le forme 0.5.1 compatibili all'ingresso.

**Prove:** stessa ricetta autonoma/montata produce lo stesso source; contributi
successivi non reimpostano valori omessi; override sulle options non duplica
campi; errori per typo/livello scorretto/collisioni; costruzione senza connessioni
né risoluzione di segreti. Colgroup preserva ordine e default senza duplicare nodi.

**Uscita:** gli esempi di configurazione 42 sono costruibili e validati; restano
esplicite le capability ancora prive di oggetti/esecuzione nelle fasi successive.

## P2 — Modello risolto completo

**Lavoro:** estendere contracts/model/object_renderer con DB, Schema, Package,
Table, gruppi, Options e descrittori di behavior; conservare schemi/package
vuoti e metadati. Separare identità logica e fisica. Registro di estensioni con
firme, costruttori, versioni e dipendenze. Registro separato dei provider server.
Accesso runtime agli oggetti e attributes coerenti, senza ricetta conservata
come seconda fonte di verità. Definire export del modello distinto da connection
config, JSON migrations e ricette delle operazioni.

**Prove:** mapping schema/package/prefix/sqlname, collisioni fisiche, forward
reference, isolamento delle mappe restituite, niente dipendenza dalla source
dopo render; provider sconosciuti e versioni incompatibili rilevati con percorso.

**Uscita:** il modello conserva ogni dichiarazione riconosciuta; nessuna sparisce
perché non ha un effetto SQL.

## P3 — Struttura fisica, identità e indici

**Lavoro:** tipi nativi/custom di package, size/default SQL/generated columns,
colonne e composite, PK/UNIQUE/FK multicolonna, weak relations e inverse, nomi
fisici, indici semplici/composti/ordinati/univoci/parziali e opzioni del dialetto.
Distinguere pkey_from testuale, composite SQL e descrittore di generazione.
Registrare le azioni applicative delle relazioni senza convertirle in DDL.

**Prove:** inferenza dei tipi delle FK, target univoci, componenti ordinate e
remapping di nomi; SQL on_delete/on_update separati dai Python; deferrability;
unicità su composite senza falsa colonna persistita. Deduplicare indici solo
quando equivalenti/coperti: un indice parziale o di metodo incompatibile non
copre automaticamente un indice completo richiesto. Una FK non può riferire
come UNIQUE universale un semplice indice univoco parziale.

**Uscita:** oggetti fisici completi e identità stabili; nessuna UNIQUE aggiunta
solo perché one_one=True.

## P4 — Validation e modello virtuale

**Lavoro:** validation con embedding validate_* locale ad Asqueel, normalizzazioni
separate, messaggi e capability client/server. Modello per formulaColumn,
aliasColumn, subQueryColumn, pyColumn, compositeColumn, bagItemColumn, subtable
e virtualRelation; parametri, dipendenze, tipi e handler simbolici. Tradurre
joinColumn/aliasTable legacy in costrutti canonici senza mantenere due semantiche.

**Prove:** embedded ed esplicito equivalenti, errore su typo, codec dei valori,
regole NULL/len/regex e nodup server; risoluzione di alias e cicli; pairing,
cardinalità, ask/source_parameters, limit/ordine e inversa virtuale; descrittori
di calcolo Python non eseguiti durante il render. Definire fixture di conformità
esportabili a Gramlot e provare le regole client supportate nel consumer reale,
senza promettere località per nodup/exists.

**Uscita:** tutte le virtuali rappresentate nel modello; le capability non ancora
compilabili sono segnalate, mai perse nella proiezione o accettate come SQL libero.

## P5 — Options ed espansione completa di test_invoice_pg

**Lavoro:** implementare fase di espansione deterministica, dipendenze e conflitti
di generazione. Coprire l'intero catalogo 42: sys_fields; hierarchical;
auto_counter/relative_index; dynamic_fields; record_hash/full_update; audit;
system_records/protection/diagnostics/release; partition/tenant; retention;
broadcast/archive/enabled_when; attachments/numbering; behavior e cifratura.
Per i provider esterni implementare contratto e raccordo necessario al corpus;
espansione fisica e runtime devono avere capability distinte.

Generazione UUID con algoritmo legacy esatto come servizio testabile, collegato
al descrittore senza eseguirlo durante build/serialize/compile. Default dei campi
di sistema e relative personalizzazioni; convenzioni legacy risolte dal bridge
in riferimenti espliciti. Attivazioni da sysRecord_*, release, defaultValues e
metodi ereditati incluse. Gestire AttachmentTable e la modifica del master.

**Prove:** oggetti generati e metadati corrispondono all'oracolo completo; ordine
delle chiamate alle options irrilevante dove concordato; disattivazione e
collisioni; versione/hash delle dipendenze; nessuna creazione di dati, ID,
connessioni o side effect esterno nel render. Copertura per ciascuna riga del 43.

**Uscita:** build completa dei tre package, con manifest di colonne/virtuali/
relazioni/options/provider e differenze deliberate documentate. Nessuno stub
silenzioso per far passare il conteggio delle tabelle.

## P6 — Proiezione JSON e collaudo migrations

**Lavoro:** aggiornare projection/renderer/reader/emitter/migration sulle nuove
identità; proiettare solo dagli oggetti tramite il contratto del migratore.
Conservare schemi vuoti, extensions, PK e nomi FK/indici stabili. Aggiornare il
percorso Python e CLI già esistente; core utilizzabile senza extra migration.

**Prove obbligatorie sui tre package:**

1. JSON normalized validato da StructureValidator e confronto con oracolo legacy.
2. Report completo di differenze attese/inattese, inclusi timestamp/user_upd,
   prefissi, campi generati e FK adm→sys.task.
3. Apply su PostgreSQL temporaneo, introspection e seconda diff vuota sul
   perimetro gestito; non solo assenza di comandi perché una capability è saltata.
4. Modifiche controllate a colonna, UNIQUE, FK e indice: diff/apply/rilettura;
   errori espliciti per feature non supportate, preservazione oggetti non gestiti.
5. Round-trip fisico reader/emitter senza dichiarare recuperabili dal DB options
   e behavior che esistono solo nel modello; round-trip completo tramite codec
   del modello verificato separatamente.
6. SQLite: prove sulle capability dichiarate e rifiuto prima del DDL per le altre.

**Uscita:** primo traguardo modello+migrations superato. Nessun DDL sull'istanza
reale test_invoice_pg. Se il contratto migratore manca di una feature necessaria,
registrare input/output e test consumer; non inserire un DDL alternativo nel core.

## P7 — Completare compilazione e letture

**Lavoro:** estendere parser/resolver/query_plan/compiler/dialetti già esistenti,
usando il piano 32 e i test correnti. Portare le espressioni effettive del corpus:
tipi custom, macro, sottoquery nominate/correlate, gruppi e aggregati, Bag/XML,
alias multipasso, composite, contesti e policy; calcoli Python post-fetch con
dipendenze. Compilare virtualRelation, pairing/inverse, ordine/limit e collezioni.

**Prove:** risultati reali PostgreSQL con dataset deterministico per sys/adm/invc;
cardinalità scalare violata, intervalli sovrapposti, NULL, legami compositi,
ordinamento stabile, cicli e namespace parametri. Preservare count/distinct/
grouping/locking già consegnati. Caso invoice.duplicate_products: riscrittura
motivata o errore esplicito, nessuna selezione arbitraria di una riga.

**Uscita:** espressioni richieste dai modelli compilano ed eseguono, oppure un
errore del modello legacy ha una correzione esplicita nel corpus e nell'oracolo.
Le anomalie non diventano esclusioni nascoste dalla release.

## P8 — Ricette trasferibili e compilazione separata

**Lavoro:** introdurre source/contratti delle operazioni con versione, riferimenti
logici, payload tipizzati, parametri e requisiti del modello. SELECT/INSERT/
UPDATE/DELETE, bulk e soft_delete/restore; distinguere modalità RECORD/RAW.
JSON e XML round-trip, renderer Python per ispezione/ricostruzione server fidata,
compilazione SQL+binding o piano multistatement quando richiesta dal lifecycle.
Gli entry point correnti possono restare facade di esecuzione immediata sul nuovo
percorso; definire accesso esplicito alla costruzione senza I/O.

**Prove:** costruire/renderizzare/compilare non scrive, non genera UUID e non
invoca hook. Decimal, date/time, timezone, bytes, NULL, collezioni e composite
conservano tipi/ordine. Payload prodotto senza importare Asqueel, trasferito a
un altro processo e validato/compilato lì; confronto con operazione locale.

Ingresso remoto: schema chiuso, limiti strutturali, versioni compatibili,
riferimenti verificati e funzioni ammesse, valori sempre binding. Rifiutare
SQL libero, callback/import arbitrari, tentativi di scegliere identità server
o bypass RAW/policy; XML senza risoluzione di entità esterne. Autorizzazione
applicativa separata dalla validità della struttura. Il renderer Python non è
un formato di codice da eseguire se ricevuto da un client.

**Uscita:** una ricetta costruita su un processo può essere eseguita su un altro
senza trasportare connessioni, segreti, oggetti runtime o codice applicativo.

## P9 — Comportamenti di lettura/scrittura e transazioni

**Lavoro:** collegare options e behavior al lifecycle esistente. Default,
normalizzazione, before, generazione/calcoli, validation/invarianti, SQL e after;
new_pkey_value, pkey_from e UUID legacy; timestamp/utenti, draft, soft-delete,
protezioni, cifratura, hash, gerarchie e contatori concorrenti. Azioni applicative
delle relazioni, duplicazione e scritture collegate. Integrare provider audit,
tenant, numbering, ecc. con errori espliciti e capability verificabili.

**Prove:** id dato preservato; id assente generato una volta in esecuzione;
bulk RECORD coerente; RAW esplicito senza generazione/hook impliciti. Trigger
before possono modificare il record ma non saltare validation; old_record e
chiave originale preservati, nested writes, rollback-only e stack ripristinato.
Concorrenti su contatori/gerarchie/uniqueness; nessun MAX()+1 non protetto.
Test di successo e fallimento dei provider, con riscontro dello stato DB;
nessun commit implicito e side effect esterni nel corretto confine dopo commit.
Le suite del core usano provider locali controllati; l'accettazione del bridge
deve provare i raccordi reali e non soltanto mock che non fanno nulla.

**Uscita:** secondo traguardo, modello+migrations+operazioni coerenti; le opzioni
non sono soltanto dichiarazioni. Le policy client non sostituiscono controlli
server e contesto autenticato.

## P10 — Accettazione completa e consumer

**Lavoro:** eseguire scenari su un DB creato dal JSON del modello completo:
cliente/prodotto/fattura/righe, totali e numerazione; chiavi testuali e composite;
sys.task con user_id; gerarchie/df; allegati e record di sistema con provider
necessari. Verificare trasporto delle stesse ricette, risultati, errori e rollback.

**Prove:** nessun requisito 42 e nessuna riga 43 senza riscontro; nessun test
centrale saltato. Confronto oracolo/schema dopo le operazioni; niente nuova diff
DDL. Regressioni complete PostgreSQL/SQLite, configurazione montata e nomi
connessione. Test consumer per Asqueel Migration e DB Manager, compreso insert
senza id e gestione errori; registrare commit/versioni effettivamente verificati.

**Uscita:** report unico con requisiti, test, versioni, limitazioni documentate e
risultati. Un limite che elimina una funzione concordata richiede revisione
esplicita del perimetro: non è una release completa semplicemente perché la CI
ridotta passa.

## P11 — Release candidate e distribuzioni

**Lavoro:** proporre versione finale 0.6.0 sulla base delle modifiche realmente
consegnate; aggiornare dipendenze minime/massime dopo i test, file requirements
e matrice CI coerenti. Rigenerare docs/grammar.md dall'API, tutorial eseguibili,
guide modello/options/recipes/migrations/writes, API changes e release notes.
Il documento 42 passa da target a descrizione consegnata solo per le parti
dimostrate; archiviare gli scostamenti anziché lasciare due grammatiche attive.

**Gate distribuzione:**

- Ruff su src/tests/scripts, mypy su src/asqueel e Sphinx con warning come errori.
- Wheel e sdist costruite, twine check --strict e check_distribution.py.
- Installazione pulita fuori checkout, pip check, check_installed.py con suite
  e PostgreSQL; Python 3.11/3.12/3.13 e profili core/routes/asgi della CI.
- Core-only senza migratore; combinazioni supportate delle dipendenze dichiarate,
  incluse quelle minime e più recenti ammesse. Nessun PYTHONPATH che mascheri
  dipendenze non rilasciate nel pacchetto destinato agli utenti.
- Smoke dalla wheel: modello tre package, JSON, migrazione temporanea,
  ricetta serializzata, INSERT senza id, lettura/UPDATE/DELETE e rollback.
- Verifica dei contenuti delle distribuzioni: includere risorse necessarie,
  escludere credenziali, snapshot con dati e file locali estranei.

**Uscita:** commit e artefatti candidati identificati, documentazione verificata
e report P10/P11 allegabili alla release. Nessun tag di pubblicazione anticipato.

## P12 — Pubblicazione e verifica installazione pubblicata

L'azione attuale richiesta è preparare il piano: questa fase descrive la futura
pubblicazione, non la esegue. Alla consegna della release verificare che la
pubblicazione sia nel mandato operativo della sessione.

**Lavoro:** far atterrare il commit candidato secondo il flusso del repository;
richiedere CI completa verde sul commit esatto da taggare. Il workflow publish
attuale esegue build/smoke ma non dipende dalla suite Tests: non considerarlo da
solo prova del gate P11. Allineare tag/versione e usare il workflow PyPI esistente;
verificare che i file pubblicati corrispondano ai candidati controllati.

**Prove finali:** installazione da indice in ambiente pulito, versione e import,
risorse di grammatica, smoke della ricetta e della migrazione su DB temporaneo.
Annotare URL della release e risultato del workflow. Se la pubblicazione o lo
smoke falliscono non segnare la release completata né spostare tag già pubblicati:
diagnosi e versione correttiva secondo la situazione.

**Uscita:** release effettivamente disponibile e verificata; handoff aggiornato
con versione, commit, dipendenze, esiti e residui esplicitamente concordati.

## Avvio operativo

P0 è completata nel commit `d767299`; il corpus completo e la baseline sono
nel report 45. Proseguire **P1** dai residui del report 46, quindi P2: non
anticipare un export dei nuovi package usando il vecchio modello parziale.
Package/schema, composizione e modello risolto sono le dipendenze comuni di
tutte le funzionalità richieste.

Il piano non promette una data di release senza baseline e dimensionamento
delle espansioni legacy. L'avanzamento si misura con i gate P6/P9/P11 e con la
matrice delle prove, non con il solo numero di metodi o keyword implementati.
