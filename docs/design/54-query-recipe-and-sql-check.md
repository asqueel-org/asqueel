# 54 — Recipe delle letture e controllo finale del SQL

13 ottobre 2026. Decisioni e ipotesi successive alla release 0.6.0.
Documento di progettazione: nessuna integrazione nel core, nessuna dipendenza
SQLGlot aggiunta e nessuna nuova firma pubblica implementata.

**Decisione successiva, 13 ottobre:** per il primo incremento si mantiene la
chiamata query con clausole e kwargs in linea, come nel legacy. Grammatica
Builder di columns/where e nuova interfaccia programmatica WhereBag sono
rinviate. Per trasferire una richiesta si considerano JSON/TYTX degli argomenti;
non è stato definito un nuovo codec. L'obiettivo immediato del compilatore è
ottenere SELECT e kwargs manglizzati. [Indagine 55](55-select-sql-and-kwargs-investigation.md).
La direzione del controllo SQL finale descritta sotto resta valida.

## Direzione concordata

**Prima ipotesi, superata per il primo incremento dalla decisione sopra.**
Si parte dalle letture, con un perimetro minimo. La query prima della
compilazione è una recipe Builder: raccoglie progressivamente le richieste,
si può serializzare in JSON/XML e ricostruire in un altro ambiente. Costruzione
e serializzazione non eseguono SQL. Al momento dell'esecuzione il compilatore
risolve i riferimenti sul modello del destinatario e produce SELECT e parametri
separati. La grammatica concreta è ancora in revisione, un punto alla volta.

Il browser deve poter costruire richieste dati, comprese espressioni definite
al volo come CASE e chiamate a funzioni SQL lecite. Non basta consentire soltanto
formule già dichiarate nel modello. Si mantiene una sintassi vicina al legacy.
Questo aggiorna l'ipotesi iniziale del documento 40 che escludeva del tutto
le espressioni SQL testuali dichiarate dal client; non autorizza SQL arbitrario
senza controlli.

## Controllo del SQL finale — direzione approvata

L'utente conferma di tenere SQLGlot come strada per controllare il SQL già
generato, prima dell'esecuzione, per richieste provenienti da fonti non fidate:

```text
recipe → compilatore Asqueel → SQL + parametri → controllo AST → esecuzione
```

Non si decide di usare SQLGlot per costruire la recipe o sostituire il
compilatore. Il requisito primario è impedire INSERT, UPDATE, DELETE e altri
comandi di modifica, anche annidati o aggiunti a una SELECT. La sola radice
SELECT non basta: il controllo deve esaminare tutto l'albero e tutti gli
statement. SQLGlot riconosce la struttura; le regole di ammissione appartengono
ad Asqueel. Il successo del parsing non è una validazione di sicurezza.

**Ipotesi proposta dall'utente:** una funzione di check per fonti non fidate,
abilitabile a richiesta. Nome, firma, collocazione della configurazione e
default non sono decisi. Il client non può autoattribuirsi fiducia o disabilitare
il controllo previsto dal server. Nessun flag viene introdotto ora.

Restano da definire i costrutti e le funzioni ammessi, i limiti del controllo e
gli errori. I permessi sui dati e i parametri separati restano questioni distinte:
vietare le scritture non certifica da solo la sicurezza complessiva della query.
Transazioni READ ONLY e ruoli di lettura PostgreSQL sono alternative o protezioni
aggiuntive discusse, non scelte architetturali già approvate.

## Prova isolata verificata

Ambiente temporaneo in /tmp, SQLGlot **30.22.0**, dialetto postgres. Nessun
accesso al database e nessuna modifica ad Asqueel. Un piccolo controllo legge
tutti gli statement, ne richiede uno solo, visita l'intero AST e ammette una
lista esplicita di tipi di nodo, senza accettare genericamente tutte le funzioni.
La lista serve solo alla dimostrazione, non è il contratto del futuro check.

| Caso | Esito osservato |
| --- | --- |
| SELECT con CASE WHEN totale > 1000 THEN 'alto' ELSE 'basso' END | Ammessa: Case, If, GT e valori riconosciuti |
| SELECT con COALESCE(totale, 0) | Ammessa: Coalesce riconosciuto |
| DELETE FROM fattura WHERE id = 7 | Rifiutata: radice Delete |
| WITH cancellate AS (DELETE FROM fattura WHERE id = 7 RETURNING id) SELECT id FROM cancellate | Rifiutata: Select → With → CTE → Delete |
| CTE contenente soltanto SELECT con COALESCE | Ammessa |
| SELECT seguita da un secondo statement DELETE | Rifiutata: più statement |
| SELECT pg_sleep(10) | Rifiutata: funzione fuori dalla lista della prova |
| COALESCE(note, 'DELETE FROM fattura') | Ammessa: DELETE è dentro un valore letterale |

Otto verifiche superate. Non sono una prova di sicurezza completa. Non è stata
provata qui l'integrazione dei riferimenti legacy $/@ nel parser: la prova
opera su SQL già compilato, coerentemente con la collocazione concordata.

Riferimenti ufficiali: [SQLGlot](https://sqlglot.com/sqlglot.html),
[licenza MIT](https://github.com/tobymao/sqlglot/blob/main/LICENSE).

## Ripresa della grammatica: columns e where

Ipotesi discussa e poi rinviata: non è la firma del prossimo incremento.

```python
q = miatable.query()
columns = q.columns()
columns.column('$codice AS code')
columns.column('@customer_id.account_name AS customer_name')
columns.column('COALESCE($totale, 0) AS value')
columns.column("CASE WHEN $totale > 1000 THEN 'alto' ELSE 'basso' END AS fascia")
w = q.where()
```

`$` identifica una colonna della tabella corrente, `@` un percorso di relazione;
AS conserva la forma legacy dell'alias. L'ipotesi di esprimere ogni trasformazione
come attributo, per esempio coalesce=0, non è stata adottata: limita la
composizione delle espressioni. Order_by, group_by, limit e offset non sono il
primo punto della revisione e restano orientati alla semantica legacy.

Per where si riparte dalla **WhereBag legacy**, non da un nuovo linguaggio
generale delle espressioni:

- nodo di condizione: attributi column e op, valore nel valore del nodo;
- jc collega la condizione o il gruppo precedente con AND/OR; il primo
  collegamento viene ignorato dal traduttore legacy;
- attributo not per la negazione (l'implementazione verifica la stringa 'not');
- una Bag annidata rappresenta un gruppo;
- parname è supportato dal legacy per il nome del parametro.

Riferimenti nel checkout GenroPy:
`gnrpy/gnr/sql/gnrsqltable/query.py::sqlWhereFromBag`,
`gnrpy/gnr/sql/adapters/_gnrbaseadapter.py::GnrWhereTranslator.innerFromBag` e
`gnrpy/gnr/web/gnrwebpage_proxy/apphandler/__init__.py::_decodeWhereBag`.
Il traduttore produce il predicato e raccoglie i parametri; il livello web lo
usa per le richieste con where rappresentato come Bag.

**Punto allora aperto, ora rinviato:** la firma Builder della singola condition e
poi quella dei gruppi, conservando questa semantica. Posizione del valore,
nomi Python per la negazione e comportamento delle chiamate ripetute non sono
fissati qui. Non sono introdotti metodi condition/group nel core.

La revisione delle variant rimane un tema separato: è stata rilevata la mancanza
del meccanismo generale legacy, ma non sono state approvate né la firma
c.variant(...), né varianti automatiche per dtype, né le loro precedenze.
