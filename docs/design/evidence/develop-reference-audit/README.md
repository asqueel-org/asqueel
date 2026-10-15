# Evidenze del censimento develop

Riferimento e classificazione nel [rapporto 95](../../95-develop-reference-audit.md).

- `commits.json`: estratto dal repository Git locale GenroPy con `rev-list`,
  `show` e `diff-tree`; tutti i 24 commit che toccano `gnrpy/gnr/sql` fra
  `ee1b8a43db` e `95da66ee64`, inclusi genitori, file e test aggiunti.
  Le liste di file/test comprendono l'intero commit, anche fuori da SQL.
  I cinque merge ripetono i test del fix incorporato: non sommarli come copertura.
  Separati i sette commit aggiuntivi trovati nel percorso `gnrpy/tests/sql`.
- `reference-checks.json`: controlli sul contenuto dei riferimenti, sincronizzazione
  dei compiler, integrità di src/tests durante l'audit, XML e link del rapporto.
- `probe.py`, `probes.json`: sonde diagnostiche sul checkout Asqueel corrente.
  Le eccezioni catturate sono risultati del censimento, non test superati.
  Nessun server DB richiesto: compilazione PostgreSQL senza esecuzione,
  esecuzione SQLite in memoria. Non costituiscono una baseline legacy eseguita.
- `tests.log`: riepilogo della suite mirata Asqueel esistente, 111 passati.

Comandi dalla radice Asqueel:

```sh
PYTHONPATH=src venv/bin/python docs/design/evidence/develop-reference-audit/probe.py
PYTHONPATH=src:../asqueel-migration/src venv/bin/python -m pytest \
  tests/object_tree/test_phase3_formulas.py \
  tests/object_tree/test_phase4_macros.py \
  tests/test_release_model_source.py \
  tests/test_release_composition.py -q -o addopts=
```

Gli oracoli precedenti non sono modificati. Nessun test GenroPy è stato
rieseguito in questo censimento, nessuna migrazione applicata, nessun commit o
push effettuato. Il confronto riguarda il checkout con le modifiche locali
preesistenti, non una distribuzione pubblicata.
