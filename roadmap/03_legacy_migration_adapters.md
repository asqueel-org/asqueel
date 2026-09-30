# Legacy Inventory — Migration System & Adapter DDL Surface

**Version**: 0.2.0 · **Last Updated**: 2026-07-08 · **Status**: 🔴 DA REVISIONARE

Part of the asqueel design documentation set (see `00_INDEX.md`).
Scope: the normalized JSON contract, the ORM→JSON projection (the
contract between model grammar and migration), the DB extractor, diff
engine, command builder and the adapter DDL surface. §7 (addendum
2026-07-08) adds runtime coupling, framework integration and the test
map. Source: Genropy
worktree `develop` @ `83c138bb6`.

---

All paths relative to `/Users/gporcari/Sviluppo/Genropy/genropy/worktrees/develop/gnrpy/gnr/sql/`. Verified against source on 2026-07-06 (worktree `develop`).

---

## 1. Normalized JSON structure (`gnrsqlmigration/structures.py`)

The whole system pivots on one normalized JSON dict produced identically by both extractors. Every entity is a dict with at least `entity` (type string), `entity_name` (identifying name), `attributes` (type-specific dict). Container entities also carry denormalized locator keys (`schema_name`, `table_name`, `column_name`) used by `getDiffBag` and the command builder.

### 1.1 Hierarchy constants

`ENTITY_TREE` (structures.py:51-60) — navigable hierarchy, `None` = leaf:

```python
ENTITY_TREE = {
    'schemas': {
        'tables': {
            'columns': None,
            'relations': None,
            'constraints': None,
            'indexes': None,
        }
    }
}
```

`COL_JSON_KEYS` (structures.py:67-70) — the **only** column attributes that survive into the JSON (both extractors filter on this tuple):

```python
COL_JSON_KEYS = (
    "dtype", "notnull", "sqldefault", "size",
    "unique", "extra_sql", "generated_expression"
)
```

`GNR_DTYPE_CONVERTER` (structures.py:77): `{'X': 'T', 'Z': 'T', 'P': 'T'}` — XML / compressed text / pickle are all `text` at DB level, normalized to `T` before comparison.

`DTYPE_INDEX_CONFIG` (structures.py:84-86): `{'TSV': dict(method='gin', required=True)}` — per-dtype index policy: `method` applied via `setdefault` (explicit wins), `required=True` forces an index even without `indexed=True`.

### 1.2 Entity factories

| Entity | Factory (line) | Shape |
|---|---|---|
| **db** (root) | `new_structure_root(dbname)` :98 | `{'root': {'entity': 'db', 'entity_name': dbname, 'schemas': {}, 'extensions': {}, 'event_triggers': {}}}` |
| **schema** | `new_schema_item(schema_name)` :122 | `{'entity': 'schema', 'entity_name': name, 'tables': {}, 'schema_name': name}` — no `attributes` dict at all |
| **table** | `new_table_item(schema, table)` :180 | `{'entity': 'table', 'entity_name': table, 'attributes': {'pkeys': None}, 'columns': {}, 'relations': {}, 'constraints': {}, 'indexes': {}, 'schema_name': ..., 'table_name': ...}`. `pkeys` is a **comma-joined string** of column sqlnames (or None) |
| **column** | `new_column_item(schema, table, col, attributes)` :207 | `{'entity': 'column', 'entity_name': col, 'attributes': clean_attributes(attributes), 'schema_name', 'table_name', 'column_name'}` |
| **constraint** | `new_constraint_item(schema, table, columns, constraint_type, constraint_name=None)` :232 | `entity_name` = `hashed_name(..., obj_type='cst')`; `attributes = {'columns': [list], 'constraint_name': explicit-or-hash, 'constraint_type': 'UNIQUE'|'CHECK'...}` |
| **relation** (FK) | `new_relation_item(schema, table, columns, attributes=None, constraint_name=None)` :266 | `entity_name` = `hashed_name(..., obj_type='fk')`; attributes copied with `dict(attributes or {})`, then `columns` and `constraint_name` injected, then `clean_attributes` |
| **index** | `new_index_item(schema, table, columns, attributes=None, index_name=None)` :302 | `entity_name` = `hashed_name(..., obj_type='idx')`; `attributes['index_name'] = index_name or hash`; then `clean_attributes` |
| **extension** | `new_extension_item(name)` :142 | `{'entity': 'extension', 'entity_name': name, 'attributes': {}}` — attributes always empty on ORM side |
| **event_trigger** | `new_event_trigger_item(name)` :161 | `{'entity': 'event_trigger', 'entity_name': name, 'attributes': {}}` — filled only by DB extractor |

Column `attributes` per `COL_JSON_KEYS`:
- `dtype`: str — normalized Genro dtype (see §5.1)
- `size`: str — `"10"` (char), `"0:20"` (varchar min:max), `"10,2"` (numeric precision,scale)
- `notnull`: `True` or the sentinel string `'_auto_'` for PK columns (both extractors set `'_auto_'` so PK NOT NULL never diffs; diff engine also filters `'_auto_'`, diff_engine.py:143)
- `sqldefault`: SQL DEFAULT expression (str)
- `unique`: bool
- `extra_sql`: str appended verbatim to the column DDL
- `generated_expression`: **dict** with keys `always`, `stored`, `expression` (consumed by `columnSqlDefinition`, _gnrbaseadapter.py:1111-1115 — note the README describes it as a str; the adapter code treats it as a dict)

Relation `attributes` (after `_relation_info_from_joiner` + `new_relation_item`): `columns: [str]`, `related_table: str`, `related_schema: str`, `related_columns: [str]`, `constraint_name: str`, `constraint_type: "FOREIGN KEY"`, `on_delete`/`on_update`: `'RESTRICT'|'CASCADE'|'NO ACTION'|'SET NULL'|'SET DEFAULT'|None`, `deferrable: bool`, `initially_deferred: bool`. Note `"NO ACTION"` is stripped by `clean_attributes` (it is the SQL default).

Index `attributes`: `columns: {col_name: 'DESC'|None}` (a **dict**, not a list — value is per-column sort order), `index_name: str`, `method: str|None` (None when btree — postgres extractor nulls the default, _gnrbasepostgresadapter.py:882), `with_options: dict`, `tablespace: str|None`, `unique: bool|None`, `where: str|None` (partial-index predicate).

### 1.3 Utilities

