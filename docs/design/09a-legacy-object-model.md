# Legacy configuration-to-object lifecycle audit

## Scope and source baseline

This is an internal architecture audit, not a proposal presented as existing API.
The question is how a SQL declaration becomes a live application object, not only
how a SELECT is compiled or a migration is rendered.

Verified legacy checkout: `/Users/gporcari/Sviluppo/Genropy/genropy`, HEAD
`fa35e5adfa6ad1b269f3a22a9b12c4c1ee6513ea`. The SQL, structure and application
sources cited below have no working-tree differences from that revision. Dirty
`projects/test_invoice` fixtures were not used. Earlier dossier references to
`e12f2ce54245e57e48371ae0f47e928e0d55b960` are a historical baseline, not the
revision used here.

Modern checkout: `asqueel`, HEAD `bf66bcacfeededc7f0ce82cd5c48f6437aa174df`.
References to modern code describe the working source at audit time; concurrent
public documentation edits do not affect the inspected implementation. Builders
observations use the installed `genro-builders` 0.27.0 source in
`/private/tmp/asqueel-v1-venv/lib/python3.12/site-packages/genro_builders`.
A sibling repository checkout is a separate baseline.

Source notation below: `legacy:` means a path relative to the legacy checkout;
`modern:` means a path relative to this repository; `builders:` means a path
relative to that installed package. Line references identify the implementation,
not only docstrings. This audit is a static source trace; it does not claim a
complete legacy application startup or compatibility test was executed.

## Main architectural finding

The legacy system deliberately has both a model object and an operational object
for each table. `DbTableObj` owns structural metadata and links into the model
hierarchy. Its `dbtable` is a `SqlTable` instance with CRUD/query behavior and
application mixins. Database lookup returns the stored operational instance.

The modern implementation already has declaration, validation, resolved
metadata, compilation, dialect rendering, driver formatting and synchronous
execution. It does **not** yet provide the same configuration-to-live-object
product lifecycle. `ResolvedModel.table()` returns a descriptor; `Database` does
not own a resolved model or a table registry. This is a missing composition and
runtime-object layer, not evidence that the compiler or execution driver must be
rewritten.

Sources: `legacy:gnrpy/gnr/sql/gnrsqlmodel/table.py:105`,
`legacy:gnrpy/gnr/sql/gnrsqltable/table.py:74`,
`legacy:gnrpy/gnr/sql/gnrsql/query.py:232`;
`modern:src/asqueel/contracts.py:86`, `:117`,
`modern:src/asqueel/runtime.py:20`.

## Concrete legacy lifecycle

### 1. Construct the database and mutable declaration source

`GnrSqlDb.__init__` creates its model through `createModel()`. `DbModel` holds the
database reference, creates `DbModelSrc.makeRoot()`, inserts the package-list
root, and initializes separate relation, mixin and deferred-callback registries.
At this point `model.obj` is `None`: the source and compiled object tree are
separate states.

Sources: `legacy:gnrpy/gnr/sql/gnrsql/db.py:149`, `:365`;
`legacy:gnrpy/gnr/sql/gnrsqlmodel/model.py:75`.

`DbModelSrc` inherits `GnrStructData`, itself a Bag subclass. Its `package()` and
`table()` methods create source nodes and collection containers. The underlying
`child()` routine constructs nested Bags, assigns tags and attributes, handles
paths and parent constraints. This is an executable declaration API over a Bag,
not a collection of Python ORM classes declared directly by users.

Sources: `legacy:gnrpy/gnr/sql/gnrsqlmodel/model.py:580`, `:589`, `:630`;
`legacy:gnrpy/gnr/core/gnrstructures.py:37`, `:46`, `:154`.

### 2. Discover package and table contributions

The application constructs `GnrSqlAppDb`, initializes each package's table-mixin
dictionary, registers the package and table mixins, broadcasts `onDbStarting`,
and invokes `db.startup()`.

