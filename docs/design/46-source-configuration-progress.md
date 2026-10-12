# 46 — Primo incremento della source di configurazione

12 ottobre 2026. **P1 in corso**, piano 44. Nessun incremento della versione
0.5.2, tag o pubblicazione: questo report non annuncia la release 0.6.0.

## Implementato e verificato

- Package logici separati dagli schemi fisici; catalogo e validatore vedono
  anche le tabelle dichiarate nei package.
- Contenitori singleton idempotenti; dichiarazioni di package e schema
  completabili. Su package, anche tabelle e colonne accettano contributi.
- `pkg.table(...)`, `tbl.column(...)`, costruttori virtuali già presenti,
  composite e indici instradano verso gli stessi contenitori interni.
  Gli attributi della tabella comprendono `name_long`, `name_short`,
  `name_plural` e `caption_field`.
- `colgroup(...)` distribuisce default e ordine alle colonne senza duplicarle;
  ripetere una dichiarazione conserva gli override espliciti precedenti.
- Options con firme chiuse e controllo del livello: metadata, context,
  requires, type, macro, sys_fields e driver. I payload sys_fields distinguono
  bool e dict, controllano le chiavi e consentono soltanto `id.type='uuid'`.
  Sono dichiarazioni: non espandono campi e non generano chiavi.
- Contributi nominati sul builder e ricette `parents` ordinate: conflitto
  nello stesso contributo, override successivo, merge per chiave dei dict
  supportati, nessuna riapplicazione dei default omessi, `None` esplicito e
  `reset` conservato attraverso i livelli. Sorgenti del chiamante copiate.
- Connessioni nominate con database fisico o DSN e options del driver tipizzate
  per PostgreSQL/SQLite. Selezione per nome, errore su nomi sconosciuti nel
  nuovo profilo, niente scelta implicita del database quando manca `main`.
  Ricette 0.5.x con `connection(name=<database>)` restano leggibili.
  Il dict legacy `connection(options=...)` viene normalizzato in driver options
  sulla copia posseduta dalla configurazione; il chiamante resta invariato.
  Due database SQLite distinti verificano la selezione effettiva in esecuzione.
- Costruzione e replay della source non risolvono i segreti. La lettura delle
  impostazioni risolve i resolver: un valore mancante non ripiega sul nome
  logico o sul default della firma.
- Source autonoma e montata equivalenti per package, schema, options,
  connessione e gruppi. Grammatica generata aggiornata.

Il modello risolto e il renderer migrations rifiutano esplicitamente una
source con nuovi package/options del modello (escluse quelle amministrative
delle connessioni): il vecchio percorso non deve produrre un
JSON vuoto o incompleto ignorando le nuove dichiarazioni. Il blocco è
temporaneo e va sostituito dal percorso P2–P6, non eliminato isolatamente.

## Verifiche

Suite completa, comprendente le fixture PostgreSQL locali e SQLite:
**919 passati, 1 skip**, 17,81 secondi. Baseline P0: 876 passati, 1 skip;
43 nuove prove fra source, connessioni e composizione. L'ultima correzione alla
persistenza di reset nella ricomposizione è verificata anche rieseguendo i
sette test di composizione dopo la suite. Nessuna connessione
all'istanza applicativa `test_invoice_pg`.

Ruff: nessun errore. Mypy: nessun errore su 41 file sorgente. `git diff --check`
pulito. Ambiente di audit e comando della suite come nel report 45; resta da
riallineare pytest al requisito >=8.4 prima della distribuzione.

Il contratto storico `test_explicit_collections_are_the_only_authoring_grammar`
contraddiceva la scelta successiva di `tbl.column(...)`. È aggiornato per
verificare l'equivalenza della dichiarazione diretta con la struttura interna,
conservando le verifiche di contenimento ancora valide; non è stato saltato.

## Residui prima di chiudere P1

1. Completare le firme comuni e le regole dei nomi della source del 42;
   completare l'inventario delle forme legacy traducibili. Le due forme delle
   driver options sono alternative prima della normalizzazione, senza
   precedenze implicite fra dizionari.
2. Completare l'inventario eseguibile dei casi di composizione: metadati
   annidati per namespace, cambi di tipo di nodo e payload incompatibili
   fra ricette, diagnostica di provenienza e disattivazione delle opzioni.
3. Rivedere l'intero diff P1 prima del commit di chiusura, poi procedere agli
   oggetti P2 e al registro di provider. Le options avanzate hanno la propria
   espansione in P5; dichiararle non ne certifica il funzionamento.

Restano integralmente i gate P6 (modello+migrations su tutte le 75 tabelle),
P9 (operazioni e comportamenti) e P11/P12 (distribuzione/pubblicazione).
