# For Peewee users

Peewee uses Model classes, fields and query objects; queries can return model
instances or projected dictionaries/tuples. Asqueel's usual entry point is a
database object whose tables and metadata come from configuration. See the
[Peewee model guide](https://docs.peewee-orm.com/en/latest/peewee/models.html)
and [query guide](https://docs.peewee-orm.com/en/latest/peewee/querying.html).

| Familiar idea | Asqueel expression |
|---|---|
| A model class representing a table | `db.table('sales.customer')`. |
| Model field expressions | `$name`, `$total`, and other model references in SQL. |
| Joining a declared related table | A path such as `@customer_id.name`. |
| Query projection | `query(columns='$id,$name').fetch()`. |
| Persisting a changed record | `table.update(record)` followed by transaction completion. |

```python
customer = db.table('sales.customer')
rows = customer.query(
    columns='$id, $name',
    where='$name ILIKE :pattern',
    pattern='Ada%',
    order_by='$name',
).fetch()
db.rollback()  # Finish this read-only transaction.
```

The main conceptual change is the role of configuration. Package contributions,
physical naming, relation paths, computed columns and UI metadata meet in the
same model. A live table exposes that model and its operations; editing returned
data does not automatically save it.

Use [transactions](transactions.md) to establish commit/rollback boundaries,
then [configuration](configuration.md) and [formulas](formulas.md) to move shared
model knowledge out of repeated query code.
