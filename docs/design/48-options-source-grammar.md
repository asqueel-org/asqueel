# 48 — Completamento della grammatica delle options

12 ottobre 2026. Perimetro aggiornato su indicazione dell'utente:
**solo grammatica; rendering a oggetti vivi nella prossima fase**.

È disponibile il catalogo dichiarativo della sezione 7 della specifica 42,
oltre a `pkey_from` e `column.dynamic_fields`. Costruire la source non genera
colonne, non cerca provider, non importa classi applicative, non alloca chiavi
e non apre connessioni. I metodi degli elementi descrivono soltanto la grammatica.

Esempio completo costruibile: [configure.py](../../examples/model_grammar/configure.py).
Firme generate dal codice: [grammar.md](../grammar.md).

```python
tbl = pkg.table('product_type', pkey='id')
tbl.options().sys_fields(id={'type': 'uuid'}, user_upd=False)
tbl.options().hierarchical(columns=[{'name': 'code', 'unique': True}])
tbl.options().auto_counter(scope='parent_id')
tbl.options().dynamic_fields(templates={'default': 'product.template'})
tbl.column('code', dtype='T')

invoice = pkg.table('invoice', pkey='id')
invoice.options().audit('full', provider='accounting.audit')
invoice.options().numbering('inv_number', provider='accounting.numbering',
                            parameters={'yearly': True})
invoice.options().broadcast('id', 'inv_number', provider='events.invoice')

pkg.table('invoice_atc', pkey='id').options().attachments(
    master='invc.invoice', provider='storage.attachments')

config.validate_source()
```

`validate_source()` controlla dichiarazioni e composizione; non risolve riferimenti
fra tabelle e non richiede che i campi promessi dalle options siano già presenti.
Conserva il contratto esistente: restituisce la lista dei problemi di cardinalità
dei figli (vuota se valida); gli errori nelle options sollevano `ValueError`.
`validate_model()` resta la verifica di dominio del modello esistente, distinta
da questo controllo della source.

## Catalogo aggiunto

Tutte sono options di tabella:

- `behavior`, `pkey_from`, `hierarchical`, `auto_counter`, `relative_index`;
- `dynamic_fields`, `record_hash`, `full_update`, `audit`, `system_records`;
- `protection`, `diagnostics`, `release`, `partition`, `tenant`, `retention`;
- `broadcast`, `archive`, `enabled_when`, `attachments`, `numbering`.

`column.dynamic_fields(source='package.table.column')` ha un payload distinto:
richiede `source`, mentre l'opzione della tabella ammette `templates`.
Le options di DB/schema/package/connection già disponibili restano ai propri livelli.

Le firme sono chiuse: keyword errate e opzioni usate al livello sbagliato danno
un errore. I provider sono riferimenti simbolici, per esempio `storage.attachments`
o `storage.attachments@1`; l'esistenza, le versioni compatibili e le capability
verranno verificate nella fase degli oggetti. Il riferimento non è un import.

## Payload e composizione

- Un'opzione senza identità ripetuta è singleton; `partition` è identificata
  da `name`, `numbering` da `field`. I rispettivi nodi possono coesistere.
- `enabled=False` disattiva una dichiarazione conservandola. Per le options
  singleton salvo `behavior` è ammesso anche `option(False)`. Le options nominate
  usano, per esempio, `partition('area', enabled=False)`.
- I parametri obbligatori quando l'opzione è attiva sono verificati sulla
  dichiarazione composta. Per consentire disattivazione/riattivazione le firme
  riportano `None` come default di alcuni parametri: ciò non rende valido
  `audit()` senza `mode` e `provider` quando attiva.
- I contributi nominati conservano le regole P1: completamento nello stesso
  contributo, errore sui valori incompatibili, override esplicito nei successivi.
  `reset('audit')` elimina l'opzione; resettare una famiglia nominata elimina
  tutte le dichiarazioni di quella famiglia.
- `parameters`, `templates`, `records` e `handlers` si compongono per chiave;
  liste e valori della singola chiave vengono sostituiti, senza merge ricorsivo.
- `hierarchical.columns` accetta nomi oppure mappe chiuse `{name, unique}`;
  queste rendono esplicita l'unicità di uno specifico percorso gerarchico.
- `system_records.records` è una mappa codice → valori oppure riferimento
  simbolico. `release.handlers` è una mappa versione scritta come stringa
  numerica → riferimento al relativo handler.
- I payload sono dati portabili: primitive JSON, mappe a chiavi stringa,
  liste/tuple. Callback, oggetti vivi e numeri non finiti sono rifiutati.
  `rules` contiene espressioni/riferimenti come stringhe, senza eseguirli.
- Profili chiusi per `audit.mode`, `pkey_from.missing`, `record_hash.algorithm`;
  flag booleani, profondità positiva, retention non negativa e liste prive di
  nomi vuoti o duplicati. I nuovi default vengono applicati dal futuro renderer,
  non inseriti automaticamente a ogni dichiarazione.

## Confine con la fase successiva

Il renderer esistente rifiuta le nuove options attive con un errore esplicito
`declaration-only`: evita di produrre un JSON apparentemente completo ignorando
campi che queste options dovranno generare. Questo controllo non implementa
l'espansione né il rendering a oggetti.

Non è stata sostituita la source espansa usata dall'artefatto del report 47.
Costruzione degli oggetti, espansioni, registro/binding dei provider e produzione
del JSON interamente dalla configurazione nativa restano il lavoro successivo.
Nessuna modifica alla versione o pubblicazione della release.

## Verifiche

Suite completa: **987 passed, 1 skipped**, inclusi i test PostgreSQL locali.
Ruff superato; mypy senza errori nei 50 file sorgente. Le nuove prove sono 43.

`tests/test_behavior_option_grammar.py` copre tutte le 21 options, firme chiuse,
ambiti, composizione/disattivazione/reset, payload invalidi, nomi indipendenti,
esportazione della grammatica e round-trip JSON della source Bag. La prova
principale impedisce esplicitamente chiamate al resolver e all'espansore e
verifica l'assenza delle colonne generate. I provider dell'esempio non esistono
nell'ambiente: costruire la source resta comunque possibile.

La serializzazione JSON della source usa il codec Bag esistente; non introduce
il codec delle ricette delle operazioni, che appartiene alla fase successiva.