Package loading gathers model contributions from the package, other packages'
`model/_packages/<package>` directories, plugins and custom model directories.
`loadTableMixinDict()` creates reusable mixin objects, applies base table mixins,
loads `Table` classes, and installs cross-package configuration and trigger
methods under package-specific suffixes. `configure()` creates the package
source and merges the package and custom `config_db.xml` documents.

Sources: `legacy:gnrpy/gnr/app/gnrapp.py:649`, `:686`, `:702`, `:713`, `:765`,
`:1052`.

This discovery and method-composition machinery is behavior beyond importing
column definitions. Extracting a schema from a package does not automatically
preserve the package's operational methods, trigger behavior or configuration
side effects.

### 3. Execute configuration callbacks before materialization

`startup()` calls `model.build()` and only then marks the database as started.
Within `build()`, table configuration runs before package configuration. Table
names are sorted within each registered package. For each mixin the order is:

1. `config_db(pkgsrc)` if present.
2. `config_db_<package_id>(pkgsrc)` in application package order.
3. `config_db_custom(pkgsrc)` if present.

The cross-package phase subscribes to source insertions to mark new column
nodes with `_owner_package`. Table mixins receive `db`, `_tblname` and `src`;
table source objects retain `_mixinobj`. Package `onBuildingDbobj` callbacks run
next, followed by the deferred callback stack. That stack uses `pop()`, hence
LIFO ordering, and drains callbacks appended while it is running.

Sources: `legacy:gnrpy/gnr/sql/gnrsql/db.py:372`;
`legacy:gnrpy/gnr/sql/gnrsqlmodel/model.py:91`, `:107`, `:120`, `:125`, `:142`,
`:158`, `:168`.

Deferred configuration is functional, not incidental: composite-column formula
construction explicitly waits until declarations are available.
Source: `legacy:gnrpy/gnr/sql/gnrsqlmodel/model.py:1092`.

### 4. Materialize the typed object tree

The model builds a class registry from `sqlclass` and `sqlresolver` markers,
then invokes `DbModelObj.makeRoot(self, self.src, sqldict)`.
`GnrStructObj.makeRoot()` chooses a class by the source node's tag. The generic
constructor records the source node, copies its attributes, establishes parent
and root links, captures children, initializes the object, recursively constructs
children, and finally invokes `afterChildrenCreation()`.

Children are stored by lowercase name; aliases refer to the same stored child.
Explicit IDs are recorded in the root's object dictionary. Lookup traverses
existing objects and invokes a resolver only when the stored child is a
`BagResolver`; it does not recreate every ordinary child on each lookup.

Sources: `legacy:gnrpy/gnr/sql/gnrsqlmodel/model.py:166`, `:174`;
`legacy:gnrpy/gnr/core/gnrstructures.py:240`, `:255`, `:292`, `:354`, `:362`,
`:388`.

`DbModelObj.init()` obtains the owning database from `root.rootparent`, applies
registered mixins and an optional declaration-level `mixin`, then calls
`doInit()`. A package receives its own mixin. A table overrides `_getMixinObj()`
to create `SqlTable(self)` and directs its behavior mixin there. This is why a
model table and its callable application table are distinct objects.

Sources: `legacy:gnrpy/gnr/sql/gnrsqlmodel/obj.py:46`, `:148`, `:153`;
`legacy:gnrpy/gnr/sql/gnrsqlmodel/table.py:105`.

Ordering matters: `DbTableObj.doInit()` calls `dbtable.onIniting()` and
`onInited()` while its physical column children have not yet been recursively
constructed. These are not whole-model-ready notifications. Afterwards,
`afterChildrenCreation()` ensures missing containers exist and creates indexes
requested by column shorthand.

Sources: `legacy:gnrpy/gnr/sql/gnrsqlmodel/table.py:58`, `:67`;
`legacy:gnrpy/gnr/core/gnrstructures.py:280`.

### 5. Initialize columns, then finalize the relation graph

Column objects retain table/package links. Their initialization applies dtype
defaults and package-provided custom types, populates physical-name mappings,
registers shorthand indexing and field triggers, and queues relation definitions.
Relation payloads are captured specially rather than blindly materialized as
ordinary child objects. Virtual columns also have specialized initialization.

