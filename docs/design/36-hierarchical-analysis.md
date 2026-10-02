# 36 — Analisi delle tabelle gerarchiche nel legacy

Stato: analisi; decisioni del 2026-10-02 nella sezione 10. Serve a progettare in asqueel la
funzione gerarchica come elemento della grammatica dentro `table`, partendo
dalle funzioni offerte e non dall'implementazione legacy.

Riferimenti: genropy `origin/develop` `1561d6547d7c`, letto con `git show`.
Abbreviazioni: `dbo` = `gnrpy/gnr/app/gnrdbo.py`; `hier.py` =
`gnrpy/gnr/sql/gnrsqltable_proxy/hierarchical.py`. L'uso nelle applicazioni
viene dall'indice Sourcerer (sezione 8). Le affermazioni marcate
**[dedotto]** vengono dalla lettura del codice, non da un'esecuzione.

## 1. Funzioni offerte allo sviluppatore

- **Attivazione**: `sysFields(tbl, hierarchical=True | 'f1,f2[:unique]', ...)`
  (dbo:324-329, `:380-444`). Richiede la colonna `id` automatica
  (`assert id`, dbo:382).
- **Path materializzati**: un path della pkey e uno per ogni campo dichiarato
  (dbo:411-436; hier.py:269-274).
- **Numero di figli**: formula `child_count` (dbo:393-394).
- **Livello**: formula `hlevel` (dbo:395).
- **Ordine fra fratelli**: con `counter=True`, `_row_count`, `_h_count` e
  `order_by` di default `$_h_sortcol` (dbo:446-455; hier.py:260-268, `:279-283`).
- **Radice del nodo**: `hierarchical_root_id=True` crea `root_id`
  (dbo:396-402).
- **Nodi virtuali**: `hierarchical_virtual_roots=True` crea `_virtual_node`,
  copiato dal padre (dbo:403-404).
- **Un albero per ogni record di un'altra tabella**:
  `hierarchical_linked_to='pkg.tbl'` crea una radice per ogni record di quella
  tabella (dbo:405-409, `:563-613`).
- **Una colonna per livello**: `hdepth=N` spezza il path in colonne virtuali
  (dbo:429-435; hier.py:237-250).
- **Valori copiati dal padre**: ogni colonna `copyFromParent=True` è copiata
  dal padre a ogni scrittura (hier.py:275-278).
- **Valore dell'antenato più vicino**: la variante `hlv` dà il primo valore non
  nullo risalendo l'albero, nodo compreso (hier.py:226-235; dbo:732-736).
- **Dati per l'albero**: `getHierarchicalData`, Bag con resolver lazy
  (dbo:757-769; hier.py:310-332).
- **Ricerca**: `hierarchicalSearch`, ILIKE sul campo caption, restituisce gli
  id dei path trovati (dbo:771-774; hier.py:209-224).
- **Path da pkey**: `pathFromPkey` (dbo:917-919; hier.py:333-341) e
  `getHierarchicalPathsFromPkeys` (dbo:921-932; hier.py:343-360).
- **Antenati**: `getAncestors(pkey | hierarchical_pkey, meToo=True)`, solo
  sull'handler, non pubblico (hier.py:363-372).
- **Rinumerazione dei fratelli**: `fixRowCount(parent_id)`, ricorsivo
  (hier.py:374-383).
- **Campi dinamici ereditati**: `df_getFieldsRows_bag/_table` uniscono i
  `df_fields` del nodo e degli antenati (dbo:1172-1207).
- **Lingue**: un campo gerarchico `localized` crea `hierarchical_<fld>_<lang>`
  per ogni lingua (dbo:242-272).
- **Spostamento e creazione in serie dall'interfaccia**: `ht_moveHierarchical`
  (`resources/common/th/th_tree.py:150-169`) e `ht_htreeCreateChildren`
  (`th_tree.py:310-353`).
- **Discendenti**: nessuna API. Si scrive a mano
  `$hierarchical_pkey LIKE :p || '/%'` (`adm/model/menu.py:33`;
  `th_tree.py:457`, `:475`, `:488`; `th_picker.py:277`).

