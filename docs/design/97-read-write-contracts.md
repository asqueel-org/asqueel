# 97 — Contratti del percorso gerarchico con le scritture

16 ottobre 2026. Worktree letture: `asqueel-read-path`, branch
`codex/core-single-read-path`. Percorso gerarchico unico attivo; verifica del perimetro letture completata.
Vedere [rapporto 98](98-single-read-path.md) per risultati e limiti della consegna.

## Confine concordato

Il fronte scritture costruisce autonomamente il DML sul modello gerarchico,
seguendo l'adapter legacy. Non richiede QueryPlan, Fragment né ResolvedModel.
Il lavoro letture non modifica le scritture e non deve mantenerle operative
negli stati intermedi. Nessuna compatibilità provvisoria. Le firme attuali
restano fino alla fusione; non anticipare la rinomina camelCase.

## Colonne X nelle letture con lock

Riferimento verificato in `gnrpy/gnr/sql/gnrsqldata/query.py:176`:
`self.bagFields = bagFields or for_update`.
`gnrsqldata/record.py:190` dichiara `bagFields=True` di default.

Il nuovo compilatore include quindi i campi X nell'espansione di `*` quando
`for_update=True`, anche se `bagFields=False`. La proiezione esplicita resta
esplicita: chiedere `$id` con lock non aggiunge tutte le altre colonne.
Una query senza lock conserva il comportamento ordinario di `bagFields`.
Le virtuali statiche rimangono incluse da `*`, secondo il legacy. Per ottenere
esattamente le colonne fisiche, il writer costruisce la proiezione dai nodi
in `table.model.columns`.

Regressione: `test_locked_star_includes_x_fields_as_legacy` in
`tests/object_tree/test_phase4_star_bag.py`, PostgreSQL e SQLite, con e senza
`bagFields`; prima del fix fallivano i due casi con `bagFields=False`.
Questa prova verifica la compilazione, non l'acquisizione effettiva del lock.

## Raccordi condivisi

- Il writer usa `table.model.columns`; le virtuali sono separate in
  `virtual_columns`. I nodi espongono `sqlname`, `dtype` e `attributes`.
- Il writer ricava le inverse dal ramo `relations`, filtrando `mode == 'M'`.
  `onDelete/onUpdate` applicativi sono distinti dagli attributi SQL.
- Il contenitore eseguibile comune è `CompiledQuery`, prodotto da
  `db.driver.prepare_sql(sql, kwargs, db.environment.snapshot())` e passato a
  `db.execute(compiled)`. `SqlCompiledQuery` è l'assemblaggio delle clausole SELECT.
- Il raccordo gerarchico di `record()`, `ignoreMissing` e output `dict`/`record`
  è implementato seguendo il legacy, conservando il default `bagFields=True`.
  Il record seleziona le colonne fisiche, senza virtuali statiche; non applica
  i filtri impliciti di query per default. Le colonne X diventano Bag in output record.
- Il lock SQLite compete a runtime/driver, sulla stessa connessione e transazione.
  Il caso di transazione già aperta è raccordato con un UPDATE senza righe;
  verificati anche contesa con seconda connessione e assenza di commit impliciti.
- I contratti di modello, relazioni e letture con lock sono verificati in questo
  worktree e nel commit di consegna del branch `codex/core-single-read-path`.
  Nessuna fusione con il fronte scritture è stata eseguita.
- I test letture si eseguono con `python -m pytest @tests/read_path/pytest.args`.
  Il manifest esplicita i test DML lasciati al writer; dopo la fusione va
  verificata la suite intera senza queste esclusioni.
