# For SQLAlchemy users

The largest change from SQLAlchemy ORM is what happens to the data you fetch.
Asqueel returns projected rows and provides table operations for writes. You do
not attach returned objects to a Session, track their dirty state or flush an
object graph. Relationships, reusable calculations and field metadata belong
to a shared configuration model.

This suits applications organized around queries, explicit commands and shared
model metadata. If your application relies on an identity map, relationship
loading strategies or persistence cascades, keeping SQLAlchemy ORM avoids
reimplementing those behaviors. Asqueel's current alpha has a synchronous
PostgreSQL runtime and a smaller implemented query surface; review
[Current status](limitations.md) before planning a port.

## Fetch the values a caller needs

For mapped SQLAlchemy classes with an `Invoice.customer` relationship, a
projection can look like this:

```python
from sqlalchemy import select

stmt = (
    select(Invoice.id, Customer.name.label('customer_name'), Invoice.total)
    .join(Invoice.customer)
    .where(Invoice.total >= 100)
    .order_by(Invoice.total.desc())
)
rows = session.execute(stmt).mappings().all()
```

With an Asqueel relation declared on `customer_id`:

```python
rows = db.table('sales.invoice').query(
    columns='$id, @customer_id.name AS customer_name, $total',
    where='$total >= :minimum',
    minimum=100,
    order_by='$total DESC',
).fetch()
```

Both queries choose a projection. In Asqueel the path supplies the join from
the model, and SQL expressions supply the filter and ordering. Values use
parameters; the returned rows are dictionaries. An alias column can name the
customer path once, while a formula column can centralize a calculation used
by several queries. See [queries](queries.md) and [formulas](formulas.md).

This is a comparison with explicit projections. SQLAlchemy can also load mapped
entities and relationships; the Asqueel result above does not create that object
graph. See the official [SQLAlchemy SELECT tutorial](https://docs.sqlalchemy.org/en/20/tutorial/data_select.html).

## A write happens at the table call

With SQLAlchemy ORM, changing a tracked attribute marks work for a later flush;
a flush can also happen automatically before a query or commit. In Asqueel:

```python
customer = db.table('sales.customer')
try:
    values = customer.record(101).output('dict')
    values['name'] = 'Ada Lovelace'
    customer.update(values)  # Execute UPDATE now, inside the transaction.
    db.commit()
except Exception:
    db.rollback()
    raise
```

Changing `values` alone schedules nothing. `update()` executes SQL and
`commit()` completes the transaction. There is no implicit flush of other
modified dictionaries and no automatic persistence of related objects. A record
reader keeps a snapshot until `refresh()`; ordinary query fetches execute again.

An Asqueel named connection owns an independent transaction, not an identity map.
Choosing another connection does not merge object state or coordinate commits.
Both libraries require deliberate transaction boundaries, but Session lifecycle
rules are not a substitute for Asqueel's [transaction contract](transactions.md).
See SQLAlchemy's [Session basics](https://docs.sqlalchemy.org/en/20/orm/session_basics.html).

## If you use SQLAlchemy Core

Explicit projections and writes will already be familiar. The difference is
what you build queries from: Core uses Python SQL expression objects; Asqueel
uses SQL expressions enriched with logical fields, relation paths and model
formulas. The same Asqueel model exposes labels and other UI metadata to
application components and supports layered configuration recipes.

Choose Asqueel when that shared model and expression language simplify repeated
application work. Core remains a natural choice when composable Python SQL
expressions and its established backend support are the main requirement.
Asqueel does not interpret every SQL construct or offer equivalent dialect
coverage. Start with [configuration](configuration.md) to see how its model is
built and [adapters](adapters.md) for backend boundaries.
