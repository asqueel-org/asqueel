# SQLite: two schemas, one application DB

From the repository root (with Asqueel and its migration extra installed):

```sh
export ASQUEEL_SQLITE_FILE=/absolute/existing/folder/example.db
asqueel register sqlite-demo ./examples/sqlite
asqueel db apply sqlite-demo
asqueel shell sqlite-demo
```

The migration adapter creates `example.db`, `example_contacts.db` and
`example_sales.db`. The relation between customer and invoice is logical;
SQLite cannot enforce a foreign key between attached files.

In Python, after migration (use unused IDs when rerunning):

```python
from asqueel import AsqueelDb

db = AsqueelDb('sqlite-demo')
try:
    db.table('contacts.customer').insert({'id': 1, 'name': 'Ada'})
    db.table('sales.invoice').insert({'id': 10, 'customer_id': 1, 'description': 'Example'})
    db.commit()
    rows = db.table('sales.invoice').query(
        columns='$id, @customer_id.name AS customer, $description'
    ).fetch()
    db.commit()
    assert rows == [{'id': 10, 'customer': 'Ada', 'description': 'Example'}]
except Exception:
    db.rollback()
    raise
finally:
    db.close()
```

SQLite units of work use `BEGIN IMMEDIATE`; finish each transaction before using
another named connection to the same files. This is not PostgreSQL row locking.
