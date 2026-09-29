# Partition, draft e cancellazione logica

Questa estensione del nucleo nativo serve alle applicazioni nuove. Store e tenant
restano rinviati. Qui «partition» indica un filtro logico sulle righe, non il
partizionamento fisico PostgreSQL e neppure una subtable.

## Dichiarazione e contesto

Le policy appartengono alla tabella risolta (`Table.policies`), accanto alle
colonne e ai loro metadati. La ricetta builder conserva la dichiarazione:

```python
table = tables.table('invoice', pkey='id',
    x_partition=dict(field='organization_id', current='organization',
                     allowed='allowed_organizations', include_null=True),
    x_draft_field='draft', x_logical_deletion_field='deleted_at')
columns = table.columns()
columns.column('id', dtype='L')
columns.column('organization_id', dtype='L')
columns.column('draft', dtype='B')
columns.column('deleted_at', dtype='DHZ')
```

`x_partitions=[...]` permette più dimensioni, combinate in AND; non si può
specificare insieme a `x_partition`. Il campo può essere una colonna fisica
locale oppure un percorso forward to-one come `@customer.organization_id`.
Le chiavi `current` e `allowed` nominano valori nell'ambiente. `current` è
obbligatoria nella dichiarazione, `allowed` è opzionale. La loro presenza nel
contesto è distinta dal valore. Le policy non ereditano dallo schema.

```python
from genro_sql import SqlEnvironment, PostgresCompiler, PostgresDatabase

environment = SqlEnvironment()
compiler = PostgresCompiler(model, environment=environment)

def invoices(conninfo, organization):
    with PostgresDatabase(conninfo, environment=environment) as db:
        with db.temp_env(organization=organization):
            return db.execute(compiler.select('sales.invoice'))
```

L'ambiente usa scope contestuali; il runtime opera sul thread chiamante. Il compiler
ne legge uno snapshot. Le query conservano le dipendenze dal contesto, anche
le chiavi assenti: il runtime rifiuta una query se quelle dipendenze sono
cambiate. Occorre ricompilarla nel nuovo contesto. Dettagli ed alias
`currentEnv`/`tempEnv`: [ambiente SQL](sql-environment.md).

## Regole delle partition

| Contesto | Filtro |
|---|---|
| `current=0`, `False` o stringa vuota | Uguaglianza sul valore, mai disabilitazione |
| `current=None` | `IS NULL` |
| Solo `allowed=[a,b]` | Appartenenza ai valori; anche NULL se `include_null=True` |
| `allowed=[]` | Nessuna riga, anche se current è presente |
| Current e allowed presenti | Intersezione delle due condizioni |
| `None` esplicito nella lista allowed | NULL ammesso anche con `include_null=False` |
| Entrambe le chiavi assenti | Errore prima dell'esecuzione |
| `ignore_partition=True` | Esclusione esplicita delle policy partition |

Allowed deve essere una collezione di valori, non una stringa, un mapping o
un valore scalare. I valori sono parametri del driver. Il WHERE applicativo
e ogni condizione di policy sono parentesizzati e combinati con AND: un OR
applicativo non può allargare implicitamente lo scope.

Le policy si applicano alla tabella interrogata. Non vengono aggiunte alle
tabelle raggiunte con join: applicarle automaticamente cambierebbe il
significato dei LEFT JOIN. La partition dichiarata tramite un percorso
relazionale usa quel percorso come condizione della tabella principale.

## Draft e logical deletion

`x_draft_field` richiede una colonna fisica booleana locale. La SELECT usa di
default `draft IS NOT TRUE`: false e NULL sono visibili. `exclude_draft=False`
include anche i draft. Non vengono creati automaticamente flag o hook Python.

`x_logical_deletion_field` richiede una colonna fisica nullable locale.
La SELECT usa di default `deleted_at IS NULL`. Con
`exclude_logical_deleted=False` include tutte le righe; con `'mark'` aggiunge
`_isdeleted`, che contiene il valore effettivo della colonna, non un booleano.
La modalità mark accetta solo proiezioni fisiche scalari locali/to-one;
formule ed espressioni opache vengono rifiutate perché manca ancora un piano
strutturato di aggregazione. Un alias `_isdeleted` già presente è un errore.

```python
query = compiler.soft_delete('sales.invoice', value=timestamp,
                             where='$id = :id', params={'id': invoice_id})
query = compiler.restore('sales.invoice', where='$id = :id',
                         params={'id': invoice_id})
```

Il valore di cancellazione è esplicito e non può essere None. Restore assegna
NULL. `delete()` resta un DELETE fisico. UPDATE e DELETE non escludono
implicitamente draft o record cancellati: devono poterli modificare e
ripristinare. Le partition continuano invece a delimitare le scritture.

## Scritture e limiti

Per una partition locale, INSERT completa il campo omesso con current quando
presente. Con solo allowed il valore va specificato: non si assume quale sia
il default del database. I valori forniti in INSERT e UPDATE devono soddisfare
lo scope; un UPDATE non può trasferire righe fuori dalla partition corrente.
UPDATE e DELETE filtrano inoltre le righe già presenti.

Le scritture su tabelle con partition relazionale vengono rifiutate in questa
versione, salvo `ignore_partition=True` esplicito. Il supporto completo richiede
un piano DML con subquery/INSERT SELECT e verifiche atomiche; non viene simulato
con controlli separati soggetti a concorrenza.

Queste policy sono regole del compiler, non autorizzazioni PostgreSQL: SQL
compilato manualmente o eseguito direttamente può bypassarle. L'importazione
dal catalogo non può dedurre le policy applicative; la proiezione verso
sqlmigration conserva lo schema fisico e non queste regole. Partizioni fisiche,
subtable, RLS, hook applicativi e adattamento della sintassi legacy richiedono
incrementi successivi. `aggregateRows` non viene reintrodotto.

## Riferimento legacy e scelte deliberate

Analisi sul commit legacy `e12f2ce54245e57e48371ae0f47e928e0d55b960`:
`gnrsqltable/columns.py` (partitionParameters), `gnrsql/compiler.py` (filtri
draft/deleted), `gnrsql/env.py` e `gnrsql/execute.py` (ambiente).
Il legacy usava truthiness, la prima partition dichiarata e fallback che
potevano omettere il filtro. La semantica esplicita qui descritta è stata
scelta per il nuovo nucleo. Sono conservati `IS NOT TRUE`, `IS NULL`, il
tombstone originale in mark e il DELETE fisico del core.
