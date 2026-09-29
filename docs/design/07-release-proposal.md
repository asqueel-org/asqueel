# 07 — Proposta di versioni e lavoro degli agenti

29 settembre 2026. **Indirizzo V1 concordato: applicazioni nuove, PostgreSQL,
nucleo e runtime sincroni. Async da valutare solo a nucleo terminato.**
I dettagli tecnici sotto restano proposte da verificare. V1–V4 indicano traguardi di
prodotto; non fissano ancora numeri di versione del package né date di consegna.
Tre agenti hanno analizzato perimetro iniziale, dipendenze e distribuzione
degli obiettivi. Dopo l’indicazione «procediamo», tre agenti hanno implementato
il profilo V1 con integrazione e revisione incrociata. Stato, verifiche e limiti
sono nel [rapporto V1](../native-v1-delivery.md); il piano seguente conserva
il perimetro concordato e le versioni successive.

**Estensione successiva concordata:** ambiente isolato per task (`current_env`,
`temp_env`), partition logiche esplicite, draft e cancellazione logica entrano
nel nucleo per applicazioni nuove. Le regole e i limiti implementativi sono in
[policy di riga](../row-policies.md) e [ambiente SQL](../sql-environment.md).
Store e tenant possono seguire. Subtable e partizionamento fisico restano
distinti e non sono implementati da questa estensione.

**Correzione architetturale successiva:** la [revisione 09](09-legacy-object-api-review.md)
mostra che la V1 consegnata è un nucleo tecnico, privo dell'object model operativo
richiesto. Prima di ampliare il compiler vanno realizzati configurazione con le
relative grammatiche → rendering a oggetti → DB/tabella/query/fetch, con sessioni
e scritture coerenti con i contratti legacy selezionati. Il livello oggetti non
è rinviato alla V2; le tabelle sotto conservano la proposta storica e vanno lette
con questa correzione e i gate applicativi del documento 09.

## V1 — Genro SQL autonomo, utilizzabile su PostgreSQL

**Risultato:** dichiarare o importare un modello semplice, interrogare e
modificare i dati con il nuovo nucleo, mantenendo nomi e metadati coerenti.
Non è ancora una sostituzione del runtime nelle applicazioni legacy.

| Area | Incluso nella proposta V1 | Verifica di consegna |
|---|---|---|
| Modello comune | Modello risolto sopra gli strumenti esistenti; identità logiche, mapping fisico e provenienza dei contributi disponibili. | La stessa tabella mantiene identità e riferimenti nei consumer del modello. |
| Builders | Dichiarazione nativa e contratto di composizione; prova di montaggio/override che coinvolga validatori ed emitter. | Nessuna regressione degli indirizzi; conflitti espliciti. La scelta concreta segue la prova, non è presupposta. |
| UI | Metadati della colonna inline o paralleli, con accesso risolto comune e precedenze documentate. | Equivalenza delle due forme e utilizzo headless; nessun editor grafico richiesto. |
| Naming | Schema logico, schema SQL, prefisso e nome fisico esplicito distinti. | Stesso mapping per query, import e proiezione migration; identificatori quotati correttamente. |
| Import DB | PostgreSQL: tabelle, colonne, PK/FK, default e indici del sottoinsieme dichiarato. | Round-trip su fixture e report degli oggetti non gestiti; overlay UI preservato. |
| Compiler | SELECT, riferimenti a colonne, parametri, filtri, alias, ordine, limit/offset, attraversamento di relazioni to-one e formule SQL semplici. | Valori, binding, ordine, NULL e metadati verificati su PostgreSQL; costrutti fuori profilo rifiutati esplicitamente. |
| Scritture | INSERT/UPDATE/DELETE, RETURNING, transazioni esplicite e rollback, un driver e un runtime sincroni sul thread chiamante. | Persistenza, errore a metà transazione, vincoli, rollback e proprietà del thread su DB reale. |
| Migrazioni di base | Integrazione con gli strumenti esistenti per il sottoinsieme gestito. | Riproduzione dei difetti #8/#9 sulla baseline scelta, correzione dei percorsi dichiarati supportati; nessun oggetto esterno eliminato implicitamente. |
| Qualità | Corpus V1, matrice capacità, diagnostica, installazione riproducibile e misure iniziali. | Suite esistente preservata, test V1 e packaging riusciti, limiti pubblicati. |

**Esclusioni esplicite:** importazione e bridge applicativi legacy, query Bag/record/selection
legacy completi, macro avanzate, virtualRelation operative, relazioni to-many e
raccolte implicite, scope/subtable legacy operativi, hook di dominio, record-cluster,
driver async nativo, altri dialetti runtime, view/funzioni/trigger nativi e partizionamento fisico.

**Vincoli presenti dal primo giorno:** aggregateRows non viene implementato,
neppure in un adapter; il modello distingue subtable, scope, tenant/store e
partizioni fisiche. Le funzionalità non supportate non possono essere ignorate
silenziosamente nell'importazione o nell'esecuzione. I contratti preparano le
estensioni senza dichiararle già operative. Non si introduce un parser SQL
universale come prerequisito della prima SELECT.

La V1 copre inizialmente O-01/O-02/O-04/O-06/O-07/O-08/O-09/O-10/O-15/O-18
nel profilo descritto; prepara O-11/O-12/O-14 e raccoglie la baseline O-17.
O-16 viene valutato sugli esempi minimi, senza fissare tutte le API future.