Sources: `legacy:gnrpy/gnr/sql/gnrsqlmodel/columns.py:70`, `:116`, `:194`,
`:199`, `:220`, `:255`, `:260`.

Only after the complete object tree exists does `DbModel.build()` drain pending
relations. `addRelation()` creates both many-to-one and inverse entries, records
Python and SQL delete/update actions separately, and processes relation indexes
and column-size compatibility. It then clears the pending registry and invalidates
the current environment's cached relation trees.

Sources: `legacy:gnrpy/gnr/sql/gnrsqlmodel/model.py:175`, `:181`, `:267`,
`:298`, `:316`.

### 6. Expose operational objects and environment-sensitive views

After construction, `db.model.table('pkg.name')` reaches the stored `DbTableObj`.
`db.table('pkg.name')` returns that object's stored `dbtable`. `SqlTable.model`
points back to the descriptor; `SqlTable.db` resolves through it to the owning
database. Its class combines query, record, CRUD, trigger, serialization and other
mixins, and its constructor allocates table-specific state and an `RLock`.

During build, source lookup is different: when no compiled tree exists,
`DbModel.table()` returns source data, and `db.table()` can return `_mixinobj`.
A modern lifecycle should not accidentally promise identical object availability
before and after finalization just because both legacy paths use `db.table()`.

Sources: `legacy:gnrpy/gnr/sql/gnrsqlmodel/model.py:532`;
`legacy:gnrpy/gnr/sql/gnrsql/query.py:232`;
`legacy:gnrpy/gnr/sql/gnrsqltable/table.py:47`, `:74`, `:123`, `:133`.

The main identity registry is the compiled tree, not a separate table factory
cache. There are additional contextual caches: relation trees are stored under
`currentEnv['_relations'][fullname]`; virtual-column handling consults a
per-table current-environment key and can extend the virtual-column container.
The model also has runtime naming behavior: package table-prefix rules, table
physical-name overrides and tenant-sensitive schema selection.

Sources: `legacy:gnrpy/gnr/sql/gnrsqlmodel/table.py:147`, `:277`, `:358`;
`legacy:gnrpy/gnr/sql/gnrsqlmodel/obj.py:200`.

Model startup is distinct from applying schema changes: `checkDb`,
`diffOrmToSql` and `syncOrmToSql` are explicit operations. Mixin registration is
rejected after startup. Repeated startup should not be inferred to preserve
identity: `build()` assigns a new object tree, and `startup()` has no corresponding
identity-preserving reload contract in the inspected code.

Sources: `legacy:gnrpy/gnr/sql/gnrsql/schema.py:99`, `:110`;
`legacy:gnrpy/gnr/sql/gnrsqlmodel/model.py:489`;
`legacy:gnrpy/gnr/sql/gnrsql/db.py:372`.

## Legacy structures and modern cascading grammar are different mechanisms

No `StructToObject` symbol was found in the inspected SQL modules or
`gnrstructures.py`. That phrase can describe the concept, but the actual legacy
mechanism here is `GnrStructObj.makeRoot()` plus tag-to-class dispatch.
Do not cite a hypothetical `StructToObject` API as evidence.

Modern Builders supplies separate capabilities:

- `BuilderBase.create()` runs `setup`, `main` and the data-element computation pass.
- `render()` materializes a source and delegates final delivery to a renderer.
- `ConfigBuilder` demonstrates distributed grammar via mounted application
  builders; `ConfigHandler` merges parent recipes and provides a layered read API.

Sources: `builders:builder/base.py:658`, `:966`;
`builders:contrib/config/config_builder.py:35`, `:57`;
`builders:contrib/config/handler.py:57`, `:123`.

The SQL builder currently assembles one vocabulary from four Python mixins,
overrides node naming/addressing, and performs domain validation. This does not
mean it already installs ConfigHandler's layered configuration semantics or
materializes live SQL table objects. Conversely, Builders' ability to produce
object output should be evaluated before inventing another generic tree walker.
The SQL-specific lifecycle, identity ownership, two-phase relation resolution and
behavior binding still require explicit design.

