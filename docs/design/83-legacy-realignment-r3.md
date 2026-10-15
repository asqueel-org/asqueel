# 83 — R3: preparazione SQL e kwargs negli adapter

**Nota successiva alla review:** questo è il rapporto storico R3 su `fa35e5ad`.
Il [censimento 95](95-develop-reference-audit.md) adotta develop `95da66ee64` per i prossimi raccordi.
Il contratto storico sotto «parametro ordinario mancante lasciato al driver»
è superato dal raccordo di `5ddb6813dc`: i binding mancanti sono ora
materializzati come None nei kwargs preparati prima del congelamento del mapping,
senza sostituire i placeholder SQL. PostgreSQL continua a richiedere un contesto
di tipo per un parametro usato soltanto con IS NULL; nessun cast automatico.
I test portati sono in `test_legacy_preparation.py` e `test_tree_missing_bindings.py`.
Restano valide le
convenzioni `%%` e `\:`. Il difetto dei prefissi `:ids`/`:ids2` è stato
corretto separatamente con `\b`; le collisioni dei nomi generati restano distinte.

14 ottobre 2026. **R3 completata.** Suite finale: **3.918 test superati,
13 saltati**. Lint dei tredici file Python interessati superato.

Preparazione offline secondo il [piano 79](79-legacy-compiler-realignment-plan.md):
compilazione del modello, assemblaggio della SELECT, preparazione degli argomenti
e infine esecuzione sono passaggi distinti. La preparazione non apre connessioni
e non passa nuovamente SQL già preparato nel formatter strutturato.

Riferimento: GenroPy `fa35e5adfa6ad1b269f3a22a9b12c4c1ee6513ea`. Nessuna nuova
sintassi, modalità pubblica o parser di espressioni.

## Algoritmi portati

| Fonte legacy | Raccordo |
| --- | --- |
| `gnrsql/execute.py`, prima di `prepareSqlText` | `prepare_arguments`: ambiente, precedenza degli input espliciti, bytes UTF-8, rimozione di `\$` e `\@` iniziali dai valori |
| `execute`, protezione di `\:` | Sostituzione con il medesimo carattere sentinella prima dell'adapter e ripristino dopo |
| `gnrpostgres.RE_SQL_PARAMS` / `prepareSqlText` | Stessa regex, esclusione dei cast `::`, nomi Unicode, formato `%(name)s` e sostituzione globale `REGEXP → ~*` |
| `gnrpostgres3.adaptTupleListSet` | Espansione delle collection PostgreSQL, con gli stessi nomi e la stessa gestione dei vuoti |
| `_gnrbaseadapter.adaptTupleListSet` | Espansione SQLite, nomi `nome0`, `nome1`, ecc., tuple/list/set e forma vuota `()` |
| `gnrsqlite.prepareSqlText` / `_booleanSubCb` | `ILIKE/ilike`, `~* → REGEXP`, traduzione dei booleani con la semantica NULL del riferimento |
| `gnrsqlite.connect` / `_regexp` | Registrazione della funzione SQLite `regexp`, con `re.match` come nel legacy |

Il nucleo non contiene scelte PostgreSQL/SQLite: delega sempre al driver.
Gli algoritmi di preparazione sono in `drivers/sql.py`; la funzione regexp
appartiene alla connessione SQLite. Il precedente compilatore continua a usare
il formatter strutturato `prepare(SqlStatement)`, non modificato da R3.

## PostgreSQL: adattamento obbligato a psycopg 3

Il vecchio adapter psycopg2 lasciava la tupla in un singolo placeholder dopo IN.
La [prova reale](evidence/legacy-realignment-r3/psycopg-tuple.json) mostra che
psycopg 3 invia `IN $1`, rifiutato da PostgreSQL. L'espansione in placeholder
distinti funziona.

È stato quindi ripreso **l'algoritmo già presente nell'adapter legacy
postgres3**, mantenendo il formato parametrico nominato dell'adapter postgres.
Non viene portato il suo cursore che interpolava `sql.SQL(...).format(...)`:
l'obiettivo Asqueel rimane una stringa SQL con un mapping separato.
Il metodo `PsycopgDriver.execute` e il cursore usato da Asqueel non cambiano.

La sonda confronta separatamente l'espansione con il metodo postgres3 originale.
Per la pipeline completa richiama il vero `execute` legacy con un cursore di
cattura, combinando quell'espansione e la regex originale del protocollo
postgres. **È una composizione dichiarata di due algoritmi legacy**, non il
risultato integrale dell'adapter psycopg2 invariato. Le SELECT d'integrazione
verificano poi il risultato sul driver effettivamente usato da Asqueel.

## Contratti recuperati e limiti conservati

- Gli operatori e i placeholder sono trattati sull'intero testo come nel legacy;
  non viene conservata la protezione aggiuntiva dello scanner per stringhe o
  commenti. La preparazione non valida il SQL.
- Un colon letterale si scrive `\:`. Nel SQL PostgreSQL parametrico, una
  percentuale letterale segue la convenzione `%%`; non viene raddoppiata
  automaticamente una seconda volta. I valori dei parametri non richiedono
  questi escape del testo SQL.
