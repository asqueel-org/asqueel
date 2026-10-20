# 92 — Fetch e count sul nuovo albero

15 ottobre 2026. I terminali `query.execute()`, `query.fetch()` e `query.count()`
eseguono ora le letture compilate dal modello gerarchico. Nessuna nuova firma,
nessun nuovo contenitore di righe, nessuna modifica agli adapter o al compilatore.

## Riferimento legacy

`SqlQuery.cursor`, `fetch` e `count` in `fa35e5ad`, confrontati anche nei sette
snapshot sperimentali: [manifest](evidence/legacy-tree-terminals/legacy-terminals.json).
Il corpo di cursor e count è identico in tutti gli otto riferimenti, ignorando
le docstring. La sola differenza del corpo fetch è la chiamata `_decryptRows`
presente nel riferimento corrente e assente in alcuni snapshot precedenti.

Nel perimetro portato, fetch esegue la SELECT, materializza le righe e chiude il
cursore. Count esegue la query compilata in modalità count: legge il primo valore
quando c'è una sola riga e la prima colonna è `gnr_row_count`, altrimenti restituisce
il numero delle righe. È la stessa distinzione già verificata nel
[rapporto 91](91-legacy-tree-count.md).

Non sono portati incidentalmente multistore, pyColumn, decrittazione o conversione
automatica dei valori Bag. Restano i tipi e i risultati già forniti dai driver;
nessun postprocessore nuovo viene agganciato al fetch.

## Raccordo minimo

È rimosso il blocco che impediva l'esecuzione delle query gerarchiche.
`execute()` continua a delegare a `db.execute(self.compiled)` e `fetch()` restituisce
le righe di quel risultato. Per ogni chiamata si ricompila con l'ambiente corrente;
non si conserva una cache dei dati.

`count()` usa il risultato legacy quando il modello è gerarchico. Il ramo del
compilatore precedente continua a leggere la sua colonna `count`, senza cambiare
SQL o regole. Le particolarità legacy di LIMIT/OFFSET e delle proiezioni aggregate
restano quelle del rapporto 91, senza wrapper SQL aggiuntivi.

I due driver usano già `drivers.result.query_result`: un indice condiviso per
risultato e righe **Toolbox NamedList**. Restano accesso per nome e posizione,
mutabilità locale, indice condiviso tra righe dello stesso risultato e metadati
per risultati vuoti. Il driver SQLite chiude il cursore in finally; psycopg usa
il context manager del cursore. Non è stata aggiunta una seconda materializzazione.

Fetch e count passano dalla connessione e transazione del database proprietario.
Una chiamata invia una sola istruzione. Nessun commit implicito; le modifiche non
confermate sono visibili nella stessa transazione e rollback le annulla.
Le operazioni su query di un database chiuso falliscono prima di chiamare il driver.

Record, Selection e scritture sul nuovo albero restano nei confini precedenti.
Le chiamate verso molti continuano a essere riconosciute e rifiutate prima
dell'esecuzione: nessun handler `many_*` implementato.

## Verifiche

- Baseline dei terminali: **34 fallimenti e 8 passaggi**, prima del raccordo;
  i fallimenti erano il blocco esplicito di esecuzione sul modello gerarchico.
- Riusati i contratti NamedList esistenti sui due driver: nome, posizione,
  modifica, aggiunta locale di colonne, indipendenza fra fetch successivi,
  metadati e nomi duplicati. Non riusate le prove di scrittura fuori perimetro.
- Count semplice, dataset vuoto, GROUP BY, HAVING, DISTINCT, filtri, mark,
  LIMIT/OFFSET ed ambiente corrente, tutti sui due dialetti.
- Query riusata alternando fetch e count, relazioni verso uno e formule;
  una sola esecuzione per chiamata sulla stessa connessione; rollback dopo fetch.
- **40 invocazioni di corpi legacy già portati**, ora sulle vere SqlQuery del
  database gerarchico: count, options, partition, star, alias e formule SQL.
- **148 verifiche di visibilità**: i 74 modelli nativi su PostgreSQL e SQLite,
  inserimenti controllati, filtri draft/deleted e override, fetch e count reali.

Le fixture precedenti sono riusate solo per predisporre schema e dati confermati.
Il nuovo database apre la propria connessione: nessun wrapper di test esegue il
fetch o interpreta il count al suo posto. Le prove isolate di compilazione delle
fasi precedenti restano disponibili separatamente.

Evidenze: [baseline](evidence/legacy-tree-terminals/baseline.log),
[prove mirate](evidence/legacy-tree-terminals/focused.log),
[modelli nativi](evidence/legacy-tree-terminals/native.log),
[suite completa](evidence/legacy-tree-terminals/full-suite.log).

## Esito finale

**5.147 test passati, 21 skip, 2 xfail** (188,99 secondi), nessun fallimento inatteso.
I due xfail sono quelli già documentati sull'ordine di star per sys_fields.
Ruff e Sphinx con warning come errori passano; mypy conserva i due errori noti
in dialects/postgres.py, righe 127 e 367, senza nuovi errori.
JSON migration invariato sui 74 modelli. Le prove mirate comprendono 132 test
terminali/oggetti/NamedList e 188 test nativi. Nessun commit, bump o push.
