# Legacy Inventory — Model Grammar (gnr.sql.gnrsqlmodel)

**Version**: 0.1.0 · **Last Updated**: 2026-07-06 · **Status**: 🔴 DA REVISIONARE

Part of the asqueel design documentation set (see `00_INDEX.md`).
Scope: exhaustive inventory of the legacy `DbModelSrc` grammar and the
runtime model objects, as input to the design of the new SqlBuilder
grammar. Source: Genropy worktree `develop` (branch
`fix/websocket-user-events-default-off`, HEAD `83c138bb6`).

---

Sources (all under `/Users/gporcari/Sviluppo/Genropy/genropy/worktrees/develop/gnrpy/gnr/sql/gnrsqlmodel/`):
- `model.py` — `DbModel` (l. 58–576), `DbModelSrc` (l. 579–1376)
- `columns.py` — `DbBaseColumnObj` (l. 38), `DbColumnObj` (l. 194), `DbVirtualColumnObj` (l. 255), `AliasColumnWrapper` (l. 340)
- `table.py` — `DbTableObj` (l. 48)
- `containers.py` — list containers, `DbTableAliasObj`, `DbSubtableObj`, `DbIndexObj`
- `obj.py` — `DbModelObj`, `DbPackageObj`
- `helpers.py` — `bagItemFormula`, `toolFormula`, exceptions

Architecture in one line: `DbModelSrc` (a `GnrStructData` subclass, model.py:579) builds a **source tree** of tagged nodes; `DbModel.build()` (model.py:106) compiles it into a **runtime object tree** rooted at `DbModelObj.makeRoot(self, self.src, sqldict)` (model.py:173), where `sqldict` maps each `sqlclass` tag string to its Python class via `moduleDict('gnr.sql.gnrsqlmodel', 'sqlclass,sqlresolver')` (model.py:165). Source tags in use: `package_list`, `package`, `table_list`, `table`, `column_list`, `column`, `virtual_columns_list`, `virtual_column`, `tblalias_list`, `table_alias`, `colgroup_list`, `colgroup`, `subtable_list`, `subtable`, `index_list`, `index`.

A note on `extract_kwargs` (imported model.py:41 from `gnr.core.gnrdecorator`): it collects `<prefix>_*` keyword arguments into a `<prefix>_kwargs` dict parameter. Internal evidence in these files shows the default strips the prefix (e.g. `meta_kwargs.get('childmode')` at model.py:339–340 implies `meta_childmode=...` arrives as key `'childmode'`), while `slice_prefix=False` keeps full key names (used in `column`, model.py:840).

---

## 1. DbModelSrc grammar methods

### 1.1 `package` (model.py:588–619)

```python
def package(self, name, sqlschema=None, comment=None, name_short=None,
            name_long=None, name_full=None, **kwargs)
```

- Lazily creates the `packages` container (`self.child('package_list', 'packages')`, l. 611–612).
- Creates `self.child('package', 'packages.%s' % name, comment=..., sqlschema=..., name_short=..., name_long=..., name_full=..., **kwargs)` (l. 614–618).
- `**kwargs` is open — anything else (e.g. `sqlprefix`, `multi_tenant`, `pkgcode`) lands directly as package-node attributes.
- No validation of any kind.

### 1.2 `externalPackage` (model.py:621–627)

```python
def externalPackage(self, name)
```