## 2. Cosa crea nel modello

- Normalizzazione dell'argomento (dbo:381): `True` → `'pkey'`; una stringa →
  `'<stringa>,pkey'`.
- `parent_id` (dbo:385-392): `size='22'`, `group='*'`, `_sysfield`; trigger
  `onInserting` / `onUpdating='hierarchical_before'`,
  `onUpdated='hierarchical_after'`; relazione verso `<tbl>.id` con
  `mode='foreignkey'`, `onDelete='cascade'`, `relation_name='_children'`,
  `deferred=True`. `onDelete_sql` non è impostato.
- `child_count` (dbo:393-394): subquery `COUNT(*)` con
  `where='@_children.parent_id=#THIS.id'`, `dtype='L'`.
- `hlevel` (dbo:395):
  `length($hierarchical_pkey)-length(replace($hierarchical_pkey,'/',''))+1`.
- `root_id`, con `hierarchical_root_id` (dbo:397-402): colonna fisica con
  `sql_value="substring(:hierarchical_pkey from 1 for 22)"`, scritta dall'SQL a
  ogni INSERT/UPDATE (`sql/adapters/_gnrbaseadapter.py:755-757`, `:814-817`,
  `:859-863`); relazione `relation_name='_grandchildren'`, `onDelete='ignore'`.
- `_virtual_node` (dbo:404): `dtype='B'`, `copyFromParent=True`.
- Per `pkey` (dbo:413-417): `hierarchical_pkey` (`unique=True`, `_sysfield`) e
  `_parent_h_pkey` (`_sysfield`).
- Per ogni altro campo `fld` (dbo:419-428): `hierarchical_<fld>` (`unique` solo
  con `fld:unique`, attributo `hierarchical_field_of=fld`, senza `_sysfield`) e
  `_parent_h_<fld>` (`_sysfield`). Nessuna colonna `hierarchical_*` dichiara
  `dtype` o `size`.
- `hdepth` (dbo:429-435): `variant='hdepth'` e `variant_hdepth_levels=N`
  sull'ultima colonna gerarchica; le colonne virtuali le produce il meccanismo
  generico delle varianti (`gnrsqlmodel/table.py:440-471`).
- Attributi di tabella:
  - `hierarchical`: elenco pulito dei campi, sempre terminato da `pkey`
    (dbo:436);
  - `order_by`: `$hierarchical_<primo>` senza contatore (dbo:438),
    `$_h_sortcol` con contatore (dbo:455);
  - `broadcast` esteso con `parent_id` (dbo:440-444);
  - `hierarchical_linked_to` (dbo:406);
  - `hierarchical_caption_field` è letto (hier.py:113, `:218`) ma nessun codice
    lo scrive.
- Con contatore (dbo:448-455; `counter` deve essere `True`, assert a dbo:449):
  `_h_count`, `_parent_h_count`, `_row_count` (`dtype='L'`, `counter=True`,
  senza trigger `setRowCounter`), formula `_h_sortcol` = `$_h_count` se la
  tabella ha solo `pkey`, altrimenti `COALESCE($_h_count,$<primo campo>)`.
- `linkHierarchicalToMaster` (dbo:563-585), differito con `deferOnBuilding`:
  - sulla tabella gerarchica: `<mastertbl>_<masterpkey>`, `copyFromParent`,
    `fkeyToMaster`, relazione verso il master con `relation_name='<tbl>s'`,
    `onDelete='cascade'`, `onDuplicate=False`;
  - sul master: `root_<tbl>_id`, relazione verso `<tbl>.id` con `one_one='*'`,
    `onDelete_sql='setnull'`, trigger `insertLinkedHierarchicalRoot` /
    `updateLinkedHierarchicalRoot`;
  - `trigger_insertLinkedHierarchicalRoot` (dbo:588-601) inserisce la radice
    con `id = masterpkey.ljust(22,'_')` e copia i campi gerarchici omonimi;
  - `trigger_updateLinkedHierarchicalRoot` (dbo:603-613) li propaga alla radice.
- L'handler esiste solo se la tabella ha l'attributo `hierarchical`
  (`gnrsqltable/table.py:82-83`).

