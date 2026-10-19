# Legacy feature status

This page compares asqueel 0.6 with the SQL layer of GenroPy (`gnrpy/gnr/sql/`),
feature by feature. It covers what a project calls or declares: methods,
attributes, macros. For each of eight areas it lists:

- what works as in GenroPy;
- what works differently, with the reason in one sentence;
- what is not available yet, with its issue and the workaround.

A last section lists the asqueel features with no GenroPy counterpart.

Every item carries an ID such as `A1.4`. The IDs refer to the verified
inventory `docs/design/112-legacy-inventory.md` (in Italian), which cites the
code on both sides. The legacy reference is GenroPy commit `95da66ee`.
When a reason reads "not recorded", the difference exists in the code and no
document states why. When this page and another page of the manual disagree,
this page describes the installed code.

For porting guidance, see [For Genropy users](legacy.md). For the refusals of
the write cycle, see [Current status](limitations.md).

## 1 Model

### Works as in GenroPy

- `validate_*` attributes (A1.8).
- `columns` and `relations` of a table (A1.21).
- **`lastTS`, `logicalDeletionField`, `draftField`, `protectionColumn`** (A1.3):
  table attributes; the table and the model table expose `lastTS`,
  `logicalDeletionField` and `draftField` (empty string when absent).
- **`partition_<field>='path'`** (A1.4): env `current_<path>` filters
  `$<field> = :env_current_<path>`; else env `allowed_<path>` filters
  `$<field> IS NULL OR $<field> IN :env_allowed_<path>`; else no filter. The first
  `partition_*` attribute counts. The fallback on an `__allowed_partition`
  column is not ported. Partitions do not apply to writes
  ([#15](https://github.com/asqueel-org/asqueel/issues/15)).
- **`column()` attributes** (A1.5): `indexed` and `unique` accept the legacy
  true strings (`'y'`, `'true'`, ...), read as `str_boolean`.
- **`format`, `print_width`** (A1.9): column metadata, readable in
  `column.attributes` and as `column.print_width`.
- **`model.table('pkg.tbl')`, `tblobj.column(name)`** (A1.19): an unknown
  package returns `None`; an unknown table of a known package raises
  `ValueError`; an unknown column returns `None`.
- **`pkeys`** (A1.20): the list of the key columns, the compositeColumn
  members when `pkey` names one.
- **`index(columns, name, unique)`** (A1.13): columns first, a string, list
  or tuple; the default name is `<table>_<columns joined by _>_key`. An index
  with that default name gets the migrator's generated SQL name, as in GenroPy;
  `method`, `where`, `tablespace`, `with_options` are keyword attributes.
- **Composite `pkey`** (A1.20): `pkey=<compositeColumn name>`, with `pkeys`
  its member list; `pkey='a,b'` raises `ValueError` at model build.
- **`name_long`, `name_short`, `name_full`, `name_plural`** (A1.22): the
  legacy fallbacks; `name_full` is an attribute of package, table and column.
- **`sql_default`, `sql_generatedExpression`, `sql_extra`** (A1.27): column
  attributes, with a variant per dialect (`sql_pg_default`,
  `sql_sqlite_extra`, ...) that wins on its dialect.

### Works differently

- **`package()`, `sqlschema`, `sqlprefix`, `sqlname`** (A1.1): declared with
  `package(name, sqlschema, sqlprefix, ...)` under `db.packages()`; there is no
  `tenant_schema`. Reason: schema and prefix follow the legacy rules; a model
  with a schema tag does not set the prefix
  ([#25](https://github.com/asqueel-org/asqueel/issues/25)); `tenant_schema`:
  not recorded.
- **`table(name, pkey=, ..., **kwargs)`** (A1.2): only declared parameters are
  accepted; any other keyword raises, naming the attribute and the element
  (`hierarchical`, `xtd`, `multi_tenant`, `group_<name>` and free `x_*` keys
  are refused). Reason: no
  attribute outside the grammar is accepted in this release (decision of
  17 October 2026).
- **UI attributes** (`values`, `cell_*`, `template_*`, `batch_*`, ...) (A1.9):
  refused as unknown attributes; `values` becomes `validate_values`.
  `encrypted` raises `UnsupportedFeatureError` naming it. Reason: UI attributes are outside this release's
  grammar; free `x_ui_*` keys are refused too.
- **`colgroup()`** (A1.11): available; `colgroup_label`,
  `colgroup_name_long` and `group_<name>` raise as attributes outside the
  grammar. Reason: not recorded for the missing attributes.
- **`compositeColumn()`** (A1.12): declared in the `composites` collection
  with `unique=`. Read as a value, and as the pkey, it is the legacy string
  (see A3.13).
- **`config_db`, `config_db_<pkg>`, `config_db_custom`** (A1.17): a package
  folder in the legacy layout loads with `package(name, path=<folder>)`:
  `main.py` holds class `Package` (`config_attributes()` gives package
  attributes, under the ones written on the element), `model/<table>.py` holds
  class `Table` whose `config_db(self, pkg)` declares through the grammar;
  tables load in alphabetical order of their modules, and the runtime table is
  `Table` combined with `SqlTable`, its triggers running in the write cycle.
  `config_db_<pkg>` and `config_db_custom` raise `UnsupportedFeatureError`.
  Recipe packages (`main(self, root)`) sit beside layout packages in one
  database. Reason: customization is application-level; the layout is
  provisional (decision of 18 October 2026).
- **`name_long`, `name_short`, `name_full`** (A1.22): there are no setters.
  Reason: not recorded.
- **Package custom types `custom_type_<dtype>`** (A1.26): in a layout package,
  `Package.custom_type_<dtype>()` returns the column defaults for
  `dtype='<dtype>'`, accepted keys as `options().type()`; a recipe package
  declares `options().type(name, dtype, size, ...)`. Explicit column attributes
  win; an unknown dtype raises `ValueError`.

### Not available yet

- **`column(default=)`** (A1.7): declared, but a table with it cannot be
  written ([#28](https://github.com/asqueel-org/asqueel/issues/28)).
  Workaround: set the value in `trigger_onInserting`.
- **`localized`, `variant`, `ext_<pkg>`** (A1.10): each raises
  `UnsupportedFeatureError` naming the attribute. No issue yet.
  Workaround: declare the generated columns by hand.
- **`sysFields(tbl, ...)`** (A1.14): `options().sys_fields(...)` expands the
  columns and the table is written as legacy: the 22-character `id` is
  generated, `__ins_ts`/`__mod_ts` are set by `trigger_setTSNow` (aware UTC
  for `DHZ`), `__ins_user`/`__mod_user` by `trigger_setCurrentUser` from
  `db.currentUser` (the `user` of `currentEnv`). Differences: no
  `__full_mod_ts` copy, no `_notUserChange` check (`batchUpdate`,
  [#32](https://github.com/asqueel-org/asqueel/issues/32)). Other options on
  the same table still refuse the write.
- **`sysFields(hierarchical=...)`** (A1.15): `options().hierarchical`
  expands and the table is written as legacy develop: the `parent_id` field
  triggers `trigger_hierarchical_before`/`trigger_hierarchical_after` call
  the table's `hierarchicalHandler`, which materializes `hierarchical_<field>`,
  `_parent_h_<field>` and `hierarchical_pkey`, copies the `copyFromParent`
  columns (`_virtual_node`), numbers siblings in `_row_count`/`_h_count` when
  `auto_counter` is declared, and rewrites the subtree after a rename or a
  move. A move under the node itself or a descendant raises
  `BusinessLogicException`; an update without `old_record` raises
  `RecordException`; deleting a node deletes its subtree. `child_count`,
  `hlevel` and `root_id` are read for every node. Three behaviours go
  beyond legacy: a node moved to another parent takes the last
  `_row_count` among its new siblings; a `_row_count` above 1295 (two
  base-36 digits of `_h_count`), computed or given, raises
  `BusinessLogicException` where legacy wrote an empty `_h_count`; max + 1
  runs after reading the parent `for_update`, or, for a root on PostgreSQL,
  after `LOCK ... IN SHARE ROW EXCLUSIVE MODE`, so concurrent inserts get
  distinct positions. Differences: no
  `subtable`; `linked_to` and `depth` raise `UnsupportedFeatureError` when
  the model is built; `getHierarchicalData`, `hierarchicalSearch`,
  `pathFromPkey`, `getAncestors`, `fixRowCount` are absent (model JSON:
  [#18](https://github.com/asqueel-org/asqueel/issues/18)).
- **`sysFields(counter=)`, `sysFields_counter`** (A1.16):
  `options().auto_counter` expands, but a table with it cannot be written,
  except a hierarchical table, where `trigger_hierarchical_before` assigns it
  ([#31](https://github.com/asqueel-org/asqueel/issues/31)). Workaround: set
  the value in `trigger_onInserting`.
- **Table and package mixins** (`tableMixin`, `packageMixin`, `_plugins`,
  `mixin=`) (A1.18): no mixin is installed. No issue yet. Workaround:
  `x_table_class`.
- **`rowcaption`, `newrecord_caption` properties** (A1.23): the attributes are
  declared, the properties do not exist. No issue yet. Workaround:
  `attributes.get('rowcaption')`.
- **`virtual_columns`, `starColumns()`** (A1.24): only declared columns are
  listed. No issue yet. Workaround: declare the columns in the recipe.
- **`subtable()`** (A1.25): `subtable()`, the `default_subtable` attribute and
  the query option `subtable` are outside this release's grammar and raise.
  No issue yet. Workaround: a `where` with the subtable condition.

## 2 Query

### Works as in GenroPy

- `*` expansion and `bagFields` (A2.2).
- Automatic column names (`colToAs`) (A2.5).
- `$col`, `$pkey` and to-one `@rel` in columns, where and order_by (A2.6).
- `sqlparams` and symbolic parameters (A2.7).
- The `:env_name` parameter (A2.9).
- `distinct`, `group_by`, `having`, `limit`, `offset` (A2.11).
- `excludeLogicalDeleted` (also `'mark'`) and `excludeDraft` (A2.13).
- `fetch()` (A2.16).
- `fetchPkeys`, `fetchAsJson`, `fetchAsDict`, `fetchAsBag`, `fetchGrouped`,
  `cursor`, `servercursor` (A2.17).
- `count()` (A2.18).

### Works differently

- **`*@rel`, `*@rel1.@rel2`, `*prefix_`, `*name`, `*@rel.(a,b)`** (A2.3):
  raise `UnsupportedFeatureError`. Reason: only `*` and explicit columns were
  kept (decision of 15 October 2026).
- **`addPkeyColumn` / automatic `pkey` column** (A2.4): the `pkey` column is
  added only with `addPkeyColumn=True`. Reason: the legacy adapter adds it
  (decision of 2 October 2026).
- **kwargs as query parameters** (A2.8): as in GenroPy, a keyword the query
  does not use stays a parameter and the query runs, with an
  `UnusedQueryParameterWarning` that names it and the parameters the query
  uses; `jc_*` keywords raise. Reason: it catches misspelled options.
- **`for_update`** (A2.12): as in GenroPy, but refused together with
  `distinct` or `group_by`. Reason: early refusal of a combination the
  database rejects.
- **`ignorePartition` and the partition filter** (A2.14): `0` and `False` are
  valid values, an empty allowed set returns no rows, a missing context raises
  an error. Reason: agreed difference, described in [For Genropy users](legacy.md).

### Not available yet

- **Default columns / `columns=None`** (A2.1): the default is `*`;
  `columns=None` raises `TypeError`. No issue yet. Workaround: omit `columns`.
- **`env_<table>_condition_*` conditions** (A2.10): an environment key of this
  form raises `UnsupportedFeatureError` at execution, naming the key; so do
  `sql_comment` and `sql_details`. No issue yet. Workaround: an explicit
  `where` in the caller.
- **`ignoreTableOrderBy`, `_storename`, `locale`, `mode`, `checkPermissions`,
  `aliasPrefix`** (A2.15): raise `UnsupportedFeatureError`; the table
  `order_by` is applied and cannot be disabled. No issue yet. Workaround: an
  explicit `order_by` and filters in the `where`.
- **`record(pkey= / where=, for_update, ignoreMissing)`, `record` mode and
  `output(mode)`** (A2.21, A2.23): `record()` raises `UnsupportedFeatureError`
  with `use query(...).fetchRecord()`; its Bag output has no replacement. No
  issue yet. Workaround: `query(where=..., for_update=...).fetchRecord()`;
  `ignoreMissing=True` returns None for no row.
- **`selection()` and the `SqlSelection` API** (A2.20): raises
  `UnsupportedFeatureError`. No issue yet. Workaround: `fetch()` and
  processing in Python.
- **`ignoreDuplicate`, `virtual_columns`, `lazy`/`eager`** (A2.22): refused
  as query options. No issue yet. Workaround: an explicit `where`, and
  `query()` for formulas.
- **`readColumns`, `countRecords`, `recordAs`, `cachedRecord` /
  `tableCachedData`, `db.query(table)`** (A2.25): absent. No issue yet.
  Workaround: `query(...).fetch()` and `query(...).fetchRecord()`.
- **`sqlWhereFromBag`, `whereTranslator`, `opTranslate`** (A2.26): absent. No
  issue yet. Workaround: a `where` written by the caller.

## 3 Formulas

### Works as in GenroPy

- `sql_formula=True` with `sql_formula_<name>(attr)`, and the `sysFields`
  formulas `__protecting_reasons` / `__invalid_reasons` (A3.2).
- `select=`, `exists=`, `select_<name>` and `exists_<name>` with `#<name>`,
  cast and `subquery_<name>()` (A3.3). `#<name>` of an `exists_<name>` becomes
  `EXISTS (<subquery>)`.
- `var_*` in formulas (A3.4).
- `aliasColumn` with `relation_path`, its own dtype and metadata (A3.6).
- Redefinition of a virtual column with a different kind (A3.7).
- `static=True` and `*` (A3.9).
- `bagItemColumn` (A3.11).
- References in formulas: `$col`, `@rel.col`, `:param`, `:env_*` (A3.16).
- `compositeColumn` read as a value (A3.13): the members joined into the
  string `'["A", 2026]'`; A/C/T members are quoted, L/F/R/B members are raw,
  other dtypes are quoted with `::<dtype>`. The value is the string, not
  decoded. A table whose pkey is a compositeColumn selects it through the same
  formula.
- Dynamic columns from `formulaColumn_<x>()` table methods (A3.15): called
  without arguments, each returns a dict or a list of dicts with `name` and the
  formula attributes. They are evaluated when a query needs the table's virtual
  columns and cached in `currentEnv['_virtual_columns_<pkg>_<tbl>']`. A
  declared column with the same name raises `ValueError`.
- `#THIS`, `#IN_RANGE`, `#PERIOD` (A3.17).

### Works differently

- **`formulaColumn` (`sql_formula`, `dtype`)** (A3.1): exactly one of
  `sql_formula`, `select`, `exists` is required; `sql_formula` with `select` or
  `exists` raises `ValueError`; an unused `select_<name>`/`exists_<name>`, or a
  `select_<n>` and an `exists_<n>` with the same name, is an error. Without
  dtype the type is `A`, as in GenroPy. Reason: ambiguous combinations are
  refused instead of picking one definition.
- **`subQueryColumn` (`query=`, `mode=`)** (A3.10): `json` and `xml` modes run
  only on PostgreSQL; any other `mode` raises `ValueError`. Reason: SQLite has
  no equivalent for json/xml.
- **`subQueryColumn(aggr=)`**: one call of the `.aggr()` grammar replaces the
  query columns; `aggr` with `mode`, or two aggregates, raise `ValueError`.
- **`#ENV(name[,fallback])`** (A3.18): expanded in a formulaColumn
  `sql_formula` only, as legacy (key, fallback key, `env_<name>()` method).
  Two corrections: single quotes in the value are doubled; no key and no
  method raise `ValueError` instead of producing `Not found <name>`.
  Elsewhere it raises `ValueError`.
- **`#BAG` / `#BAGCOLS` in columns** (A3.19): expanded in the query columns
  only; the value becomes a Bag, or its leaves become columns, after the fetch.
  Elsewhere they raise `ValueError`.

### Not available yet

- **`_override`** (A3.8): refused; a virtual column cannot replace a physical
  one. No issue yet. Workaround: rename the virtual column.
- **`pyColumn`** (A3.12): declared; selecting it raises "pyColumn is not
  connected yet". No issue yet. Workaround: compute the value after `fetch()`.
- **`toolColumn`** (A3.14): absent. No issue yet. Workaround: a
  `formulaColumn` with the explicit expression.
- **Dynamic columns: `variant=` with `variantColumn_<v>()`,
  `sqlparams[name]={field:...}`** (A3.15): not read. No issue yet.
  Workaround: declare explicit `formulaColumn`s.
- **`#PREF(path[,default])`** (A3.18): refused with `UnsupportedFeatureError`
  naming the macro ("macro #PREF is not available in this release"). No issue
  yet. Workaround: `:env_name` and `var_*`.
- **Dialect macros `#TSQUERY`, `#TSRANK`, `#TSHEADLINE`, `#VECQUERY`,
  `#VECRANK`** (A3.20): refused the same way, naming the macro. No issue yet.
  Workaround: explicit full-text SQL in `sql_formula` or in the `where`.

## 4 Relations

### Works as in GenroPy

- `relation()` to `'pkg.tbl.col'` or `'tbl.col'`, also to another package
  (A4.1).
- `one_name`, `many_name`, `one_group`, `many_group`, `many_order_by` (A4.5).
- `relation_name=` names the inverse relation `@<relation_name>` (A4.3).
- `onDelete`, `onUpdate` (Python actions `raise`, `cascade`, `setnull`,
  `ignore`, optionally `:message`), `onDelete_sql`, `onUpdate_sql` (SQL
  action of the foreign key; `onUpdate_sql` defaults to `cascade`),
  `deferred` (True by default with `setnull`), `onDuplicate` (A4.6).
- To-one path `@fkey_col.col` in columns, where, order_by (A4.7).
- Multi-hop path `@a.@b.c` (A4.8).
- Relation on a composite key (A4.10).
- The `relations` Bag of table and model (A4.15).
- **`one_one`** (A4.4): `True` or `'*'`. `'*'` without `relation_name` names
  the inverse after the many table and makes it public; otherwise the default
  inverse name is `pkg_tbl_col`, private without `relation_name`.
- **Join conditions `cnd`, `join_on`, `between`** (A4.12): each replaces the
  key equality in the ON clause; `join_on` wins over `cnd`;
  `between='value;low;high'` builds the range condition. A relation with `cnd`
  projects no FOREIGN KEY (GenroPy `mode='custom'`); `aggr` refuses these
  relations.

### Works differently

- **`relation(mode='foreignkey'/'relation'/'insensitive')`** (A4.2):
  `relation(to, foreign_key=, case_insensitive=)`; inside a package
  `foreign_key` defaults to `True`; `weak_relation` creates no FK; `mode=` is
  refused. Reason: `relation` creates the FK and `weak_relation` does not.
- **SQL action abbreviations** (A4.6): `onDelete_sql`/`onUpdate_sql` take the
  full names only (`cascade`, `restrict`, `no action`, `setnull`,
  `setdefault`); `'C'`, `'SN'` and the other abbreviations raise. Reason:
  planned for a later release.
- **To-many path `@relation_name.col`** (A4.9): raises
  `UnsupportedFeatureError`; with `one_one=True` it becomes a LEFT JOIN.
  Reason: no to-many JOIN, no multiplied rows, no implicit DISTINCT; `aggr`
  replaces it (decision of 16 October 2026).
- **`aliasTable` / `table_alias`** (A4.18): removed from the grammar;
  `virtualRelation(relation=...)` works only inside `aggr`. Reason:
  `virtualRelation` is to-many only (decision of 13 October 2026); a
  multi-hop to-one alias cannot be expressed.

### Not available yet

- **`joinColumn`** (A4.11): a relation on a virtual column exists, the
  `joinColumn` signature does not. No issue yet. Workaround: write
  `formulaColumn` with `relation` and an `aliasColumn` by hand.
- **`joinConditions`, `setJoinCondition`, query kwargs `jc_*`** (A4.13):
  refused. No issue yet. Workaround: the condition in the `where` or in a
  `subQueryColumn`.
- **`relationDict`** (A4.14): refused by `query()`. No issue yet.
  Workaround: `aliasColumn` in the model.
- **`getRelation`, `getRelationBlock`, `getJoiner`, `resolveRelationPath`,
  `relations_one`, `relations_many`, `manyRelationsList`,
  `oneRelationsList`** (A4.16): absent. No issue yet. Workaround: read
  `table.relations` and the joiner.
- **`relationExplorer`** (A4.17): absent. No issue yet. Workaround: none in
  the SQL layer; it is a UI function.

## 5 Writes

### Works as in GenroPy

- Table triggers `trigger_onInserting`, `onInserted`, `onUpdating`,
  `onUpdated`, `onDeleting`, `onDeleted`; `trigger_assignCounters` /
  `trigger_releaseCounters` (A5.4).
- Column triggers and `trigger_table` on the column (A5.5).
- `protect_update`, `protect_delete`, `protect_validate` (A5.6).
- Record data in writes: `@`, `pkey`, virtual and unknown keys discarded;
  `None` omitted in INSERT; UPDATE of every present key; `sql_value` always
  emitted (A5.14).
- Row policies in writes: physical delete, logical deletion by update,
  partition and draft not applied (A5.28).

### Works differently

- **`insert(record)`** (A5.1): same order, without package triggers (a table
  class defining `trigger_on<Event>_<pkg>` raises when the model is built),
  `dbo_onInserting` and `_onDbChange`; a table with declarations the cycle
  does not execute is refused before any hook. Reason: the write cycle is
  database-only; see [Current status](limitations.md) for the refusals.
- **`update(record, old_record=None, pkey=None)`** (A5.2): key from
  `old_record`, then `pkey`, then `record`; composite pkey as mapping or
  sequence; no storename; extra kwargs ignored. Reason: same pkey shape as
  legacy `record()`; the package storename: not recorded.
- **`delete(record)` and `deletable`** (A5.3): a missing string key returns
  without error; an incomplete dict is re-read with a lock; the DELETE must
  remove exactly one row, otherwise `RecordNotFoundError`; `deletable` is only
  a boolean. Reason: design decision of 2026-10-15 (provisional); `deletable`
  as a permission tag: not recorded.
- **`protect_draft` and `dbo_onInserting` / `dbo_onUpdating` /
  `dbo_onDeleting`** (A5.7): `protect_draft` is called directly in the legacy
  positions; no `dbo_*` is called. Reason: the dbo concept is removed; only
  `protect_draft` remains (decision of 2026-10-16).
- **`currentTrigger` and the trigger stack** (A5.9): same fields, without
  `level`; the stack is popped also on exceptions; `sql_*` commands do not
  enter it. Reason: stack as in GenroPy, with the pop on exception
  (decision of 2026-10-15).
- **`self.exception(name, record=, msg=)`** (A5.10): same exceptions; the
  caption is the pkey value; no localizer. Reason: not recorded (the
  `rowcaption` property is missing, A1.23).
- **`deleteRelated`** (A5.11): actions raise, cascade, setnull, ignore with
  `action:message`, default ignore; short forms are refused; no subtable or
  dbstore. Reason: legacy spellings kept, the short forms had no uses
  (decision of 2026-10-16).
- **`updateRelated`** (A5.12): continues to the next relation; raise with
  `'save'`; setnull ignored as in GenroPy; without `old_record` a
  `ValueError`. Reason: legacy defects corrected (decision of 2026-10-16,
  provisional).
- **`checkPkey`, `newPkeyValue`, `pkeyValue`** (A5.13): same order of
  strategies; composite key as JSON; UUID from `genro_toolbox`; `__syscode`
  without `sysRecord_<code>`. Reason: a time-ordered id (decision of
  16 October); `sysRecord_<code>` and the JSON format: not recorded.
- **`raw_insert`, `raw_update`, `raw_delete`, `insertMany`** (A5.17):
  replaced by `sql_insert` (record or list), `sql_update`, `sql_delete`: SQL
  only, no capability check. Reason: raw commands exist to skip triggers;
  `insertMany` becomes `sql_insert` with a list (decision of 2026-10-15).
- **`sql_deleteSelection(where, _pkeys)`** (A5.18): replaced by
  `query(...).sql_delete()`, one `DELETE ... WHERE pk IN (SELECT ...)`
  returning the row count. Reason: removed from the core (decision of
  2026-10-15).

### Not available yet

- **Package triggers `trigger_<event>_<pkg>` and `avoid_trigger_<pkg>`**
  (A5.8): not called. No issue yet. Workaround: put the logic in the table
  trigger.
- **Bag value in an `X` column** (A5.15): not converted; the driver raises an
  error. No issue yet (depends on the bagfield format of genro-bag).
  Workaround: convert the Bag to text before the write.
- **`deleteSelection` with triggers** (A5.20): absent. No issue yet.
  Workaround: fetch with `for_update` and `delete()` for each row.
- **`batchUpdate`** (A5.21): absent
  ([#32](https://github.com/asqueel-org/asqueel/issues/32)). Workaround: fetch
  with `for_update` and `update()` for each row.
- **`recordToUpdate(pkey, ...)`** (A5.22): absent
  ([#17](https://github.com/asqueel-org/asqueel/issues/17)). Workaround:
  `query(..., for_update=True).fetchRecord()` and `update(record, old_record)`.
- **`insertOrUpdate(record)`** (A5.23): absent. No issue yet. Workaround:
  `query(...).fetchRecord(ignoreMissing=True)`, then `insert` or `update`.
- **`newrecord`, `defaultValues`, `extendDefaultValues`, `recordCopy`**
  (A5.24): absent; a column with `default` or `default_from` blocks the write
  ([#28](https://github.com/asqueel-org/asqueel/issues/28)). Workaround:
  initial values in the caller or in `trigger_onInserting`.
- **`touchRecords`** (A5.25): absent. No issue yet. Workaround: fetch and
  `update()` for each row.
- **`_onDbChange` effects: `totalizer_<x>`, `logChanges`, `notify`** (A5.26):
  no `_onDbChange`; `logChanges`, `notify` and `totalizer_<x>` are refused.
  No issue yet. Workaround: application after-triggers or database
  triggers.
- **Logical archiving cascade `onArchivingRecord` / `archiveRelatedRecords`**
  (A5.27): the children are not touched. No issue yet. Workaround: update the
  children in `trigger_onUpdating`.
- **`check_updatable`, `check_deletable`, `isDraft`, `islocked_write`,
  `islocked_delete`, `hasProtectionColumns`** (A5.29): absent. No issue yet.
  Workaround: catch the exceptions of `protect_*`.
- **Table helpers `setColumns`, `changePrimaryKeyValue`, `empty`,
  `fillFromSqlTable`, `duplicateRecord`, copy/paste** (A5.30): absent. No
  issue yet. Workaround: `record`, `update`, `insert` and `sql_delete` on the
  query.

## 6 Transactions

### Works as in GenroPy

- `tempEnv(**kwargs)` / `temp_env` (A6.1).
- `connectionName` in the environment, `currentConnectionName`,
  `usingMainConnection`, `'_main_connection'` (A6.5).
- `:env_*` parameters and argument preparation in `execute` (A6.19).
- `deferToCommit` / `deferAfterCommit` (A6.12): same blocks, deduplication and
  returned kwargs; the queues live in `currentEnv` under the GenroPy keys
  `to_commit_defer_calls__main_db_<connectionName>` and
  `after_commit_defer_calls__main_db_<connectionName>`, so `clearCurrentEnv()`
  drops them.

### Works differently

- **`currentEnv`, `updateEnv`, `clearCurrentEnv`** (A6.2): a per-thread dict;
  the setter raises `TypeError` for a non-dict; `current_env` returns a
  read-only copy. Reason: `current_env` is a snapshot; the `TypeError`: not
  recorded.
- **`workdate` / `locale`** (A6.3): same `workdate` fallback; `locale` comes
  from `GNR_LOCALE` or the system, without validation. Reason: not recorded.
- **Per-thread, per-name connections opened at the first statement** (A6.6):
  a name may point to another physical database; with explicit declarations an
  undeclared name raises `ValueError`; a connection is used only in the thread
  that created it. Reason: not recorded.
- **`db.commit()`** (A6.8): same order on the selected connection; inside a
  write or a hook, a commit on the connection in use raises
  `TransactionStateError`, on another named connection it is allowed; then
  `onDbCommitted()` runs once, as legacy. Reason: avoids a deadlock reported in
  GenroPy (decision of 2026-10-15, provisional).
- **`db.rollback()` / `rollbackAll()`** (A6.9): rollback also empties the
  deferred queues; `rollbackAll` is absent because there is one store. Reason:
  a GenroPy defect on rollback and deferred callbacks is corrected (decision
  of 2026-10-16).
- **Automatic rollback on SQL error** (A6.10): rollback and re-raise; if the
  rollback fails the connection is discarded and stays rollback-only until
  `rollback()`. Reason: documented recovery contract.
- **Python error in a trigger or write hook** (A6.11): the connection becomes
  rollback-only; commit is refused until `rollback()`. Reason: decision of
  2026-10-15 (provisional).
- **`deferredRaise(exception)`** (A6.13): `TypeError` for a non-exception;
  the exception is kept in `currentEnv['_pendingExceptions']`, as in GenroPy;
  at commit, `DeferredCommitError`, a rollback-only connection and an emptied
  list. Reason: a GenroPy defect is corrected (decision of 2026-10-16).
- **`db.execute(sql, sqlargs, cursor, cursorname, autocommit, dbtable, storename,
  _adaptArguments)`** (A6.17): the legacy signature; it returns the open
  cursor, whose rows are read by name. `sql` may also be a `CompiledQuery`.
  `cursorname` opens a server-side cursor on PostgreSQL (`'*'` generates the
  name) and is ignored on SQLite. `dbtable` is accepted. `storename`, `cursor`
  and `_adaptArguments=False` raise `UnsupportedFeatureError`. A driver error
  raised while fetching rolls the connection back, as one raised by execute.
  Reason: one store in this release.
- **`autocommit`** (A6.18): `execute(..., autocommit=True)` commits after the
  statement, as legacy; an autocommit connection is refused. Reason: the
  connection completes only through `commit()`.
- **`db.closeConnection()`** (A6.21): rollback and close of every connection
  of the thread; the database stays usable; refused inside a write; the first cleanup error is re-raised
  after closing the others. Reason: not recorded for the error propagation.
- **`for_update` on SQLite** (A6.27): it takes the database write lock; the
  legacy emits no lock on SQLite. Transactions are deferred as legacy: reads
  open none. Reason: `for_update` locks as on PostgreSQL (decision of
  2026-10-15).
- **`setLocale()`** (A6.4): hands `currentEnv['locale']` to the adapter, whose
  `setLocale` has no effect, as legacy. Reason: not recorded.
- **`setConstraintsDeferred()`** (A6.28): PostgreSQL runs `SET CONSTRAINTS ALL
  DEFERRED`; SQLite runs `PRAGMA defer_foreign_keys = ON` (legacy SQLite has no
  foreign keys). Reason: asqueel migrates deferrable foreign keys on SQLite.
- **`analyze()` / `vacuum(table='', full=False)`** (A6.29, A8.18): `analyze()`
  runs `ANALYZE` in the current transaction. `vacuum` runs on a separate
  connection: `VACUUM [FULL] ANALYZE [table]` on PostgreSQL, `VACUUM` then
  `ANALYZE [table]` on SQLite. Reason: legacy emits `VACUUM ANALYZE` on SQLite,
  which SQLite rejects (GenroPy defect corrected).

### Not available yet

- **`storename`, `use_store`, multiple stores, `currentStorename`,
  `connection`, `connectionKey`, `get_dbname`** (A6.7): a storename other than
  `_main_db` raises `UnsupportedFeatureError`. No issue yet. Workaround: one
  `AsqueelDb` per physical database, or a declared named connection.
- **`autoCommit`, `dbevents`, `systemDbEvent`, `GnrMissedCommitException`,
  `tblobj.dbevents` / `notifyDbUpdate`** (A6.14): absent. No issue yet.
  Workaround: `deferAfterCommit` for application notifications.
- **NOTIFY: table attribute `notify`, `db.notify`, `db.listen`** (A6.16):
  absent. No issue yet. Workaround: run NOTIFY with `db.execute`.
- **SQL comment with the user, `sql_audit`, debugger** (A6.20): absent. No
  issue yet. Workaround: driver logging (psycopg, sqlite3).
- **`tblobj.lock(mode, nowait)` / `adapter.lockTable`** (A6.25): absent. No
  issue yet. Workaround: `db.execute('LOCK ...')`.
- **`for_update` with a string mode (`'NOWAIT'`, `'SKIP LOCKED'`)** (A6.26):
  `for_update` must be a boolean. No issue yet. Workaround: boolean
  `for_update`.

## 7 Migration

### Works as in GenroPy

- Creation of a missing database (CREATE DATABASE) (A7.5).
- Application schemas and CREATE SCHEMA from the package `sqlschema` (A7.6).
- Migrated column attributes and dtype normalization (A7.10).
- Primary key in the migration: pkeys, composite pkey, pkey change (A7.11).
- Removal policy (`removeDisabled`) (A7.14).
- FKs from relations with `foreign_key`: SQL actions, deferred, composite
  columns, target schema (A7.15).
- `unique` on a column and `compositeColumn(unique=True)` (A7.20).
- Constraint and index names (`ignore_constraint_name`) (A7.22).

### Works differently

- **`db.checkDb(applyChanges=)`, `model.check()`, `modelChanges`,
  `applyModelChanges()`** (A7.1): `db.migration_plan()` with `plan.empty`, and
  `db.migrate()`; one engine, asqueel-migration. Reason: not recorded for the
  absence of `checkDb`.
- **`db.diffOrmToSql()` / `SqlMigrator.getChanges()`** (A7.2):
  `db.migration_plan()` changes nothing and returns
  `MigrationPlan(commands, warnings, skipped)`. Reason: not recorded for the
  changed return value.
- **`db.syncOrmToSql()` / `SqlMigrator.applyChanges()`** (A7.3): `db.migrate()`
  refuses before any DDL if changes were skipped and verifies after the run;
  it refuses in-memory SQLite, a connection without database name and a model
  without tables. Reason: skipped changes are refused and the result is
  verified.
- **Extensions: `SqlMigrator(extensions=)` and automatic unaccent** (A7.9):
  declared with `db.extensions().extension(name)`, never removed;
  `column(unaccent=True)` is refused. Reason: not recorded for the removed
  automatic extension.
- **Column type change** (A7.12): same engine on PostgreSQL; on SQLite the
  change is skipped and `migrate()` refuses. Reason: documented in
  [Migrations](migrations.md).
- **Abbreviated SQL actions `'C'`, `'R'`, `'N'`, `'SN'`, `'SD'`, `'SETNULL'`**
  (A7.16): refused; `cascade`, `restrict`, `no_action`, `set_null`,
  `set_default` are accepted, case and spaces normalized. Reason: not
  recorded.
- **Index on relation columns** (A7.17): an FK relation gets a source index
  unless `indexed=False`; `foreign_key=False` gets none; `weak_relation`
  indexes source and target. Reason: not recorded for FK targets and
  `foreign_key=False`.
- **`column(indexed=True)` and `indexed={options}`** (A7.18): `indexed` is
  only a boolean; options go through `index()`. Reason: not recorded.
- **`index()` in the migration** (A7.19): projected with `unique`, `method`,
  `where`, `tablespace`, `with_options` and per-column ordering. Reason: not
  recorded.
- **`model.importFromDb()`** (A7.28): `inspect_postgres` returns
  `ImportResult(model, warnings)` and does not touch `db.model`. Reason: the
  imported model cannot be queried
  ([#22](https://github.com/asqueel-org/asqueel/issues/22)).
- **Model JSON: `extractOrm`, `ormStructure`, `jsonModelWithoutMeta`**
  (A7.29): rendered by `SqlMigrationRenderer`; no orm/sql Bag view. Reason:
  not recorded.

### Not available yet

- **Package `readOnly` / storename excluded from migration** (A7.7):
  `readOnly=True` is refused. No issue yet. Workaround: do not declare those
  tables in the migrated model.
- **Tenant schemas: `multi_tenant` tables replicated per tenant** (A7.8):
  `tenant` is not an option of the grammar and `multi_tenant` is not a table
  attribute: both raise. No issue yet. Workaround: one database per tenant.
- **`force`, `backup`, `verifyConversionBackups`** (A7.13): absent. No issue
  yet. Workaround: use `SqlMigrator` of asqueel-migration directly.
- **TSV dtype: mandatory gin index** (A7.21): no automatic index. No issue
  yet. Workaround: `index(columns=..., method='gin')`.
- **`model.enableForeignKeys(enable=False)`** (A7.26): absent. No issue yet.
  Workaround: `weak_relation` where the FK is not needed.
- **Direct DDL: `createDb`, `dropDb`, `createSchema`, `dropSchema`,
  `dropTable`, `dropColumn`** (A7.27): absent. No issue yet. Workaround: SQL
  executed by the application.

## 8 Dialects

### Works as in GenroPy

- `db.adapter`, one adapter object per implementation (A8.1).
- **Backend choice `implementation`** (A8.1): default `'sqlite'`; `'postgres'`,
  `'postgres3'`, `'sqlite'`; custom modules as `'<name>:<module>'`;
  `currentImplementation` in the environment selects another adapter. In
  asqueel `'postgres'` and `'postgres3'` both load the psycopg 3 adapter.
- `db.adapter.string_agg(field, separator)` and `unaccentFormula(field)` (A8.15, A8.16).
- Collections after `IN :param` (A8.3).
- `REGEXP` / `~*` and the regexp function on SQLite (A8.4).
- `IS TRUE` / `IS FALSE` on SQLite (A8.6).
- **Value types on SQLite** (A8.9): columns declared `date`, `time`,
  `timestamp`, `numeric` and `boolean`/`bool` return `datetime.date`,
  `datetime.time`, `datetime.datetime`, `Decimal` and `bool`;
  `datetime.time` parameters are passed as ISO strings. In the legacy a
  `boolean` column returns an integer, because only `bool` has a converter.
- **SQLite transactions** (A8.10): the driver opens a deferred `BEGIN`
  before the first INSERT, UPDATE or DELETE; reads open no transaction and
  hold no lock.

### Works differently

- **`mask_field_sql` and `ageAtDate`** (A8.16): an invalid `mask_field_sql`
  mode raises `ValueError` instead of falling back to `'2-4'`; `ageAtDate` on
  SQLite raises `UnsupportedFeatureError`, because the legacy SQL uses
  `EXTRACT(EPOCH ...)`, which SQLite does not have. Reason: anything outside
  the grammar raises.
- **`:name` parameters and the PostgreSQL driver** (A8.2): psycopg 3 only,
  with server-side binding; a missing parameter becomes `None`. Reason: SQL and
  mapping stay separate; a literal `%` is tracked in
  [#19](https://github.com/asqueel-org/asqueel/issues/19).
- **ILIKE on SQLite** (A8.5): only the operator is replaced, outside strings,
  quoted identifiers and comments. Reason: not recorded.
- **SQLite schemas as attached files** (A8.7): `<name>_<schema>.db` files,
  default schema `main`, the folder must exist. Reason: same layout as the
  migration adapter; the file name change: not recorded.
- **SQLite connection opening** (A8.8): `PRAGMA foreign_keys = ON`; only
  `timeout` (default 20 seconds, as legacy) and `cached_statements`; SQLite
  3.35 required. Reason: FKs are on by decision of 2026-10-16.
- **`for_update` on SQLite** (A8.10): `BEGIN IMMEDIATE` when no transaction
  is open, a no-op UPDATE inside an open one; the legacy emits no lock.
  Reason: `for_update` locks as on PostgreSQL (decision of 2026-10-15).
- **Bulk insert (`insertMany`, `executemany`)** (A8.14): `sql_insert` with a
  list runs one executemany per group of records with the same columns,
  without RETURNING and without generating the pkey. Reason: `insertMany`
  becomes `sql_insert` with a list (decision of 2026-10-15); the missing pkey:
  not recorded.
- **Adapter capabilities** (A8.20): SQL capabilities per dialect, reducible in
  the constructor; no `has_capability`. Reason: declaring a capability does
  not implement it; the write compiler does not check all of them
  ([#21](https://github.com/asqueel-org/asqueel/issues/21)).
- **LIMIT and OFFSET per dialect** (A8.21): `LIMIT 0` is emitted; on SQLite
  OFFSET without LIMIT adds the maximum LIMIT. Reason: the legacy truthiness
  of `limit=0` is not imported; SQLite OFFSET: not recorded.
- **SQL types of dtypes** (A8.22): DDL from asqueel-migration with the legacy
  PostgreSQL types; `X`, `Z`, `P` and `A` without size become `T` in package
  models. Reason: not recorded.

### Not available yet

- **`for_update` with a mode (`'NOWAIT'`, `'SKIP LOCKED'`)** (A8.11):
  `for_update` must be a boolean. No issue yet. Workaround: explicit SQL with
  `db.execute`.
- **Table `lock()` (`lockTable`)** (A8.12): no public method. No issue yet.
  Workaround: `db.execute('LOCK ...')`.
- **`db.listen` / `db.notify`** (A8.17): absent. No issue yet. Workaround:
  `db.execute('NOTIFY channel, :payload')` and a dedicated psycopg connection.
- **`createDb`, `dropDb`, `dbExists`, `dump`, `restore`, `importRemoteDb`**
  (A8.19): absent. No issue yet. Workaround: `createdb`, `dropdb`, `pg_dump`,
  `pg_restore`.
- **Other legacy adapters: mssql, mysql, db2_400, fourd, postgres8000**
  (A8.23): refused with `UnsupportedFeatureError`. No issue yet. Workaround:
  PostgreSQL or SQLite.

## New in asqueel

- **`@rel.aggr(...)` and `@rel.order_by('...').aggr(...)`** (A4.19): count,
  sum, avg, min, max, join, to_json, to_xml over related rows, in the
  projection only; `to_xml` needs PostgreSQL.
- **`virtualRelation`** (A4.20): derived (`relation=`) or direct (`table=`)
  to-many relations with `var_*`, usable only inside `aggr`; `ask` is
  refused.
- **Relation inherited by an `aliasColumn`** (A4.21): `@alias.col` works
  without `.relation()` on the alias.
- **RETURNING of database-decided values** (A5.16): values from `sql_value`,
  generated expressions, omitted `sql_default` and serial columns are written
  into the record before the after-triggers, on PostgreSQL and SQLite; on a
  dialect without the capability RETURNING is dropped without error
  ([#21](https://github.com/asqueel-org/asqueel/issues/21)).
- **`query(...).sql_update(values)`** (A5.19): one
  `UPDATE ... WHERE pk IN (SELECT ...)`; `group_by` and `having` are refused.
- **`session(db, **env)`**: the unit of work outside a request, as a GenroPy
  page request; entry clears `currentEnv` and applies `env`, exit calls
  `closeConnection()`, also when the body raises; a nested session on the same
  thread raises `TransactionStateError`.
- **`asqueel db plan`, `asqueel db apply [--allow-removals]`, `asqueel check`**
  (A7.4): migration and model check from the command line.
- **Table and column `comment` in the migration** (A7.23).
- **Declared CHECK constraint `constraints().constraint(constraint_type='CHECK')`**
  (A7.24).
- **`serial4` dtype** (A7.25): 32-bit SERIAL.
- **Minimum SQLite version** (A8.13): `connect()` raises `RuntimeError`
  below SQLite 3.35, the version that introduced RETURNING.
