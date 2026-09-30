# Legacy Inventory — Query Compiler & Data Layer (gnr.sql.gnrsqldata)

**Version**: 0.2.0 · **Last Updated**: 2026-07-08 · **Status**: 🔴 DA REVISIONARE

Part of the asqueel design documentation set (see `00_INDEX.md`).
Scope: exhaustive inventory of the legacy query language, compiler,
query/selection/record surface — the future consumer of the new model
tree. §7 (addendum 2026-07-08) adds sizes, consumers, the dialect
boundary at runtime, the test map and the porting-complexity estimate.
Source: Genropy worktree `develop` @ `83c138bb6`. Companion doc:
`07_legacy_compiler_experiments.md` (the 2026 improvement attempts).

---

Sources (all paths under `/Users/gporcari/Sviluppo/Genropy/genropy/worktrees/develop/gnrpy/gnr/sql/`):

- `gnrsqldata/compiler.py` (1512 lines) — `SqlCompiledQuery`, `SqlQueryCompiler`
- `gnrsqldata/query.py` (624 lines) — `SqlQuery`, `SqlDataResolver`
- `gnrsqldata/selection.py` (1588 lines) — `SqlSelection` (surface)
- `gnrsqldata/record.py` (865 lines) — `SqlRecord`, resolvers (surface)
- Supporting contracts verified in: `adapters/_gnrbaseadapter.py`, `adapters/_gnrbasepostgresadapter.py`, `gnrsql/db.py`, `gnrsql/query.py`, `gnrsqlmodel/table.py`, `gnrsqlmodel/columns.py`, `gnrsqlmodel/model.py`

All regexes, signatures and attribute names below are quoted verbatim from source.

---

## 1. Query language surface

### 1.1 Reference syntax

| Token | Meaning | Recognized by |
|---|---|---|
| `$column` | column of the current table (physical or virtual) | `COLFINDER` |
| `@rel.column`, `@rel.@rel2.column` | related column through one or more relation hops | `RELFINDER` (char class `[\w.@:]` allows chained `@` and `:`) |
| `:param` | named bind parameter (adapter `paramstyle = 'named'`, `_gnrbaseadapter.py:156`); list/tuple/set values are expanded to `(:k0,:k1,…)` by `adaptTupleListSet` (`_gnrbaseadapter.py:208-219`) |
| `expr AS alias` | explicit output alias; `' as '` is normalized to `' AS '` (`compiler.py:919`) |
| `*` | all columns of main table (`starColumns`, includes static virtual columns) |
| `*prefix_` | main-table columns starting with `prefix_` |
| `*@rel1.@rel2` / `*@rel1.@rel2.prefix_` | all/prefixed columns of the related table |
| `*@rel.(col1,col2,…)` | explicit related-column list; also populates `cpl.aggregateDict` (`compiler.py:784-796`) |
| `*<virtualcolname>` | if the filter names a virtual column, its `sql_formula` is used as the expansion source (`compiler.py:770-773`) |
| `#MACRO(...)` | macros, below |

Glob expansion is `expandMultipleColumns(self, flt, bagFields)` (`compiler.py:744-800`); Bag-typed columns (`dtype='X'`) are excluded from `*` unless `bagFields=True` (`table.py:479-491`).

### 1.2 Module-level regex constants (compiler.py:62-74, verbatim)

```python
COLFINDER = re.compile(r"(\W|^)\$(\w+)")
RELFINDER = re.compile(r"([^A-Za-z0-9_]|^)(\@(\w[\w.@:]+))")
COLRELFINDER = re.compile(r"([@$]\w+(?:\.\w+)*)")

IN_RANGEFINDER = re.compile(r"#IN_RANGE\s*\(\s*((?:\$|@|\:)?[\w\.\@]+)\s*,\s*((?:\$|@|\:)?[\w\.\@]+)\s*,\s*((?:\$|@|\:)?[\w\.\@]+)\s*\)\s*",re.MULTILINE)
PERIODFINDER = re.compile(r"#PERIOD\s*\(\s*((?:\$|@)?[\w\.\@]+)\s*,\s*:?(\w+)\)")

BAGEXPFINDER = re.compile(r"#BAG\s*\(\s*((?:\$|@)?[\w\.\@]+)\s*\)(\s*AS\s*(\w*))?")
BAGCOLSEXPFINDER = re.compile(r"#BAGCOLS\s*\(\s*((?:\$|@)?[\w\.\@]+)\s*\)(\s*AS\s*(\w*))?")

ENVFINDER = re.compile(r"#ENV\(([^,)]+)(,[^),]+)?\)")
PREFFINDER = re.compile(r"#PREF\(([^,)]+)(,[^),]+)?\)")
THISFINDER = re.compile(r'#THIS\.([\w\.@]+)')
```

- **COLFINDER** — bare `$name`; group(2) = column name. Used by `updateFieldDict` to seed identity entries in `relationDict`.
- **RELFINDER** — `@name…` tokens; group(2) = full token including `@`. `updateFieldDict` flattens each to a `$`-alias via `db.colToAs`.
- **COLRELFINDER** — either `$col` or `@rel.col` dotted token; used only to prefix the traversed parent path onto column refs inside nested join conditions (`compiler.py:639`).
- **IN_RANGEFINDER / PERIODFINDER / BAGEXPFINDER / BAGCOLSEXPFINDER / ENVFINDER / PREFFINDER / THISFINDER** — macro syntaxes, semantics in 1.3.

### 1.3 Macros

**`#IN_RANGE(value, low, high)`** — `expandInRange` (`compiler.py:1309-1339`). Expands into a four-branch OR handling NULL bounds; **inclusive** on both ends (`value <= high`, `value >= low`, `low <= value <= high`, both-NULL → true). Applied to: `where` (`:960`), explicit join `cnd` (`:612`), `sql_formula` (`:423`). Registered as a db-level macro at startup with `callback=None` (`gnrsql/db.py:220-222`) but actual expansion in the compiler is by direct `IN_RANGEFINDER.sub`.

**`#PERIOD(field, :param)`** — `expandPeriod` (`compiler.py:1341-1397`). Decodes `self.sqlparams[param]` via `decodeDatePeriod(..., workdate=self.db.workdate, returnDate=True, locale=self.db.locale)`; emits `field = :param_from` (single day), `field BETWEEN :param_from AND :param_to`, `field >= :param_from`, `field <= :param_to`, or literal `' true'`. **Side effect**: writes `<param>_from`/`<param>_to` into `sqlparams`. Applied only to `where` (`:961`).

**`#BAG($field) [AS alias]`** — `expandBag` (`compiler.py:1274-1289`). Emits the column expression unchanged and appends `((asfld or fld).replace('$',''), False)` to `cpl.evaluateBagColumns`; post-fetch, `SqlQuery.handleBagColumns` (`query.py:281-301`) parses the raw value into a `Bag`.

