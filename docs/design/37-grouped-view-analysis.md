# 37 — Analisi della grouped view del legacy

Stato: analisi, nessuna decisione presa. Serve a progettare in asqueel il
raggruppamento codeless che il legacy offre in ogni TableHandler, compresi i
raggruppamenti lungo una tabella gerarchica (documento 36).

Riferimenti: genropy `origin/develop` `5e7f02e8d774`, letto con `git show`.
Prova in browser il 2026-10-02 sull'istanza `test_invoice_pg`, pagina
`/sys/thpage/invc/invoice_row`, utente `amelia.martin`. L'uso nelle
applicazioni viene dall'indice Sourcerer (sezione 7).

Abbreviazioni: `groupth.py` = `resources/common/th/th_groupth.py`; `groupth.js`
= `resources/common/th/th_groupth.js`; `framegrid.py` =
`resources/common/gnrcomponents/framegrid.py`; `th_view.py` =
`resources/common/th/th_view.py`; `viewconf.js` =
`resources/common/th/th_viewconfigurator.js`; `grid.js` =
`gnrjs/gnr_d11/js/genro_grid.js`; `comp.js` =
`gnrjs/gnr_d11/js/genro_components.js`; `tree.js` =
`gnrjs/gnr_d11/js/genro_tree.js`; `dev.js` = `gnrjs/gnr_d11/js/genro_dev.js`.

## 1. Funzioni offerte

- Raggruppamento di qualunque vista TableHandler senza scrivere codice.
- Campi scelti trascinandoli dall'albero dei campi, anche attraverso relazioni
  (Invoice → Customer → State Name).
- Ogni colonna ha un modo:
  - testo: Break, No break, Count distinct;
  - numero: Sum, Average, Min, Max, Break, No break;
  - data: un formato `to_char` (`YYYY`, `YYYY-MM`, ...).
- Conteggio delle righe per gruppo (`_grp_count`).
- Vista piatta (Flat) e vista ad albero (Hierarchical / Tree View): i livelli
  dell'albero sono le colonne Break in ordine; i totali salgono ai padri.
- Pivot (In pila / Stacked): l'ultima dimensione di raggruppamento diventa
  colonne.
- Drill-down: un clic su un gruppo mostra le righe di quel gruppo.
- Salvataggio della vista con codice, nome, autorizzazione, note, privata o no.
- Dashboard di raggruppamento salvate.
- Esportazione.

## 2. Le due interfacce

### 2.1 Pannello `Σ` a sinistra

- Si apre con l'icona gialla in basso a sinistra della vista. È il tab di un
  pannello `closable` largo 300px (`framegrid.py:222-248`, colore a `:224`,
  icona a `:231`).
- È `th_groupByTableHandler` (`groupth.py:36`) in modalità `grouper`, con
  `linkedTo` uguale alla vista principale e `configurable=False`
  (`framegrid.py:251-266`). Si attiva quando la vista è `configurable` con
  `extendedQuery=='*'` (`th_view.py:397-405`).
- Toolbar: selettore delle viste, ricerca, toggle `Flat` / `Hierarchical`
  (`framegrid.py:326-334`). Non c'è la modalità Stacked.
- Titolo «Empty View»: è la docstring di `_thg_defaultstruct`
  (`groupth.py:251`), mostrata da `viewsSelect` (`framegrid.py:215-218`).
- Drawer dei campi: linguetta grigia a metà altezza, `viewConfigurator` con
  `fieldsTree(... trash=True)` (`framegrid.py:284`, `:374`, `:399-405`).
  L'ingranaggio del drawer ha «Vista Favorite», «Salva vista», «Elimina vista»,
  «Configuratore completo».
- Con più di una colonna Break il pannello passa da solo a Hierarchical
  (`framegrid.py:268-272`).

### 2.2 «Raggruppa per» della toolbar

- Si apre con l'icona `Σ` della toolbar (`th_slotbar_stats`,
  `th_view.py:900-902`). Sostituisce la vista principale nello stesso
  stackContainer (`th_view.py:547-562`; `framegrid.py:420`, `:438`).
- È lo stesso `th_groupByTableHandler`, in modalità completa: toolbar con
  «Visualizzazione a griglia» / «Tree View», «Piatto» / «In pila»,
  «Controcolonna» (`groupth.py:148-160`, `:262`).
