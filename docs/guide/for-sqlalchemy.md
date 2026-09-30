# For SQLAlchemy users

Start by distinguishing SQLAlchemy Core from its ORM. Core provides SQL and
schema constructs; the ORM adds mapped classes and a Session with identity-map
and unit-of-work behavior. This guide compares the ORM workflow with Genro SQL;
it does not imply that SQLAlchemy requires ORM mapping for every query.
See the official [SQLAlchemy architecture](https://www.sqlalchemy.org/features.html)
and [Session basics](https://docs.sqlalchemy.org/en/20/orm/session_basics.html).

## Translate the objects, not just the method names

| SQLAlchemy concept | Genro SQL concept |
|---|---|
| Table metadata and mapped-class declarations | Configuration recipe and resolved model. |
| Mapped entity class | Live table obtained with `db.table('sales.customer')`. |
| A mapped entity instance | Record data; use explicit table writes. |
| Relationship expressions | Declared relation paths such as `@customer_id.name`. |
| Session transaction | Transaction on the selected named DB connection. |
| SQL expression and bound parameter | SQL expression with `$field`, `@path` and `:parameter`. |

This is a conceptual mapping, not a mechanical API substitution. In particular,
a Genro SQL table object represents the table's operations and metadata, not a
Python class whose instances participate in an identity map.

## Query a projection

For a declared invoice/customer relation:

```python
invoice = db.table('sales.invoice')
rows = invoice.query(
    columns='$id, @customer_id.name AS customer_name, $total',
    where='$total >= :minimum',
    minimum=100,
    order_by='$total DESC',
).fetch()
```

The model supplies the relationship used by the query. An alias column can give
`@customer_id.name` a reusable local name; a formula column can give a related
aggregate a reusable identity. Choose the projected columns and result shape
explicitly when defining a service boundary.

## Write explicitly

SQLAlchemy's ORM tracks changes to mapped instances and flushes work through
its Session. Genro SQL table methods execute writes; commit concludes the
transaction. There is no need to wait for an object-state flush before the SQL
is sent. See [SQLAlchemy's unit-of-work description](https://docs.sqlalchemy.org/en/20/tutorial/orm_data_manipulation.html).

```python
customer = db.table('sales.customer')
record = customer.record(101).output('dict')
record['name'] = 'Ada Lovelace'
customer.update(record)
db.commit()
```

Changing `record['name']` alone does not update the database. Likewise, a cached
record reader is a snapshot and must be refreshed when you want another read.

## Keep the model above the dialect

The model is shared by the query compiler, introspection and application
metadata consumers. Backend-specific SQL belongs to the dialect or an explicit
SQL expression. UI metadata and package contributions belong to model
configuration, not to the connection driver.

An independent named connection has an independent transaction. It does not
provide object-session merging or a distributed commit. Start with
[configuration](configuration.md), [queries](queries.md) and
[transactions](transactions.md), then read [formulas](formulas.md).
