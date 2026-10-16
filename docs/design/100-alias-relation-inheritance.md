# 100 — Eredità delle relazioni sulle aliasColumn

16 ottobre 2026. Estensione esplicitamente approvata dopo il confronto col legacy.
Il lavoro riguarda renderer, grammatica delle relazioni sulle colonne e test delle
letture. Compilatore e moduli delle scritture non sono modificati.

## Contratto

```python
# invoice.customer_id dichiara già una relazione verso customer.id
row.aliasColumn('customer_id', '@invoice_id.customer_id')
# La query sulla riga può usare @customer_id.name.
```

Nel legacy verificato l'alias da solo permetteva `$customer_id`, ma non
`@customer_id.name`: occorreva dichiarare `.relation('customer.id')` anche
sull'alias. La nuova eredità automatica è una decisione Asqueel, non un
comportamento attribuito al legacy.

- L'alias senza relazione propria eredita la destinazione della relazione
  della colonna riferita. Il nuovo collegamento è weak, senza FK o indici fisici.
- Una relazione esplicita sull'alias prevale, anche per gli alias che dipendono
  da esso. `.relation(...)` sulle virtuali è ammessa e weak per default;
  resta ammessa anche la firma esistente `.weak_relation(...)`.
- Una FK fisica su una colonna virtuale resta rifiutata. Questa modifica non
  cambia i vincoli FK delle dichiarazioni fisiche preesistenti.
- La relazione derivata usa l'identità dell'alias. Non duplica nome inverso,
  cardinalità inversa o azioni applicative della colonna originaria: più righe
  possono riferirsi alla stessa fattura/cliente. La registrazione usa le normali
  inverse interne private del modello, senza nuovi nomi pubblici.
- Il tipo del nodo relazione è quello effettivo dell'alias; l'override esplicito
  resta prioritario. La source originale e il nodo destinazione non cambiano.
- Un alias di una colonna senza relazione non riceve alcun collegamento.
  Cicli e percorsi non supportati conservano gli errori di compilazione esistenti;
  l'eredità non abilita virtualRelation o navigazione verso molti.

## Ordine nel renderer

1. Costruzione di tutti gli oggetti e registrazione delle relazioni esplicite.
2. Risoluzione ricorsiva delle dipendenze degli alias sul registro completo,
   con precedenza alle relazioni esplicite e protezione dai cicli.
3. Registrazione delle relazioni ereditate tramite lo stesso algoritmo usato
   dalle relazioni esplicite, prima di esporre gli alberi di navigazione.

L'eredità non passa attraverso una vista `table.relations` ancora incompleta:
la sua cache potrebbe nascondere le relazioni aggiunte dopo. Gli alias concatenati
e i percorsi che attraversano altri alias vengono risolti nel renderer. Non
vengono aggiunti resolver, scanner o percorsi alternativi nel compilatore.

## Impatto sui 74 modelli nativi

Si aggiungono due collegamenti weak e le rispettive inverse interne:

| Alias | Destinazione ereditata |
| --- | --- |
| `invc.invoice_row.customer_id` | `invc.customer.id` |
| `invc.invoice.customer_state` | `invc.state.code` |

Il registro passa da 144 a 148 nodi. Il confronto verifica separatamente i
quattro nodi nuovi e mantiene identico il controllo dei 144 precedenti;
gli oracoli legacy non sono modificati. Non viene ripristinato il vecchio nome
inverso `invoice_rows_by_customer` dai metadati opachi del ponte legacy.

L'abbreviazione `virtualRelation('customer', relation='@invoice_id.@customer_id')`
non è la soluzione adottata: le virtualRelation sono destinate alle relazioni
verso molti, secondo il chiarimento dell'utente. Il caso corrente è risolto
tramite l'alias di colonna già presente nel modello.

## Verifiche

`tests/object_tree/test_alias_relations.py` copre eredità, precedenza esplicita,
alias concatenati, percorsi attraverso una relazione ereditata, tipo del nodo,
source invariata, assenza di FK nel JSON, cicli e rifiuto di FK sulle virtuali.
I test di esecuzione usano SQLite e PostgreSQL, con corrispondenze, valori NULL,
filtri parametrizzati e riuso della JOIN. Il caso esplicito sceglie una tabella
diversa con valori diversi, così verifica effettivamente la precedenza.

Il confronto del corpus è in `tests/object_tree/test_invoice.py`; la regressione
completa usa `tests/read_path/pytest.args`, che esclude il lavoro del writer.

Esito finale: **4.262 passati, 12 skip, 16 deselected** in 241,25 secondi con
`PYTHONPATH=src python -m pytest @tests/read_path/pytest.args --no-cov -q --tb=short`.
I 9 nuovi casi comprendono esecuzione reale su entrambi i dialetti. Confronto
strutturale dei 74 modelli e JSON migration invariato; 144 relazioni precedenti
conservate, 4 nodi deboli derivati verificati separatamente. Ruff, mypy (57 file)
e Sphinx con warning come errori superati. Nessun push o pubblicazione.