- `clean_attributes(attributes)` (structures.py:440-457) — drops any key whose value is in `(None, {}, False, [], '', "NO ACTION")`. This is the anti-spurious-diff normalizer applied to columns, relations, indexes.
- `hashed_name(schema, table, columns, obj_type='idx')` (structures.py:460-485) — `identifier = f"{schema}_{table}_{'_'.join(columns)}_{obj_type}"`, name = `f"{obj_type}_{md5(identifier)[:8]}"` → `idx_a3f2c1b0`, `fk_7e4d9a12`, `cst_b5c8e3f1`. This makes constraint/FK/index identity **structural** (schema+table+columns+kind), independent of the actual name in the DB. Actual names live in `attributes.constraint_name` / `attributes.index_name` and are neutralized by `ignore_constraint_name`. (In-code REVIEW marker: 8 hex chars = 32 bits, birthday collisions ~65k objects.)
- `camel_to_snake(camel_str)` (structures.py:354-367) — regex `(?<!^)([A-Z])` → `_\1`, lowercased. Used only on joiner keys (`onDeleteSql` → `on_delete_sql`).
- `json_equal(json1, json2)` (structures.py:370-386) — `json.dumps(sort_keys=True)` string compare.
- `json_to_tree(data, key, entity_tree=None, parent=None)` (structures.py:389-437) — recursive JSON→Bag conversion following `ENTITY_TREE`, for the admin UI (`SqlMigrator.jsonModelWithoutMeta`).
- `nested_defaultdict()` (structures.py:339-351) — recursively self-creating defaultdict, used for `self.commands`.

---

## 2. ORM → JSON projection (`gnrsqlmigration/orm_extractor.py`)

This is the contract between the model grammar and migration. `OrmExtractor(migrator=None, db=None, extensions=None)` (line 99).

### 2.1 Model surface actually read

**Package** (`fill_json_package`, :110-125): `pkgobj.sqlname` → schema name; `pkgobj.tables` dict; `pkgobj.attributes.get('readOnly')` (boolean, checked in `get_json_struct` :531-533 when `excludeReadOnly`).

**Table** (`fill_json_table`, :141-173):
- `tblobj.pkg.sqlname` (schema), `tblobj.sqlname` (table name), `tblobj.fullname`
- `tblobj.pkeys` (list of column names) → `pkeys = ','.join(tblobj.column(col).sqlname for col in tblobj.pkeys)` (:157-160)
- `tblobj.multi_tenant` → table is replicated into every tenant schema (`add_tenant_schemas` :546-559, tenant list from `migrator.tenant_schemas`)
- `tblobj.columns` (simple columns → column item + relations/indexes)
- `tblobj.composite_columns` (composite columns → **only** relations/indexes + multi-column UNIQUE constraint; no column item is emitted — they are not physical columns)
- **NOT read**: `tblobj.virtual_columns` are never touched — virtual/formula columns, aliasColumns and `@relations` never enter the JSON. Any model metadata not listed here (name_long, validations, triggers, `sql_value`, `encrypted`, etc.) is invisible to migration.

