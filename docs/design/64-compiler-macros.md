# 64 — Macro del compilatore

Stato al **16 ottobre 2026**, sul percorso unico consegnato nel
[rapporto 98](98-single-read-path.md). Capitolo separato dalla
[checklist generale](58-compiler-checklist.md): distingue supporto verificato,
contratti ancora da valutare e rinvii espliciti. Non introduce nuove sintassi.

Il raccordo di IN_RANGE, PERIOD, THIS e riferimenti select_* segue il
[rapporto 90](90-legacy-rewrite-phase4.md). IN_RANGE riusa la correzione
approvata che antepone i confronti tipizzati ai controlli NULL per PostgreSQL.
Il compilatore precedente e lo scanner sono eliminati: valgono gli algoritmi
regex legacy, senza promettere le protezioni del vecchio scanner.

## Stato

| Stato | Costrutto | Copertura attuale |
| --- | --- | --- |
| 🟢 Implementato | `#IN_RANGE(value, low, high)` | WHERE e formule SQL, anche native |
| 🟢 Implementato | `#PERIOD(field, :period)` | WHERE della query e delle sottoquery supportate |
| 🟢 Implementato | `#THIS.field` / `#THIS.@relation.field` | Riferimenti alla tabella proprietaria nelle formule e nelle correlazioni |
| 🟢 Implementato | `#nome` associato a `select_nome` | Inserimento della sottoquery nominata nella formula |
| 🟡 Contratto da valutare | `#ENV` | Espansione legacy non implementata; `:env_nome` è già disponibile ma distinto |
| 🟡 Contratto da valutare | TSQUERY, TSRANK, TSHEADLINE, VECQUERY, VECRANK | Macro full-text/vettoriali non implementate |
| 🟡 Contratto da valutare | BAG, BAGCOLS | Parte SQL non implementata; da distinguere dai codec dei risultati |

Il giallo indica che manca anche il confronto conclusivo sul perimetro da
portare. Queste voci non sono funzionalità parzialmente utilizzabili né
autorizzano automaticamente l'importazione di tutti i comportamenti legacy.

## 🟢 Intervalli: `#IN_RANGE`

```python
q = db.table('sales.invoice').query(
    '$id', where='#IN_RANGE($total, :minimum, :maximum)',
    minimum=100, maximum=None,
)
compiled = q.compiled
sql, kwargs = compiled.sql, dict(compiled.params)
```

Gli estremi sono inclusivi. Un limite NULL lascia aperto quel lato;
entrambi NULL rendono il predicato vero, anche se il valore è NULL.
Si conserva la grammatica legacy degli argomenti semplici: campi, percorsi
e parametri. Non è un contenitore per espressioni arbitrarie negli argomenti.
L'ordine dei confronti permette a PostgreSQL di inferire il tipo dei limiti NULL.

## 🟢 Periodi: `#PERIOD`

```python
q = db.table('sales.invoice').query(
    '$id', where='#PERIOD($issued, :period)', period='mese scorso',
)
```

Nell'esempio `issued` è una colonna DATE e l'ambiente fornisce `workdate`
e `locale='it'`. L'espansione usa il decoder già presente in Toolbox:
un giorno genera un'uguaglianza; un intervallo chiuso un BETWEEN inclusivo;
un intervallo aperto un confronto su un solo estremo. Un periodo vuoto non
restringe il filtro. Il colon davanti al nome del parametro è facoltativo.

Il testo del periodo viene consumato per espandere il WHERE; il parametro
originale resta nei kwargs del chiamante secondo il contratto legacy. Le date
risultanti hanno binding separati, senza sovrascrivere quelli del chiamante.
Il supporto attuale è nel WHERE, non in una proiezione SQL arbitraria.
La verifica dei casi documentati non certifica tutti i locali del legacy.

## 🟢 Correlazioni e sottoquery nominate

`#THIS.id` indica il campo della tabella proprietaria della formula, mentre
`$id` dentro una sottoquery indica il campo della tabella della sottoquery.
I percorsi dopo `#THIS` usano le relazioni verso uno già supportate.
I percorsi verso molti sono esplicitamente non supportati: non vengono
generate righe esplose né aggregazioni automatiche.

Con `select_total=dict(...)`, il riferimento `#total` inserisce quella
sottoquery nell'espressione della formula. È un riferimento locale alla
dichiarazione, non una nuova macro globale registrabile. Gli alias SQL e
i parametri delle sottoquery mantengono scope distinti.

## 🟡 Macro da valutare

- **`#ENV`:** confrontare l'espansione legacy, che legge currentEnv e può
  ricorrere ai metodi `env_<nome>` delle tabelle. Il secondo argomento ha
  anche usi legacy come chiave di ambiente o identificazione della tabella;
  non va reinterpretato automaticamente come un semplice valore di default.
  La lettura parametrizzata `:env_nome` esistente non copre questo contratto.
- **Full-text e vettori:** censire firme e test legacy; separare espansione
  della macro, costrutti del dialetto e dipendenze applicative. L'accettazione
  di SQL esplicito non equivale al supporto delle macro.
- **BAG/BAGCOLS:** macro ancora da valutare. L’estrazione SQL di bagItemColumn
  è raccordata nel [rapporto 69](69-native-bag-items.md), senza abilitare queste macro.
  Conversioni e codec successivi all'esecuzione restano un lavoro distinto.

## Garanzie comuni e verifiche

L'espansione usa le regex legacy. Non si certifica protezione da riscrittura
per commenti, literal o identificatori quotati. I token macro non espansi
vengono rifiutati; il codice non costituisce una validazione di SQL non fidato.
I valori parametrizzati restano nei binding e la compilazione non esegue query.
`#THIS` nelle formule è espanso prima della raccolta dei riferimenti.

Riferimenti attuali: `src/asqueel/compiler.py` (`_TreeContext.formula`,
`subquery`, `select_plan`, `expand_period`, `_check_macros`), gli algoritmi
in `_legacy_sql.py` e gli scope dei parametri in `_sql_bindings.py`.

Test sul percorso unico: `tests/object_tree/test_phase4_macros.py`,
`test_phase3_formulas.py`, `tests/native_formulas/test_tree_phase4_macros.py`
e i contratti delle formule native. Il [rapporto 98](98-single-read-path.md)
riporta il risultato della selezione letture completa; i rapporti precedenti
restano fonti storiche, non attestazioni del vecchio percorso ancora disponibile.

## Esclusione concordata

`#PREF` è **non portato e fuori dal lavoro corrente**, secondo
[R-08 del registro dei rinvii](41-deferred-features.md#r-08--macro-pref).
Non compare nella TODO attiva delle macro. La dichiarazione esistente resta
conservata, senza sostituzione automatica con il default.