## 3. Ciclo di scrittura e costi

- I trigger di campo girano a ogni insert e update, qualunque colonna cambi
  (`gnrsqltable/crud.py:680-694`). `parent_id` è solo il punto di
  registrazione.
- **Insert** (`gnrsql/write.py:153-168`), `trigger_before`:
  1. una SELECT del padre (hier.py:257-259);
  2. con contatore e `_row_count` vuoto, una SELECT del massimo fra i fratelli,
     poi massimo + 1 (hier.py:260-268);
  3. path come `'%s/%s' % (path_padre, valore)` (hier.py:269-274);
  4. copia delle colonne `copyFromParent` (hier.py:275-278);
  5. `_h_count = _h_count_padre + encode36(_row_count, 2)` (hier.py:281-283).
  All'insert non c'è trigger dopo la scrittura.
- **Update** (`write.py:251-265`): `hierarchical_before` → UPDATE →
  `updateRelated` → `_onDbChange` → `hierarchical_after`.
  - `before` legge il padre a ogni update, anche senza modifiche gerarchiche.
  - `_row_count` non è riassegnato in update.
  - `trigger_after` (hier.py:287-308): se è cambiato un `hierarchical_<fld>`,
    `_row_count` o `_parent_h_count`, legge i figli `for_update=True` ed esegue
    `tblobj.update(new_row, row)` su ognuno. La cascata è un update ricorsivo,
    un figlio alla volta, con tutti i trigger.
  - Spostare un nodo (cambiare `parent_id`) o rinominare un campo del path
    riscrive tutto il sottoalbero.
  - Costo per discendente **[dedotto]**: una SELECT del padre, un UPDATE, una
    SELECT dei figli, le SELECT di `updateRelated` (una per relazione many con
    `onUpdate`, `crud.py:150-180`), un evento `dbChange`.
- **Delete** (`write.py:294-319`; `crud.py:182-229`): nessun trigger
  gerarchico. `deleteRelated` legge i figli via `_children`
  (`onDelete='cascade'`) e cancella ognuno ricorsivamente. Costo per nodo: una
  SELECT per relazione many non `ignore` più un DELETE. La cascata è solo
  Python.
- **Duplicazione** (`gnrsqltable/copy.py:251-321`): `parent_id` invariato
  (`:268`); colonne `_sysfield` e `unique` azzerate e ricalcolate da `before`
  (`:270-274`); `_children` diventa `onDuplicate='recursive'` (`:293-297`);
  ogni figlio duplicato ricorsivamente (`:303-316`).
- **Copia e incolla**: `onCopyRecord` espande `@_children` (`copy.py:106-141`);
  con `hierarchical_linked_to` non lo espande (`:148-154`) e
  `_duplicateLinkedTree` copia tutti i nodi del master (`:208-229`).
- **Import di record cluster JSON**: esegue gli `onInserting` e poi
  `raw_insert` (`gnrsqltable/serialization.py:134-140`), quindi `before` gira.

## 4. Lettura

- `TableHandlerTreeResolver` (hier.py:28-199): un livello per `load`, con
  `$parent_id=:p_id`, `$parent_id IS NULL` o `$id=:r_id` (`:104-134`); colonne
  `*, $child_count, $<caption>`; `order_by` della tabella o la caption
  (`:128`); scelta della caption: `caption_field`, `hierarchical_caption_field`,
  primo campo gerarchico, `caption_field` della tabella (`:111-119`).
  - `related_kwargs` aggiunge come foglie righe di un'altra tabella, una query
    per foglia (`:153-161`).
  - `condition` seleziona le foglie (`$child_count=0`) che la soddisfano e
    raccoglie gli id dei loro path nel pageStore (`:182-199`).
- `getAncestors`: `:p ILIKE $hierarchical_pkey || '/%'`, opzionalmente
  `OR :p = $hierarchical_pkey`, ordinato per `$hlevel` (hier.py:363-372).
- `hlv`: `#THIS.hierarchical_pkey LIKE $hierarchical_pkey || '%' AND $fld IS
  NOT NULL ORDER BY hierarchical_pkey DESC LIMIT 1` (hier.py:228-230).
