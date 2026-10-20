# 68 — Fetch con NamedList di Toolbox

14 ottobre 2026. Verificato e raccordato il porting pubblicato in
`genro-toolbox==0.18.0`. Nessun contenitore nuovo in Asqueel: i driver usano
direttamente `genro_toolbox.NamedList`.

## Verifica del porting

Installata la distribuzione PyPI nell'ambiente di Asqueel. Il modulo
`genro_toolbox/named_list.py` dichiara la provenienza da `GnrNamedList`, commit
legacy `fa35e5adfa6ad1b269f3a22a9b12c4c1ee6513ea`, con licenza Apache-2.0.
Confrontato il codice con `gnrpy/gnr/core/gnrlist.py:173`: accesso e modifica
per nome/posizione, slices, iterazione sui valori e interfaccia keys/items/get/update.

La differenza esplicita del port è la validazione del costruttore: posizioni
intere uniche e contigue, numero iniziale dei valori uguale a quello dei nomi.
Il percorso Asqueel soddisfa questo contratto; una riga DB-API incoerente non
viene accettata silenziosamente. L'indice resta condivisibile, senza copie
indipendenti per ogni riga.

Otto test `test_GnrNamedList*` del legacy sono rieseguiti sul riferimento
originale (**8/8**) e portati contro Toolbox (**8/8**). Cambia solo il riferimento
al costruttore, non le asserzioni. Provenienza e hash:
[legacy-tests.json](evidence/named-list-fetch/legacy-tests.json).
Questo verifica il contenitore pertinente ad Asqueel, non certifica l'intera
suite di Toolbox né ne riclassifica gli eventuali fallimenti noti.

## Raccordo dei driver e fetch

Nel legacy `SqlQuery.fetch()` restituisce le righe del cursore. Gli adapter
PostgreSQL/SQLite usano GnrNamedList o GnrDictRow derivato da esso; il driver
PostgreSQL psycopg3 usa direttamente GnrNamedList con l'indice del cursore.
Riferimenti: `gnrsqldata/query.py:241`, `adapters/gnrpostgres3.py:301`,
`adapters/gnrsqlite.py:82`, `adapters/_gnrbaseadapter.py:1631`.

In Asqueel entrambi i driver delegano al medesimo `drivers/result.py`:

1. verificano nomi unici e corrispondenza dei metadati **prima di fetchall**;
2. costruiscono un solo indice nome → posizione per il risultato del cursore;
3. creano le righe NamedList con quell'indice e conservano rowcount/metadati.

`query.fetch()`, `query.execute().rows`, SQL diretto, query già compilate e DML
RETURNING espongono quindi lo stesso tipo su PostgreSQL e SQLite.
`QueryResult.rows` è annotato `list[NamedList]`. Non si aggiungono sottoclassi,
wrapper di compatibilità, uguaglianza speciale con dict o un secondo fetch.
I codec dei valori SQL restano quelli dei rispettivi driver.

`record.output('dict')` conserva il proprio contratto: converte esplicitamente
la riga a dict prima della copia del record. Questo preserva anche i percorsi
di aggiornamento ordinario e gli hook che lavorano su record mapping.

## Comportamento pubblico

```python
rows = table.query('$id,$name', order_by='$id').fetch()
row = rows[0]
assert row['id'] == row[0]
row['name'] = 'Modifica locale'
assert row[1] == 'Modifica locale'
row[1] = 'Altra modifica'
data = dict(row)
```

Le modifiche sono locali, non scrivono sul DB. Ogni fetch riesegue la query e
produce righe e indici nuovi. La membership riguarda i nomi; l'iterazione
riguarda i valori. L'uguaglianza segue list, non dict. Per confronti o JSON
con chiavi esplicite si usa `dict(row)` oppure `[dict(row) for row in rows]`.
Il JSON della NamedList stessa è un array, come per una lista.

L'aggiunta di un nome locale estende l'indice condiviso del cursore. Le altre
righe possono restare fisicamente più corte, con None per l'accesso al nuovo
nome fino all'assegnazione. Operazioni strutturali di lista non riallineano
l'indice: è il comportamento del contenitore legacy, non un nuovo contratto
di tabella modificabile. Nessun calcolo pyColumn viene abilitato da questo passo.

## Verifiche e documentazione

- **8 test legacy** del contenitore superati sul legacy e su Toolbox.
- **10 prove di integrazione**, cinque per dialetto: tipo esatto, accesso e
  modifica per nome/posizione, slices, iterazione, aliases, NULL, indice condiviso,
  colonne locali, copie, JSON, fetch ripetuti, metadati vuoti, SQL diretto,
  RETURNING, record dict e nomi duplicati rifiutati.
- Aggiornati i confronti delle regressioni usando esplicitamente dict(row),
  conservando valori attesi e verifiche di cardinalità. Le prove del nuovo
  contratto verificano direttamente NamedList, senza conversioni che ne
  nascondano il tipo. Nessun test scartato per il cambio di contenitore.
- Conservata la verifica preesistente che impedisce fetchall su metadati errati;
  rollback, chiusura del cursore e lifecycle di scrittura restano coperti.
- Dipendenza minima portata a Toolbox 0.18.0 e rigenerati i lock core/routes/asgi;
  esempi eseguibili, README e guide riallineati al risultato effettivo.

Suite completa: **1940 superati, 13 saltati**; nove esempi documentali rieseguiti.
Ruff, mypy e Sphinx strict superati. Comandi ed esiti statici/documentali
nel [riepilogo](evidence/named-list-fetch/verification.json).
Query concatenate, operatori, RuntimeModel e postprocessing Python restano
nel perimetro già deciso; questo incremento riguarda il contenitore dei risultati.
