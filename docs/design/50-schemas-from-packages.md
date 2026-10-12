# 50 — Schemi dedotti dai package

12 ottobre 2026. Decisione esplicita dell'utente: non servono parametri autonomi
per gli schemi; dedurli dai package come nel legacy. Supera la precedente scelta
di una sezione schemas, incluse options e metadati indipendenti di schema.

```python
db = config.source.db('test_invoice_pg', implementation='postgresql')
packages = db.packages()
sys = packages.package('sys', sqlschema='sys', sqlprefix=True)
adm = packages.package('adm', sqlschema='adm', sqlprefix=True)
invc = packages.package('invc', sqlschema='invc', sqlprefix=True)
adm.options().requires('sys')
```

- sqlschema è direttamente il nome fisico, senza alias o dichiarazione separata.
- Più package possono condividere lo stesso schema: viene dedotto una sola volta.
- Un package vuoto conserva lo schema, anche nella proiezione del migratore.
- Se sqlschema è omesso/None, resta il default del dialetto già previsto:
  public per PostgreSQL, main per SQLite. Il nome del package non viene usato
  implicitamente come nome di schema.
- sqlprefix resta indipendente e mantiene il contratto esistente.
- Un override di tabella può scegliere uno schema dedotto dai package; non
  introduce una dichiarazione autonoma di schema.
- Nessuna opzione authorization e nessuna sezione options sullo schema dedotto.

La configurazione a package rifiuta una sezione schemas esplicita. Il vecchio
formato fisico schema→table resta supportato per gli input del migratore e le
configurazioni precedenti senza package: non è una seconda dichiarazione da
aggiungere alla nuova configurazione. La grammatica generata conserva questi
nodi di compatibilità, marcati come tali.

L'adattatore della source legacy espansa è stato adeguato: dichiara package,
senza duplicare gli schemi. L'esempio model_grammar segue la stessa regola.
La risoluzione già presente è stata corretta solo per questo mapping: non
sono stati aggiunti esecutori di options/provider o nuovi oggetti runtime.

Le verifiche coprono schemi condivisi, package vuoti, default del dialetto,
proiezione fisica, override di tabella e rifiuto della sezione superata. La
suite completa include il confronto del JSON di tutti i package test_invoice_pg
con l'oracolo legacy e le verifiche migrations PostgreSQL.

Esito: **1004 passed, 1 skipped**; Ruff superato e mypy senza errori nei
50 file sorgente nell’ambiente di verifica.