**`#BAGCOLS($field) [AS alias]`** — `expandBagcols` (`compiler.py:1291-1307`). Same, with `True` as second tuple element: post-fetch the Bag leaves are flattened into `'{field}_{leafpath}'` row keys and the source field is set to `None` (`query.py:296-299`). Both applied only to the columns spec (`:997-998`).

**`#ENV(name[, fallback_or_table])`** — closure `expandEnv` inside `getFieldAlias` (`compiler.py:322-350`). Resolution order: (1) `name` in `db.currentEnv` → quoted text literal `'%s'`; (2) `par2` in `currentEnv` → quoted literal; (3) `env_<name>` method on `db.table(par2)` if given, else on the current table object; (4) literal string `'Not found <name>'`. **Only expanded inside virtual-column `sql_formula`** (`:424`), not in plain WHERE.

**`#PREF(path[, default])`** — closure `expandPref` (`compiler.py:316-320`): `str(curr_tblobj.pkg.getPreference(prefpath, dflt))`, injected as unquoted literal. Only inside `sql_formula` (`:425`).

**`#THIS.field`** — closure `expandThis` (`compiler.py:311-314`): `self.getFieldAlias(fld, curr=curr, basealias=alias)` — i.e. the reference is resolved **relative to the table that owns the formula**, at the alias reached by the current traversal. Expanded inside `sql_formula` (`:426`) and inside sub-select `where` (`:417`).

**Adapter macros** (Postgres family, `_gnrbasepostgresadapter.py:13-108`): class-level `macros` dict with compiled regexes for
`#TSQUERY[_code](tsv, :querystring[, language])`, `#TSRANK[_code][([weights][, normalization])]`, `#TSHEADLINE[_code](textfield[, 'config'])`, `#VECQUERY[_code](veccol, :target)`, `#VECRANK[_code]`.
`_expand_TSQUERY` emits `"{tsv} @@ websearch_to_tsquery(CAST({language} AS regconfig),{querystring})"` and stashes channel params in `sqlparams['tsquery_<code>']`; `_expand_VECRANK` emits `(1 - ({veccol} <=> CAST({target} AS vector)))`. The compiler invokes them by site: `where` gets `'TSQUERY,VECQUERY'` (`compiler.py:962`), columns get `'TSRANK,TSHEADLINE,VECRANK'` (`:1094`, and inside `sql_formula` `:421`), `order_by` gets `'TSRANK,VECRANK'` (`:1098`). Dispatcher: `MacroExpander.replace(sql_text, macro)` (`_gnrbaseadapter.py:61-73`) — instance-registered macros take precedence over class macros; the base adapter has `macros = {}`.

**`var_` pseudo-macro** in formula columns (`compiler.py:427-434`): attributes prefixed `var_` on a formula column are extracted, stored in `db.currentEnv` under `f'{id(fldalias)}_{self._currColKey}_{k}'`, and `:k` references in the formula are rewritten to `:env_<newkey>`.

**Storename sentinel**: if `storename == '*'` or contains a comma, `"'_STORENAME_' AS _dbstore_"` is appended to columns (`compiler.py:921-923`); the execution layer substitutes it per store.

---

## 2. Relation path resolution → JOINs

### 2.1 Alias allocation

- `aliasCode(self, n)` → `'%s%i' % (self.aliasPrefix, n)` (`compiler.py:241-250`); `aliasPrefix` defaults to `'t'` → `t0, t1, …`.
- `init(self, lazy=None, eager=None)` (`:253-271`) resets per-compilation state: `self.aliases = {self.tblobj.sqlfullname: self.aliasCode(0)}`, `self.fieldlist = []`, `self._explodingRows = False`, `self._explodingTables = []`.
- Relation tree: `self.relations = tblobj.relations` if `tblobj.db.reuse_relation_tree` else `tblobj.newRelationResolver(cacheTime=-1)` (`:228-231`).

### 2.2 `getFieldAlias(self, fieldpath, curr=None, basealias=None, parent=None)` (`compiler.py:273-454`)

Splits the dotted path, pops the final field, and if relation segments remain calls `_findRelationAlias` (building JOINs as a side effect). A physical column returns:

```python
return '%s.%s' % (self.db.adapter.asTranslator(alias), curr_tblobj.column(fld).adapted_sqlname)   # :454
```

(base `asTranslator` wraps in double quotes: `'"%s"' % as_`, `_gnrbaseadapter.py:221-223`). Non-physical fields fall into the virtual-column branches (§3). Raises `GnrSqlMissingField` when nothing matches (`:370`).

### 2.3 `_findRelationAlias(self, pathlist, curr, basealias, newpath, parent=None)` (`:456-501`)

Consumes one segment `p = pathlist.pop(0)`:
- `currNode = curr.getNode(p)` — a real relation → `_getRelationAlias` builds/reuses the JOIN; `curr = curr[p]`.
- **aliasTable handling**: if no node, `tblalias = self.db.table(curr.tbl_name, pkg=curr.pkg_name).model.table_aliases[p]`; if `None` → `GnrSqlMissingField(f"Relation {p} not found")`; otherwise its `relation_path` is split and **prepended** to the remaining pathlist (`:488-491`) — table aliases are pure path rewrites, they allocate no alias of their own.
- Recurses with `parent=f"{parent}.{p}" if parent else p`.

### 2.4 `_getRelationAlias(self, relNode, path, basealias, parent=None)` (`:507-668`)

- Joiner: `joiner = relNode.attr['joiner']`; `ref = joiner['many_relation'].split('.', 1)[-1]`; memoization key `pw = tuple(newpath+[basealias])` against `self.aliases` — a re-traversed hop returns the existing alias (and re-flags the current column as exploding if the table was exploding, `:544-549`). New joins get `alias = self.aliasCode(len(self.aliases))`.
- **Direction**: `joiner['mode'] == 'O'` (foreign-key lookup toward the one side) → target = `one_relation`, from = `many_relation`. Otherwise (many side) target/from swap and `manyrelation = not joiner.get('one_one', False)` (`:557-569`).
- Target table name honours multi-tenant: `target_sqlfullname = target_tbl._get_sqlfullname(ignore_tenant=joiner.get('ignore_tenant'))` (`:573-574`).
- **ON-condition flavours**, in priority order (`:576-655`):
  1. `'join_on' in joiner` → copied into `joiner['cnd']`.
  2. `joiner.get('cnd')` — explicit expression; `#IN_RANGE` expanded inside it.
  3. `joiner.get('between')` — legacy `"value;low;high"` triple → four-branch OR with **half-open upper bound `<`** (`:614-626`, marked TODO-deprecate in favour of `#IN_RANGE`, which is `<=`).
  4. `joiner.get('case_insensitive', False) == 'Y'` → `f'lower({adaptedAlias}.{target_sqlcolumn}) = lower({adaptedBaseAlias}.{from_sqlcolumn})'` (`:629`).
  5. `joinerList` (standard single-column FK, or composite via `composed_of` on both columns zipped pairwise — mismatch raises `GnrSqlException('Relation with multikey works only with compositeColumns')`, `:590-597`) → `' AND '.join([f'({adaptedBaseAlias}.{from_column})={adaptedAlias}.{target_sqlcolumn}' ...])` (`:632`).
  6. `joiner.get('virtual')` → `f'(${from_column})={adaptedAlias}.{target_sqlcolumn}'` (`:635`) — the `$` ref is later resolved like any field.