## Contratto sincrono per V1

La decisione aggiornata rinvia async. Bag, modello, compiler, connessione e
transazione lavorano nel contesto chiamante. `Database` e `PostgresDatabase`
espongono `with`, `execute()` e `close()` sincroni, senza worker o executor.
Un database appartiene al thread che lo crea; accessi da altri thread sono errori.
Una transazione apre una connessione, esegue commit/rollback e la chiude.

Il driver resta separato da compiler e dialetto. Un futuro livello async sarà
valutato sui casi reali, dopo aver definito proprietà delle Bag e materializzazione
dei valori. Non viene promesso come semplice wrapper thread-safe.
Vedi [contratto runtime corrente](../native-runtime.md).

## V2 — Compiler avanzato e prima applicazione legacy

Due traguardi interni, ciascuno verificabile:

1. **V2-A, semantica:** virtualRelation GEP, relazioni to-many esplicite,
   EXISTS, aggregati/raccolte, sottoquery, formule e macro del profilo scelto;
   subtable e scope, ingressi Bag e metadati dei risultati derivati.
2. **V2-B, adozione:** importazione del modello di package/applicazioni con
   report delle perdite, mixin/bridge per un'applicazione campione, consumer record
   e selection necessari, hook e scritture di dominio, concorrenza e cluster nel
   profilo concordato; migrazione degli usi di aggregateRows verso forme esplicite.

Gli interrogativi ancora aperti del GEP vengono chiusi prima delle rispettive
implementazioni. La compatibilità è dichiarata per comportamento e consumer,
senza promettere copertura di tutte le applicazioni legacy. Test su scenari
applicativi completi, errori e rollback sono il gate distinto di V2-B.

Completa il primo profilo O-05/O-09/O-11/O-12/O-13 e amplia O-07/O-10/O-16/O-18.
È la versione a maggior rischio di espansione: il campione delimita la consegna.

## V3 — Prestazioni e portabilità del sottoinsieme scelto

Misurazioni rappresentative, cache di compilazione con invalidazione corretta,
gestione di connessioni/cursori, streaming e batch secondo i contratti; keyset
quando applicabile. Secondo dialetto scelto in base a un caso d'uso reale e
matrice delle capacità con esecuzione effettiva dei percorsi dichiarati.

Consegna O-03/O-17 nel profilo concordato, consolidando O-02/O-13/O-18.
La correttezza e l'assenza di perdite di risorse restano obbligatorie già in V1:
V3 rinvia le ottimizzazioni e l'ampliamento, non la qualità di base.

## V4 — Oggetti nativi e migrazioni evolute

View, funzioni, trigger nativi accanto agli hook Python; estensione di
sqlmigration a introspezione, identità, dipendenze, diff e applicazione;
partizioni fisiche PostgreSQL e relativi vincoli operativi.

Consegna O-14 e amplia O-15, con gate separati per ciascuna famiglia di oggetti.
È un ramo futuro: potrà procedere indipendentemente da parte di V3 quando
modello, migrazioni e runtime saranno stabili. Non blocca il rilascio V1/V2.

## Sequenza degli agenti dopo l'accordo sul perimetro

L'agente principale integra e verifica; fino a tre agenti lavorano su aree
distinte. La disponibilità di agenti non elimina le dipendenze fra contratti.

| Passaggio | Agente A | Agente B | Agente C | Gate dell'integratore |
|---|---|---|---|---|
| 1. Contratti | Modello risolto, naming e UI | Corpus V1 e fixture DB indipendenti | Import PostgreSQL e ricognizione migratore | Firme minime, ownership e limiti fissati; prove di composizione. |
| 2. Verticale | Compiler sul contratto condiviso | Runtime PostgreSQL e transazioni sincrone | Importatori e mapping verso gli strumenti esistenti | Un modello, una SELECT e CRUD reali con rollback. |
| 3. Completamento | Casi limite compiler e diagnostica | DML, risorse e integrazione | Round-trip PostgreSQL e report perdite | Corpus V1 completo e regressioni esistenti. |
| 4. Consegna | Revisione incrociata | Revisione incrociata | Guida e matrice capacità | Installazione, packaging e demo riproducibile. |

Prima delle modifiche si assegnano file/moduli in proprietà esclusiva; gli
agent non riscrivono contemporaneamente builder, catalogo o API pubbliche.
Le modifiche ai contratti comuni passano dall'integratore. I test d'integrazione
non usano scritture concorrenti sullo stesso schema PostgreSQL. Le correzioni in
sqlmigration hanno checkout e verifiche distinti da genro-sql.

## Indirizzo acquisito e prossimo passaggio

Prima dell'ampliamento V2 è stata realizzata l'[estrazione degli adapter dati](../data-adapters-delivery.md):
compiler comune, adapter SQL PostgreSQL e driver psycopg distinti, preservando
il runtime sincrono e le facciate V1. Il [piano 08](08-data-adapters-plan.md)
conserva compiti e gate assegnati agli agenti; il rapporto distingue risultati e limiti.

La V1 serve applicazioni nuove. Importazione dei package e adozione applicativa
legacy restano obiettivi successivi e non bloccano questa consegna. L'eventuale uso async è rinviato fino al completamento e alla valutazione del nucleo sincrono.