- I kwargs inutilizzati rimangono nel mapping come nel riferimento postgres /
  base SQLite. Un parametro ordinario mancante viene lasciato al driver:
  nessuna nuova diagnosi anticipata nel percorso testuale.
- Un valore ambiente assente diventa `None`; `workdate` usa il default legacy.
  Un input esplicito, anche `None`, mantiene la precedenza sull'ambiente.
  Sul nuovo albero lo snapshot resta quello catturato durante la pianificazione.
- Le collection sono `list`, `tuple`, `set`, come nei metodi portati. Non sono
  aggiunti controlli di tipo per IN o una nuova gestione della posizione scalare.
- Su PostgreSQL la regex legacy dei vuoti riconosce il campo qualificato prodotto
  dal compilatore (`"t0"."campo" IN :valori`); non è stata estesa ad espressioni
  arbitrarie o al campo non qualificato del SQL manuale.
- **Le collisioni dei nomi generati sono conservate**, non corrette di nascosto:
  SQLite può sovrascrivere `ids0`, postgres3 può sovrascrivere `ids_0`.
  La proposta M1 di un allocatore che eviti collisioni non è stata introdotta.
  Sono presenti test espliciti e confronti con gli originali.

Il SQL testuale passato a `db.execute` usa questa preparazione. I controlli e
le protezioni del precedente compilatore strutturato restano nel suo percorso;
non certificano il comportamento del nuovo albero. Fetch/esecuzione sul nuovo
albero rimangono disabilitate: R3 non le abilita.

## Verifiche

- **100 confronti sul riferimento**, senza differenze: preparazione comune,
  operatori, valori, Unicode, cast, percentuali e collection. Oracle portabile
  generato solo dagli originali in `tests/oracles/legacy_r3.json`.
- **800 confronti sugli otto snapshot**. Gli snapshot `legacy`, `v3_merged`,
  `v4`, `simplify`, `next` coincidono in tutti i casi. `compound`, `v2`, `v3`
  hanno quattro differenze ciascuno: due cast PostgreSQL e due traduzioni dei
  booleani SQLite. Il port segue le correzioni già presenti nel riferimento,
  senza prendere il comportamento dai branch più vecchi.
- **Cinque prove originali di adapter passate**: `TestSqlDbAdapter.test_sqltext`
  e i quattro metodi PostgreSQL di `TestPrepareSqlTextDoubleColon`.
  Il setup originale di quest'ultima classe importa anche MySQLdb, non presente
  nel runtime congelato: la sonda usa gli stessi corpi dei test con il solo
  adapter PostgreSQL, senza modificare i test originali né simulare MySQL.
- **24 verifiche d'integrazione passate**, su SQLite in memoria e PostgreSQL
  locale: IN/NOT IN, vuoti e NULL, nomi Unicode, bytes/escape, date/Decimal,
  cast, percentuali, ambiente e operatori.
- **148 SELECT native** sui 74 modelli senza differenze; 47 compilazioni mirate,
  delle quali 23 eseguite SQLite, con gli stessi risultati del legacy.
- I test offline vietano connessioni, esecuzione e un secondo passaggio nel
  formatter strutturato. I test di riuso controllano input e nomi dei binding.

I 100 confronti includono casi di sola preparazione che possono generare SQL
non eseguibile, come nel legacy. Non sono 100 esecuzioni riuscite. I kwargs
mantengono i tipi Python durante la preparazione; i driver applicano poi gli
adattamenti già esistenti. Per esempio SQLite restituisce testo da una SELECT
di un Decimal legato senza affinità di colonna; PostgreSQL restituisce numeric.

### Aspettative Asqueel riallineate

I test non richiedono più la rimozione dei kwargs inutilizzati o un errore del
compilatore per il parametro mancante. Le collisioni sono ora esplicite invece
di pretendere l'allocatore non concordato. Le prove SQL manuali applicano gli
escape legacy e la forma qualificata richiesta dalla regex dei vuoti; i casi
non trasformati restano visibili negli oracle e nei limiti sopra.
Non sono stati aggiunti skip o xfail per nascondere regressioni.

## Seguito

R4 deve eseguire l'accettazione integrata e misurare i costi dopo R1–R3, prima
di riprendere le relazioni. Non sono implementati qui JOIN, formule, sottoquery,
options di lettura o macro sul nuovo albero. Mixin e RuntimeModel rimangono separati.

## Evidenze riproducibili

- [Sonda dei confronti](probes/compare_legacy_r3.py).
- [Riferimento: risultati e casi](evidence/legacy-realignment-r3/legacy.json).
- [Corpi dei test originali PostgreSQL](probes/test_legacy_r3_original.py).
- [Esito dei test originali](evidence/legacy-realignment-r3/original-pg-tests.log).
- [Integrazioni finali](evidence/legacy-realignment-r3/integration-final.log).
- [SELECT native](evidence/legacy-realignment-r3/native/select-summary.json).
- [Suite completa finale](evidence/legacy-realignment-r3/full-tests-final.log).
- [Verifica finale e impronte](evidence/legacy-realignment-r3/verification.json).

Le evidenze R0–R2 restano storiche e immutate. Le impronte isolano R3 dal resto
del working tree già modificato. Nessun commit o push.
