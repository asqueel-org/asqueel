# 108 — ask nelle virtualRelation: rinviato

**Decisione del 16 ottobre 2026:** `ask` per ora non serve. Esce dalla TODO
attiva delle letture e delle aggregazioni; non è un requisito per completarle.
Questo documento conserva il contesto per un eventuale recupero futuro.

## Dichiarazione già prevista

La grammatica conserva `ask` come dichiarazione dei parametri richiesti,
secondo la GEP sulle virtual relations. La decisione provvisoria del 13 ottobre
usa `:ask_<nome>` nella condizione, mantenendo il nome del campo senza prefisso.
Ogni dichiarazione possiede i propri parametri, anche in presenza di nomi uguali.

```python
tbl.virtualRelation('invoices_year', relation='@invoices',
    condition='EXTRACT(YEAR FROM $date)=:ask_year',
    ask=dict(title='Anno delle fatture',
             fields=[dict(name='year', dtype='I', lbl='Anno')]))
```

Questo è un esempio dichiarativo conservato, non una query eseguibile:
il compilatore delle aggregazioni rifiuta attualmente virtualRelation con `ask`.
Il rinvio non cambia codice, firma, dati conservati nel modello o rifiuto attuale.
Non introduce raccolta di valori, interfacce utente o binding impliciti.

## Punti da riprendere soltanto se servirà

- Associazione dei valori esterni ai singoli utilizzi della relazione, anche
  quando la stessa relazione viene usata più volte nella query.
- Composizione e precedenza degli `ask` omonimi nelle derivazioni e rapporto
  con i binding `var_*`.
- Verifica del namespace provvisorio e dell'isolamento dei parametri generati.
  L'isolamento dei mangler esistente non decide l'associazione dei valori esterni.

Questi punti restano da esaminare, senza una soluzione aggiunta per deduzione.
Le derivazioni senza `ask` e la forma diretta `table=` restano questioni distinte:
questa decisione non le rinvia.

Riferimenti: [grammatica 42](42-configuration-grammar.md),
[decisioni aggregazioni 101](101-many-aggregation-decisions.md),
[checklist 58](58-compiler-checklist.md).