**Column** (`fill_json_column`, :175-225): reads `colobj.attributes` (the raw ORM attribute dict), `colobj.sqlname`, `colobj.table`. Steps:
1. Extension auto-detect: for each attr name in `db.adapter.struct_auto_extension_attributes()` (postgres → `['unaccent']`, _gnrbasepostgresadapter.py:670-671), if `colattr.get(attr)` is truthy the attr name is appended to `self.extensions` (:194-196). So a column with `unaccent=True` pulls in `CREATE EXTENSION unaccent`.
2. `convert_colattr(colattr)` (see §2.2).
3. `min:max` size normalization: if size contains `:` and doesn't start with `0`, force `size = f"0:{max}"` (:204-205) — the DB catalog only knows the max, so min must be zeroed to avoid perpetual diffs.
4. PK handling (:216-220): if column ∈ `pkeys.split(',')` → `attributes['notnull'] = '_auto_'`; `attributes.pop('indexed', None)` always; `attributes.pop('unique', None)` only for **single-column** PKs (composite PK columns may keep their own UNIQUE — issue #576 referenced in comment :215).

### 2.2 `convert_colattr` — dtype/size derivation (:466-513)

1. Filter `colattr` to `COL_JSON_KEYS`, dropping `None` values.
2. `dtype = GNR_DTYPE_CONVERTER.get(dtype, dtype)` (X/Z/P → T).
3. Size rules:
   - size starting with `:` → prefixed `0` (`:20` → `0:20`)
   - `':' in size` → `dtype = 'A'` (varchar with range)
   - size without `:` and without `,`:
     - dtype absent or in `('A','T','X','Z','P')` → `dtype = 'C'` (fixed char)
     - dtype `'N'` → `size = f'{size},0'` (scale-0 numeric)
4. `dtype in ('A','C') and not size` → `dtype = 'T'` (char/varchar without length is impossible).
5. Result carries `dtype` always, `size` only if present.

### 2.3 Relations and indexes (`fill_json_relations_and_indexes`, :227-280)

Per column:
- `joiner = colobj.relatedColumnJoiner()` — the ORM many-side joiner dict.
- `indexed = colattr.get('indexed') or colattr.get('unique')` (:245); if falsy but `DTYPE_INDEX_CONFIG[dtype].required` → `indexed = True` (TSV columns always get a GIN index).
- If joiner exists:
  - `indexed = indexed or True` (:257 — in-code REVIEW: always True; every FK column is indexed, discarding any richer dict value from `indexed`)
  - `_relation_info_from_joiner` (:339-391) extracts:
    - all joiner keys ending in `_sql`, converted `camel_to_snake(k[:-4])` with value through `statement_converter` — i.e. `onDeleteSql` → `on_delete`, `onUpdateSql` → `on_update` (:367-369)
    - `joiner['one_relation']` = `"pkg.table.column"` → resolved via `colobj.db.table(related_table)` and `.column(related_column)`
    - `related_columns = (rel_colobj.attributes.get('composed_of') or rel_colobj.name).split(',')` (:376-378) — composite target support
    - `related_table = rel_tblobj.model.sqlname`; `related_schema = rel_tblobj.pkg.sqlname` (or the tenant schema if target is multi-tenant, :382-383)
    - `deferrable = joiner.get('deferrable') or joiner.get('deferred')`; `initially_deferred = joiner.get('initially_deferred') or joiner.get('deferred')` (:385-388) — legacy `deferred` implies both
    - `related_to_pkeys = result['related_columns'] == rel_tblobj.pkeys` (:389)
  - the FK item is emitted **only if `joiner.get('foreignkey')`** is truthy (:263) — a relation without `foreignkey=True` gives index-only behavior, no DB constraint
  - if the related column is *not* the target pkey, a **deferred index** on the related column is queued (`self.deferred_indexes.append(...)` :271-275) and processed at the end of `get_json_struct` (:536-541), because the target table may not be extracted yet
- If `indexed` and the column is not in pkeys → `fill_json_column_index` (:277-279).

`statement_converter` (:304-336) FK-action normalization: `R/RESTRICT→RESTRICT`, `C/CASCADE→CASCADE`, `N/NO ACTION→NO ACTION`, `SN/SETNULL/SET NULL→SET NULL`, `SD/SETDEFAULT/SET DEFAULT→SET DEFAULT`, empty→None, **unknown→None silently** (in-code REVIEW marker).

`fill_json_relation` (:393-421): `columns = (colobj.attributes.get('composed_of') or colobj.name).split(',')`; sets `constraint_name` = hash, `constraint_type = "FOREIGN KEY"`, stores under `table_json["relations"][hash]`.

### 2.4 Index derivation (`fill_json_column_index`, :423-464)

- `indexed` may be `True` (plain) or a **dict** of options.
- `DTYPE_INDEX_CONFIG` method applied via `setdefault('method', ...)` (:439-441).
- **If `colobj.attributes.get('unique')` → return, no index** (:442-444): the UNIQUE constraint already creates one.
- `with_options = dictExtract(indexed, 'with_', pop=True)` — any `with_*` keys of the indexed dict become index WITH options (:445).
- `sorting = indexed.pop('sorting', None)`, split by comma, zipped per column: `columns=dict(zip(columns, sorting))` (:446-456).
- Composite columns: `composed_of` splits into the column list.
- Remaining keys of the `indexed` dict pass through into index attributes (`**indexed` :458) — so `method`, `where`, `tablespace`, `unique` can be declared in the model as `indexed=dict(method='gin', where=..., ...)`.

### 2.5 Composite UNIQUE (`fill_multiple_unique_constraint`, :282-302)

Composite column with `unique` truthy → `new_constraint_item(schema, table, colattr['composed_of'].split(','), 'UNIQUE')` into `table_json['constraints']`.

### 2.6 Orchestration (`get_json_struct`, :515-544)

Order: packages (skipping readOnly if `excludeReadOnly`) → `add_tenant_schemas()` → deferred indexes (always plain `indexed=True`) → extensions (`fill_json_extension` per name in `self.extensions`).

### 2.7 What is ignored (summary)

- Virtual/formula columns, aliasColumns, `sql_value` columns, relation aliases (`@`), python-level metadata (captions, validations), `encrypted` (affects DML only), table/column comments, python triggers/methods.
- Column attributes not in `COL_JSON_KEYS` + `indexed` + `composed_of` + `unique` + adapter auto-extension attrs.
- CHECK constraints (no ORM grammar for them).
- `changed` events for `generated_expression`/`extra_sql` are explicitly non-migratable (command_builder.py:426-428).

---

## 3. DB → JSON (`gnrsqlmigration/db_extractor.py`)

`DbExtractor.get_json_struct(schemas)` → `prepare_json_struct` → `get_info_from_db` (:168-208): opens one connection, calls five adapter methods, closes in `finally`. `GnrNonExistingDbException` → returns `False` → `json_structure = {}` (whole ORM becomes "added"). Result dict keys dispatch dynamically to `process_{key}` (:165-166).

| Key | Adapter source | Processing |
|---|---|---|
| `base_structure` | `struct_get_schema_info(schemas)` | `process_base_structure` (:210-260): each record pops `_pg_schema_name`, `_pg_table_name`, `_pg_is_nullable`, `name`; remaining keys filtered by `COL_JSON_KEYS`; `is_nullable == 'NO'` → `notnull=True`; creates schema/table/column items. Schemas requested but empty in DB are removed from the result (:257-260) |
| `constraints` | `struct_get_constraints(schemas)` — dict `{(schema, table): {ctype: ...}}` | `process_constraints` (:262-323): **PRIMARY KEY** → `table['attributes']['pkeys'] = ','.join(cols)` + each PK column `notnull='_auto_'`; **UNIQUE** single-col → column attribute `unique=True` (skipped entirely if the column equals the pkey); multi-col UNIQUE → constraint item (keeps original DB `constraint_name`, :316-321); **FOREIGN KEY** → `process_table_relations` (:325-346) — pops the DB `constraint_name` and passes the remaining attrs (columns, related_schema/table/columns, on_delete/on_update, deferrable, initially_deferred as bools) to `new_relation_item`; **CHECK** — currently ignored (:323 comment) |
| `indexes` | `struct_get_indexes(schemas)` — dict `{(schema, table): {index_name: attrs}}` | `process_indexes` (:348-377): skips any index with `constraint_type` set (PK/UNIQUE backing indexes); `columns = list(attrs['columns'].keys())`; keeps real DB `index_name` |
| `extensions` | `struct_get_extensions()` | `process_extensions` (:379-394): skips `schema_name == 'pg_catalog'`; extension item with **empty attributes** (full info goes to `json_meta`, so version etc. never diff) |
| `event_triggers` | `struct_get_event_triggers()` | `process_event_triggers` (:396-408): item attributes updated with the full trigger dict (event, owner, description, function_name, enabled_state, event_tags) |

Because both sides pass through the same factories + `clean_attributes` + hashed names, the two JSONs are directly comparable by `dictdiffer`.

---

## 4. Diff engine + command builder

### 4.1 Diff engine (`diff_engine.py`, class `DiffMixin`)

- `diff` property (:72-88): `dictdiffer.diff(self.sqlStructure or {'root': {}}, self.ormStructure)` — DB is *old*, ORM is *new*; missing DB collapses to `{'root': {}}` so everything is `add`.
- `dictDifferChanges()` (:90-168) normalizes dictdiffer triples `(event, path, changes)` into `(event_type, kw)` pairs:
  - If `'attributes'` occurs in the path (`get_attributes_index_in_path` :190-205) → **`changed`** events, one per changed attribute. `kw = {item (ORM entity), changed_attribute, oldvalue (from sqlStructure), newvalue (from ormStructure), entity, entity_name}`. When the diff is an add/remove of keys inside `attributes`, values equal to `'_auto_'` are filtered out (:140-143).
  - Otherwise → **`added`** / **`removed`** for the whole entity; `difflist` is dict-ified, single items wrapped as `{entity_name: item}` (:156-168). `kw = {item, entity, entity_name}`.
- `getDiffBag()` (:207-239): UI Bag `schema.table.column.{entity}_{entity_name}.{reason}` with the kw stored on node attributes.

### 4.2 Dispatch (`migrator.py:186-196`)

```python
handler = getattr(self, f'{evt}_{kw["entity"]}', self.missing_handler_cb)
handler(**kw)
```
Naming convention **`{added|changed|removed}_{db|schema|table|column|relation|constraint|index|extension|event_trigger}`**. `removed` events skipped entirely when `removeDisabled` (default True); items in readOnly schemas skipped (:188-192).

### 4.3 Command storage

`self.commands` is a `nested_defaultdict` with hierarchy (command_builder.py docstring :25-40):

```
commands['db']
├── 'command'                       # CREATE DATABASE
├── 'extensions'[name]['command']   # CREATE EXTENSION
└── 'schemas'[schema]
    ├── 'command'                   # CREATE SCHEMA
    └── 'tables'[table]
        ├── 'command'               # CREATE TABLE (new tables) / pkey rebuild
        ├── 'pre_commands': [...]   # backup columns before conversion
        ├── 'columns'[col]['command']       # ADD/ALTER/DROP COLUMN fragments
        ├── 'indexes'[idx]['command']       # full CREATE INDEX statements
        ├── 'relations'[rel]['command']     # "ADD CONSTRAINT ... FOREIGN KEY" fragments
        └── 'constraints'[cst]['command']   # "ADD/DROP CONSTRAINT" fragments
```

### 4.4 `added_*` handlers

- `added_db` (:132-145): `adapter.createDbSql(name, 'UNICODE')` + recursion into `added_schema` for every schema.
- `added_schema` (:147-158): `adapter.createSchemaSql(name)` + recursion into `added_table`.
- `added_table` (:160-203): builds `CREATE TABLE "schema"."table"(\n col_defs..., PRIMARY KEY (pkeys), CONSTRAINT ...\n);` — column defs via `columnSql` (which also spins off separate UNIQUE constraints), PK inline, constraints inline via `struct_constraint_sql`; skips tables with no columns; then recursion into `added_index` and `added_relation` (created *after* the table).
- `added_column` (:205-216): fragment `ADD COLUMN {columnSql(item)}`.
- `added_index` (:218-227): full statement via `createIndexSql` → `adapter.struct_create_index_sql`.
- `added_relation` (:229-254): fragment `ADD {struct_foreign_key_sql(...)}` with on_delete/on_update/deferrable/initially_deferred.
- `added_constraint` (:256-273): fragment `ADD {struct_constraint_sql(...)};`.
- `added_extension` (:275-285): `struct_create_extension_sql`.
- `added_event_trigger` (:287-289): **no-op**.

### 4.5 `changed_*` handlers

- `changed_table` (:295-319): only `pkeys` handled → `struct_drop_table_pkey_sql` + `struct_add_table_pkey_sql` joined with `\n` as the table `command`.
- `changed_column` (:340-428) — the complex one, per `changed_attribute`:
  - **`size`** (:381-382, `_handle_size_change` :430-467): if no existing command with `USING` → `struct_alter_column_sql(column, columnSqlType(dtype, size))`; if a USING command already exists (dtype change processed first) → regex-patch the type inside it: `re.sub(r'TYPE\s+\S+(\s+USING)', f'TYPE {new_sql_type}\\1', existing)` (:463-467). Skipped if `item['_rebuilt']` (column was DROP+ADD rebuilt).
  - **`dtype`** (`_handle_dtype_change` :469-538), priority cascade with `TEXT_TYPES = ('T','A','C','X','Z','P')` (:485):
    1. any→text always allowed; `O` (bytea)→text uses conversion expression `encode("{col}", 'hex')` (:493-504), else plain `struct_alter_column_sql` (implicit cast).
    2. `(old, new) in adapter.TYPE_CONVERSIONS` → `_apply_type_conversion` (:540-631): value `None`/`True` → plain ALTER TYPE; value str = USING template formatted with `column_name` →
       - without `--force`: raise `GnrSqlException` if column not empty (:584-592, message suggests `--force` / `--backup`)
       - with `--backup` (:594-620): backup column `f'{column_name}__{oldvalue}'`, registered in `self._conversion_backups` (list of dicts schema/table/column/backup_column/old_dtype/new_dtype), `pre_commands`: `ALTER TABLE ... ADD COLUMN "{backup}" text` + `UPDATE ... SET "{backup}" = "{col}"::text`
       - then `struct_alter_column_with_conversion_sql(column, type, USING-expr)`
    3. unsupported: if `struct_is_empty_column` → rebuild: `table_dict['columns'][f'rem_{name}']['command'] = f'DROP COLUMN "{name}"'` + `added_column(item)` + `item['_rebuilt'] = True` (:525-532); else raise `GnrSqlException('Incompatible data type change in a non-empty column. ...')` (:534-538).
  - **`notnull`** (:390-406): `struct_add_not_null_sql` / `struct_drop_not_null_sql`.
  - **`unique`** (:408-424): add → `addColumnUniqueConstraint` (hashed `cst_` name, fragment `ADD CONSTRAINT ... UNIQUE (col)`); remove → `struct_drop_constraint_sql` under the hashed name.
  - **`generated_expression`, `extra_sql`** (:426-428): explicitly ignored — "not automatically migratable".
- `changed_index` (:633-661): `index_name` change with `ignore_constraint_name=True` → keep old name, no SQL; else `ALTER INDEX {old} RENAME TO {new};`. Any other attribute → rebuild: `DROP INDEX IF EXISTS {index_name};\n{createIndexSql(item)}`.
- `changed_relation` (:663-709): `constraint_name` diff → ignored (name reset to old) or `RENAME CONSTRAINT`; any other attribute → `relations_dict[f'rem_{name}']` = `struct_drop_constraint_sql` fragment + `relations_dict[f'add_{name}']` = `ADD {struct_foreign_key_sql(...)}`.
- `changed_constraint` (:711-749): same pattern → `drop_{name}` = `DROP CONSTRAINT {constraint_name};` + `add_{name}` = `ADD {struct_constraint_sql(...)}`.

### 4.6 `removed_*` handlers (:759-794)

Only **`removed_column`** produces SQL (`DROP COLUMN "{name}"`, :763-774), and only when `removeDisabled=False`. `removed_table`, `removed_index`, `removed_relation`, `removed_constraint`, `removed_extension`, `removed_event_trigger` are all **no-op `pass`** — the system never drops tables/indexes/FKs/constraints.

### 4.7 Assembly & ordering (`executor.py`)

`getChanges()` (:74-136) assembles `self.sql_commands` with keys `db_creation`, `build_commands`, `extensions_commands`, returned joined by `\n`. Per table (`sqlCommandsForTable` :138-207) the order is:

1. `pre_commands` (backup columns), each terminated `;`
2. `CREATE TABLE ...` **or** one combined `ALTER TABLE "schema"."table"\n{col_cmd1},\n{col_cmd2};` (all column fragments comma-joined into a single ALTER, :174-193)
3. one `ALTER TABLE ...\n{constraint_sql};` per constraint
4. `CREATE INDEX` statements (standalone)
5. FKs collected separately (`relation_commands`, one `ALTER TABLE ...\n ADD CONSTRAINT ...;` each) and appended **after all tables** (:132-133) so cross-table references to tables created in the same migration don't fail.

`applyChanges()` (:209-236) executes in three phases: `db_creation` with `manager=True` (system connection); `build_commands` with `autoCommit=True` (each statement committed, **not atomic**); `extensions_commands` with `autoCommit=True`.

`verifyConversionBackups()` (:238-318): per backup, `SELECT COUNT(*) ... WHERE "{backup}" IS NOT NULL AND "{col}" IS NULL`; loss>0 → keep backup + report entry `{lost_values, backup_column, conversion, message}` keyed `schema.table.column`; loss=0 → `DROP COLUMN "{backup}"`; verification error → backup kept.

### 4.8 Migrator flags (`migrator.py:140-163`)

`extensions` (comma string), `ignore_constraint_name=True`, `excludeReadOnly=True`, `removeDisabled=True`, `force=False`, `backup=False` (**`self.force = force or backup`** — backup implies force, :158). Schemas inspected = `db.getApplicationSchemas()` minus `db.readOnlySchemas()` (if excludeReadOnly) plus `db.getTenantSchemas()` (:198-222).

---

## 5. Adapter DDL surface

### 5.1 The Genro dtype system

Genro dtypes that actually exist across `typesDict`/`revTypesDict`/migration code:

| dtype | Meaning | Base rev-mapping (_gnrbaseadapter.py:100-109) | Postgres rev-mapping (:146-169) | SQLite rev-mapping (gnrsqlite.py:50-54) |
|---|---|---|---|---|
| `A` | varchar | `character varying` | `character varying` | `character varying` |
| `C` | fixed char | `character` | `character` | `character` |
| `T` | text | `text` | `text` | `text` |
| `X` | XML text | `text` | `text` | `blob` |
| `Z` | compressed text | `text` | `text` | `text` |
| `P` | pickled text | `text` | `text` | `text` |
| `N` | numeric | `numeric` | `numeric` | `numeric` |
| `M` | money | `money` | `money` | — |
| `B` | boolean | `boolean` | `boolean` | `boolean` |
| `D` | date | `date` | `date` | `date` |
| `H` | time | `time without time zone` | `time without time zone` | `time` |
| `HZ` | time w/ tz | `time without time zone` (sic, base :104) | `time with time zone` | — |
| `DH` | timestamp | `timestamp without time zone` | `timestamp without time zone` | `timestamp` |
| `DHZ` | timestamp w/ tz | `timestamp with time zone` | `timestamp with time zone` | `timestamp with time zone` |
| `DT` | interval | `interval` (typesDict :95) | — (absent from pg revTypesDict) | — |
| `I` | integer | `integer` | `integer` | `integer` |
| `L` | bigint | `bigint` | `bigint` | `bigint` |
| `R` | real/double | `real` | `real` | `real` |
| `O` | bytea/binary | `bytea` | `bytea` | — |
| `serial` | auto-increment | `serial8` | `serial8` | `serial8` |
| `TSV` | tsvector | — | `tsvector` (pg only) | — |
| `VEC` | pgvector vector | — | `vector` (pg only) | — |
| `jsonb` | jsonb | — | `jsonb` (pg only, dtype key is the literal string `jsonb`) | — |

Reverse (SQL→dtype) notes: postgres `typesDict` maps `smallint→I`, `double precision→R`, `character→C` (base maps `character→A`, _gnrbaseadapter.py:89); unknown pg types default to `'T'` (`struct_get_schema_info` :738); a `bigint` with a `nextval(...)` default is re-classified as dtype `'serial'` (:762-763). SQLite `typesDict` additionally accepts `nvarchar`, `varchar`, `char`, `int`, `datetime`, `decimal`, `bool`, unsigned variants, `serial8→L`, `blob→X` (gnrsqlite.py:43-48).

**`columnSqlType(dtype, size)`** (_gnrbaseadapter.py:1118-1132): if `dtype != 'N'` and size: `':' in size` → use max part, dtype `A`; else dtype `C`. With size → `f'{revTypesDict[dtype]}({size})'`, else bare type. So `A 0:20` → `character varying(20)`, `C 10` → `character(10)`, `N 10,2` → `numeric(10,2)`.

**`columnSqlDefinition(sqlname, dtype, size, notnull, pkey, unique, default, extra_sql, generated_expression)`** (_gnrbaseadapter.py:1097-1116): `'"{name}" {type}'` + `NOT NULL` + `PRIMARY KEY` + `UNIQUE` + `DEFAULT {valueToSql(default)}`; `generated_expression` dict → `GENERATED{ ALWAYS} AS ({expression}){ STORED} {extra_sql}`; trailing `extra_sql` appended verbatim.

### 5.2 `TYPE_CONVERSIONS`

Base (_gnrbaseadapter.py:116-152) — all value `None` (plain ALTER TYPE): text↔text family (`A/T/C` → `T/A/C/X/Z/P` combinations), `I→L`, `I→N`, `B→I`, `N→I/L/R`, `L→I/N/R`, `D→DH/DHZ`, `DH→D/DHZ`, `DHZ→D/DH`.

Postgres (_gnrbasepostgresadapter.py:175-217) inherits base and adds USING-templated conversions (`{column_name}` placeholder, non-matching values → NULL):
- `T/A → DH`, `T/A → DHZ`: regex-guard `'^[0-9]{4}-[0-9]{2}-[0-9]{2}'` then `::timestamp` / `::timestamp with time zone`
- `T/A/C → D` (`C` variant TRIMs), `T/A → H` (`'^[0-9]{2}:[0-9]{2}'` → `::time`)
- `T/A/C → N` (`'^-?[0-9]+(\.[0-9]+)?$'` → `::numeric`), `T/A/C → I`, `T/A/C → L` (integer regex)
- `T/A/C → B`: `LOWER(...) IN ('true','t','yes','y','1') → TRUE; ('false','f','no','n','0','') → FALSE; ELSE NULL`
- `R → I` / `R → L`: `ROUND(...)::integer/bigint`

SQLite defines no `TYPE_CONVERSIONS` of its own (inherits base) but has `allowAlterColumn = False` (gnrsqlite.py:61) and no MIGRATIONS capability, so the migration path is never exercised.

### 5.3 `struct_*` surface (base declarations, _gnrbaseadapter.py:475-634)

Abstract (raise `AdapterMethodNotImplemented`) unless noted:

| Method | Purpose |
|---|---|
| `struct_auto_extension_attributes()` | column attr names that imply extensions — base returns `[]` (:484-488), postgres `['unaccent']` |
| `struct_get_schema_info(schemas)` / `_sql` | columns catalog (generator of col dicts) |
| `struct_get_constraints(schemas)` / `struct_get_constraints_sql` | PK/UNIQUE/FK/CHECK dict |
| `struct_get_indexes(schemas)` / `_sql` | index dict |
| `struct_get_extensions()` / `_sql` | installed extensions |
| `struct_get_event_triggers()` / `_sql` | DDL event triggers |
| `struct_is_empty_column(schema, table, column)` | concrete in base (:551-567), delegates to `struct_is_empty_column_sql`, reads `result[0]['is_empty']` |
| `struct_table_fullname_sql(schema, table)` | qualified quoted name |
| `struct_drop_table_pkey_sql` / `struct_add_table_pkey_sql` | PK rebuild |
| `struct_create_index_sql(schema_name, table_name, columns, index_name, unique, **kw)` | full CREATE INDEX |
| `struct_alter_column_sql(column_name, new_sql_type, **kw)` | ALTER TYPE fragment |
| `struct_alter_column_with_conversion_sql(column_name, new_sql_type, conversion_expression, **kw)` | base raises "Type conversion not supported for this database adapter. Use an upgrade script..." (:608-617) |
| `struct_add_not_null_sql` / `struct_drop_not_null_sql` | NOT NULL toggling fragments |
| `struct_drop_constraint_sql(constraint_name, **kw)` | DROP CONSTRAINT fragment |
| `struct_foreign_key_sql(fk_name, columns, related_table, related_schema, related_columns, on_delete, on_update, **kw)` | FK constraint fragment |
| `struct_constraint_sql(constraint_name, constraint_type, columns, check_clause, **kw)` | UNIQUE/CHECK constraint fragment |
| `struct_create_extension_sql(extension_name)` | CREATE EXTENSION |

Postgres implementations (all in `_gnrbasepostgresadapter.py`), exact SQL fragments:

- `adaptSqlName` → `'"%s"' % name` (:236-238); `struct_table_fullname_sql` → `f'"{schema_name}"."{table_name}"'` (:673-674)
- `struct_alter_column_sql` → `ALTER COLUMN "{col}" TYPE {type}` (:966-970)
- `struct_alter_column_with_conversion_sql` → `ALTER COLUMN "{col}" TYPE {type} USING {expr}` (:972-978)
- `struct_add_not_null_sql` → `ALTER COLUMN "{col}" SET NOT NULL` (:980-984); drop variant `DROP NOT NULL` (:986-990)
- `struct_drop_constraint_sql` → `DROP CONSTRAINT IF EXISTS "{name}"` (:993-997)
- `struct_foreign_key_sql` (:999-1029) → `CONSTRAINT "{fk}" FOREIGN KEY ({cols}) REFERENCES "{schema}"."{table}" ({rcols})` + optional ` ON DELETE X`, ` ON UPDATE X`, ` DEFERRABLE`, ` INITIALLY DEFERRED` (INITIALLY DEFERRED only when also deferrable, :1023)
- `struct_constraint_sql` (:1031-1056) → `CONSTRAINT "{name}" UNIQUE ({cols})` or `CONSTRAINT "{name}" CHECK ({check_clause})`; raises ValueError for other types
- `struct_create_index_sql` (:902-947) → `CREATE[ UNIQUE ]INDEX {name} ON "{schema}"."{table}" USING {method} ("col" [DESC], ...) [WITH (k = v, ...)] [TABLESPACE x] [WHERE pred];` — default method `btree` (DEFAULT_INDEX_METHOD, :11)
- `struct_drop_table_pkey_sql` → `ALTER TABLE {full} DROP CONSTRAINT IF EXISTS {table}_pkey;` (:676-678) — **assumes the pg default pkey naming convention**; add → `ALTER TABLE {full} ADD PRIMARY KEY ({pkeys});` (:680-682)
- `struct_create_extension_sql` → `CREATE EXTENSION IF NOT EXISTS {name};` (:1117-1121)
- `createDbSql` → `CREATE DATABASE "%s" ENCODING '%s';` (:412-414); `createSchemaSql` (base) → `CREATE SCHEMA %s;` (_gnrbaseadapter.py:1015-1017)
- Introspection SQL: `struct_get_schema_info_sql` joins `information_schema.schemata/tables/columns`, handles USER-DEFINED types via `udt_name` (:684-708); PK/UNIQUE from `information_schema.table_constraints` + `key_column_usage` (:1164-1208); FK from `pg_constraint` with `LATERAL UNNEST(conkey/confkey) WITH ORDINALITY` to preserve multi-column order, action decode from `confupdtype/confdeltype` codes (:1210-1271); CHECK from `information_schema.check_constraints` (:1274-1291, fetched but discarded downstream); indexes from `pg_index/pg_class/pg_am/pg_attribute/pg_namespace/pg_tablespace/pg_constraint` including `indoption` DESC bit, `pg_get_expr(indpred)` for WHERE, `reloptions` for WITH (:835-864); extensions from `pg_extension` (:1074-1093); event triggers from `pg_event_trigger` (:1124-1141).

Legacy (pre-migration-system) DDL helpers still in base: `addForeignKeySql` (:971-987, drop+add with `ON DELETE/ON UPDATE`), `addUniqueConstraint` → `un_{pkg}_{tbl}_{fld}` naming (:989-997), `addColumn` (:1035-1043), `renameColumn` (:1045-1063, also drops old index/fkey by naming convention), `dropColumn` (:1065-1070), `createIndex` (:1169-1189), `dropIndex` (:1159-1167), `alterColumnSql` (:1134-1138 — note the base version contains a typo'd `ALTER TABLE %s ALTER TABLE %s TYPE %s`; the postgres override in gnrpostgres.py:294-297 is correct and adds `USING col::type`), `dropTable`, `dropEmptyTables`, `createTableAs`.

### 5.4 Capabilities

`AdapterCapabilities` enum (gnr/sql/__init__.py:14-18): `MIGRATIONS`, `VECTOR`, `SCHEMAS`, `ADMINISTER`. `ADMINISTER` is added at adapter init if all `REQUIRED_EXECUTABLES` are on PATH (_gnrbaseadapter.py:159-166). Postgres: `{MIGRATIONS, VECTOR, SCHEMAS}` + `REQUIRED_EXECUTABLES = ['psql','pg_dump','pg_restore']` (_gnrbasepostgresadapter.py:112-118). SQLite: `{SCHEMAS}` only (gnrsqlite.py:56-58) — **no MIGRATIONS**: the migration system is effectively postgres-only.

### 5.5 Postgres-only features

- Extensions (auto-detected `unaccent`; explicit via migrator `extensions=` param), event triggers (extract-only, no DDL generation), partial indexes (`where`), index methods (`gin`/`gist`/etc. via `USING`, TSV forced to GIN), `WITH` storage options, tablespaces, per-column DESC ordering, DEFERRABLE/INITIALLY DEFERRED FKs, generated columns (`GENERATED ALWAYS AS ... STORED`), `serial` detection, `jsonb`, `tsvector` (+ TSQUERY/TSRANK/TSHEADLINE macros), `vector` (pgvector, VECQUERY/VECRANK macros), LISTEN/NOTIFY, pg_dump/pg_restore/remote import.

### 5.6 SQLite limitations (gnrsqlite.py)

- `allowAlterColumn = False` (:61); no `struct_*` overrides at all → any migration call raises `AdapterMethodNotImplemented`.
- `addForeignKeySql` returns `''` — "Sqlite cannot add foreign keys, only define them in CREATE TABLE. However they are not enforced." (:360-362).
- `createSchemaSql` returns `''`; schemas are emulated via `ATTACH DATABASE '<schema>.db' AS <schema>` at connect time (:70-93, :98-109, :364-371).
- `createIndex` puts the schema prefix on the **index name**, not the table (:373-388).
- `lockTable` no-op (:390-392), `notify`/`listen` no real messaging (:299-317), `_selectForUpdate` returns `''` (:140-141), no extensions (`_list_enabled_extensions` → `[]`, :195-196), `getTableConstraints` returns empty Bag (TODO, :351-357). ILIKE→LIKE, `~*`→REGEXP, IS TRUE/FALSE rewriting in `prepareSqlText` (:111-128).

---

## 6. Planned/missing entities (from `gnrsqlmigration/README.md`)

Extension recipe (README:127-136): new factory in `structures.py` + extractor logic + `added_/changed_/removed_` handlers + `ENTITY_TREE` entry; diff engine and executor are generic.

Planned entity schemas (README:138-247):

- **Functions/procedures** (schema-level, `schema_item.functions`): attributes `language` (plpgsql/sql/...), `return_type`, `arguments` (full signature), `body` (hash for comparison), `volatility` (VOLATILE/STABLE/IMMUTABLE), `security` (DEFINER/INVOKER|None), `is_procedure: bool`. ORM counterpart needed: `@sql_function` decorator or `functions` section in the model.
- **Views / materialized views** (schema-level, `schema_item.views`): `definition` (SELECT, hash for comparison), `materialized: bool`, `columns: [str]`, `with_data: bool|None`. ORM counterpart: `views` section with SQL string or callable.
- **Table triggers** (table-level, `table_item.triggers`): `timing` (BEFORE/AFTER/INSTEAD OF), `events: [INSERT, UPDATE, DELETE, TRUNCATE]`, `for_each` (ROW|STATEMENT), `function_name`, `function_schema`, `condition` (WHEN clause|None), `arguments`. ORM counterpart: trigger declaration on the table referencing a function entity.
- **Custom types** (schema-level, `schema_item.types`): `type_kind` (ENUM/COMPOSITE/DOMAIN/RANGE), `enum_values: [str]|None`, `columns: dict|None` (composite), `base_type: str|None` (domain), `constraint: str|None` (domain CHECK). ENUM flagged as the main use case.
- **Sequences** (schema-level, `schema_item.sequences`): `start_value`, `increment`, `min_value`, `max_value`, `cycle: bool`, `owned_by` (`schema.table.column`|None). Only standalone sequences — serial/IDENTITY sequences are implicit.
- **CHECK constraints** (README:263-273): `constraint_item` and `struct_constraint_sql` already support `check_clause`; missing pieces are (1) processing in `db_extractor.process_constraints` (currently silently dropped), (2) `check_clause` in constraint attributes, (3) CHECK handling in `added_constraint`/`changed_constraint`, (4) ORM grammar to declare them.
- **Comments** (README:274-299): column comments as an 8th `COL_JSON_KEYS` entry `"comment"` (extracted from `pg_description`, emitted as `COMMENT ON COLUMN ... IS '...'`; ORM counterpart = column `doc` attribute); table comments as `table_item["attributes"]["comment"]`.
- Explicitly out of scope (README:249-258): GRANT/REVOKE, tablespaces, publications/subscriptions, FDWs, collations.

**Caveat on the legacy README bug list** (README:340-424), verified against current source: bugs #1/#2 (factory mutation — `new_relation_item`/`new_index_item` now do `dict(attributes or {})`, structures.py:285/:324), #3 (db_extractor stale `v` — db_extractor.py:320 uses `multiple_unique_const['constraint_name']`), #4 (`changed_constraint` — command_builder.py:742 uses `constraint_attr['constraint_name']`) and #5 (`jsonModelWithoutMeta` — migrator.py:260 uses `is None` checks) are **already fixed in the current code**. The remaining in-code `# REVIEW` markers (32-bit hash, `indexed = indexed or True`, silent `statement_converter` fallthrough, `_conversion_backups` hasattr init, `infodict is False`, `dict(difflist)` fragility) are still present at the quoted lines.

---

## 7. Addendum (2026-07-08) — coupling, framework integration, test map

Findings from a verification pass over the whole package; sections 1–6
were re-checked against the source and confirmed accurate.

### 7.1 Runtime coupling (external imports per file)

| File | External imports | Nature |
|---|---|---|
| `__init__.py` | `gnr.sql.gnrsql_exceptions.GnrSqlException` | exception |
| `structures.py` | `gnr.core.gnrbag.Bag` (only in `json_to_tree`, :409-437) | gnr.core, optional |
| `orm_extractor.py` | `gnr.core.gnrdict.dictExtract`, `gnr.core.gnrstring.boolean` | gnr.core |
| `db_extractor.py` | `gnr.dev.decorator.time_measure`, exceptions | decorator + exceptions |
| `diff_engine.py` | `dictdiffer` (PyPI), `gnr.core.gnrbag.Bag`, `gnr.sql._typing` | dictdiffer + typing |
| `command_builder.py` | `re`, `GnrSqlException`, `gnr.sql._typing` | exception + typing |
| `executor.py` | `gnr.sql._typing` | typing |
| `migrator.py` | `Bag`, exceptions, the 5 internal modules | gnr.core |

`gnr/sql/_typing.SqlMigratorBaseMixin` is **type-checking only**: at
runtime `TYPE_CHECKING` is `False` and the mixin base is `object`
(`_typing.py:30`). No runtime coupling between the mixins and
`SqlMigrator`.

**Verdict on "diff engine and command builder are reused as-is"** (§1
of the design doc): true for `diff_engine.py` (reads only
`self.sqlStructure`/`self.ormStructure` dicts + `dictdiffer`; the Bag
is only for the admin-UI `getDiffBag`). **Not entirely true for
`command_builder.py`**: it never touches the model, but it is tightly
coupled to the adapter via `self.db.adapter` — ~15 `struct_*_sql` /
`columnSql*` / `createDbSql` / `adaptSqlName` calls plus
`TYPE_CONVERSIONS` (command_builder.py:141, :188, :241, :264, :334,
:443-449, :489-514, :557, :691, :739, :816, :843, :868, :895) — and to
the host flags (`self.force`, `self.backup`,
`self.ignore_constraint_name`, `self.removeDisabled`). It is reusable
only if the new world reproduces that DDL surface (in the rewrite: the
renderer/dialect, per the plan) and the flags. The exact SQL strings
are produced by the adapter, not by the command builder. The only file
truly coupled to the old model is `orm_extractor.py` (§2) — by design,
and that is precisely the file the rewrite replaces with a projection
of the new source tree.

### 7.2 Framework integration — two coexisting engines

`SqlMigrator` is invoked from exactly two places:

1. **CLI `gnr migrate`** (`gnr/db/cli/gnrmigrate.py:218`) — flags
   `--force`, `--backup`, `--check`, `--inspect`, `--extensions`,
   `--upgrade`; aborts if the adapter lacks the `MIGRATIONS`
   capability (:199).
2. **`GnrSqlDb` schema API** (`gnr/sql/gnrsql/schema.py`):
   `diffOrmToSql()` (:110-117) and `syncOrmToSql()` (:119-124).

It **coexists** with the OLD schema-alignment engine:
`SqlModelChecker` + `ModelExtractor` (`gnr/sql/gnrsqlutils.py:123` and
`:14`), wired behind `db.checkDb()` → `model.check()`
(`schema.py:99-108` → `gnrsqlmodel/model.py:440-455`) and still called
from `web/_gnrbasewebpage.py:787,796`. The OLD engine compares the
model directly against the legacy adapter introspection
(`listElements`/`relations`/`getTableConstraints`, doc `06` §3) and
emits DDL through the legacy pre-migration helpers (§5.3). Porting
decision (plan, Fase 3): only `SqlMigrator` is ported; `checkDb`
consumers move to the new engine.

### 7.3 Execution semantics

`applyChanges` runs each statement with `autoCommit=True`
(`executor.py:232`, documented at :44-45): migrations are **not
atomic** — a mid-run failure leaves the DB partially migrated.
Idempotence is by design (diff recomputed each run) and pinned by
`checkChanges` re-running the migrator (test, :92-97). Whether the new
world wraps migrations in a transaction is a new design decision, not
a porting one.

### 7.4 Test map (the migration oracles)

`tests/sql/test_gnrsqlmigration.py` (1658 lines, 79 test methods):

| Base class | Tests | Collected as | Coverage |
|---|---|---|---|
| `BaseGnrSqlMigration` | 50 | `TestGnrSqlMigration_postgres`, `_postgres3` | create db/schema/table, columns, PK/composite PK, UNIQUE, FK (single/multi, non-PK + auto index, onDelete/deferred), all dtype conversions (12a–12q) |
| `..._DefaultException` | 4 | `_postgres_exception` | incompatible conversion on non-empty column raises; empty column converts |
| `..._ForceMode` | 4 | `_postgres_force` | `force=True`: unconvertible values → NULL (real data verified) |
| `..._BackupMode` | 8 | `_postgres_backup` | backup column `__{dtype}` + data preserved |
| `..._Extension` | 3 | `_postgres_extension`, `_postgres3_extension` | `CREATE EXTENSION IF NOT EXISTS`, no drop, no recreate |
| `ToDo` | 4 | **not collected** (no `Test` prefix) | FK/UNIQUE add-drop, change pkey — unimplemented features |
| `GeneralSqlMigrationCode` | 6 | **not collected** | MagicMock regression tests for the 5 fixed README bugs |

122 cases actually execute against a live ephemeral Postgres
(`testing.postgresql`, `tests/sql/common.py:6,50`); models are built
inline via `cls.db.model.src`. `checkChanges(expected)` (:63-97)
normalizes whitespace, compares the **exact generated SQL** against a
pinned string, applies it for real, and re-runs the migrator asserting
zero residual changes. Pinned oracles include the hashed constraint
names (`cst_703bf76b`, `fk_*`, `idx_*` — structural 8-hex hashes:
changing `hashed_name` invalidates every oracle) and all the dtype
`USING` conversion expressions (:405-:850). The 10 uncollected tests
(`ToDo`, `GeneralSqlMigrationCode`) are written but inactive — the
regression six should be activated in the port (rename to `Test*`).
`tests/sql/test_connection_error.py` adds 6 mock-based tests pinning
the `GnrNonExistingDbException` vs `GnrSqlConnectionException`
taxonomy and the `SystemExit` abort path (`migrator.py:181-185`).

## Riferimenti

- Session: `ce254e4b-4c8c-49ae-a635-12536130ad35` (2026-07-06); addendum verification 2026-07-08
- Legacy source: `/Users/gporcari/Sviluppo/Genropy/genropy/worktrees/develop/gnrpy/gnr/sql/{gnrsqlmigration,adapters}/` @ `83c138bb6`
- Adapter full inventory: doc `06`
