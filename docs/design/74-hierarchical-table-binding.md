# 74 — Collegamento della tabella operativa al modello gerarchico

14 ottobre 2026. Il nuovo albero costruisce le coppie DbTableObj ↔ SqlTable
e può essere associato al SqlDatabase esistente. Il compilatore non viene
adattato né costruito per questo percorso. Il renderer `objects` resta il default.

## Contratto legacy verificato

Riferimento: `fa35e5adfa6ad1b269f3a22a9b12c4c1ee6513ea`:

- `gnrsqlmodel/obj.py`, init: creazione dell'oggetto operativo prima dei figli;
- `gnrsqlmodel/table.py`, _getMixinObj: conserva SqlTable in `.dbtable`;
- `gnrsql/query.py`, table: restituisce `model.table(...).dbtable`;
- `gnrsqltable/table.py`, model/db/pkg: collegamenti al modello e al database;
- `gnrsqltable/columns.py`, column: restituisce `self.model.column(...)`.

La [sonda eseguibile](probes/test_legacy_table_binding.py) verifica direttamente
questi contratti sul legacy: 75 tabelle originali, identità delle colonne,
percorso relazionale e ordine di costruzione. SQL e socket bloccati; nessun
metodo applicativo o compilatore Asqueel usato come oracolo.

## Raccordo implementato

DbTableObj.doInit crea una sola SqlTable, prima di costruire le colonne.
Il costruttore riconosce il modello gerarchico e non legge figli né relazioni
ancora incompleti. Non crea SqlColumn/SqlRelation separati: columns,
virtual_columns, indexes, options e relations sono quelli del modello, esposti
dal fallback già concordato. `column()` delega al modello anche per alias e
percorsi `@`, mantenendo la semantica dell'AliasColumnWrapper esistente.

SqlDatabase accetta il DbModel già costruito. Il collegamento non ricostruisce
tabelle, non converte in ResolvedModel e non crea un secondo registro di
oggetti operativi: `table()` raggiunge la `.dbtable` del nodo strutturale.
Un modello può essere associato a un solo database, anche dopo la chiusura
di quest'ultimo. Un render nuovo produce oggetti indipendenti.

Il collegamento aggiorna `model.db` al database operativo: tutti i nodi
strutturali lo raggiungono tramite il modello; la tabella operativa legge
lo stesso proprietario. La dichiarazione db costruita offline resta conservata
internamente in `model._database` e la source resta in `model.src`.
Il riferimento interno non è una nuova grammatica o API applicativa.
La configurazione delle connessioni continua a essere il ConfigHandler esistente.

Prima del collegamento sono disponibili struttura e `.dbtable`, ma l'accesso
al database operativo della SqlTable solleva UnsupportedFeatureError.
Dopo il collegamento valgono queste identità:

```python
table = db.table('invc.customer')
assert table is db.model.table('invc.customer').dbtable
assert table.model is db.model.table('invc.customer')
assert table.db is table.model.db is db
assert table.columns is table.model.columns
assert table.relations is table.model.relations
assert table.column('id') is table.model.column('id')
assert db.table('invc.invoice').column('@customer_id.id') is table.column('id')
```

Per esercitare il raccordo si usa il costruttore SqlDatabase già esistente.
Questo esempio interno riprende l'helper di configurazione posseduta usato
dal renderer corrente; non introduce una nuova firma della grammatica:

```python
from asqueel import SqlDatabase
from asqueel.configuration import _owned_handler
from examples.test_invoice_pg import source

recipe = source()
config = _owned_handler(recipe)
model = recipe.render(mode='objects_tree')
db = SqlDatabase(model=model, config=config)
try:
    customer = db.table('invc.customer')
    query = customer.query(columns='$id', where='$id = :customer_id', customer_id='example')
    assert query.table is customer
finally:
    db.close()
```

## Confini e lavoro successivo

- Query intent disponibile; compiled, fetch e count rifiutati esplicitamente:
  manca il raccordo del compilatore al nuovo modello e al ramo relations.
- Record e scritture rifiutati prima di hook, preparazione SQL o connessioni.
  La API corrente `relation()` che restituisce SqlRelation non viene emulata:
  si navigano la Bag relations e `column('@relazione.campo')` del legacy.
- Il nuovo percorso non applica x_table_class o mixin. Raccolta dei contributi,
  precedenze, override, namespace e RuntimeModel restano da decidere.
- Il renderer alternativo continua a restituire il modello offline: non si
  sostituisce ancora il percorso di costruzione predefinito di AsqueelDb.
- La proiezione JSON migration, ancora aperta a questo passo, è stata poi
  completata nel [rapporto 75](75-hierarchical-migration-json.md).
- Driver e gestione connessioni restano quelli esistenti. Il raccordo non
  certifica l'esecuzione di query generate dal nuovo modello.

Queste limitazioni sono esplicite: il vecchio percorso resta disponibile per
compilazione ed esecuzione e mantiene i suoi SqlColumn/SqlRelation correnti.

## Verifiche

- Tre prove sul legacy originale: 75 tabelle, accesso relazionale e lifecycle.
- Ottanta nuovi test: 74 identità native e sei prove di costruzione,
  collegamento, proprietario unico, errori di configurazione, confini operativi
  e indipendenza dal renderer corrente. Connessioni ed execute bloccati.
- Aggiornata la precedente prova della tabella vuota: ora verifica la presenza
  della `.dbtable` scollegata, mantenendo l'assenza di un database esecutivo.
- Suite completa: **2.222 superati, 13 saltati**, incluse le integrazioni
  PostgreSQL e SQLite. Ruff superato sui file Python interessati; mypy superato
  sui 55 file sorgenti. Diff del compilatore identico prima e dopo il lavoro.

[Comandi e impronte](evidence/table-binding/verification.json),
[suite](evidence/table-binding/suite.log),
[legacy](evidence/table-binding/legacy.log).
