# Legacy Inventory — SQL Test Suite (oracle material)

**Version**: 0.1.0 · **Last Updated**: 2026-07-06 · **Status**: 🔴 DA REVISIONARE

Part of the asqueel design documentation set (see `00_INDEX.md`).
Scope: map of the legacy test suite, the model-definition fixtures
(canonical grammar usage examples), the behaviors pinned by tests, and
the oracle shortlist for the new grammar's acceptance suite. Source:
Genropy worktree `develop` @ `83c138bb6`.

---

Source tree: `/Users/gporcari/Sviluppo/Genropy/genropy/worktrees/develop/gnrpy/tests/sql/`
Companion project (real model fixture): `/Users/gporcari/Sviluppo/Genropy/genropy/worktrees/develop/projects/test_invoice/`

---

## 1. Suite map

| File | Covers | ~Tests | Dependencies |
|---|---|---|---|
| `common.py` | Shared infra: `BaseGnrSqlTest`, `MockApplication`, `get_pg_config()`, and **`configurePackage()` — the inline "video" model fixture** | — | `testing.postgresql` (skipped on win32); env vars `GITHUB_WORKFLOW` / `GNR_TEST_PG_*` select real PG |
| `conftest.py` | Module-scoped fixtures `db_sqlite`, `db_pg`, `db_pg3`: boot `GnrApp('test_invoice')`, `model.check(applyChanges=True)`, bulk-import CSVs from `projects/test_invoice/data/export/` | — | test_invoice project + CSV data; sqlite tempdir; PG via `get_pg_config` |
| `a_structure_load_test.py` | Model **source** layer (`packageSrc`, `table()`, `column()`, `.relation()`, package/table mixins via `config_db`) — no DB needed | 10 | none (pure model src) |
| `b_structure_build_test.py` | Model **object** layer after `db.startup()`: `DbModelObj`, `DbPackageObj`, `DbTableObj`, `DbColumnObj`, containers, `relations_one/many`, `@rel.col` lookup | 8 | none (pure model obj) |
| `d_table_test.py` | `SqlTable` runtime: insert/update/delete/record, `insertMany`, `raw_insert/raw_update`, `deferToCommit`, `saveModel` | 17 × 3 dialect classes | sqlite + postgres + postgres3; `data/dbdata_base.xml` |
| `e_query_test.py` | `SqlQuery` runtime: count/fetch/cursor, `:param` binding, `IN :tuple`, `#IN_RANGE` macro, joins via `relationDict`, subtable filters, limit/offset | 19 × 3 dialect classes | same as above |
| `f_selection_test.py` | `SqlSelection` sort/output/filter/freeze | 4 × 3 | same |
| `h_query_surface_test.py` | SqlQuery public API surface: `fetchAsDict/Grouped/AsBag/Pkeys/AsJson`, `test()`, `sqltext`, `compiled`, `setJoinCondition`, `*@rel` star expansion | 41 × 2 | sqlite + postgres |
| `h_record_surface_test.py` | SqlRecord API: `out_dict/json/record/bag/newrecord/template` | 37 | sqlite + postgres |
| `h_selection_surface_test.py` | SqlSelection API: output modes, sort, filter, apply, sum, `newRow`, `getByKey`, `allColumns` | 58 | sqlite + postgres |
| `test_model_structure.py` | **Exhaustive structural tests of `gnrsqlmodel`** on the real test_invoice model (SQLite, no data needed) | 162 | test_invoice app (`BaseGnrAppTest`) |
| `test_compiler_coverage.py` | **Runtime compiler oracle**: real queries, real results for every virtual-column type, macros, subtables, partitions, joinConditions | 291 | `db_pg`/`db_sqlite` fixtures + CSV data (hard-coded counts, e.g. `CUSTOMER_COUNT = 3200` at `test_compiler_coverage.py:23`) |
| `test_compiler_simulation.py` | Relation-tree resolution perf simulation (build vs cached vs rebuild) | 4 | `db_sqlite` |
| `test_composite_column.py` | compositeColumn runtime: JSON-array value, composite-key JOINs, deep navigation, WHERE/ORDER BY through composite | 14 (7 PG + 7 sqlite) | `db_pg`/`db_sqlite` |
| `test_gnrsqlmigration.py` | `SqlMigrator`: DDL diff/apply — exact SQL text asserted | 79 | postgres/postgres3 only (capability-gated) |
| `test_macro_registration.py` | `db.addMacro()` registry, adapter macros, `MacroExpander.register/replace`, package-level macros via `pkgBroadcast` (issue #617) | 26 | sqlite + PG + test_invoice app |
| `test_vecquery_macro.py` | `#VECQUERY`/`#VECRANK` PG macros + TSQUERY regressions (#583) | 13 | none (FakeQueryCompiler, pure expander) |
| `test_sqlite_boolean_rewrite.py` | `IS NOT TRUE` rewrite bug #549 (NULL-safe draft filter on sqlite) | 4 | both DBs |
| `test_encrypted_columns.py` | Encrypted columns #747: `Encryptor` modes R/Q/X, `encrypted=` column attribute end-to-end | 37 | sqlite (test_invoice customer table) |
| `test_gnrsql.py` | `GnrSqlDb` generic attrs, `tempEnv`, locale | 7 | light |
| `test_gnrsqlutils.py` | `importModelFromDb` smoke | 1 | light |
| `test_gnrsqlxml2py.py` | `structToPyFull` (XML struct → .py codegen) | 1 | tempdir |
| `test_import_export_tojson.py` | model `toJson` import/export | 1 | light |
| `test_db_notify.py` | `adapter.notify()` / `_dbNotify` payloads (#663) | 12 | PG LISTEN/NOTIFY |
| `test_gnrlistener.py` | `@listen` decorator, `tblobj.notify()`, GnrListener autodiscovery | 27 | PG |
| `test_gnrbaseadapter.py` | Base adapter unit tests (fake cursor/connection) | 32 | none |
| `test_adapterinheritance.py` | All adapters subclass `SqlDbAdapter` | 2 | none |
| `test_connection_error.py` | #654 unreachable DB → `GnrSqlConnectionException` | 6 | mocks |
| `test_gnrexceptions.py` | Exception codes | 3 | none |
| `test_relations_benchmark.py` / `test_relations_thread_safe.py` | Relation-tree cache perf (#548) / resolver lock deadlock (#548) | 4 / 2 | `db_sqlite` / mocks |
| `data/configTest.xml` | sqlite filename config (`testsqlite.db`) | — | — |
| `data/dbdata_base.xml` | sample rows for the "video" package (movies, people, cast, dvd, location) | — | — |
| `data/simplestruct.xml` | XML-serialized model source (packages→tables→columns with `tag="table"/"column"`, `relation=` attribute) | — | — |

---

## 2. Model-definition fixtures (MOST IMPORTANT)

### 2a. Inline "video" package — `common.py:114-159` (`configurePackage`)

The minimal grammar: package attributes, `pkg.table(...)`, `table.column(...)`, `.relation(...)` chained on the column, `subtable`, dtype as 2nd positional arg, validators as `validate_*` kwargs, `indexed=`:

```python
# common.py:114-134
def configurePackage(pkg):
    pkg.attributes.update(comment='video package', name_short='video', name_long='video', name_full='video')

    people = pkg.table('people', name_short='people', name_long='People',
                       rowcaption='name,year:%s (%s)', pkey='id')
    people.column('id', 'L')
    people.column('name', name_short='N.', name_long='Name')
    people.column('year', 'L', name_short='Yr', name_long='Birth Year')
    people.column('nationality', name_short='Ntl', name_long='Nationality')

    cast = pkg.table('cast', name_short='cast', name_long='Cast',
                     rowcaption='', pkey='id')
    cast.column('id', 'L')
    cast.subtable("first_movie", condition="$movie_id=1")
    cast.subtable("second_movie", condition="$movie_id=2")
    cast.column('movie_id', 'L', name_short='Mid',
                name_long='Movie id').relation('movie.id')
    cast.column('person_id', 'L', name_short='Prs',
                name_long='Person id').relation('people.id')
```

```python
# common.py:136-145
    movie = pkg.table('movie', name_short='Mv', name_long='Movie',
                      rowcaption='title', pkey='id')
    movie.column('id', 'L')
    movie.column('title', name_short='Ttl.', name_long='Title',
                 validate_case='capitalize', validate_len='3:40')
    movie.column('genre', name_short='Gnr', name_long='Genre',
                 validate_case='upper', validate_len='3:10', indexed='y')
```

Note `dvd` uses a non-`id` pkey: `dvd = pkg.table('dvd', name_short='Dvd', name_long='Dvd', pkey='code')` (`common.py:147`).

### 2b. Mixin-based definition — `a_structure_load_test.py:87-100`

`config_db(self, pkg)` is the universal hook; mixins extend existing tables or add new ones:

```python
# a_structure_load_test.py:87-97
class MyTblMixin(object):
    def config_db(self, pkg):
        t = pkg.table('people')
        t.column('foo')
    ...
class MyPkgMixin(object):
    def config_db(self, pkg):
        pkg.table('actor', name_short='act', name_long='actor', pkey='id').column('id', 'L')
```

Registered via `cls.db.packageMixin('video', pm)` / `cls.db.tableMixin('video.people', tm)` (`a_structure_load_test.py:39-40`).

### 2c. test_invoice package — the canonical full-grammar fixture

**Package config with sqlschema, macros and custom types** — `packages/invc/main.py:12-31`:

```python
class Package(GnrDboPackage):
    def config_attributes(self):
        return dict(comment='invc package',sqlschema='invc',sqlprefix=True,
                    name_short='Invc', name_long='Invoicer', name_full='Invc')
    def registerMacros(self, db):
        db.addMacro('UPPERCASE', re.compile(r'#UPPERCASE\(([^)]+)\)'), _expand_uppercase)
    def custom_type_money(self):
        return dict(dtype='N',size='14,2',format='#,###.00')
    def custom_type_perc(self):
        return dict(dtype='N',size='5,2',format='##.00')
```

**customer** — `packages/invc/model/customer.py`. Header with `partition_state`, `caption_field`, `sysFields(draftField=True)`; FK with `relation_name/mode/onDelete`; encrypted columns:

```python
# customer.py:6-16, 20-22
tbl = pkg.table('customer', pkey='id', name_long='!!Customer', name_plural='!!Customers',
                caption_field='account_name',
                partition_state='invc_state')
self.sysFields(tbl, draftField=True)
tbl.column('account_name', name_long='!!Account name',name_short='Account name', validate_notnull=True, validate_len='2:40')
...
tbl.column('state',size=':5',name_long='!!State',name_short='Pr.').relation('invc.state.code',relation_name='clients',mode='foreignkey',onDelete='raise')
...
tbl.column('access_token', name_long='!!Access Token', encrypted='X')
tbl.column('bank_account', name_long='!!Bank Account', encrypted='R')
tbl.column('registration_id', name_long='!!Registration ID', encrypted='Q')
```

formulaColumn in all its forms — `select=dict(...)`, `select` **with relation chained on it**, `sql_formula`, `exists=dict(...)`, named subselects `select_<name>` + `#name` placeholder, `var_*` params:

```python
# customer.py:23-46
tbl.formulaColumn('n_invoices',select=dict(table='invc.invoice',
                                          columns='COUNT(*)',
                                          where='$customer_id=#THIS.id'),
                              dtype='L',name_long='N.Invoices')
...
tbl.formulaColumn('last_invoice_id',select=dict(table='invc.invoice',
                                          columns='$id',
                                          where='$customer_id=#THIS.id',
                                          order_by='$date DESC',
                                          limit=1),
                              dtype='T',name_long='Last Invoice'
                              ).relation('invoice.id',relation_name='last_invoice')
tbl.formulaColumn('full_address',
                  sql_formula="$street_address || ', ' || $suburb",
                  dtype='T',name_long='Full Address')
tbl.formulaColumn('has_invoices',
                  exists=dict(table='invc.invoice',
                              where='$customer_id=#THIS.id'),
                  dtype='B',name_long='Has Invoices')
```

```python
# customer.py:56-63, 73-83, 93-96
tbl.aliasColumn('state_name', relation_path='@state.name',
                name_long='State Name')
...
tbl.aliasColumn('region_name',
                relation_path='@state.@region_code.name',
                name_long='Region Name')
...
tbl.pyColumn('customer_score', dtype='N',
             required_columns='$account_name,$email',
             name_long='Customer Score')
tbl.formulaColumn('invoice_numbers',
                  sql_formula="array_to_string(ARRAY(#inv_nums), ', ')",
                  select_inv_nums=dict(table='invc.invoice', columns='$inv_number',
                                       where='$customer_id=#THIS.id',
                                       order_by='$date DESC', limit=5),
                  dtype='T', name_long='Invoice Numbers')
...
tbl.subtable('residential', condition="$customer_type_code = 'RES'")
tbl.subtable('commercial', condition="$customer_type_code = 'COM'")
```

pyColumn implementation convention (`customer.py:103-107`): `def pyColumn_customer_score(self, record, field)`.

**invoice** — `packages/invc/model/invoice.py`. `joinColumn` with `cnd=` and `one_one`, `subQueryColumn` in three modes, `var_*` bind params, `:env_workdate`:

```python
# invoice.py:7-9, 11-16
tbl = pkg.table('invoice', pkey='id', name_long='!!Invoice', name_plural='!!Invoice',
                caption_field='inv_number',
                partition_customer_state='invc_state')
...
tbl.column('inv_number' ,size='10',name_long='!!Invoice number', name_short='Inv N',unique=True)
tbl.column('customer_id',size='22' ,group='_',name_long='!!Customer'
                                ).relation('customer.id',
                                            relation_name='invoices',
                                            mode='foreignkey',
                                            onDelete='raise')
```

```python
# invoice.py:53-58
tbl.joinColumn('discount_tier_id', name_long='Discount Tier').relation(
    'discount_tier.id',
    cnd="""@discount_tier_id.customer_type_code=@customer_id.customer_type_code
           AND @discount_tier_id.min_amount <= $total
           AND @discount_tier_id.max_amount > $total""",
    relation_name='invoices_in_tier', one_one=True)
```

```python
# invoice.py:80-87 (var_* params) and 149-163 (subQueryColumn)
tbl.formulaColumn('status_label',
                  sql_formula="""CASE WHEN $total > 1000 THEN :high_label
                                      WHEN $total > 100 THEN :mid_label
                                      ELSE :low_label END""",
                  var_high_label='Premium Invoice', ...)
...
tbl.subQueryColumn('rows_json',
                   query=dict(table='invc.invoice_row',
                              columns='$product_id,$quantity,$unit_price',
                              where='$invoice_id=#THIS.id'),
                   mode='json')
tbl.subQueryColumn('notes_xml',
                   query=dict(table='invc.invoice_note', columns='$note_type,$note_text',
                              where='$invoice_id=#THIS.id'),
                   mode='xml')
tbl.subQueryColumn('max_row_price',
                   query=dict(table='invc.invoice_row', columns='MAX($unit_price)',
                              where='$invoice_id=#THIS.id'),
                   dtype='N', name_long='Max Row Price')
```

**invoice_row** — `packages/invc/model/invoice_row.py`. Cascade FK, deep aliasColumn, **aliasColumn with `.relation()`** (reverse virtual relation), `static=True`, **aliasTable**, `#PREF` macro:

```python
# invoice_row.py:7-10
self.sysFields(tbl,counter='invoice_id')
tbl.column('invoice_id',size='22' ,group='_',
            name_long='!!Invoice').relation('invoice.id',relation_name='rows',mode='foreignkey',onDelete='cascade')
```

```python
# invoice_row.py:16-26
tbl.aliasColumn('customer_name', relation_path='@invoice_id.@customer_id.account_name',
                name_long='Customer name')
tbl.aliasColumn('customer_id', relation_path='@invoice_id.customer_id',
                name_long='Customer id'
                ).relation('customer.id',relation_name='invoice_rows_by_customer')
...
tbl.aliasColumn('customer_state',
                relation_path='@invoice_id.@customer_id.@state.name',
                name_long='Customer State')
```

```python
# invoice_row.py:59-61, 84-98
tbl.aliasColumn('customer_region',
                relation_path='@invoice_id.@customer_id.@state.@region_code.name',
                name_long='Customer Region')
...
tbl.formulaColumn('is_exempt_vat',
                  sql_formula="@product_id.vat_type_code IN :exempt_codes",
                  var_exempt_codes=['FRE', 'INP'],
                  dtype='B', name_long='Is Exempt VAT')
tbl.aliasColumn('invoice_date_static',
                relation_path='@invoice_id.date',
                static=True, dtype='D',
                name_long='Invoice Date Static')
# aliasTable: shortcut for @invoice_id.@customer_id
tbl.aliasTable('customer', relation_path='@invoice_id.@customer_id')
tbl.formulaColumn('adjusted_total',
                  sql_formula='$line_total * #PREF(markup_rate,1)',
                  dtype='N', name_long='Adjusted Total')
```

**price_year / price_year_note** — `packages/invc/model/price_year.py:16-17` and `price_year_note.py:15-18`. **compositeColumn**, both unique-target and FK-side with `.relation()` to another compositeColumn:

```python
# price_year.py:16-17
tbl.compositeColumn('product_year_key',
                    columns='product_id,year', unique=True)
```

```python
# price_year_note.py:15-18
tbl.compositeColumn('product_year_ref',
                    columns='product_id,year').relation(
    'price_year.product_year_key',
    relation_name='notes')
```

And navigation through it (`price_year_note.py:21-29`): `aliasColumn('price_year_price', relation_path='@product_year_ref.unit_price')`, `aliasColumn('product_description', relation_path='@product_year_ref.@product_id.description')`.

**product** — `packages/invc/model/product.py`. `bagItemColumn`, Bag-typed column with `subfields`, shorthand formulaColumn (2nd positional = formula):

```python
# product.py:16-17, 38-43, 53-55
tbl.column('details',dtype='X',name_long='!!Details',subfields='product_type_id')
tbl.formulaColumn('picture',"image_url" ,dtype='P',name_long='!!Picture',name_short='Img',cell_format='auto:.5')
...
tbl.bagItemColumn('detail_weight', bagcolumn='$details',
                  itempath='specs.weight', dtype='N',
                  name_long='Detail Weight')
...
tbl.pyColumn('computed_margin', dtype='N',
             required_columns='$unit_price',
             name_long='Computed Margin')
```

**state / region / lookups** — non-id pkey and `lookup=True` pattern, `sysFields(tbl, id=False)`:

```python
# state.py:6-12
tbl = pkg.table('state', pkey='code', name_long='!!State', 
                name_plural='!!States',caption_field='code',lookup=True)
self.sysFields(tbl,id=False)
tbl.column('code' ,size=':5',name_long='!!Code')
tbl.column('name' ,size=':100',name_long='!!Name')
tbl.column('region_code', size=':5', name_long='!!Region').relation(
    'region.code', relation_name='states', mode='foreignkey', onDelete='raise')
```

Same pattern in `customer_type.py`, `payment_type.py`, `vat_type.py`, `staff_role.py`, `region.py`. `product_type.py:9` shows `self.sysFields(tbl,hierarchical='description',counter=True,df=True)`.

**staff** — cross-package FK and `onDelete='setnull'` (`staff.py:22-24`):

```python
tbl.column('user_id', size='22', name_long='!!User').relation(
    'adm.user.id', relation_name='staff_member',
    mode='foreignkey', onDelete='setnull')
```

**postcode** — `legacy_name=` and `indexed=True`/`unique=False` (`postcode.py:7-9`).

### 2d. Inline models in migration tests — `test_gnrsqlmigration.py`

Model built incrementally on `db.model.src` (the raw source Bag API): `self.src.package('alfa', sqlschema='alfa')` (`test_gnrsqlmigration.py:106`), then e.g. composite pkey (`:206-214`):

```python
tbl = pkg.table('recipe_row', pkey='composite_key')
tbl.column('recipe_code', size=':12')
tbl.column('recipe_line',dtype='L')
tbl.compositeColumn('composite_key',columns='recipe_code,recipe_line')
```

and composite FK (`:309-311`):

```python
tbl.compositeColumn('restaurant_ref',columns='restaurant_country,restaurant_vat'
                    ).relation('alfa.restaurant.international_vat', mode='foreignkey')
```

Also direct attribute mutation as a model-change idiom: `foo_varchar.attributes['dtype'] = 'O'; foo_varchar.attributes.pop('size')` (`:370-371`).

### 2e. XML source form — `data/simplestruct.xml:6-23`

The model is a plain Bag: nodes tagged `tag="table"` / `tag="column"`, relation as attribute `relation="video.movie.id"` — evidence that the legacy grammar is *structure-in-a-Bag*, exactly the shape a genro-builders dialect must emit.

---

## 3. Grammar behaviors pinned by tests (MODEL layer)

**Source layer (pre-startup):**
- `test_package` / `test_table_pkey` / `test_column` (`a_structure_load_test.py:43-56`) — package attributes, `pkey` as table attribute, column attributes retrievable via `packageSrc(...).table(...).column(...)`.
- `test_column_upd` (`a_structure_load_test.py:58-60`) — **calling `column('genre', name_full='Genre')` again UPDATES attributes** (idempotent-merge semantics), readable via Bag path `['columns.genre?name_full']`.
- `test_table_upd` (`a_structure_load_test.py:70-72`) — same for tables.
- `test_relation` (`a_structure_load_test.py:62-64`) — `.relation('people.id')` stores `relation?related_column == "people.id"` under the column node.
- `test_mixinPackage` / `test_mixinTable` (`a_structure_load_test.py:74-80`) — mixins both add grammar (`config_db`) and behavior methods reachable via `db.package('video').sayMyName()` / `db.table('video.people').sayHello()`.
- `test_modelSrc` (`d_table_test.py:59-60`) — `db.model.src['packages.video.tables.people?pkey'] == 'id'`: the source is addressable as a Bag path.

**Object layer (post-startup):**
- `test_SqlPackageObj` (`b_structure_build_test.py:43-51`) — `pkg.tableSqlName(tbl) == 'video_movie'` (sqlprefix), `pkg.sqlschema == 'main'` on sqlite; insertion order of tables preserved.
- `test_SqlTableObj` (`b_structure_build_test.py:53-69`) — `fullname='video.movie'`, `sqlname='video_movie'`, ordered `columns.keys()`.
- `test_SqlTableObj_rel_one` / `rel_many` (`b_structure_build_test.py:78-84`) — FK column appears in `relations_one['person_id'] == 'video.people.id'`; reverse side keyed `relations_many['video_dvd_movie_id'] == 'id'`.
- `test_SqlTableObj_rel_column` (`b_structure_build_test.py:86-89`) — `tbl.column('@movie_id.title')` resolves through the relation to a `DbColumnObj` of the far table.
- `test_SqlColumnObj` (`b_structure_build_test.py:92-107`) — `col.dtype == 'L'`; **column with no dtype defaults to `'A'`**; `relatedTable()` / `relatedColumn()` navigation.
- `test_pkey_code` (`test_model_structure.py:53-55`) — non-id pkey (`state.pkey == 'code'`).
- `test_sqlschema` (`test_model_structure.py:69-71`) — `sqlschema='invc'` from package `config_attributes`.
- `test_rowcaption_with_caption_field` (`test_model_structure.py:73-75`) — `caption_field='account_name'` → `tbl.rowcaption == '$account_name'`.
- `test_draftField` / `test_logicalDeletionField` / `test_lastTS` (`test_model_structure.py:81-91`) — sysFields wiring: `__is_draft`, `__del_ts`, `__mod_ts`.
- `test_columns_has_system_fields` (`test_model_structure.py:140-143`) — `sysFields` injects `__ins_ts, __del_ts, __mod_ts, __ins_user, __is_draft` as real columns.
- `test_column_resolve_alias` (`test_model_structure.py:161-166`) — `tbl.column('state_name')` returns an `AliasColumnWrapper` with `relation_path == '@state.name'`.
- `test_column_with_dollar_prefix` (`test_model_structure.py:172-175`) — `column('$account_name')` accepted.
- `test_column_nonexistent_returns_none` (`test_model_structure.py:168-170`) — missing column → `None` (not raise) at table level; `pkg.table('MISSING')` raises `GnrSqlMissingTable` (`test_model_structure.py:686-689`).
- Virtual columns classified per kind (`test_model_structure.py:200-260`): `select`→`n_invoices`, `sql_formula`→`full_address`, `exists`→`has_invoices`, alias→`state_name`, py→`customer_score`, join→`discount_tier_id`, bagItem→`detail_weight`; plus `static_virtual_columns` contains `invoice_date_static` (`:245-249`), `composite_columns` is a Bag (`:251-254`), `dynamic_columns` contains `__allowed_for_partition` (`:256-260`, auto-generated from `partition_state`).
- `TestVirtualColumnObj` (`test_model_structure.py:600-644`) — each VC exposes exactly one of `relation_path` / `sql_formula` / `select` / `exists` / `py_method` / `join_column`; the `select` dict round-trips verbatim (`:615-621`); `vc.readonly is True` always (`:638-640`); `py_method == 'pyColumn_customer_score'` (`:630-632`).
- **Relations tree** (`TestTableRelations`, `test_model_structure.py:280-427`): physical columns AND `@fk` AND reverse `@relation_name` all live in one `relations` Bag; **virtual columns without FK are excluded** (`:308-312`), **formulaColumn with `.relation()` IS included** (`@last_invoice_id`, `:314-316`); joiner dict pinned exactly: `getRelation('@customer_id') == {'many': 'invc.invoice.customer_id', 'one': 'invc.customer.id'}` (`:349-352`); `getRelationBlock` mode/mpkg/mtbl/mfld/opkg/otbl/ofld (`:354-363`); `getJoiner` with `foreignkey: True/False` distinguishing real FK vs virtual joinColumn (`:365-372` and `:967-974`); `manyRelationsList(cascadeOnly=True)` filters by `onDelete='cascade'` (`:384-394`); `oneRelationsList(foreignkeyOnly=True)` excludes virtual relations (`:401-406`).
- **Reverse-relation naming**: `relations_many` key is `invc_invoice_customer_id` (`:337-341`); `@invoices` / `@invoice_rows_by_customer` reverse labels come from `relation_name` (`:296-298`, `:787-790`).
- **Subtables** (`test_model_structure.py:436-456`): declared names retrievable; `sub.attributes['condition'] == "$customer_type_code = 'RES'"`; `getCondition(sqlparams=...)`.
- **aliasTable** exists at table level (`test_model_structure.py:458-460`) and expands in query (`test_compiler_coverage.py:2645-2654`, `@customer.account_name` → `@invoice_id.@customer_id`).
- **Indexes** (`test_model_structure.py:874-889`): FK columns auto-generate index entries (`'customer_state_key' in tbl.indexes`); index objects have `sqlname` containing `idx`.
- `isReserved` is True on FK columns (`test_model_structure.py:535-537`).
- Serialization: `tbl.toJson()` (`:469-481`), `col.toJson()['related_to'] == 'invc.customer.id'` (`:590-593`).
- `bagItemFormula` helper generates xpath: `kwargs['var_calculated_path'] == '/GenRoBag/specs/weight/text()'` (`:483-493`), positional `#0` → `*[1]`, `?attr` → `@myattr` (`:917-925`).
- Deep alias resolution across four hops resolves to a column object (`test_deep_alias_resolves`, `:994-997`).
- Encrypted attribute is a column-model concern: `encrypted='X'|'R'|'Q'` (`customer.py:20-22`) drives write-encrypt/read-decrypt (`test_encrypted_columns.py:234-246` — mode X reads back `None`).
- Custom dtypes: `dtype='money'` / `dtype='perc'` resolved via package `custom_type_money/perc` (`main.py:27-31`), pinned by `test_dtype_money` (`test_model_structure.py:510-512`, money → `'N'`).

Note: no test in this suite pins case-insensitive relation resolution or composite-column deferral explicitly (searched for `insensitive`, `defer` — only `deferToCommit` and DDL `DEFERRABLE` appear). Composite validation is pinned only indirectly through migration DDL and runtime JOIN tests.

---

## 4. Query/compiler behaviors pinned by tests

- **`$col` and `:param`** — `e_query_test.py:80-99`: `where='$year=:y', sqlparams={'y': 2005}`; `IN :tuple` (`:119-131`).
- **`@rel.col` join with auto-alias naming** — `h_query_surface_test.py:169-176`: selecting `@person_id.name` yields result key `_person_id_name`; `*@movie_id` star-through-relation yields `_movie_id_title` (`:274-279`).
- **relationDict** aliasing (`e_query_test.py:230-236`): `columns='$title', relationDict={'title': '@movie_id.title'}`.
- **`#IN_RANGE` macro** — NULL-safe range expansion, exhaustive param matrix (`e_query_test.py:141-228`; also `test_compiler_coverage.py:2787-2808`).
- **`#THIS`** — every `select=dict(...)` formula uses `where='$customer_id=#THIS.id'` and results are cross-validated against direct queries (`test_compiler_coverage.py:262-311`).
- **Formula chaining** — formula referencing formula (`line_gross = $line_total + $line_vat`, `TestFormulaChain`, `test_compiler_coverage.py:1018-1063`); `avg_invoice_value` referencing two select-formulas (`:1462+`).
- **compositeColumn SQL** — value is JSON array string `key.startswith('[')` (`test_composite_column.py:26-35`); composite JOIN navigation, deep nav, WHERE/ORDER BY through composite, exact count `3381` (`test_composite_column.py:107-113`).
- **pyColumn** — emits NULL in SQL, filled by `pyColumn_*` (`test_compiler_coverage.py:1191-1233`).
- **joinColumn** — navigation `@discount_tier_id.discount_rate` works with `cnd` condition (`test_compiler_coverage.py:1284-1299`).
- **Subtable filters in query** — `subtable='residential'`, negation `'!first_movie'`, union `'a|b'`, intersection `'a&b'`, wildcard `'*'`, auto virtual column `$subtable_residential` (`e_query_test.py:250-261`; `test_compiler_coverage.py:2135-2292`).
- **Partition** — `partition_state` + `currentEnv['current_invc_state']`/`['allowed_invc_state']` filters counts; `ignorePartition=True` bypass (`test_compiler_coverage.py:2299-2398`).
- **aliasTable expansion** — `@customer.account_name` on invoice_row (`test_compiler_coverage.py:2645-2664`).
- **Errors** — unknown `$field` or `@relation` → `GnrSqlMissingField` (`test_compiler_coverage.py:2634-2643`, `2708-2718`).
- **`sql_formula=True` delegate** — compiler calls `sql_formula_<fieldname>()` on the table object (`test_compiler_coverage.py:2721-2750`, used by sysFields `__protecting_reasons`).
- **Exploding relations** — two columns on same many-side relation reuse the JOIN and aggregate (`test_compiler_coverage.py:2753-2784`); `setJoinCondition(one_one=True)` suppresses DISTINCT (`:3105-3113`); `('*','*')` global WHERE injection (`:3115-3137`).
- **`#PREF(path, default)`** compile-time preference macro (`test_compiler_coverage.py:2667-2698`).
- **Macro registry** — `db.addMacro` duplicate raises / replace flag; PG adapter adds TSQUERY/VECQUERY; package `registerMacros` broadcast (`test_macro_registration.py`, whole file); VECQUERY param storage and expansion (`test_vecquery_macro.py`).
- **Draft/boolean rewrite** — `$__is_draft IS NOT TRUE` must keep NULL rows on sqlite (`test_sqlite_boolean_rewrite.py`, bug #549).
- Surfaces: `fetchAsDict/fetchGrouped/fetchAsBag/fetchPkeys/fetchAsJson`, `q.compiled.get_sqltext(db)` contains WHERE/ORDER BY/GROUP BY/HAVING/LIMIT (`h_query_surface_test.py:360-384`).

---

## 5. Migration behaviors pinned by tests — `test_gnrsqlmigration.py`

Mechanism: build model src incrementally, then `checkChanges(expected_sql)` asserts the **exact DDL text** produced by `SqlMigrator.getChanges()`, applies it, and asserts a second diff is empty (`test_gnrsqlmigration.py:63-97`). PG/PG3 only.

Scenarios covered (main class `BaseGnrSqlMigration`, `:43-855`):
- **Create**: database with encoding (`:99-102`), schema (`:104-108`), table without pkey (`:110-116`), table with serial pkey (`:190-197`), table with composite pkey from `compositeColumn` → `PRIMARY KEY (recipe_code,recipe_line)` + members forced NOT NULL (`:206-215`), pkey column implies NOT NULL + separate unique constraints preserved (`:217-254`).
- **Add column**: plain/text (`:118-124`), numeric with `size='14,2'` → `numeric(14,2)` (`:126-132`), `indexed=True` → `CREATE INDEX ... USING btree` (`:134-142`), `unique=True` → `ADD CONSTRAINT ... UNIQUE` (`:156-162`), `indexed=dict(method='gin')` and TSV auto-GIN (`:164-187`, issue #626).
- **Constraints/relations**: FK to single pkey → `FOREIGN KEY ... ON UPDATE CASCADE` (`:271-283`); FK from compositeColumn to composite pkey → multi-column index + multi-column FK (`:285-293`); FK to a NON-pkey column → auto index on referencing side (`:295-301`); composite FK to non-pk unique composite (`:303-312`); `onDelete_sql='setnull'` → `ON DELETE SET NULL ... DEFERRABLE INITIALLY DEFERRED` (`:315-328`); create-table-with-relations in one shot (`:331-353`); pkey change on existing table → `DROP CONSTRAINT IF EXISTS ..._pkey; ADD PRIMARY KEY` (`:199-204`).
- **Change**: column type resize (`:355-361`), text→bytea via DROP+ADD (`:364-372`), add/remove `unique` (`:385-398`); a long series of **data-preserving type conversions** with real data checks: text→varchar/timestamp/date/integer/boolean/numeric, real→integer, any→text (`test_12a`–`test_12q`, `:434-855`).
- **Remove**: `test_09a_remove_column` (`:408`) — with `removeDisabled=False`.
- **Failure/force/backup modes**: incompatible conversion raises unless column empty (`:894-993`); force mode nulls invalid values (`:994-1139`); backup mode copies old values to a backup column (`:1140-1347`).
- **Extensions**: create PG extension once, not recreated (`:1348-1424`).
- **Naming**: hashed deterministic names `idx_<hash>` / `cst_<hash>` / `fk_<hash>` (visible in every expected string, e.g. `:152`); multi-unique constraint keeps own name (`:1520`); `new_relation_item`/`new_index_item` don't mutate caller dicts (`:1481-1519`).

---

## 6. Oracle shortlist (model layer first)

1. **`configurePackage` — `common.py:114-159`** — the smallest complete model (5 tables, FKs, subtables, validators, indexed) — first grammar target for the new dialect.
2. **`a_structure_load_test.py:58-60` (`test_column_upd`)** — re-declaration merges attributes; pins the idempotent update semantics of `table()`/`column()`.
3. **`a_structure_load_test.py:74-80` + `:87-100`** — package/table mixins via `config_db`: the extension mechanism the new grammar must reproduce (maps naturally to builders' mixin/struct_method machinery).
4. **`b_structure_build_test.py:78-89`** — `relations_one`/`relations_many` wiring + `column('@movie_id.title')` cross-table resolution: minimal relations oracle without an app.
5. **`test_model_structure.py:349-372` (`test_getRelation`/`getRelationBlock`/`getJoiner`)** — exact joiner dict shape; the contract every query compiler downstream consumes.
6. **`test_model_structure.py:308-316`** — which virtuals enter the relations tree (only those with `.relation()`); subtle, easy to get wrong in a rewrite.
7. **`test_model_structure.py:600-644` (`TestVirtualColumnObj`)** — one-of classification of virtual columns (`select`/`sql_formula`/`exists`/`relation_path`/`py_method`/`join_column`) with verbatim dict round-trip.
8. **`test_model_structure.py:140-143` + `:81-91`** — `sysFields` injection (`__ins_ts` etc., draftField, logical deletion): the table-header contract.
9. **`test_model_structure.py:161-166` + `:994-997`** — aliasColumn wrapper and 4-hop deep alias resolution.
10. **`price_year.py:16-17` + `price_year_note.py:15-18` + `test_composite_column.py:26-59`** — compositeColumn declaration (unique target + FK side) and its runtime JSON-array/JOIN semantics.
11. **`invoice.py:53-58` + `test_model_structure.py:967-974`** — joinColumn with `cnd` and `one_one`; `getJoiner` reports `foreignkey: False` for it.
12. **`invoice_row.py:94` + `test_compiler_coverage.py:2645-2654`** — aliasTable declaration and expansion.
13. **`customer.py:33-39`** — formulaColumn with `select=dict(...)` **plus chained `.relation()`**: virtual FK, the hardest composition in the legacy grammar.
14. **`state.py:6-12` + `test_model_structure.py:53-55`** — non-id pkey, `lookup=True`, `sysFields(id=False)` variant.
15. **`main.py:12-31`** — package-level `config_attributes` (sqlschema/sqlprefix), `custom_type_*`, `registerMacros`: the package half of the grammar.
16. **`test_gnrsqlmigration.py:206-215` (`test_05c_create_table_withCompositePkey`)** — composite pkey forces NOT NULL on members; pins how compositeColumn interacts with pkey at DDL level.
17. **`test_gnrsqlmigration.py:295-301` (`test_06c_add_relation_to_nopk_single`)** — FK to non-pkey column auto-creates supporting index: relation semantics beyond declaration.
18. **`test_model_structure.py:436-456` + `test_compiler_coverage.py:2135-2244`** — subtable declaration + query algebra (`|`, `&`, `!`, `*`, `$subtable_*` virtual columns).
19. **`customer.py:6-8` + `test_compiler_coverage.py:2299-2398`** — `partition_state` header attribute → `__allowed_for_partition` dynamic column and env-driven filtering.
20. **`data/simplestruct.xml:6-23` + `test_gnrsqlxml2py.py`** — the Bag/XML serialized form of the model and struct→py codegen: the round-trip target (analogous to the XsdReader/XsdEmitter pair already done in genro-builders).

### Key structural observations for the rewrite

- The legacy model grammar is **already builder-shaped**: `pkg.table(...)` → `tbl.column(...)` → chained `.relation(...)` mutating a source Bag (`db.model.src`, addressable as `'packages.video.tables.people?pkey'`, `d_table_test.py:59-60`). A genro-builders dialect maps 1:1 (table/column/relation as `@element`, virtual columns as elements with `_meta`).
- Two distinct layers are tested separately and must stay separable: **source** (Bag, mergeable, mixin-extendable — `a_*` test) and **resolved object model** (joiners, relation tree, wrappers — `b_*` + `test_model_structure.py`).
- The chained-`.relation()` return-value idiom (column call returns something you can call `.relation()` on) appears in all fixture files — it is the single most load-bearing ergonomic pattern to preserve or consciously redesign.
- `test_compiler_coverage.py` (291 tests, data-dependent counts) is a *runtime* oracle: valuable later, but only the model-layer files above are needed for the grammar's first acceptance suite.

---

## Riferimenti

- Session: `ce254e4b-4c8c-49ae-a635-12536130ad35` (2026-07-06)
- Legacy source: `/Users/gporcari/Sviluppo/Genropy/genropy/worktrees/develop/gnrpy/tests/sql/` and `projects/test_invoice/` @ `83c138bb6`
