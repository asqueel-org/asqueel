# 110 — virtualRelation diretta con table e condition

16 ottobre 2026. Decisione approvata: nella forma `table=` la `condition` è
obbligatoria. La compilazione riusa aggregazioni, mangler e derivazioni esistenti.
`ask` resta [rinviato](108-deferred-virtual-relation-ask.md).

## Dichiarazione e significato

```python
customer.virtualRelation('invoices_direct', table='invc.invoice',
    condition='$customer_id=:var_customer', var_customer='$id')
```

```text
@invoices_direct.aggr(count() AS numero, sum($total) AS totale)
```

`table` identifica la destinazione; `condition` esprime l'intero collegamento.
I riferimenti `$campo` e `@relazione.campo` della condizione sono relativi alla
destinazione. Le espressioni `var_*` appartengono alla riga sorgente: qui `$id`
è l'id del cliente e `$customer_id` è il campo della fattura.

Non è necessaria una relazione ordinaria o una FK preesistente. Non viene
aggiunta una correlazione implicita su chiavi, nomi di colonna o pkey. Anche
una condizione con confronti diversi dall'uguaglianza viene compilata così
come dichiarata. La condizione obbligatoria non è un analizzatore SQL: non
verifica che il testo contenga necessariamente un riferimento alla sorgente.

L'uso rimane verso molti e richiede `.aggr()` in proiezione. Il raccordo non
introduce una forma scalare né abbreviazioni delle relazioni verso uno.

## Validazione e contributi

La source completa rifiuta una condizione assente, `None`, vuota o composta
solo da spazi quando è presente `table=`. Il controllo avviene dopo la
composizione: un contributo può completare la condizione di una dichiarazione
precedente. Anche source importate e render sono coperti dalla validazione.
Il compilatore controlla inoltre la condizione effettiva prima dell'espansione.

La firma resta invariata. `relation=` e `table=` restano le alternative già
previste nella grammatica, non vengono introdotti nuovi parametri.

## Riutilizzo del percorso esistente

La risalita della catena può ora terminare in una relazione ordinaria verso
molti oppure in una dichiarazione diretta `table=`:

- Nel caso ordinario, la correlazione tra chiavi viene costruita come prima;
  l'algoritmo è soltanto raccolto nel metodo `_many_joiner_condition`.
- Nel caso diretto, la destinazione viene cercata nel modello gerarchico e
  la condizione già espansa diventa il filtro della sottoquery.
- I filtri delle derivazioni vengono aggiunti in AND, ciascuno tra parentesi.
  Ogni livello mantiene il proprio scope `var_*` tramite `SqlBindings` esistente.
- La stessa `subquery` compila espressioni, formule, relazioni interne e
  parametri. Gli stessi adapter producono aggregati numerici, join, JSON e XML.
- Ordine base e override `.order_by()` restano quelli della destinazione.
  Nessuna aggregazione Python dopo il fetch e nessuna esplosione di righe esterne.

`ask` viene rifiutato in ogni livello. XML resta disponibile soltanto su
PostgreSQL; SQLite mantiene il rifiuto concordato. I joiner ordinari verso molti
con condizioni custom non ancora raccordate restano fuori da questo passo.

## Verifiche

La baseline SQLite dei nuovi contratti e della grammatica dava **20 failed,
16 passed, 1 skipped**, con 19 casi PostgreSQL esclusi da quella baseline.
Dopo il raccordo, i test della forma diretta danno **37 passed, 1 skipped** sui
due dialetti; i cinque nuovi casi di grammatica passano.

La regressione mirata di aggregazioni, formule e grammatica dà **332 passed,
22 skipped**. La sola suite aggregazioni dà **274 passed, 22 skipped**, con
catalogo Bag disponibile. Ruff e mypy passano (59 file sorgente).

I contratti coprono: assenza di FK/relazione ordinaria, equivalenza dei risultati
con la relazione ordinaria quando la condizione è equivalente, nessuna
correlazione aggiunta, formule e riferimenti interni, derivazioni su più livelli,
OR parentetici, parametri omonimi isolati, usi ripetuti, percorsi verso uno,
immutabilità del modello e dei parametri esterni, compilazione senza I/O,
ordine base/override e risultati vuoti per raccolte e aggregati.

Suite completa delle letture: **4531 passed, 42 skipped, 16 deselected**,
con due errori di allineamento della reference generata. Rigenerato
`docs/grammar.md` con `python -m asqueel.grammar_doc`, i sei controlli documentali
rieseguiti passano, compresi entrambi i precedenti fallimenti. Nessun codice
produttivo modificato dopo la suite completa. Esiti finali combinati:
**4533 passed, 42 skipped**, nessun fallimento o xfail residuo. Evidenze nell'
[evidenza del passo](evidence/many-aggregation-contracts/direct-table.json).
Manifesto di esclusione delle scritture invariato. Nessun intervento sulle scritture.
