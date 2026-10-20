# 101 — Aggregazioni sulle relazioni verso molti

Decisioni del 16 ottobre 2026. **Grammatica concordata; count/numerici nel [passo 103](103-numeric-many-aggregates.md), join e ordine nel [passo 104](104-join-ordered-many-aggregates.md), JSON nel [passo 105](105-json-many-aggregates.md), XML Bag PostgreSQL nel [passo 106](106-xml-many-aggregates.md).**
Questo documento sostituisce le precedenti proposte di metodi separati sulle
relazioni verso molti. Non modifica compilatore, renderer o scritture.

## Perimetro

Le relazioni ordinarie verso molti e le virtualRelation verso molti seguono
la stessa regola: in proiezione richiedono un'aggregazione esplicita.
`@invoices` da sola e `@invoices.total` non sono proiezioni ammesse.
Non si producono righe esterne esplose attraverso JOIN verso molti.

Nella dichiarazione `virtualRelation(..., relation='@invoices')`, invece,
`relation` identifica la relazione di partenza: non è una proiezione e non
richiede `.aggr()`.

Le virtualRelation servono alle relazioni verso molti filtrate/parametrizzate,
non alle abbreviazioni di percorsi verso uno. Per un alias di colonna che eredita
una relazione vale il [raccordo 100](100-alias-relation-inheritance.md).
Questa grammatica di aggregazione è una decisione nuova di Asqueel; non viene
presentata come porting di una sintassi legacy.

## Unico metodo di aggregazione: .aggr()

Si mantiene soltanto `.aggr(...)`. Non si introducono i metodi diretti
`.count()`, `.sum()`, `.avg()`, `.min()` o `.max()` sulla relazione.
Le funzioni di aggregazione sono espresse dentro `.aggr()`:

```text
@invoices.aggr(count())
@invoices.aggr(sum($total), min(total), avg(iva))
@invoices.aggr(join($code, '-') AS hhh, sum($totale))
```

Sono concordate `count`, `sum`, `avg`, `min`, `max`, `join`, `to_json` e `to_xml`.
`count()` senza argomenti conta le righe correlate; senza righe restituisce 0.
`join` concatena i valori delle righe correlate con il separatore indicato.
Il nome grammaticale `join` non impone una funzione SQL uguale nei vari dialetti:
la traduzione SQL deve passare dagli adapter.

Resta il requisito già concordato di poter sommare una o più colonne, con lo
stesso principio per `avg`, `min` e `max`: ogni argomento produce un aggregato
separato. Non significa sommare fra loro gli argomenti della stessa riga.
**Decisione approvata:** gli alias si scrivono sui singoli argomenti:

```text
@invoices.aggr(sum($netto AS netto_sum, $iva AS iva_sum))
```

Si producono due colonne indipendenti, `netto_sum` e `iva_sum`. Senza `AS`
valgono i nomi automatici `_invoices_netto_sum` e `_invoices_iva_sum`.
La stessa regola vale per `avg`, `min` e `max`; non si assegna un unico alias
all'intero risultato multiplo.

## Espressioni e ambito dei riferimenti

Gli argomenti possono essere colonne oppure espressioni SQL, non soltanto nomi
di colonna. I riferimenti appartengono alla tabella raggiunta dalla relazione.
Sono accettati i riferimenti `$campo` e i nomi semplici mostrati nell'esempio
concordato `min(total), avg(iva)`.

**Chiarimento approvato:** gli argomenti possono contenere anche formulaColumn
e campi raggiunti attraverso relazioni, con la stessa risoluzione della query.
Il contesto di partenza è la tabella correlata: non si limita la selezione alle
colonne fisiche e non si introduce un risolutore separato. Questo vale anche
per i campi raccolti da `to_json` e `to_xml`. Restano i vincoli già concordati
sui percorsi verso molti, che richiedono aggregazione esplicita.

```text
@invoices.aggr(sum($price * $qty) AS totale)
```

Qui si somma il prodotto calcolato su ciascuna riga correlata; non si moltiplicano
la somma dei prezzi e la somma delle quantità. Non si introduce una nuova
grammatica generale delle espressioni né una validazione per SQL non fidato.

