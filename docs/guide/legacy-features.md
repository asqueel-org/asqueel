# Differences from GenroPy

This page compares asqueel with the SQL layer of GenroPy (`gnrpy/gnr/sql/`).
It covers what a project calls or declares: methods, attributes, macros.
The legacy reference is GenroPy commit `95da66ee`.

The page has four blocks: Model, Query, Read-Write and Adapters.
Each block has four branches:

- **Missing**: the GenroPy feature is absent in asqueel. A label says why.
  - <span class="asq-label asq-label-temporary">temporary</span>: absent for now; no decision to implement it yet.
  - <span class="asq-label asq-label-removed">removed</span>: decided not to exist in asqueel.
  - <span class="asq-label asq-label-replaced">replaced</span>: another asqueel feature takes its place.
- **Different**: the same feature, with a different syntax or behaviour.
- **New**: an asqueel feature with no GenroPy counterpart.
- **Same**: works as in GenroPy.

[To implement](#to-implement) lists the features a recorded decision will add.
[Migration](#migration), [Low-level and high-level API](#low-level-and-high-level-api)
and [Proposals](#proposals) close the page.

Each card shows the GenroPy side above and the asqueel side below.
The files on both sides are listed in the closed "Files" block at the end of the card.
Every item carries an ID such as `A1.4`. The IDs refer to the verified
inventory `docs/design/112-legacy-inventory.md` (in Italian), which cites the
code on both sides. When this page and another page of the manual disagree,
this page describes the installed code.

For porting guidance, see [For Genropy users](legacy.md). For the refusals of
the write cycle, see [Current status](limitations.md).

## Model

### Missing

(a1-7)=
#### `column(default=)` <span class="asq-label asq-label-temporary">temporary</span>

In GenroPy you wrote:

```python
tbl.column('status', default='new')
```

In GenroPy you got: the attribute stored on the column; a new record took the value from it.

In asqueel: the attribute is declared and readable, but a table with such a column cannot be written. An insert raises `UnsupportedFeatureError`: `app.t: write execution of d.default is not available in this release`.

Workaround: set the value in `trigger_onInserting`.

Notes: [#28](https://github.com/asqueel-org/asqueel/issues/28).

<details><summary>Files</summary>

- GenroPy: `gnrpy/gnr/sql/gnrsqlmodel/model.py:938`, `gnrpy/gnr/sql/gnrsqltable/record.py:600`
- asqueel: `src/asqueel/elements.py:274`, `src/asqueel/model_source.py:251`

</details>

(a1-10)=
#### `localized`, `variant`, `ext_<pkg>` <span class="asq-label asq-label-temporary">temporary</span>

In GenroPy you wrote:

```python
tbl.column('description', localized=True)
```

In GenroPy you got: package hooks that added the generated columns (one per language, per variant, per extension).

In asqueel: each attribute raises `UnsupportedFeatureError` naming it, on the table (`variant`, `ext_<pkg>`) and on the column (`localized`, `variant`, `ext_<pkg>`). Example: `app.t.c: localized is not available in this release`.

Workaround: declare the generated columns by hand.

<details><summary>Files</summary>

- GenroPy: `gnrpy/gnr/sql/gnrsqlmodel/model.py:919`, `gnrpy/gnr/sql/gnrsqlmodel/model.py:958`, `gnrpy/gnr/sql/gnrsqlmodel/model.py:935`, `gnrpy/gnr/sql/gnrsqlmodel/model.py:948`
- asqueel: `src/asqueel/builder.py:405-411`

</details>

(a1-14)=
#### `sysFields(tbl, ...)` <span class="asq-label asq-label-replaced">replaced</span>

In GenroPy you wrote:

```python
def config_db(self, pkg):
    tbl = pkg.table('note', pkey='id')
    self.sysFields(tbl)
```

In GenroPy you got: the system columns (`id`, `__ins_ts`, `__mod_ts`, `__del_ts`, users, draft) and their values on write.

In asqueel you write:

```python
tbl = pkg.table('note', pkey='id')
tbl.options().sys_fields()
```

In asqueel you get: the columns `id`, `__ins_ts`, `__mod_ts`, `__del_ts`, `__ins_user`, `__mod_user`, `__is_draft`, `__syscode`. The write fills a 22-character `id`, the timestamps through `trigger_setTSNow` and the users through `trigger_setCurrentUser` from `db.currentUser`.

Notes: write behaviour in [#29](https://github.com/asqueel-org/asqueel/issues/29).

<details><summary>Files</summary>

- GenroPy: `gnrpy/gnr/app/gnrdbo.py:324`
- asqueel: `src/asqueel/model_elements.py:90`, `src/asqueel/model_expansion.py:125`, `src/asqueel/model_source.py:237`, `src/asqueel/table_triggers.py:50`, `src/asqueel/table_triggers.py:57`, `src/asqueel/runtime.py:158`

</details>

(a1-15)=
#### `sysFields(hierarchical=...)` <span class="asq-label asq-label-replaced">replaced</span>

In GenroPy you wrote:

```python
self.sysFields(tbl, hierarchical='code')
```

In GenroPy you got: a hierarchical table with `parent_id`, the materialized `hierarchical_<field>` columns, and their values on write.

In asqueel you write:

```python
tbl.options().sys_fields()
tbl.options().hierarchical('code')
```

In asqueel you get: the same columns, written by `trigger_hierarchical_before` and `trigger_hierarchical_after` through `HierarchicalHandler`; `child_count`, `hlevel` and `root_id` are read. The pkey must be `id` of size 22. `linked_to` and `depth` raise `UnsupportedFeatureError`, for example `app.cat: hierarchical linked_to is not available in this release`.

Notes: [#30](https://github.com/asqueel-org/asqueel/issues/30); model JSON in [#18](https://github.com/asqueel-org/asqueel/issues/18).

<details><summary>Files</summary>

- GenroPy: `gnrpy/gnr/app/gnrdbo.py:326`, `gnrpy/gnr/app/gnrdbo.py:437`
- asqueel: `src/asqueel/option_elements.py:14`, `src/asqueel/model_expansion.py:226`, `src/asqueel/hierarchical.py:29`, `src/asqueel/table_triggers.py:61`

</details>

(a1-16)=
#### `sysFields(counter=)` / `sysFields_counter` <span class="asq-label asq-label-replaced">replaced</span>

In GenroPy you wrote:

```python
self.sysFields(tbl, counter=True)
```

In GenroPy you got: a `_row_count` column, the table ordered by it, and a value assigned on insert.

In asqueel you write:

```python
tbl.options().auto_counter()
```

In asqueel you get: the `_row_count` column and the table `order_by`. The write is refused except on a hierarchical table: an insert raises `UnsupportedFeatureError` with `write execution of option auto_counter is not available in this release`.

Notes: the counter value on write is [#31](https://github.com/asqueel-org/asqueel/issues/31). Until then, set the value in `trigger_onInserting`.

<details><summary>Files</summary>

- GenroPy: `gnrpy/gnr/app/gnrdbo.py:326`, `gnrpy/gnr/app/gnrdbo.py:556`
- asqueel: `src/asqueel/option_elements.py:22`, `src/asqueel/model_expansion.py:199-209`, `src/asqueel/model_source.py:239-242`

</details>

(a1-18)=
#### Table and package mixins <span class="asq-label asq-label-temporary">temporary</span>

In GenroPy you wrote:

```python
model.tableMixin('sales.invoice', InvoiceMixin)
```

In GenroPy you got: the mixin classes (`tableMixin`, `packageMixin`, `_plugins`, `mixin=`) composed into the table or package object.

In asqueel: `db.tableMixin` and `db.packageMixin` raise `UnsupportedFeatureError` (`tableMixin is not available in this release`). `mixin=` on a table raises too, and so does a `Table` class in `main.py`. A table has one class only.

Workaround: `x_table_class`, or the `Table` class of the package layout.

<details><summary>Files</summary>

- GenroPy: `gnrpy/gnr/sql/gnrsqlmodel/model.py:516`, `gnrpy/gnr/sql/gnrsqlmodel/model.py:525`, `gnrpy/gnr/sql/gnrsqlmodel/obj.py:58-63`
- asqueel: `src/asqueel/runtime.py:53`, `src/asqueel/runtime.py:57`, `src/asqueel/builder.py:407`, `src/asqueel/package_layout.py:55`, `src/asqueel/object_tree.py:166`, `src/asqueel/package_layout.py:75`

</details>

(a1-23)=
#### `rowcaption` / `newrecord_caption` properties <span class="asq-label asq-label-temporary">temporary</span>

In GenroPy you wrote:

```python
caption = tblobj.rowcaption
```

In GenroPy you got: the declared `rowcaption`, else `caption_field`, else the pkey.

In asqueel: the `table()` attributes are declared, but the properties raise `UnsupportedFeatureError`: `app.t: rowcaption is not available in this release`.

Workaround: `attributes.get('rowcaption')`.

<details><summary>Files</summary>

- GenroPy: `gnrpy/gnr/sql/gnrsqlmodel/table.py:240`, `gnrpy/gnr/sql/gnrsqlmodel/table.py:255`
- asqueel: `src/asqueel/elements.py:172-173`, `src/asqueel/object_tree.py:334`

</details>

(a1-24)=
#### `virtual_columns` / `starColumns()` <span class="asq-label asq-label-temporary">temporary</span>

In GenroPy you wrote:

```python
names = list(tblobj.virtual_columns.keys())
cols = tblobj.starColumns()
```

In GenroPy you got: `virtual_columns` with the local columns, the `formulaColumn_*` columns and the variants; `starColumns()` as a public method.

In asqueel: `virtual_columns` lists only the declared virtual columns. The `formulaColumn_<x>()` columns are in `dynamic_columns`, and `column()` resolves them. `starColumns()` raises `UnsupportedFeatureError`: `app.t: starColumns is not available in this release`. The `*` expansion is internal to the compiler.

Workaround: declare the columns in the recipe.

<details><summary>Files</summary>

- GenroPy: `gnrpy/gnr/sql/gnrsqlmodel/table.py:359`, `gnrpy/gnr/sql/gnrsqlmodel/table.py:405`, `gnrpy/gnr/sql/gnrsqlmodel/table.py:440`, `gnrpy/gnr/sql/gnrsqlmodel/table.py:479`
- asqueel: `src/asqueel/object_tree.py:217`, `src/asqueel/object_tree.py:225`, `src/asqueel/object_tree.py:334`, `src/asqueel/compiler.py:805`

</details>

(a1-25)=
#### `subtable()` <span class="asq-label asq-label-temporary">temporary</span>

In GenroPy you wrote:

```python
tbl.subtable('open', condition='$status = :s', condition_s='open')
```

In GenroPy you got: a named subset of the table, with a `subtable_<name>` formula and a package variant with `maintable`.

In asqueel: there is no `subtable` element. `t.subtable(...)` raises `AttributeError`. `default_subtable` as a table attribute raises `ValueError` (`Element 'table' does not accept 'default_subtable'`). The query option `subtable` raises `UnsupportedFeatureError`: `query option 'subtable' is not available in this release`.

Workaround: a `where` with the subtable condition.

<details><summary>Files</summary>

- GenroPy: `gnrpy/gnr/sql/gnrsqlmodel/model.py:685`, `gnrpy/gnr/sql/gnrsqlmodel/model.py:800`, `gnrpy/gnr/sql/gnrsqlmodel/model.py:704`
- asqueel: `src/asqueel/builder.py:365`, `src/asqueel/application_table.py:45`

</details>

(a3-8)=
#### `_override` <span class="asq-label asq-label-temporary">temporary</span>

In GenroPy you wrote:

```python
tbl.formulaColumn('total', sql_formula='$net + $vat', _override=True)
```

In GenroPy you got: the virtual column replaced the physical column of the same name.

In asqueel: the grammar refuses the attribute with `ValueError`: `Element 'formulaColumn' does not accept '_override'`. A virtual column with the name of a physical one raises `conflicting element kinds`.

Workaround: rename the virtual column.

Notes: a recorded decision defers it to the composition between packages, with the GenroPy syntax.

<details><summary>Files</summary>

- GenroPy: `gnrpy/gnr/sql/gnrsqlmodel/model.py:1007-1019`
- asqueel: `src/asqueel/builder.py:194-197`, `tests/test_virtual_column_redefinition.py:93-106`

</details>

(a3-12)=
#### `pyColumn` <span class="asq-label asq-label-temporary">temporary</span>

In GenroPy you wrote:

```python
tbl.pyColumn('age', py_method='calc_age', dtype='L')
```

In GenroPy you got: NULL in the SQL and the value computed in Python on each fetched row.

In asqueel: the declaration is accepted. Selecting the column raises `UnsupportedFeatureError`: `pyColumn is not available in this release`.

Workaround: compute the value in the application after `fetch()`.

<details><summary>Files</summary>

- GenroPy: `gnrpy/gnr/sql/gnrsqlmodel/model.py:1291-1303`, `gnrpy/gnr/sql/gnrsqldata/compiler.py:442-446`, `gnrpy/gnr/sql/gnrsqldata/query.py:257-280`
- asqueel: `src/asqueel/elements.py:388`, `src/asqueel/compiler.py:214`, `tests/test_specific_errors.py:62`

</details>

(a3-14)=
#### `toolColumn` <span class="asq-label asq-label-temporary">temporary</span>

In GenroPy you wrote:

```python
tbl.toolColumn('print_link', tool='print', dtype='T')
```

In GenroPy you got: a column that renders a link to an external tool.

In asqueel: the element does not exist. The call raises `AttributeError`: `'SourceBagNode' object has no attribute 'toolColumn'`.

Workaround: a `formulaColumn` with the explicit expression.

Notes: excluded from this release by a recorded decision.

<details><summary>Files</summary>

- GenroPy: `gnrpy/gnr/sql/gnrsqlmodel/model.py:1194-1211`
- asqueel: `src/asqueel/builder.py:66-70`

</details>

(a3-25)=
#### Variant columns <span class="asq-label asq-label-temporary">temporary</span>

In GenroPy you wrote:

```python
tbl.column('date', dtype='D', variant='year')
```

In GenroPy you got: extra columns from the table methods `variantColumn_<v>()`, and a variant created from `sqlparams[name]={field: ...}`.

In asqueel: `variant=` raises on `column` (`UnsupportedFeatureError`) and in `formulaColumn` (`Element 'formulaColumn' does not accept 'variant'`). The `variantColumn_*` methods are not read. A name passed only in the sqlparams raises `Unknown column`.

Workaround: declare explicit `formulaColumn`s.

<details><summary>Files</summary>

- GenroPy: `gnrpy/gnr/sql/gnrsqlmodel/table.py:440-471`, `gnrpy/gnr/sql/gnrsqlmodel/table.py:343-356`
- asqueel: `src/asqueel/builder.py:405-410`, `src/asqueel/compiler.py:139`

</details>

(a4-9)=
#### To-many path `@relation_name.col` <span class="asq-label asq-label-replaced">replaced</span>

In GenroPy you wrote:

```python
tbl.query(columns='$id, @invoices.amount').fetch()
```

In GenroPy you got: a JOIN toward the many side, one row per related row, and an automatic DISTINCT.

In asqueel you write:

```python
tbl.query(columns='$id, @invoices.aggr(count() AS n)').fetch()
```

In asqueel you get: one row per customer and the aggregate as a correlated subquery. The path `@invoices.amount` raises `UnsupportedFeatureError`: `@invoices: a path through the many relation @invoices is not available in this release`. With `one_one` on the relation the path becomes a LEFT JOIN.

Notes: a recorded decision rules out to-many JOINs, multiplied rows and implicit DISTINCT; `aggr` replaces them (see the `@rel.aggr(...)` card under New).

<details><summary>Files</summary>

- GenroPy: `gnrpy/gnr/sql/gnrsqldata/compiler.py:571`, `gnrpy/gnr/sql/gnrsqldata/compiler.py:665`, `gnrpy/gnr/sql/gnrsqldata/compiler.py:1059`
- asqueel: `src/asqueel/compiler.py:377-379`, `src/asqueel/compiler.py:363-364`

</details>

(a4-11)=
#### `joinColumn` <span class="asq-label asq-label-temporary">temporary</span>

In GenroPy you wrote:

```python
tbl.joinColumn('customer_code', ...)
```

In GenroPy you got: a virtual column with a relation and an automatic `relation_path` of the form `@name.col`.

In asqueel: the call raises `UnsupportedFeatureError`: `joinColumn is not available in this release`. A relation on a virtual column exists: it is weak by default and the join uses the column expression.

Workaround: declare by hand a `formulaColumn` with `.relation(...)` and an `aliasColumn`.

<details><summary>Files</summary>

- GenroPy: `gnrpy/gnr/sql/gnrsqlmodel/model.py:1067`, `gnrpy/gnr/sql/gnrsqlmodel/columns.py:273-279`
- asqueel: `src/asqueel/builder.py:126-129`, `src/asqueel/builder.py:441-446`, `src/asqueel/compiler.py:428`, `src/asqueel/legacy_source.py:77-88`, `src/asqueel/compiler.py:354`

</details>

(a4-13)=
#### `joinConditions`, `setJoinCondition`, `jc_*` <span class="asq-label asq-label-temporary">temporary</span>

In GenroPy you wrote:

```python
tbl.query(columns='@lines.amount', joinConditions={...}).fetch()
```

In GenroPy you got: an extra condition on the join of a relation; with `one_one` a to-many join became to-one.

In asqueel: each form raises `UnsupportedFeatureError`. `query(joinConditions=...)` gives `query option 'joinConditions' is not available in this release`. `setJoinCondition` gives `setJoinCondition is not available in this release`. A `jc_<name>` keyword gives `join condition keyword jc_<name> is not available in this release`.

Workaround: put the condition in the `where` or in a `subQueryColumn`.

<details><summary>Files</summary>

- GenroPy: `gnrpy/gnr/sql/gnrsqldata/query.py:191`, `gnrpy/gnr/sql/gnrsqltable/query.py:134`, `gnrpy/gnr/sql/gnrsqltable/query.py:157`, `gnrpy/gnr/sql/gnrsqldata/compiler.py:653`, `gnrpy/gnr/sql/gnrsqldata/compiler.py:702`
- asqueel: `src/asqueel/application_table.py:44`, `src/asqueel/application_table.py:80-81`, `src/asqueel/application_table.py:397-399`

</details>

(a4-14)=
#### `relationDict` <span class="asq-label asq-label-temporary">temporary</span>

In GenroPy you wrote:

```python
tbl.query(columns='$cust', relationDict={'cust': '@customer_id.name'})
```

In GenroPy you got: symbolic column names resolved to relation paths.

In asqueel: `query(relationDict=...)` raises `UnsupportedFeatureError`: `query option 'relationDict' is not available in this release`. `cpl.relationDict` holds only the resolved output paths.

Workaround: an `aliasColumn` in the model, or `AS` aliases in the columns.

<details><summary>Files</summary>

- GenroPy: `gnrpy/gnr/sql/gnrsqldata/query.py:146`, `gnrpy/gnr/sql/gnrsqldata/query.py:491`
- asqueel: `src/asqueel/application_table.py:44`, `src/asqueel/compiler.py:125`

</details>

(a4-16)=
#### Relation introspection methods <span class="asq-label asq-label-temporary">temporary</span>

In GenroPy you wrote:

```python
joiner = tblobj.getJoiner('sales.customer')
```

In GenroPy you got: `getRelation`, `getRelationBlock`, `getJoiner`, `resolveRelationPath`, `relations_one`, `relations_many`, `manyRelationsList`, `oneRelationsList`.

In asqueel: `getRelation`, `getJoiner`, `relations_one`, `relations_many` and `manyRelationsList` raise `UnsupportedFeatureError`, for example `app.t: getRelation is not available in this release`. `getRelationBlock`, `resolveRelationPath` and `oneRelationsList` raise a plain `AttributeError`.

Workaround: read `table.relations` and its joiner.

<details><summary>Files</summary>

- GenroPy: `gnrpy/gnr/sql/gnrsqlmodel/table.py:648`, `gnrpy/gnr/sql/gnrsqlmodel/table.py:696`, `gnrpy/gnr/sql/gnrsqlmodel/table.py:709`, `gnrpy/gnr/sql/gnrsqlmodel/table.py:717`, `gnrpy/gnr/sql/gnrsqlmodel/table.py:730`, `gnrpy/gnr/sql/gnrsqlmodel/table.py:755`, `gnrpy/gnr/sql/gnrsqlmodel/table.py:859`, `gnrpy/gnr/sql/gnrsqlmodel/table.py:881`
- asqueel: `src/asqueel/object_tree.py:334-336`, `src/asqueel/table_crud.py:167`

</details>

(a4-17)=
#### `relationExplorer` <span class="asq-label asq-label-temporary">temporary</span>

In GenroPy you wrote:

```python
tree = tblobj.relationExplorer()
```

In GenroPy you got: a tree of the relations reachable from the table.

In asqueel: the method raises `UnsupportedFeatureError` on the model table and on `SqlTable`: `app.t: relationExplorer is not available in this release`.

Workaround: read the `relations` tree of the table.

<details><summary>Files</summary>

- GenroPy: `gnrpy/gnr/sql/gnrsqltable/utils.py:456`, `gnrpy/gnr/sql/gnrsql/query.py:378`
- asqueel: `src/asqueel/object_tree.py:335`

</details>

(a4-18)=
#### `aliasTable` / `table_alias` <span class="asq-label asq-label-temporary">temporary</span>

In GenroPy you wrote:

```python
tbl.aliasTable('customer', relation_path='@invoice_id.@customer_id')
```

In GenroPy you got: `@customer.name` expanded to the full path inside queries.

In asqueel: there is no `aliasTable` element; the call raises `AttributeError`. The `aliasTable` and `table_alias` nodes of a source are refused. A `virtualRelation(relation=...)` resolves only inside `aggr`: `@alias.col` raises `Relation @alias not found`.

Workaround: write the full path `@a.@b.col`.

Notes: a recorded decision takes `aliasTable` out of the grammar for now; `virtualRelation` is to-many only.

<details><summary>Files</summary>

- GenroPy: `gnrpy/gnr/sql/gnrsqlmodel/model.py:1305`, `gnrpy/gnr/sql/gnrsqldata/compiler.py:490`
- asqueel: `src/asqueel/configuration.py:121-123`, `src/asqueel/legacy_source.py:98-100`, `src/asqueel/compiler.py:354`

</details>

### Different

(a1-1)=
#### `package()`, `sqlschema`, `sqlprefix`, `sqlname`

In GenroPy you wrote:

```python
pkg = model.package('sales', sqlschema='sales')
```

In GenroPy you got: the package name as table prefix (`sales_invoice`), the schema from `sqlschema`, and a `tenant_schema` for multi-tenant tables.

In asqueel you write:

```python
pkg = root.packages().package('sales', sqlschema='crm', sqlprefix='c')
```

In asqueel you get: the same schema and prefix rules. Package `sales` gives `sales_inv` in `public`; `sqlschema` defaults to `public`, or `main` on SQLite. There is no `tenant_schema`: the table attribute `multi_tenant` raises as outside the grammar.

Notes: a model with a schema tag does not set the prefix: [#25](https://github.com/asqueel-org/asqueel/issues/25). Multi-tenant tables are out of scope for now.

<details><summary>Files</summary>

- GenroPy: `gnrpy/gnr/sql/gnrsqlmodel/model.py:602`, `gnrpy/gnr/sql/gnrsqlmodel/obj.py:200`, `gnrpy/gnr/sql/gnrsqlmodel/table.py:151`
- asqueel: `src/asqueel/model_elements.py:38`, `src/asqueel/object_tree.py:150`, `src/asqueel/object_tree.py:155`, `src/asqueel/object_tree.py:256`, `src/asqueel/object_tree.py:260`, `src/asqueel/builder.py:365`

</details>

(a1-2)=
#### `table(name, pkey=, ..., **kwargs)`

In GenroPy you wrote:

```python
tbl = pkg.table('category', pkey='id', hierarchical='code', my_attr=1)
```

In GenroPy you got: every keyword stored as a table attribute.

In asqueel you write:

```python
tbl = pkg.table('category', pkey='id', name_long='Category')
```

In asqueel you get: a closed signature plus the `partition_*` family. Any other keyword raises `ValueError` naming the attribute and the element: `Element 'table' does not accept 'hierarchical'`. `hierarchical`, `xtd`, `multi_tenant`, `group_x`, `x_custom` and `my_attr` are refused.

Notes: a recorded decision says that anything outside the grammar raises.

<details><summary>Files</summary>

- GenroPy: `gnrpy/gnr/sql/gnrsqlmodel/model.py:643`
- asqueel: `src/asqueel/elements.py:166`, `src/asqueel/builder.py:365`

</details>

(a1-4)=
#### `partition_<field>='path'`

In GenroPy you wrote:

```python
tbl = pkg.table('invoice', pkey='id', partition_company_id='company_id')
```

In GenroPy you got: a filter from env `current_<path>`, else from `allowed_<path>`, else from a `__allowed_partition` column.

In asqueel you write:

```python
tbl = pkg.table('invoice', pkey='id', partition_company_id='company_id')
```

In asqueel you get: `$company_id = :env_current_company_id` when `current_company_id` is set; else `$company_id IS NULL OR $company_id IN :env_allowed_company_id`; else no filter. The first `partition_*` attribute counts. There is no fallback on the `__allowed_partition` column. Writes do not read the partition, as in GenroPy.

Notes: partitions on writes are proposed in [#15](https://github.com/asqueel-org/asqueel/issues/15).

<details><summary>Files</summary>

- GenroPy: `gnrpy/gnr/sql/gnrsqltable/columns.py:104-105`
- asqueel: `src/asqueel/elements.py:164`, `src/asqueel/compiler.py:876`

</details>

(a1-9)=
#### UI attributes on columns

In GenroPy you wrote:

```python
tbl.column('status', values='o:Open,c:Closed', format='#', print_width=10)
```

In GenroPy you got: every keyword stored on the column.

In asqueel you write:

```python
tbl.column('status', validate_values='o:Open,c:Closed', print_width=10)
```

In asqueel you get: `format` and `print_width` declared and readable in `attributes` and as `column.print_width`. `encrypted` raises `UnsupportedFeatureError` (`app.t.e: encrypted is not available in this release`). Any other attribute (`values`, `cell_*`, `template_*`, `x_*`) raises `ValueError`: `Element 'column' does not accept 'values'`.

Notes: a recorded decision says that anything outside the grammar raises.

<details><summary>Files</summary>

- GenroPy: `gnrpy/gnr/sql/gnrsqlmodel/model.py:938`
- asqueel: `src/asqueel/elements.py:272`, `src/asqueel/object_tree.py:348`, `src/asqueel/builder.py:415`, `src/asqueel/builder.py:365`

</details>

(a1-11)=
#### `colgroup()`

In GenroPy you wrote:

```python
grp = tbl.colgroup('addr', name_long='Address', colgroup_label='Addr')
grp.column('street')
```

In GenroPy you got: `group='addr.001'`, `colgroup_label` and `colgroup_name_long` on the columns, any `col_*` default, and a table attribute `group_addr`.

In asqueel you write:

```python
grp = tbl.colgroup('addr', name_long='Address', col_dtype='T')
grp.column('street')
```

In asqueel you get: `group='addr.001'` and the `col_*` defaults for declared `column` parameters. There is no `group_<name>` on the table and no `colgroup_label` or `colgroup_name_long` on the columns. `colgroup_label` as an argument raises `ValueError`: `Element 'colgroup' does not accept 'colgroup_label'`.

<details><summary>Files</summary>

- GenroPy: `gnrpy/gnr/sql/gnrsqlmodel/model.py:809`, `gnrpy/gnr/sql/gnrsqlmodel/model.py:843-848`, `gnrpy/gnr/sql/gnrsqlmodel/model.py:831`
- asqueel: `src/asqueel/model_elements.py:26`, `src/asqueel/builder.py:496`, `src/asqueel/builder.py:500`, `src/asqueel/builder.py:520`

</details>

(a1-12)=
#### `compositeColumn()`

In GenroPy you wrote:

```python
tbl.compositeColumn('identity', columns='code,year', static=True)
```

In GenroPy you got: a virtual column with `composed_of`, dtype `JS` and `static=True`; `pkeys` expanded it.

In asqueel you write:

```python
tbl.compositeColumn('identity', columns='code,year', unique=True)
```

In asqueel you get: the column in the `composites` collection, dtype `JS`, the pkey resolved on its members. It is read as the value `'["A", 2026]'`, and `where='$identity=:key'` finds the row. `static=` raises `ValueError`: `Element 'compositeColumn' does not accept 'static'`.

Notes: reading as a value: [#26](https://github.com/asqueel-org/asqueel/issues/26).

<details><summary>Files</summary>

- GenroPy: `gnrpy/gnr/sql/gnrsqlmodel/model.py:1078`, `gnrpy/gnr/sql/gnrsqlmodel/table.py:191`
- asqueel: `src/asqueel/elements.py:408`, `src/asqueel/object_tree.py:367`, `src/asqueel/model_source.py:148`, `src/asqueel/compiler.py:219`

</details>

(a1-13)=
#### `index()`

In GenroPy you wrote:

```python
tbl.index('code,year', 'doc_code_year', True)
```

In GenroPy you got: an index with positional `columns`, `name`, `unique`; the default name `<table>_<columns>_key`.

In asqueel you write:

```python
tbl.index(['code', 'year'], name='doc_code_year', unique=True)
```

In asqueel you get: the same default name, and a list or tuple joined with `,`. Only `columns` is positional: `index('a', 'b', True)` raises `TypeError` (`index: at most one positional argument is allowed`). `method`, `where`, `tablespace` and `with_options` are extra keyword attributes.

<details><summary>Files</summary>

- GenroPy: `gnrpy/gnr/sql/gnrsqlmodel/model.py:1326`, `gnrpy/gnr/sql/gnrsqlmodel/model.py:1343`, `gnrpy/gnr/sql/gnrsqlmodel/model.py:1346`
- asqueel: `src/asqueel/elements.py:446`, `src/asqueel/builder.py:458-464`, `src/asqueel/common.py:88`, `src/asqueel/builder.py:170`

</details>

(a1-17)=
#### `config_db`, `config_db_<pkg>`, `config_db_custom`

In GenroPy you wrote:

```python
class Table(object):
    def config_db_custom(self, pkg):
        pkg.table('invoice').column('note')
```

In GenroPy you got: `config_db`, then `config_db_<pkg>` and `config_db_custom` run by `build()` on the table mixins.

In asqueel you write:

```python
class Table:
    def config_db(self, pkg):
        tbl = pkg.table('invoice', pkey='id')
```

In asqueel you get: `Table.config_db(self, pkg)` of `model/<table>.py` run in alphabetical order. `config_db_<pkg>` and `config_db_custom` raise `UnsupportedFeatureError`, for example `sales.invoice: config_db_custom is not available in this release`. Beside it, the recipe `main(self, root)` stays, with overrides through `builder.contribution`.

Notes: customization belongs to the application level; the layout is provisional (a recorded decision).

<details><summary>Files</summary>

- GenroPy: `gnrpy/gnr/sql/gnrsqlmodel/model.py:127`, `gnrpy/gnr/sql/gnrsqlmodel/model.py:130`, `gnrpy/gnr/sql/gnrsqlmodel/model.py:140`
- asqueel: `src/asqueel/package_layout.py:69`, `src/asqueel/package_layout.py:66-68`, `src/asqueel/builder.py:123`, `src/asqueel/builder.py:181`

</details>

(a1-19)=
#### `model.table()`, `model.column()`, `tblobj.column()`

In GenroPy you wrote:

```python
model.table('nope.t')
model.table('sales.nope')
```

In GenroPy you got: `None` for an unknown package; `GnrSqlMissingTable` for an unknown table; `None` for an unknown simple column; `AttributeError` from `model.column` with an unknown package.

In asqueel you write:

```python
model.table('nope.t')
model.table('sales.nope')
```

In asqueel you get: `None` for an unknown package and for an unknown column, as in GenroPy. An unknown table of a known package raises `ValueError` (`Unknown table sales.nope`). `model.column` with an unknown package raises `ValueError` (`Unknown package/schema 'nope'`). `@` paths and `AliasColumnWrapper` work as in GenroPy.

Notes: the different exception classes have no issue.

<details><summary>Files</summary>

- GenroPy: `gnrpy/gnr/sql/gnrsqlmodel/model.py:545`, `gnrpy/gnr/sql/gnrsqlmodel/table.py:514`
- asqueel: `src/asqueel/object_tree.py:465`, `src/asqueel/object_tree.py:143`, `src/asqueel/object_tree.py:298`, `src/asqueel/object_tree.py:473`

</details>

(a1-20)=
#### `pkey` / `pkeys`

In GenroPy you wrote:

```python
tbl = pkg.table('doc', pkey='identity')
tbl.compositeColumn('identity', columns='code,year')
```

In GenroPy you got: `pkey` as one column name, `pkeys` expanded from `composed_of`; without a pkey, `''` and an empty list with a critical log.

In asqueel you write:

```python
tbl = pkg.table('doc', pkey='identity')
tbl.compositeColumn('identity', columns='code,year')
```

In asqueel you get: `pkey` is `'identity'` and `pkeys` is `['code', 'year']`. Without a pkey, `None` and `[]`. `pkey='a,b'` raises `ValueError`: `app.t: pkey 'a,b' is not a column or a compositeColumn`.

Notes: [#23](https://github.com/asqueel-org/asqueel/issues/23). `None` instead of `''` has no issue.

<details><summary>Files</summary>

- GenroPy: `gnrpy/gnr/sql/gnrsqlmodel/table.py:210`, `gnrpy/gnr/sql/gnrsqlmodel/table.py:191`
- asqueel: `src/asqueel/object_tree.py:252`, `src/asqueel/object_tree.py:264`, `src/asqueel/model_source.py:145`

</details>

(a1-22)=
#### `name_long`, `name_short`, `name_full`

In GenroPy you wrote:

```python
tblobj.name_long = 'Invoices'
```

In GenroPy you got: the fallbacks (`name_long` on `name_short`, `name_full` on `name_long`) and setters.

In asqueel you write:

```python
label = tblobj.name_long
```

In asqueel you get: the same fallbacks; `name_plural` falls back on `name_long`; `name_full` is an attribute of package, table and column. There are no setters: assigning `name_long` raises `AttributeError`.

Notes: the missing setters have no issue.

<details><summary>Files</summary>

- GenroPy: `gnrpy/gnr/sql/gnrsqlmodel/obj.py:109-125`
- asqueel: `src/asqueel/object_tree.py:88-97`, `src/asqueel/object_tree.py:284`

</details>

(a1-26)=
#### Package custom types `custom_type_<dtype>`

In GenroPy you wrote:

```python
class Package(GnrDboPackage):
    def custom_type_money(self):
        return dict(dtype='N', size='14,2')
```

In GenroPy you got: the column attributes of `dtype='money'`. An unknown dtype stayed as a string.

In asqueel you write:

```python
pkg.options().type('money', dtype='N', size='14,2')
```

In asqueel you get: in a layout package, `Package.custom_type_<dtype>()` works as in GenroPy, explicit column attributes winning. In a recipe package, `options().type(...)`. An unknown dtype raises `ValueError`: `app.t.p: unknown dtype 'ZZ'`.

Notes: a recorded decision says that anything outside the grammar raises.

<details><summary>Files</summary>

- GenroPy: `gnrpy/gnr/sql/gnrsqlmodel/columns.py:126-133`
- asqueel: `src/asqueel/package_layout.py:76-91`, `src/asqueel/model_elements.py:84`, `src/asqueel/model_source.py:115`

</details>

(a1-27)=
#### `column(sqldefault=, extra_sql=, generated_expression=)`

In GenroPy you wrote:

```python
tbl.column('qty', dtype='L', sqldefault='0')
```

In GenroPy you got: the keyword read by the migrator as the column SQL default.

In asqueel you write:

```python
tbl.column('qty', dtype='L', sql_default='0', sql_sqlite_default='1')
```

In asqueel you get: `sql_default`, `sql_extra`, `sql_generatedExpression`, with `sql_pg_*` and `sql_sqlite_*` variants that win on their dialect. The migration receives the GenroPy keys `sqldefault`, `extra_sql`, `generated_expression`. `sqldefault`, `extra_sql`, `generated_expression` and `sql_mysql_default` raise `ValueError`.

<details><summary>Files</summary>

- GenroPy: `gnrpy/gnr/sql/gnrsqlmigration/structures.py:68-69`, `gnrpy/gnr/sql/gnrsqlmigration/orm_extractor.py:490`
- asqueel: `src/asqueel/elements.py:266-268`, `src/asqueel/common.py:35`, `src/asqueel/common.py:28`

</details>

(a1-28)=
#### Package folder in the legacy layout

In GenroPy you wrote:

```python
class Package(GnrDboPackage):
    def config_attributes(self):
        return dict(name_long='Sales')
```

In GenroPy you got: `main.py` imported, `config_attributes()` under the package attributes, the tables loaded from `model/` in alphabetical order, plus `custom.py`, `_packages` and plugins.

In asqueel you write:

```python
pkg = root.packages().package('sales', path='/path/to/sales')
```

In asqueel you get: `config_attributes()` under the attributes written on the element, `Table.config_db(pkg)` in alphabetical order, the runtime class `Table` combined with `SqlTable`. `Package.config_db`, `onBuildingDbobj` and a `Table` in `main.py` raise `UnsupportedFeatureError`. `custom.py`, `_packages` and plugins are not read.

Notes: the layout is provisional (a recorded decision).

<details><summary>Files</summary>

- GenroPy: `gnrpy/gnr/app/gnrapp.py:640`, `gnrpy/gnr/app/gnrapp.py:654`, `gnrpy/gnr/app/gnrapp.py:679-680`
- asqueel: `src/asqueel/model_elements.py:38`, `src/asqueel/package_layout.py:41`, `src/asqueel/package_layout.py:55-60`

</details>

(a3-1)=
#### `formulaColumn` (`sql_formula`, `select`, `exists`, `dtype`)

In GenroPy you wrote:

```python
tbl.formulaColumn('total', sql_formula='#t', select=dict(...), select_t=dict(...))
```

In GenroPy you got: `sql_formula` winning over `select`/`exists`; dtype `A` by default.

In asqueel you write:

```python
tbl.formulaColumn('label', sql_formula='$code')
```

In asqueel you get: dtype `A` by default. Exactly one of `sql_formula`, `select`, `exists` is required. `sql_formula` with `select` or `exists` raises `ValueError`: `sql_formula cannot be combined with select or exists`. A `select_<name>` without `sql_formula`, or not used in the formula, raises.

Notes: the checks on unused `select_<name>` have no issue.

<details><summary>Files</summary>

- GenroPy: `gnrpy/gnr/sql/gnrsqlmodel/model.py:1265`, `gnrpy/gnr/sql/gnrsqlmodel/model.py:1271`, `gnrpy/gnr/sql/gnrsqldata/compiler.py:400-401`
- asqueel: `src/asqueel/elements.py:346`, `src/asqueel/object_tree.py:369`, `src/asqueel/model.py:49-52`, `src/asqueel/model.py:62-66`, `tests/test_formula_columns_legacy.py:100`, `tests/test_formula_columns_legacy.py:114`

</details>

(a3-10)=
#### `subQueryColumn` (`query=`, `mode=`)

In GenroPy you wrote:

```python
tbl.subQueryColumn('codes', query=dict(table='app.invoice', columns='$code',
                   where='$customer_id=#THIS.id'), mode='json')
```

In GenroPy you got: `jsonb_agg` for `json`, `xmlagg` for `xml`, a plain SELECT for any other mode.

In asqueel you write:

```python
tbl.subQueryColumn('codes', query=dict(table='app.invoice', columns='$code',
                   where='$customer_id=#THIS.id'), mode='json')
```

In asqueel you get: the same `query=`. `mode` accepts only `None`, `'json'`, `'xml'`; another mode raises `ValueError` pointing to `aggr`. `mode='xml'` with a string query is refused. On SQLite `json` and `xml` are refused before execution.

<details><summary>Files</summary>

- GenroPy: `gnrpy/gnr/sql/gnrsqlmodel/model.py:1213-1262`, `gnrpy/gnr/sql/gnrsqlmodel/model.py:1233`, `gnrpy/gnr/sql/gnrsqlmodel/model.py:1247`
- asqueel: `src/asqueel/elements.py:368`, `src/asqueel/compiler.py:183-199`, `src/asqueel/compiler.py:341-345`, `src/asqueel/adapters/postgres.py:113`, `src/asqueel/adapters/sqlite.py:191-192`, `tests/test_subquery_aggr_and_macros.py:154`

</details>

(a3-13)=
#### `compositeColumn` read as a value

In GenroPy you wrote:

```python
tbl.compositeColumn('identity', columns='code,year')
tblobj.query(columns='*').fetch()
```

In GenroPy you got: the string `'["A", 2026]'`; the column was `static=True` by default, so `*` included it.

In asqueel you write:

```python
tbl.compositeColumn('identity', columns='code,year')
tblobj.query(columns='$identity').fetch()
```

In asqueel you get: the same string `'["A", 2026]'`, dtype `JS`, and a composite pkey read and filtered through the same formula. `static` is not accepted, and `*` does not include the compositeColumn.

Notes: linked to [#26](https://github.com/asqueel-org/asqueel/issues/26). The exclusion from `*` and the refusal of `static` have no issue.

<details><summary>Files</summary>

- GenroPy: `gnrpy/gnr/sql/gnrsqlmodel/model.py:1078-1118`, `gnrpy/gnr/sql/gnrsqlmodel/model.py:1120-1157`
- asqueel: `src/asqueel/compiler.py:200-202`, `src/asqueel/compiler.py:219-230`, `src/asqueel/object_tree.py:366-367`, `src/asqueel/elements.py:408`, `src/asqueel/compiler.py:805-808`, `tests/test_formula_columns_legacy.py:75`, `tests/test_formula_columns_legacy.py:80`

</details>

(a3-15)=
#### Dynamic columns `formulaColumn_<x>()`

In GenroPy you wrote:

```python
def formulaColumn_labels(self):
    return dict(name='loud', sql_formula='upper($code)', dtype='T')
```

In GenroPy you got: the column added to the virtual columns and cached in `currentEnv`. A name already declared was replaced.

In asqueel you write:

```python
def formulaColumn_labels(self):
    return dict(name='loud', sql_formula='upper($code)', dtype='T')
```

In asqueel you get: the method called without arguments, a dict or a list of dicts, cached in `currentEnv['_virtual_columns_<pkg>_<tbl>']`. A name already declared raises `ValueError` (`redefines a declared column`).

Notes: the error on a declared name has no issue.

<details><summary>Files</summary>

- GenroPy: `gnrpy/gnr/sql/gnrsqlmodel/table.py:405-427`, `gnrpy/gnr/sql/gnrsqlmodel/table.py:369-383`
- asqueel: `src/asqueel/object_tree.py:224-245`, `src/asqueel/compiler.py:158-159`, `tests/test_formula_columns_legacy.py:64`, `tests/test_formula_columns_legacy.py:69`

</details>

(a4-1)=
#### `relation()` target `'pkg.tbl.col'` / `'tbl.col'`

In GenroPy you wrote:

```python
tbl.column('customer_id').relation('customer.id')
```

In GenroPy you got: `'tbl.col'` completed with the current package; a two-part path always read as `tbl.col`.

In asqueel you write:

```python
tbl.column('customer_id').relation('customer.id')
```

In asqueel you get: the same completion when the first name is not a package. When it is a package, `'x.y'` reads as `pkg.tbl` and points to the target pkey. `'tbl'` alone raises. Inside package `sal`, `'app.code'` looks for package `app` when one exists.

Notes: the ambiguity between a package and a table with the same name has no issue.

<details><summary>Files</summary>

- GenroPy: `gnrpy/gnr/sql/gnrsqlmodel/columns.py:153`, `gnrpy/gnr/sql/gnrsqlmodel/model.py:256`
- asqueel: `src/asqueel/model_source.py:155-157`, `src/asqueel/object_tree_relations.py:75-82`, `src/asqueel/validators.py:261-265`

</details>

(a4-2)=
#### `relation(mode=...)`

In GenroPy you wrote:

```python
tbl.column('customer_id').relation('customer.id', mode='foreignkey')
```

In GenroPy you got: `mode='relation'` by default, with no foreign key; `foreignkey` and `insensitive` set from `mode`.

In asqueel you write:

```python
tbl.column('customer_id').relation('customer.id', foreign_key=True)
```

In asqueel you get: inside a package `foreign_key` is `True` by default and `False` with `cnd`. `weak_relation` creates no foreign key. `mode=` raises `ValueError`: `Element 'relation' does not accept 'mode'`. `case_insensitive=True` produces no `lower()` in the join, as in GenroPy.

<details><summary>Files</summary>

- GenroPy: `gnrpy/gnr/sql/gnrsqlmodel/model.py:1357`, `gnrpy/gnr/sql/gnrsqlmodel/model.py:268-269`
- asqueel: `src/asqueel/elements.py:470`, `src/asqueel/builder.py:447-451`, `src/asqueel/semantic_elements.py:24`, `src/asqueel/builder.py:438-440`, `src/asqueel/legacy_source.py:115-120`, `src/asqueel/compiler.py:422`

</details>

(a4-6)=
#### `onDelete`, `onUpdate`, `onDelete_sql`, `onUpdate_sql`, `deferred`

In GenroPy you wrote:

```python
tbl.column('customer_id').relation('customer.id', onDelete_sql='C')
```

In GenroPy you got: the actions stored in the joiner as written; `onUpdate_sql='cascade'` by default; `deferred` set with `setnull`.

In asqueel you write:

```python
tbl.column('customer_id').relation('customer.id', onDelete_sql='C')
```

In asqueel you get: the same names, defaults and projected foreign key. The joiner stores the actions in lower case without spaces: `'C'` becomes `'c'`, and `'no action'` becomes `None`. `on_delete=` is refused.

Notes: the normalization in the joiner has no recorded reason and no issue.

<details><summary>Files</summary>

- GenroPy: `gnrpy/gnr/sql/gnrsqlmodel/model.py:1366-1370`, `gnrpy/gnr/sql/gnrsqlmodel/model.py:276`
- asqueel: `src/asqueel/elements.py:471-473`, `src/asqueel/object_tree_relations.py:35-39`, `src/asqueel/model_source.py:167-171`, `src/asqueel/common.py:15`, `src/asqueel/object_tree_relations.py:18-25`

</details>

(a4-12)=
#### Join conditions `cnd`, `join_on`, `between`

In GenroPy you wrote:

```python
tbl.column('rate_id').relation('rate.id', cnd='#IN_RANGE(...)')
```

In GenroPy you got: the condition replaced the key equality; `#IN_RANGE` expanded inside `cnd`.

In asqueel you write:

```python
tbl.column('customer_id').relation('customer.id', cnd='$ccode = @customer_id.code')
```

In asqueel you get: `join_on`, `cnd` and `between` replace the key condition, `join_on` winning over `cnd`. A relation with `cnd` creates no foreign key. `#IN_RANGE` inside `cnd` raises `UnsupportedFeatureError`: `macro #IN_RANGE is not available in this release`. `aggr` refuses these relations.

Notes: the refusal of `#IN_RANGE` inside `cnd` has no recorded reason and no issue.

<details><summary>Files</summary>

- GenroPy: `gnrpy/gnr/sql/gnrsqlmodel/model.py:222-224`, `gnrpy/gnr/sql/gnrsqldata/compiler.py:609-616`
- asqueel: `src/asqueel/elements.py:483-484`, `src/asqueel/compiler.py:410-420`, `src/asqueel/builder.py:448-451`, `src/asqueel/compiler.py:429`, `src/asqueel/compiler.py:604-607`

</details>

### New

(a3-21)=
#### `subQueryColumn(aggr=...)`

In asqueel you write:

```python
lines = dict(table='app.invoice', where='$customer_id=#THIS.id')
customer.subQueryColumn('total', query=lines, aggr='sum($amount)', dtype='N')
customer.subQueryColumn('lines', query=lines, aggr='count()', dtype='L')
```

In asqueel you get: one aggregate (`count`, `sum`, `avg`, `min`, `max`, `join`, `to_json`, `to_xml`) in place of the query columns. The query `order_by` orders `join`, `to_json` and `to_xml`. `aggr` with `mode` raises `ValueError`.

<details><summary>Files</summary>

- GenroPy: none
- asqueel: `src/asqueel/elements.py:368-369`, `src/asqueel/compiler.py:193-198`, `tests/test_subquery_aggr_and_macros.py:53`, `tests/test_subquery_aggr_and_macros.py:58`, `tests/test_subquery_aggr_and_macros.py:139`, `tests/test_subquery_aggr_and_macros.py:146`

</details>

(a3-22)=
#### `exists_<name>=dict(...)` in `formulaColumn`

In asqueel you write:

```python
customer.formulaColumn('has_big', sql_formula='#big', dtype='B',
    exists_big=dict(table='app.invoice', where='$customer_id=#THIS.id AND $amount > 100'))
```

In asqueel you get: `#big` replaced by `EXISTS (<subquery>)`. A `select_<name>` and an `exists_<name>` with the same name raise.

<details><summary>Files</summary>

- GenroPy: `gnrpy/gnr/sql/gnrsqldata/compiler.py:398`
- asqueel: `src/asqueel/elements.py:345`, `src/asqueel/model.py:54-61`, `src/asqueel/compiler.py:254`, `tests/test_formula_columns_legacy.py:54`, `tests/test_formula_columns_legacy.py:59`, `tests/test_formula_columns_legacy.py:122`

</details>

(a4-19)=
#### `@rel.aggr(...)`

In asqueel you write:

```python
db.table('sales.invoice').query(
    columns='$id, @lines.aggr(count() AS line_count, sum($amount) AS amount)')
```

In asqueel you get: one value per row of the query, computed by a correlated subquery. The functions are `count`, `sum`, `avg`, `min`, `max`, `join`, `to_json`, `to_xml`. `@rel.order_by('$field DESC').aggr(...)` orders `join`, `to_json` and `to_xml`. `aggr` is accepted only in the projection: `where` and `order_by` refuse it. `to_xml` needs PostgreSQL.

<details><summary>Files</summary>

- GenroPy: none
- asqueel: `src/asqueel/compiler.py:452`, `src/asqueel/compiler.py:523`, `src/asqueel/compiler.py:627`, `src/asqueel/_many_aggregates.py:21`, `src/asqueel/compiler.py:526`

</details>

(a4-20)=
#### `virtualRelation`

In asqueel you write:

```python
customer.virtualRelation('direct_invoices', table='app.invoice',
    condition='$customer_id=:var_customer', var_customer='$id')
```

In asqueel you get: a to-many relation, derived from a relation with `relation=` or direct with `table=`. It is usable only inside `aggr`: `@direct_invoices.col` raises `Relation @direct_invoices not found`. `ask` is refused.

<details><summary>Files</summary>

- GenroPy: none
- asqueel: `src/asqueel/semantic_elements.py:39`, `src/asqueel/compiler.py:536`, `src/asqueel/compiler.py:566`, `src/asqueel/compiler.py:577`

</details>

(a4-21)=
#### Relation inherited by `aliasColumn`

In asqueel you write:

```python
row.aliasColumn('customer_id', '@invoice_id.customer_id')
```

In asqueel you get: the alias inherits the relation of its target column. The row can query `@customer_id.name` through two joins. The inherited relation is weak: no column, foreign key or index is created. A `.relation()` declared on the alias wins.

<details><summary>Files</summary>

- GenroPy: none
- asqueel: `src/asqueel/object_tree_relations.py:127-182`, `src/asqueel/elements.py:332-333`, `tests/object_tree/test_alias_relations.py:34`

</details>

### Same

- **`lastTS`, `logicalDeletionField`, `draftField`**: table attributes and properties, empty string when absent, applied as read filters. (A1.3)
- **`column()` attributes**: `dtype`, `size`, `notnull`, `unique`, `indexed`, `sqlname`, `comment`, `group`, `sql_value`, with the same dtype default and true strings. (A1.5)
- **`'name::dtype'` shorthand**: splits the name and sets the dtype, for physical and virtual columns. (A1.6)
- **`validate_*` attributes**: stored on the column and not executed. (A1.8)
- **`columns` and `relations`**: the columns of a table and the Bag of its relations. (A1.21)
- **`sql_formula=True` with `sql_formula_<name>(attr)`**: calls the method on the owning table, also for `__protecting_reasons` and `__invalid_reasons`. (A3.2)
- **`select=`, `exists=`, `select_<name>`**: `#<name>` replacement, cast, `subquery_<name>()` and the same defaults. (A3.3)
- **`var_*` in formulas**: bound as parameters local to the formula. (A3.4)
- **`aliasColumn`**: recursion on `relation_path` and `AliasColumnWrapper` with the target metadata. (A3.6)
- **Redefinition of a virtual column with another kind**: the attributes of the previous kind are removed. (A3.7)
- **`static=True` and `*`**: `*` gives the physical columns, then the static virtual columns. (A3.9)
- **`bagItemColumn`**: XPath and cast on PostgreSQL; SQLite refuses it at compile time. (A3.11)
- **`relation_name=`**: names the inverse relation `@<relation_name>`. (A4.3)
- **Default inverse name and `one_one='*'`**: `pkg_tbl_col` by default, the many table name with `'*'`. (A4.4)
- **`one_name`, `many_name`, `one_group`, `many_group`, `many_order_by`**: stored in the joiner, with the FK `group` moved to `one_group`. (A4.5)
- **To-one path `@fkey_col.col`**: one LEFT JOIN reused in columns, `where` and `order_by`. (A4.7)
- **Multi-hop path `@a.@b.c`**: resolved recursively; the form `@a.b.c` fails with `KeyError 'joiner'`. (A4.8)
- **Relation on a composite key**: member pairs joined with AND between compositeColumns. (A4.10)
- **`relations` Bag of table and model**: same registration algorithm and tree with joiner. (A4.15)
- **`eager_one`, `eager_many`, `external_relation`, `resolver_kwargs`, `onDuplicate`**: copied into the joiner with the same values. (A4.22)

## Query

### Missing

(a2-1)=
#### `columns=None` <span class="asq-label asq-label-temporary">temporary</span>

In GenroPy you wrote:

```python
rows = tblobj.query(columns=None).fetch()
```

In GenroPy you got: `None` or an empty string became `'*'`, so the query read every column.

In asqueel: `query(columns=None)` and `query(columns='')` raise `UnsupportedFeatureError` with the message `columns=None is not available in this release` (or `columns='' is not available in this release`).

Workaround: omit `columns`. The default is `'*'`.

```python
rows = db.table('sales.invoice').query().fetch()
```

Notes: the refusal is listed in the limitations page.

<details><summary>Files</summary>

- GenroPy: `gnrpy/gnr/sql/gnrsqldata/query.py:157`
- asqueel: `src/asqueel/application_table.py:383`
- asqueel: `src/asqueel/application_table.py:385-386`
- asqueel: `docs/guide/limitations.md:219`

</details>

(a2-3)=
#### Prefixed wildcards `'*@rel'`, `'*prefix_'` <span class="asq-label asq-label-removed">removed</span>

In GenroPy you wrote:

```python
rows = tblobj.query(columns='*@customer_id').fetch()
```

In GenroPy you got: the wildcard expanded to the columns of the related table. The forms `'*@rel1.@rel2'`, `'*prefix_'`, `'*name'` and `'*@rel.(a,b)'` expanded in the same way.

In asqueel: only `'*'` and explicit columns exist. Any other column starting with `*` raises `UnsupportedFeatureError` with the message `column wildcard '*@customer_id' is not available in this release; use * or explicit columns`.

Workaround: list the related columns explicitly.

```python
rows = db.table('sales.invoice').query(columns='$id, @customer_id.name, @customer_id.city').fetch()
```

Notes: only `*` and explicit columns are kept (see genropy#623 and genropy#1504).

<details><summary>Files</summary>

- GenroPy: `gnrpy/gnr/sql/gnrsqldata/compiler.py:746`
- GenroPy: `gnrpy/gnr/sql/gnrsqldata/compiler.py:776`
- asqueel: `src/asqueel/compiler.py:816-818`
- asqueel: `docs/design/41-deferred-features.md:226`
- asqueel: `docs/adattamenti-legacy.md:178-182`

</details>

(a2-10)=
#### `env_<table>_condition_*` conditions <span class="asq-label asq-label-temporary">temporary</span>

In GenroPy you wrote:

```python
db.updateEnv(env_sales_invoice_condition_open='$closed IS NOT TRUE')
rows = db.table('sales.invoice').query().fetch()
```

In GenroPy you got: every condition found in the environment under `env_sales_invoice_condition_` was added to the WHERE of each query on that table.

In asqueel: the conditions are not read. A key `env_<table>_condition_*` in the environment raises `UnsupportedFeatureError` at execution, with the message `environment key 'env_sales_invoice_condition_open' is not available in this release`.

Workaround: write the condition in the `where` of the query.

```python
rows = db.table('sales.invoice').query(where='$closed IS NOT TRUE').fetch()
```

Notes: the team will discuss this difference; one proposal is to drop the feature.

<details><summary>Files</summary>

- GenroPy: `gnrpy/gnr/sql/gnrsqldata/compiler.py:966`
- asqueel: `src/asqueel/runtime.py:433-437`
- asqueel: `docs/guide/limitations.md:200-201`

</details>

(a2-15)=
#### `ignoreTableOrderBy`, `_storename`, `locale`, `mode`, `checkPermissions`, `aliasPrefix` <span class="asq-label asq-label-temporary">temporary</span>

In GenroPy you wrote:

```python
rows = tblobj.query(columns='$id', ignoreTableOrderBy=True).fetch()
```

In GenroPy you got: the query without the table `order_by`. The other options selected a store, a locale, permission checks or an alias prefix. `mode` was accepted and not passed on.

In asqueel: each of these options raises `UnsupportedFeatureError`, for example `query option 'ignoreTableOrderBy' is not available in this release`. The table `order_by` is applied and cannot be turned off.

Workaround: pass an explicit `order_by`, and put any filter in the `where`.

```python
rows = db.table('sales.invoice').query(columns='$id', order_by='$id').fetch()
```

Notes: `_storename` belongs to the application level, outside this release. The guide pages that say tables have no default ordering are wrong: the table `order_by` is applied.

<details><summary>Files</summary>

- GenroPy: `gnrpy/gnr/sql/gnrsqltable/query.py:130-133`
- GenroPy: `gnrpy/gnr/sql/gnrsqldata/compiler.py:912`
- asqueel: `src/asqueel/application_table.py:42-48`
- asqueel: `src/asqueel/application_table.py:400-403`
- asqueel: `src/asqueel/compiler.py:707-708`

</details>

(a2-21)=
#### `record()` <span class="asq-label asq-label-replaced">replaced</span>

In GenroPy you wrote:

```python
record = tblobj.record(pkey=10, ignoreMissing=True).output('dict')
```

In GenroPy you got: the record with key 10, or an empty Bag when no row matched. A composite key was passed as a string `'[...]'`.

In asqueel you write:

```python
row = db.table('sales.invoice').query(where='$id = :id', id=10).fetchRecord(ignoreMissing=True)
```

In asqueel you get: the single row in the format of `fetch()`, or `None` when no row matches. `table.record()` raises `UnsupportedFeatureError` with the message `record is not available in this release; use query(...).fetchRecord()`.

Notes: `record()` will come back with its own revision. See `fetchRecord()` in the New section.

<details><summary>Files</summary>

- GenroPy: `gnrpy/gnr/sql/gnrsqltable/record.py:309`
- GenroPy: `gnrpy/gnr/sql/gnrsqldata/record.py:224`
- GenroPy: `gnrpy/gnr/sql/gnrsqldata/record.py:353`
- asqueel: `src/asqueel/application_table.py:426-427`
- asqueel: `docs/guide/queries.md:573-574`

</details>

(a2-22)=
#### `record()` selectors, `ignoreDuplicate`, `virtual_columns`, `lazy`, `eager` <span class="asq-label asq-label-temporary">temporary</span>

In GenroPy you wrote:

```python
record = tblobj.record(code='INV-7', ignoreDuplicate=True, virtual_columns='$total').output('dict')
```

In GenroPy you got: a WHERE built from the column keywords (`code = :code`). Duplicates that were logically deleted were dropped first; then `ignoreDuplicate` took the first row. `virtual_columns`, `lazy` and `eager` chose the extra columns and the relation loading.

In asqueel: `record()` raises `UnsupportedFeatureError`. Passed to `query()`, the options `lazy`, `eager`, `virtual_columns`, `ignoreMissing` and `ignoreDuplicate` raise `UnsupportedFeatureError`, for example `query option 'virtual_columns' is not available in this release`.

Workaround: write the `where` and the columns explicitly in `query(...).fetchRecord()`.

```python
row = db.table('sales.invoice').query(columns='*, $total', where='$code = :code', code='INV-7').fetchRecord()
```

Notes: the whole record topic waits for its own revision.

<details><summary>Files</summary>

- GenroPy: `gnrpy/gnr/sql/gnrsqldata/record.py:305`
- GenroPy: `gnrpy/gnr/sql/gnrsqldata/record.py:360-366`
- GenroPy: `gnrpy/gnr/sql/gnrsqldata/compiler.py:1105`
- asqueel: `src/asqueel/application_table.py:426-427`
- asqueel: `src/asqueel/application_table.py:47`

</details>

(a2-23)=
#### Record output modes <span class="asq-label asq-label-temporary">temporary</span>

In GenroPy you wrote:

```python
bag = tblobj.record(pkey=10).output('bag')
```

In GenroPy you got: the record in the chosen mode: `bag` (with resolvers on the relations), `dict`, `record`, `json`, `template`, `sample` or `newrecord`.

In asqueel: there is no record object. `record()` raises `UnsupportedFeatureError`. `fetchRecord()` returns only the `NamedList` row.

Workaround: use the row of `fetchRecord()`, or `dict(row)`.

```python
row = db.table('sales.invoice').query(where='$id = :id', id=10).fetchRecord()
data = dict(row)
```

Notes: the Bag and JSON outputs wait for the revision of `record()`. `newrecord` is tracked in [#28](https://github.com/asqueel-org/asqueel/issues/28).

<details><summary>Files</summary>

- GenroPy: `gnrpy/gnr/sql/gnrsqldata/record.py:263`
- asqueel: `src/asqueel/application_table.py:426-427`
- asqueel: `docs/guide/queries.md:573-574`

</details>

(a2-24)=
#### Cached record copy and its refresh <span class="asq-label asq-label-removed">removed</span>

In GenroPy you wrote:

```python
record = tblobj.record(pkey=10)
first = record.output('dict')
again = record.output('dict')
```

In GenroPy you got: the record object kept its result in a cache. The second call read the cached copy, not the database. There was no method to reload it.

In asqueel: there is no record object and no cache. `fetchRecord()` runs the query at every call, so a second call reads the current row.

```python
row = db.table('sales.invoice').query(where='$id = :id', id=10).fetchRecord()
```

Notes: the cached copy and a `refresh()` method are not kept; data is read again through resolvers.

<details><summary>Files</summary>

- GenroPy: `gnrpy/gnr/sql/gnrsqldata/record.py:313`

</details>

(a2-25)=
#### `readColumns`, `countRecords`, `recordAs`, `cachedRecord`, `tableCachedData`, `db.query` <span class="asq-label asq-label-temporary">temporary</span>

In GenroPy you wrote:

```python
name = tblobj.readColumns(pkey=10, columns='$name')
total = tblobj.countRecords()
```

In GenroPy you got: helpers that read columns, counted rows, converted a record, or read a cached record. `db.query(table)` built a query from the database.

In asqueel: reading `readColumns`, `countRecords`, `recordAs` or `cachedRecord` on a table raises `UnsupportedFeatureError`, for example `readColumns is not available in this release`. `db.query` raises `db.query is not available in this release`. `tableCachedData` does not exist and gives `AttributeError`.

Workaround: use `query(...).fetch()`, `query(...).fetchRecord()` and `query(...).count()`.

```python
row = db.table('sales.customer').query(columns='$name', where='$id = :id', id=10).fetchRecord()
total = db.table('sales.customer').query(exclude_logical_deleted=False, exclude_draft=False).count()
```

<details><summary>Files</summary>

- GenroPy: `gnrpy/gnr/sql/gnrsqltable/crud.py:447`
- GenroPy: `gnrpy/gnr/sql/gnrsqltable/crud.py:476`
- GenroPy: `gnrpy/gnr/sql/gnrsqltable/record.py:346`
- GenroPy: `gnrpy/gnr/sql/gnrsqltable/record.py:183`
- GenroPy: `gnrpy/gnr/sql/gnrsqltable/record.py:241`
- GenroPy: `gnrpy/gnr/sql/gnrsql/query.py:253`
- asqueel: `src/asqueel/application_table.py:376-379`
- asqueel: `src/asqueel/runtime.py:60`
- asqueel: `docs/guide/limitations.md:214-218`

</details>

(a2-26)=
#### `sqlWhereFromBag`, `whereTranslator`, `opTranslate` <span class="asq-label asq-label-temporary">temporary</span>

In GenroPy you wrote:

```python
where, sqlArgs = tblobj.sqlWhereFromBag(wherebag)
```

In GenroPy you got: a WHERE clause and its parameters, built from a Bag by the adapter translator.

In asqueel: reading `sqlWhereFromBag` or `whereTranslator` on a table raises `UnsupportedFeatureError`, for example `sqlWhereFromBag is not available in this release`. `db.whereTranslator` raises `db.whereTranslator is not available in this release`. `opTranslate` does not exist and gives `AttributeError`.

Workaround: the caller writes the `where` with bound parameters.

```python
rows = db.table('sales.invoice').query(where='$total >= :minimum', minimum=100).fetch()
```

<details><summary>Files</summary>

- GenroPy: `gnrpy/gnr/sql/gnrsqltable/query.py:91`
- GenroPy: `gnrpy/gnr/sql/gnrsqltable/query.py:95`
- GenroPy: `gnrpy/gnr/sql/gnrsqltable/query.py:85`
- asqueel: `src/asqueel/application_table.py:380-381`
- asqueel: `src/asqueel/runtime.py:61`
- asqueel: `docs/guide/limitations.md:214-218`

</details>

(a3-20)=
#### Dialect macros `#TSQUERY`, `#TSRANK`, `#TSHEADLINE`, `#VECQUERY`, `#VECRANK` <span class="asq-label asq-label-temporary">temporary</span>

In GenroPy you wrote:

```python
rows = tblobj.query(columns='$id', where='#TSQUERY($body, :search)', search='invoice').fetch()
```

In GenroPy you got: the PostgreSQL adapter expanded the macro into full-text or vector SQL, in formulas and in the WHERE.

In asqueel: each macro raises `UnsupportedFeatureError` with a message that names it, for example `macro #TSQUERY is not available in this release`.

Workaround: write the full-text SQL explicitly in a `sql_formula` or in the `where`.

```python
rows = db.table('app.doc').query(columns='$id', where="to_tsvector($body) @@ plainto_tsquery(:search)", search='invoice').fetch()
```

<details><summary>Files</summary>

- GenroPy: `gnrpy/gnr/sql/gnrsqldata/compiler.py:421`
- GenroPy: `gnrpy/gnr/sql/gnrsqldata/compiler.py:964`
- GenroPy: `gnrpy/gnr/sql/adapters/_gnrbasepostgresadapter.py:13-46`
- asqueel: `src/asqueel/compiler.py:649-656`
- asqueel: `tests/test_specific_errors.py:109`
- asqueel: `tests/object_tree/test_phase4_macros.py:80-83`

</details>

(a3-24)=
#### `#PREF(path[,default])` <span class="asq-label asq-label-temporary">temporary</span>

In GenroPy you wrote:

```python
tbl.formulaColumn('vat', sql_formula='$amount * #PREF(vat_rate,0.22)')
```

In GenroPy you got: the package preference at `vat_rate` (or the default) written into the SQL as literal text.

In asqueel: `#PREF` raises `UnsupportedFeatureError` with the message `macro #PREF is not available in this release`.

Workaround: use a `var_*` parameter of the formula or an `:env_<name>` parameter.

```python
tbl.formulaColumn('vat', '$amount * :env_vat_rate', dtype='N')
```

<details><summary>Files</summary>

- GenroPy: `gnrpy/gnr/sql/gnrsqldata/compiler.py:315-319`
- GenroPy: `gnrpy/gnr/sql/gnrsqldata/compiler.py:428`
- asqueel: `src/asqueel/compiler.py:649-656`
- asqueel: `tests/test_specific_errors.py:109`
- asqueel: `tests/object_tree/test_phase4_macros.py:80-83`

</details>

### Different

(a2-4)=
#### Automatic `pkey` column

In GenroPy you wrote:

```python
rows = tblobj.query(columns='$name').fetch()
```

In GenroPy you got: rows with an extra column `pkey`, because `addPkeyColumn` defaulted to `True`. The column was not added to aggregating queries.

In asqueel you write:

```python
rows = db.table('sales.customer').query(columns='$name', addPkeyColumn=True).fetch()
```

In asqueel you get: the `pkey` column only with `addPkeyColumn=True`. The default is `False`: without the option the row has no `pkey`.

Notes: the implicit `pkey` column belongs to a future GenroPy adapter, not to the core.

<details><summary>Files</summary>

- GenroPy: `gnrpy/gnr/sql/gnrsqltable/query.py:130`
- GenroPy: `gnrpy/gnr/sql/gnrsqldata/compiler.py:949`
- asqueel: `src/asqueel/compiler.py:738-739`
- asqueel: `src/asqueel/compiler.py:692`
- asqueel: `docs/adattamenti-legacy.md:118-126`
- asqueel: `docs/guide/limitations.md:236-237`

</details>

(a2-8)=
#### Keyword arguments as query parameters

In GenroPy you wrote:

```python
rows = tblobj.query(where='$total >= :minimum', minimun=100).fetch()
```

In GenroPy you got: every keyword became a parameter. A keyword the query did not use (here the misspelled `minimun`) was ignored without notice.

In asqueel you write:

```python
rows = db.table('sales.invoice').query(where='$total >= :minimum', minimun=100).fetch()
```

In asqueel you get: the same parameters, and the query runs. At compilation `UnusedQueryParameterWarning` names the unused keyword and the parameters the query uses: `query keyword 'minimun' is not used by the query; its parameters are: minimum`.

<details><summary>Files</summary>

- GenroPy: `gnrpy/gnr/sql/gnrsqldata/query.py:162`
- asqueel: `src/asqueel/application_table.py:408`
- asqueel: `src/asqueel/application_table.py:103-112`
- asqueel: `src/asqueel/contracts.py:31`
- asqueel: `docs/guide/queries.md:276-279`

</details>

(a2-12)=
#### `for_update`

In GenroPy you wrote:

```python
rows = tblobj.query(columns='$customer_id', group_by='$customer_id', for_update=True).fetch()
```

In GenroPy you got: `FOR UPDATE` in the SQL, with `bagFields` forced on. With `distinct` or `group_by` the database refused the statement at execution.

In asqueel you write:

```python
rows = db.table('sales.invoice').query(columns='$id', for_update='NOWAIT').fetch()
```

In asqueel you get: `bagFields` forced on, as in GenroPy. `for_update` accepts `True`, `'NOWAIT'` and `'SKIP LOCKED'`. With `distinct` or `group_by`, `query()` raises `UnsupportedFeatureError` with the message `for_update is incompatible with distinct or group_by`, before any SQL runs.

Notes: PostgreSQL does not lock grouped rows, so the error comes at construction.

<details><summary>Files</summary>

- GenroPy: `gnrpy/gnr/sql/gnrsqldata/query.py:176`
- asqueel: `src/asqueel/compiler.py:729`
- asqueel: `src/asqueel/compiler.py:694-695`
- asqueel: `src/asqueel/application_table.py:406-407`
- asqueel: `docs/guide/queries.md:483-484`

</details>

(a2-14)=
#### Partition filter and `ignorePartition`

In GenroPy you wrote:

```python
tbl = pkg.table('document', pkey='id', partition_organization_id='organization')
rows = db.table('app.document').query().fetch()
```

In GenroPy you got: `$organization_id = :env_current_organization` when `current_organization` was set, else the `allowed_organization` filter. With neither key, a column `@organization_id.__allowed_partition` on the related table gave the filter `@organization_id.__allowed_partition IS TRUE`.

In asqueel you write:

```python
with db.tempEnv(current_organization=10):
    rows = db.table('app.document').query().fetch()
```

In asqueel you get: the same `current_<path>` and `allowed_<path>` filters. False values and a missing key give no filter. The fallback on `__allowed_partition` does not exist: with neither key, the query has no partition filter. `ignorePartition=True` removes the filter, as in GenroPy.

Notes: the behaviour follows GenroPy for now; a review is open for discussion. The missing fallback has no issue.

<details><summary>Files</summary>

- GenroPy: `gnrpy/gnr/sql/gnrsqldata/compiler.py:971`
- GenroPy: `gnrpy/gnr/sql/gnrsqltable/columns.py:85-100`
- asqueel: `src/asqueel/compiler.py:876-891`
- asqueel: `docs/guide/limitations.md:196-197`
- asqueel: `docs/guide/legacy.md:48-54`

</details>

(a3-17)=
#### `#THIS`, `#IN_RANGE`, `#PERIOD`

In GenroPy you wrote:

```python
tbl.column('tier_id').relation('app.tier.id', cnd='#IN_RANGE($total,@tier_id.low,@tier_id.high)')
```

In GenroPy you got: `#THIS` in formulas, `#IN_RANGE` in formulas, in relation conditions and in the WHERE, and `#PERIOD` in the WHERE only.

In asqueel you write:

```python
owner.formulaColumn('within', '#IN_RANGE($id,:low,:high)', var_low=0, var_high=9, dtype='B')
```

In asqueel you get: `#THIS`, `#IN_RANGE` in formulas and in the WHERE, and `#PERIOD` in the WHERE, expanded as in GenroPy. `#PERIOD` uses the environment `workdate` and `locale`. `#IN_RANGE` in the `cnd` of a relation raises `UnsupportedFeatureError` with the message `macro #IN_RANGE is not available in this release`.

Notes: `#IN_RANGE` in a relation condition has no issue.

<details><summary>Files</summary>

- GenroPy: `gnrpy/gnr/sql/gnrsqldata/compiler.py:74`
- GenroPy: `gnrpy/gnr/sql/gnrsqldata/compiler.py:614`
- GenroPy: `gnrpy/gnr/sql/gnrsqldata/compiler.py:963`
- asqueel: `src/asqueel/compiler.py:258`
- asqueel: `src/asqueel/compiler.py:827-858`
- asqueel: `src/asqueel/compiler.py:429`
- asqueel: `tests/object_tree/test_phase4_macros.py:49-78`

</details>

(a3-18)=
#### `#ENV(name[,fallback])`

In GenroPy you wrote:

```python
tbl.formulaColumn('who', sql_formula='#ENV(user)')
```

In GenroPy you got: the environment value, then the fallback key, then the `env_user()` table method, written as quoted text without doubling the quotes. With no key and no method, the text `Not found user` went into the SQL.

In asqueel you write:

```python
with db.tempEnv(user="O'Hara"):
    rows = db.table('app.customer').query(columns='$who').fetch()
```

In asqueel you get: the same lookup order, only in the `sql_formula` of a `formulaColumn`. Quotes in the value are doubled, so `O'Hara` is valid SQL. With no key and no method, a `ValueError` names the key: `app.customer.ghost: #ENV(ghost) finds no environment key 'ghost' and no method env_ghost`. `#ENV` anywhere else raises `ValueError` with the message `#ENV is expanded only in a formulaColumn sql_formula`.

Notes: the doubled quotes and the explicit errors have no issue.

<details><summary>Files</summary>

- GenroPy: `gnrpy/gnr/sql/gnrsqldata/compiler.py:321-350`
- GenroPy: `gnrpy/gnr/sql/gnrsqldata/compiler.py:427`
- asqueel: `src/asqueel/compiler.py:239-240`
- asqueel: `src/asqueel/compiler.py:266-277`
- asqueel: `src/asqueel/compiler.py:651-652`
- asqueel: `tests/test_subquery_aggr_and_macros.py:66-95`
- asqueel: `docs/guide/formulas.md:303-317`

</details>

(a3-19)=
#### `#BAG` and `#BAGCOLS` in columns

In GenroPy you wrote:

```python
rows = tblobj.query(columns='$id, #BAG(@customer_id.payload) AS doc').fetch()
```

In GenroPy you got: the column in the SQL, then a Bag decoded after the fetch. A relation path was accepted.

In asqueel you write:

```python
rows = db.table('app.customer').query(columns='$id,#BAG($payload) AS doc', order_by='$id').fetch()
```

In asqueel you get: a Bag in `doc`, decoded after `fetch()`, `fetchRecord()` and the cursor. `#BAGCOLS` spreads the leaves into columns such as `payload_value`. A relation path raises `ValueError`: `#BAG takes a column of the queried table, not the relation path @customer_id.payload`. `#BAG` outside the columns raises `ValueError` with the message `#BAG is expanded only in the query columns`.

Notes: the refusal of a relation path has no issue.

<details><summary>Files</summary>

- GenroPy: `gnrpy/gnr/sql/gnrsqldata/compiler.py:69-70`
- GenroPy: `gnrpy/gnr/sql/gnrsqldata/compiler.py:1283-1316`
- GenroPy: `gnrpy/gnr/sql/gnrsqldata/query.py:282-300`
- asqueel: `src/asqueel/compiler.py:716-718`
- asqueel: `src/asqueel/compiler.py:279-286`
- asqueel: `src/asqueel/application_table.py:142-150`
- asqueel: `src/asqueel/compiler.py:653-654`
- asqueel: `tests/test_subquery_aggr_and_macros.py:106`

</details>

### New

(a2-27)=
#### `query(...).fetchRecord(ignoreMissing=False)`

In asqueel you write:

```python
customer = db.table('sales.customer')
first = customer.query(where='$id = :id', id=1).fetchRecord()
missing = customer.query(where='$id = :id', id=99).fetchRecord(ignoreMissing=True)
lowest = customer.query(order_by='$id').fetchRecord()
```

In asqueel you get: the single row in the format of `fetch()`. No row raises `RecordNotFoundError`, or returns `None` with `ignoreMissing=True`. Several rows raise `RecordMultipleRowsError`. With an explicit `order_by` the query compiles with `LIMIT 1` and returns the first row. Every call executes the query.

Notes: GenroPy has no equivalent query terminal; it reads one record with `record()`.

<details><summary>Files</summary>

- GenroPy: `gnrpy/gnr/sql/gnrsqltable/record.py:309`
- asqueel: `src/asqueel/application_table.py:222-242`
- asqueel: `src/asqueel/table_crud.py:79-84`
- asqueel: `src/asqueel/table_crud.py:66-67`
- asqueel: `docs/guide/queries.md:562-574`

</details>

(a3-23)=
#### `#TEMPLATE` macro

In asqueel you write:

```python
query = model.table('app.person').query(
    "#TEMPLATE('${i}: ${n}', $id AS i, $name AS n) AS tag",
    where="#TEMPLATE('${n}!', $name AS n) = :value", sqlparams={'value': 'Ada!'})
```

In asqueel you get: the template expanded into the string concatenation of the dialect, here `'1: Ada'`. A NULL argument becomes empty text. `$$` writes a literal `$`. The macro works in `sql_formula`, in columns, `where`, `order_by`, `group_by` and `having`.

Notes: GenroPy has no such SQL macro; its `templateColumn` is a Python template on the record.

<details><summary>Files</summary>

- GenroPy: `gnrpy/gnr/app/gnrdbo.py:1250`
- asqueel: `src/asqueel/compiler.py:65-102`
- asqueel: `src/asqueel/adapters/base.py:98`
- asqueel: `src/asqueel/adapters/sqlite.py:206`
- asqueel: `tests/test_template_macro.py:71`

</details>

### Same

- **`'*'` expansion and `bagFields`**: physical columns, then static virtual columns; X columns only with `bagFields` or `for_update`. (A2.2)
- **Automatic result names**: `@customer_id.name` is named `_customer_id_name`, as with GenroPy `colToAs`. (A2.5)
- **`$col`, `$pkey`, `@rel` references**: resolved in columns, `where` and `order_by` as in GenroPy. (A2.6)
- **Symbolic parameters**: a `$col` or `@rel` value of a WHERE parameter is embedded as in GenroPy `embedFieldPars`. (A2.7)
- **`:env_<name>` parameters**: read from the environment at each execution; an explicit parameter wins. (A2.9)
- **`distinct`, `group_by`, `having`, `limit`, `offset`**: same clauses; a false `limit` or `offset` emits no clause. (A2.11)
- **`excludeLogicalDeleted` and `excludeDraft`**: same filters in the same order, `'mark'` included. (A2.13)
- **`fetch()`**: `NamedList` rows from a query compiled once, then `#BAG` decoding. (A2.16)
- **Fetch terminals**: `fetchAsDict`, `fetchAsBag`, `fetchGrouped`, `fetchPkeys`, `fetchAsJson`, `cursor`, `servercursor`, `serverfetch`, `iterfetch` keep the GenroPy signatures. (A2.17)
- **`count()`**: same algorithm; `limit` and `offset` are kept, so `offset=1` gives 0. (A2.18)
- **`compiled`, `sqltext`, `sqlparams`, `test()`**: compiled once and kept; `test()` returns `(sqltext, sqlparams)`. (A2.19)
- **Formula references `$col`, `@rel.col`, `:param`, `:env_*`**: resolved on the table that owns the formula. (A3.16)

## Read-Write

### Missing

(a5-17)=
#### `raw_insert`, `raw_update`, `raw_delete` and `insertMany` <span class="asq-label asq-label-replaced">replaced</span>

In GenroPy you wrote:

```python
tbl.raw_insert(record)
tbl.raw_update(record, old_record=old)
tbl.insertMany(records)
```

In GenroPy you got: writes without table triggers, but `_onDbChange` still ran with `_raw=True`. `insertMany` assigned `newPkeyValue` to missing keys and used the columns of the first record.

In asqueel you write:

```python
customer.sql_insert([{"id": 11, "name": "Grace"}, {"id": 12, "name": "Alan"}])
customer.sql_update({"id": 11, "name": "Grace Hopper"})
customer.sql_delete({"id": 12})
```

In asqueel you get: SQL only, with no triggers and no `_onDbChange`. `sql_insert` takes one record or a list. A missing key is assigned as `checkPkey` does; in a list each further integer key is the next integer. A list runs one `executemany` per group of consecutive records with the same columns. `sql_insert` does not refuse a table whose declarations the write cycle does not execute. `raw_insert`, `raw_update`, `raw_delete` and `insertMany` raise `AttributeError`.

<details><summary>Files</summary>

- GenroPy: `gnrpy/gnr/sql/gnrsqltable/crud.py:67`
- GenroPy: `gnrpy/gnr/sql/gnrsql/write.py:180-220`
- GenroPy: `gnrpy/gnr/sql/adapters/_gnrbaseadapter.py:821`
- asqueel: `src/asqueel/application_table.py:434-477`
- asqueel: `src/asqueel/write_compiler.py:136-150`
- asqueel: `tests/write_compiler/test_write_compiler.py:266`

</details>

(a5-18)=
#### `sql_deleteSelection` <span class="asq-label asq-label-replaced">replaced</span>

In GenroPy you wrote:

```python
tbl.sql_deleteSelection(where='$total < :minimum', minimum=10)
```

In GenroPy you got: the keys were read with a lock, then one `DELETE ... IN :pkeyList` ran without triggers.

In asqueel you write:

```python
deleted = tbl.query(where="$total < :minimum", minimum=10).sql_delete()
```

In asqueel you get: one `DELETE ... WHERE (pk) IN (SELECT ...)` with the filters, order and limit of the query, without triggers. The result is the number of deleted rows. A query with `group_by` or `having` is refused. `sql_deleteSelection` raises `AttributeError`.

<details><summary>Files</summary>

- GenroPy: `gnrpy/gnr/sql/gnrsqltable/crud.py:280-295`
- asqueel: `src/asqueel/application_table.py:244-255`
- asqueel: `src/asqueel/write_compiler.py:227-231`
- asqueel: `tests/write_compiler/test_write_compiler.py:253`

</details>

(a5-20)=
#### `deleteSelection` <span class="asq-label asq-label-replaced">replaced</span>

In GenroPy you wrote:

```python
tbl.deleteSelection(where='$status = :s', s='closed')
```

In GenroPy you got: the rows were read with a lock, then `delete(r)` ran for each row. Draft and logically deleted rows were included by default. The result was the selection.

In asqueel you write:

```python
rows = tbl.query(where="$status = :s", s="closed").delete()
```

In asqueel you get: the query is run again with every physical column, the `X` columns and `for_update=True`. Then `delete()` runs for each row through the write cycle, with the key as a string, so a row already removed by a cascade is skipped. The result is the list of rows. The query's default filters apply: draft and logically deleted rows are excluded. A query with `group_by` or `having` is refused. `deleteSelection` raises `AttributeError`.

<details><summary>Files</summary>

- GenroPy: `gnrpy/gnr/sql/gnrsqltable/crud.py:297-324`
- asqueel: `src/asqueel/application_table.py:264-272`
- asqueel: `src/asqueel/application_table.py:292-302`
- asqueel: `tests/test_selection_writes_legacy.py:82`

</details>

(a5-21)=
#### `batchUpdate` <span class="asq-label asq-label-temporary">temporary</span>

In GenroPy you wrote:

```python
tbl.batchUpdate({'note': 'Reviewed'}, where='$total >= :m', m=100, autocommit=True)
```

In GenroPy you got: the rows were read with a lock, the updater (dict or callable) was applied, and `update()` ran for each row. Options covered `_raw_update`, `autocommit` and `deferredTotalize`.

In asqueel: `batchUpdate` does not exist and raises `AttributeError`. `query(...).update(updater)` covers the dict or callable updater through the write cycle. `query(...).sql_update(values)` writes in one statement without hooks.

Notes: batchUpdate is a high-level API, outside this release ([#32](https://github.com/asqueel-org/asqueel/issues/32)).

<details><summary>Files</summary>

- GenroPy: `gnrpy/gnr/sql/gnrsqltable/crud.py:349-387`
- GenroPy: `gnrpy/gnr/sql/gnrsqltable/crud.py:389-436`

</details>

(a5-22)=
#### `recordToUpdate` <span class="asq-label asq-label-temporary">temporary</span>

In GenroPy you wrote:

```python
with tbl.recordToUpdate(pkey) as record:
    record['status'] = 'closed'
```

In GenroPy you got: a context manager that read the row with a lock, then ran update, insert (`insertMissing`) or delete (`pkey` False), also as raw writes.

In asqueel: `recordToUpdate` does not exist and raises `AttributeError`. Read the row with `query(..., for_update=True).fetchRecord()` and call `update(record, old_record)`.

Notes: recordToUpdate is a high-level API, outside this release ([#17](https://github.com/asqueel-org/asqueel/issues/17)).

<details><summary>Files</summary>

- GenroPy: `gnrpy/gnr/sql/gnrsqltable/crud.py:345`
- GenroPy: `gnrpy/gnr/sql/gnrsqltable/helpers.py:190`

</details>

(a5-24)=
#### `newrecord`, `defaultValues`, `extendDefaultValues`, `recordCopy` <span class="asq-label asq-label-temporary">temporary</span>

In GenroPy you wrote:

```python
record = tbl.newrecord(assignId=True, name='Ada')
```

In GenroPy you got: a new record filled with the declared defaults (`defaultValues`, `defaultFrom`), optionally with a new key or copied from another record.

In asqueel: these methods do not exist and raise `AttributeError`. A column that declares `default` or `default_from` blocks the write cycle: `UnsupportedFeatureError` "<table>: write execution of n.default is not available in this release". Set initial values in the caller or in `trigger_onInserting`.

Notes: [#28](https://github.com/asqueel-org/asqueel/issues/28).

<details><summary>Files</summary>

- GenroPy: `gnrpy/gnr/sql/gnrsqltable/record.py:161-177`
- GenroPy: `gnrpy/gnr/sql/gnrsqltable/record.py:600`
- asqueel: `src/asqueel/model_source.py:251`

</details>

(a5-25)=
#### `touchRecords` <span class="asq-label asq-label-temporary">temporary</span>

In GenroPy you wrote:

```python
tbl.touchRecords(where='$status = :s', s='open')
```

In GenroPy you got: the selected records were saved again, or a method was applied to each of them.

In asqueel: `touchRecords` does not exist and raises `AttributeError`. `query(...).update()` with an empty updater runs the update cycle on each row.

<details><summary>Files</summary>

- GenroPy: `gnrpy/gnr/sql/gnrsqltable/triggers.py:52-100`

</details>

(a5-26)=
#### `_onDbChange` effects: `totalizer_<x>`, `logChanges`, `notify` <span class="asq-label asq-label-temporary">temporary</span>

In GenroPy you wrote:

```python
tbl = pkg.table('invoice', pkey='id', logChanges=True, notify=True)
```

In GenroPy you got: after every write `_onDbChange` updated the totalizers, wrote the change log and sent `NOTIFY 'dbevent'`.

In asqueel: there is no `_onDbChange` on the database. `totalizer_<x>`, `logChanges` and `notify` are refused by the table grammar as undeclared attributes. Use after-triggers of the application or database triggers.

<details><summary>Files</summary>

- GenroPy: `gnrpy/gnr/sql/gnrsql/write.py:50-85`
- GenroPy: `gnrpy/gnr/sql/gnrsql/write.py:87-131`
- asqueel: `docs/guide/hooks.md:120-128`

</details>

(a5-29)=
#### `check_updatable`, `check_deletable`, `isDraft`, `islocked_*`, `hasProtectionColumns` <span class="asq-label asq-label-temporary">temporary</span>

In GenroPy you wrote:

```python
if tbl.check_deletable(record):
    tbl.delete(record)
```

In GenroPy you got: a boolean answer from `protect_*` without an exception, from the table `readOnly` setting and from the draft field.

In asqueel: these methods do not exist and raise `AttributeError`. The `draftField` property exists. Catch the exceptions that `protect_*` raises.

<details><summary>Files</summary>

- GenroPy: `gnrpy/gnr/sql/gnrsqltable/triggers.py:152`
- GenroPy: `gnrpy/gnr/sql/gnrsqltable/triggers.py:186-231`
- asqueel: `src/asqueel/object_tree.py:280`

</details>

(a5-30)=
#### Table helpers: `setColumns`, `changePrimaryKeyValue`, `empty`, `fillFromSqlTable`, `duplicateRecord`, copy and paste <span class="asq-label asq-label-temporary">temporary</span>

In GenroPy you wrote:

```python
tbl.setColumns(pkey, status='closed')
tbl.duplicateRecord(pkey, howmany=2)
```

In GenroPy you got: helpers that changed columns, changed a key, emptied a table, copied from another table, or duplicated and copied records.

In asqueel: these methods do not exist and raise `AttributeError`. Use `query(...).fetchRecord()`, `update`, `insert` and `query(...).sql_delete()`.

Notes: recordCopy is tracked in [#28](https://github.com/asqueel-org/asqueel/issues/28).

<details><summary>Files</summary>

- GenroPy: `gnrpy/gnr/sql/gnrsqltable/crud.py:438`
- GenroPy: `gnrpy/gnr/sql/gnrsqltable/copy.py:251`

</details>

(a6-7)=
#### Database stores: `storename`, `use_store`, multiple stores <span class="asq-label asq-label-temporary">temporary</span>

In GenroPy you wrote:

```python
with db.tempEnv(storename='customer_a'):
    tbl.query().fetch()
```

In GenroPy you got: the connection of that store. `'*'` or a list ran the statement on several stores in parallel. `use_store`, `currentStorename`, `connection`, `connectionKey` and `get_dbname` worked on the stores.

In asqueel: a `storename` in the environment other than `'_main_db'` raises `UnsupportedFeatureError` "environment key storename='customer_a': database stores are not available in this release". `execute(storename=...)` raises "storename is not available in this release". `use_store`, `currentStorename`, `connection`, `connectionKey` and `get_dbname` do not exist. Use one `AsqueelDb` per physical database, or a declared named connection.

<details><summary>Files</summary>

- GenroPy: `gnrpy/gnr/sql/gnrsql/env.py:131`
- GenroPy: `gnrpy/gnr/sql/gnrsql/connections.py:104-121`
- GenroPy: `gnrpy/gnr/sql/gnrsql/execute.py:137-145`
- asqueel: `src/asqueel/runtime.py:123-126`
- asqueel: `src/asqueel/runtime.py:203-206`

</details>

(a6-14)=
#### `autoCommit`, `dbevents`, `systemDbEvent`, `notifyDbUpdate` <span class="asq-label asq-label-temporary">temporary</span>

In GenroPy you wrote:

```python
tbl.notifyDbUpdate(record)
db.autoCommit()
```

In GenroPy you got: database events collected in the environment and sent to the application, and a commit raising `GnrMissedCommitException` when events were left.

In asqueel: these names do not exist on the database or on the table. Use `deferAfterCommit` for application notifications.

<details><summary>Files</summary>

- GenroPy: `gnrpy/gnr/sql/gnrsql/transactions.py:210-233`
- GenroPy: `gnrpy/gnr/sql/gnrsql/helpers.py:152`
- GenroPy: `gnrpy/gnr/sql/gnrsqltable/triggers.py:45-50`

</details>

(a6-16)=
#### NOTIFY: table attribute `notify`, `db.notify`, `db.listen` <span class="asq-label asq-label-temporary">temporary</span>

In GenroPy you wrote:

```python
db.listen('dbevent', cb)
db.notify('dbevent', payload)
```

In GenroPy you got: `LISTEN` and `NOTIFY` delegated to the adapter. A table with `notify` sent `NOTIFY 'dbevent'` after every write.

In asqueel: `db.listen` and `db.notify` do not exist. The table attribute `notify` raises `ValueError` "Element 'table' does not accept 'notify'". The write cycle sends no NOTIFY. Run `NOTIFY` yourself with `db.execute`.

<details><summary>Files</summary>

- GenroPy: `gnrpy/gnr/sql/gnrsql/write.py:87-131`
- GenroPy: `gnrpy/gnr/sql/gnrsql/transactions.py:289-305`
- asqueel: `src/asqueel/db_write.py:5`

</details>

### Different

(a5-1)=
#### `insert`

In GenroPy you wrote:

```python
record = tbl.insert({'id': 3, 'name': 'Katherine'})
```

In GenroPy you got: the cycle `checkPkey`, `protect_validate`, column triggers, table triggers, package triggers, counters, `dbo_onInserting`, `protect_draft`, INSERT, `_onDbChange`, after-triggers. The record was returned.

In asqueel you write:

```python
record = customer.insert({"id": 3, "name": "Katherine"})
```

In asqueel you get: the same order without package triggers, `dbo_onInserting` and `_onDbChange`. The record is returned. A table with declarations the cycle does not execute is refused with `UnsupportedFeatureError` before any hook.

<details><summary>Files</summary>

- GenroPy: `gnrpy/gnr/sql/gnrsqltable/crud.py:57`
- GenroPy: `gnrpy/gnr/sql/gnrsql/write.py:134-168`
- asqueel: `src/asqueel/table_crud.py:31-34`
- asqueel: `src/asqueel/db_write.py:21-33`
- asqueel: `src/asqueel/model_source.py:231`

</details>

(a5-2)=
#### `update`

In GenroPy you wrote:

```python
tbl.update(record, old_record=old)
tbl.update(record, pkey='["a", "2026-01-01::D"]')
```

In GenroPy you got: the update cycle. The package storename was set in `tempEnv`. A composite key was the serialized string.

In asqueel you write:

```python
customer.update(record, old_record)
customer.update({"id": 3, "name": "Katherine Johnson"})
```

In asqueel you get: the key comes from `old_record`, then `pkey`, then the record. A composite key is the serialized string (`toTypedJSON`); a tuple or mapping raises `ValueError`. There is no storename. `storename` and other extra keyword arguments are accepted and ignored. A missing row raises no error, as in GenroPy.

<details><summary>Files</summary>

- GenroPy: `gnrpy/gnr/sql/gnrsqltable/crud.py:118-148`
- GenroPy: `gnrpy/gnr/sql/gnrsql/write.py:223-265`
- asqueel: `src/asqueel/table_crud.py:36-47`
- asqueel: `src/asqueel/write_compiler.py:186-193`
- asqueel: `src/asqueel/write_compiler.py:253-264`
- asqueel: `tests/write_compiler/test_write_cycle.py:146`

</details>

(a5-3)=
#### `delete` and `deletable`

In GenroPy you wrote:

```python
tbl.delete(pkey)
pkg.table('invoice', pkey='id', deletable='admin')
```

In GenroPy you got: a key string was read with a lock; a dict was deleted as given. `deletable` could be a permission tag. The number of deleted rows was not checked.

In asqueel you write:

```python
db.table("sales.line").delete({"id": 101})
```

In asqueel you get: a key string is read again with `for_update`, outside the draft, logical-deletion and partition filters; a missing key string returns without error. A dict is deleted as given. The DELETE must remove exactly one row, otherwise `RecordNotFoundError`. The WHERE uses the sqlname. `deletable` is only a bool; a string is refused by the validator.

<details><summary>Files</summary>

- GenroPy: `gnrpy/gnr/sql/gnrsqltable/crud.py:103-115`
- GenroPy: `gnrpy/gnr/sql/gnrsql/write.py:294-305`
- asqueel: `src/asqueel/table_crud.py:49-58`
- asqueel: `src/asqueel/db_write.py:68-72`
- asqueel: `src/asqueel/elements.py:177`
- asqueel: `tests/write_compiler/test_write_cycle.py:171`

</details>

(a5-7)=
#### `protect_draft` and `dbo_on*` hooks

In GenroPy you wrote:

```python
def dbo_onUpdating(self, record, old_record=None, **kwargs):
    ...
```

In GenroPy you got: `dbo_onInserting`, `dbo_onUpdating` and `dbo_onDeleting` in the cycle. In update, `dbo_onUpdating` called `protect_draft` and started the logical-deletion cascade.

In asqueel you write:

```python
def protect_draft(self, record):
    return record.get("status") != "confirmed"
```

In asqueel you get: `protect_draft` is called directly, when the table has a `draftField` and defines the method; in update it runs before the counters. The logical-deletion cascade runs in the same position. No `dbo_*` method is called.

<details><summary>Files</summary>

- GenroPy: `gnrpy/gnr/sql/gnrsql/write.py:159-163`
- GenroPy: `gnrpy/gnr/app/gnrdbo.py:1079`
- asqueel: `src/asqueel/db_write.py:29`
- asqueel: `src/asqueel/db_write.py:43-48`
- asqueel: `src/asqueel/db_write.py:77-82`

</details>

(a5-9)=
#### `currentTrigger` and the trigger stack

In GenroPy you wrote:

```python
trigger = self.currentTrigger
parent = trigger.parent
```

In GenroPy you got: the current event, table, record, old_record and parent. Push and pop had no `try/finally`: after an exception the element stayed on the stack.

In asqueel you write:

```python
trigger = self.currentTrigger
parent = trigger.parent
```

In asqueel you get: the same fields, with no `level`. The pop runs also when a hook raises. `sql_*` commands do not enter the stack.

Notes: the fix follows genropy#1688.

<details><summary>Files</summary>

- GenroPy: `gnrpy/gnr/sql/gnrsqltable/triggers.py:107-110`
- GenroPy: `gnrpy/gnr/sql/gnrsql/helpers.py:80-82`
- asqueel: `src/asqueel/triggers.py:9-17`
- asqueel: `src/asqueel/triggers.py:52-57`
- asqueel: `tests/write_compiler/test_write_cycle.py:139`

</details>

(a5-10)=
#### `self.exception`

In GenroPy you wrote:

```python
raise self.exception('protect_update', record=record, msg='locked')
```

In GenroPy you got: the exception named in `EXCEPTIONS`, with the row caption from `recordCaption` and the database localizer.

In asqueel you write:

```python
raise self.exception("protect_update", record=record, msg="locked")
```

In asqueel you get: the same `EXCEPTIONS`. The row caption is the key value, with no localizer: "The record 1 in table app.t is not updatable: locked". An unknown name raises `ValueError`.

<details><summary>Files</summary>

- GenroPy: `gnrpy/gnr/sql/gnrsqltable/table.py:92-118`
- asqueel: `src/asqueel/table_triggers.py:67-77`
- asqueel: `src/asqueel/errors.py:69-77`

</details>

(a5-11)=
#### `deleteRelated` and `onDelete`

In GenroPy you wrote:

```python
tbl.column('invoice_id').relation('sales.invoice.id', onDelete='c')
```

In GenroPy you got: actions `raise`, `cascade`, `setnull`, `ignore` and the short forms `r`, `c`, `n`, `i`. The effective default was `ignore`. The query used `subtable='*'` and skipped the dbstores.

In asqueel you write:

```python
columns.column("invoice_id").relation("sales.invoice.id", onDelete="cascade")
```

In asqueel you get: the same actions, default `ignore`, and a message after `:`. The short forms are refused by the validator with "invalid onDelete". There is no subtable and no dbstore.

<details><summary>Files</summary>

- GenroPy: `gnrpy/gnr/sql/gnrsqltable/crud.py:182-229`
- asqueel: `src/asqueel/table_crud.py:185-207`
- asqueel: `src/asqueel/validators.py:297-301`
- asqueel: `tests/write_compiler/test_write_cycle.py:176`

</details>

(a5-12)=
#### `updateRelated` and `onUpdate`

In GenroPy you wrote:

```python
tbl.column('invoice_id').relation('sales.invoice.id', onUpdate='raise')
```

In GenroPy you got: with an unchanged key the loop stopped at the first relation. `raise` used the name `'update'`, which is not in `EXCEPTIONS`. Without `old_record` an `AttributeError`.

In asqueel you write:

```python
columns.column("invoice_id").relation("sales.invoice.id", onUpdate="raise")
```

In asqueel you get: an unchanged key moves to the next relation. `raise` raises `SaveException` "Record referenced in table app.u". `setnull` is ignored, as in GenroPy. Short forms are refused by the validator. Without `old_record` a `ValueError` "<table>: onUpdate of <relation> requires old_record".

Notes: the fixes follow genropy#1686 and genropy#1687.

<details><summary>Files</summary>

- GenroPy: `gnrpy/gnr/sql/gnrsqltable/crud.py:150-180`
- asqueel: `src/asqueel/table_crud.py:222-243`
- asqueel: `tests/write_compiler/test_write_cycle.py:207`
- asqueel: `tests/write_compiler/test_write_cycle.py:163`

</details>

(a5-13)=
#### Key generation: `checkPkey`, `newPkeyValue`, `pkeyValue`

In GenroPy you wrote:

```python
record = tbl.insert({'name': 'Ada'})
```

In GenroPy you got: `max+1` for an integer key, `getUuid` for a text key, a composite key with `toTypedJSON`, a `__syscode` key with `sysRecord_<code>`.

In asqueel you write:

```python
record = customer.insert({"name": "Ada"})
```

In asqueel you get: the same order of strategies. An integer key gets 1, 2, ...; a text key gets a 22-character UUID from `genro_toolbox` `get_uuid`, ordered by time. `__syscode` does not use `sysRecord_<code>`. A key with `sql_default` is left to the database.

<details><summary>Files</summary>

- GenroPy: `gnrpy/gnr/sql/gnrsqltable/record.py:620`
- GenroPy: `gnrpy/gnr/sql/gnrsqltable/utils.py:75`
- asqueel: `src/asqueel/table_crud.py:96-144`
- asqueel: `tests/test_record_writes_legacy.py:50`

</details>

(a5-15)=
#### Bag value in an `X` column

In GenroPy you wrote:

```python
tbl.insert({'id': 1, 'data': Bag(dict(a=1))})
```

In GenroPy you got: the Bag was written as its `toXml()`, with the `GenRoBag` root and type attributes.

In asqueel you write:

```python
tbl.insert({"id": 1, "data": Bag(dict(a=1))})
```

In asqueel you get: the Bag is written as `to_xml()` of `genro_bag`: `'<a>1</a>'`, without the `GenRoBag` root and the type attributes. An empty Bag becomes NULL.

Notes: the bagfield format depends on genro-bag#72.

<details><summary>Files</summary>

- GenroPy: `gnrpy/gnr/sql/adapters/_gnrbaseadapter.py:742-747`
- asqueel: `src/asqueel/write_compiler.py:117-118`
- asqueel: `tests/test_record_writes_legacy.py:92`

</details>

(a5-23)=
#### `insertOrUpdate`

In GenroPy you wrote:

```python
result = tbl.insertOrUpdate(record)
```

In GenroPy you got: the key was read with a lock; insert if missing, otherwise update with the first row. After an update the result was None.

In asqueel you write:

```python
result = customer.insertOrUpdate(record)
```

In asqueel you get: the key is read with `for_update` and the query's default filters, then insert, or update with the read row as `old_record`. A composite key is the serialized string. The record is returned in both cases.

<details><summary>Files</summary>

- GenroPy: `gnrpy/gnr/sql/gnrsqltable/crud.py:252-263`
- asqueel: `src/asqueel/table_crud.py:60-70`
- asqueel: `src/asqueel/application_table.py:411-424`
- asqueel: `tests/test_record_writes_legacy.py:75`

</details>

(a5-27)=
#### Logical-deletion cascade: `onArchivingRecord`, `archiveRelatedRecords`

In GenroPy you wrote:

```python
def onArchivingRecord(self, record=None, archive_ts=None):
    self.archiveRelatedRecords(record=record, archive_ts=archive_ts)
```

In GenroPy you got: when `__del_ts` changed, `batchUpdate` wrote the logical-deletion field of the children with `onDelete` cascade. The hook `onArchivingRecord` could be overridden.

In asqueel you write:

```python
old = dict(invoice.query(columns="*", where="$id=:pk", pk="o1").fetchRecord())
invoice.update({**old, "__del_ts": datetime.now()}, old_record=old)
```

In asqueel you get: an update with `old_record` that changes the field calls `archiveRelatedRecords`. Children of `onDelete='cascade'` relations with their own `logicalDeletionField` are written with `query(...).update()`, so the cascade is recursive. There is no `onArchivingRecord` hook, no dbstore skip and no `restoreUnifiedRecord`.

<details><summary>Files</summary>

- GenroPy: `gnrpy/gnr/sql/gnrsqltable/copy.py:70-100`
- GenroPy: `gnrpy/gnr/app/gnrdbo.py:1088`
- asqueel: `src/asqueel/table_crud.py:209-220`
- asqueel: `src/asqueel/db_write.py:45-48`
- asqueel: `tests/test_selection_writes_legacy.py:97`

</details>

(a6-2)=
#### `currentEnv`, `updateEnv`, `clearCurrentEnv`

In GenroPy you wrote:

```python
db.currentEnv = {'user': 'ada'}
db.updateEnv(workdate=today)
```

In GenroPy you got: a dict per thread. The setter accepted any value.

In asqueel you write:

```python
db.currentEnv = {"user": "ada"}
snapshot = db.current_env
```

In asqueel you get: a dict per thread. The setter raises `TypeError` "currentEnv must be a dictionary" for another value. `current_env` returns a read-only copy without the deferred queues and `_pendingExceptions`.

<details><summary>Files</summary>

- GenroPy: `gnrpy/gnr/sql/gnrsql/env.py:63-71`
- asqueel: `src/asqueel/runtime.py:147-166`
- asqueel: `src/asqueel/environment.py:100-118`

</details>

(a6-3)=
#### `workdate` and `locale`

In GenroPy you wrote:

```python
locale = db.locale
```

In GenroPy you got: `workdate` fell back to `date.today()`. `locale` fell back to `defaultLocale()`, which validated the identifier and fell back to `en_GB`.

In asqueel you write:

```python
locale = db.locale
```

In asqueel you get: the same `workdate` fallback. `locale` comes from `GNR_LOCALE` or `locale.getlocale()`, without validation: with system locale `'C'` it is `'C'`, and `'xx_INVALID'` stays as it is.

<details><summary>Files</summary>

- GenroPy: `gnrpy/gnr/sql/gnrsql/env.py:75-101`
- GenroPy: `gnrpy/gnr/core/gnrlocale.py:308-313`
- asqueel: `src/asqueel/environment.py:120-134`

</details>

(a6-6)=
#### Connections per thread and per name

In GenroPy you wrote:

```python
with db.tempEnv(connectionName='worker'):
    tbl.insert(record)
```

In GenroPy you got: one connection per thread and `(storename, connectionName)`. Every name used the physical parameters of the store.

In asqueel you write:

```python
with db.tempEnv(connectionName="worker"):
    customer.insert(record)
```

In asqueel you get: one connection per thread and name, opened at the first statement. A name can declare a connection to another physical database. With explicit declarations, an undeclared name raises `ValueError` "Unknown named connection: 'worker'". Operations on a connection must run on the thread that created it.

<details><summary>Files</summary>

- GenroPy: `gnrpy/gnr/sql/gnrsql/connections.py:79-102`
- asqueel: `src/asqueel/runtime.py:128-140`
- asqueel: `src/asqueel/configuration.py:306-320`
- asqueel: `src/asqueel/runtime.py:414-416`

</details>

(a6-8)=
#### `db.commit()`

In GenroPy you wrote:

```python
def trigger_onInserted(self, record):
    self.db.commit()
```

In GenroPy you got: commit of every uncommitted connection with the same connectionName, in all stores, then `onDbCommitted`. Commit was allowed inside a trigger.

In asqueel you write:

```python
db.commit()
```

In asqueel you get: the same order on the selected connection only, then `onDbCommitted`. Inside a write or hook, commit on the connection in use raises `TransactionStateError` "Cannot finish the transaction of a table write or hook in progress". Commit on another named connection is allowed.

Notes: the rule avoids the deadlock of genropy#1621.

<details><summary>Files</summary>

- GenroPy: `gnrpy/gnr/sql/gnrsql/transactions.py:47-93`
- asqueel: `src/asqueel/runtime.py:259-267`
- asqueel: `src/asqueel/runtime.py:520-551`

</details>

(a6-9)=
#### `db.rollback()` and `rollbackAll()`

In GenroPy you wrote:

```python
db.rollback()
db.rollbackAll()
```

In GenroPy you got: `rollback` left the deferred queues and pending exceptions in `currentEnv`; they ran at the next commit. `rollbackAll` emptied them.

In asqueel you write:

```python
db.rollback()
```

In asqueel you get: `rollback` empties the deferred queues and pending exceptions of the connection, as `rollbackAll` did. `rollbackAll` does not exist. Inside a write, rollback is refused as commit is.

Notes: the fix follows genropy#1689.

<details><summary>Files</summary>

- GenroPy: `gnrpy/gnr/sql/gnrsql/transactions.py:252-287`
- asqueel: `src/asqueel/runtime.py:296-298`
- asqueel: `src/asqueel/runtime.py:494-518`

</details>

(a6-10)=
#### Automatic rollback on SQL error

In GenroPy you wrote:

```python
db.execute('INSERT INTO bad_table VALUES (1)')
```

In GenroPy you got: the error was logged, `self.rollback()` ran and the error was raised again.

In asqueel you write:

```python
db.execute("INSERT INTO bad_table VALUES (1)")
```

In asqueel you get: rollback and the original error raised again, also for an error while reading from the cursor. If the rollback fails, the connection is discarded. The deferred queues are emptied.

<details><summary>Files</summary>

- GenroPy: `gnrpy/gnr/sql/gnrsql/execute.py:154-159`
- asqueel: `src/asqueel/runtime.py:463-478`
- asqueel: `src/asqueel/runtime.py:631-640`

</details>

(a6-11)=
#### Python error in a trigger or write hook

In GenroPy you wrote:

```python
try:
    tbl.insert(record)
except ValueError:
    db.commit()
```

In GenroPy you got: the transaction stayed valid. The next commit saved the interrupted write.

In asqueel you write:

```python
try:
    customer.insert(record)
except ValueError:
    db.rollback()
```

In asqueel you get: the connection becomes rollback-only. Commit, `deferToCommit` and new statements raise `TransactionStateError` "Connection is rollback-only; call rollback before reuse" until `rollback()`.

Notes: see genropy#1696.

<details><summary>Files</summary>

- GenroPy: `gnrpy/gnr/sql/gnrsql/helpers.py:56-85`
- asqueel: `src/asqueel/runtime.py:300-318`
- asqueel: `src/asqueel/runtime.py:428-431`

</details>

(a6-13)=
#### `deferredRaise`

In GenroPy you wrote:

```python
self.db.deferredRaise(ValueError('stock below zero'))
```

In GenroPy you got: one global list in `currentEnv['_pendingExceptions']`. Commit raised `GnrException` and did not empty the list, so every later commit raised it again.

In asqueel you write:

```python
self.db.deferredRaise(ValueError("stock below zero"))
```

In asqueel you get: one list per named connection in `currentEnv['_pendingExceptions__main_db_<connectionName>']`. Commit raises `DeferredCommitError`, empties the list and makes the connection rollback-only. A value that is not an exception raises `TypeError`.

Notes: the fix follows genropy#1690.

<details><summary>Files</summary>

- GenroPy: `gnrpy/gnr/sql/gnrsql/transactions.py:131-137`
- GenroPy: `gnrpy/gnr/sql/gnrsql/transactions.py:84-87`
- asqueel: `src/asqueel/runtime.py:373-377`
- asqueel: `src/asqueel/runtime.py:530-536`

</details>

(a6-17)=
#### `db.execute`

In GenroPy you wrote:

```python
cursor = db.execute('SELECT id FROM t', cursorname='*', storename='a')
```

In GenroPy you got: the cursor. `cursorname='*'` created a server cursor.

In asqueel you write:

```python
cursor = db.execute("SELECT id FROM t", cursorname="*")
rows = cursor.fetchall()
```

In asqueel you get: an `SqlCursor` with `description`, `rowcount`, `fetchone`, `fetchmany`, `fetchall`, iteration and `close`. `sql` is a string or a `CompiledQuery`. `cursorname` opens a server cursor on PostgreSQL; SQLite ignores it. `dbtable` has no effect. `storename`, `cursor` and `_adaptArguments=False` raise `UnsupportedFeatureError` "<name> is not available in this release".

<details><summary>Files</summary>

- GenroPy: `gnrpy/gnr/sql/gnrsql/execute.py:47-56`
- asqueel: `src/asqueel/runtime.py:195-216`
- asqueel: `src/asqueel/runtime.py:586-655`

</details>

(a6-18)=
#### `autocommit`

In GenroPy you wrote:

```python
db.execute(sql, autocommit=True)
```

In GenroPy you got: a commit after the statement. A PostgreSQL connection could also be opened in autocommit mode.

In asqueel you write:

```python
db.execute(sql, autocommit=True)
```

In asqueel you get: `db.commit()` after the statement. An autocommit connection is refused: `connect_kwargs` with `autocommit` raises `ValueError` "autocommit is incompatible with explicit transactions".

<details><summary>Files</summary>

- GenroPy: `gnrpy/gnr/sql/gnrsql/execute.py:161-162`
- GenroPy: `gnrpy/gnr/sql/adapters/gnrpostgres3.py:41`
- asqueel: `src/asqueel/runtime.py:214-215`
- asqueel: `src/asqueel/runtime.py:76-77`
- asqueel: `src/asqueel/adapters/postgres.py:32-33`

</details>

(a6-21)=
#### `db.closeConnection()`

In GenroPy you wrote:

```python
db.closeConnection()
```

In GenroPy you got: rollback and close of all connections of the thread. Errors were ignored.

In asqueel you write:

```python
db.closeConnection()
```

In asqueel you get: rollback and close of all connections of the thread, and of their open cursors. The database stays usable. Inside a write it raises `TransactionStateError` "Cannot close connections inside a table write or hook". The first cleanup error is raised after the other connections are closed.

<details><summary>Files</summary>

- GenroPy: `gnrpy/gnr/sql/gnrsql/connections.py:41-57`
- asqueel: `src/asqueel/runtime.py:320-346`

</details>

(a6-25)=
#### `tblobj.lock`

In GenroPy you wrote:

```python
tbl.lock(mode='SHARE', nowait=True)
```

In GenroPy you got: on PostgreSQL a `LOCK` statement with `NO WAIT`. On SQLite nothing.

In asqueel you write:

```python
customer.lock(mode="SHARE", nowait=True)
```

In asqueel you get: on PostgreSQL `LOCK <table> IN <mode> MODE NOWAIT`. A mode that is not a PostgreSQL lock mode raises `ValueError` "lock mode must be one of ...". On SQLite the write lock is taken with an UPDATE without effect.

Notes: the `NOWAIT` fix follows genropy#1692.

<details><summary>Files</summary>

- GenroPy: `gnrpy/gnr/sql/gnrsqltable/crud.py:481-487`
- GenroPy: `gnrpy/gnr/sql/adapters/_gnrbasepostgresadapter.py:319-325`
- asqueel: `src/asqueel/table_crud.py:72-76`
- asqueel: `src/asqueel/write_compiler.py:233-247`

</details>

(a6-26)=
#### `for_update` with a string mode

In GenroPy you wrote:

```python
tbl.query(where='$id = :id', id=1, for_update='SKIP LOCKED').fetch()
```

In GenroPy you got: the string after `FOR UPDATE OF`. On SQLite nothing.

In asqueel you write:

```python
customer.query(where="$id = :id", id=1, for_update="SKIP LOCKED").fetch()
```

In asqueel you get: `for_update` is `True`, `'NOWAIT'` or `'SKIP LOCKED'`, otherwise `ValueError`. PostgreSQL adds the mode after `FOR UPDATE OF`. SQLite refuses a string mode with `UnsupportedFeatureError` "for_update=NOWAIT is not available on SQLite".

<details><summary>Files</summary>

- GenroPy: `gnrpy/gnr/sql/adapters/_gnrbaseadapter.py:717-723`
- asqueel: `src/asqueel/compiler.py:694-695`
- asqueel: `src/asqueel/adapters/sqlite.py:215-218`

</details>

(a6-27)=
#### Transactions and locks on SQLite

In GenroPy you wrote:

```python
tbl.query(where='$id = :id', id=1, for_update=True).fetch()
```

In GenroPy you got: the sqlite3 default implicit transaction. `for_update` and `lockTable` did nothing.

In asqueel you write:

```python
customer.query(where="$id = :id", id=1, for_update=True).fetch()
```

In asqueel you get: `isolation_level='DEFERRED'`: BEGIN before the first INSERT, UPDATE or DELETE; reads open no transaction. `for_update` takes the write lock (`BEGIN IMMEDIATE`, or an UPDATE without effect inside an open transaction). Foreign keys are on by default.

<details><summary>Files</summary>

- GenroPy: `gnrpy/gnr/sql/adapters/gnrsqlite.py:80`
- GenroPy: `gnrpy/gnr/sql/adapters/gnrsqlite.py:140-141`
- asqueel: `src/asqueel/adapters/sqlite.py:54-57`
- asqueel: `src/asqueel/adapters/sqlite.py:111-121`

</details>

(a6-28)=
#### `setConstraintsDeferred()`

In GenroPy you wrote:

```python
db.setConstraintsDeferred()
```

In GenroPy you got: `SET CONSTRAINTS all DEFERRED` on PostgreSQL. No effect on SQLite.

In asqueel you write:

```python
db.setConstraintsDeferred()
```

In asqueel you get: `SET CONSTRAINTS ALL DEFERRED` on PostgreSQL, in the current transaction. `PRAGMA defer_foreign_keys = ON` on SQLite.

<details><summary>Files</summary>

- GenroPy: `gnrpy/gnr/sql/gnrsql/transactions.py:243-250`
- GenroPy: `gnrpy/gnr/sql/adapters/gnrpostgres3.py:347-348`
- asqueel: `src/asqueel/runtime.py:278-280`
- asqueel: `src/asqueel/adapters/sqlite.py:93-95`

</details>

(a6-29)=
#### `analyze()` and `vacuum()`

In GenroPy you wrote:

```python
db.analyze()
db.vacuum(full=True)
```

In GenroPy you got: `ANALYZE` in the current transaction. `VACUUM [FULL] ANALYZE` on a separate autocommit connection, with the same text on SQLite.

In asqueel you write:

```python
db.analyze()
db.vacuum(full=True)
```

In asqueel you get: `analyze` in the current transaction. `vacuum` with pending work on the thread raises `TransactionStateError` "vacuum requires no pending work on this thread; commit or rollback first". PostgreSQL runs `VACUUM [FULL] ANALYZE` on a separate autocommit connection. SQLite runs `VACUUM` on the main file and on every attached schema, then `ANALYZE`.

<details><summary>Files</summary>

- GenroPy: `gnrpy/gnr/sql/gnrsql/transactions.py:307-318`
- GenroPy: `gnrpy/gnr/sql/adapters/_gnrbaseadapter.py:929-948`
- asqueel: `src/asqueel/runtime.py:282-294`
- asqueel: `src/asqueel/adapters/postgres.py:42-49`
- asqueel: `src/asqueel/adapters/sqlite.py:97-109`

</details>

(a6-31)=
#### `db.currentUser`

In GenroPy you wrote:

```python
user = self.db.currentUser
```

In GenroPy you got: the `user` of `currentEnv`, otherwise the user of the current page.

In asqueel you write:

```python
user = self.db.currentUser
```

In asqueel you get: only the `user` value of `currentEnv`. There is no page fallback. The user-field trigger reads it.

<details><summary>Files</summary>

- GenroPy: `gnrpy/gnr/app/gnrapp.py:537-538`
- asqueel: `src/asqueel/runtime.py:157-159`
- asqueel: `src/asqueel/table_triggers.py:59`

</details>

### New

(a5-16)=
#### RETURNING of database-decided values

In asqueel you write:

```python
record = customer.insert({"name": "Ada"})
created = record["created_ts"]
```

In asqueel you get: the INSERT reads back with RETURNING the columns with `sql_value`, `sql_generatedExpression`, an omitted `sql_default` or dtype `serial`. The values are written into the record before the after-triggers. This holds on PostgreSQL and SQLite, also for `sql_insert` of one record.

Notes: on an adapter without the `returning_insert` capability the RETURNING is dropped without error ([#21](https://github.com/asqueel-org/asqueel/issues/21)).

<details><summary>Files</summary>

- GenroPy: `gnrpy/gnr/sql/adapters/_gnrbaseadapter.py:797`
- asqueel: `src/asqueel/write_compiler.py:284-309`
- asqueel: `src/asqueel/db_write.py:84-89`
- asqueel: `tests/write_compiler/test_write_compiler.py:73`

</details>

(a5-19)=
#### `query(...).sql_update(values)`

In asqueel you write:

```python
changed = db.table("sales.invoice").query(
    where="$total >= :minimum", minimum=100,
).sql_update({"note": "Reviewed"})
```

In asqueel you get: one `UPDATE ... WHERE (pk) IN (SELECT ...)` without hooks. The result is the affected row count. A query with `group_by` or `having` is refused. Parameter names shared by the query and the values raise `ValueError`.

<details><summary>Files</summary>

- asqueel: `src/asqueel/application_table.py:257-262`
- asqueel: `src/asqueel/write_compiler.py:206-225`
- asqueel: `tests/write_compiler/test_write_compiler.py:246`

</details>

(a5-31)=
#### `query(...).update(updater)`

In asqueel you write:

```python
pkeys = db.table("sales.invoice").query(
    where="$total >= :minimum", minimum=100,
).update({"note": "Reviewed"})
```

In asqueel you get: the rows are read with every physical column, the `X` columns and `for_update=True`. The updater, a dict or a callable, is applied to a copy of each row. Each row is written with `update(record, old_record=<row as read>)`. The result is the list of updated keys. A query with `group_by` or `having` is refused.

<details><summary>Files</summary>

- asqueel: `src/asqueel/application_table.py:274-302`
- asqueel: `tests/test_selection_writes_legacy.py:66`

</details>

(a6-30)=
#### `session(db, **env)`

In asqueel you write:

```python
from asqueel import session

with session(db, user="scheduler"):
    db.table("sales.customer").insert({"id": 5, "name": "Batch"})
    db.commit()
```

In asqueel you get: entry runs `clearCurrentEnv` and `updateEnv(**env)`. Exit runs `closeConnection`, also when the body raises. A nested session on the same thread raises `TransactionStateError` "a session is already open on this thread for this database". In GenroPy the page request did this work.

<details><summary>Files</summary>

- GenroPy: `gnrpy/gnr/web/gnrwebpage.py:161`
- GenroPy: `gnrpy/gnr/web/gnrwsgisite.py:1542`
- asqueel: `src/asqueel/runtime.py:666-691`
- asqueel: `src/asqueel/__init__.py:53`

</details>

### Same

- **Table triggers `trigger_on*`, `trigger_assignCounters`, `trigger_releaseCounters`**: empty methods with the same signatures, called in the same positions. (A5.4)
- **Column triggers**: `onInserting` and the other column attributes call `trigger_<name>` or a callable, as in GenroPy. (A5.5)
- **`protect_update`, `protect_delete`, `protect_validate`**: same methods, called in the same positions. (A5.6)
- **Record data in a write**: `@`, virtual and unknown keys are ignored, `None` is left out of INSERT, UPDATE writes every present column. (A5.14)
- **Row policies in writes**: DELETE is physical; partition, draft and logical-deletion filters do not apply to writes. (A5.28)
- **`tempEnv` / `temp_env`**: same restore rule on exit. (A6.1)
- **`setLocale()`**: called when `currentEnv` has a locale; the adapters have no effect. (A6.4)
- **`connectionName`, `currentConnectionName`, `usingMainConnection`**: same default `'_main_connection'`. (A6.5)
- **`deferToCommit` / `deferAfterCommit`**: same blocks, deduplication and queue keys in `currentEnv`. (A6.12)
- **`onDbCommitted()`**: empty method called at the end of every commit. (A6.15)
- **`:env_*` parameters in `execute`**: read from `currentEnv`, a missing key is `None`, `env_workdate` by default. (A6.19)

## Adapters

### Missing

(a8-14)=
#### `insertMany` <span class="asq-label asq-label-replaced">replaced</span>

In GenroPy you wrote:

```python
tblobj.insertMany(records)
```

In GenroPy you got: each record without a primary key received `newPkeyValue(record)`, then one `cursor.executemany` ran outside `db.execute`.

In asqueel you write:

```python
db.table('app.counter').sql_insert([{'text': 'a'}, {'text': 'b'}])
```

In asqueel you get: one `executemany` for each group of consecutive records with the same columns, without `RETURNING`. Missing keys are assigned first. In a list, integer keys are consecutive: the records above get `1` and `2`. There is no `insertMany` method.

Notes: GenroPy gave every record of the list the same integer key; asqueel assigns consecutive integers.

<details><summary>Files</summary>

- GenroPy: `gnrpy/gnr/sql/gnrsqltable/crud.py:86`
- GenroPy: `gnrpy/gnr/sql/adapters/_gnrbaseadapter.py:821`
- asqueel: `src/asqueel/application_table.py:434-450`
- asqueel: `src/asqueel/application_table.py:453-468`
- asqueel: `src/asqueel/write_compiler.py:136-151`
- asqueel: `src/asqueel/adapters/base.py:200-205`
- asqueel: `src/asqueel/adapters/sqlite.py:129-133`
- asqueel: `tests/write_compiler/test_write_compiler.py:259`
- asqueel: `tests/test_record_writes_legacy.py:103`

</details>

(a8-17)=
#### `db.listen` and `db.notify` <span class="asq-label asq-label-temporary">temporary</span>

In GenroPy you wrote:

```python
db.notify('orders', payload='42')
db.listen('orders', timeout=10, onNotify=handle)
```

In GenroPy you got: PostgreSQL `NOTIFY` and `LISTEN` on the current connection. On SQLite `notify` did nothing and `listen` only waited.

In asqueel: `db.listen`, `db.notify` and the matching adapter methods do not exist. Calling them raises `AttributeError: 'Database' object has no attribute 'listen'`. The write cycle does not handle `NOTIFY`.

Possible ways, none chosen yet:

- `db.listen` and `db.notify` as in GenroPy.
- Only `notify` in the current transaction; `listen` in the application layer.
- Leave them out: `db.execute('NOTIFY channel, :payload')` and a dedicated psycopg connection.

Notes: postponed; planned as a capability of the PostgreSQL adapter.

<details><summary>Files</summary>

- GenroPy: `gnrpy/gnr/sql/gnrsql/transactions.py:289`
- GenroPy: `gnrpy/gnr/sql/gnrsql/transactions.py:298`
- GenroPy: `gnrpy/gnr/sql/adapters/gnrpostgres3.py:155`
- GenroPy: `gnrpy/gnr/sql/adapters/gnrpostgres3.py:180`
- GenroPy: `gnrpy/gnr/sql/adapters/_gnrbasepostgresadapter.py:1295`
- GenroPy: `gnrpy/gnr/sql/adapters/_gnrbasepostgresadapter.py:1311`
- GenroPy: `gnrpy/gnr/sql/adapters/gnrsqlite.py:299`
- GenroPy: `gnrpy/gnr/sql/adapters/gnrsqlite.py:315`
- asqueel: `src/asqueel/db_write.py:5`

</details>

(a8-19)=
#### `createDb`, `dropDb`, `dbExists`, `dump`, `restore`, `importRemoteDb` <span class="asq-label asq-label-replaced">replaced</span>

In GenroPy you wrote:

```python
db.createDb('shop')
db.dump('/backup/shop.sql')
```

In GenroPy you got: the adapter created, dropped, dumped or restored the database. PostgreSQL used `pg_dump`, `pg_restore` or `psql`. SQLite created and deleted the file.

In asqueel you write:

```python
plan = db.migration_plan()
db.migrate()
```

In asqueel you get: database administration goes through asqueel-migration only. `db.migration_plan()` and `db.migrate()`, or the CLI `asqueel db plan` and `asqueel db apply`. The PostgreSQL adapter of asqueel-migration creates a missing database. On SQLite, opening the connection creates the file and its folder. `db` and `db.adapter` have no `createDb`, `dropDb`, `dbExists`, `dump`, `restore` or `importRemoteDb`.

<details><summary>Files</summary>

- GenroPy: `gnrpy/gnr/sql/gnrsql/schema.py:266`
- GenroPy: `gnrpy/gnr/sql/gnrsql/schema.py:275`
- GenroPy: `gnrpy/gnr/sql/gnrsql/schema.py:302`
- GenroPy: `gnrpy/gnr/sql/gnrsql/schema.py:315`
- GenroPy: `gnrpy/gnr/sql/adapters/_gnrbasepostgresadapter.py:417`
- GenroPy: `gnrpy/gnr/sql/adapters/_gnrbasepostgresadapter.py:435`
- GenroPy: `gnrpy/gnr/sql/adapters/_gnrbasepostgresadapter.py:486`
- GenroPy: `gnrpy/gnr/sql/adapters/_gnrbasepostgresadapter.py:335`
- GenroPy: `gnrpy/gnr/sql/adapters/_gnrbasepostgresadapter.py:439`
- GenroPy: `gnrpy/gnr/sql/adapters/gnrpostgres3.py:146`
- GenroPy: `gnrpy/gnr/sql/adapters/gnrsqlite.py:319`
- GenroPy: `gnrpy/gnr/sql/adapters/gnrsqlite.py:329`
- GenroPy: `gnrpy/gnr/sql/gnrsqlmodel/model.py:496`
- asqueel: `src/asqueel/application.py:104-125`
- asqueel: `src/asqueel/adapters/sqlite.py:51-53`
- asqueel: `docs/guide/cli.md:115-117`

</details>

(a8-23)=
#### Other adapters: `mssql`, `mysql`, `db2_400`, `fourd`, `postgres8000` <span class="asq-label asq-label-temporary">temporary</span>

In GenroPy you wrote:

```python
db = GnrSqlDb(implementation='mssql', dbname='shop')
```

In GenroPy you got: the adapter of `gnr.sql.adapters.gnrmssql`, and likewise for `mysql`, `db2_400`, `fourd` and `postgres8000`.

In asqueel: only `sqlite`, `postgres` and `postgres3` exist. Any other implementation raises `ModuleNotFoundError: No module named 'asqueel.adapters.mssql'` when the adapter is loaded. The migration package has MySQL and SQL Server adapters for DDL only.

Possible ways, none chosen yet:

- Port the GenroPy adapters as modules `asqueel.adapters.<name>`.
- Compile only PostgreSQL and translate to the other dialects with sqlglot.
- Leave them out: use PostgreSQL or SQLite.

Notes: out of this release.

<details><summary>Files</summary>

- GenroPy: `gnrpy/gnr/sql/adapters/gnrmssql.py:102`
- GenroPy: `gnrpy/gnr/sql/adapters/gnrmysql.py:48`
- GenroPy: `gnrpy/gnr/sql/adapters/gnrdb2_400.py:113`
- GenroPy: `gnrpy/gnr/sql/adapters/gnrfourd.py:84`
- GenroPy: `gnrpy/gnr/sql/adapters/gnrpostgres8000.py:91`
- asqueel: `src/asqueel/runtime.py:68-73`
- asqueel: `docs/guide/cli.md:141-144`

</details>

### Different

(a8-1)=
#### Backend choice and `db.adapter`

In GenroPy you wrote:

```python
db = GnrSqlDb(implementation='postgres', dbname='shop')
```

In GenroPy you got: the module `gnr.sql.adapters.gnrpostgres` (psycopg2). `'name:module'` loaded the adapter from another module. The default was `'sqlite'`. `currentImplementation` in the environment changed the adapter.

In asqueel you write:

```python
db = Database(implementation='postgres')
with db.tempEnv(currentImplementation='postgres'):
    adapter = db.adapter
```

In asqueel you get: the same loading rules and the same default `'sqlite'`. `'postgres'` and `'postgres3'` both load the psycopg 3 adapter `asqueel.adapters.postgres`. `'name:module'` loads `SqlDbAdapter` of that module. `db.adapter` follows `currentImplementation` and loads the adapter on first use. Any other name raises `ModuleNotFoundError`. Named connections use the dialect of the database.

Notes: the only difference is the driver behind `'postgres'`: psycopg 3 in asqueel, psycopg2 in GenroPy.

<details><summary>Files</summary>

- GenroPy: `gnrpy/gnr/sql/gnrsql/db.py:97`
- GenroPy: `gnrpy/gnr/sql/gnrsql/db.py:151-156`
- GenroPy: `gnrpy/gnr/sql/gnrsql/db.py:272`
- asqueel: `src/asqueel/runtime.py:67-73`
- asqueel: `src/asqueel/runtime.py:81-86`
- asqueel: `src/asqueel/configuration.py:57`
- asqueel: `src/asqueel/adapters/postgres3.py:2`
- asqueel: `src/asqueel/configuration.py:373-374`
- asqueel: `tests/adapters/test_db_adapter.py:10`
- asqueel: `docs/guide/adapters.md:8-16`

</details>

(a8-2)=
#### `:name` parameters and the PostgreSQL driver

In GenroPy you wrote:

```python
db.execute("SELECT ':id' AS v", {'id': 1})
```

In GenroPy you got: with `postgres`, `:name` became `%(name)s` for psycopg2. With `postgres3`, `:name` became `{name}` and the values were interpolated into the text with `sql.SQL().format`. SQLite kept `:name` (paramstyle named).

In asqueel you write:

```python
db.execute("SELECT ':id' AS v", {'id': 1})
```

In asqueel you get: on PostgreSQL, collections are expanded as in `gnrpostgres3`, then `:name` becomes `%(name)s` and `REGEXP` becomes `~*`, as in `gnrpostgres`. The values stay separate from the SQL and psycopg 3 binds them on the server. The query above returns `'$1'` on PostgreSQL and `':id'` on SQLite. `\:` protects a colon. A parameter missing from the arguments is bound to `None`. A literal `%` is written `%%`.

Notes: see [#19](https://github.com/asqueel-org/asqueel/issues/19) for the `%%` rule.

<details><summary>Files</summary>

- GenroPy: `gnrpy/gnr/sql/adapters/gnrpostgres.py:166`
- GenroPy: `gnrpy/gnr/sql/adapters/gnrpostgres3.py:107`
- GenroPy: `gnrpy/gnr/sql/adapters/gnrpostgres3.py:337`
- GenroPy: `gnrpy/gnr/sql/adapters/gnrsqlite.py:60`
- asqueel: `src/asqueel/adapters/postgres.py:51-54`
- asqueel: `src/asqueel/adapters/postgres.py:36-40`
- asqueel: `src/asqueel/adapters/sqlite.py:146-154`
- asqueel: `src/asqueel/adapters/base.py:149`
- asqueel: `src/asqueel/adapters/base.py:153-156`
- asqueel: `docs/guide/queries.md:329`

</details>

(a8-3)=
#### Collections after `IN :param`

In GenroPy you wrote:

```python
tblobj.query(where='$id IN :ids', ids=[1, 2]).fetch()
```

In GenroPy you got: on SQLite the parameters `ids0`, `ids1`. On PostgreSQL (`postgres3`) `ids_0`, `ids_1`, and an empty list replaced by `TRUE` or `FALSE`. On PostgreSQL a parameter `:ids` also matched the start of `:ids2`.

In asqueel you write:

```python
db.table('app.item').query('$id', where='$id IN :ids', ids=[1, 2]).fetch()
```

In asqueel you get: the same generated names on both dialects. On SQLite an empty list becomes `IN ()` and returns no rows. On PostgreSQL an empty list after a column `"tN"."col"` becomes `TRUE` or `FALSE`. On PostgreSQL only the whole parameter name matches: `:ids` no longer captures `:ids2`. Collisions of the generated names behave as in GenroPy.

<details><summary>Files</summary>

- GenroPy: `gnrpy/gnr/sql/adapters/_gnrbaseadapter.py:208`
- GenroPy: `gnrpy/gnr/sql/adapters/gnrpostgres3.py:65`
- asqueel: `src/asqueel/adapters/base.py:164-172`
- asqueel: `src/asqueel/adapters/postgres.py:56-81`
- asqueel: `tests/adapter_driver/test_legacy_preparation.py:43`
- asqueel: `tests/adapter_driver/test_legacy_preparation.py:151`
- asqueel: `tests/adapter_driver/test_legacy_preparation.py:160`
- asqueel: `tests/object_tree/test_minimal_select.py:270`

</details>

(a8-5)=
#### `ILIKE` on SQLite

In GenroPy you wrote:

```python
tblobj.query(where='$name ILIKE :pattern', pattern='ali%')
```

In GenroPy you got: `ILIKE` became `LIKE` and `ilike` became `like` in the whole text, also inside names and strings. `IlIkE` stayed unchanged.

In asqueel you write:

```python
db.table('app.customer').query('$name', where='$name IlIkE :pattern', pattern='ali%')
```

In asqueel you get: only the `ILIKE` operator becomes `LIKE`, in any letter case. Strings, quoted identifiers and comments are not changed. A column `ilike_label` and the string `'ILIKE'` stay unchanged.

Notes: the SQLite guide says `ILIKE` is not translated; the code translates it.

<details><summary>Files</summary>

- GenroPy: `gnrpy/gnr/sql/adapters/gnrsqlite.py:115`
- asqueel: `src/asqueel/adapters/sqlite.py:20-24`
- asqueel: `src/asqueel/adapters/sqlite.py:150`
- asqueel: `tests/sqlite/test_ilike.py:32`
- asqueel: `tests/sqlite/test_ilike.py:39`
- asqueel: `tests/sqlite/test_ilike.py:45`
- asqueel: `docs/guide/legacy-features.md:704-705`

</details>

(a8-8)=
#### SQLite connection: foreign keys, timeout, options

In GenroPy you wrote:

```python
db = GnrSqlDb(implementation='sqlite', dbname='/data/shop.db')
```

In GenroPy you got: `timeout=20.0` and `detect_types`. No `PRAGMA foreign_keys`: SQLite did not check foreign keys.

In asqueel you write:

```python
db.connection(name='/data/shop.db', implementation='sqlite').options().driver(
    foreignKeys=False, timeout=5)
```

In asqueel you get: `detect_types` as in GenroPy. `timeout` is 20 seconds by default; `timeout` and `cached_statements` can be set. Each connection runs `PRAGMA foreign_keys = ON`. `foreignKeys=False` runs `PRAGMA foreign_keys = OFF`. PostgreSQL refuses `foreignKeys` with `ValueError`.

<details><summary>Files</summary>

- GenroPy: `gnrpy/gnr/sql/adapters/gnrsqlite.py:80`
- asqueel: `src/asqueel/adapters/sqlite.py:46-49`
- asqueel: `src/asqueel/adapters/sqlite.py:56-57`
- asqueel: `src/asqueel/adapters/sqlite.py:61`
- asqueel: `src/asqueel/configuration.py:352-353`
- asqueel: `src/asqueel/configuration.py:392`
- asqueel: `src/asqueel/adapters/postgres.py:27-28`
- asqueel: `tests/test_sqlite_legacy_connection.py:82`
- asqueel: `tests/test_sqlite_legacy_connection.py:93`
- asqueel: `tests/test_sqlite_legacy_connection.py:106`
- asqueel: `docs/guide/sqlite.md:21-29`

</details>

(a8-9)=
#### Value types on SQLite

In GenroPy you wrote:

```python
tblobj.insert({'id': 1, 'price': Decimal('9.90'), 'day': date(2026, 1, 1)})
```

In GenroPy you got: `Decimal` written as float, `numeric` read as `Decimal`, `date` read as `date`. `bool` and `timestamp` had converters; a `boolean` column did not. Time zones were removed.

In asqueel you write:

```python
db.table('app.item').insert({'id': 1, 'price': Decimal('9.90'), 'day': date(2026, 1, 1)})
```

In asqueel you get: values come back converted to the dtype. `D`, `DH`, `H`, `N` and `B` read as `date`, `datetime`, `time`, `Decimal` and `bool`. Dates and times are written as ISO strings and keep `tzinfo`. `Decimal` is written as a string. Both `boolean` and `bool` columns are converted.

<details><summary>Files</summary>

- GenroPy: `gnrpy/gnr/sql/adapters/gnrsqlite.py:80`
- GenroPy: `gnrpy/gnr/sql/adapters/gnrsqlite.py:543-544`
- GenroPy: `gnrpy/gnr/sql/adapters/gnrsqlite.py:552`
- GenroPy: `gnrpy/gnr/sql/adapters/gnrsqlite.py:579`
- GenroPy: `gnrpy/gnr/sql/adapters/gnrsqlite.py:596`
- asqueel: `src/asqueel/adapters/sqlite.py:76-87`
- asqueel: `src/asqueel/adapters/sqlite.py:135-144`
- asqueel: `tests/sqlite/test_sqlite_legacy_values.py:38`
- asqueel: `docs/guide/sqlite.md:83-88`

</details>

(a8-10)=
#### Transactions and `for_update` on SQLite

In GenroPy you wrote:

```python
tblobj.record(pkey, for_update=True).output('bag')
```

In GenroPy you got: no lock. `_selectForUpdate` returned an empty string. The `sqlite3` module opened a deferred transaction.

In asqueel you write:

```python
db.table('app.item').query('$id', for_update=True).fetch()
```

In asqueel you get: transactions are deferred as in GenroPy: `BEGIN` before the first INSERT, UPDATE or DELETE, and reads open no transaction. With `for_update`, asqueel runs `BEGIN IMMEDIATE` when no transaction is open. Inside an open transaction it runs an UPDATE of no row on the table. The SQL text carries no `FOR UPDATE`.

<details><summary>Files</summary>

- GenroPy: `gnrpy/gnr/sql/adapters/gnrsqlite.py:140-141`
- GenroPy: `gnrpy/gnr/sql/adapters/gnrsqlite.py:80`
- asqueel: `src/asqueel/adapters/sqlite.py:54-57`
- asqueel: `src/asqueel/adapters/sqlite.py:111-121`
- asqueel: `src/asqueel/adapters/sqlite.py:221-222`
- asqueel: `tests/sqlite/test_sqlite_legacy_values.py:51`
- asqueel: `tests/sqlite/test_sqlite_legacy_values.py:65`
- asqueel: `docs/guide/sqlite.md:59-66`

</details>

(a8-11)=
#### `for_update` modes `'NOWAIT'` and `'SKIP LOCKED'`

In GenroPy you wrote:

```python
tblobj.query(for_update='SKIP LOCKED').fetch()
```

In GenroPy you got: `FOR UPDATE OF t0` followed by any mode string. SQLite took no lock.

In asqueel you write:

```python
db.table('app.note').query(columns='$id', for_update='SKIP LOCKED').fetch()
```

In asqueel you get: on PostgreSQL the SQL ends with `FOR UPDATE OF t0 SKIP LOCKED`. Only `True`, `'NOWAIT'` and `'SKIP LOCKED'` are accepted. Any other value raises `ValueError: for_update must be True, NOWAIT or SKIP LOCKED`. On SQLite a mode string raises `UnsupportedFeatureError: for_update=SKIP LOCKED is not available on SQLite`.

Notes: anything outside the grammar raises.

<details><summary>Files</summary>

- GenroPy: `gnrpy/gnr/sql/adapters/_gnrbaseadapter.py:721-723`
- GenroPy: `gnrpy/gnr/web/gnrtask.py:99`
- asqueel: `src/asqueel/compiler.py:694-695`
- asqueel: `src/asqueel/adapters/base.py:139`
- asqueel: `src/asqueel/adapters/sqlite.py:217-218`
- asqueel: `tests/test_record_writes_legacy.py:136`
- asqueel: `tests/test_record_writes_legacy.py:141`
- asqueel: `docs/guide/legacy-features.md:185-188`

</details>

(a8-12)=
#### Table `lock()`

In GenroPy you wrote:

```python
tblobj.lock(mode='SHARE', nowait=True)
```

In GenroPy you got: `LOCK ... IN SHARE MODE NO WAIT` on PostgreSQL, which is not valid SQL. SQLite ran no statement.

In asqueel you write:

```python
db.table('app.note').lock(mode='SHARE', nowait=True)
```

In asqueel you get: on PostgreSQL `LOCK ... IN SHARE MODE NOWAIT` in the current transaction. The mode must be a PostgreSQL lock mode; any other mode raises `ValueError`. On SQLite asqueel takes the write reservation with an UPDATE of no row, for example `UPDATE "app"."app_item" SET "id"="id" WHERE 0`.

<details><summary>Files</summary>

- GenroPy: `gnrpy/gnr/sql/gnrsqltable/crud.py:481`
- GenroPy: `gnrpy/gnr/sql/adapters/_gnrbasepostgresadapter.py:319`
- GenroPy: `gnrpy/gnr/sql/adapters/_gnrbasepostgresadapter.py:321`
- GenroPy: `gnrpy/gnr/sql/adapters/gnrsqlite.py:390`
- asqueel: `src/asqueel/table_crud.py:72-76`
- asqueel: `src/asqueel/write_compiler.py:23`
- asqueel: `src/asqueel/write_compiler.py:233-245`
- asqueel: `tests/test_record_writes_legacy.py:127`
- asqueel: `tests/write_compiler/test_write_compiler.py:146`
- asqueel: `docs/guide/writes.md:226-232`

</details>

(a8-16)=
#### `unaccentFormula`, `mask_field_sql`, `ageAtDate`

In GenroPy you wrote:

```python
self.db.adapter.mask_field_sql('$email', mode='email')
self.db.adapter.ageAtDate('$born', timeUnit='year')
```

In GenroPy you got: the SQL expression of the dialect. An unknown mode fell back to `'2-4'`. An unknown `timeUnit` fell back to `day`.

In asqueel you write:

```python
self.db.adapter.mask_field_sql('$email', mode='email')
self.db.adapter.unaccentFormula('$name')
```

In asqueel you get: the GenroPy expressions. `unaccentFormula` gives `unaccent($name)` on PostgreSQL and the field unchanged on SQLite. An invalid mode raises `ValueError: mask_field_sql: unknown mode ...`. An unknown `timeUnit` raises `ValueError: ageAtDate: unknown timeUnit ...`. On SQLite `ageAtDate` raises `UnsupportedFeatureError`. `db.whereTranslator` is refused.

Notes: anything outside the grammar raises.

<details><summary>Files</summary>

- GenroPy: `gnrpy/gnr/sql/adapters/_gnrbasepostgresadapter.py:1291`
- GenroPy: `gnrpy/gnr/sql/adapters/_gnrbasepostgresadapter.py:1333`
- GenroPy: `gnrpy/gnr/sql/adapters/_gnrbasepostgresadapter.py:248`
- GenroPy: `gnrpy/gnr/sql/adapters/gnrsqlite.py:401`
- GenroPy: `gnrpy/gnr/sql/adapters/_gnrbaseadapter.py:681`
- GenroPy: `gnrpy/gnr/sql/gnrsqltable/columns.py:297`
- asqueel: `src/asqueel/adapters/postgres.py:126-184`
- asqueel: `src/asqueel/adapters/sqlite.py:227-287`
- asqueel: `src/asqueel/adapters/base.py:45-50`
- asqueel: `src/asqueel/adapters/base.py:235-246`
- asqueel: `src/asqueel/runtime.py:61`
- asqueel: `tests/adapters/test_adapter_functions.py:45`
- asqueel: `tests/adapters/test_adapter_functions.py:52`
- asqueel: `tests/adapters/test_adapter_functions.py:64`
- asqueel: `tests/adapters/test_adapter_functions.py:98`

</details>

(a8-18)=
#### `db.analyze()` and `db.vacuum()`

In GenroPy you wrote:

```python
db.vacuum(table='app.app_item', full=True)
```

In GenroPy you got: `VACUUM FULL ANALYZE app.app_item` on a separate autocommit connection. On SQLite the same statement, which SQLite rejects.

In asqueel you write:

```python
db.commit()
db.vacuum(table='app.app_item', full=True)
```

In asqueel you get: `analyze()` runs `ANALYZE` in the current transaction, as in GenroPy. `vacuum()` raises `TransactionStateError` when the thread has pending work. On PostgreSQL it runs `VACUUM [FULL] ANALYZE [table]` on a separate autocommit connection. On SQLite it runs `VACUUM` on `main` and on every attached schema, then `ANALYZE [table]`, on a separate connection.

<details><summary>Files</summary>

- GenroPy: `gnrpy/gnr/sql/gnrsql/transactions.py:307`
- GenroPy: `gnrpy/gnr/sql/gnrsql/transactions.py:311`
- GenroPy: `gnrpy/gnr/sql/adapters/_gnrbaseadapter.py:929`
- GenroPy: `gnrpy/gnr/sql/adapters/_gnrbaseadapter.py:933`
- asqueel: `src/asqueel/runtime.py:282-294`
- asqueel: `src/asqueel/adapters/base.py:223-225`
- asqueel: `src/asqueel/adapters/postgres.py:42-49`
- asqueel: `src/asqueel/adapters/sqlite.py:97-109`
- asqueel: `tests/test_execute_and_transactions.py:73`
- asqueel: `tests/test_read_write_final_touch.py:118`
- asqueel: `tests/test_sqlite_legacy_connection.py:123`
- asqueel: `docs/guide/legacy-features.md:534-541`

</details>

(a8-20)=
#### Adapter capabilities

In GenroPy you wrote:

```python
if db.adapter.has_capability('SCHEMAS'):
    pass
```

In GenroPy you got: `CAPABILITIES` such as `MIGRATIONS`, `VECTOR`, `SCHEMAS`, and `ADMINISTER` when the executables were present.

In asqueel you write:

```python
adapter = PostgresAdapter(db, capabilities=PostgresAdapter.capabilities - {'returning_insert'})
```

In asqueel you get: an attribute `capabilities` with SQL capabilities: `select`, `insert`, `update`, `delete`, `returning_insert`, `returning_update`, `returning_delete`, `left_join`, `limit`, `offset`, `default_values`, `for_update`. The constructor option `capabilities` can reduce the set. There is no `has_capability` and no `SCHEMAS`, `MIGRATIONS`, `VECTOR` or `ADMINISTER`.

Notes: declaring a capability does not implement it. The write compiler does not check all capabilities: [#21](https://github.com/asqueel-org/asqueel/issues/21).

<details><summary>Files</summary>

- GenroPy: `gnrpy/gnr/sql/adapters/_gnrbaseadapter.py:87`
- GenroPy: `gnrpy/gnr/sql/adapters/_gnrbaseadapter.py:343`
- GenroPy: `gnrpy/gnr/sql/adapters/_gnrbasepostgresadapter.py:114`
- GenroPy: `gnrpy/gnr/sql/adapters/gnrsqlite.py:56`
- GenroPy: `gnrpy/gnr/sql/adapters/_gnrbaseadapter.py:164-165`
- GenroPy: `gnrpy/gnr/sql/gnrsqlmodel/table.py:176`
- asqueel: `src/asqueel/adapters/base.py:58-73`
- asqueel: `src/asqueel/adapters/postgres.py:20-24`
- asqueel: `src/asqueel/adapters/sqlite.py:32-36`
- asqueel: `tests/adapter_dialect/test_postgres.py:46`
- asqueel: `docs/guide/limitations.md:222-224`

</details>

(a8-21)=
#### `LIMIT` and `OFFSET`

In GenroPy you wrote:

```python
tblobj.query(limit=0, offset=10).fetch()
```

In GenroPy you got: `LIMIT` and `OFFSET` only when set: `limit=0` was omitted. On SQLite an `OFFSET` without `LIMIT` was a syntax error.

In asqueel you write:

```python
db.table('app.item').query('$id', limit=0, offset=10).fetch()
```

In asqueel you get: a false `limit` or `offset` emits no clause, as in GenroPy: `limit=0` returns all rows. A value that is not a nonnegative integer raises `ValueError: limit must be a nonnegative integer`. On SQLite an `OFFSET` without `LIMIT` adds `LIMIT 9223372036854775807`.

Notes: the queries guide says `limit=0` returns no rows; the code returns all rows.

<details><summary>Files</summary>

- GenroPy: `gnrpy/gnr/sql/adapters/_gnrbaseadapter.py:715-716`
- asqueel: `src/asqueel/adapters/base.py:117-121`
- asqueel: `src/asqueel/adapters/base.py:133-137`
- asqueel: `src/asqueel/adapters/sqlite.py:219-220`

</details>

(a8-22)=
#### SQL types of the dtypes

In GenroPy you wrote:

```python
tbl.column('note', dtype='X')
tbl.column('code', dtype='A', size='10')
```

In GenroPy you got: `columnSqlType` and `revTypesDict` of each adapter. A size without `:` gave `C`, `'n:m'` gave `A`. On SQLite `X` was `blob`, `DH` `timestamp`, `H` `time`. `typesDict` read the types back.

In asqueel you write:

```python
tbl.column('note', dtype='X')
tbl.column('code', dtype='A', size='10')
```

In asqueel you get: asqueel-migration writes the DDL with the GenroPy type names. On PostgreSQL the types of `revTypesDict`. On SQLite `character varying(n)`, `character(n)`, `timestamp`, `time`, and `blob` for `O`. `X`, `Z`, `P`, and `A` or `C` without size become `text` on both dialects, in the DDL only; the model column keeps its dtype. On PostgreSQL the types are read back with the entries of `typesDict`.

Notes: `X` becomes `text` also on SQLite, where GenroPy gave `blob`.

<details><summary>Files</summary>

- GenroPy: `gnrpy/gnr/sql/adapters/_gnrbaseadapter.py:1133`
- GenroPy: `gnrpy/gnr/sql/adapters/_gnrbasepostgresadapter.py:146`
- GenroPy: `gnrpy/gnr/sql/adapters/gnrsqlite.py:50`
- GenroPy: `gnrpy/gnr/sql/adapters/_gnrbasepostgresadapter.py:123`
- asqueel: `src/asqueel/projection.py:15-30`
- asqueel: `src/asqueel/elements.py:62-65`
- asqueel: `src/asqueel/importers.py:210-225`
- asqueel: `tests/test_sqlite_legacy_connection.py:139`
- asqueel: `tests/test_sqlite_legacy_connection.py:152`
- asqueel: `docs/guide/legacy-features.md:686-691`

</details>

### New

(a8-13)=
#### Minimum SQLite version

In asqueel you write:

```python
db.connection(name='/data/shop.db', implementation='sqlite')
```

In asqueel you get: `connect()` raises `RuntimeError: SQLite 3.35 or later is required for RETURNING` when the SQLite library is older than 3.35. GenroPy did not check the version.

<details><summary>Files</summary>

- GenroPy: `gnrpy/gnr/sql/adapters/gnrsqlite.py:1`
- asqueel: `src/asqueel/adapters/sqlite.py:39-40`
- asqueel: `docs/guide/sqlite.md:5`

</details>

### Same

- **`REGEXP` and `~*`**: PostgreSQL turns `REGEXP` into `~*`; SQLite turns `~*` into `REGEXP` with a `regexp` function based on `re.match`. (A8.4)
- **`IS TRUE` / `IS FALSE` on SQLite**: rewritten as a comparison with 1 or 0 that handles NULL, with the same regex. (A8.6)
- **SQLite schemas as attached files**: each schema is the file `<schema>.db` in the folder of the main file, attached at connection; the default schema is `main`. (A8.7)
- **`db.adapter.string_agg(field, separator)`**: `string_agg(...)` on PostgreSQL and `group_concat(...)` on SQLite, for table formulas. (A8.15)

## To implement

### Query

(a2-20)=
#### `selection()` and the `SqlSelection` API

In GenroPy you wrote:

```python
selection = tblobj.query(columns='$id, $total').selection()
selection.sort('total:d')
bag = selection.output('grid')
```

In GenroPy you got: a `SqlSelection` with `output`, `sort`, `totalize`, `freeze` and `frozenSelection`.

In asqueel: `selection()` raises `UnsupportedFeatureError` with the message `selection(): Selection and Bag output are not available in this release`. A recorded decision says it will be implemented, as the next step.

<details><summary>Files</summary>

- GenroPy: `gnrpy/gnr/sql/gnrsqldata/query.py:446`
- GenroPy: `gnrpy/gnr/sql/gnrsqldata/selection.py:256`
- GenroPy: `gnrpy/gnr/sql/gnrsqldata/selection.py:493`
- GenroPy: `gnrpy/gnr/sql/gnrsqldata/selection.py:558`
- GenroPy: `gnrpy/gnr/sql/gnrsqldata/selection.py:731`
- GenroPy: `gnrpy/gnr/sql/gnrsqltable/query.py:107`
- asqueel: `src/asqueel/application_table.py:315-316`
- asqueel: `docs/guide/limitations.md:238`

</details>

### Read-Write

(a5-8)=
#### Package triggers `trigger_<event>_<pkg>`

In GenroPy you wrote:

```python
class Table(object):
    def trigger_onInserting_mypkg(self, record):
        record['code'] = record['code'].upper()
```

In GenroPy you got: for every package of the application, the write cycle called `trigger_<event>_<pkg>` on the table. The environment key `avoid_trigger_<pkg>` skipped them.

In asqueel: the write cycle does not call package triggers. A method named `trigger_on<Event>_<pkg>` in the table class raises `UnsupportedFeatureError` "<table>: table method 'trigger_onInserting_mypkg' is not available in this release" when the model is built. `avoid_trigger_<pkg>` does not exist. A recorded decision says package triggers will be implemented after an evaluation.

<details><summary>Files</summary>

- GenroPy: `gnrpy/gnr/sql/gnrsqltable/crud.py:696-710`
- GenroPy: `gnrpy/gnr/sql/gnrsql/write.py:157`
- asqueel: `src/asqueel/object_tree.py:173-181`
- asqueel: `src/asqueel/db_write.py:6`

</details>

(a6-20)=
#### SQL comment, `sql_audit` and debugger

In GenroPy you wrote:

```python
with db.tempEnv(sql_comment='nightly import'):
    db.execute('SELECT 1')
```

In GenroPy you got: every statement started with `-- <sql_comment or user>`. An audit log recorded each statement with its time. A debugger hook received the statements.

In asqueel: no comment and no audit log are written. The environment keys `sql_comment` and `sql_details` raise `UnsupportedFeatureError` "environment key 'sql_comment' is not available in this release" at execution. The debugger does not exist. A recorded decision says these keys will be implemented later, in a more usable form (for example JSONL).

<details><summary>Files</summary>

- GenroPy: `gnrpy/gnr/sql/gnrsql/execute.py:105`
- GenroPy: `gnrpy/gnr/sql/gnrsql/helpers.py:88-117`
- asqueel: `src/asqueel/runtime.py:433-437`

</details>

## Migration

asqueel does not change the database structure itself. It uses the separate
package asqueel-migration for DDL, installed with `asqueel[migration]`.
`project_tree()` translates the asqueel model into the format asqueel-migration reads.
`db.migration_plan()` returns the plan and changes nothing; `db.migrate()` applies it.
Both take the options `allow_removals`, `foreignKeys`, `force` and `backup`.
The command line offers the same two operations: `asqueel db plan` and `asqueel db apply`,
with `--allow-removals`, `--no-foreign-keys`, `--force` and `--backup`.
The differences of the migration layer are described in asqueel-migration.

## Low-level and high-level API

This release is the low-level layer of the SQL API.

- In this release: `query()` with `fetch()` and its derivatives, `fetchRecord()`,
  `query().update()` and `query().delete()` (row by row, through the write cycle),
  `query().sql_update()` and `query().sql_delete()` (one statement, no triggers),
  `insert()`, `update()`, `delete()` and the `sql_*` writes of a table.
- Later, in the high-level layer: `record()` with its rich API, `selection()`
  (the next step), `batchUpdate()`, `recordToUpdate()`, `check_updatable()` and
  `check_deletable()`.

A high-level feature called in this release raises an error that names it.

## Proposals

These proposals are under discussion. None of them is implemented.

**sqlglot transpilation.** asqueel would compile only PostgreSQL SQL and
translate it into the other dialects with sqlglot, through its syntax tree.
One compiler would serve every dialect, and dialects such as MySQL, SQL Server
and DuckDB would become reachable. Open points: semantics that does not
translate (`FOR UPDATE` on SQLite, `jsonb_agg`, `xmlagg`, `tsvector`),
preservation of the query parameters, the cost of parsing, a new dependency.

**A `.sql(...)` child element.** The `sql_*` attributes of a column would be
grouped in one child element `.sql(...)` instead of being spread over the column.

**Capability catalogue.** Each adapter would declare the capabilities it has,
organised by theme: alter column, gin indexes, RETURNING, JSON and XML
aggregates, full-text search, vectors, schemas, migration, administration.
A call that needs a capability the dialect lacks would raise an error that
names the capability.

**Async connection modes.** asqueel handles connections as GenroPy does: the
environment is read again at every execution, and there is no `db.close()`,
`with db:` or `acquire()`. Alternative connection modes, for example for async
code, are a possible future study.

### Application and SQL update actions

`onUpdate_sql` defaults to `cascade`. The database applies that action during
UPDATE, before the application calls `updateRelated`: matching child rows may
already have moved, so their application hooks need not run. When application
propagation and child hooks are required, explicitly use `onUpdate='cascade'`,
`onUpdate_sql='no action'` and a deferred foreign key on a backend that supports
it. Composite application cascades remain limited (issue #49).