- `hdepth`: `array_to_string((string_to_array($f,'/'))[1:i],'/')`
  (hier.py:244), solo PostgreSQL.
- Il compiler e le selezioni non trattano le tabelle gerarchiche in modo
  speciale: nessun riferimento in `gnrpy/gnr/sql/gnrsqldata`.

## 5. Interfaccia

Solo elenco, per sapere cosa l'adattatore dovrà servire.

- `th_tree.py`: `ht_hdbselect` `:19`, `ht_treemenu` `:47`,
  `ht_htableViewStore` `:84`, `ht_moveHierarchical` `:151`, `ht_hTableTree`
  `:174` (drop `:197-214`), `ht_treeViewer` `:243`, `ht_hviewTree` `:282`,
  `th_hviewTreePicker` `:293`, `ht_htreeCreateChildren` `:311`,
  `ht_slotbar_treeSortingTool` `:357`, `ht_slotbar_form_hbreadcrumb` `:375`,
  `ht_relatedTableHandler` `:434`, `ht_updateRelatedRows` `:588`,
  `ht_removeAliasRows` `:621`, `ht_structureTree` `:634`.
- `th_tree.js`: `refreshTree` `:2`, `fullPathByIdentifier` `:61` (chiama
  `pathFromPkey` a `:83`), `dropTargetCbOnSelf` `:87-113`, `onPickerDrop`
  `:124`, `onRelatedRow` `:151`.
- `th_form.py:197-200` (stack gerarchico se `hierarchical != 'pkey'`),
  `:349` (`treeViewer`); `th_picker.py:70-84`, `:184-280`, `:343-344`;
  `genro_components.js:5938`, `:5997`; `tag_matrix_grid.py:45`, `:274-316`.

## 6. Il meccanismo precedente `htable`

- `htableFields` non è definito in `origin/develop`; resta una chiamata
  commentata in `adm/model/htag.py:13-14`.
- Resta il componente `resources/common/gnrcomponents/htablehandler.py`:
  `HTableResolver` `:41`, `HTableHandler` `:285`, `HTablePicker` `:869`.
  Colonne attese: `code`, `parent_code`, `child_code`, `child_count`,
  `description`, `rec_type` (`:240`). `code` è un path separato da `.`
  (`:810`); i discendenti con `$code LIKE :code%` (`:395-399`). Il drag chiama
  `reorderCodes` (`:799`), che non esiste nel repository.
- `flib.category` è migrata al meccanismo attuale (`flib/model/category.py:9`)
  e conserva `parent_code`/`code`.

| | `htable` | `hierarchical` |
|---|---|---|
| Legame col padre | `parent_code` (testo) | `parent_id` (FK su `id`) |
| Path | `code`, separato da `.` | `hierarchical_pkey`, separato da `/` |
| Path di altri campi | nessuno | `hierarchical_<fld>` |
| Cascata | nessun trigger presente | trigger prima e dopo la scrittura |

## 7. Difetti del legacy

- **`:unique` nella formula di ordinamento**: `_h_sortcol` usa la stringa
  grezza (dbo:381, `:453`); con `hierarchical='code:unique', counter=True`
  diventa `COALESCE($_h_count,$code:unique)`. Verificato.
- **Più di 1295 fratelli**: `encode36(n, 2)` restituisce `''` oltre due cifre
  (`gnr/core/gnrstring.py:845-847`); il nodo prende lo `_h_count` del padre e
  l'ordinamento si rompe. Verificato.
- **Cicli**: nessun controllo lato server che un nodo diventi antenato di se
  stesso (hier.py:252-283; `th_tree.py:155`). Solo il client controlla i nodi
  caricati (`th_tree.js:99`). **[dedotto]** Spostare A sotto un suo
  discendente produce una cascata senza fine.
- **Spostamento e `_row_count`**: il nodo spostato tiene il numero del vecchio
  padre (hier.py:261); fra i nuovi fratelli nascono duplicati.
- **`fixRowCount` sulle radici**: usa `$parent_id=:pid` con `pid=None`
  (hier.py:377) e `row['id']` fisso (`:383`).
