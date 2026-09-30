# For Peewee users

Peewee lets you put fields on Python model classes and build queries from those
fields. Asqueel moves the shared definition into configuration: the resulting
`db` exposes tables, relation paths, formula columns and UI metadata. The reason
to consider this change is reuse across application components, especially when
the same join, calculation or field description appears in many places.

For a small application whose model classes and explicit queries already cover
its needs, Peewee can remain the simpler fit. Asqueel adds a configuration and
model layer to learn. Its current alpha runs synchronously on PostgreSQL;
[Current status](limitations.md) lists its implemented query and runtime limits.

## Replace repeated joins with model paths

Given Peewee models where `Invoice.customer` is a foreign key to `Customer`, a
query for invoices and customer names can be written as:

```python
rows = list(
    Invoice.select(Invoice.id, Customer.name.alias('customer_name'))
    .join(Customer)
    .where(Customer.name == 'Ada')
    .order_by(Invoice.id)
    .dicts()
)
```

With the relation declared on `customer_id` in Asqueel:

```python
rows = db.table('sales.invoice').query(
    columns='$id, @customer_id.name AS customer_name',
    where='@customer_id.name = :name',
    name='Ada',
    order_by='$id',
).fetch()
```

Both examples return projected dictionaries. The difference is how you express
the query: Peewee field expressions become SQL expressions with `$field`,
`@relation.field` and `:parameter`. Asqueel resolves the path's join. For a
frequently used related value, an alias column lets callers use a local name
such as `$customer_name`; a formula column does the same for a calculation.

Peewee also supports model-instance results. Asqueel's `fetch()` returns
dictionaries and does not lazily fetch related objects when you read a value.
Ask for the related values in your projection. See the official
[Peewee query guide](https://docs.peewee-orm.com/en/latest/peewee/querying.html)
and Asqueel's [query guide](queries.md).

## Write explicitly and finish the transaction

A Peewee instance can be changed and saved with `save()`; Peewee also has explicit
update queries. With Asqueel you pass record data to its table:

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

Changing the dictionary does not save it. The table call executes SQL, while
commit makes the transaction durable. Asqueel's application DB retains an
implicit transaction across calls until you commit or roll it back, including
after reads. Establish that boundary in each job or service operation.

Peewee's `atomic()` supports nested blocks through savepoints; Asqueel currently
has no nested transaction or savepoint API. Do not port those blocks unchanged.
See [Peewee transaction management](https://docs.peewee-orm.com/en/latest/peewee/database.html#managing-transactions)
and Asqueel's [transactions](transactions.md).

## Let queries and UI consumers share field definitions

A configuration recipe can combine physical naming, relations, aliases,
calculations and labels. Application-specific recipes can contribute to that
model before the live database is built. A list view and an export can query
the same formula; a custom form can inspect the same field's label.

This is useful when keeping those definitions consistent is a substantial part
of your application work. It does not generate an interface: your UI code must
consume the metadata. Continue with [configuration](configuration.md) and
[formulas](formulas.md) for the declaration and reuse mechanisms.
