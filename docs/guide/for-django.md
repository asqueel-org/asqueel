# For Django users

Django describes data with Model subclasses and exposes queries through managers
and QuerySets. Fields also carry information used by forms and the admin.
Asqueel puts data declarations and linked UI metadata in configuration, then
renders a live database/table graph. See Django's official
[model guide](https://docs.djangoproject.com/en/5.2/topics/db/models/).

## Translate the model and query vocabulary

| Django concept | Asqueel concept |
|---|---|
| Model fields and Meta configuration | Table/column declarations and their effective configuration. |
| `Invoice.objects` | `db.table('sales.invoice')`. |
| Relation lookup such as `customer__name` | Declared path such as `@customer_id.name`. |
| Projecting selected values | `query(columns=...).fetch()`. |
| Row instance and `save()` | Record data followed by explicit `insert()` or `update()`. |
| Django application integration | Separate application-linked database services. |

Django QuerySets are lazy and provide projected-value APIs as well as model
instances. Asqueel also separates query construction from execution; a query
terminal compiles against the current environment and executes. This mapping
explains the concepts rather than equating every evaluation/caching rule.
See [Django's query documentation](https://docs.djangoproject.com/en/5.2/topics/db/queries/).

```python
rows = db.table('sales.invoice').query(
    columns='$id, @customer_id.name AS customer_name',
    where='@customer_id.name = :name',
    name='Ada',
    order_by='$id',
).fetch()
```

The path follows the relationship declared on `customer_id`. An alias or formula
column lets you name a reusable related value or calculation once in the model.

## Make the transaction difference explicit

Django normally uses autocommit outside an active transaction; `atomic()` defines
transactional blocks. Asqueel's application DB retains an implicit transaction
until explicit completion. See [Django transactions](https://docs.djangoproject.com/en/5.2/topics/db/transactions/).

```python
customer = db.table('sales.customer')
try:
    customer.insert({'id': 101, 'name': 'Ada'})
    customer.insert({'id': 102, 'name': 'Grace'})
    db.commit()
except Exception:
    db.rollback()
    raise
```

Do not assume that a successful insert is already committed. Select a named
connection when you need independent transactional work, and manage its completion
separately. Environment scopes select context; they are not transaction blocks.

## Separate application services from the database model

Asqueel's standalone database can be used by scripts, jobs or services.
Application integration supplies resources, localization, policies and events.
UI consumers can use labels and other column metadata without making a web
request object a requirement of the SQL compiler.

Rendering configuration builds objects; it does not apply a database migration.
Inspect and apply structural changes through the
[migration integration](migrations.md). Continue with [models](models.md),
[row policies](row-policies.md) and [hooks](hooks.md).
