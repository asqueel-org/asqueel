# Dialetti dati e confini del compiler

Il compiler asqueel risolve nomi logici, formule, relazioni, parametri e metadati
in un `QueryPlan`. Il dialetto rende quel piano in `SqlStatement`; il driver
traduce i nodi parametro nel formato richiesto dalla libreria di connessione.
Una `Fragment` contiene stringhe SQL applicative, `Identifier` e `Parameter`
distinti: nessun componente deve cercare placeholder già formattati nel testo.

| Confine | Responsabilità | Esclusioni |
|---|---|---|
| Compiler comune | Modello, `$campo`, percorsi, formule, scope, alias e result metadata | Quoting SQL del backend, connessioni e formato psycopg. |
| `PostgresDialect` | Lessico SQL PostgreSQL, quoting identificatori, SELECT/DML e capability | Risoluzione asqueel, valore dei parametri, connessioni, migrazioni DDL. |
| Driver | Binding concreto, connessione/esecuzione e convenzioni della libreria | Interpretare nuovamente il DSL o inventare relazioni. |
| Provider catalogo | Introspezione read-only e rapporto di fedeltà del modello importato | Migrare o cancellare oggetti. |
| sqlmigration | Struttura fisica, confronto, pianificazione e applicazione DDL | Runtime delle query e metadati UI. |

## Dialetto PostgreSQL

`asqueel.dialects.postgres.PostgresDialect` implementa il protocollo
`DataDialect`. È l'unico dialetto dati fornito in questa versione; l'esistenza
del protocollo non implica supporto runtime per SQLite o altri backend.

Le capability predefinite sono `select`, `insert`, `update`, `delete`,
`returning_insert`, `returning_update`, `returning_delete`, `left_join`, `limit`,
`offset`, `default_values`. La costruzione con
`PostgresDialect(capabilities=frozenset(...))` permette un sottoinsieme
esplicito, utile per verificare i rifiuti senza emulazioni. Non si possono
abilitare nomi di capability sconosciuti.

`render(plan)` accetta esclusivamente piani con `dialect='postgresql'` e genera:

- SELECT con proiezioni esplicite e alias, LEFT JOIN, WHERE, ORDER BY,
  LIMIT/OFFSET, compresi gli zeri.
- INSERT con assegnazioni oppure DEFAULT VALUES.
- UPDATE con almeno un'assegnazione e predicato esplicito; DELETE con predicato
  esplicito. `TRUE` è la scelta deliberata per tutte le righe.
- RETURNING per ciascuna operazione DML, se la relativa capability è abilitata.

Anche per piani costruiti direttamente, il dialetto termina con newline i
commenti di linea finali di ogni frammento prima di aggiungere alias, separatori
e clausole. Un commento in una proiezione o assegnazione non può quindi
assorbire FROM o WHERE. Il piano originale non viene modificato.

Piani incoerenti, alias duplicati, parametri mancanti, predicati vuoti o fatti
solo di commenti, DML con join/paginazione e operazioni non supportate falliscono
prima dell'esecuzione. I metadati `ResultColumn` del piano attraversano il
dialetto senza interrogare nuovamente il modello.

`quote_identifier` raddoppia soltanto le virgolette doppie e racchiude il nome
fra virgolette. Non trasforma `%`: l'eventuale escape appartiene al formatter
del driver. Nomi vuoti, NUL e nomi oltre 63 byte UTF-8 sono rifiutati, evitando
la troncatura implicita di PostgreSQL. Il limite comprende i byte, non il numero
di caratteri. I normali identificatori della facciata preesistente mantengono
la stessa forma SQL finale dopo la preparazione del driver.

`tokens(expression)` protegge stringhe SQL normali e `E'...'`, identificatori
quotati, dollar quote e commenti a blocchi annidati. Espone separatamente il
cast `::` come `operator` e i commenti `--` come `line_comment`: il compiler
comune può preservarli senza incorporare quelle regole PostgreSQL. Il token
`field` per `$"nome"` indica un confine lessicale; la risoluzione effettiva
della colonna rimane nel compiler. Questo scanner non è un parser SQL completo
né rende sicuri frammenti SQL non affidabili.

## Catalogo e migrazioni: sovrapposizione attuale

L'introspezione nativa attuale (`inspect_postgres` e provider PostgreSQL)
conserva dati necessari al modello e alle verifiche di fedeltà: tipi originali,
collazioni, sequence, PK/FK, indici, RLS, oggetti non gestiti e warning. Il reader
PostgreSQL di sqlmigration legge anch'esso cataloghi, ma restituisce la sua
struttura fisica normalizzata. I due risultati hanno scopi differenti e non
sono intercambiabili senza dimostrare quali informazioni sopravvivono.

`to_physical_builder` è oggi il passaggio esplicito dal modello risolto alla
grammatica usata da `SqlMigrationRenderer`: applica i nomi fisici, rifiuta
modelli incompleti e mantiene le limitazioni descritte in
[native-model.md](native-model.md). Il dialetto dati non importa il migratore
e non sostituisce né duplica la sua generazione DDL.

L'interfaccia `CatalogProvider` permette di isolare questa lettura dietro
`inspect(connection, schemas, *, ui=None) -> ImportResult`. Per un eventuale
riuso del reader di sqlmigration occorrerà prima verificare, con test di
contratto, la conservazione di tutti i dati oggi usati dai controlli della
proiezione. Se il reader non espone un'informazione, il provider deve
arricchirla o segnalarla; non cancellare il controllo. L'implementazione di
altri provider e la riorganizzazione del repository sqlmigration restano fuori
questa consegna.

## Verifiche

I test in `tests/adapter_dialect` costruiscono direttamente `QueryPlan`, senza
model resolver, database né driver: controllano SQL strutturato, token,
parametri, metadati, capability e rifiuti. I test del compiler e del driver
verificano separatamente la composizione dei confini e la compatibilità del
risultato finale. Le prove PostgreSQL del runtime restano necessarie per
certificare l'esecuzione; il successo dei soli test di rendering non la implica.