- One-liner: `return self.root('packages.%s' % name)` — invokes the root struct as a callable with the dotted path, returning the (existing) package node of another package so it can be extended (columns plugged into other packages' tables).

### 1.3 `table` (model.py:629–669)

```python
def table(self, name, pkey=None, lastTS=None, rowcaption=None, sqlname=None,
          sqlschema=None, comment=None, name_short=None, name_long=None,
          name_full=None, **kwargs)
```

- Lazily creates the `tables` container (`table_list`, l. 660–661).
- **Order dependency:** `pkg = self.parentNode.label` (l. 662) — must be called on a package node; the enclosing package name is baked in.
- Creates node `'table'` at `tables.<name>` with attributes: `comment`, `name_short`, `name_long`, `name_full`, `pkey`, `lastTS`, `rowcaption`, `pkg`, `fullname='%s.%s' % (pkg, name)`, plus open `**kwargs` (l. 663–668). Note `sqlname`/`sqlschema` are declared parameters but are **not** in the explicit `child()` call — see Oddity 5.19: `sqlname`/`sqlschema` declared in the signature are silently dropped by `table()` as written (they do not appear in the `child(...)` attribute list at l. 663–668).

### 1.4 `subtable` (model.py:671–688) — dispatcher

```python
def subtable(self, name, condition=None, **kwargs)
```

- If `self.attributes['tag'] == 'package'` → `_subtable_package(name, **kwargs)`; else `_subtable_table(name, condition=condition, **kwargs)` (l. 685–688). Same grammar word, two entirely different constructs.

#### `_subtable_package` (model.py:690–763) — table inheritance

```python
def _subtable_package(self, name, maintable=None, relation_name=None, **kwargs)
```

- `pkey` in kwargs triggers a `DeprecationWarning` ("you cannot set pkey inside subtable", l. 711–717).
- `pkg, tblname = maintable.split('.')`; main table source fetched as `self.parent[pkg]['tables'][tblname]` (l. 718–719).
- `name_plural = relation_name or kwargs.get('name_plural') or name` (l. 721).
- Creates the subtable as a **real table node** with `maintable=maintable` attribute (l. 722).
- Copies every main-table attribute via `setdefault`, **except keys starting with `partition_`** (l. 724–726).
- Adds discriminator to the main table: `maintable_src.column('__subtable', size=':64', group='_', indexed=True)` (l. 727).
- Copies every physical column of the main table: attribute dict minus `tag` and `indexed`, plus `sql_inherited=True` (l. 728–734). For each relation child on a copied column, rewrites `relation_name` to `kwargs.get('relation_name') or f'{name_plural.lower().replace(" ", "_")}'`, pops `related_column`, re-declares `col.relation(related_column, **rnattr)` (l. 735–744).
- `subtablename = f'{self.attributes.get("pkgcode")}.{name}'` — uses the **package's `pkgcode` attribute** (l. 745).
- Subtable's own discriminator: `result.column('__subtable', sql_value=f"'{subtablename}'", default=name, group='_', sql_inherited=True)` (l. 746–749).
- Registers on the main table: `subtable(name, condition='$__subtable=:sn', condition_sn=name, table=subtablename, name_plural=...)` and `subtable('_main', condition='$__subtable IS NULL', name_plural=...)`; sets `maintable_attributes['default_subtable'] = '_main'` (l. 750–760).
- On the subtable itself: `result.subtable('_main', condition='$__subtable=:sn', condition_sn=name)` and `resultattr['default_subtable'] = '_main'` (l. 761–762).

#### `_subtable_table` (model.py:765–792) — filtered view

```python
def _subtable_table(self, name, condition=None, name_long=None, **kwargs)
```

- Lazily creates the `subtables` container (`subtable_list`, l. 782–783).
- `condition_kwargs = dictExtract(kwargs, 'condition_')` (l. 784) — condition parameters (`condition_sn=...` → `sn`).
- `self.attributes.setdefault('group_subtables', '!![en]Subtables')` (l. 785) — injects a column-group label on the table.
- **Side effect:** creates a boolean formula column `formulaColumn(f'subtable_{name}', condition, dtype='B', name_long=name_long or name, group='subtables', _addClass=f'subtable_{name}', **{f'var_{k}': v for k, v in condition_kwargs.items()})` (l. 786–791).
- Creates node `'subtable'` at `subtables.<name>` with `condition=condition, **kwargs` — the `condition_*` keys remain in `kwargs` and are stored as node attributes too (consumed at runtime by `DbSubtableObj.getCondition`, containers.py:61–85).

### 1.5 `colgroup` (model.py:794–838)

```python
@extract_kwargs(col=True)
def colgroup(self, name, name_long=None, col_kwargs=None, **kwargs)
```

- `col_*` kwargs are collected into `col_kwargs` — defaults applied to every child column.
- Sets `self.attributes.setdefault(f'group_{name}', name_long or name)` on the **table** node (l. 817) — the table-level group-label registry.
- Lazily creates `colgroups` container (`colgroup_list`); creates node `'colgroup'` at `colgroups.<name>` with `name_long` and open kwargs (l. 818–823).
- `cg._destinationNode = self` (l. 824) — columns invoked on the colgroup struct are physically created **on the table**.
- Installs a closure `cg._decorateChildAttributes(destination, tag, kwargs)` (l. 826–837) that mutates each child column's kwargs:
  - `kwargs['group'] = f'{name}.{len(destination) + 1:03}'` — ordinal group path like `anagraphics.001`;
  - `kwargs['colgroup_label'] = cg.parentNode.label`;
  - `kwargs['colgroup_name_long'] = cg.attributes.get('name_long', kwargs['colgroup_label'])`;
  - `kwargs.setdefault(k, v)` for every pair in `col_kwargs`.

### 1.6 `column` (model.py:840–952) — THE physical column

```python
@extract_kwargs(variant=dict(slice_prefix=False), ext=True)
def column(self, name, dtype=None, size=None, default=None, notnull=None,
           unique=None, indexed=None, sqlname=None, comment=None,
           name_short=None, name_long=None, name_full=None, group=None,
           onInserting=None, onUpdating=None, onDeleting=None,
           localized=None, variant=None, variant_kwargs=None,
           ext_kwargs=None, **kwargs)
```

Body behavior, in order:

1. **String coercion:** `indexed`/`unique` given as strings are converted with `gnr.core.gnrstring.boolean` (l. 894–899). Note the local import at l. 894.
2. **Shorthand:** `if '::' in name: name, dtype = name.split('::')` (l. 900–901) — `name::dtype` works here.
3. Lazily creates the `columns` container (`column_list`, l. 902–903).
4. **Localized resolution:** if `localized is True`, reads `self.root._dbmodel.db.extra_kw.get('languages')`; if it contains a comma, `localized = dblanguages.lower()`, otherwise `localized = None` (l. 905–910) — single-language DBs silently drop localization.
5. **Virtual-column coexistence:** if `virtual_columns.<name>` already exists (l. 904, 911–920), the physical column is **not created**; instead the VC node's attributes are updated with the **non-None subset** of `dict(dtype, name_short, name_long, name_full, comment, unique, indexed, group, **kwargs)` and `vc.value` is returned. `size`, `default`, `notnull`, `sqlname`, `localized`, trigger hooks are **dropped** in this path.
6. `kwargs.update(variant_kwargs)` — because of `slice_prefix=False`, variant kwargs keep their full names, so attributes like `variant_total_dtype=...` land verbatim on the node (matching the `dictExtract(colattr, 'variant_<name>_')` read at table.py:454–457). Then `kwargs.update(ext_kwargs)` (l. 921–922) — ext kwargs (prefix-sliced, keyed by package name) also land as attributes named after the package.
7. Creates node `'column'` at `columns.<name>` with: `dtype, size, comment, sqlname, localized, name_short, name_long, name_full, default, notnull, unique, indexed, group, onInserting, onUpdating, onDeleting, variant, **kwargs` (l. 923–931).
8. `tblsrc = self._destinationNode if hasattr(self, '_destinationNode') else self` (l. 932) — colgroup redirection.
9. **Package-extension hooks:** for each `ext_<pkg>=...` kwarg whose package is installed, calls `pkgobj.ext_config(tblsrc, colname=name, colattr=result.attributes, **extKwargs)` (l. 934–942); a non-dict value is wrapped as `{pkgExt: extKwargs}`.
10. **Localization hook:** if `localized`, calls the owning package's `handleLocalizedColumn(tblsrc, colname=name, colattr=result.attributes, languages=localized)` (l. 944–951). Package looked up via `tblsrc.attributes['pkg']`.

### 1.7 `virtual_column` (model.py:954–1024) — the generic virtual column

```python
@extract_kwargs(variant=dict(slice_prefix=True))
def virtual_column(self, name, relation_path=None, sql_formula=None,
                   select=None, exists=None, py_method=None, _override=None,
                   variant=None, variant_kwargs=None, **kwargs)
```

- `if '::' in name: name, dtype = name.split('::')` (l. 989–990) — **the split dtype is assigned to a local and never used**: the `name::dtype` shorthand is silently discarded here (see Oddity 5.3).
- Lazily creates `virtual_columns` container (`virtual_columns_list`, l. 991–992).
- **Clash with a physical column** (l. 993–1005): if `name in columns` — with `_override=True` the physical node is removed (`columns.popNode(name)`); otherwise raises `GnrSqlException("Column {colname} already defined in table {tablename} as a real column. Use _override to override it")`.
- `kwargs.update(variant_kwargs)` (prefix sliced here, unlike `column`).
- Creates node `'virtual_column'` at `virtual_columns.<name>` with: `relation_path, select, exists, sql_formula, py_method, virtual_column=True, variant, **kwargs` (l. 1008–1013).
- **Runtime hot-insertion** (l. 1014–1023): if `db.auto_static_enabled` and the compiled model already exists, immediately instantiates `DbVirtualColumnObj(structnode=vcsrc.parentNode, parent=virtual_columns)` into the **compiled** tree (`virtual_columns.children[obj.name.lower()] = obj`), navigating `self.parentNode.label` (table name) and `self.parentNode.parentNode.parentNode.label` (package name). There is an inline REVIEW comment flagging this as fragile.

### 1.8 `aliasColumn` (model.py:1026–1036)

```python
def aliasColumn(self, name, relation_path, **kwargs)
```

- Pure shorthand: `return self.virtual_column(name, relation_path=relation_path, **kwargs)`.

### 1.9 `joinColumn` (model.py:1038–1047)

```python
def joinColumn(self, name, **kwargs)
```

- `return self.virtual_column(name, join_column=True, **kwargs)`. The interesting behavior is at runtime: `DbVirtualColumnObj.doInit` (columns.py:276–279) synthesizes `relation_path = f'@{self.name}.{reldict["related_column"].split(".")[-1]}'` when `join_column` is set and the VC carries a relation.

### 1.10 `compositeColumn` (model.py:1049–1089) + `_buildCompositeColumnFormula` (model.py:1091–1128)

```python
def compositeColumn(self, name, columns=None, static=True, **kwargs)
```

- `composed_of = [c[1:] if c.startswith('$') else c for c in columns.split(',')]` (l. 1072–1074) — `$` prefixes are tolerated but **warned about**: `logger.warning(f"compositeColumn {name} has columns='{columns}'. It should be '{composed_of_str}'.")` (l. 1076–1080).
- Creates the VC with `virtual_column(name, composed_of=composed_of_str, static=static, sql_formula=None, dtype='JS', **kwargs)` (l. 1081–1084) — dtype is hard-set to `'JS'`, `static` defaults to `True`.
- **Deferred formula build:** `self.root._dbmodel.deferOnBuilding(self._buildCompositeColumnFormula, name=name, composed_of=composed_of)` (l. 1085–1088). Rationale (docstring l. 1057–1062): source columns may be declared in any order relative to this call; validation must happen when the table definition is complete.

`_buildCompositeColumnFormula(self, name, composed_of)` — runs inside `DbModel.runOnBuildingCb()`:

- `tblname = self.attributes.get('fullname') or self.attributes.get('name') or ''` (l. 1102).
- For each source column, `self.getNode(f'columns.{column}')`; if missing:
  - if it exists under `virtual_columns` → `GnrSqlException("compositeColumn '<name>' in table <tbl>: source column '<col>' is a virtual column; a physical column is required")` (l. 1107–1112);
  - otherwise → `GnrSqlException("... source column '<col>' does not exist")` (l. 1113–1116).
- Per-dtype chunk generation (l. 1117–1124):
  - `dtype in ('A', 'C', 'T')` → `""" '"' ||  ${column} || '"' """` (quoted string);
  - `dtype in ('L', 'F', 'R', 'B')` → `f'${column}'` (raw literal);
  - otherwise → `rf""" '"' ||  ${column} || '\:\:{dtype}"' """` (quoted with escaped `::dtype` suffix — the TytxJSON-style typed string).
- Chunks joined with `" ||', '||"`, wrapped as `f"'[' || {sql_formula} || ']' "` (l. 1125–1126) — a JSON-array-shaped text expression.
- Result written back onto the source node: `vcnode.attr['sql_formula'] = sql_formula` (l. 1127–1128).

### 1.11 `bagItemColumn` (model.py:1130–1158)

```python
def bagItemColumn(self, name, bagcolumn=None, itempath=None, dtype=None, **kwargs)
```

- `sql_formula = bagItemFormula(bagcolumn=bagcolumn, itempath=itempath, dtype=dtype, kwargs=kwargs)` — note `kwargs` is passed **by reference and mutated**: `bagItemFormula` (helpers.py:34–87) injects `kwargs['var_calculated_path'] = f'/GenRoBag/{itempath}/{suffix}'` (helpers.py:74), which then flows into the node attributes through `**kwargs`.
- `bagItemFormula` details: dot path split; `#N` segments become 1-based XPath positional indexes `*[N+1]` (helpers.py:67–70); trailing `?attr` extracts an XML attribute instead of `text()` (helpers.py:63–66); core expression `" CAST( (xpath(:calculated_path, CAST({bagcolumn} as XML) ) )[1]  AS text)"` (helpers.py:71–73); a hardcoded **PostgreSQL** type map (`{'T': 'text', 'A': 'text', 'C': 'text', 'P': 'text', 'N': 'numeric', 'B': 'boolean', 'D': 'date', 'H': 'time without time zone', 'L': 'bigint', 'R': 'real', 'X': 'text'}`, helpers.py:78–84) wraps a second CAST for non-text dtypes.
- Final node: `virtual_column(name, sql_formula=..., dtype=dtype, bagcolumn=bagcolumn, itempath=itempath, **kwargs)`.

### 1.12 `toolColumn` (model.py:1160–1177)

```python
def toolColumn(self, name, tool=None, dtype=None, **kwargs)
```

- `sql_formula = toolFormula(tool, dtype=dtype, kwargs=kwargs)`; `toolFormula` (helpers.py:90–123) builds `"(:env_external_host || '/_tools/{tool}?record_pointer=' || $__record_pointer)"` and wraps it in a SQL `format()` call producing either `<img>` (when `dtype == 'P'`) or `<a>`; reads from kwargs: `format_class`, `iconClass`, `link_text`, `name_long` (helpers.py:111–122). HTML-in-SQL, PostgreSQL `format()` specific.

### 1.13 `subQueryColumn` (model.py:1179–1222)

```python
def subQueryColumn(self, name, query=None, mode=None, **kwargs)
```

Three modes:

- **`mode == 'json'`** (l. 1199–1208): `tname = f"{self.attributes.get('fullname').replace('.', '_')}_{name}"`; formula `f"SELECT json_agg(row_to_json({tname}_json)) FROM #nestedselect {tname}_json"`; node created with `sql_formula=..., select_nestedselect=query, subquery=True, format='json_table', **kwargs`. `#nestedselect` is a placeholder resolved downstream by the query compiler from the `select_nestedselect` attribute.
- **`mode == 'xml'`** (l. 1209–1219): `columns = query['columns'].replace('$', '')` — requires `query` to be a dict with a `'columns'` key; formula `f"SELECT xmlagg(xmlelement(name {tname}_xml, xmlforest({columns}))) FROM #nestedselect {tname}_xml"`; node gets `sql_formula=..., select_nestedselect=query, subquery=True, **kwargs` (no `format` attribute).
- **default/scalar** (l. 1220–1222): `virtual_column(name, select=query, subquery=True, subquery_aggr=mode, **kwargs)` — plain sub-select where `mode` (if given) is the aggregation function name stored as `subquery_aggr`.

### 1.14 `formulaColumn` (model.py:1224–1248)

```python
def formulaColumn(self, name, sql_formula=None, select=None, exists=None,
                  dtype='A', **kwargs)
```

- Thin wrapper: `virtual_column(name, sql_formula=sql_formula, select=select, exists=exists, dtype=dtype, **kwargs)`. Default dtype `'A'`.

### 1.15 `pyColumn` (model.py:1250–1262)

```python
def pyColumn(self, name, py_method=None, **kwargs)
```

- `py_method = py_method or 'pyColumn_%s' % name` — implicit method-name convention on the table's Python class; then `virtual_column(name, py_method=py_method, **kwargs)`.

### 1.16 `aliasTable` / `table_alias` (model.py:1264–1283)

```python
def aliasTable(self, name, relation_path, **kwargs)
table_alias = aliasTable   # model.py:1283
```

- `'::'` shorthand split with **discarded** dtype (same dead pattern as `virtual_column`, l. 1274–1275).
- Lazily creates `table_aliases` container (`tblalias_list`); node `'table_alias'` created at `'table_aliases.@%s' % name` — **the label carries the `@` prefix**, so runtime lookups like `self['table_aliases.%s' % firstrel]` (table.py:583) work with `@`-prefixed segment names.

### 1.17 `index` (model.py:1285–1310)

```python
def index(self, columns=None, name=None, unique=None)
```

- `columns` may be a str, list, or tuple; lists/tuples are comma-joined (l. 1302–1303).
- Default name: `'%s_%s_key' % (self.parentNode.label, columns.replace(',', '_'))` (l. 1304–1305).
- Lazily creates `indexes` container (`index_list`); node `'index'` at `indexes.<name>` with attributes `columns`, `unique`.
- This is the **only** grammar method with a closed signature (no `**kwargs`).

### 1.18 `relation` (model.py:1312–1376) — declared on a column node

```python
def relation(self, related_column=None, related_table=None, mode='relation',
             one_name=None, many_name=None, eager_one=None, eager_many=None,
             one_one=None, child=None, one_group=None, many_group=None,
             onUpdate=None, onUpdate_sql='cascade', onDelete=None,
             onDelete_sql=None, deferred=None, relation_name=None,
             onDuplicate=None, **kwargs)
```

- `related_table` is documented as "Unused — kept for backwards compatibility" (l. 1343) and is indeed never referenced in the body.
- Defaults worth noting: `mode='relation'`, `onUpdate_sql='cascade'`.
- **Group hoisting side effect** (l. 1362–1366): if the FK column has a `group` other than `'_'` and no `one_group` was given, the column's `group` attribute is rewritten to `'_'` (reserved/hidden), the original group becomes `one_group`, and `one_group` is also written onto the column node itself. So declaring a relation semantically moves the FK column's grouping onto the relation.
- Storage: `self.setItem('relation', self.__class__(), related_column=..., mode=..., one_name=..., many_name=..., one_one=..., child=..., one_group=..., many_group=..., deferred=..., onUpdate=..., onDelete=..., eager_one=..., eager_many=..., onUpdate_sql=..., onDelete_sql=..., relation_name=..., onDuplicate=..., **kwargs)` (l. 1367–1376) — a child node labelled `relation` **inside the column node's value**, with an open kwargs tail (this is how `cnd`, `join_on`, `between`, `storefield`, `external_relation`, `ignore_tenant`, `resolver_*`, `meta_*`, `inheritProtect`, `inheritLock` etc. travel to `addRelation`).

---

## 2. Attribute inventory

Everything below is an attribute name actually **read** somewhere in these six files (with the reading site). `**kwargs` is open everywhere except `index()`, so this list is the observable contract, not a closed schema.

### 2.1 Package node attributes

| Attribute | Kind | Read at |
|---|---|---|
| `sqlschema` | physical | obj.py:165, obj.py:223; table.py:153 (table fallback) |
| `sqlname` | physical | obj.py:165 (fallback after sqlschema) |
| `sqlprefix` | physical | obj.py:212 (`tableSqlName`: `True`→pkg name prefix, falsy→bare table name, str→custom prefix) |
| `multi_tenant` | physical/deploy | table.py:125 (inherited by tables) |
| `pkgcode` | semantic | model.py:745 (`_subtable_package` discriminator value) |
| `comment`, `name_short`, `name_long`, `name_full` | semantic | set model.py:614–618; name accessors obj.py:106–128 |

### 2.2 Table node attributes

Physical / SQL:

| Attribute | Read at |
|---|---|
| `pkey` | table.py:212 (`pkey` property); composite expansion via the pkey column's `composed_of` (table.py:204–206) |
| `sqlname` | table.py:167 (falls back to `pkg.tableSqlName` → `<pkg>_<table>`) |
| `sqlschema` | table.py:153 (falls back to pkg sqlschema; tenant override via `currentEnv['tenant_schema']`, `'_main_'` sentinel forces ignore, table.py:154–161) |
| `multi_tenant` | table.py:123 (None → inherit from package) |
| `maintable` | table.py:116 (subtable → `_refsqltable` redirection for sqlname/sqlschema, table.py:146–149) |

Semantic / application metadata:

| Attribute | Read at |
|---|---|
| `lastTS` | table.py:218 |
| `rowcaption` | table.py:246 (fallback chain: `rowcaption` → `'$'+caption_field` → `'$'+pkey`, table.py:245–250) |
| `caption_field` | table.py:247 |
| `name_plural` | table.py:142; model.py:721, 754, 758 |
| `newrecord_caption` | table.py:257 |
| `queryfields` | table.py:261 |
| `logicalDeletionField` | table.py:224; model.py:402–415 (`checkAutoStatic` propagation) |
| `draftField` | table.py:230; model.py:402–415 |
| `noChangeMerge` | table.py:236 |
| `default_subtable` | set model.py:760, 762 |
| `group_subtables`, `group_<name>` | set model.py:785, 817 (group-label registry) |
| `partition_*` | model.py:725 (excluded from subtable attribute copy) |
| `fullname`, `pkg` | set model.py:666–667; read model.py:1102, 1200; column ext/localized hooks model.py:945 |
| `tag` | model.py:685 (subtable dispatch) |
| `mixin` | obj.py:59–63 (per-node mixin: `'module:Class'` or class name relative to `self.module`) |
| `comment`, `name_short`, `name_long`, `name_full` | obj.py:106–128 |

### 2.3 Column node attributes (physical columns)

Physical / SQL:

| Attribute | Read at |
|---|---|
| `dtype` | columns.py:48 (default `'T'`); doInit default: `size`→`'A'` else `'T'` (columns.py:118–122); model.py:1117 |
| `size` | columns.py:120; model.py:318–323 (relation size check); `':64'` min:max syntax seen at model.py:727 |
| `default` | set model.py:927 |
| `notnull` | set model.py:927 |
| `unique` | columns.py:234 (registers `_indexedColumn`) |
| `indexed` | columns.py:233 |
| `sqlname` | columns.py:210 (base of localized name computation) |
| `localized` | columns.py:211 (runtime suffix `_<current_language>`, columns.py:211–216) |
| `sql_value` | set model.py:747 (SQL literal instead of stored value — subtable discriminator) |
| `sql_inherited` | set model.py:732, 748 (column inherited from maintable, no DDL) |

Semantic / application metadata:

| Attribute | Read at |
|---|---|
| `group` | columns.py:54 (`isReserved` = group startswith `'_'`); model.py:1362 |
| `one_group` | set model.py:1366 |
| `colgroup_label`, `colgroup_name_long` | set model.py:830–833 |
| `name_short`, `name_long`, `name_full`, `comment` | obj.py:106–128; model.py:275–277 |
| `readonly` | columns.py:60 (string flag: `'Y'`/`'N'`) |
| `encrypted` | columns.py:66, 123–125 (`True`→`'R'`; modes `'R'`,`'Q'`,`'X'`) |
| `print_width` | columns.py:100–110 (lazily computed and cached into attributes) |
| `onInserting`, `onUpdating`, `onDeleting`, `onInserted`, `onUpdated`, `onDeleted` | columns.py:238–244 (field-trigger registration) |
| `trigger_table` | columns.py:237 (third element of trigger tuples) |
| `variant` | table.py:451 (comma-separated variant names) |
| `variant_<name>_<key>` | table.py:454–457 (`dictExtract` per variant) |
| `ext_<pkg>` (as extracted `ext_kwargs`) | model.py:934–942; the sliced key (package name) also lands as node attribute via `kwargs.update(ext_kwargs)` (model.py:922) |
| `_owner_package` | set model.py:119–122 (during `config_db_<pkg>` customization); read table.py:320–325 (`pluggedColumns`) |
| `mixin` | obj.py:59 |

### 2.4 Virtual-column node attributes

| Attribute | Read at |
|---|---|
| `virtual_column` (always `True`) | set model.py:1012; read table.py:563; columns.py:360 |
| `relation_path` | columns.py:288; table.py:541, 609, 629 |
| `sql_formula` | columns.py:306; set model.py:1128 |
| `select` | columns.py:312 |
| `exists` | columns.py:318 |
| `py_method` | columns.py:324 |
| `join_column` | columns.py:300; columns.py:276 |
| `composed_of` | columns.py:294; table.py:204, 392 |
| `static` | table.py:401 (`static_virtual_columns`, included in `starColumns`) |
| `virtual` | columns.py:337 (set `True` in `DbVirtualColumnObj.doInit` when a relation child exists, columns.py:273) |
| `subquery`, `subquery_aggr`, `select_nestedselect`, `format` (`'json_table'`) | set model.py:1205–1221 |
| `bagcolumn`, `itempath`, `var_calculated_path` | set model.py:1155–1157, helpers.py:74 |
| `_addClass`, `var_<k>` | set model.py:786–790 (subtable formula column) |
| `dtype` (`'JS'` for composite, `'B'` for subtable flag, `'A'` formula default) | model.py:1083, 787, 1230 |
| `variant`, `variant_kwargs` (sliced) | model.py:954, 1007 |

### 2.5 Relation node attributes (child of a column)

Set at model.py:1367–1376: `related_column`, `mode`, `one_name`, `many_name`, `one_one`, `child`, `one_group`, `many_group`, `deferred`, `onUpdate`, `onDelete`, `eager_one`, `eager_many`, `onUpdate_sql`, `onDelete_sql`, `relation_name`, `onDuplicate`, plus the open tail (`cnd`, `join_on`, `between`, `storename`, `storefield`, `external_relation`, `ignore_tenant`, `virtual`, `resolver_*`, `meta_*`, `inheritProtect`, `inheritLock`, ...). Read back verbatim in `DbColumnObj.doInit` (columns.py:225–232) / `DbVirtualColumnObj.doInit` (columns.py:270–284).

### 2.6 Index / subtable / table-alias node attributes

- Index: `columns`, `unique` (model.py:1309), `sqlname` (containers.py:146–149, default `'<table.sqlname>_<columns>_idx'`).
- Subtable: `condition`, `condition_<k>` (containers.py:73–85), `table`, `name_plural` (model.py:750–755).
- Table alias: `relation_path` (containers.py:45).

---

## 3. `DbModel.addRelation` (model.py:180–354) — full analysis

### 3.1 How a column declaration becomes a model relation

1. Grammar: `col.relation(related_column, ...)` stores a `relation` child node in the column's value (model.py:1367).
2. Compile: `DbColumnObj.doInit` (columns.py:220–232) reads `self.structnode.value['relation']`, copies its attributes to `reldict`, normalizes `related_column` to three-part form via `_fillRelatedColumn` (columns.py:153–168 — 2-part paths get the **current column's package** prepended), sets `reldict['mode'] = 'custom'` **iff `'cnd'` is present** (columns.py:229–230), and registers `self.dbroot.model._columnsWithRelations[(pkg, table, colname)] = reldict`.
   - Virtual variant (`DbVirtualColumnObj.doInit`, columns.py:266–284): additionally sets `self.attributes['virtual'] = True`, synthesizes `relation_path` for join columns, forces `reldict['virtual'] = True`, defaults `reldict['one_name'] = reldict.get('one_name') or self.name_long`.
3. Build tail (model.py:174–177): for each entry, `oneCol = relation.pop('related_column')`; `self.addRelation(many_relation_tuple, oneCol, **relation)`. Then `_columnsWithRelations.clear()` and `db.currentEnv.pop('_relations', None)` (invalidate the per-request relation-tree cache, model.py:178).

### 3.2 Signature (model.py:180–214)

```python
@extract_kwargs(resolver=True, meta=True)
def addRelation(self, many_relation_tuple, oneColumn, mode=None,
                storename=None, one_one=None, onDelete=None, onDelete_sql=None,
                onUpdate=None, onUpdate_sql=None, deferred=None,
                eager_one=None, eager_many=None, relation_name=None,
                one_name=None, many_name=None, one_group=None, many_group=None,
                many_order_by=None, storefield=None, external_relation=None,
                resolver_kwargs=None, inheritProtect=None, inheritLock=None,
                meta_kwargs=None, onDuplicate=None, between=None, cnd=None,
                join_on=None, virtual=None, ignore_tenant=None, **kwargs)
```

`resolver_*` kwargs collapse into `resolver_kwargs`; `meta_*` into `meta_kwargs`.

### 3.3 Body walkthrough

- **Everything is inside `try: ... except Exception:`** (l. 239, 346–354). On failure: re-raise only if `self.debug`, otherwise `logger.error('The relation %s - %s cannot be added: %s', ...)` and continue. This is the "missing tables" behavior — a relation pointing into a not-installed external package fails somewhere in the lookups (`self.obj[many_pkg]` at l. 257, or the `.column(...)` calls) and is **silently dropped in production**. The inline REVIEW comment (l. 236–238) flags the breadth of the except.
- Endpoint decomposition (l. 240–243): `many_pkg, many_table, many_field = many_relation_tuple`; `one_pkg, one_table, one_field = oneColumn.split('.')`.
- Guard (l. 244–249): if `many_field` or `one_field` is empty → warning `"pkg, table or field involved in the relation ... doesn't exist"` and **silent return**.
- **Naming defaults** (l. 250–253):
  - `private_relation = relation_name is None and one_one != '*'` — unnamed relations are "private" (excluded from the first pass of path discovery, table.py:825–826), unless one_one `'*'`.
  - `default_relation_name = many_table if one_one == '*' else '_'.join(many_relation_tuple)` — e.g. `fatt_fattura_testata_cliente_id`; `relation_name = relation_name or default_relation_name`.
- **Mode decoding** (l. 254–255): `case_insensitive = (mode == 'insensitive')`; `foreignkey = (mode == 'foreignkey')`. `mode='relation'` (the grammar default) yields both False — a purely logical join with no SQL FK constraint. (`mode='custom'` injected for `cnd` relations also yields both False.)
- **Tenant guard** (l. 258–261): `ignore_tenant is False` on a multi-tenant many-table → warning only.
- **Deferred default** (l. 262–263): `if deferred is None and (onDelete == 'setnull' or onDelete_sql == 'setnull'): deferred = True`.
- **Many side (`mode='O'`)** (l. 256, 264–288): key `many_relkey = '%s.%s.@%s' % (many_pkg, many_table, many_field)`. Duplicate key → `GnrSqlRelationError('Cannot add many relation ... exist another relation ...')`. Stored attrs: `mode='O'`, `many_relation`, `many_rel_name=many_name`, `foreignkey`, `many_order_by`, `relation_name`, `one_relation`, `one_rel_name = one_name or <many-side column>.attributes.get('name_long')` (l. 275–277 — display-name fallback taken from the FK column), `one_one`, `onDelete`, `onDelete_sql`, `onDuplicate`, `onUpdate`, `onUpdate_sql`, `deferred`, `case_insensitive`, `eager_one`, `eager_many`, `private_relation`, `external_relation`, `ignore_tenant`, `one_group`, `many_group`, `storefield`, `_storename=storename`, `between`, `cnd`, `join_on`, `virtual`, `resolver_kwargs`.
- **One side (`mode='M'`)** (l. 289–314): key `one_relkey = '%s.%s.@%s' % (one_pkg, one_table, relation_name)` — the inverse relation lives on the one-table under `@<relation_name>`. Duplicate → `GnrSqlRelationError("Same relation_name '<name>' in table <old.many_relation> and <many_relation>")` (global uniqueness of relation_name per one-table). Then `meta_kwargs.update(kwargs)` (l. 297) — leftover kwargs merge into meta and are stored **only on the M side** together with `inheritLock`, `inheritProtect` (also M-side only). M-side attrs otherwise mirror the O side but with `one_rel_name=one_name` raw (no fallback) and **without** `foreignkey`, `relation_name`, `resolver_kwargs`.
- **Index + size validation** (l. 315–336), skipped for `virtual` relations:
  - `checkRelationIndex(many_pkg, many_table, many_field)` and same for the one side (l. 316–317). `checkRelationIndex` (l. 356–374) injects a `DbIndexObj` named `'<table>_<column>_key'` directly into the compiled `tblobj.indexes.children` when the column is not the pkey and no such index exists — implicit index creation for every relation endpoint.
  - Size comparison of the two columns' `size` attributes; mismatch → `logger.warning('Different size in relation ...')` (l. 326–336).
- **Auto-static propagation** (l. 338–344): triggered when `(onDelete == 'cascade' and self.db.auto_static_enabled) or meta_kwargs.get('childmode')`. `checkAutoStatic` (l. 376–415) copies `draftField` and `logicalDeletionField` from the one-side table to the many-side table (when the parent defines them and the child does not): creates on the child `aliasColumn(one_sf, '@{many_field}.{one_sf}', name_long='!![en]{many_field} {one_sf}', group='zz', static=True)` and sets the system-field attribute on both the child's source node and compiled node (l. 399–415).
- **Dead code** (l. 269): `col_finder = self.column if not virtual else (lambda x: self.virtual_columns[x])` — never used afterwards, and `DbModel` has no `virtual_columns` attribute; would raise if the lambda were ever called.

### 3.4 `one_one`, `eager`, `groups`, case-insensitive, deferred — semantics as stored

- `one_one` is typed `str | None`; the only value given special treatment in these files is `'*'` (public one-to-one: relation label defaults to the bare `many_table`, `private_relation` False). Any value is passed through to both relation entries for downstream resolvers.
- `eager_one` / `eager_many` are pure pass-through flags on both sides (consumed by the relation resolvers/query layer, not here).
- `one_group` / `many_group` control UI grouping of the two relation directions; `one_group` may be auto-hoisted from the FK column's `group` (model.py:1362–1366).
- `case_insensitive` (`mode='insensitive'`) is stored on both sides; join generation elsewhere uses it for case-insensitive matching.
- `deferred` maps to the SQL deferred-constraint flag; auto-set for `setnull` deletes (l. 262–263); also surfaces in `DbTableObj.dependencies` (table.py:303–312) where a dependency counts as deferred if `deferred or onDelete == 'setnull'`.

---

## 4. Runtime model objects — what the framework depends on

### 4.1 `DbModelObj` base (obj.py:38–145)

- `init()` (obj.py:46–64): resolves `self._dbroot = self.root.rootparent.db`; applies registered mixins — `mixobj.mixin(self.db.model.mixins[mixpath], attributes='_plugins,_pluginId')` where `mixpath` comes from `_getMixinPath()` (`'pkg.<name>'` for packages, `'tbl.<pkg>.<table>'` for tables) and `mixobj` from `_getMixinObj()` (`self`, except `DbTableObj` returns the `SqlTable` proxy, table.py:105–107); a per-node `mixin` attribute (`'module:Class'`, or class name resolved against `self.module.__module__`) is also applied; then `doInit()`.
- Naming ladder: `name_short` → falls back to `name_long` → node name; `name_long` → falls back to `name_short`; `name_full` → falls back to `name_long` (obj.py:106–128). All three have setters writing into `attributes`.
- `sqlname` default `attributes.get('sqlname', self.name)` (obj.py:96–99); `adapted_sqlname = adapter.adaptSqlName(self.sqlname)` (obj.py:101–104).
- `getAttr(attr=None, dflt=None)` (obj.py:134–145); `getTag()` returns `sqlclass` (obj.py:130–132); `__bool__` always True (obj.py:82).

### 4.2 `DbPackageObj` (obj.py:148–238)

- `tables` → `self['tables'] or {}` ("temporary FIX", obj.py:159).
- `sqlname` → `attributes.get('sqlschema', attributes.get('sqlname', self.name))` (obj.py:165).
- `table(name)` raises `GnrSqlMissingTable` (obj.py:193–198); `dbtable(name)` returns the `SqlTable` proxy.
- `tableSqlName(tblobj)` (obj.py:200–218): `sqlprefix` falsy → bare name; `True` → `'<pkg>_<table>'`; string → `'<prefix>_<table>'`.
- `sqlschema` → `adapter.adaptSqlSchema(attributes.get('sqlschema', dbroot.main_schema))` (obj.py:220–226).
- `toJson()` (obj.py:228–238).

### 4.3 `DbTableObj` (table.py:48–913)

State installed in `doInit` (table.py:58–65): `_sqlnamemapper` (colname → adapted sqlname, filled by each `DbColumnObj.doInit`, columns.py:224), `_indexedColumn`, `_fieldTriggers`, `allcolumns`; wrapped in `dbtable.onIniting()` / `onInited()` hooks. `afterChildrenCreation` (table.py:67–81) guarantees the four child containers exist (`columns`, `indexes`, `virtual_columns`, `table_aliases`) and materializes `DbIndexObj`s from `_indexedColumn` with names `"<table>_<columns>_key"`.

Identity / SQL naming:
- `fullname` = `'<pkg>.<name>'` (table.py:134–138); `pkg` = `self.parent.parent` (table.py:128–132).
- `maintable` (cached in `_maintable`, table.py:111–118); `_refsqltable = self.maintable or self` (table.py:146–149) — **subtables borrow the main table's sqlname/sqlschema/multi_tenant**.
- `sqlschema` (table.py:151–163): tenant-aware — `currentEnv['tenant_schema']` overrides the static schema on multi-tenant tables; sentinel `'_main_'` forces the static schema.
- `sqlname` (table.py:165–172): explicit attr or `pkg.tableSqlName(...)`.
- `sqlfullname` (table.py:174–184): `'<adapted schema>.<adapted name>'` when the adapter has the SCHEMAS capability, else bare adapted name.
- `sqlnamemapper` property (table.py:186–189).

Pkey and system fields: `pkey` (attr, table.py:210–214); `pkeys` (table.py:191–208) — logs critical on missing pkey, raises `AssertionError` on a pkey attr pointing to a nonexistent column, expands **composite pkeys** through the pkey column's `composed_of`; `lastTS`, `logicalDeletionField`, `draftField`, `noChangeMerge`, `rowcaption` (fallback `$caption_field` → `$pkey`), `newrecord_caption`, `queryfields`, `name_plural` (table.py:216–263).

Column collections and resolution:
- `columns` = `self['columns']` (physical only, table.py:265–269); `indexes`; `table_aliases`.
- `virtual_columns` (table.py:358–384): **stateful property** — merges `self['virtual_columns']` with `db.localVirtualColumns(fullname)`, `dynamic_columns`, and variant columns, mutating `virtual_columns.children`, then caches the merged container in `currentEnv['_virtual_columns_<pkg>_<tbl>']`. Inline REVIEW flags the thread-safety race.
- `dynamic_columns` (table.py:404–427): scans the `SqlTable` proxy for `formulaColumn_*` methods; each returns a dict (or list of dicts) with a `name` key; converted to `virtual_column`-tagged Bag nodes.
- `_handle_variant_columns` (table.py:440–471): for every column (real + virtual) with `variant='<v1>,<v2>'`, calls `dbtable.variantColumn_<variant>(colname, **dictExtract(colattr, 'variant_<variant>_'))` and injects the returned defs as virtual columns.
- `full_virtual_columns` (table.py:429–438): adds `db.customVirtualColumns(fullname)` on top.
- `composite_columns` / `static_virtual_columns` (table.py:386–402): filtered Bags on `composed_of` / `static`.
- `getVirtualColumn(fld, sqlparams=None)` (table.py:329–356): unknown names may be defined on the fly from `sqlparams[fld]` (a dict with a `field` key naming the base VC); deep-copies the base structnode, relabels it, overlays the params, and wraps in a fresh `DbVirtualColumnObj` — per-query parametrized virtual columns.
- `column(name)` (table.py:514–565): strips `$`; physical hit wins; then virtual: dispatch order is `virtual` flag → `relation_path` (name is replaced by the path and falls through to `@` handling) → `sql_formula`/`select`/`exists` → `join_column` → `composed_of` → `py_method` → raise `GnrSqlMissingColumn('Invalid column ...')`. `@`-paths go to `_relatedColumn`; when both an alias VC and an `@`-path resolution exist, returns `AliasColumnWrapper(relcol, colalias.attributes)` (after asserting `'virtual_column' in colalias.attributes`, else `GnrSqlException('Col alias must be virtual_column')`).
- `_relatedColumn(fieldpath)` (table.py:567–597): resolves the first `@segment` through `self.relations` (joiner-based hop to the O- or M-side table) or through `table_aliases` (path splice), recursing on the remainder; raises `GnrSqlMissingField`.
- `virtualColumnAttributes(name)` (table.py:599–613): for alias VCs, merges the target column's attributes under the alias's own.
- `fullRelationPath(name)` / `resolveRelationPath(relpath)` (table.py:615–681): recursively expand alias columns and table aliases to a canonical `@rel.@rel...field` path; `resolveRelationPath` raises `GnrSqlRelationError` on unknown segments.

Relations:
- `relations` (table.py:277–295): builds a `RelationTreeResolver` (`newRelationResolver(cacheTime=-1)()`, table.py:83–100) and caches per-request in `currentEnv['_relations'][fullname]`. The resolved tree's nodes carry a `joiner` attr dict (with keys observed here: `mode` `'O'|'M'`, `many_relation`, `one_relation`, `onDelete`, `onDelete_sql`, `deferred`, `foreignkey`, ...).
- `relations_one` / `relations_many` (table.py:685–709): digest-based Bags of O-mode / M-mode joiners; `relatingColumns` (table.py:711–715) = list of FK paths pointing at this table.
- `getRelation(relpath)` → `{'many': ..., 'one': ...}`; `getRelationBlock(relpath)` → `dict(mode, mpkg, mtbl, mfld, opkg, otbl, ofld)` (table.py:717–742).
- `getJoiner(related_table)` (table.py:754–777): searches this table's relations for a joiner whose `one_relation` is the related table's pkey column, then the reverse direction.
- `getTableJoinerPath(table, deepLimit=5, eager=False)` (table.py:779–856): iterative-deepening search over `db.model.relations(currtable)`, first pass skipping `private_relation` entries, second pass including them; returns lists of joiner-attr dicts augmented with `relpath` and `table`.
- `manyRelationsList(cascadeOnly=False)` → `(table, fkey)` tuples; `oneRelationsList(foreignkeyOnly=False)` → `(table, pkey, fkey)` tuples (table.py:858–895).
- `dependencies` (table.py:302–312): `(reltable, deferred)` for FK relations, self-references excluded.

Misc: `pluggedColumns(packages=None)` via `_owner_package` (table.py:314–325); `starColumns(bagFields=False)` — all physical columns (excluding dtype `'X'` unless `bagFields`) **plus all static virtual columns** as `$name` tokens (table.py:479–491); `getColPermissions` → `user_*`-prefixed dict from user configuration (table.py:493–502); `subtable(name)` lookup (table.py:504–510); `toJson()` (table.py:897–913).

### 4.4 `DbColumnObj` (columns.py:194–252)

- `sqlname` (columns.py:203–218): localized columns resolve to `'<base>_<current_language>'` when `currentEnv['current_language']` differs from `dbroot.default_language` — **per-request SQL name switching**.
- `doInit` (columns.py:220–244): fills `table.sqlnamemapper`; harvests the relation child into `model._columnsWithRelations` (see 3.1); registers `_indexedColumn` entries for `indexed`/`unique`; registers field triggers — for each of `onInserting, onUpdating, onDeleting, onInserted, onUpdated, onDeleted` appends `(colname, trigFunc, trigger_table)` to `table._fieldTriggers[trigType]`.
- `_captureChildren` (columns.py:199–201): returns False (relation child kept as `self.column_relation`, no child objects built).
- `rename(newname)` → `db.adapter.renameColumn(...)` (columns.py:246–252).
- Inherited from `DbBaseColumnObj` (columns.py:38–191): `dtype` (default `'T'`), `isReserved` (group startswith `_`), `readonly` (`'Y'` flag), `encrypted`, `pkg`, `table`, `sqlfullname` (`'<table.sqlfullname>.<sqlname>'`), `fullname` (`'<pkg.table>.<name>'`), `print_width` (lazy, mutating getter), `getPermissions`, `toJson`, `relatedTable()` / `relatedColumn()` / `relatedColumnJoiner()` (joiner looked up as `table.relations.getAttr('@'+name)` and verified against `fullname`, columns.py:182–191), `doInit` dtype defaulting + `custom_type_<dtype>` package hook that **replaces** the attributes dict with the mixin-merged one (columns.py:116–133).

### 4.5 `DbVirtualColumnObj` (columns.py:255–337)

Exposes as properties: `relation_path`, `composed_of`, `join_column`, `sql_formula`, `select`, `exists`, `py_method`, `virtual` (default False), and hard-overrides `readonly → True` (columns.py:328–332). `doInit` handles relation-bearing VCs (see 3.1) including the join-column `relation_path` synthesis.

### 4.6 `AliasColumnWrapper` (columns.py:340–367)

- Constructor merges `dict(originalColumn.attributes)` with the alias attributes (alias wins), pops `tag` and `relation_path` **without defaults** (REVIEW comment flags the KeyError risk, columns.py:354–358), stores `relation_path` as an instance attr, promotes `sqlclass='virtual_column'` if the merged attrs contained `virtual_column`; `__getattr__` delegates everything else to `originalColumn` (columns.py:366–367).

### 4.7 Containers (containers.py)

- `DbTableAliasObj.relation_path` (containers.py:43–47) — consumed by `_relatedColumn` / `fullRelationPath` / `resolveRelationPath` at runtime; note the node labels are `@`-prefixed (model.py:1279).
- `DbSubtableObj.getCondition(sqlparams)` (containers.py:61–85): pulls `condition` and `condition_*` from node attributes; each param with value not in `('*', None)` is renamed `:k` → `:subtable_condition_k` via regex and written into `sqlparams` — `'*'` acts as a wildcard that leaves the placeholder unbound.
- `DbIndexObj.sqlname` default `'%s_%s_idx' % (table.sqlname, columns.replace(',', '_'))` (containers.py:141–151); `table = self.parent.parent`.
- List containers are empty classes whose `sqlclass` strings double as source tags (containers.py:88–133).

---

## 5. Oddities and design notes (rewrite decision points)

1. **Deferred building is LIFO.** `runOnBuildingCb` drains with `self.onBuildingCb.pop()` (model.py:92–94) — callbacks run in reverse registration order. Only current client is `compositeColumn`; a rewrite should decide FIFO vs LIFO explicitly.
2. **Two-phase relation wiring with in-flight mutation.** Relations are harvested during object construction (`doInit` → `_columnsWithRelations`) and wired after `makeRoot` (model.py:174–177); `build()` also clears `self.relations` and pops the `currentEnv['_relations']` cache (model.py:170–178), implying rebuildability is a requirement.
3. **`name::dtype` shorthand is inconsistent**: honored in `column` (model.py:900–901), silently discarded in `virtual_column` (model.py:989–990) and `aliasTable` (model.py:1274–1275) — the split dtype is never used.
4. **Dead/broken `col_finder`** in `addRelation` (model.py:269) referencing nonexistent `self.virtual_columns`.
5. **`table()` drops declared `sqlname`/`sqlschema` params** — they are in the signature (model.py:636–637) but absent from the `child()` attribute list (model.py:663–668); the runtime fallbacks (`pkg.tableSqlName`, pkg schema) are what actually govern naming unless the attribute is set some other way (e.g. XML load or kwargs on other paths).
6. **`DbBaseColumnObj._get_sqlschema` returns a tuple**: `return 'sqlschema', self.table.sqlschema` (columns.py:82–86) — a latent bug; the property yields `('sqlschema', <schema>)`.
7. **Property getters with side effects**: `print_width` writes into `attributes` on first read (columns.py:103–108); `virtual_columns` mutates children and `currentEnv` (table.py:358–384, REVIEW notes the race); `relations` caches into `currentEnv`.
8. **`column()` over an existing virtual column mutates the VC instead of creating the physical column** (model.py:911–920), merging only a non-None subset — `size`, `default`, `notnull`, `sqlname`, triggers are silently lost in that path. Order of declaration matters.
9. **`relation()` mutates the FK column's `group`** (model.py:1362–1366) — declaring a relation hides the column (`group='_'`) and hoists the group to `one_group`.
10. **`addRelation` swallows all exceptions in production** (model.py:346–354). This doubles as the external-package mechanism (relations into absent packages just log an error) and as a bug-hider. The `external_relation` flag is stored but the tolerance is implemented by the bare except, not by the flag.
11. **Implicit index creation** on both endpoints of every non-virtual relation (`checkRelationIndex`, model.py:356–374), injected directly into the **compiled** tree, named `<table>_<column>_key`. Meanwhile grammar `index()` labels default to `<table>_<columns>_key` and `DbIndexObj.sqlname` defaults to `<sqlname>_<columns>_idx` — three naming conventions in play.
12. **Asymmetric relation entries**: `foreignkey`, `relation_name`, `resolver_kwargs` only on the O side; `inheritLock`, `inheritProtect` and the merged `meta_kwargs`+leftover kwargs only on the M side (model.py:270–314). `one_rel_name` on the O side falls back to the FK column's `name_long`; on the M side it stays raw.
13. **`relation_name` global uniqueness per one-table** enforced with `GnrSqlRelationError` (model.py:291–296); default name `'_'.join((pkg, table, column))`, but bare `many_table` when `one_one == '*'`; `private_relation` derived from "no explicit name given" (model.py:251) and consumed by path discovery (table.py:825).
14. **Mode is a string multiplex**: `'relation'` (logical join only), `'foreignkey'` (SQL constraint), `'insensitive'` (case-insensitive join), plus `'custom'` injected automatically when a `cnd` attribute exists (columns.py:229–230). A rewrite should make these orthogonal flags.
15. **`one_one` is a string** whose only special value in this layer is `'*'`; its truthiness semantics live downstream.
16. **Mixin config protocol** (model.py:119–169): table mixins applied in sorted table-name order; `config_db(pkgsrc)`, then per-installed-package `config_db_<pkg>(pkgsrc)` wrapped in a subscribe/unsubscribe that stamps `_owner_package` on every inserted column node (basis of `pluggedColumns`), then `config_db_custom(pkgsrc)`; package mixins may also register `onBuildingDbobj` callbacks executed before `runOnBuildingCb`. Mixins are frozen after startup (`ConfigureAfterStartError`, model.py:488–500). Runtime object mixins are re-applied per node in `DbModelObj.init` with `attributes='_plugins,_pluginId'` plus the per-node `mixin` attribute.
17. **`custom_type_<dtype>` package hook replaces the whole attribute dict** of a column (columns.py:126–133): the mixin's attrs become the base and the declared attrs override — dtype itself is taken from the mixin. Custom dtypes are thus package-defined macros.
18. **System-field propagation (`checkAutoStatic`)** is the closest thing to `_sysfields` in this package (no identifier named `_sysfields` exists in these six files): cascade/childmode relations copy `draftField`/`logicalDeletionField` down as static alias columns with `group='zz'` (model.py:376–415), gated by `db.auto_static_enabled`.
19. **`auto_static_enabled` also changes `virtual_column` semantics** (hot-insertion into the compiled model, model.py:1014–1023) — the same flag toggles two unrelated behaviors.
20. **Localization is stringly typed end-to-end**: `localized=True` resolves against `db.extra_kw['languages']` only if it contains a comma (model.py:905–910); the physical effect is delegated to the package's `handleLocalizedColumn`; reads are redirected per request in `DbColumnObj.sqlname` (columns.py:203–216).
21. **Variant machinery spans both trees**: declared as `variant='a,b'` + `variant_a_x=...` attrs (kept **with** prefix by `slice_prefix=False`), expanded lazily by `_handle_variant_columns` calling `dbtable.variantColumn_<name>(colname, **kwargs)` (table.py:440–471). Contrast: `virtual_column` slices the prefix (model.py:954) — two different conventions on the same concept.
22. **The subtable double meaning** (package-level = single-table inheritance with `__subtable` discriminator, `sql_value` literal columns, `sql_inherited` flags, `_main` pseudo-subtable, `default_subtable`; table-level = named filter + auto-generated boolean `subtable_<name>` formula column) shares one grammar word dispatched on the node tag (model.py:671–688).
23. **PostgreSQL leakage in the grammar layer**: `xpath`/CAST type map (helpers.py:71–86, REVIEW comment present), `json_agg`/`row_to_json`/`xmlagg`/`xmlforest` (model.py:1201–1215), SQL `format()` producing **HTML** (helpers.py:110–123), and the `#nestedselect` placeholder convention.
24. **`compositeColumn` emits `dtype='JS'`** and a hand-built JSON-array text formula with `\:\:dtype` typed-value escapes (model.py:1117–1126) — composite pkeys ride on this via `pkeys` expansion (table.py:204–206).
25. **Colgroup ordinals** are assigned from container length at declaration time (`f'{name}.{len(destination)+1:03}'`, model.py:829) — group ordering is declaration-order-dependent and capped at 3 digits.
26. **`_captureChildren` asymmetry**: physical columns never build child objects (returns False, columns.py:199–201); virtual columns build them unless a relation child exists (columns.py:260–264).
27. **`externalPackage`** returns the root struct called with a path (model.py:627) — cross-package table extension relies on shared mutable source trees and build ordering.
28. **`related_table` parameter of `relation()` is accepted and ignored** (model.py:1314, 1343) — backward-compat noise a rewrite can drop.
29. **`DbPackageObj._get_tables` has an `or {}` marked "temporary FIX"** (obj.py:159); `DbTableObj.toJson` filters virtual columns whose names start with `__` (table.py:910).
30. **Name property ladder** (`name_short` ⇄ `name_long` → `name_full`, obj.py:106–128) is bidirectionally defaulted — a rewrite must pick a single canonical display-name story.

---

## Riferimenti

- Session: `ce254e4b-4c8c-49ae-a635-12536130ad35` (2026-07-06)
- Legacy source: `/Users/gporcari/Sviluppo/Genropy/genropy/worktrees/develop/gnrpy/gnr/sql/gnrsqlmodel/` @ `83c138bb6`