- **`pathFromPkey` con `condition`**: la condizione è costruita ma non passata a
  `readColumns` (hier.py:335-339).
- **`getHierarchicalPathsFromPkeys` con `parent_id`**: `split(parent_id,1)[1]`
  (hier.py:358) dà IndexError se `parent_id` non è nel path.
- **`trigger_after` senza `old_record`**: `old_record.get` senza controllo
  (hier.py:290). Verificato.
- **Campo gerarchico nullo**: il path diventa `None` alla radice e `'None/x'`
  nei figli (hier.py:274).
- **Padre cancellato logicamente o in bozza**: la query del padre usa i default
  `excludeLogicalDeleted=True`, `excludeDraft=True` (hier.py:258;
  `gnrsqltable/query.py:129`): il figlio diventa radice. Anche i figli
  cancellati o in bozza sono esclusi dalla cascata (hier.py:297) e restano con
  il path vecchio.
- **`_` nei LIKE**: gli id contengono `_` (`gnrlang.py:165-170`) e le radici
  sintetiche sono riempite con `_` (`menu.py:26-29`; dbo:600); nessun LIKE fa
  escape (`menu.py:33`; hier.py:228, `:367`; dbo:1182, `:1202`;
  `th_tree.py:475`, `:488`; `th_picker.py:277`).
- **ILIKE su id**: `getAncestors` e `df_*` usano ILIKE su id che distinguono
  maiuscole e minuscole (hier.py:367; dbo:1182, `:1202`).
- **`/` nei valori**: nessun escape (hier.py:274); `hdepth` spezza male
  (hier.py:244).
- **Id di 22 caratteri fissi**: `root_id` (dbo:397), `hlv` con LIKE prefisso
  senza `/` (hier.py:228), radice collegata con `ljust(22,'_')` (dbo:600).
- **Indice di `hierarchical_pkey`**: nessun `size` (dbo:414); `unique=True` lo
  indicizza ma senza `text_pattern_ops`. **[dedotto]** Con collation non-C
  l'indice non serve per `LIKE 'x%'`. Ogni livello aggiunge 23 caratteri.
- **`hdepth` crea `N-1` colonne**: `range(1, levels)` (hier.py:240).
- **`hlv`/`hdepth` su tabella non gerarchica**: AttributeError invece del
  messaggio previsto (dbo:734, `:740`; `table.py:82-83`).
- **Controllo sempre vero**: `hierarchical is not True` con un attributo che è
  sempre stringa (dbo:596, `:607`, `:436`).
- **`_parent_h_*` scritto due volte**: da `trigger_after` sui figli
  (hier.py:302) e poi da `before` del figlio (hier.py:273). Nessun codice del
  framework legge `_parent_h_*`.
- **`copyFromParent` a ogni update**: una modifica diretta sul figlio viene
  persa (hier.py:275-278).
- **`child_count`** con join su `@_children` invece di `$parent_id=#THIS.id`
  (dbo:394), eseguito per ogni riga dell'albero (hier.py:130).
- **`condition` sull'albero**: filtra solo le foglie (hier.py:190); un nodo
  interno senza foglie valide sparisce.
- **Concorrenza [dedotto]**: `_row_count = max+1` senza lock (hier.py:266-268);
  un figlio inserito durante lo spostamento del padre resta con il path
  vecchio.
- **Duplicazione con `hierarchical_<fld>` unique**: il trigger ricalcola lo
  stesso valore del sorgente (`copy.py:270-274`; hier.py:274) e viola
  l'unicità.
- **`_duplicateLinkedTree`**: presume radice per prima e padri prima dei figli
  senza `order_by` (`copy.py:217-229`).
- **Codice morto**: `fixRowCount`; `htablehandler.py` con `reorderCodes`
  inesistente; `hv_defaultConf` (`th_extra.py:236`).
- **`assert`** per `id` e `counter` (dbo:382, `:449`): spariscono con
  `python -O`.

## 8. Uso nelle applicazioni (Sourcerer)