- «Controcolonna» aggiunge o toglie la colonna del conteggio `_grp_count`
  (`groupth.py:152-159`; traduzione in `localization.xml:835`). La pivot è
  «In pila» (`localization.xml:837`).
- Ha un pannello di dettaglio in basso con le righe del gruppo scelto
  (`groupth.py:66-90`, `_thg_details_rows` `:367-384`).

### 2.3 Codice in comune

- Store `_thg_groupByStore` (`groupth.py:187-247`), metodo server
  `_thg_selectgroupby` (`groupth.py:388-513`), tree view `_thg_treeview`
  (`groupth.py:312-363`), `buildGroupTree` e `groupTreeData` (`groupth.js:16-108`).
- Differenza nel clic su un gruppo:
  - pannello di sinistra: scrive `grouperPkeyList` e ricarica la griglia
    principale (`framegrid.py:274-324`);
  - «Raggruppa per»: scrive `details_pkeylist` e carica il proprio dettaglio
    (`groupth.py:66-68`, `:375-384`).

## 3. Definizione delle colonne

- L'albero dei campi arriva dall'RPC `relationExplorer`
  (`dev.js:288-293`; `gnrpy/gnr/web/gnrwebpage.py:2825-2861`;
  `gnrpy/gnr/sql/gnrsqltable/utils.py:456-569`;
  `gnrpy/gnr/sql/gnrsqlmodel/resolvers.py:167`). Ogni nodo porta gli attributi
  della colonna, quindi anche `hierarchical_field_of`.
- Il drag copia tutti gli attributi del nodo (`dev.js:333-337`).
- Il drop apre «Add column» (`viewconf.js:87-100`; `groupth.js:303-334`):
  Caption, Modo, Empty value (`[NP]`).
- `mixin_addColumn` costruisce la cella con `width`, `name`, `dtype`, `field`,
  `tag`, `formulaVariant`, `_owner_package` e gli attributi `cell_*`
  (`grid.js:2186-2199`). Un `field` più lungo di 63 caratteri riceve un alias
  `relation_<hash>_...` in `queryfield` (`grid.js:2192-2196`).
- `hierarchical_field_of`, `table` e `related_table` non entrano nella cella
  (`grid.js:2186-2199`).
- La colonna si toglie trascinandola fuori dalla griglia; le colonne si
  riordinano trascinando le intestazioni (`viewconf.js:81`; `comp.js:6185-6194`).
- Vista salvata osservata nel DB (`adm.adm_userobject`, `code='tipo_stato'`,
  `objtype='grpview'`): una `cell` per colonna con `field`, `name`, `dtype`,
  `mode="break"`, `group_aggr`, `group_empty`, `width`. Nessuna informazione
  sulla gerarchia.

## 4. Flusso dei dati

- Lo store è un `selectionStore` con `selectmethod=_thg_selectgroupby`
  (`groupth.py:193-219`). Prima della chiamata legge gli attributi dello store
  della vista principale, cioè la sua query (`groupth.py:198-218`;
  `gnrjs/gnr_d11/js/gnrdomsource.js:950-955`).
- `_thg_selectgroupby` (`groupth.py:388-513`):
  - numeri: `<aggr>($col) AS <field>_<aggr>`, `sum` di default (`:430-434`);
  - HAVING da `not_zero`, `min_value`, `max_value`, uniti con OR (`:436-447`,
    `:492`);
  - date: `to_char(col,'fmt')` nel GROUP BY (`:452-459`);
  - `distinct` / `distinct_count`: `string_agg(CAST(col AS TEXT),'|')`
    (`:460-465`);
  - Break: la colonna nel GROUP BY, con l'eventuale `caption_field`
    (`:466-478`);
  - sempre `count(*) AS _grp_count_sum` e
    `string_agg(CAST($pkey AS TEXT),',') AS _pkeylist` (`:482-487`);
  - `order_by` = colonne Break, salvo `groupOrderBy` (`:488-490`);
  - senza colonne Break restituisce `False` (`:483-484`);
  - dopo la query: valore vuoto → `group_empty` o `[NP]`; `distinct_count`
    deduplicato; `_thgroup_pkey` = chiavi Break unite con `|` (`:497-512`).
- `group_aggr` arrivato dal client entra nell'SQL come testo:
  `f'{group_aggr}({col})'` (`groupth.py:430-434`) e
  `to_char({col},'{group_aggr}')` (`:453`).