## Risultato e alias

Il risultato è una tupla logica di colonne da espandere nella proiezione:
una colonna per ogni aggregato richiesto. Non si impacchetta l’intera `.aggr()`
in una sola colonna. Le singole funzioni `to_json` e `to_xml`, invece, producono
ciascuna una colonna contenente la raccolta delle righe correlate.

```text
@invoices.aggr(sum($netto) AS sxd, sum($iva) AS fff)
@invoices.aggr(sum($netto), sum($iva), avg($iva))
@invoices.aggr(join($code, '-') AS hhh, sum($totale))
```

- L'alias esplicito `AS` assegna il nome alla singola colonna prodotta.
- Senza alias esplicito, per una colonna semplice si usa
  `_<relazione>_<colonna>_<aggregazione>`: `_invoices_netto_sum`,
  `_invoices_iva_sum`, `_invoices_iva_avg`, `_invoices_totale_sum`.
- **Decisione approvata per `count()`:** senza `AS` si usa
  `_<relazione>_count`, quindi `@invoices.aggr(count())` produce
  `_invoices_count`. Un alias esplicito prevale:
  `@invoices.aggr(count() AS numero)` produce `numero`.
- **Decisione approvata per le raccolte senza colonne esplicite:**
  `@invoices.aggr(to_json())` produce `_invoices_json`;
  `@invoices.aggr(to_xml())` produce `_invoices_xml`.
  Anche in questi casi l'alias esplicito `AS` prevale.
- **Decisione approvata per `join`:** l'alias automatico usa relazione e
  campo, escludendo separatore e placeholder. Sia `join($code, ',')` sia
  `join($code, ';', '-empty-')` su `@invoices` producono
  `_invoices_code_join`. L'alias esplicito `AS` prevale.
- Si possono mescolare alias espliciti e automatici nella stessa `.aggr()`.
- **Collisioni: prevale l'ultima dichiarazione.** Se più colonne hanno lo
  stesso alias, esplicito o automatico, rimane l'ultima dichiarata per quel
  nome. Non si solleva un errore e non si generano rinomine automatiche.
- Per le espressioni si riusa il flattener esistente (`col_to_as`, corrispondente
  al `colToAs` legacy), senza inventare un algoritmo di normalizzazione.
  Il [passo 107](107-outer-as-projections.md) distingue AS esterno da AS dentro
  CAST usando lo splitter esistente. Anche to_xml accetta CAST senza alias
  dichiarato; due CAST allo stesso tipo rimangono due colonne.

## join: separatore e placeholder

```text
@invoices.aggr(join($code, ',') AS codici)
@invoices.aggr(join($code, ',', '-empty-') AS codici)
```

Il secondo argomento è il separatore. Il terzo è il placeholder del **singolo
valore vuoto** e, se omesso, vale `''`. La posizione del valore vuoto viene
conservata, con i relativi separatori. Per valori `xx`, vuoto, `zz`:

| Espressione | Risultato |
| --- | --- |
| `join($code, ',')` | `xx,,zz` |
| `join($code, ',', '-empty-')` | `xx,-empty-,zz` |
| `join($code, ',', 'null')` | `xx,null,zz` |

`'null'` è solo un possibile testo del placeholder, senza significato SQL
speciale. Il placeholder non è il default per un insieme senza righe.
**Decisione approvata:** il placeholder sostituisce sia `NULL` SQL sia la
stringa vuota `''` nella singola riga. Non si aggiungono altre normalizzazioni
implicite (per esempio il trim degli spazi).

## to_json e to_xml

```text
@invoices.aggr(to_json() AS fatture)
@invoices.aggr(to_xml() AS fatture)
@invoices.aggr(
    to_json($number, $total) AS fatture_json,
    to_xml($number, $total) AS fatture_xml
)
```

- `to_json` raccoglie le righe correlate in un array JSON di oggetti.
- `to_xml` raccoglie le righe correlate in **XML compatibile con Bag**.
  Sostituisce soltanto il nome precedentemente proposto `to_bag`: non cambia
  il formato in XML generico e non introduce un sinonimo pubblico.
