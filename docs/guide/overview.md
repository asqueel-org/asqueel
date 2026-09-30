# What is Genro SQL?

Genro SQL is a Python database layer for building applications around a shared,
declarative data model. The model describes tables, columns, relationships,
computed values and the metadata that application interfaces need. Genro SQL
turns that configuration into live database objects and compiles operations on
those objects into SQL.

The main object is `db`. Application code works through its tables:

```python
customers = db.table('sales.customer')
rows = customers.query(
    columns='$id, $name, @state_id.name AS state_name',
    where='$name ILIKE :search',
    search='Ada%',
    order_by='$name',
).fetch()
```

This reads customer names and the name of each customer's state. `$name` refers
to a column in the model, `@state_id.name` follows a declared relationship, and
`:search` binds a value separately from SQL. The compiler resolves the physical
table names and the join. You work with a database model without having to
write the join again wherever that relationship is used.

## What belongs in the model?

A column has an identity that applications can follow through several views:

- **Storage:** SQL name, type, size, key and database constraints.
- **Meaning:** relationships, aliases, formulas and application rules.
- **Presentation:** labels, formatting and other UI metadata, attached to the
  column or supplied by linked configuration.

An alias can expose a related value as a column of the table you are querying.
A formula can express a calculation, an existence check or a correlated total.
These definitions can be reused in filters, projections and ordering. A UI
consumer can inspect the same column metadata used by the data layer; it does
not need to maintain an unrelated description of the field.

Genro SQL supplies this information to applications. Rendering a form and
choosing its widgets belong to the application or UI framework.

## Configuration becomes an object graph

```mermaid
flowchart LR
    A["Configuration<br/>packages and application contributions"] --> B["Grammars<br/>validation and resolution"]
    B --> C["Live db<br/>tables, columns and relations"]
    C --> D["Query and write operations"]
    D --> E["Compiler, dialect and driver"]
    E --> F["Database"]
```

A configuration recipe declares the model. Cascading grammars define the
vocabulary of each part of that configuration, while package and application
contributions supply its values. Rendering resolves the contributions and
produces the live `db` object graph.

A live table is an object that knows how to query and change records. It is not
one record from that table. Query results and records carry data; changing a
returned dictionary does not silently schedule a database update.

The logical identity `sales.customer` is separate from its physical SQL name.
A deployment can use a schema, a table prefix or an explicit mapping without
requiring every query to adopt those physical names.

## SQL remains part of the language

Genro SQL combines SQL expressions with model references:

| Form | Meaning |
|---|---|
| `$amount` | A column of the current table. |
| `@customer_id.@state_id.name` | A path through declared relations. |
| `:minimum` | A bound value. |
| `:env_workdate` | A value resolved from the execution environment. |
| `#IN_RANGE(...)` | A Genro construct interpreted by the compiler. |
| `SUM($amount)` | An SQL expression using a model column. |

A `#NAME` construct can produce SQL, prepare parameters, resolve a contextual
reference or specify how a result should be decoded. Its meaning belongs to
the compiler; it is more than a text replacement convention.

Relation paths also support model navigation. The same field identity connects
query expressions, resolved metadata and related data. A collection relationship
has explicit cardinality and result shape: collections are not reconstructed
by an implicit `aggregateRows` pass over multiplied join rows.

## Transactions follow the work

The application API is synchronous. Operations on the selected named connection
share an implicit transaction until you commit or roll it back:

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

You can select an independent connection through `db.tempEnv(connectionName=...)`.
Each connection has its own transaction. Environment values also provide context
for queries and policies, such as the current business date or organization.
Partition scope, draft visibility and logical deletion are model concerns;
database constraints and application authorization retain their own roles.

SQL and related writes in hooks belong to a transaction. Deferred work around
commit has a different purpose from a hook that runs immediately after an INSERT.
The [transaction guide](transactions.md) explains those boundaries.

## Standalone use and application integration

The database layer can be used without a web application. An application-linked
layer connects it to package contributions, localization, resources, policy
services and events. A Genropy compatibility adapter supplies conventions of
legacy applications on top of that integration.

These are separate from the SQL dialect and driver. A dialect generates SQL
for a backend; a driver handles its connection, parameter binding and execution.
PostgreSQL is the primary database. Backend-specific features remain explicit,
so choosing another dialect does not imply that every PostgreSQL operation has
an equivalent there.

## Existing databases and schema evolution

You can approach the model from either direction: declare it in application
configuration, or inspect an existing database and enrich its physical model
with application meaning. Legacy package declarations provide another source
of model information through the compatibility integration.

Rendering a model does not apply DDL. Schema changes are planned and applied
through the separate `genro-sqlmigration` integration. The structural model
includes the distinction between tables, native views, database functions,
native triggers and physical partitions. Python hooks and native SQL triggers
have different execution boundaries and can coexist.

Logical subtables, application partition filters and physical database partitions
solve different problems. They should be chosen and declared independently.

## How it relates to other Python ORMs

The useful comparison is where each library places its main abstraction.
This table describes their usual entry points, not exclusive capabilities or
performance rankings.

| Library | Usual entry point | What to translate when learning Genro SQL |
|---|---|---|
| Genro SQL | A configured `db` and its live table/model graph. | Query model paths, keep shared metadata in configuration, and write records explicitly. |
| SQLAlchemy ORM | Mapped Python classes and a Session tracking object state. | Move from tracked row objects to table operations; keep transaction ownership explicit. |
| Django ORM | Model classes, managers and QuerySets integrated with Django. | Move field declarations into model configuration and distinguish the standalone DB from app services. |
| Peewee | Model classes, fields and query objects. | Use the database's table graph and model paths in place of class-based query expressions. |

SQLAlchemy also provides Core, which can be used without ORM object tracking;
Django and Peewee can return projected values rather than model instances.
There is overlap in capability. Genro SQL's particular emphasis is the shared,
extensible application model and its query language. See the official
[SQLAlchemy overview](https://www.sqlalchemy.org/features.html),
[Django model guide](https://docs.djangoproject.com/en/5.2/topics/db/models/)
and [Peewee query guide](https://docs.peewee-orm.com/en/latest/peewee/querying.html)
for those libraries' own descriptions.

Genro SQL is a natural fit when packages contribute to a model, related values
and calculations should be reusable as columns, and data and UI consumers need
shared metadata. A project built around tracked Python entity graphs, Django's
application stack or a small class-based mapper may prefer those corresponding
abstractions. No execution-speed advantage follows from this comparison.

## Choose your learning path

- [For Genropy users](legacy.md): familiar contracts and deliberate differences.
- [For SQLAlchemy users](for-sqlalchemy.md): tables, records and transaction ownership.
- [For Django users](for-django.md): model declarations, queries and app boundaries.
- [For Peewee users](for-peewee.md): translating a compact class-based data layer.
- [Core concepts](concepts.md), [quickstart](quickstart.md) and [tutorial](tutorial.md):
  learn the configuration-to-query workflow from the beginning.