- Flat: la griglia `flatview` (`groupth.py:107-114`).
- Hierarchical: `groupTreeData` (`groupth.js:72-108`) crea un path per riga,
  un segmento per colonna Break, con `flattenString(description,['.','?','#'])`
  (`groupth.js:98`; `gnrjs/gnr_d11/js/gnrlang.js:2289-2297`). Il `/` resta
  dentro il segmento. Il widget è un `treeGrid` (`groupth.js:16-48`;
  `comp.js:2470-2592`).
- Stacked: `getPivotGrid` (`groupth.js:168-302`). L'ultima colonna di
  raggruppamento diventa colonne (valori distinti più `TOTALS`); le colonne
  pivot hanno un solo livello.

## 5. Risalita dei totali (`groupth.js:110-166`)

- `*_sum` (anche `_grp_count_sum`): somma.
- `*_avg`: media pesata su `_grp_count_sum`.
- `*_min`, `*_max`: minimo e massimo.
- `*_distinct`: unione degli insiemi separati da `|`, più `_count`.
- Formule: rivalutate dopo ogni figlio (`groupth.js:141-143`).
- `_pkeylist` del padre: concatenazione di quelle dei figli
  (`groupth.js:139`). Selezionare un nodo intermedio passa le pkey di tutto il
  sottoalbero (`tree.js:978-987`).
- `[NP]`: un solo nodo `[NP]` alla radice o in un ramo viene tolto e il suo
  contenuto sale di un livello (`groupth.js:113-115`, `:130-134`).

## 6. Drill-down e concatenamento

- Pannello di sinistra, Flat: le righe selezionate raccolgono `_pkeylist` in
  `grouperPkeyList` (`framegrid.py:274-282`); la griglia principale ricarica
  con `condition='$pkey IN :currpkeylist'` e `query_reason='grouper'`
  (`framegrid.py:308-324`; `th_view.py:1344-1347`).
- Pannello di sinistra, Hierarchical: il nodo scelto scrive il suo `_pkeylist`
  (`tree.js:978-987`).
- Osservato in browser: il clic su «Tasmania» (133) mostra 133 righe; il clic
  sul nodo «Building Materials/Insulation/Foam Board» (8) in Hierarchical ne
  mostra 8.
