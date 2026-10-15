# 64 — Macro del compilatore

Il raccordo di IN_RANGE, PERIOD, THIS e riferimenti select_* al nuovo albero
è descritto nel [rapporto 90](90-legacy-rewrite-phase4.md). IN_RANGE riusa,
con approvazione esplicita, la correzione esistente che antepone i confronti
tipizzati ai controlli NULL per il binding PostgreSQL. Le garanzie scanner delle note storiche seguenti
riguardano soltanto il compilatore precedente, non il nuovo percorso regex legacy.

Stato al **14 ottobre 2026**. Capitolo separato dalla
[TODO generale](58-compiler-checklist.md): distingue supporto verificato,
contratti ancora da valutare e rinvii espliciti. Non introduce nuove sintassi.

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

Il testo del periodo viene consumato durante la compilazione: nei kwargs
arrivano le date risultanti, con nomi che non sovrascrivono quelli del chiamante.
Il supporto attuale è nel WHERE, non in una proiezione SQL arbitraria.
La verifica dei casi documentati non certifica tutti i locali del legacy.

## 🟢 Correlazioni e sottoquery nominate

`#THIS.id` indica il campo della tabella proprietaria della formula, mentre
`$id` dentro una sottoquery indica il campo della tabella della sottoquery.
I percorsi dopo `#THIS` usano le relazioni ordinarie già supportate. Un percorso
inverso può moltiplicare le righe nel SELECT a cui appartiene: non viene
aggiunta automaticamente un'aggregazione.

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

🟢 Stringhe SQL, commenti e identificatori quotati sono protetti durante
l'espansione. Le macro sconosciute nei contesti SQL vengono rifiutate
esplicitamente. I valori restano nei binding; l'espansione non esegue query.

Riferimenti di implementazione: `src/asqueel/compiler.py`, metodi
`_Context.where`, `_period`, `field` ed `expression`, e l'allocatore esistente
in `_compiler_bindings.py`.

Test: `tests/native_compiler/test_query_macros.py`, `test_compile_only.py`,
test di formule/sottoquery e test delle inverse. I
[rapporti 60](60-native-sql-formulas.md), [61](61-native-subqueries.md) e
[63](63-native-inverse-relations.md) documentano i rispettivi incrementi.

## Esclusione concordata

`#PREF` è **non portato e fuori dal lavoro corrente**, secondo
[R-08 del registro dei rinvii](41-deferred-features.md#r-08--macro-pref).
Non compare nella TODO attiva delle macro. La dichiarazione esistente resta
conservata, senza sostituzione automatica con il default.