Metodo: `code_search_code` a pagine da 50 moduli fino alla pagina vuota,
deduplicato per repo:path. Le copie di package in più repository
(contractmanager/genrojobs, erpy/erpyready, icond/erpylight `_legacy`,
teamset/teamset_v1) sono contate separatamente. Le query che terminano con `_`
restituiscono zero: si sono cercati i nomi completi.

### 8.1 Dichiarazioni

| | Framework `genropy` | Applicazioni |
|---|---|---|
| Tabelle gerarchiche | 14 | 150 in 35 repository |
| Un solo campo | 8 | 106 |
| Più campi | 4 | 42 |
| `hierarchical=True` | 2 | 2 |
| con `counter=True` | 8 | 93 |
| con `df=True` | 4 | 57 |
| con `hierarchical_root_id` | 1 | 19 |
| senza altre opzioni | 5 | 32 |

- Per repository: erpy 27, icond 12, contractmanager 10, erpylight 9, anaci 9,
  aisla 6, pfrc 6, erpyready 5, genropynet 5, mbe 5, genrojobs 5, gnrbau 4,
  ldrc 4, teamset 4; altri 21 repository da 1 a 3.
- Primo campo: `descrizione` 68, `description` 25, `codice` 13, `name` 12,
  `nome` 8, `titolo` 4, `denominazione`, `nome_campo`, `caption`, `title` 3
  ciascuno, altri 6; più 2 con `hierarchical=True`.
- Più campi: `descrizione,codice` 19, `description,child_code` 6,
  `description,code` 3, `codice,descrizione` 3, altri 11.
- `_row_count` come campo gerarchico: 2 (`genropy:model/product_group.py:11`;
  `gnrextra:model/question.py:10`).
- `:unique`: 0 usi.
- `hierarchical_virtual_roots`: 1 (`icond:model/st_struttura.py:7`).
- `hierarchical_linked_to`: 1 (`gnrextra:model/question.py:11`).
- `hdepth=3`: 3 (`erpy:model/conto_gerarchia.py:16`,
  `erpyready:model/conto_gerarchia.py:15`, `erpy:model/un_ind_gerarchia.py:11`);
  le colonne `_0N` non sono lette (4 righe commentate).

### 8.2 Letture delle colonne generate

Moduli trovati per query, framework e applicazioni insieme.

| Colonna | Moduli | Uso prevalente |
|---|---|---|
| `hierarchical_pkey` | 165 | sottoalbero, antenati, radice |
| `hierarchical_descrizione` | 131 | caption, vista, ordinamento, ricerca |
| `hierarchical_description` | 69 | idem |
| `hierarchical_name` | 56 | idem |
| `hierarchical_codice` | 52 | idem, filtri per prefisso |
| `child_count` | 126 | `$child_count=0` (foglie) |
| `hlevel` | 27 | `order_by`, `CASE` per livello |
| `@_children` | 26 | `relation='@_children'` nei TableHandler |
| `root_id` | 12 | backfill, `@root_id.codice` |
| `_h_count` | 30 | confronto d'ordine |
| `_h_sortcol` | 6 | ordinamento |
| `_parent_h_*` | 37 | quasi solo colonne di vista |
| `_grandchildren` | 0 | — |

- Sottoalbero su `hierarchical_pkey`, tre forme diverse:
  - `LIKE x || '/%'` (esclude il nodo): per esempio `erpy:model/conto.py:96`,
    `teamset_v1:model/conto.py:24`, `genropy:model/menu.py:33`;
  - `LIKE x || '%'` (include il nodo): per esempio
    `erpy:model/centro_lavoro.py:41`, `icond:model/st_struttura.py:19`;
  - `'%' || x || '%'`, regex, `SIMILAR TO`: `colto:model/rint_path_index.py:38`,
    `pfrc:resources/tables/extra/th_extra.py:180`, `dlfgest:lib/report.py:192`.
- Antenati con `:p ILIKE $hierarchical_pkey || '/%'`:
  `icond:model/pr_evento.py:399`, `erpy:model/li_listino_cliente.py:55`.
- Radice con `substring`: `erpy:model/riclassificazione.py:44`,
  `icond:model/pr_evento.py:201`.
- Path ricostruito in Python con `split('/')`:
  `erpy:model/conto_gerarchia.py:142`, `icond:model/pr_pratica.py:527`.