- I due pannelli si usano insieme (indicazione dell'utente). Dal codice letto il
  «Raggruppa per» riesegue la query della vista principale e non legge
  `grouperPkeyList` (`groupth.py:202-245`). Contraddizione da verificare nel
  payload di `_thg_selectgroupby`.

## 7. Uso nelle applicazioni (Sourcerer)

Metodo: `code_search_code` a pagine da 50 moduli fino alla pagina vuota,
deduplicato per repo:path; `genropy` contato a parte. Le viste salvate dagli
utenti stanno nei DB delle istanze e Sourcerer non le indicizza.

| Elemento | Moduli app | Repository app |
|---|---|---|
| chiamate `groupByTableHandler(` | 22 | 11 |
| strutture `th_groupedStruct*` | 173 (329 metodi) | 24 |
| `linkedGroupByAnalyzer` | 0 | 0 |
| `groupMode='stackedview'` attivo | 1 | 1 |
| `getPivotGrid`, `treeRoot=` | 0 | 0 |

- `th_groupedStruct*` per repository: teamset 46, anaci 29, erpy 18,
  teamset_v1 15, colto 12, anaci_soci 7, frigel_cont 6, gnrgh 4, altri 16
  repository da 1 a 3.

| `group_aggr` / opzione | Moduli app |
|---|---|
| `sum` su `_grp_count` | 117 |
| `sum` su un campo | 109 |
| `YYYY-MM` | 15 |
| `YYYY` | 14 |
| `YYYY-WW` | 8 |
| `group_aggr=False` | 7 |
| `group_empty` | 5 |
| `avg`, `min`, `max` | 2 ciascuno |
| `distinct`, `distinct_count`, `not_zero`, `min_value`, `max_value`, `queryfield` | 0 |

- Raggruppamenti su un path gerarchico: 5 moduli in erpy ed erpylight (per
  esempio `erpy:resources/tables/movimento_industriale/th_movimento_industriale.py:93`,
  `@unita.@gerarchia_id.hierarchical_descrizione`). Raggruppano tutti per path
  completo, senza totali dei nodi intermedi.
- Colonne per livello di `hdepth` (`hierarchical_nome_02`): 4 righe, tutte
  commentate.
- Workaround: `split_part(...hierarchical_descrizione,'/',2)` con `group_by`
  (`frigel_cont:resources/tables/_packages/erpy_fatt/fattura/action/export_trimestre.py:32`,
  `:35`); somme per livello scritte a mano (issue `anaci/anaci#203`;
  docstring di `anaci:packages/anc_cnt/lib/bilancio_io.py`).
- Altri meccanismi per lo stesso bisogno: `group_by=` nelle query applicative in
  184 moduli di 30 repository; `selection.totalize(` in 7 moduli;
  `AnalyzingBag` in 13 moduli; override di `stats_group_by` in 3 moduli.
- Issue aperta: genropy/genropy#893, classificazione JS delle colonne che
  ignora la somma numerica di default.

## 8. Difetti e punti aperti del legacy

- Nessun codice di raggruppamento conosce le tabelle gerarchiche: il `/` non
  viene spezzato e i nodi intermedi non esistono (sezione 4; verificato in
  browser).
- `group_aggr` dal client entra nell'SQL come testo (sezione 4).
- Nel dialog «Add column», «No break», `not_zero`, `min_value` e `max_value`
  sono scritti senza il prefisso `cell_` (`groupth.js:327-351`) e
  `mixin_addColumn` copia solo `cell_*` (`grid.js:2197`): non arrivano alla
  cella. Verificato.
- `group_nobreak` non è letto dal server: una cella «No break» senza
  `group_aggr` entra comunque nel GROUP BY (`groupth.py:466-470`).
- `_pkeylist` concatena tutte le pkey di ogni gruppo: il peso cresce con le
  righe.
- Con un nodo che ha righe proprie e figli, `_avg` perde il peso delle righe
  del nodo (`groupth.js:151-153`).
- `thgp_linkedGroupByAnalyzer` (`groupth.py:546-568`) non ha chiamanti.
- Interfaccia, osservato in browser:
  - icona `Σ` e linguetta del drawer piccole e senza etichetta;
  - rimozione di una colonna solo trascinandola fuori, senza segnale;
  - lingue mescolate («Cerca», «Raggruppa per», «Modo» accanto a
    «Add column», «Confirm», «Flat»);
  - caption tecniche (`@product_id.product_type_id`, «Invoice/Customer/State
    Name»);
  - in Hierarchical il selettore delle viste mostra solo «Empty View»;
  - il clic su «Flat» non viene preso dopo la chiusura del menu delle viste;
  - la voce di menu «Invoice rows» della home non ha aperto la pagina.

## 9. Correzione possibile nel legacy

- Portare `hierarchical_field_of` nella cella: da `addColumnCb`, che ha i dati
  del drag (`groupth.js:314`), o da `cellFromField`
  (`gnrpy/gnr/web/gnrwebstruct/_helpers.py:79-112`), o letto dal modello in
  `_thg_selectgroupby` e restituito nella risposta.
- In `groupTreeData` (`groupth.js:91-103`), per una cella gerarchica, spezzare
  il valore sul `/` e aggiungere un livello per segmento.
- I totali dei nodi intermedi e il loro `_pkeylist` li calcola già
  `updateBranchTotals`.
- Vale per entrambe le interfacce e per le viste salvate, che conservano la
  cella.
- Limiti: la pivot resta a un livello; il passaggio automatico a Hierarchical
  conta solo le colonne Break (`framegrid.py:271`).

## 10. Requisiti per asqueel, in sintesi

Elenco ricavato dalle sezioni precedenti. Divisione nucleo/adattatore
approvata dall'utente come direzione; nessuna decisione di dettaglio presa.

1. Richiesta di raggruppamento dichiarativa e serializzabile, compilata dal
   resolver unico; aggregati da un elenco chiuso.
2. Break gerarchici con nodi intermedi a qualsiasi profondità.
3. Regole di risalita uniche per albero, pila e pivot, calcolate in Python
   sopra un GROUP BY SQL piatto.
4. Drill-down per condizione invece che per elenco di pkey.
5. Concatenamento: la condizione di un gruppo filtra un nuovo raggruppamento.
6. Pivot nel nucleo, anche su una dimensione gerarchica.
7. Metadati del modello per l'interfaccia: relazioni, dtype, caption
   leggibili, campo gerarchico.
8. L'adattatore GenroPy traduce la `struct` legacy nella richiesta e il
   risultato nella forma attesa (`_grp_count_sum`, `_pkeylist`,
   `_thgroup_pkey`).
