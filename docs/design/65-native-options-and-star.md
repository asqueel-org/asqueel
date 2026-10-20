# 65 — Options native, filtri impliciti ed espansione di `*`

14 ottobre 2026. Chiusura del passo 2 del piano 56, nel perimetro delle
letture: modello già renderizzato → piano SELECT → SQL e kwargs.
Nessuna nuova sintassi di configurazione, macro, provider o resolver.

## Riferimento legacy

Snapshot e commit restano quelli dell'inventario del rapporto 59.

- `gnrsqlmodel/table.py:396,479`: `static_virtual_columns` e `starColumns`.
  Fisiche in ordine di dichiarazione, poi virtuali statiche. Le fisiche X
  richiedono `bagFields=True`; le virtuali statiche X sono sempre incluse.
- `gnrsqldata/compiler.py:744,969–989`: delega a `starColumns`, filtri della
  tabella root combinati in AND, cancellazione logica `IS NULL`, draft
  `IS NOT TRUE`, modalità `_isdeleted`. Non propaga questi filtri ai JOIN.
- `gnrsqltable/columns.py:72`: partition corrente, insieme ammesso e fallback
  `__allowed_partition`. La option nativa dispone invece di un solo `value`:
  non sono stati importati implicitamente tutti questi comportamenti.
- v2: stesso filtro root a `compiler.py:1265–1290`; v3/v3_merged/v4 mantengono
  questo percorso (v4:1395–1419), nonostante il refactor dei JOIN. La delega a
  `starColumns` è conservata anche in simplify e next. Il branch compound usa
  ancora il modulo monolitico `gnrsqlmodel.py:1349`, con la stessa selezione
  fisiche/statiche. Nessun secondo algoritmo di espansione introdotto.

I riferimenti e gli hash AST sono in
[evidence/native-options/legacy-comparison.json](evidence/native-options/legacy-comparison.json).
La corrispondenza AST dei test portati è nel manifest
`tests/native_formulas/legacy-options-manifest.json`.

## Decisione esplicita sulla partition nativa

L'utente ha confermato durante questo incremento:

- `value` è il solo valore corrente **scalare**, anche risolto dagli esistenti
  EnvResolver/BagCbResolver durante il render;
- valore presente: uguaglianza con parametro, mai interpolazione nel SQL;
- `None`: nessun filtro se `required=False`, errore se `required=True`;
- `ignorePartition=True` disattiva il filtro; una option disabilitata non filtra;
- insiemi di valori ammessi rinviati. Dict/list non diventano implicitamente
  policy `allowed`; nessuna chiave `current_*`/`allowed_*` viene inventata.

Zero, False e stringa vuota sono valori presenti. Questo differisce dal test
truthy di `getPartitionCondition` legacy: discende dal contratto scalare
confermato, non da un tentativo di riprodurre l'intero runtime partition.
Il valore nel modello è quello ottenuto al render, non viene rivalutato dal
compilatore. RuntimeModel e ciclo di scrittura della partition restano separati.
Il precedente contratto `x_partition`/`PartitionScope` conserva le sue regole,
compresa l'applicazione cumulativa di current e allowed: non viene riscritto.

## Raccordo implementato

`_parse_row_policies` legge anche i marcatori già prodotti da sys_fields:
`x_legacy_draftField` e `x_legacy_logicalDeletionField`. Nessuna inferenza dal
nome di una colonna. Dichiarazioni native e low-level incompatibili producono
un errore; marcatori equivalenti sono accettati. Si riusano `RowPolicies`,
validazione dei campi e filtri esistenti.

La partition nativa alimenta solo il percorso SELECT con i binding già
esistenti. Un alias come `invc.invoice.customer_state` usa il normale algoritmo
di risoluzione delle relazioni e riusa il JOIN. Il filtro della root non
attiva quelli di customer. Le sottoquery mantengono i default legacy verificati
nel rapporto 61, con override espliciti e parametri isolati.

