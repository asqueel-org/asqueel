# 84 — R4: verifica integrata e prestazioni

15 ottobre 2026. **Verifica eseguita; accettazione completa non chiusa.**
R5 e il raccordo delle relazioni non sono avviati. Nessuna modifica a produzione,
test o esempi, nessuna nuova sintassi o ottimizzazione. Le impronte dei 238 file
Python verificano questo confine; sono aggiunti soltanto sonda, evidenze e documenti.

## Risultati verificati

- **3.918 test superati, 13 saltati**, inclusi precedente compilatore, scritture,
  adapter, modello, options e migration; copertura della suite 95%.
- **15 prove legacy superate**: sei SELECT minime, quattro embedFieldPars,
  quattro corpi originali dei test dei cast PostgreSQL e un test base adapter.
  Per i cast resta la fixture ristretta già documentata in R3: non viene importato
  MySQLdb. Le prove embedFieldPars usano anche il database PostgreSQL reale.
- **148 SELECT fisiche**, 74 modelli × SQLite/PostgreSQL, identiche al riferimento
  dopo la sola normalizzazione di spazi e quoting di `t0` già usata in R1.
  Altri 47 casi mirati compilati, 23 eseguiti su SQLite senza differenze.
- **JSON migration identico** all'artefatto salvato, al precedente renderer e al
  riferimento legacy con l'esclusione concordata di `sys_locked_record`.
  I test coprono tutti i package: sys 16 tabelle, adm 40, invc 18.
- Il test con 100 proiezioni ripetute conferma **una risoluzione per campo distinto
  e per compilazione**, condivisa tra columns, WHERE e ORDER BY. Ricompilare la
  stessa query ricrea il contesto; non è introdotta una cache tra query.

## Corpus integrato: cosa significano i numeri

La sonda riusa senza modificarlo il corpus congelato del rapporto 78:
**132 combinazioni caso/dialetto, 396 tracce** sui tre percorsi. SQLite in memoria e PostgreSQL
con sole tabelle temporanee della sessione. Prima si compila con connessioni
vietate, poi si esegue il SQL catturato con i driver reali. Non viene abilitata
`fetch()` sul nuovo albero. La prova con più istruzioni non viene eseguita.

Il riferimento è il risultato effettivo GenroPy `fa35e5ad`, non il campo
`expected` del corpus storico, che conteneva anche aspettative dello scanner.
Le forme escluse dalla grammatica, compreso il riferimento logico con virgolette,
rimangono soltanto evidenza storica: non sono requisiti né proposte.

| Confronto con il legacy | Precedente compilatore | Nuovo albero |
| --- | ---: | ---: |
| Stesso esito nelle fasi compilazione/esecuzione | 89/132 | 116/132 |
| Casi eseguiti con successo da entrambi | 84 | 84 |
| Stesse righe e nomi di colonna, tra quelli eseguiti da entrambi | 62/84 | 82/84 |

Il primo conteggio include errori da entrambe le parti e il caso non eseguito:
**non è un conteggio di test passati**, né verifica l'identità di classe/messaggio
dell'errore. Nei 82 casi con righe e nomi uguali coincidono anche i tipi restituiti.
SQL e kwargs non sono necessariamente identici byte per byte: il legacy aggiunge
il proprio commento diagnostico e `jc_kwargs`, oltre alle differenze di binding
postgres/psycopg2 rispetto a postgres3 già esplicitate in R3.

## Differenze residue

1. **Parametro dentro una stringa SQL, PostgreSQL.** Con
   `columns="':id' AS value", where='$id=:id', id=1`, entrambi preparano
   `'%(id)s'` nella proiezione. Il legacy psycopg2 restituisce la stringa `1`;
   psycopg3 con binding server restituisce la stringa `$1`. È una differenza
   effettiva di esecuzione, non di risoluzione del campo né una nuova sintassi.
   L'escape legacy `\:id` per ottenere il testo letterale passa. R3 aveva verificato
   la preparazione ma non questa combinazione a valle del driver: la parità
   dell'algoritmo di preparazione non implica la parità dell'esecuzione.
2. **Collisione `ids_0`, PostgreSQL.** Con `ids=[1,2]` e un distinto `ids_0=3`,
   l'espansione dell'adapter legacy postgres3 riusata in R3 sovrascrive `ids_0`.
   Il riferimento psycopg2 non espande quella tupla: il caso produce `[1,2]`
   contro `[2]`. È il limite già documentato in R3/M1, ora verificato nell'intera
   pipeline; non viene introdotto un allocatore per correggerlo. La collisione
   SQLite `ids0` coincide invece con il suo adapter legacy.
3. **Residuo del vecchio scanner nel renderer condiviso.** `_fragment` e
   `_has_expression` di `dialects/postgres.py` chiamano ancora `_tokens`.
   Questo aggiunge un newline al commento finale e anticipa l'errore sul commento
   incompleto: quattro differenze di fase/esito nei due dialetti. Il renderer è
   condiviso con SQLite e con il compilatore precedente. Non è una proposta di
   supportare i commenti: sono tracce storiche che localizzano un residuo tecnico
   da riallineare, secondo la decisione già presa. R4 non lo modifica.
