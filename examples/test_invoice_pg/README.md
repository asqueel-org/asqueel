# test_invoice_pg: source nativa

74 modelli: sys 16, adm 40, invc 18. Le dichiarazioni derivano dai config_db
originali indicati nei commenti; non servono GenroPy o la source legacy espansa.
Le options sono ancora presenti e vengono espanse soltanto dal render.

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
