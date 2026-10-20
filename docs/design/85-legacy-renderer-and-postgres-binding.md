# 85 — Renderer legacy e proposta sul binding PostgreSQL

**Decisione successiva dell’utente:** la proposta ClientCursor è ritirata.
Il parametro tra apici è un errore d’uso e non una compatibilità richiesta;
il binding attuale resta invariato. Le prove sotto sono evidenza storica,
non un blocco per procedere. Vedi il [piano 86](86-legacy-compiler-logical-phases.md).

15 ottobre 2026. Raccordo successivo alla verifica R4, autorizzato soltanto per
rimuovere i residui dello scanner nel renderer. Il binding PostgreSQL rimane
invariato; `ClientCursor` è una proposta provata separatamente. Relazioni non avviate.

## Renderer

`PostgresDialect.render`, condiviso da SQLite, assembla ora clausole e frammenti
senza chiamare `tokens` o `_tokens`. `_fragment`, che analizzava il testo e
aggiungeva un newline ai commenti finali, è rimosso. `_has_expression` verifica
soltanto la presenza di parti non vuote nel piano: non interpreta il SQL.

La costruzione segue `_gnrbaseadapter.compileSql`: clausole su righe separate,
indipendentemente dal loro contenuto. Le proiezioni usano il separatore `,\n`
di `compiledQuery`. Il `WHERE` della SELECT gerarchica riprende le parentesi per
ciascun elemento del `wherelist` legacy; in questa fase c'è il solo predicato
esplicito. Un predicato vuoto viene omesso come nel riferimento. Nessun filtro
implicito è anticipato.

I frammenti SQL non vengono corretti né validati lessicalmente dal renderer;
restano i controlli strutturali del piano, gli identificatori e i nodi parametro.
Le separazioni di clausola sono applicate anche al DML condiviso. Il test reale
PostgreSQL sul predicato di UPDATE continua a verificare che il confine di
clausola conservi il filtro. Non vengono riscritti i valori delle assegnazioni.

Il servizio `tokens` resta disponibile per il **precedente compilatore**:
questa fase non ne riscrive la risoluzione delle espressioni. I nuovi test
vietano esplicitamente qualsiasi chiamata allo scanner durante il rendering
e durante la SELECT minima sul nuovo albero.

## Riferimenti e verifiche

**3.944 test superati, 13 saltati**, copertura 95%; lint dei 17 file Python
interessati superato. Il JSON migration resta identico e nessun file dei driver
o degli esempi è cambiato.

La sonda [verify_legacy_renderer.py](probes/verify_legacy_renderer.py) estrae ed
esegue il corpo originale di `compileSql` negli otto snapshot già esaminati:
12 casi di assemblaggio, identici in tutti gli snapshot, senza mock del risultato.
L'oracle portabile alimenta 24 test, su entrambi i dialetti; altri due verificano
il separatore delle proiezioni. I casi lessicali derivano dalle prove storiche,
non introducono una nuova grammatica.

Nel corpus integrato di 132 combinazioni caso/dialetto, gli esiti concordi
passano da **116 a 120**: sono eliminate tutte e quattro le differenze di fase/
esito dovute al renderer. I 12 esiti restanti riguardano relazioni e macro non
ancora raccordate. Tra le 84 esecuzioni riuscite da entrambe le parti, 82 hanno
ancora righe, nomi e tipi uguali: le due differenze PostgreSQL sono volutamente
invariate.

Le **148 SELECT fisiche dei 74 modelli**, i 47 casi mirati e le 23 esecuzioni
SQLite coincidono con il riferimento. Le aspettative dei test precedenti sono
aggiornate ai newline del SQL; gli oracle legacy non sono riscritti per farli
coincidere con Asqueel. Solo i test delle correzioni lessicali rimosse cambiano
contratto, ora verificando la conservazione del testo e la separazione fissa
delle clausole.

Evidenze nella directory [legacy-renderer-r4](evidence/legacy-renderer-r4/):
`algorithm-anchors.json`, `integrated.json`, `native/select-summary.json`,
`full-final.log`, `verification.json` e `benchmark.json`. Le evidenze precedenti
di R4 restano immutate.

## Prestazioni dopo il riallineamento

Stesso harness R4, query nuove, dieci warmup e nove round a ordine ruotato.
Tutti i 14 carichi sono eseguiti sui tre percorsi prima di misurare soltanto
compilazione e preparazione SQL/kwargs. Nessuna nuova cache o ottimizzazione.
Mediane in microsecondi; confronto contemporaneo con il legacy:

