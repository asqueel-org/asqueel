# test_invoice_pg: source nativa

74 modelli: sys 16, adm 40, invc 18. Ogni package è una cartella nel layout
dei package, dichiarata con `package(name, path=...)`:

```text
test_invoice_pg/
├── __init__.py          # source(): i tre package, requires, tipi
└── packages/
    ├── sys/
    │   ├── main.py      # Package.config_attributes()
    │   └── model/       # 16 moduli, uno per tabella
    ├── adm/
    │   ├── main.py
    │   └── model/       # 40 moduli
    │       └── _packages/sys/task.py   # contributo di adm a sys.task
    └── invc/
        ├── main.py
        └── model/       # 18 moduli
```

Ogni `model/<table>.py` contiene `Table.config_db(self, pkg)`, derivato dal
config_db originale indicato nel commento; non servono GenroPy o la source
legacy espansa. Il contributo di adm alla tabella `sys.task` sta in
`adm/model/_packages/sys/task.py` e gira dopo le tabelle di tutti i package.
Restano nella ricetta `requires('sys')` di adm e i tipi `money` e `perc` di invc:
`custom_type_<dtype>` di `main.py` vale solo per le `column`. Le options sono
ancora presenti e vengono espanse soltanto dal render.

```python
from examples.test_invoice_pg import source
from asqueel.configuration import build_database
from asqueel import SqlMigrationRenderer
from asqueel.projection import to_physical_builder

db = build_database(source())
try:
    structure = SqlMigrationRenderer(to_physical_builder(db.model)).render()
finally:
    db.closeConnection()
```

`INVC_STATE` è letto dal resolver esistente durante il render per il valore di
configurazione delle partizioni; non influenza il DDL. Non sono dichiarate
credenziali o connessioni al database applicativo.

[Esiti, differenze concordate e verifiche](../../docs/design/53-native-invoice-render-and-migration.md).