`projection` espande `*` con l'ordine fisiche/statiche. La convenzione legacy
`bagFields` attraversa query applicativa, piano e sottoquery. Colonne nominate
esplicitamente restano selezionabili. `RETURNING *` resta limitato a tutte le
fisiche, comprese le X. Nessuna colonna statica non supportata viene scartata
silenziosamente. Poiché il record applicativo usa la stessa query, gli alias
che devono comparire nella sua proiezione predefinita devono essere statici.
Per i campi fisici X, record mantiene `bagFields=True` per default, come
`compiledRecordQuery` legacy (riga 1106); `bagFields=False` li esclude. Questa
distinzione evita di perdere dati nei record per effetto del nuovo wildcard.

Le altre options rimangono nel modello; questo incremento non attribuisce loro
nuovi filtri o hook. Subtable, condizioni ambientali SQL implicite, pkey e
ordine impliciti, wildcard per prefisso/percorso restano separati dal passo 2.
La modalità mark conserva i limiti già dichiarati su formule/aggregati.

## Verifiche

- **16 test portati dal legacy**, tutti superati sui due database. Otto su
  draft/mark/`*`, due sull'assenza di partition, sei su partition corrente e
  bypass. Nei sei test partition cambia solo la preparazione del valore:
  fixture con `INVC_STATE=NSW` al render, anziché currentEnv a query time.
  Query e asserzioni conservate: 399 customer NSW, 21 invoice NSW, 3200 customer
  con bypass o senza partition.
- Replay degli stessi corpi test disponibili negli snapshot: legacy **16/16**,
  next **16/16**, v3_merged **14/14**, v4 **14/14**, simplify **10/14**.
  In simplify falliscono due formule is_confirmed e due partition invoice
  tradotte come campo fisico state: difetti dello snapshot, registrati senza
  modificare il legacy. Non si dichiara un replay equivalente per i riferimenti
  privi di questi corpi test; il confronto degli algoritmi resta distinto.
- **43 nuovi test mirati di compilazione**: marcatori, alias di partition,
  default/override delle sottoquery, mangler distinti, riuso, valori mancanti,
  required, scalari falsy, risoluzione al render, collection rifiutate,
  option disabilitate, binding di testo SQL, statiche, X, alias statici,
  bagFields nelle sottoquery e DML RETURNING. Le prove sulle options bloccano
  esplicitamente le operazioni I/O dei driver.
- **148 prove sui dati**, una per ciascuna delle 74 tabelle su PostgreSQL e
  SQLite. Righe controllate con draft NULL/False/True e tombstone presente/assente;
  verificati filtri predefiniti, override e mark. DDL di test senza vincoli e
  senza hook; le prove riguardano la visibilità, non il ciclo di scrittura.
- Le fixture generiche delle formule ora hanno partition assente, come nel
  legacy; quelle dedicate risolvono NSW. Le gerarchie includono i marcatori
  fisici necessari. Due test unitari sono riallineati alla proiezione esplicita;
  l'alias richiesto dal record nel test applicativo è dichiarato statico.
  Nessuna asserzione sul valore dell'alias o sulla rilevazione dei cicli eliminata.

Sonda senza I/O dei **74 modelli su entrambi i dialetti**:
66 con cancellazione logica, una tabella con draft, due partition native.
Tutte le query con proiezione fisica compilano. `*`, sia con bagFields False
sia True, compila su **73/74**. Resta bloccata `adm.htmltemplate_atc`, che contiene
pyColumn statiche (`fileurl` è il primo errore). È un limite della famiglia
pyColumn ancora aperta, non dell'espansione del wildcard.

Riproduzione della sonda:

```sh
PYTHONPATH=src:../asqueel-migration/src:. venv/bin/python \
  docs/design/probes/native_options_coverage.py \
  --output docs/design/evidence/native-options/native-census.json
```

Suite completa: **1840 superati, 9 saltati**. Ruff, mypy e Sphinx strict
superati. Dettagli registrati nel riepilogo
[evidence/native-options/verification.json](evidence/native-options/verification.json).
