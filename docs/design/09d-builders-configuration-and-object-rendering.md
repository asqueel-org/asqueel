# 09D — Configuration grammars and object rendering

Internal architecture audit, 29 September 2026. This is an analysis and proposed
correction, not documentation of an implemented object API. The companion
[review](09-legacy-object-api-review.md) states the product-level conclusion.

## Evidence boundaries

The SQL checkout is `bf66bcacfeededc7f0ce82cd5c48f6437aa174df`. Pending public-documentation
edits do not change its Python code. Builders was examined in the **installed
0.27.0 distribution**, under `genro_builders/`, not inferred from a newer sibling
checkout. File/line references below use that distribution unless prefixed
`SQL:`. No dependency was upgraded for this audit.

The legacy object build is a separate mechanism, documented in
[09A](09a-legacy-object-model.md). It is not evidence that legacy used the modern
ConfigHandler or modern mounted grammar implementation.

## B01 — The configuration facilities exist, but SQL does not integrate them

`contrib/config/config_builder.py:1–96` defines a configuration dialect whose
consuming classes can provide mounted grammars. Its example host vocabulary
is server/applications; it is **not** a SQL configuration grammar to copy
unchanged. `ConfigHandler` owns an executed source and is the callable read door.

`contrib/config/handler.py:56–76,78–114,119–177` provides:

1. Recipe input by path, builder class or builder instance; create an empty
   instance when needed and enforce one root per layer.
2. Execute parent recipes in declared order, then apply the main recipe last
   using `bag_update(..., ignore_none=True)`.
3. Read an explicitly written value, otherwise the annotated grammar signature
   default, otherwise a supplied call-site default, otherwise raise KeyError.
4. Resolve defaults using the addressed node's grammar; a mounted envelope's
   own attributes belong to the host grammar, its children to the mounted one.

A path-based recipe loader specifically searches for one **ConfigBuilder**
subclass (`handler.py:179–209`); accepting an existing SqlBuilder instance does
not imply accepting a SqlBuilder-only class from a config.py file.

The source deliberately retains only authored values. Consumers that merely
copy `node.attr` do **not** obtain the read-time signature-default contract.
SQL's resolver currently does just that (`SQL: model.py:50–60`). Naming inheritance
and UI overlays implemented by SQL are specific merge rules, not this general
configuration read stack.

## B02 — Layering has ownership and value semantics to preserve deliberately

ConfigHandler folds into the first executed builder; passing an existing parent
instance can mutate that instance's source. The configuration data store is not
merged. A new DB's configuration must therefore have deliberate ownership:
instantiate fresh recipe layers or produce a grammar-preserving owned source,
rather than reuse a mutable parent instance across independent DBs.

A written None is treated as missing by the config reader, whereas 0 and False
remain present values. This is different from the adopted SQL **environment**
contract, where None is a real partition value and absence is distinct. Keep
configuration and request environment separate; do not derive SQL scope presence
from ConfigHandler's missing-value behavior.

Attribute resolvers can evaluate on configuration reads. Specify which values
are resolved when building objects and which at use time, on the owning thread.
Do not serialize resolver results or credentials into migration structures,
query metadata, logs or emitted configuration by accident.

## B03 — Builders already supports object-shaped output

`renderer/base.py:44–63` declares `render_type='object'` as a supported renderer
kind. The walk hands child fragments and runtime attributes to a dialect's
`rendered_item` (`118–156,269–319`). The base `finalize` joins text fragments;
object renderers must implement their own final composition (`415–437`).

`builder/base.py:966–990` materializes then finalizes the rendered result. This
operation does not automatically validate the source. The SQL construction
entry point must therefore validate both grammar and domain contracts before
publishing a partially built DB object. `target=False` is a string-renderer
convention and is explicitly rejected for object renderers (`1007–1023`).

Rendering dispatches through the node's owning builder. A mounted subtree's
renderer is selected through its builder's default render mode and
`renderer_<mode>` property (`renderer/base.py:93–115`). A SQL object renderer
must arrange compatible object renderers for mounted SQL configuration grammars;
adding only a renderer to the root does not make every foreign subtree an SQL
object graph.

The generic walk is child-first. Proposed implementation options are to create
unbound child objects and bind their DB/parent in finalization, or to allocate
an object context before the walk and resolve references afterward. In either
case, relations may refer to later tables or form cycles: allocate/register
objects before linking all relations. This recommendation is an inference from
the renderer contract, not functionality already supplied by genro-sql.

## B04 — The current SQL renderer is the wrong product boundary

`SQL: elements.py:74–84` declares `db(name)` with schemas/extensions children.
There is no connection, adapter or session configuration vocabulary at the DB
root. `SQL: builder.py:122–133` exposes `renderer_sql`, whose implementation
is an unimplemented direct-DDL placeholder (`SQL: renderer.py:1–16`). It neither
creates live database objects nor performs an object build.

`resolve_model()` is useful semantic resolution into table/column/relation
**descriptors**. It is not an object renderer. `PostgresDatabase` is a synchronous
connection/transaction executor with no ownership of those descriptors. A
consumer has to assemble compiler, environment and executor independently.

Do not overload migration rendering with object construction: physical schema
projection, SQL text compilation and live application-object construction have
different outputs and lifecycles. Keep `SqlMigrationRenderer` as the physical
projection; introduce a deliberate object render/build entry point whose
result is the application DB. The exact public spelling is still to be chosen.

## B05 — Mounted grammar limitations are SQL consumer defects to address

The existing experiment proves named paths survive nested schema/table mounts
(`SQL: tests/native_composition/test_composition.py:49–59`). The defects are:

- `SQL: validators.py:104–119` consults the root builder schema for all nodes,
  so a valid local mounted attribute can be rejected. `test_composition.py:152–170`
  specifically characterizes this failure.
- `SQL: emitter.py:221–231` resolves signature order from the root builder class,
  keyed only by tag. Different mounted grammars with the same tag cannot be
  represented correctly by this lookup.
- Configuration classes retained as attribute values can become invalid Python
  reprs during export. `test_composition.py:62–66` passes by **expecting** a
  SyntaxError, not by demonstrating supported export.

Explicit helper functions contributing tables to one grammar are useful, but
they do not satisfy the user's requirement for configuration with its applicable
grammars. Replace the earlier blanket deferral with concrete fixes for per-node
signature ownership and a serializable recipe/reference contract. Dynamic
classes need not magically become serializable; supported and unsupported
configuration forms must be explicit.

## Executed probes

All probes used Python 3.12 and installed Builders 0.27.0; no DB connection was
opened and no production file changed.

| Probe | Observed result |
|---|---|
| `ConfigHandler(existing_sql_builder)('name')` | Returned the declared DB name. This confirms the read door can wrap an existing SQL recipe, not full SQL integration. |
| Distributed parent-config example | Main host won; parent port 9000 and parent application remained; mounted child signature default `stages=3` resolved. |
| Reused parent instance | Handler's builder was that same instance; its original host attribute was overwritten by the merge. |
| Minimal RendererBase subclass with `render_type='object'`, `rendered_item` and `finalize` | Produced a Python object tree from a SQL recipe. No live SQL DB behavior was implemented by this probe. |
| Current `SqlBuilder.render()` | Raised `NotImplementedError: SqlRenderer does not implement rendered_item`. |
| Current Database API | No `table`, `model`, `config` or `commit` attribute. |
| Current resolved table / compiled query | No table `query()` and no query `fetch()`. |
| Existing composition tests | 7 passed, including the two tests that deliberately characterize unsupported mount behavior. |

These observations establish both feasibility in Builders and the missing SQL
integration. They do not establish a completed new database object API.