4. **Perimetro successivo.** Relazioni e macro restano esplicitamente bloccate
   nel nuovo compilatore. Nel corpus ci sono 14 tracce rifiutate per questo motivo;
   due falliscono anche nel legacy perché la relazione non esiste, perciò solo
   12 contribuiscono alle differenze di esito. Formule, filtri impliciti ed
   espansione `*` richiedono ancora i raccordi del piano 76. La suite verde del
   precedente compilatore non certifica tali funzionalità sul nuovo albero.

I 16 esiti differenti sono quindi 12 di perimetro successivo e quattro residui
del renderer. A questi si aggiungono le due differenze di risultato PostgreSQL.
I dettagli completi, inclusi errori del riferimento e kwargs, sono conservati in
[integrated.json](evidence/legacy-realignment-r4/integrated.json).

## Prestazioni

Stesso harness del rapporto 78, tre motori nello stesso processo: query nuova
ogni volta, dieci warmup, nove round con ordine ruotato, 100 iterazioni per round
(30 per le proiezioni da 50/100 colonne), GC disabilitato solo durante la misura.
Sono esclusi costruzione del modello e tempo di esecuzione SQL; il percorso legacy
passa dal suo `execute` con cursore di cattura per includere la vera preparazione
degli argomenti, con il relativo overhead. Non è una misura isolata dello scanner.
I 14 carichi sono prima eseguiti su tutti e tre i motori: righe e nomi delle colonne
coincidono con le aspettative. Il profiling viene eseguito fuori dai round misurati.

Mediane in microsecondi per query; più basso è meglio:

| Dialetto | Carico | Legacy | Precedente | Nuovo albero | Nuovo / legacy |
| --- | --- | ---: | ---: | ---: | ---: |
| SQLite | SELECT ordinaria | 184,2 | 229,7 | 151,9 | 0,82× |
| PostgreSQL | SELECT ordinaria | 168,2 | 229,9 | 140,7 | 0,84× |
| SQLite | 100 proiezioni dello stesso campo | 550,3 | 2268,7 | 1271,1 | 2,31× |
| PostgreSQL | 100 proiezioni dello stesso campo | 448,2 | 2265,4 | 1175,9 | 2,62× |
| SQLite | 20 CASE | 385,4 | 2449,3 | 761,5 | 1,98× |
| PostgreSQL | 20 CASE | 315,3 | 2629,6 | 696,9 | 2,21× |

Il nuovo percorso è più veloce del precedente nei carichi misurati, ma **non è
uniformemente più veloce del legacy**. Sono rilevanti i costi sulle proiezioni
numerose: non si può considerare conclusa la valutazione solo dalla SELECT breve.

Il profilo PostgreSQL di 100 compilazioni con 20 CASE attribuisce circa 0,116 s
cumulativi su 0,236 s a `_tokens`, raggiunto soprattutto da `_fragment` nel
renderer. Con 100 proiezioni ripetute, su 0,439 s circa 0,231 s sono nella
costruzione delle proiezioni e 0,177 s nel rendering; `result_column` ne assorbe
circa 0,082 s. Sono tempi sotto cProfile, **non sommabili indiscriminatamente né
convertibili in una previsione di speedup**. Individuano lavoro aggiuntivo per
proiezione e scansione nel renderer, non una nuova risoluzione del campo per ogni
occorrenza. Nessuna correzione prestazionale viene applicata in R4.

Le misure storiche di R1 usavano lo stesso harness ma un'altra sessione: cambiano
anche i tempi del legacy invariato. Perciò il confronto causale è quello
contemporaneo sopra, non una percentuale ricavata confrontando i tempi assoluti
delle due sessioni. Campioni completi e profili sono nella directory delle evidenze.

## Stato dopo R4

- Verifica e misure completate; codice, test, esempi e JSON migration invariati.
- Accettazione completa aperta per le differenze sopra; nessuna parità generale
  dichiarata e nessun miglioramento considerato approvato.
- Prima di R5 va affrontata la differenza concreta del binding PostgreSQL e va
  completato il riallineamento del renderer già richiesto. Le collisioni restano
  la differenza nota tra gli adapter legacy; non autorizzano una correzione M1.
- Eventuali interventi sui costi devono essere separati, motivati da queste
  misure e concordati. R4 non autorizza nuove cache o altri algoritmi.

Evidenze: [verifica](evidence/legacy-realignment-r4/verification.json),
[suite](evidence/legacy-realignment-r4/full-tests.log),
[benchmark](evidence/legacy-realignment-r4/benchmark.json),
[JSON migration](evidence/legacy-realignment-r4/migration.json).
Sonda: [verify_legacy_r4.py](probes/verify_legacy_r4.py), che riusa
`compare_scanners.py` e `scanner_corpus.py` senza modificarli.