- Path di un campo usato come chiave naturale: `$hierarchical_name=:hname`
  (`genropy:webpages/docserver.py:21`), `$hierarchical_codice=:codice`
  (`infoit:resources/tables/orig_item/th_orig_item.py:98`).
- Path che codifica una classificazione, filtrato per prefisso:
  `$hierarchical_child_code ILIKE 'CEE/%%'` (`erpy:model/xbrl.py:98`),
  `$hierarchical_codice like '3/40/85%%'`
  (`frigel_cont:model/_packages/erpy_mag/tipo_prodotto.py:103`).

### 8.3 API e override

- `getHierarchicalData`: 7 chiamate applicative (erpy 5, anaci 1, learn 1).
- `pathFromPkey`, `getHierarchicalPathsFromPkeys`: 0 chiamate applicative.
- `getAncestors`: 1 chiamata applicativa (`pfrc:model/extra.py:103`).
- `fixRowCount`: 1 (`gnrextra:model/question.py:162`).
- Override di `trigger_hierarchical_before/after`: 0. Sottoclassi di
  `HierarchicalHandler`: 0.
- Ridefinizione di una colonna generata: `hlevel` in
  `frigel_cont:.../tipo_prodotto.py:56`.

### 8.4 Interfaccia

Conteggio manuale sulle pagine, errore non misurato.

- `th_options` con `hierarchical=True`: circa 120 file (10 nel framework); con
  `'open'`/`'closed'`: 21.
- Widget con `hierarchical=True` (checkboxtext, dbSelect, queryBySample):
  circa 36 file.
- `hTableTree` diretto: 20 file applicativi.
- `ht_moveHierarchical`: nessuna applicazione lo chiama o lo ridefinisce;
  `moveTreeNode=False` in 12 file applicativi.

### 8.5 Meccanismo `htable`

- `htableFields(tbl)` attivo in 4 tabelle (`mbe:model/item_classification.py:16`,
  `mbe:model/test_htable.py:19`, `icond:model/piano_conti.py:10`,
  `gnrau:model/sla_tree.py:10`); 7 righe commentate.
- `htableHandler(...)` in 7 pagine di 5 applicazioni.
- Conversione esplicita al meccanismo attuale:
  `icond:model/pt_tipo_uscita.py:40` (`convertToNewHierarchical`).

### 8.6 Cose che le applicazioni fanno a mano

- Limite di livelli: «Can't go over the 6th level»
  (`frigel_cont:.../tipo_prodotto.py:190-192`); `hlevel` gestito da 1 a 5
  (`icond:model/pr_pratica.py:339-343`); massimo 3 livelli
  (`anaci:.../esporta_cs.py:40`).
- Lunghezza massima di `hierarchical_codice`: 20 caratteri
  (`frigel_cont:.../tipo_prodotto.py:263`).
- Unicità del codice fra fratelli controllata nel trigger
  (`frigel_cont:.../tipo_prodotto.py:213`).
- Codice progressivo fra fratelli: `frigel_cont:.../tipo_prodotto.py:240`;
  `assignCode` su `hierarchical_child_code` in `pfrc:model/extra.py:135`,
  `pfrc:model/product_type.py:158`, `pfrc:model/stage.py:37`.
- Livello ricalcolato da un path di campo: `erpy:model/conto_gerarchia.py:44`,
  `erpy:model/riclassificazione.py:49`.
- Foglia come formula propria invece di `child_count`:
  `frigel_cont:.../tipo_prodotto.py:43`.
- Resolver di albero scritti a mano su `parent_id`:
  `erpylight:model/_legacy/pr_pratica.py:39`, `genropy:model/mailbox.py:32`.
- Backfill di `root_id` con `touchRecords(where='$root_id IS NULL')` in 4
  upgrade erpy (`lib/upgrades/0001`, `0003`, `0016`, `0018`).
- `WITH RECURSIVE` compare in 5 moduli, tutti su auto-relazioni proprie, non su
  tabelle `sysFields(hierarchical)`.

### 8.7 Non verificato

