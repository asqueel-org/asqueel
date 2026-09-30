# Query Language — Legacy Analysis & Reform Proposals

**Version**: 0.1.0 · **Date**: 2026-07-11 · **Status**: 🔴 DA REVISIONARE

Part of the asqueel design documentation set (see `00_INDEX.md`).
Purpose: an exhaustive, verified inventory of the legacy GenroPy
query-language options, the 2026 compiler experiments, and reform
proposals for the new query grammar — so the project owner can decide
the new language keeping the best of the legacy.

The new query representation is a **genro-builders grammar** (a tree of
`@element` nodes — the "Genro query AST"), with full-SQL constructs and
Genro semantic primitives both first-class citizens of the same tree.
Those design decisions are GIVEN (see `05_grammar_design.md` and the
constraints in §1.4 of this doc); this document builds proposals **on**
them, it does not re-litigate them.

---

## 1. Scope and sources

### 1.1 What this document covers

1. The legacy query **surface** users actually write: column specs,
   the structured WHERE (the `op_*` vocabulary), parameters/env,
   relation-path→JOIN resolution, structural clauses, macros, and
   subqueries (§2).
2. The Feb–Mar 2026 compiler **experiments** in genropy — in particular
   `SqlCompoundQuery` and the `+`/`-`/`&`/`|` operator composition of
   queries (§3).
3. **Reform proposals**: per legacy option (keep / reform / absorb /
   drop) and the new AST-enabled capabilities, with authoring examples
   and migration notes (§4).
4. **Open questions** for the owner (§5).

### 1.2 Two legacy layers, one pipeline

The legacy query language is **two cooperating layers**, and the reform
must treat them together:

- **The compiler layer** (`gnrsqldata/`) — a *string-oriented* language:
  `columns`, `where`, `order_by`, `group_by`, `having` are **strings**
  containing `$col`, `@rel.col`, `:param`, `#MACRO(...)`. Inventoried
  in `02_legacy_compiler_query.md`; source
  `gnrpy/gnr/sql/gnrsqldata/compiler.py` (1512 lines).
- **The structured-WHERE layer** (`GnrWhereTranslator`, in the adapter)
  — a *Bag-of-conditions* language: each condition carries `column`,
  `op` (from the `op_*` vocabulary), `value`, `jc` (and/or), `not`;
  groups nest. `GnrWhereTranslator.__call__` renders the Bag into a SQL
  WHERE **string**, which is then fed as `where=` into the compiler.
  Source `gnrpy/gnr/sql/adapters/_gnrbaseadapter.py:1265-1628`.

So today the structured layer *compiles down to* the string layer. The
new AST unifies both: WHERE is a structured, recursive citizen of the
same tree as SELECT/FROM/JOIN.

### 1.3 Source of truth

All file:line citations are verified in the Genropy `develop` worktree
`/Users/gporcari/Sviluppo/Genropy/genropy/worktrees/develop/gnrpy/gnr/`
@ `83c138bb6`, except §3 which cites the genropy branch
`feature/compound_query` (unmerged). `§` citations point at the roadmap
docs in this directory.

### 1.4 GIVEN design constraints (not questioned here)

- New query representation = a genro-builders `@element` tree (SOURCE
  tree), not the ANSI SQL AST alone.
- First-class full-SQL: UNION/INTERSECT/EXCEPT (recursive), WITH/CTE
  (incl. recursive), window functions (OVER/PARTITION BY/frame/FILTER),
  GROUPING SETS/ROLLUP/CUBE, LATERAL, VALUES, DISTINCT ON, FETCH/OFFSET,
  FOR UPDATE/SKIP LOCKED, structured CASE/CAST, EXISTS/IN/ANY/ALL.
- First-class Genro primitives inside ANY construct: (a) relation path
  stored as-is, never pre-lowered; (b) structured WHERE (column-or-path,
  semantic `op_*` operator, typed term: constant | `:param` | column/
  path | escape-hatch expr), grouped by `and_`/`or_` with negation,
  recursive; (c) `:param` and env as typed citizens.
- Two forms: SOURCE tree (Genro primitives) → model-aware compile →
  LOWERED tree (pure SQL) → per-backend renderer. SOURCE is what is
  saved. Raw-SQL string is a declared escape hatch, never the default.
- A textual-SQL reader may lean on `sqlglot` (optional dep) — mentioned,
  not designed here.
- Two MODEL dialects (legacy / modern); the query grammar is separate
  but must play with both; the compiler resolves relation paths against
  the model tree.

---

## 2. Legacy query language — exhaustive option inventory

### 2.a Column spec

The `columns` argument is a string of comma-separated column
expressions. Normalized (`'  '→' '`, `'\n'→''`, `' as '→' AS '`,
`' ,'→','`) at `compiler.py:917-920`.

