# 48 — Grammatica delle options: stato corretto dopo la revisione

**Rettifica del 13 ottobre:** diagnostics, citata nel censimento storico sotto,
è rimossa dalla grammatica attiva. Diagnostic/invalidFields/invalidRelations
sono funzionalità non portate, da rivedere come opzioni di tabella (41, R-07).


**Decisione successiva sui timestamp:** i timestamp di sistema sono DHZ;
la convenzione di scrittura nel DB è UTC. Per ora nessuna opzione
`timestamp_type` o `use_timezone`. Prevale sui punti ancora aperti citati sotto.
La baseline salvata del corpus usa già use_timezone=True (report 45).

**Decisione successiva:** [schemi dedotti dai package](50-schemas-from-packages.md);
nessuna dichiarazione schemas nella nuova configurazione.

**Aggiornamento del 13 ottobre:** espansioni strutturali e conservazione delle
options negli oggetti implementate nelle fasi 2–3 del [piano 51](51-source-to-live-objects-plan.md).
Il resoconto seguente descrive il checkpoint grammaticale precedente.

12 ottobre 2026. **Checkpoint di sola grammatica.**
La precedente versione conteneva scelte non concordate. Le correzioni e la
provenienza delle funzioni sono nel [report 49](49-grammar-corrections-and-audit.md).

Esempio costruibile con tabelle reali selezionate dai tre package:
[configure.py](../../examples/model_grammar/configure.py).
Non è la trascrizione completa delle 75 tabelle e non produce il modello risolto.
Le firme effettive sono nella [grammatica generata](../grammar.md).

```python
from genro_bag.resolvers import EnvResolver, BagCbResolver

customer.options().partition(
    'state', field='state', value=EnvResolver('INVC_STATE'))
# In alternativa, un callback locale legge l'ambiente applicativo:
# value=BagCbResolver(lambda: application.db.currentEnv.get('invc_state'))

invoice.column('date', dtype='D')
invoice.options().numbering('inv_number', parameters={
    'format': '$K$YY/$NNNNNN', 'code': 'A', 'period': 'YY',
    'date_field': 'date', 'showOnLoad': True, 'recycle': True})

adm.table('htmltemplate_atc', pkey='id').options().attachments(
    master='adm.htmltemplate')
```

Il callback è racchiuso nel resolver esistente. Non viene eseguito costruendo,
validando, copiando o componendo la source. `EnvResolver` legge variabili di
processo quando risolto; per l'ambiente applicativo si usa un resolver/callback
adatto, senza confondere i due ambienti. Non si aggiungono classi resolver al core.
Durante il render il resolver fornisce il valore della configurazione. Questo
non definisce un default da ricalcolare a ogni scrittura; defaultValues/workdate
del legacy appartengono all'esecuzione, fuori dal presente esempio.

## Catalogo e firme

Le 19 options conservano le famiglie dichiarative del legacy:
hierarchical, auto_counter, relative_index, dynamic_fields,
record_hash, full_update, audit, system_records, protection, diagnostics,
release, partition, tenant, retention, broadcast, archive, enabled_when,
attachments e numbering. Le funzioni DB/package già presenti restano
ai rispettivi livelli. La provenienza dei nomi e i dettagli ancora proposti
sono esplicitati nell'audit 49: presenza nel codice non equivale ad approvazione.

Le firme sono chiuse. Il parametro provider e la dichiarazione behavior sono
rimossi: anticipavano collegamenti esecutivi estranei a grammatica e traduzione.
La source dichiara dati del modello, senza predisporre registri di esecutori.

## Composizione e verifica

- Le options sono singleton salvo partition (name) e numbering (field).
- enabled=False conserva una dichiarazione disattivata; le singleton
  ammettono anche option(False). reset elimina la dichiarazione.
- Parametri richiesti verificati sulla dichiarazione composta; audit richiede
  mode, non un provider arbitrario. Partition richiede field e ammette value
  letterale o resolver; tenant non richiede una variabile aggiuntiva.
- parameters, templates, records e handlers si compongono per chiave.
- I payload dati ammettono resolver Bag già esistenti senza eseguirli.
  Un callback nudo non sostituisce BagCbResolver.
- validate_source() conserva il contratto: lista dei problemi di cardinalità,
  vuota se valida; errori di firma sollevano ValueError. Non risolve riferimenti
  tra tabelle né richiede colonne che saranno generate dalle options.

Il codec JSON Bag viene verificato separatamente su dichiarazioni di soli dati.
Questo non certifica la trasportabilità di un callback Python: codec e binding
remoto restano da definire, senza serializzare o eseguire automaticamente codice.

Il renderer esistente continua a rifiutare le nuove options attive con errore
esplicito: non produce una proiezione apparentemente completa ignorandone gli
effetti. L'artefatto del report 47 continua a provenire dalla source legacy
espansa. Nessun incremento di versione o pubblicazione.

La chiave testuale derivata usa pkey_columns e pkey_columns_joiner sulla
tabella, come nel legacy. pkey_from è ritirata; non è un’opzione separata.