- Nested-path qualification: when `parent` is set, `COLRELFINDER.sub(lambda g: f'{parent}.'+g.group(0).replace('$',''), cnd)` prefixes the parent path onto refs in the ON clause (`:639`). Then `cnd = self.updateFieldDict(cnd, reldict=joindict)`; any refs found are immediately resolved with `getFieldAlias` and merged into `cpl.relationDict` (`:643-646`).
- **Customized join conditions**: if `self.joinConditions`, `getJoinCondition(target_fld, from_fld, alias, relation=relNode.label)` returns `(extracnd, one_one)`; `extracnd` goes through `embedFieldPars` + `updateFieldDict` and is ANDed: `cnd = '(%s AND %s)' % (cnd, extracnd)`; **`one_one=True` demotes a many join to non-exploding** (`:649-657`).
- **JOIN emission — always LEFT**: `self.cpl.joins.append(f'LEFT JOIN {target_sqlfullname} AS {self.db.adapter.adaptSqlName(alias)} ON ({cnd})')` (`:660`). There is **no INNER-join path anywhere**; multiplicity is countered by DISTINCT injection (§4/§6), not by join type.
- **Exploding tracking** (`:663-667`): many-side joins append `self._currColKey` to `cpl.explodingColumns`, record `pw` in `_explodingTables`, set `self._explodingRows = True`.

### 2.5 `getJoinCondition` / `setJoinCondition`

- Lookup key: `relation or '%s_%s' % (target_fld.replace('.', '_'), from_fld.replace('.', '_'))` (`compiler.py:700`). Entry shape: `{'condition': str with $tbl placeholder, 'params': dict merged into sqlparams, 'one_one': bool}`; `$tbl` is replaced with the target alias (`:702`).
- Registered from `SqlQuery.setJoinCondition(self, target_fld=None, from_fld=None, relation=None, condition=None, one_one=False, **kwargs)` (`query.py:191-205`) and `SqlRecord.setJoinCondition(self, target_fld, from_fld, condition, one_one=False, **kwargs)` (`record.py:250-261`).
- A **main-table wildcard** condition keyed `'*_*'` is looked up as `getJoinCondition('*', '*', self.aliasCode(0))` and ANDed onto the final WHERE (`compiler.py:1042-1048`).

### 2.6 Relation mode classification (record path)

`_getRelationMode(self, joiner)` (`compiler.py:1187-1211`): `'DynItemOne'` for mode `'O'`; else `'DynItemOneOne'` when `joiner.get('one_one')` or when a joinCondition declares `one_one`; else `'DynItemMany'`. Stored as `_relmode` in `cpl.resultmap` (`:1162`) and consumed by `SqlRecord._loadRecord_DynItem{One,OneOne,Many}` (`record.py:557,605,650`).

### 2.7 `updateFieldDict` and `embedFieldPars`

- `updateFieldDict(self, teststring, reldict=None)` (`compiler.py:709-742`): `$col` → identity entry `{col: col}` in `reldict` (default `cpl.relationDict`); each `@rel...` token → flattened alias via `self.db.colToAs(colname)` (`gnrsql/query.py:361-376`: `re.sub(r'\W', '_', col)` + leading `_` if starting with digit), registered as `{asname: '@rel...'}`, and the token in the string is replaced by `$asname` (first occurrence only, `.replace(colname, '$%s' % asname, 1)`). Result: a string containing only `$name` placeholders resolvable by `gnrstring.templateReplace`.
- `embedFieldPars(self, sql)` (`:802-829`): bind params whose *value* is a string starting with `@` (existing relation) or `$` (existing column/virtual column) are inlined into the SQL replacing `:paramname` — turning a parameter into a field reference. Applied to WHERE (`:992`) and to joinCondition extras (`:653`).

---

## 3. Virtual columns in the compiler

### 3.1 Dispatch inside `getFieldAlias` (`compiler.py:366-451`)

When `fld not in curr.keys()` (not physical in the relation-resolver node):

```python
fldalias = curr_tblobj.model.getVirtualColumn(fld, sqlparams=self.sqlparams)   # :367
```

`getVirtualColumn` (`gnrsqlmodel/table.py:329-356`) also supports **parametric virtual columns**: if `sqlparams[fld]` is a dict with a `'field'` key, an existing virtual column is deep-copied and its attributes overridden per query.

Branch order:
1. `fldalias is None` → `GnrSqlMissingField` (`:369-371`).
2. `fldalias.relation_path and not fldalias.composed_of` → **alias column**: recurse `self.getFieldAlias(fldalias.relation_path, curr=curr, basealias=alias, parent='.'.join(pathlist))` (`:373-377`).
3. `fldalias.sql_formula or fldalias.select or fldalias.exists` → **formula/sub-select** (§3.2).
4. `fldalias.py_method` → emit `'NULL'` in SQL and register `self.cpl.pyColumns.append((fld, getattr(fldalias.table.dbtable, fldalias.py_method, None)))` (`:440-445`).
5. else → `GnrSqlInvalidVirtualColumn` (`:446-451`).

### 3.2 `sql_formula` expansion pipeline (`:390-439`)

1. `sql_formula is True` → delegate to table method: `getattr(curr_tblobj, 'sql_formula_%s' % fld)(attr)` (`:396-397`).
2. `select_dict = dictExtract(attr, 'select_')` — the **`select_*` kwargs convention**: each attribute `select_<name>` is a sub-select spec; `#<name>` in the formula is the substitution point.
3. If no formula: `sql_formula = '#default' if fldalias.select else 'EXISTS(#default)'` with `select_dict['default'] = fldalias.select or fldalias.exists` (`:400-402`) — this is how `select=`/`exists=` columns work.
4. For each sub-select spec (`:404-419`):
   - a **string** spec calls `getattr(self.tblobj.dbtable, 'subquery_%s' % sq_pars)()` (the `subquery_*` table-method convention);
   - `cast` popped → wrapper `' CAST( ( %s ) AS <cast>) '`, else `' ( %s ) '`;
   - `table` and `where` popped; defaults injected: `ignorePartition=True`, `excludeDraft=False`, `excludeLogicalDeleted=False`, `subtable='*'`;
   - sub-select alias namespace: `aliasPrefix = '%s_t' % alias`;
   - `#THIS` expanded in the sub-select where;
   - compiled via `self.db.queryCompile(table=sq_table, where=sq_where, aliasPrefix=aliasPrefix, addPkeyColumn=False, ignoreTableOrderBy=True, **sq_pars)` (`:418`) — i.e. **a full recursive compilation** (`gnrsql/query.py:265-334`);
   - spliced with `re.sub('#%s\\b' % susbselect, tpl % sql_text, sql_formula)`.