| Dialetto | Carico | Legacy | Nuovo albero | Nuovo / legacy |
| --- | --- | ---: | ---: | ---: |
| SQLite | SELECT ordinaria | 187,0 | 117,4 | 0,63× |
| PostgreSQL | SELECT ordinaria | 164,9 | 101,8 | 0,62× |
| SQLite | 100 proiezioni ripetute | 540,6 | 918,3 | 1,70× |
| PostgreSQL | 100 proiezioni ripetute | 428,0 | 792,2 | 1,85× |
| SQLite | 20 CASE | 386,7 | 424,0 | 1,10× |
| PostgreSQL | 20 CASE | 302,1 | 337,6 | 1,12× |

Il costo di 100 proiezioni resta superiore al legacy: non si dichiara parità
prestazionale. Il profilo precedente identificava anche la costruzione delle
proiezioni e dei metadati; tale percorso non viene ottimizzato in questo passo.
I tempi assoluti tra sessioni possono variare; campioni e rapporti contemporanei
sono salvati in `benchmark.json`. Anche il precedente compilatore beneficia
del renderer condiviso, senza modifiche al suo algoritmo di risoluzione.

## Binding PostgreSQL: problema riprodotto, nessuna modifica applicata

Esempio minimo della differenza già presente nel corpus R4:

```python
sql = "SELECT ':id' AS value, :id::integer AS bound"
kwargs = {'id': 1}
```

La preparazione legacy e quella attuale producono, a parte il commento diagnostico:

```python
sql = "SELECT '%(id)s' AS value, %(id)s::integer AS bound"
kwargs = {'id': 1}
```

| Cursore effettivo | Riga restituita |
| --- | --- |
| Legacy, psycopg2 | `('1', 1)` |
| Asqueel attuale, psycopg3 Cursor | `('$1', 1)` |
| Proposta isolata, psycopg3 ClientCursor | `('1', 1)` |

Psycopg2 adatta i valori sul client. Il cursore predefinito psycopg3 traduce i
placeholder in `$1` e invia i valori separatamente: **dentro le virgolette `$1`
è testo SQL letterale**, mentre l'altra occorrenza rimane un parametro effettivo.
Il caso con `\:id`, quando si vuole conservare il testo letterale `:id`, passa
su tutti e tre i percorsi secondo la convenzione legacy.

La sonda [compare_postgres_binding.py](probes/compare_postgres_binding.py) esegue
solo SELECT: parametro tra virgolette, parametro ordinario, escape letterale,
testo con apostrofo, percentuale, data/Decimal/booleano, NULL e parametro ripetuto.
**Otto casi su otto** coincidono tra psycopg2 e il ClientCursor proposto, inclusi
i tipi restituiti. Questo verifica la proposta sui casi indicati, non certifica
ogni adattamento possibile del driver.

## Proposta storica — ritirata

Usare `psycopg.ClientCursor` nel metodo `PsycopgDriver.execute`, mantenendo SQL e
kwargs separati nell'output del compilatore e lasciando al driver il binding:

```python
# Proposta: non applicata al codice Asqueel.
with psycopg.ClientCursor(connection, row_factory=tuple_row) as cursor:
    cursor.execute(query.sql, dict(query.params))
```

È la modalità psycopg3 prevista per avvicinare il comportamento a psycopg2;
non richiede di riconoscere o correggere le stringhe SQL nel compilatore.
Il risultato continua a passare dall'attuale `query_result`, senza nuovi
contenitori o API. Prima dell'adozione va verificata la regressione del driver,
inclusi scritture, tipi, transazioni e connessioni.

La scelta riguarda tutte le esecuzioni che passano da quel metodo: ClientCursor
non supporta prepared statement server né parametri/risultati in formato binario,
e impiega il protocollo semplice fuori dalla pipeline. È quindi un cambiamento
di strategia del driver, non un dettaglio del renderer. Fonte:
[documentazione ufficiale psycopg](https://www.psycopg.org/psycopg3/docs/advanced/cursors.html#client-side-binding-cursors),
oltre al sorgente installato `psycopg/client_cursor.py` verificato localmente.

La collisione `ids_0` dell'espansione IN rimane separata: ClientCursor riceverebbe
il mapping già espanso e **non recupererebbe il valore sovrascritto**. L'algoritmo
postgres3 portato in R3 e la decisione M1 non sono cambiati.