Sources: `modern:src/asqueel/builder.py:23`, `:46`, `:68`, `:86`, `:113`, `:123`.

## What exists now and what is missing

| Responsibility | Current implementation | Product gap |
| --- | --- | --- |
| Declarative vocabulary | SqlBuilder and elements | Package/application contribution lifecycle and documented precedence |
| Source indexing | SqlModelCatalog, preserving node order and paths | Not a live object registry |
| Semantic model | resolve_model plus Column/Table/Relation/ResolvedModel | No package runtime object or behavior binding |
| Metadata/UI | Column.ui, attributes, identities and provenance | No complete live column/table API |
| SQL compilation | QueryCompiler using model, dialect and formatter | Needs a table-bound entry point, not another SQL parser |
| Execution | Synchronous Database/Transaction and SyncDriver | Database has no model/table ownership |
| Relations | Resolved outgoing to-one relations | No legacy inverse resolver tree or virtual-relation runtime parity |
| Configuration mixins | None equivalent in native model resolution | Explicit extension/hook contracts and a separate legacy adapter |
| Schema management | Physical projection and migration integration | Must stay an explicit action, separate from object startup |

Modern source evidence: `src/asqueel/catalog.py:19`, `:60`;
`src/asqueel/model.py:32`, `:54`, `:105`;
`src/asqueel/contracts.py:59`, `:78`, `:86`, `:117`;
`src/asqueel/compiler.py:416`, `:498`;
`src/asqueel/runtime.py:20`, `:106`.

The resolved dataclasses are frozen and wrap their outer mappings in read-only
proxies, but nested attribute values are not deeply frozen. They are not
execution contexts. Their provenance is useful input for diagnostics but does
not reconstruct application methods from imported declarations.
Source: `modern:src/asqueel/contracts.py:68`, `:99`, `:122`.

## Recommended boundary for the next design, not implemented API

Preserve the useful legacy ownership graph while making stages explicit:

1. Collect declaration contributions using Builders; define deterministic
   package/application/custom precedence and record their provenance.
2. Validate and resolve one complete semantic model, including relations and
   physical naming, without opening a transaction or changing the database.
3. Bind that model to an execution context owning environment, driver and compiler.
4. Create stable table facades scoped to that context. Each exposes its descriptor
   and delegates compilation/execution to existing components.
5. Bind declared behavior through explicit extension contracts; separate
   declaration callbacks from post-model-ready hooks and write-time hooks.
6. Add a legacy compatibility adapter only where required. Model extraction and
   arbitrary legacy Python behavior execution must be distinguishable choices.

Retain declarative source, resolved metadata and live bindings as separate
artifacts. Prefer shared immutable descriptors where feasible, but never put a
request's environment or active transaction inside a globally shared table
registry. The current synchronous Database thread-ownership rule is an existing
constraint that the new binding layer must respect.

Do not copy accidental legacy coupling: undocumented build-time object-kind
changes, reliance on LIFO callback ordering, mutation of shared metadata to cache
request-specific information, implicit source execution during introspection,
or ad hoc monkey-patching of runtime objects without conflict rules. These are
design risks derived from the traced lifecycle, not newly proven production bugs.

## Acceptance evidence needed before calling the lifecycle complete

A future implementation should demonstrate a small application recipe producing
one usable database/model/table graph; repeated table lookup within a context
must preserve identity. Two contexts sharing the same resolved model must not
share environment or transaction state. Contributions must have deterministic
precedence with traceable provenance. Missing relation targets must fail before
publication of a partially built model. Application hooks must run at documented
stages, and a table method must use the existing compiler and driver path.

Startup must not apply DDL. Introspection must remain usable without executing
application mixins. Legacy adaptation must report unimplemented behavior rather
than silently preserving only its metadata. These checks address the actual
configuration-to-live-object product gap; compiler SQL snapshots alone cannot
establish that it is filled.