5. Then, in order: adapter macros `'TSRANK,TSHEADLINE,VECRANK'`; `updateFieldDict(sql_formula, reldict=subreldict)`; `IN_RANGEFINDER`; `ENVFINDER`; `PREFFINDER`; `THISFINDER`; `var_` param rewiring (`:421-434`).
6. `subreldict` entries resolved via `getFieldAlias(value, curr=curr, basealias=alias)` — field refs inside a formula are resolved **relative to the formula's own table/alias** — then `gnrstring.templateReplace(sql_formula, subColPars, safeMode=True)`; returned as `f'( {sql_formula} )'` (`:435-439`).

### 3.3 Subquery columns (`nestedselect`, JSON/XML aggregation)

Defined in the model, consumed via the mechanism above. `DbTableObj.subQueryColumn(name, query=None, mode=None, **kwargs)` (`gnrsqlmodel/model.py:1179-1222`):
- `mode='json'` → `sql_formula = "SELECT json_agg(row_to_json(<t>_json)) FROM #nestedselect <t>_json"` with `select_nestedselect=query, subquery=True, format='json_table'`;
- `mode='xml'` → `xmlagg(xmlelement(... xmlforest(...)))` over `#nestedselect`, `subquery=True`;
- otherwise → `select=query, subquery=True, subquery_aggr=mode`.
The `#nestedselect` placeholder is just a `select_*` name resolved by step 4 above.

### 3.4 py_method columns at fetch time

`SqlQuery.handlePyColumns(self, data)` (`query.py:257-279`): builds `pcdict = dict(self.compiled.pyColumns)`, iterates `self.dbtable.model.virtual_columns.keys()`, and for every registered handler runs `d[field] = handler(d, field=field)` per row. Runs before decryption and Bag parsing in `fetch()` (`query.py:252-254`) and `_dofetch()` (`:441-443`).

### 3.5 `_handle_virtual_columns(self, virtual_columns)` (`compiler.py:1214-1272`) — record path only