| Option | Syntax (verbatim) | Where | Assessment |
|---|---|---|---|
| Physical/virtual column | `$column` | `COLFINDER = re.compile(r"(\W|^)\$(\w+)")` `compiler.py:49` | Core. Strong. `$` prefix is load-bearing (distinguishes a column ref from a SQL keyword). |
| Related column (multi-hop) | `@rel.column`, `@rel.@rel2.column` | `RELFINDER = re.compile(r"([^A-Za-z0-9_]|^)(\@(\w[\w.@:]+))")` `compiler.py:50` | Core, unique to Genro. Char class `[\w.@:]` allows chained `@` and `:`. Drives JOIN generation (§2.d). Strong. |
| Explicit alias | `expr AS alias` | `' as '` normalized to `' AS '` `compiler.py:919`; recorded in `cpl.aliasDict` `:1018` | Standard SQL. Keep. |
| All main columns | `*` | `starColumns(bagFields)` `table.py:479-491` | Includes static virtual columns; excludes Bag (`dtype='X'`) unless `bagFields=True`. Keep as a projection helper. |
| Prefixed glob | `*prefix_` | `expandMultipleColumns` `compiler.py:744-800` | Niche. Keep as sugar. |
| Related glob | `*@rel1.@rel2`, `*@rel.prefix_` | same | **Zero production usage — deprecation candidate (#623)** per `07_legacy_compiler_experiments.md` §2. |
| Explicit related list | `*@rel.(col1,col2,…)` | `compiler.py:784-796`; also fills `cpl.aggregateDict` | Populates post-fetch aggregation metadata. Quirky (couples projection with aggregation). |
| Virtual-column glob source | `*<virtualcolname>` | `compiler.py:770-773` | If the token names a VC, its `sql_formula` is the expansion source. Obscure. |
| Aggregate (implicit) | `sum(...)`, `count(...)` in a column | regex `re.search("(sum|count) *?\(", col, re.I)` `compiler.py:1004` flips `aggregate=True` | **Misses `avg/min/max/array_agg/…`** (REVIEW, `02` §6). Weak — a real quirk to fix. |
| Storename sentinel | `_STORENAME_` | `compiler.py:921-923` | Multi-store injection; **move out of the compiler (#624)**. |

**Virtual columns consumed as columns.** A `$vc` or `@rel.vc` reference
in the columns spec dispatches through `getFieldAlias`
(`compiler.py:366-451`) into the virtual-column family declared in the
model (`01_legacy_model_grammar.md` §1.7–1.15):

- **aliasColumn / relation_path** (`01` §1.8): recurses on
  `fldalias.relation_path` → resolves like a plain `@path`
  (`compiler.py:373-377`).
- **formulaColumn** (`01` §1.14): `sql_formula` string spliced in,
  after the macro/field pipeline (`compiler.py:390-439`).
- **subQueryColumn** (`01` §1.13): three modes — `mode='json'` →
  `SELECT json_agg(row_to_json(...)) FROM #nestedselect`; `mode='xml'`
  → `xmlagg(xmlelement(...))`; **scalar/aggregate** → `select=query,
  subquery_aggr=mode` (a correlated sub-select). Compiled by recursive
  `db.queryCompile` at the `#nestedselect`/`select_*` substitution point
  (`compiler.py:404-419`; `model.py:1179-1222`). PG-specific SQL is
  generated in the **model** (leakage — `01` §5.23, design q7).
- **pyColumn** (`01` §1.15): emits `'NULL'` in SQL, registers a Python
  post-fetch handler (`compiler.py:440-445`); computed row-by-row in
  `handlePyColumns` (`query.py:257-279`).
- **compositeColumn** (`01` §1.10): `dtype='JS'`, a hand-built
  JSON-array text formula; composite pkeys ride on it.
- **bagItemColumn / toolColumn** (`01` §1.11-1.12): PG-specific
  `xpath`/`format()` HTML-in-SQL formula columns.

There is **no `addColumn`/RuntimeColumns in `develop`** — `RuntimeColumns`
is an unmerged experiment (`07` §2, PR #542 open). *Not present in the
shipped legacy.*

### 2.b WHERE / conditions

Two ways to author a WHERE:

**(1) As a string** fed to `compiler.compiledQuery(where=...)`. It goes
through the macro pass (`IN_RANGE`, `PERIOD`, `TSQUERY/VECQUERY`,
`compiler.py:959-962`), `embedFieldPars`, `updateFieldDict`, then
`templateReplace`. Users write raw SQL predicates with `$col`/`@rel`/
`:param` tokens. This is the escape-hatch-heavy path.

**(2) As a structured Bag of conditions** via `GnrWhereTranslator`
(`_gnrbaseadapter.py:1265-1628`) — the query-panel language. Node
shape (docstring `:1366-1371`, verbatim):

```
<condition column="fattura_num" op="ISNULL" rem='senza fattura' />
<condition column="@anagrafica.provincia" op="IN" jc='AND'>MI,FI,TO</condition>
<group not="true::B" jc='AND'>
        <condition column="" op=""/>
        <condition column="" op="" jc='OR'/>
</group>
```

Per-node attributes read (`innerFromBag`, `:1365-1421`): `column`
(a `$col` or `@rel.col` path — same syntax as §2.a), `op` (the operator
name, §below), `value` (node value; `?name` indirects into `sqlArgs`,
`:1377-1378`), `jc` (join connector, uppercased — `AND`/`OR`,
`:1379`; blank on the first node), `not` (`'not'` → wraps `NOT (...)`,
`:1382,1418-1419`), `parname` (explicit bind-param name, else derived
from the column path with collision suffixing `:1390-1397`),
`encrypted` (mode `'Q'` encrypts the value before binding,
`:1408-1414`). A **Bag-valued node is a nested group** → recursion
wrapped in `(...)` (`:1383-1385`). Empty `op`/`column` lines are
silently skipped (`:1398-1400`).

**The `op_*` operator vocabulary** — the full list. Base translator
`GnrWhereTranslator` (`_gnrbaseadapter.py`); each method's docstring is
the localizable caption (`opCaption`, `:1279-1286`):

| `op` | Method:line | Rendered SQL (semantics) |
|---|---|---|
| `startswithchars` | `:1504` | `col LIKE :v || '%'` (case-sensitive prefix) |
| `equal` | `:1508` | `col = :v`; a **list value auto-promotes to `in`** (`:1441-1442`) |
| `startswith` | `:1512` | `col ILIKE :v || '%'` (case-insensitive prefix) |
| `wordstart` | `:1516` | `col ~* '(^|\W)' || :v` (word-boundary regex; parens/brackets escaped) |
| `contains` | `:1521` | `col ILIKE '%' || :v || '%'` |
| `fulltext` | `:1526` | `#TSQUERY(<tsvColumn>,:v,<tsvLanguage>)` (PG full-text; reads column attrs) |
| `greater` | `:1532` | `col > :v` |
| `greatereq` | `:1536` | `col >= :v` |
| `less` | `:1540` | `col < :v` |
| `lesseq` | `:1544` | `col <= :v` |
| `between` | `:1548` | `col BETWEEN :v_from AND :v_to` (value split on `;`; **inclusive**) |
| `isnull` | `:1555` | `col IS NULL` |
| `istrue` | `:1559` | `col IS TRUE` |
| `isfalse` | `:1563` | `col IS FALSE` |
| `nullorempty` | `:1567` | `col IS NULL OR col = ''` (numeric dtypes → `isnull`) |
| `in` | `:1574` | `col IN :v` (string split on comma; list expanded by `adaptTupleListSet`) |
| `regex` | `:1581` | `col ~* :v` (case-insensitive POSIX regex) |
| `similar` | `_gnrbasepostgresadapter.py:1329` | PG-only `op_similar` (SIMILAR TO), in `GnrWhereTranslatorPG` |

That is **17 base operators + 1 PG operator = 18**. Adapter subclasses
**override** `startswith`/`contains`/`startswithchars`/`wordstart`/
`equal` for dialect quoting (`gnrmysql.py:449,453`; `gnrmssql.py:473,477`;
`gnrdb2_400.py:441,445`; `gnrfourd.py:366-383`) — same vocabulary,
different rendering. `op_similar` is the only *additional* operator, and
it is PG-only.

**Negation** — two mechanisms: (a) the `not` node attribute →
`NOT (cond)` (`:1418-1419`); (b) the `not_` key suffix in
`whereFromDict` (`:1606-1608`) and the `not_<op>` caption fallback
(`:1281-1282`). There is no `op_not_*` method — negation is structural.

**Referenced-but-unimplemented ops**: `notcontains` and `endswith`
appear only in the dtype-CAST guard list (`:1436-1437`); **no
`op_notcontains`/`op_endswith` handler exists in the base translator**
(verified: `grep def op_endswith/op_notcontains` → none). They would
have to be supplied via `customOpCbDict` (`:1447-1449`). *Not verified*
whether any dialect or caller registers them.

**dtype-aware rendering** (`prepareCondition`, `:1426-1450`):

- `column` auto-prefixed with `$` if bare (`:1429-1430`).
- Dates (`D`/`DH`/`DHZ`): `decodeDates` (`:1452-1492`) interprets Genro
  period strings (`decodeDatePeriod`) and **rewrites the operator**
  (`;value`→`lesseq`, `value;`→`greatereq`, `a;b`→`between`, single→
  `equal`); `DH`/`DHZ` wrap the column in `date(col)` (`:1434-1435`).
- Text operators on non-text dtypes → `CAST(col AS text)` and dtype
  coerced to `'A'` (`:1436-1440`).
- `unaccentTpl` (`:1586-1591`): if the column carries an `unaccent`
  attribute, wraps both sides in `unaccent(...)`.
- Encryption mode `'Q'` (deterministic) encrypts the value before
  binding (`:1408-1414`).
- Value typing: `storeArgs` (`:1494-1502`) converts non-text values via
  `catalog.fromText(v, dtype)` and registers the bind param.

**ILIKE / case-insensitivity** is baked into `startswith`/`contains`
(PG `ILIKE`); SQLite repairs `ILIKE→LIKE` and `~*→REGEXP` at runtime in
`prepareSqlText` (`gnrsqlite.py:111-128`, per `02` §7.3).

**value-is-field** (`checkValueIsField`, `:1423-1424`): a value starting
with `$` or `@` is treated as a **column/relation reference**, not a
literal — comparison against another column/path. Bind-param typing and
date decoding are skipped for such values.

### 2.c Parameters and environment

| Option | Syntax | Where | Notes |
|---|---|---|---|
| Named bind param | `:param` | adapter `paramstyle='named'` `_gnrbaseadapter.py:156` | list/tuple/set expanded to `(:k0,:k1,…)` by `adaptTupleListSet` `:208-219`. |
| kwargs → params | `query(..., foo=1)` | `SqlQuery.__init__` merges `**kwargs` into `sqlparams` `query.py:162` | Arbitrary bind values by keyword. |
| Param→field switch | value of `:param` is a `$col`/`@rel` string | `embedFieldPars` `compiler.py:802-829` | **Silently rewrites** the param into a field ref in the SQL. Injection-adjacent; a rewrite must make this explicit (`02` §6). |
| `#ENV(name[,fallback])` | macro | closure `expandEnv` `compiler.py:322-350` | Reads `db.currentEnv`; **only inside `sql_formula`**, never a plain WHERE. **Zero usage — deprecate for `:env_*` (#618)**. |
| `#PREF(path[,dflt])` | macro | `expandPref` `compiler.py:316-320` | `pkg.getPreference`; only inside `sql_formula`. |
| `env_*_condition_*` | implicit predicate | `dictExtract(currentEnv, 'env_%s_condition_'...)` `compiler.py:964-990` | Per-table WHERE injected from ambient env. |
| `var_` pseudo-macro | formula col attrs | `compiler.py:427-434` | `var_<k>` attrs stashed in `currentEnv`, `:k` rewritten to `:env_<newkey>`. |

Compilation is therefore **not pure**: `sqlparams` and `currentEnv` are
mutated during compile (`#PERIOD` adds `_from`/`_to`; TSQUERY channel
params; `var_` values). Identical inputs → different SQL under different
env/locale (`02` §6). A rewrite must decide the purity contract.

### 2.d Relation-path resolution → JOINs

The signature mechanism of the Genro query language. A `@rel.col` path in
any clause is resolved by `getFieldAlias` (`compiler.py:273-454`), which
pops relation segments and calls `_findRelationAlias`/`_getRelationAlias`
(`:456-668`), building JOINs as a **side effect**.

- **Alias allocation**: `t0, t1, …` (`aliasCode`, `:241-250`); the main
  table is `t0`.
- **Memoization**: a re-traversed hop reuses its alias (key
  `tuple(newpath+[basealias])`, `:544-549`).
- **Direction** from the joiner dict: `mode=='O'` (toward the one side,
  FK lookup) vs many side (`:557-569`).
- **ON-condition flavours**, in priority order (`:576-655`):
  `join_on` → `cnd` (explicit expr, `#IN_RANGE` expanded) → `between`
  (legacy triple, half-open `<`) → `case_insensitive=='Y'` →
  `lower(a)=lower(b)` (`:629`) → standard/composite FK
  (`composed_of` zipped pairwise; mismatch raises
  `GnrSqlException('...multikey works only with compositeColumns')`) →
  `virtual` (`($from)=alias.target`).
- **Always `LEFT JOIN`** (`:660`) — **no INNER path anywhere**;
  multiplicity is countered by auto-DISTINCT (§2.e), not by join type
  (`02` §6).
- **one_one** demotes a many join to non-exploding (`:649-657`).
- **Exploding tracking**: many-side joins set `_explodingRows`, feeding
  auto-DISTINCT.
- **Table aliases** (`aliasTable`, `01` §1.16): pure path rewrites —
  their `relation_path` is prepended to the remaining pathlist, no alias
  of their own (`:488-491`). **Undocumented/untested — evaluate (#616)**.
- **Paths on virtual columns**: alias VCs recurse; formula VCs resolve
  their refs relative to the formula's own table/alias (`#THIS`,
  `compiler.py:311-314`).
- **`joinConditions`** (runtime per-query join filters): 3 API levels,
  keyed `relation` or `<target>_<from>`; `one_one` demotes; a wildcard
  `'*_*'` condition is ANDed onto the final WHERE
  (`compiler.py:700-702,1042-1048`). **Needs the unified redesign of
  #625.**

### 2.e Structure (order_by, group_by, having, distinct, limit/offset, for_update)

`compiledQuery` signature (`compiler.py:831-846`, verbatim):

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

- `order_by`/`group_by`/`having`: strings with `$col`/`@rel` tokens;
  default `order_by` from `tblobj.attributes['order_by']` unless
  `ignoreTableOrderBy` or aggregate (`:909-910`).
- `group_by == '*'` sentinel = "aggregating, no GROUP BY list"
  (`:906-907`).
- `distinct`: explicit truthy → `DISTINCT `; **auto-injected** when rows
  explode and not aggregating, with hidden `__ord_col_N` sort columns
  appended to SELECT (`:1054-1081`) — a compensating hack.
- `limit`/`offset`: passthrough to `compileSql` (dialect assembles them).
- `for_update`: bool/str → `FOR UPDATE OF <t0> <mode>`
  (`_gnrbaseadapter.py:695-719`).
- `addPkeyColumn`: auto-appends `$pkey AS "pkey"` unless aggregate/count.
- `columnsFromStruct`: *not verified* as a query-language token in the
  compiler — the `struct`/`columnsFromStruct` helpers live in the UI/dbo
  layer, above `gnrsqldata`. Not part of the compiler surface.
- Implicit predicates ANDed (`:964-990`): env conditions, partition
  (`getPartitionCondition`), subtable (`&`→AND `|`→OR `!`→NOT), logical
  deletion (`$field IS NULL`; `=='mark'`→extra `_isdeleted` col), draft
  (`$field IS NOT TRUE`).
- `count=True` recompiles: `count(*) AS "gnr_row_count"`, or distinct
  main-table pkeys on exploding queries — **counts distinct pkeys, not
  result rows** (`:1054-1081`, REVIEW doubt in source).

### 2.f Macros and special tokens

Module-level regexes (`compiler.py:62-74`, verbatim in `02` §1.2):

- **`#IN_RANGE(value, low, high)`** (`expandInRange`, `:1309-1339`):
  four-branch OR handling NULL bounds; **inclusive** both ends. Applied
  to WHERE, join `cnd`, `sql_formula`. (Renamed from `#BETWEEN`, #622,
  merged.)
- **`#PERIOD(field, :param)`** (`expandPeriod`, `:1341-1397`): decodes a
  date-period param; emits `=`, `BETWEEN`, `>=`, `<=`, or `true`; **side
  effect**: writes `<param>_from`/`_to` into `sqlparams`. WHERE only.
- **`#BAG($field) [AS alias]`** (`expandBag`, `:1274-1289`): marks a
  column for post-fetch Bag parsing. Columns only.
- **`#BAGCOLS($field) [AS alias]`** (`expandBagcols`, `:1291-1307`):
  flattens Bag leaves into `<field>_<leafpath>` row keys. Columns only.
- **`#ENV` / `#PREF` / `#THIS`**: `sql_formula`/sub-select only (§2.c).
- **Adapter macros** (PG family, `_gnrbasepostgresadapter.py:13-108`):
  `#TSQUERY`/`#TSRANK`/`#TSHEADLINE`/`#VECQUERY`/`#VECRANK`. Now behind
  the **extensible `db.addMacro()` registry** (merged, #650/#660 — `07`
  §2).

Macro availability is **positional** (`02` §6): `#ENV/#PREF/#THIS` only
in formulas, `#PERIOD` only in WHERE, `#BAG(COLS)` only in columns. A
rewrite must decide whether to keep the positional constraint or make
macros uniform.

### 2.g Subqueries and nested selects

- **`#nestedselect` placeholder + `select_nestedselect` attribute**
  (`model.py:1179-1222`; `compiler.py:404-419`): the substitution point
  where a `subQueryColumn` splices a fully recursively-compiled
  sub-select. The `select_*` kwargs convention names each sub-select;
  `#<name>` in the formula is its slot.
- **`select=` / `exists=` VC** (`compiler.py:400-402`): a column with
  `select=` compiles as a correlated sub-select; `exists=` wraps it in
  `EXISTS(...)`.
- **subquery string-delegation**: `select='method_name'` →
  `subquery_<name>()` table method returns the spec (`compiler.py:406`).
  **Undocumented — document (#620).**
- **`subquery_aggr`** (scalar mode): the aggregation function name for a
  scalar correlated subquery.

Every `formulaColumn(select=...)` compiles as a **correlated inline
subquery** (the N+1 pattern) — the exact thing the 2026 experiments
tried to convert to JOINs (§3).

### 2.h Other user-writable tokens inventoried in doc 02

- `AS` alias normalization; auto-AS via `db.colToAs` (`:1006-1019`).
- `*_*` wildcard joinCondition (`:1042-1048`).
- `_STORENAME_` multi-store sentinel (`:921-923`).
- `_isdeleted` extra column (logical-deletion `'mark'` mode).

---

## 3. The 2026 experiments (Feb–Mar) — what they teach the reform

Full inventory in `07_legacy_compiler_experiments.md`. **Key fact**
(`07` §, verified): none of the experimental code landed in `develop` —
`SqlCompoundQuery`, `SqlCompiledSubQuery`, `sq_as_join`, `compiler_new`
are all absent; they survive only in branches/PRs (PRs #542, #544 still
open). What *did* land is the surrounding infrastructure (macro
registry, coverage suites, `#IN_RANGE` rename, thread-safe relation
tree).

### 3.1 The subquery-improvement chain (`07` §1)

A superseding sequence (PRs #457→#458→#460→#461→#471→#544, branch
`subquery_refactor_v2`) that taught:

1. **Subquery-to-JOIN as a compile-time strategy** (PR #461/#544): every
   `formulaColumn(select=...)` correlated subquery can be transformed
   into a pre-aggregated `LEFT JOIN` subquery, activated by a 3-level
   priority chain: per-column `sq_as_join=True` > per-query
   `enable_sq_join=True` > global `subquery_as_join=True`. Lesson: the
   **rendering of a virtual column (inline subquery vs join vs LATERAL)
   is a strategy chosen at compile time, not the column's identity**
   (`07` §4.1).
2. **LATERAL is on the map** (`subquery_refactor_v2` torture tests) — the
   third rendering strategy (`07` §4.2).
3. **Compiler decomposition** — `CompiledColumn`, `AliasManager`,
   `ColumnCompiler`, `SqlCompiledSubQuery` are the seams the legacy
   author identified inside the monolith (`07` §4.4).
4. **Bug found**: "formula + single subquery" (`COALESCE(#default, 0)`)
   was silently ignored in the single-subquery path (PR #458). The new
   compiler must handle formula-wrapping-a-subquery.

### 3.2 Compound queries — the `+`/`-` operator composition

**This is the idea the project owner recalls.** Reconstructed exactly
from the source (genropy branch `feature/compound_query`,
`gnrpy/gnr/sql/gnrsqldata/query.py`).

`SqlQuery` gained operator overloads (`query.py:630-641`, verbatim):

```python
def __add__(self, other):
    return self._compound(other, 'UNION')

def __or__(self, other):
    return self._compound(other, 'UNION ALL')

def __and__(self, other):
    return self._compound(other, 'INTERSECT')

def __sub__(self, other):
    return self._compound(other, 'EXCEPT')
```

The class docstring (`query.py:643-657`, verbatim) states the mapping:

```
q_union     = q1 + q2   # UNION
q_union_all = q1 | q2   # UNION ALL
q_intersect = q1 & q2   # INTERSECT
q_except    = q1 - q2   # EXCEPT
```

So the precise operator map is:

| Operator | Set op | Dunder |
|---|---|---|
| `q1 + q2` | UNION | `__add__` |
| `q1 \| q2` | UNION ALL | `__or__` |
| `q1 & q2` | INTERSECT | `__and__` |
| `q1 - q2` | EXCEPT | `__sub__` |

Mechanism (`query.py:602-703`):

- `_compound(other, operator)` (`:602-628`) builds a `SqlCompoundQuery`
  holding a `queries` dict (`{mangler_key: query}`) and a `template`
  string with `{key}` placeholders, e.g. `'{cq0} UNION {cq1}'`. When
  `other` is already compound, the left query is nested:
  `'{cq0} UNION SELECT * FROM (<other._template>) AS _cr'`.
- **Mangler** (`_next_mangler_key`, `:584-600`): each member query gets a
  unique prefix (`cq0`, `cq1`, …), counters stored in
  `currentEnv['_mangler_counters']`; the compiler prefixes every bind
  param with the mangler (`compiler.py:264-301` on that branch) so
  **params from different members never collide**.
- `SqlCompoundQuery(SqlQuery)` (`:643-703`): `sqltext` = the template
  formatted with each member's `sqltext` (`:667`); `sqlparams` = union of
  all members' params (`:678-682`); `compiled` = the first member's
  compiled (for column metadata, `:672-675`); `count()` wraps the whole
  thing in `SELECT count(*) FROM (<compound>) AS _compound`
  (`:695-703`). It composes further via its own `_compound` (`:683-693`),
  so chains like `q1 + q2 - q3` work associatively.

Doc `07` §1 also records companion infrastructure on the same branches:
`mangler`/`mainquery_kw`/`query_kw` params added to `SqlQuery.__init__`
(`query.py:154-155,165,176-177` on the branch) and a 344-line
`test_compound_query.py` (per `07` §1; *the test file was not found at
that path on `feature/compound_query` during this pass — not verified*,
but the operators, class and mangler are verified in
`query.py`).

**Lesson for the reform**: query composition is a **designed, tested**
surface. Because the new representation is an AST, composition should be
an **element in the tree** (a `union`/`intersect`/`except_` node with
child selects), and the `+`/`-`/`&`/`|` operators become **authoring
sugar** that build those nodes — no string-template mangling, because
param namespacing is intrinsic to a tree with scoped nodes (§4.2).

### 3.3 Other threads (`07` §2) worth carrying

- **Shadow compiler** (`compiler_new.py`, env switch
  `use_new_compiler`, divergence warnings) — a proven migration/
  validation technique if the new compiler must run inside legacy
  genropy.
- **RuntimeColumns/RuntimeModel** (PR #542 open) — programmatic
  temporary virtual columns/relations in a query scope; maps to
  AST-local column definitions.
- **Relation tree containing ALL virtual columns** (compiler-simplify) —
  anticipates the rewrite's single-tree-carries-every-column-kind
  decision.
- **Deprecation list (#616–#625)**, ready to consult: `table_aliases`
  (#616), `#ENV()` (#618), `*@relation` glob (#623), joiner `between`/
  `join_on`/`case_insensitive` (#621), `_STORENAME_` in compiler (#624),
  `joinConditions` redesign (#625).

---

## 4. Reform proposals

Legend per option: **KEEP** (as-is) · **REFORM** (kept, changed shape) ·
**ABSORB** (folded into a first-class AST construct) · **DROP** (with
reason).

### 4.1 Per-legacy-option disposition

#### Column spec (§2.a)

- `$column`, `@rel.col` (multi-hop) — **KEEP as tree primitives.** In the
  AST a column ref is a `col` element carrying `path="@rel.col"` stored
  **verbatim, never pre-lowered** (GIVEN constraint). The `$`/`@`
  distinction survives as a `kind` on the node (physical/relation).
- `expr AS alias` — **REFORM**: `alias="…"` attribute on any select-item
  element (no in-string `AS`).
- `*`, `*prefix_` — **KEEP** as projection sugar (a `starColumns`
  element / a `select(all=True, prefix=…)`), expanded at compile time.
- `*@rel...` related glob — **DROP** (zero usage, #623).
- `*@rel.(c1,c2)` explicit related list — **REFORM**: express as ordinary
  `@rel.c1`, `@rel.c2` refs; the aggregate-metadata side effect
  (`aggregateDict`) becomes an explicit `aggregate=` on the select item.
- implicit `sum/count` regex detection — **DROP the regex**; **REFORM**
  to an explicit `aggregate` element (`sum(...)`, `avg(...)`, `min`,
  `max`, `array_agg`, …) so the aggregate set is complete (fixes the
  `avg/min/max` miss, `02` §6) and GROUP BY inference is exact.
- `_STORENAME_` sentinel — **DROP from the compiler** (#624); handle at
  the execution layer.

Virtual-column consumption (aliasColumn/formulaColumn/subQueryColumn/
pyColumn/compositeColumn/bagItem/tool) — these are **model** citizens
(design `05` §2.2). In queries they are **referenced by name**; the
compiler resolves them against the model tree. The reform: the query AST
references them uniformly (`col path="@rel.formula_x"`), and the
*rendering strategy* for a formula/subquery column (inline subquery vs
pre-aggregated JOIN vs LATERAL) is a **compile-time strategy** (§3.1),
attached as a compile option, not baked into the reference.

#### WHERE / conditions (§2.b)

- String WHERE with raw predicates — **REFORM to escape hatch.** The
  default WHERE is the **structured, recursive** form (GIVEN). A raw SQL
  string remains available as an explicit `raw="…"` term, never the
  default.
- The `op_*` vocabulary (18 ops) — **KEEP as the semantic operator set**,
  as first-class tree operators. Each `op` becomes a value the `cond`
  element carries (`op="contains"`), and the **rendering per dtype /
  per dialect stays in the renderer** (exactly where `GnrWhereTranslator`
  and its dialect subclasses already put it). Recommended cleanups:
  - **ADD** the missing symmetric ops as real elements: `endswith`,
    `notcontains`, `notin`, `notequal` — today only reachable via `not_`
    or the CAST guard list, with no handler (§2.b). Make them explicit so
    the vocabulary is closed and testable.
  - **KEEP** `startswithchars` vs `startswith` (case-sensitive vs
    -insensitive) but rename for clarity, e.g. `startswith` +
    `case_insensitive=True` flag rather than two op names.
- Negation — **REFORM**: a `not_` wrapper element (matching `and_`/`or_`),
  not a string attribute and not a `not_<op>` name. Recursive.
- `jc` and/or, nested groups — **ABSORB** into `and_`/`or_` group
  elements (recursive), mirroring the Bag-of-conditions but as typed
  nodes. The first-node-blank-jc quirk disappears (grouping is
  structural).
- dtype-aware rendering (date period decoding, text-op CAST, unaccent,
  `'Q'` encryption) — **KEEP, in the renderer.** These are the genuinely
  valuable, non-obvious behaviors. Date-period decoding that **rewrites
  the operator** (`;v`→`lesseq`, etc.) should be an explicit,
  documented compile step, not a hidden mutation.
- `?name` value indirection — **DROP**; use a typed `:param` term.
- `value-is-field` (`$`/`@` value → column comparison) — **REFORM to
  explicit**: a comparison term is typed (constant | `:param` |
  column/path | raw expr, GIVEN). No sniffing of the value's first
  character.

#### Parameters and env (§2.c)

- `:param` — **KEEP** as a typed term citizen.
- kwargs→params — **KEEP** as an authoring convenience.
- `embedFieldPars` (param→field silent switch) — **DROP the silence**;
  a term is either a param or a path, declared (GIVEN).
- `#ENV(...)` macro — **DROP** (#618); use typed `:env_*` param terms.
- `#PREF(...)` — **REFORM** to a typed `pref` term (env citizen), not a
  string macro confined to formulas.
- `env_*_condition_*` implicit predicates, `var_` — **KEEP** as
  model/compile behavior, but surface them as explicit compile inputs so
  compilation can be made pure (the env→SQL coupling is documented, not
  ambient).

#### Relation-path resolution (§2.d)

- `@rel.col` → JOIN generation — **KEEP**, the crown jewel. In the AST the
  path is stored as-is on the source tree; the **model-aware compile**
  step lowers it into explicit `join` nodes in the LOWERED tree (GIVEN).
- LEFT-only joins — **REFORM**: the lowered tree carries a real join
  `type` (INNER/LEFT/…); the compiler can pick INNER when semantics allow
  (e.g. a NOT-NULL FK filtered in WHERE), removing the auto-DISTINCT
  hack. Auto-DISTINCT / `__ord_col_N` becomes an explicit lowering
  decision, not three cooperating hacks (`02` §6).
- ON-condition flavours — **REFORM to orthogonal attributes** on the
  relation (already decided model-side, `05` §2.4: `foreign_key`,
  `case_insensitive`, `cnd`/`join_on` ordinary attrs). The compiler reads
  them; `between` joiner flavour **DROP** (#621, deprecated).
- `aliasTable`/`table_aliases` path rewrites — **evaluate/likely DROP**
  (#616, undocumented/untested).
- `joinConditions` (runtime join filters) — **REFORM** per #625: one
  unified mechanism (a `join(on=…)` node or a query-scoped join filter),
  not 3 API levels / 5 code blocks / 2 keying strategies.

#### Structure (§2.e)

- `order_by`/`group_by`/`having` strings — **ABSORB** into structured
  `orderBy`/`groupBy`/`having` elements holding column/path refs and
  (for having) structured conditions.
- `group_by == '*'` sentinel — **DROP**; an explicit `aggregate=True`
  query flag.
- auto-DISTINCT + `__ord_col_N` — **REFORM** (see joins above): explicit
  lowering.
- `limit`/`offset` — **KEEP**; **ADD** first-class `FETCH`/`OFFSET` and
  `DISTINCT ON` (GIVEN).
- `for_update` — **KEEP**; **ADD** `SKIP LOCKED` / `FOR UPDATE OF`
  granularity (GIVEN).
- implicit predicates (logical deletion, draft, partition, subtable) —
  **KEEP** as model-aware compile injections (Genro semantics), but as
  explicit, inspectable lowering steps.
- `count` mode / distinct-pkey counting — **REFORM**: exact row semantics
  once joins have real types; keep a documented `count(distinct pkey)`
  option rather than an implicit behavior.

#### Macros (§2.f)

- `#IN_RANGE` — **ABSORB** into a structured range condition (it is just
  an inclusive `between` with NULL-bound handling). Keep the NULL-bound
  four-branch semantics in the renderer.
- `#PERIOD` — **ABSORB** into the date-period handling of the structured
  WHERE (the `op_*` date decoding already does this); drop the
  side-effecting macro.
- `#BAG` / `#BAGCOLS` — **KEEP** as explicit post-fetch column directives
  (a `bag`/`bagcols` flag on a select item), not string macros.
- `#TSQUERY`/`#TSRANK`/… adapter macros — **KEEP** via the merged
  `db.addMacro()` registry (`07` §2); they are dialect renderer concerns.
- `#ENV`/`#PREF`/`#THIS` — **DROP `#ENV`**; **REFORM `#PREF`/`#THIS`**
  into typed terms (`#THIS` = "this table's column", becomes the natural
  self-reference in a correlated subquery node).
- positional macro availability — **DROP the positional constraint**:
  in a tree, a term is valid wherever its node type is allowed.

#### Subqueries / nested selects (§2.g)

- `#nestedselect` / `select_*` convention — **ABSORB**: a subquery is a
  child `select` node, referenced structurally; no placeholder string.
- `select=`/`exists=` VC, `subquery_aggr` — **ABSORB** into `EXISTS`/
  scalar-subquery AST nodes; the inline-vs-JOIN-vs-LATERAL choice is a
  compile strategy (§3.1).
- json/xml aggregation SQL — **ABSORB into the renderer** (design `05`
  q7): the tree stores intent (`mode="json"`), the dialect emits
  `json_agg`/`xmlagg`.

### 4.2 New capabilities from the AST grammar

Full-SQL constructs (GIVEN as first-class) get authoring surfaces:

- **UNION/INTERSECT/EXCEPT** (recursive) — element `union` / `intersect`
  / `except_` with child `select` nodes and an `all=True` variant.
  **Operator composition sugar** (from §3.2, now over the tree):

  | Operator | Node built | ALL variant |
  |---|---|---|
  | `q1 + q2` | `union` | `q1 + q2` with `.all()` or a distinct `q1 | q2` |
  | `q1 - q2` | `except_` | `except_(all=True)` |
  | `q1 & q2` | `intersect` | `intersect(all=True)` |
  | `q1 \| q2` | `union all` | — |

  **Recommendation on the operator map**: keep the legacy semantics
  (`+`=UNION, `-`=EXCEPT, `&`=INTERSECT) because they match set algebra
  intuition and the existing tested surface. For the ALL variants,
  prefer an explicit `.all()` / `all=True` over overloading `|`: `|` as
  "UNION ALL" is the one non-obvious mapping (a reader expects `|` to be
  OR-like/union, not specifically *ALL*). Precedence: Python's operator
  precedence (`&` binds tighter than `+`/`-`, which bind tighter than
  `|`) does **not** match SQL set-op precedence (all left-associative,
  equal) — so the sugar must **parenthesize into explicit nodes** and
  the docs must state that mixed chains require explicit grouping
  `(q1 + q2) - q3`. Because each `select` is a scoped subtree, **param
  namespacing is intrinsic** — the legacy "mangler" (§3.2) is
  unnecessary; params are qualified by their owning node.

  *Authoring example*:
  ```python
  active   = q.select('customer', where=cond(op='istrue', col='active'))
  archived = q.select('customer_archive')
  all_rows = active + archived            # UNION
  only_new = active - archived            # EXCEPT
  ```
  *Migration note*: legacy code composed `SqlQuery` objects with the same
  operators on the `feature/compound_query` branch (never shipped);
  shipped legacy had **no** set-op surface — users wrote raw
  `UNION`-strings or multiple queries merged in Python. The AST makes it
  native.

- **WITH / CTE (incl. recursive)** — a `with_` element holding named
  `cte` children; `recursive=True` for recursive CTEs. Genro paths and
  structured WHERE usable inside each CTE.
  *Migration note*: no legacy equivalent (CTEs were only expressible via
  raw SQL).

- **Window functions** — a `window` term (`over`, `partitionBy`,
  `orderBy`, frame `rows`/`range`, `filter`). *No legacy equivalent.*

- **GROUPING SETS / ROLLUP / CUBE** — variants of the `groupBy` element.
  *No legacy equivalent.*

- **LATERAL** — a join `type="lateral"`; also the third rendering
  strategy for correlated subquery columns (§3.1/§3.3). *Only reached in
  the unmerged torture tests legacy-side.*

- **VALUES** — a `values` element usable as a row source. *No legacy
  equivalent.*

- **CASE / CAST** — structured `case`(`when`/`then`/`else_`) and `cast`
  terms, usable as select items and inside conditions. Legacy had string
  `CAST(...)` only.

- **EXISTS / IN / ANY / ALL** — structured predicate terms taking a child
  `select`, replacing the legacy `exists=`/`select=` string conventions.

- **DISTINCT ON**, **FETCH/OFFSET**, **FOR UPDATE … SKIP LOCKED** — flags
  on the query element (GIVEN).

Each of these is a node the **model-aware compile** step leaves mostly
untouched (they are already SQL-shaped), while it lowers the Genro
primitives (paths, structured WHERE, model-injected predicates) around
them.

### 4.3 The SOURCE→LOWERED→render pipeline (how the reform lands)

The GIVEN two-form model maps the reform cleanly:

- **SOURCE tree** carries Genro primitives verbatim: `@rel.col` paths,
  `op_*` structured conditions, `:param`/env terms, formula/subquery
  column refs, model-injected-predicate intent. This is what is
  serialized/saved.
- **Model-aware compile**: resolves paths against the model tree
  (reusing the relation-resolver contract, `02` §7.5 — the ~6-7 methods),
  chooses join types and subquery-rendering strategies (§3.1), injects
  logical-deletion/draft/partition/subtable predicates, decodes date
  periods.
- **LOWERED tree**: pure SQL nodes (explicit joins, plain predicates,
  bound params) — dialect-agnostic.
- **Per-backend renderer**: emits the SQL string; dialect variance
  (ILIKE, `~*`, `IS NOT TRUE`, `json_agg`, TSQUERY macros, LIMIT/OFFSET/
  FETCH syntax) lives here, exactly as today the adapter owns
  `compileSql`/`prepareSqlText`/macro sets (`02` §7.3).

A **textual-SQL reader** (optional `sqlglot`) parses a SQL string into
the LOWERED tree (then optionally re-lifts recognizable patterns to
SOURCE) — mentioned per GIVEN, not designed here.

---

## 5. Open questions (each with a recommendation)

1. **UNION ALL operator.** Keep legacy `|`=UNION ALL, or require explicit
   `.all()`? *Recommendation*: explicit `all=True`/`.all()`; reserve `|`
   only if user demand appears — `|` reading as "ALL" is the one
   surprising mapping (§4.2).

2. **Set-op precedence in operator chains.** Python precedence
   (`&` > `+`/`-` > `|`) ≠ SQL (all equal, left-assoc). *Recommendation*:
   sugar always builds explicit nodes; document that mixed chains need
   parentheses; consider emitting a loud error on an ambiguous mixed
   chain rather than silently following Python precedence.

3. **`op_*` vocabulary completeness.** Add `endswith`, `notcontains`,
   `notin`, `notequal` as real ops (today unimplemented/`not_`-only,
   §2.b)? *Recommendation*: yes — close the vocabulary so it is testable
   and symmetric; keep negation *also* available as a `not_` group for
   composed predicates.

4. **Date-period operator rewriting.** The legacy `decodeDates`
   **changes the operator** based on the value (`;v`→`lesseq`, …,
   `:1452-1492`). Keep this magic? *Recommendation*: keep the capability
   (it is genuinely useful for query panels) but make it an explicit,
   named compile pass (`decode_periods=True`) rather than an implicit
   mutation, so a plain comparison stays a plain comparison.

5. **Compile purity.** Legacy compile mutates `sqlparams`/`currentEnv`
   and reads ambient env/locale (§2.c, `02` §6). *Recommendation*: make
   the SOURCE→LOWERED compile **pure** — env/locale/workdate are explicit
   compile inputs; the LOWERED tree + bound params are the sole outputs.
   This is what makes queries serializable and cacheable.

6. **Subquery rendering strategy surface.** inline vs pre-aggregated JOIN
   vs LATERAL (§3.1). Per-column, per-query, or global default — and what
   IS the default? *Recommendation*: default = inline correlated
   subquery (legacy-compatible, always correct); opt into JOIN/LATERAL
   per-query and per-column, reusing the #461/#544 3-level priority
   design. Do **not** change the default silently.

7. **Escape hatch scope.** Raw SQL is allowed as a declared term
   (GIVEN). At what granularity — whole-clause only, or per-term? *
   Recommendation*: per-term `raw="…"` plus whole-query `rawSql="…"`;
   both flagged so a tree consumer (migrate, cache-key, permission
   checker) can detect "this query contains raw SQL" and refuse to
   reason about it.

8. **`joinConditions` unification (#625).** Runtime per-query join
   filters have 3 legacy API levels. *Recommendation*: one form — a
   `join(on=<structured condition>)` node or a query-scoped
   `join_filter` — resolved through the same structured-condition
   machinery as WHERE.

9. **Where does the structured-WHERE authoring API live** relative to the
   query-panel Bag (`GnrWhereTranslator` consumes an XML/Bag today)? *
   Recommendation*: the query-panel Bag becomes one *reader* into the
   SOURCE WHERE subtree (round-trippable), so existing UI panels keep
   working while the canonical form is the AST.

10. **Two model dialects, one query grammar.** The compiler resolves
    paths against either the legacy or modern model tree (GIVEN). *
    Recommendation*: define the compiler's model-tree contract as the
    compact ~6-7-method interface identified in `02` §7.5, so both
    dialects satisfy it and the query grammar depends on neither dialect
    directly.

---

## References

Sources consulted (all verified during this session):

- Roadmap docs (this directory): `01_legacy_model_grammar.md` §1.6–1.18,
  §2.4; `02_legacy_compiler_query.md` (full); `05_grammar_design.md`
  §2.4–2.7, §3; `07_legacy_compiler_experiments.md` (full).
- Legacy source @ `83c138bb6`
  (`/Users/gporcari/Sviluppo/Genropy/genropy/worktrees/develop/gnrpy/gnr/`):
  - `sql/gnrsqldata/compiler.py` (query compiler, macros, JOIN
    resolution) — lines cited inline.
  - `sql/gnrsqldata/query.py` (`SqlQuery` surface).
  - `sql/adapters/_gnrbaseadapter.py:1265-1628`
    (`GnrWhereTranslator`, the full `op_*` vocabulary, `whereFromDict`).
  - `sql/adapters/_gnrbasepostgresadapter.py:1328-1329`
    (`GnrWhereTranslatorPG.op_similar`); dialect `op_*` overrides in
    `gnrmysql.py`, `gnrmssql.py`, `gnrdb2_400.py`, `gnrfourd.py`.
  - `sql/gnrsqltable/query.py:85-105` (`sqlWhereFromBag` — the bridge
    from the structured Bag to the compiler's `where` string).
- Compound-query composition (genropy branch **`feature/compound_query`**,
  unmerged): `gnrpy/gnr/sql/gnrsqldata/query.py:584-703` — `_compound`,
  `__add__`/`__or__`/`__and__`/`__sub__`, `SqlCompoundQuery`, mangler.

Unverified claims explicitly flagged in-text:
- `test_compound_query.py` (344 lines, cited by `07` §1) not found at the
  expected path on `feature/compound_query` during this pass.
- `notcontains`/`endswith` ops have no base handler (verified absent);
  whether any caller registers them via `customOpCbDict` — not verified.
- `columnsFromStruct` is not a compiler-level query token (it lives above
  `gnrsqldata`) — stated as not-part-of-surface, not exhaustively traced.

Session: 26b5ad69-afbc-44c4-9652-2be5dff3cc12 (2026-07-11)
