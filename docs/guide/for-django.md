# For Django users

Moving from Django to Asqueel changes how you organize data access and how much
application infrastructure you supply. You work with a configured `db` and its
tables, select values with SQL expressions and model paths, and explicitly
complete transactions. The model can serve a script, service or custom UI.

Django's integration between models, forms and admin is a reason to keep Django
when those components already meet your needs. Asqueel exposes field metadata
for your own consumers; it does not supply replacements for Django's admin,
ModelForms or migration history. It is currently an alpha with a synchronous
PostgreSQL runtime. Check [Current status](limitations.md) before planning a port.

## Read the same related value

Suppose an invoice has a foreign key to a customer. In Django, a projected query
can use relation lookups without loading customer instances:

```python
rows = list(
    Invoice.objects.filter(customer__name='Ada')
    .order_by('id')
    .values('id', 'customer__name')
)
```

In Asqueel, assuming the relation is declared on `customer_id`:

```python
rows = db.table('sales.invoice').query(
    columns='$id, @customer_id.name AS customer_name',
    where='@customer_id.name = :name',
    name='Ada',
    order_by='$id',
).fetch()
```

Both ask the database for selected values across a relationship. The change is
the expression language: Django lookup keywords become SQL expressions with
model references and bound parameters. Asqueel returns dictionaries using the
projection names, here `id` and `customer_name`. Each `fetch()` executes again;
reusing the query does not reuse a QuerySet-style result cache.

If many screens and exports need `customer_name`, declare an alias column for
that path. Queries can then use `$customer_name`, and UI code can inspect its
label from the same model. SQL formula columns similarly give a calculation a
shared name. See [models](models.md) and [formulas](formulas.md).

The Django examples follow its official [query guide](https://docs.djangoproject.com/en/5.2/topics/db/queries/).

## Save through the table and choose the commit boundary

A Django row is commonly changed with `customer.name = ...` followed by
`customer.save()`. With Asqueel you read record data and pass the update to the
table:

```python
customer = db.table('sales.customer')
try:
    values = customer.record(101).output('dict')
    values['name'] = 'Ada Lovelace'
    customer.update(values)
    db.commit()
except Exception:
    db.rollback()
    raise
```

Editing the dictionary only changes local data. `update()` sends the write;
`commit()` makes the transaction durable. Django normally uses autocommit
outside `atomic()` blocks. Asqueel's application DB keeps a transaction open
until commit or rollback, including after reads. A successful write alone does
not commit. See [Django transactions](https://docs.djangoproject.com/en/5.2/topics/db/transactions/)
and the Asqueel [transaction guide](transactions.md).

Do not translate nested `atomic()` blocks mechanically: Asqueel does not currently
provide nested transactions or savepoints. `tempEnv()` changes query context;
it is not a transaction block.

## Share model information with your own application components

Django field declarations already carry information useful to forms and admin.
In Asqueel, configuration recipes collect the physical mapping, relationships,
formulas and linked UI metadata. Your components consume that configuration
through live tables and columns. This is useful when different application
components need the same definition of a field without depending on a Django
model class or request lifecycle.

Labels and formatting do not build a form or enforce permissions by themselves.
You implement those consumers and authorization rules. Schema evolution is also
a separate step: rendering configuration creates Python objects; the
[migration integration](migrations.md) compares supported structures and prepares
changes. It does not translate existing Django migration files.