- Adds `self.tblobj.static_virtual_columns.keys()` to the requested list; strips leading `$`; `uniquify`.
- Per name: `column = tbl_virtual_columns[col_name]` (`None` → silently `continue`); `column_attributes = self.tblobj.virtualColumnAttributes(col_name)` (merges the related column's attributes under a `relation_path` alias, `table.py:599-613`); `field = self.getFieldAlias(column.name)`; tag must be `'virtual_column'` else `ValueError`; `as_name = '%s_%s' % (self.aliasCode(0), column.name)`; appends `'%s AS %s' % (field, as_name)` to `self.fieldlist` and stores metadata in `cpl.resultmap`.
- In the *selection* path, static virtual columns instead flow in through `*` expansion (`starColumns`, `table.py:490`).

### 3.6 The model↔compiler read contract

Attributes/properties of `DbVirtualColumnObj` read by the compiler (`gnrsqlmodel/columns.py:255-330`): `relation_path`, `composed_of`, `join_column`, `sql_formula`, `select`, `exists`, `py_method`, `attributes` (raw dict, incl. `select_*`, `var_*`, `cast`, `static`, `subquery`, `format`), `table` (→ `.dbtable` for `py_method` lookup), `name`. Base column contract (`DbBaseColumnObj`): `dtype` (default `'T'`; `'X'` = Bag), `encrypted` (`'R'/'Q'/'X'`), `print_width`, `attributes['name_long']`, `attributes['format']`.

On the table model (`DbTableObj`): `sqlfullname`, `pkey`, `columns`, `virtual_columns`, `static_virtual_columns`, `getVirtualColumn`, `virtualColumnAttributes`, `starColumns(bagFields)`, `table_aliases`, `sqlnamemapper` (column name → adapted SQL name, filled in `DbColumnObj.doInit`, `columns.py:223`), `column(name).adapted_sqlname`, `attributes.get('order_by')`, `attributes.get('default_subtable')`, `logicalDeletionField`, `draftField`, `fullname`, `relations` / `newRelationResolver`. On the `SqlTable` proxy (`tblobj.dbtable`): `getPartitionCondition(ignorePartition=…)`, `subtable(name).getCondition(sqlparams=…)`, `subquery_<name>()`, `sql_formula_<fld>(attr)`, `env_<name>()`, `fieldAggregate(...)`.

Joiner dict keys read: `mode` (`'O'`/many), `one_relation`, `many_relation`, `one_one`, `virtual`, `cnd`, `join_on`, `between`, `case_insensitive`, `ignore_tenant`, `range` (record path only, `compiler.py:1158-1161`).

---

## 4. SqlCompiledQuery

`SqlCompiledQuery(maintable, relationDict=None, maintable_as=None)` (`compiler.py:118-148`). Every field:

| Field | Type / init | Populated by |
|---|---|---|
| `maintable` | str — `tblobj.sqlfullname` | ctor |
| `relationDict` | dict — as-name → field path; seeded with `{'pkey': tblobj.pkey}` (`:912-913`, `:1133-1134`) | `updateFieldDict`, join cnds |
| `aliasDict` | dict — output AS-name → original SQL body when explicit `AS` was written (`:1018`) | column loop |
| `resultmap` | `Bag()` — per-field metadata incl. `as`, `_relmode`, sqlname, dtype… (record path) | `compiledRecordQuery`, `_handle_virtual_columns` |
| `distinct` | `''` or `'DISTINCT '` | §4.1 |
| `columns` | str — final comma/newline-joined SELECT list | `compiledQuery` / record `fieldlist` |
| `joins` | `list[str]` — `LEFT JOIN … AS tN ON (…)` clauses | `_getRelationAlias` |
| `additional_joins` | `list[str]` — appended after joins (`:1053`); never filled in this module | — |
| `where`, `group_by`, `having`, `order_by` | str/None — compiled clauses | `compiledQuery` |
| `limit`, `offset` | passthrough | `compiledQuery` |
| `for_update` | bool/str | `compiledQuery` / record |
| `explodingColumns` | `list[str]` — column keys traversing many-side joins | `_getRelationAlias` |
| `evaluateBagColumns` | `list[tuple(fieldname, separateCols_bool)]` | `#BAG` / `#BAGCOLS` |
| `encryptedColumns` | dict — column → encryption mode (`:1084-1090`, `:1168-1170`) | select-list scan |
| `aggregateDict` | dict — `flattened_fldpath → [subfield_name, f, '<path>_<rowkey>']` from `*@rel.(c1,c2)` (`:795`) | `expandMultipleColumns` |
| `pyColumns` | `list[tuple(fld, bound_method_or_None)]` | py_method branch |
| `maintable_as` | str — `'t0'` (selection) / `None` (record; adapter defaults to `'t0'`) | ctor |

**`get_sqltext(self, db)`** (`:150-169`): copies the 11 keys `('maintable', 'distinct', 'columns', 'joins', 'where', 'group_by', 'having', 'order_by', 'limit', 'offset', 'for_update')` and delegates to `db.adapter.compileSql(maintable_as=self.maintable_as, **kwargs)`. Base implementation (`_gnrbaseadapter.py:695-719`):

```python
def compileSql(self, maintable, columns, distinct='', joins=None, where=None,
               group_by=None, having=None, order_by=None, limit=None, offset=None,
               for_update=None, maintable_as=None):
```

emits `SELECT  {distinct}{columns}\n FROM {maintable} AS {maintable_as}`, one line per join, then WHERE/GROUP BY/HAVING/ORDER BY/LIMIT/OFFSET only if truthy, plus `FOR UPDATE OF {maintable_as} {mode}`. Overridden per dialect in `gnrpostgres.py:169`, `gnrpostgres3.py:121`, `gnrmssql.py:445`, `gnrdb2_400.py:413`.

### 4.1 `compiledQuery(...)` — full signature and pipeline (`compiler.py:831-1104`)

```python
def compiledQuery(self, columns='', where='', order_by='',
                  distinct='', limit='', offset='',
                  group_by='', having='', for_update=False,
                  relationDict=None, bagFields=False,
                  storename=None, subtable=None,
                  count=False, excludeLogicalDeleted=True, excludeDraft=True,
                  ignorePartition=False, ignoreTableOrderBy=False,
                  addPkeyColumn=True):
```

Order of operations (exact):
1. Create `cpl`; `aggregate = bool(distinct or group_by)`; `group_by == '*'` is a sentinel meaning "aggregating, no GROUP BY list" and is nulled (`:906-907`); default `order_by` from `tblobj.attributes.get('order_by')` unless `ignoreTableOrderBy` or aggregate (`:909-910`); `init()`; seed `relationDict['pkey']`.
2. Normalize columns string: `'  '→' '`, `'\n'→''`, `' as '→' AS '`, `' ,'→','` (`:917-920`); storename sentinel; expand `*` globs.
3. `count` mode: drop order_by; `columns = group_by` if grouped; leave as-is if distinct; else `columns = 'count(*) AS "gnr_row_count"'` (`:939-946`). Otherwise `addPkeyColumn and tblobj.pkey and not aggregate` → append `f'${self.tblobj.pkey} AS {asTranslator("pkey")}'` (`:947-949`).
4. Subtable resolution: explicit arg, else `currentEnv['context_subtables']` bag keyed by table fullname, else `tblobj.attributes['default_subtable']` (`:954-958`).
5. WHERE macro pass: `IN_RANGEFINDER.sub` → `PERIODFINDER.sub` → `macro_expander.replace(where, 'TSQUERY,VECQUERY')` (`:959-962`).
6. Implicit predicates ANDed as `(chunk)` list (`:964-990`): env conditions `dictExtract(currentEnv, 'env_%s_condition_' % fullname.replace('.','_'))`; `dbtable.getPartitionCondition(ignorePartition=...)`; subtable condition (spec split on `[&|]`, `&→AND`, `|→OR`, `!→NOT`, each name → `dbtable.subtable(s).getCondition(sqlparams=...)`); logical deletion (`excludeLogicalDeleted is True` → `'$<field> IS NULL'`; `=='mark'` and not aggregate/count → extra column `,$<field> AS "_isdeleted"`); draft (`excludeDraft is True` and `draftField` → `'$<field> IS NOT TRUE'`).
7. Reference scan: `updateFieldDict` on columns; `embedFieldPars` then `updateFieldDict` on where; `updateFieldDict` on order_by/group_by/having (`:991-996`); `#BAG`/`#BAGCOLS` on columns (`:997-998`).
8. Column list cleanup: `uniquify`; per column, regex `re.search("(sum|count) *?\\(", col, re.I)` flips `aggregate=True` (`:1004`); auto-AS via `db.colToAs` + `asTranslator`; explicit AS recorded in `aliasDict` (`:1006-1019`).
9. **Fixpoint resolution loop** (`:1024-1034`): resolve every `relationDict` entry via `getFieldAlias` (with `self._currColKey` set for exploding attribution); because resolution can add new entries (join cnds, formulas), loop `while missingKeys`.
10. `templateReplace` — columns with `safeMode=True`, where/order_by/having/group_by without; joins list templated too: `self.cpl.joins = [gnrstring.templateReplace(j, colPars) for j in self.cpl.joins + self.cpl.additional_joins]` (`:1038-1053`); wildcard `'*_*'` joinCondition ANDed to where.
11. **DISTINCT handling** (`:1054-1081`): explicit truthy → `'DISTINCT '`. If `distinct in (None, '')` and `self._explodingRows` and not aggregate → auto-inject `'DISTINCT '`; missing ORDER BY expressions are appended to the SELECT list as `'%s AS __ord_col_%s'` (after lowercasing and stripping `asc/desc/ascending/descending`); if also `count` → `columns = 't0.<pkey>'` (counts **distinct main-table pkeys**, not exploded rows — flagged with the original "It is the right behaviour ????" doubt, REVIEW note 5).
12. Encrypted-column detection over `col_dict` keys (`:1084-1090`).
13. Store fragments into `cpl` — columns/order_by pass once more through the macro expander for TSRANK/TSHEADLINE/VECRANK (`:1092-1104`).

### 4.2 `compiledRecordQuery(...)` (`compiler.py:1106-1184`)

```python
def compiledRecordQuery(self, lazy=None, eager=None, where=None,
                        bagFields=True, for_update=False, relationDict=None, virtual_columns=None):
```

Walks `self.relations.digest('#k,#v,#a')`: physical columns → `'t0.<sqlname> AS "t0_<fieldname>"'` in `fieldlist` plus resultmap entry with `as`; relations → resultmap entry with `_relmode` (no SELECT entry); virtual joiners in mode `'O'` are promoted to virtual columns and their `cnd`/`range` scanned for refs (`:1156-1161`); Bag columns skipped unless `bagFields`. Then `_handle_virtual_columns`, `_recordWhere(where)` (`:1399-1421` — updateFieldDict + getFieldAlias + templateReplace), joins templated. `maintable_as` stays `None`.

---

## 5. SqlQuery API surface

### 5.1 Constructor (`query.py:143-189`, verbatim)

```python
def __init__(self, dbtable, columns=None, where=None, order_by=None,
             distinct=None, limit=None, offset=None,
             group_by=None, having=None, for_update=False,
             relationDict=None, sqlparams=None, bagFields=False,
             joinConditions=None, sqlContextName=None,
             excludeLogicalDeleted=True, excludeDraft=True,
             ignorePartition=False, subtable=None,
             addPkeyColumn=True, ignoreTableOrderBy=False,
             locale=None, _storename=None,
             checkPermissions=None,
             aliasPrefix=None,
             **kwargs):
```

Notes: `columns` defaults to `'*'` (`:157`); `**kwargs` are merged into `sqlparams` (`:162`) — arbitrary bind values by keyword; `addPkeyColumn = addPkeyColumn and dbtable.pkey is not None` (`:166`); `bagFields = bagFields or for_update` (`:176`); `rels`/`params` regex scans at `:172-174` are computed and never used (dead, REVIEW note 7). Compilation is lazy: `compiled` property caches `compileQuery()` (`:215-220`), `sqltext` property renders it (`:210-213`). `compileQuery(count=False)` (`:222-233`) instantiates `SqlQueryCompiler(self.dbtable.model, joinConditions=…, sqlContextName=…, sqlparams=…, aliasPrefix=…, locale=…)` and calls `compiledQuery(count=count, relationDict=…, **self.querypars)`.

There is no `mode` parameter on `SqlQuery` itself; `mode` appears at the `GnrSqlDb.queryCompile` level (`gnrsql/query.py:265-290`, full signature includes `mode: str | None = None`).

### 5.2 Consumption methods

| Method | Signature / behaviour |
|---|---|
| `cursor()` | executes `sqltext` with `sqlparams` under `tempEnv(currentImplementation=…)`; may return a **list of cursors** (multi-store) (`:235-239`) |
| `fetch()` | fetchall + post pipeline `handlePyColumns → _decryptRows → handleBagColumns` (`:241-255`); list-cursor branch skips the pipeline |
| `fetchPkeys()` | `[r[pkeyfield] for r in fetch]` (`:320-328`) |
| `fetchAsJson(key=None)` | JSON dump with datetime→isoformat encoder (`:330-349`) |
| `fetchAsDict(key=None, ordered=False, pkeyOnly=False)` (`:351-369`) |
| `fetchAsBag(key=None)` | sorted Bag of row dicts (`:371-377`) |
| `fetchGrouped(key=None, asBag=False, ordered=False)` (`:379-399`) |
| `test()` | `(self.sqltext, self.sqlparams)` without executing (`:401-409`) |
| `selection(pyWhere=None, key=None, sortedBy=None, _aggregateRows=False)` | `_dofetch` then builds `SqlSelection(dbtable, data, index=…, querypars=…, colAttrs=self._prepColAttrs(index), joinConditions=…, sqlContextName=…, key=…, sortedBy=…, explodingColumns=compiled.explodingColumns, checkPermissions=…, _aggregateRows=…, _aggregateDict=compiled.aggregateDict)` (`:446-468`) |
| `servercursor()` | named server-side cursor (`cursorname='*'`) (`:504-510`) |
| `serverfetch(arraysize=30)` / `iterfetch(arraysize=30)` | chunked generator over server cursor (`:512-537`) |
| `count()` | recompiles with `count=True`; multi-store sums partials; single row named `gnr_row_count` → its value, otherwise row count = number of groups/distinct rows (`:557-590`) |

`_prepColAttrs(index)` (`:470-502`) maps each result column back through `aliasDict`/`relationDict` to a model column and exports `dataType` (from `dtype`), `label` (from `name_long`), `print_width`, permission overrides.

### 5.3 SqlSelection surface (selection.py)

Constructor (`selection.py:82-143`): `(dbtable, data, index=None, colAttrs=None, key=None, sortedBy=None, joinConditions=None, sqlContextName=None, explodingColumns=None, checkPermissions=None, querypars=None, _aggregateRows=False, _aggregateDict=None)`. `_aggregateRows=True` collapses duplicate-pkey rows, list-aggregating exploding columns and applying `dbtable.fieldAggregate` (`:145-203`).

`output(self, mode, columns=None, offset=0, limit=None, filterCb=None, subtotal_rows=None, formats=None, locale=None, dfltFormats=None, asIterator=False, asText=False, **kwargs)` (`:256-340`) dispatches to `out_<mode>` / `iter_<mode>`; unknown mode → `SelectionExecutionError`.

**Output modes** (from `out_*`/`iter_*` methods, lines 927-1496): `listItems`, `count`, `distinctColumns`, `distinct`, `generator`, `data` (+iter), `dictlist` (+iter), `json`, `list`, `pkeylist` (+iter), `template` (rowtemplate+joiner), `records` (+iter), `bag` (optional recordResolver), `recordlist`, `baglist` (recordResolver, labelIsPkey), `selection` (recordResolver, caption), `grid` / `fullgrid` (grid struct + resolvers), `xmlgrid`, `html`, `tabtext` (forces asText), `xls`.

**Sort/filter/mutation API**: `sort(*args)` (`:558-588` — comma-string accepted, `.`/`@` normalized to `_`, `:d` suffix = descending, delegates to `gnrlist.sortByItem`); `filter(filterCb=None)` (`:591-607` — in-memory, reversible); `extend(selection, merge=True)`; `apply(cb)` (dict=update / None=remove / list=replace); `insert/append/newRow/remove`; `setKey(key)`; `getByKey(k)`; totals: `totalize(group_by=None, sum=None, collect=None, distinct=None, keep=None, key=None, captionCb=None, **kwargs)` (`:731`), `analyze(...)` (deprecated alias, `:776`), `totalizer/totalizerSort/totals/sum`; persistence: `freeze(fpath, autocreate=False, freezePkeys=False)`, `freezeUpdate()`.

### 5.4 SqlRecord surface (record.py)

Constructor (`record.py:186-247`): `(dbtable, pkey=None, where=None, lazy=None, eager=None, relationDict=None, sqlparams=None, ignoreMissing=False, ignoreDuplicate=False, bagFields=True, for_update=False, joinConditions=None, sqlContextName=None, virtual_columns=None, _storename=None, checkPermissions=None, aliasPrefix=None, **kwargs)` — kwargs merged into sqlparams; serialized composite pkey `'[...]'` parsed via `dbtable.parseSerializedKey`.

WHERE selection in `compileQuery` (`:290-311`): explicit `where` | `'$pkey = :pkey'` | AND of `f'"{self.aliasPrefix}0".{k}=:{k}'` over sqlparams keys that are real columns. Execution `adapterResult` (`:319-370`): 0 rows → `RecordNotExistingError` unless `ignoreMissing` (empty Bag); >1 rows → drop logically-deleted, then `RecordDuplicateError` unless `ignoreDuplicate`; exploding columns → `aggregateRecords` merges rows into lists + `fieldAggregate`.

**Output modes** (`output(mode, **kwargs)`, `:263-281`): `bag`, `dict`, `json`, `record`, `newrecord` (empty record + defaults + resolvers), `sample`, `template` — each with `resolver_one` / `resolver_many` flags where applicable.

**Resolvers**: `SqlRelatedRecordResolver` (`:47-116`) — lazy one-side record load via a new `SqlRecord` on `target_fld` (`pkg.table.column`) matching `relation_value`; `SqlRelatedSelectionResolver` (`:119-170`) — lazy many-side load via `db.table(...).relatedQuery(field=…, value=…, where=condition, ...)` then `selection().output(mode, recordResolver=(mode=='grid'))`. Both serialize for Bag persistence with `_serialized_app_db='maindb'`. `SqlRecordBag` (`:759+`) — Bag subclass with `save(**kwargs)` and a `db` property. `SqlDataResolver` (`query.py:51-99`) — generic lazy table resolver (`classArgs = ['tablename']`, `classKwargs = {'cacheTime': 0, 'readOnly': True, 'db': None}`).

---

## 6. Contract notes for a rewrite

**Assumptions about the model tree**
- The compiler navigates a *relation resolver* tree (`tblobj.relations`) whose nodes expose: `keys()` (physical fields), `getNode(p)`, indexing `curr[p]`, `tbl_name`, `pkg_name`, `attr['joiner']`, `digest('#k,#v,#a')`, `label`. Joiner dicts are the single source of join truth (keys listed in §3.6).
- Two parallel table objects exist and are used interchangeably: `db.table(name)` returns the runtime `SqlTable` (with `.model` → `DbTableObj`); the compiler is constructed with the **model** (`SqlQuery.compileQuery` passes `self.dbtable.model`, `query.py:226`) and reaches back through `tblobj.dbtable` for runtime hooks (`subquery_*`, `sql_formula_*`, `env_*`, partition/subtable conditions, `fieldAggregate`). A rewrite must decide on a single facade.
- Naming: `sqlnamemapper` maps model name → adapted SQL name; `DbColumnObj.sqlname` is **environment-dependent** for localized columns (suffix `_<current_language>` from `currentEnv`, `columns.py:203-218`) — the same query spec compiles to different SQL under different locales.

**Order of operations (must be preserved or consciously changed)**
1. columns normalization/glob expansion → 2. count/pkey column adjustments → 3. WHERE macros (`IN_RANGE`, `PERIOD`, adapter TSQUERY/VECQUERY) → 4. implicit predicates (env conditions, partition, subtable, logical deletion, draft) → 5. `embedFieldPars` (WHERE only) → 6. `updateFieldDict` on every fragment → 7. `#BAG`/`#BAGCOLS` (columns only) → 8. AS assignment/aliasDict → 9. fixpoint `getFieldAlias` loop (JOIN side effects) → 10. `templateReplace` (safeMode only for columns) → 11. DISTINCT auto-injection + `__ord_col_N` → 12. encrypted-column scan → 13. adapter macro second pass on columns/order_by. Macro availability is **positional**: `#ENV/#PREF/#THIS` work only inside `sql_formula` (and sub-select where), never in a top-level WHERE; `#PERIOD` only in WHERE; `#BAG(COLS)` only in columns.

**Dialect delegation boundary** — everything dialect-specific goes through the adapter: `compileSql` (final assembly incl. LIMIT/OFFSET/FOR UPDATE), `asTranslator` (AS-name quoting), `adaptSqlName` (identifier quoting), `macroExpander` (class of macro set), `adaptTupleListSet` (list bind params), `paramstyle`. The compiler itself hard-codes ANSI-ish `LEFT JOIN … ON`, `lower()`, `EXISTS`, `CAST`, `BETWEEN`, `IS NULL / IS NOT TRUE` — these are inline, not delegated.

**Statefulness / side channels a rewrite must decide on**
- `sqlparams` is mutated during compilation (`#PERIOD` adds `_from`/`_to`; joinCondition `params` merged; TSQUERY/VECQUERY channel dicts; `var_` values pushed into `db.currentEnv`). Compilation is therefore not pure and not idempotent.
- `db.currentEnv` is read for: storename, `context_subtables`, per-table `env_*_condition_*` WHERE injections, `#ENV`, virtual-columns cache (`table.py:358-384`, explicitly not thread-safe), `current_language`. Identical inputs → different SQL depending on ambient env.
- `SqlQuery.compiled` is cached but `count()` recompiles separately with `count=True`; `reuse_relation_tree` toggles shared vs fresh relation resolvers (`compiler.py:228-231`).

**Known oddities (each verified in source; several carry `# REVIEW:` markers, summarized at `compiler.py:1448-1512` and `query.py:593-624`)**
- Only LEFT JOINs, ever; INNER semantics are unobtainable except via WHERE.
- Row explosion is compensated by auto-DISTINCT, `__ord_col_N` hidden sort columns, and post-fetch `_aggregateRows` — three cooperating hacks. `count()` on an exploding query counts distinct main-table pkeys, not result rows.
- Aggregate detection via regex `(sum|count) *?\(` misses `avg/min/max/array_agg` etc.
- Interval semantics disagree: `#IN_RANGE` upper bound `<=`, legacy joiner `between` upper bound `<`, `#PERIOD` uses SQL `BETWEEN` (inclusive).
- `_getRelationAlias`: `target_sqlcolumn` can remain `None` on the `case_insensitive`/`virtual` branches if the standard/composite branch was taken first (REVIEW note 11).
- `updateFieldDict` uses `str.replace(colname, …, 1)` — substring-based, order-sensitive replacement of `@rel` tokens.
- `#ENV` fallback emits the literal `'Not found <name>'` into SQL rather than raising; `_handle_virtual_columns` silently skips `None` columns.
- `embedFieldPars` silently switches a bind parameter into SQL text when its value looks like `$col`/`@rel` — an injection-adjacent convenience that a rewrite must make explicit.
- Dead code: duplicated `virtual_columns or []` (`compiler.py:1139-1141`), unused `rels`/`params` in `SqlQuery.__init__`, commented `_getJoinerCnd`, refs-#120 block; `_dofetch` multi-cursor branch overwrites `index` per cursor and skips the py/decrypt/bag pipeline; pyWhere branch never closes the cursor.
- Fetch post-pipeline order is a contract: `handlePyColumns` → `_decryptRows` → `handleBagColumns` (decryption must precede Bag XML parsing, `query.py:304-318`).

---

## 7. Addendum (2026-07-08) — sizes, consumers, dialect boundary, tests, porting estimate

Findings from a verification pass; sections 1–6 were re-checked
against the source and confirmed accurate.

### 7.1 Package sizes

`gnrsqldata/` totals 4,624 lines: `compiler.py` 1512, `selection.py`
1588, `record.py` 865, `query.py` 624, `__init__.py` 35 (facade
re-exporting the public classes). Surrounding context: `adapters/`
6510, `gnrsqlmodel/` 3574, `gnrsql/` 2777, `gnrsqltable/` 4460. The
core to rewrite is `compiler.py` (~33% of the package);
query/selection/record are mostly orchestration (fetch pipeline,
output modes) whose API must be preserved.

### 7.2 Consumers — the public boundary

`compiledQuery`/`compiledRecordQuery` have **no callers outside
`gnrsqldata/`**: the compiler is an internal boundary, replaceable
behind a stable API. The public surface is:

- `SqlQuery` / `SqlSelection` / `SqlRecord` (re-exported by
  `gnrsqldata/__init__.py:29-34`), wrapped by
  `gnrsqltable/query.py:125-178` (`SqlTable.query(...)`, plus
  `relatedQuery`/`relatedQueryPars` :62,:74) and
  `gnrsqltable/record.py:38`;
- `GnrSqlDb.query(table, **kw)` and `queryCompile(...)`
  (`gnrsql/query.py:253-265`);
- macro registry `db.registerMacros()` / `_macro_registry`
  (`gnrsql/db.py:220-228`).

Framework-wide usage (excluding tests): ~130 call sites of `.query(`
in `gnr/`; `.selection(` used across web
(`_gnrbasewebpage.py`, `gnrwebpage_proxy/apphandler/*`), batch
(`btcmail.py`, `btcbase.py`), app engine (`gnrdbo.py`,
`api_engine/core.py`) and xtnd (`gnrpandas.py`). The port must
preserve `SqlQuery.__init__` (`query.py:143`), `table.query()`, the
fetch modes and the selection output modes (~24 `out_*`/`iter_*`,
`selection.py:927-1496`).

### 7.3 Dialect boundary at runtime

The compiler emits ANSI-flavored SQL with a few PG-isms hard-coded
(`IS NULL` / `IS NOT TRUE` for logical deletion/draft,
`compiler.py:982,989`); nothing else in the compiler is strictly
PG-only. The genuinely PG-specific surface lives **outside** it:
adapter macro sets (`#TSQUERY`/`#TSRANK`/`#TSHEADLINE`/`#VECQUERY`/
`#VECRANK`, `_gnrbasepostgresadapter.py:13-108`) and the
`subQueryColumn` json/xml aggregation SQL generated by the **model**
(`gnrsqlmodel/model.py:1179-1222` — the PG leakage of design question
7). SQLite never overrides `compileSql`: it repairs the PG-flavored
text at runtime in `prepareSqlText` (`gnrsqlite.py:111-128`:
ILIKE→LIKE, `~*`→REGEXP, `IS [NOT] TRUE/FALSE` boolean rewrite). PG's
`compileSql` runs a second pass (`TsVectorCompiler().adapt`,
`gnrpostgres.py:194-197`). Consequence for the rewrite: the new
compiler can stay dialect-agnostic; dialect variance concentrates in
the renderer/adapter macro layer.

### 7.4 Test map — behavioral, not pure-compile

`tests/sql/` holds 32 files, ~922 test functions. Compiler-relevant:

| File | Lines | Tests | Kind | Real DB |
|---|---|---|---|---|
| `test_compiler_coverage.py` | 3137 | 291 | behavioral — runs queries, asserts values/counts | sqlite always, PG when available |
| `h_query_surface_test.py` | 405 | 41 | `SqlQuery` API surface (incl. `.test()`/`.sqltext`) | yes |
| `h_record_surface_test.py` | 363 | 37 | `SqlRecord` surface | yes |
| `h_selection_surface_test.py` | — | 58 | `SqlSelection` surface | yes |
| `test_vecquery_macro.py` | 125 | 13 | **pure-compile**: FakeQueryCompiler, asserts exact SQL strings | no |
| `test_compiler_simulation.py` | 192 | 4 | relation-tree resolution benchmark | yes |
| `test_macro_registration.py` | 250 | 26 | macro registry | partial |

Key gap for the rewrite: **there is no pure-compile oracle corpus for
the core** (SELECT/JOIN/WHERE as expected strings) — the only
string-level oracles cover the PG macros. `test_compiler_coverage.py`
asserts result values on a live DB, which makes it a regression
harness, not a compile spec. A pure-compile corpus can be derived by
running the legacy `SqlQuery.test()` (returns `(sqltext, sqlparams)`
without executing, `query.py:401-409`) over the `test_invoice` model
(plan, Fase 4.2).

### 7.5 Porting-complexity estimate

Mechanical (near 1:1): the token/macro regexes (`compiler.py:62-74`)
and their expanders (`:1274-1397`); `SqlCompiledQuery` +
`get_sqltext` (`:118-169`); `aliasCode`/`updateFieldDict`/
`embedFieldPars` (`:241-250,709-742,802-829`); the implicit predicates
(logical deletion/draft/partition/env, `:964-990`); DISTINCT
auto-injection (`:1054-1081`); the fetch pipeline
(`query.py:257-318`).

The five entangled points (redesign, not translation):

1. `_getRelationAlias` — JOIN construction from the joiner dict
   (`:507-668`): O/many direction, 6 ON-condition variants in priority
   order, composite keys, alias memoization, multi-tenant
   `_get_sqlfullname`, exploding tracking.
2. `getFieldAlias` + virtual dispatch (`:273-454`): recursion on
   alias columns, the `sql_formula` pipeline calling **runtime Python
   methods** (`sql_formula_*` :397, `subquery_*` :406, `env_*` :346)
   and recursively invoking `db.queryCompile` (:418) —
   runtime-in-compile is the main architectural knot.
3. The `relationDict` fixpoint (`:1024-1034`): resolving a field can
   add new entries mid-iteration, with JOIN emission as side effect.
4. Positional macro pipeline + mutation of `sqlparams`/`currentEnv`
   (`:311-434, 959-962, 1341-1397`).
5. `compiledRecordQuery` + `_getRelationMode` +
   `_handle_virtual_columns` (`:1106-1272`): `relations.digest`
   walk, `DynItemOne/OneOne/Many` classification consumed by
   `SqlRecord._loadRecord_DynItem*` (`record.py:557,605,650`).

The tree contract the compiler actually needs is compact (~6-7
methods): node access (`getNode`/`keys`/`[]`), `digest('#k,#v,#a')`,
node attrs `tbl_name`/`pkg_name`/`attr['joiner']`, `table_aliases`,
`getVirtualColumn`, `column().adapted_sqlname`/`sqlnamemapper`, plus
the runtime hooks listed in §3.6 — defining it early anchors the
grammar design (plan, Fase 4.1).

## Riferimenti

- Session: `ce254e4b-4c8c-49ae-a635-12536130ad35` (2026-07-06); addendum verification 2026-07-08
- Legacy source: `/Users/gporcari/Sviluppo/Genropy/genropy/worktrees/develop/gnrpy/gnr/sql/gnrsqldata/` @ `83c138bb6`
- Improvement experiments (2026): doc `07`