- Dichiarazioni con `hierarchical` passato da variabile o `**kwargs`.
- Se i duplicati vengono da branch diversi o da copie di package.
- `$parent_id IS NULL`: letta solo la prima pagina (50 moduli, piena).
- Numero di righe delle tabelle gerarchiche: nessun dato trovato.

## 9. Funzioni richieste, in sintesi

Elenco delle funzioni da progettare, ricavato dalle sezioni 1 e 8. Nessuna
decisione presa.

1. Legame col padre e cascata alla cancellazione.
2. Path materializzato della pkey e di uno o più campi.
3. Lettura di sottoalbero, discendenti, antenati e radice. Oggi solo gli
   antenati hanno un'API; il resto è SQL scritto a mano in tre forme diverse.
4. Livello e foglia (`hlevel`, `child_count`).
5. Ordine fra fratelli, con spostamento e riordino.
6. Spostamento di un nodo con riscrittura del sottoalbero.
7. Valori copiati o ereditati dal padre (`copyFromParent`, `hlv`).
8. Radice per ogni record di un'altra tabella (`hierarchical_linked_to`): 1
   uso.
9. Nodi virtuali: 1 uso.
10. Una colonna per livello (`hdepth`): 3 usi, colonne mai lette.
11. Vincoli che le applicazioni scrivono a mano: numero massimo di livelli,
    unicità di un campo fra fratelli, codice progressivo fra fratelli.
12. Controlli assenti nel legacy: cicli, escape di `_` e `/`, concorrenza.

## 10. Decisioni (2026-10-02)

Confermate dall'utente. Non ancora registrate nella proposta 0001.

### 10.1 Modello

- Il modello resta quello del legacy: `parent_id` più path materializzati
  fisici, della pkey (`hierarchical_pkey`) e dei campi (`hierarchical_<fld>`).
- La riscrittura del sottoalbero resta un update per figlio, con i trigger
  Python, per la regola «prima Python».
- Motivo: le tabelle gerarchiche sono molto statiche; spostamenti e rinomine
  sono rari e le letture contano di più. Il costo della cascata non è
  rilevante.

### 10.2 Miglioramenti adottati (rischio basso)

Rischio = quanto il miglioramento cambia comportamento o dati rispetto a un DB
legacy.

- Controllo dei cicli allo spostamento: un nodo che diventerebbe discendente
  di se stesso è un errore (oggi: cascata senza fine, sezione 7).
- Lettura di padre, figli e fratelli senza i filtri di bozza e cancellazione
  logica (oggi: path sbagliati, sezione 7).
- Allo spostamento il nodo prende l'ultima posizione fra i nuovi fratelli
  (oggi: tiene il `_row_count` del vecchio padre).
- Ordine fra fratelli tramite `auto_counter('parent_id')`, con lock sul padre
  durante il calcolo di massimo + 1.
- `_h_count` resta a 2 caratteri in base 36 come nel legacy, compatibile con i
  DB esistenti. Il 1296° fratello sotto lo stesso padre è un errore esplicito
  all'insert (oggi: stringa vuota e ordinamento rotto). Un parametro per la
  larghezza è stato valutato e scartato: l'ordine manuale riguarda pochi
  fratelli.
- Escape di `_` e `%` in ogni LIKE sui path generato dal nucleo.
- Su PostgreSQL l'indice del path è creato con `text_pattern_ops`.
- Il nucleo offre sottoalbero, antenati e radice, con «nodo incluso» o «nodo
  escluso» esplicito. La forma va decisa insieme a GEP 1 e `virtualRelation`.

### 10.3 Aperti (rischio medio)

- Valore nullo in un campo del path come errore: i dati esistenti con valori
  nulli non si potrebbero più scrivere.
- `/` dentro un valore come errore o codificato: stesso problema per i valori
  che lo contengono.
- `copyFromParent` solo all'insert e allo spostamento: cambia la propagazione
  rispetto al legacy.
- `_parent_h_*` calcolato invece che fisico: le colonne esistono nei DB legacy.

### 10.4 Fuori dal primo incremento

- `hierarchical_linked_to`, nodi virtuali, `hdepth`: da 1 a 3 usi ciascuno
  (sezione 8.1).