- Entrambe le aggregazioni devono essere prodotte in SQL, con traduzione
  delegata agli adapter; non assemblate dopo il fetch in Python.
- Gli argomenti seguono la selezione delle colonne della query, comprese
  formule, alias e colonne statiche. Senza argomenti vale l'espansione di `*`
  della query, **incluse le statiche**: nessuna selezione separata limitata alle
  sole colonne fisiche e nessun nuovo espansore dedicato.
- Con argomenti sono incluse soltanto le colonne richieste. Gli alias della
  selezione nominano i campi; l'`AS` dopo la funzione nomina la colonna esterna
  contenente JSON/XML.

**Etichette delle righe XML approvate:** `r_0`, `r_1`, …, posizionali secondo
l'ordine della raccolta. Ogni nodo contiene i campi della riga; non è necessario
includere la primary key nella selezione.

Per XML occorre verificare la compatibilità con il serializer Bag esistente,
compresi tipi e NULL. Non viene definito qui un nuovo formato. Il risultato rimane XML; questa decisione non introduce una conversione
a oggetti Bag nel fetch.

PostgreSQL offre `json_agg`/`json_build_object`/`row_to_json` e
`xmlelement`/`xmlattributes`/`xmlforest`/`xmlagg`. SQLite offre
`json_group_array`/`json_object`, ma non equivalenti XML nativi.
Sono strumenti disponibili, non un'implementazione già certificata:
[JSON PostgreSQL](https://www.postgresql.org/docs/current/functions-json.html),
[XML PostgreSQL](https://www.postgresql.org/docs/18/functions-xml.html),
[JSON SQLite](https://www.sqlite.org/json1.html),
[funzioni SQLite](https://www.sqlite.org/lang_corefunc.html).
**Capability concordate:** `to_xml` è previsto su PostgreSQL. SQLite non ha
questa capability: la richiesta deve risultare non supportata, senza fallback
o emulazione. Non è un requisito da implementare successivamente su SQLite.
`to_json` è implementato su entrambi i dialetti nel [passo 105](105-json-many-aggregates.md).
`to_xml` è implementato su PostgreSQL nel [passo 106](106-xml-many-aggregates.md).

## Ordine base e .order_by(...)

L'ordine base della tabella raggiunta dalla relazione si applica
**automaticamente**. `.order_by(...)` serve soltanto a sostituirlo, usando la
stessa sintassi di ordinamento della query:

```text
# Ordine base della tabella delle fatture
@invoices.aggr(join($code, ',') AS codici, to_json() AS fatture)

# Ordine esplicito al posto di quello base
@invoices.order_by('$date DESC, $id').aggr(
    join($code, ',', '-empty-') AS codici,
    to_json($number, $total) AS fatture_json,
    to_xml($number, $total) AS fatture_xml
)
```

L'ordine scelto è comune alle aggregazioni della chiamata ed è significativo
per `join`, `to_json` e `to_xml`. I riferimenti appartengono alla tabella
correlata; è possibile ordinare per colonne non incluse nel risultato.
Non è l'ordine delle righe della query esterna. Se mancano sia l'ordine base
sia quello esplicito, l'ordine interno non è garantito; non si inventa un
ordinamento di fallback.

Il nome definitivo è `.order_by(...)`, senza sinonimo `.sorted(...)`.
Questa decisione sostituisce la proposta di un parametro `order_by` interno
alle singole funzioni. Non reintroduce `order_by` nella dichiarazione del
modello `virtualRelation`: l'override appartiene all'uso nella query.

## Nessuna riga correlata

Risultati approvati, da produrre in SQL:

| Aggregazione | Risultato senza righe correlate |
| --- | --- |
| `count()` | `0` |
| `sum`, `avg`, `min`, `max` | `NULL` |
| `join(...)` | `''` |
| `to_json(...)` | `[]` |
| `to_xml(...)` | XML compatibile con una Bag vuota |

Il risultato numerico `NULL` distingue l'assenza di valori da una somma
uguale a zero. Il placeholder di `join` riguarda un valore vuoto in una riga
presente: non si applica quando mancano tutte le righe correlate.
Questa decisione non equipara un insieme senza righe a righe presenti con
valori NULL e non modifica la cardinalità della query esterna.

## Stato delle decisioni e verifiche residue

I punti esaminati sulla grammatica delle aggregazioni sono chiusi, compreso
il perimetro dei dialetti: `to_xml` non è una capability di SQLite. Non si
aggiungono fallback né ulteriori sintassi.

Le etichette XML `r_0`, `r_1`, … sono decise. La verifica del formato Bag
esistente, compresi tipi e NULL, è completata nel [passo 106](106-xml-many-aggregates.md).

Il primo perimetro resta la proiezione. L'uso degli aggregati in filtri o altri
contesti non viene aggiunto implicitamente. L'ordinamento delle righe interne,
invece, è deciso come descritto sopra.

Le **derivazioni delle virtualRelation** sono raccordate nel
[passo 109](109-derived-virtual-relations.md): condizioni in AND tra parentesi
e `var_*` manglizzati separatamente per livello e utilizzo, senza precedenza
tra nomi uguali. Ogni condizione conserva le proprie espressioni sorgente.
La forma diretta `table=` è raccordata nel [passo 110](110-direct-virtual-relations.md),
con `condition` obbligatoria nella source completa. La condizione descrive
l’intero collegamento; non si aggiungono correlazioni implicite. Vale lo stesso
uso verso molti con `.aggr()`, senza abbreviazioni scalari.

**Decisione del 16 ottobre:** `ask` è rinviato ed escluso dalla TODO attiva.
Contesto e punti da riprendere sono nel
[documento separato 108](108-deferred-virtual-relation-ask.md).

`first`/`last` e selezione dei primi/ultimi N record non entrano in questa
decisione. `limit`, `order_by`, `one_one` e inverse automatiche nella
dichiarazione delle virtualRelation restano rinviati. Le raccolte JSON/XML
sono implementate nei passi 105 e 106.

## Stato dell'implementazione

La [baseline 102](102-many-aggregation-contracts.md) conserva l'esito iniziale:
24 passed, 93 xfailed, 5 skip di dialetto; include la verifica del serializer
Bag tipizzato e il round-trip dell'XML prodotto da un esempio SQL PostgreSQL.

**Primo passo implementato:** [103](103-numeric-many-aggregates.md).
`many_aggr` compila count/sum/avg/min/max attraverso sottoquery scalari correlate,
riusando formule, relazioni, alias e binding esistenti. La suite dedicata di quel passo
restituiva 91 passed, 34 xfailed, 5 skipped. Le semplici virtualRelation filtrate
con `condition`/`var_*` sono incluse nei contratti superati.

**Secondo passo implementato:** [104](104-join-ordered-many-aggregates.md).
Join e `.order_by(...).aggr(...)` passano su entrambi i dialetti; la suite dedicata
restituiva 139 passed, 14 xfailed, 5 skipped.

**Terzo passo implementato:** [105](105-json-many-aggregates.md).
To_json passa sui due dialetti: selezione, star/statiche, alias, ordine, formule,
parametri e insieme vuoto. Suite dedicata: 177 passed, 4 xfailed, 5 skipped.
**Quarto passo implementato:** [106](106-xml-many-aggregates.md).
To_xml produce XML Bag su PostgreSQL; SQLite resta non supportato. Suite dedicata:
190 passed, 14 skipped, nessun xfail. Compresi i round-trip dei valori e tipi
attraverso il parser Bag reale.
Il riconoscimento generico degli altri nomi non li rende sintassi approvata.
Le derivazioni sono implementate nel [passo 109](109-derived-virtual-relations.md).
La forma diretta `table=` è implementata nel [passo 110](110-direct-virtual-relations.md),
con condizione obbligatoria e riuso delle stesse aggregazioni e derivazioni.
`ask` è rinviato nel documento 108.

Riferimenti: [grammatica 42](42-configuration-grammar.md),
[checklist 58](58-compiler-checklist.md),
[registro R-10](41-deferred-features.md#r-10--compilazione-delle-relazioni-verso-molti-sul-nuovo-albero).
