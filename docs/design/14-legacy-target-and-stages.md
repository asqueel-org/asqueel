# 14 — Traguardo del prodotto e tappe proposte dopo l'audit legacy

Questo documento risponde a «dove si può e si deve arrivare». Si basa sui
[contratti LT01–LT42](13-legacy-test-audit.md), non amplia unilateralmente il
perimetro approvato e non dichiara completata una versione. L'ordine è una
proposta da concordare prima di introdurre differenze di comportamento.

## Traguardo

Un Genro SQL sincrono per nuove applicazioni, centrato su `db`, ottenuto dal
rendering della configurazione dichiarativa con grammatiche in cascata.
L'esperienza quotidiana deve conservare il meglio del legacy:

```python
customer = db.table('cont.cliente')
rows = customer.query(
    columns='$id,$name,@state_id.name AS state_name',
    where='$active=:active', active=True
).fetch()
```

I path devono essere utilizzabili dal compiler, dall'introspezione del modello
e dalla navigazione dei dati. Definizioni fisiche, formule, alias, relazioni e
informazioni UI devono descrivere la stessa colonna, con origine e override
comprensibili. Scritture sulla stessa sessione cooperano nella transazione
implicita, conclusa secondo il contratto applicativo con commit/rollback.

Il linguaggio legacy è il riferimento. Mixin di adattamento possono gestire
forme storiche, senza costringere il nucleo a dipendere dall'intero framework.
Un requisito non ancora implementato va dichiarato tale; la parola «moderno»
non autorizza a sostituire silenziosamente nomi, default o semantiche.

## Decisioni già acquisite

- Sinc prima; un'eventuale API async si valuta dopo, senza condividere Bag
  mutabili tra thread o task come se fossero sicure.
- PostgreSQL prima in lettura e scrittura; altri dialect con capacità esplicite.
- Configurazione → rendering → oggetti vivi; db è l'oggetto primario.
- Modello importabile da DB e, progressivamente, da package/applicativi legacy.
- Metadati UI sulla colonna o in una seconda entità collegata.
- Partition applicativa esplicita: 0/False validi, allowed=[] nessuna riga,
  contesto necessario assente errore, bypass solo esplicito.
- Nessun aggregateRows.
- Store e tenant possono seguire; view, trigger e funzioni native sono obiettivi
  di prospettiva, con supporto coerente nelle migrazioni.

## Tappa A — Contratti quotidiani coerenti, candidata alla prima versione utile

**Dipendenze:** fissare prima gli oracle di LT04, LT09, LT12, LT15, LT26, LT27.
Sono punti dove una differenza può rompere codice semplice senza che la query
sembri complessa. Recuperare default legacy salvo decisione diversa esplicita.

| Gruppo | Risultato da consegnare | Prova di accettazione |
|---|---|---|
| Transazioni | Avvio implicito, commit/rollback e comportamento errore coerenti; documentazione sul db applicativo | Due scritture atomiche; errore SQL dopo la prima; persistenza verificata con connessione indipendente; comportamento dopo rollback; nessun obbligo di context manager. |
| Environment | currentEnv/tempEnv e default necessari con contratto concordato | Scope annidati, ripristino su errore, valori falsy, parametri env e assenza di contaminazione tra unità di lavoro. |
| Modello e path | Lookup colonne locali/$/path; metadati alias e grafo relazioni coerenti | `@customer_id.state`, percorso a tre hop, alias verso formula; errori distinti per colonna e relazione inesistente; nessun SQL per sola introspezione. |
| Query | count, distinct, group/having, IN/NOT IN, wildcard e default risultati | Confronti legacy su duplicati, NULL, lista vuota, gruppi, limit/offset; chiavi e tipi delle righe esatti, pkey e ordinamento verificati. |
| Record e fetch | Lettura singola/mancante/duplicata e terminali dati essenziali | PK 0, composite, filtro keyword, ignoreMissing/ignoreDuplicate ove previsti, fetchPkeys/AsDict con casi di collisione definiti. |
| Policy | Draft, deleted e partition integrate in query/formule/CRUD | Valori NULL/False/True, mark, combinazione current/allowed, relazione partition e bypass esplicito. |
| Scritture | CRUD, chiavi, old_record, hook e callback al commit necessari | Ordine dei callback, rollback che non produce notifiche, update concorrente e nessuna modifica parziale dopo errore. |

**Criterio d'uscita:** percorso applicativo realistico configurazione → render →
query relazionali → record → scritture → commit/rollback, con test PostgreSQL
ripetibili e documentazione inglese i cui esempi sono eseguiti. Una lista di API
esistenti o il solo numero di test verdi non basta. Selection completa, UI e
oggetti SQL nativi non sono automaticamente requisiti della prima release;
la loro collocazione resta esplicita nelle tappe successive.

## Tappa B — Modello espressivo e compiler avanzato

Dipende da A per path, proiezioni e cardinalità. Copre LT05–LT10, LT17–LT21.

- Virtual relation secondo la GEP: tradurre ciascuna forma prevista in un caso
  eseguibile, separandola dalle sole formula-FK già viste nei test.
- joinColumn, relazioni su virtuali, aliasTable multi-hop e relazioni inverse.
- compositeColumn compatibile dove necessario, distinta dalla PK fisica composta.
- Provider formule e sottoquery, varianti/var_*, pyColumn e bagItemColumn;
  valori reali attesi, non sole verifiche di chiavi presenti.
- Raccolte correlate JSON/Bag con cardinalità e ordinamento espliciti.
  Due raccolte indipendenti non devono moltiplicarsi a vicenda né richiedere aggregateRows.
- Subtables logiche: selettori, negazione, combinazioni, contesto, parametri,
  interazione con draft/deleted/partition e formule sintetiche.
- Sistema di estensioni del compiler con sintassi macro compatibile `#NOME`,
  nucleo minimo, estensioni package e capacità per dialect; elaborazione
  strutturata di SQL, parametri, riferimenti e trasformazioni dei risultati.

**Criterio d'uscita:** fixture fatture/clienti/righe con alias profondi, aggregati
correlati, una relazione virtuale e due raccolte; confronto dati col legacy
quando il contratto è conservato. Ogni deviazione concordata ha una prova propria.

## Tappa C — Servizi applicativi e interoperabilità legacy

Copre LT01, LT03, LT23–LT25, LT28–LT31, LT34–LT35.

- Selection e output essenziali; resolver one/many, Bag e serializzazione.
  Specificare quali output appartengono al nucleo e quali al ponte legacy.
- Record cluster, scritture correlate, cascata applicativa, contatori/gerarchie.
- Metadati UI e required_columns: esempio completo in cui il consumatore UI
  trova tipo, caption, vincoli e dipendenze anche tramite un path.
- Importazione dichiarazioni da package legacy: rapporto delle funzionalità
  tradotte, non traducibili e dipendenti dall'applicazione; niente omissioni silenziose.
- Eventi/notifiche e listener, cifratura e masking dove richiesti dalle app.

**Criterio d'uscita:** importare un piccolo package reale, renderizzarlo e usarlo
con query, scritture e un consumatore di metadati UI. Confrontare prima/dopo;
le eventuali dipendenze dal framework restano visibili nel mixin di adattamento.

## Tappa D — Strutture avanzate, sqlmigration e più dialect

Percorso in parte parallelo ad A–C, con contratti condivisi sui descriptor.
Copre LT02, LT36–LT41 e gli obiettivi futuri non esauriti dai test legacy.

1. Roundtrip DB → modello → piano di migrazione vuoto per il profilo supportato;
   preservare schema, prefissi, tipi, PK/FK/unique/indici e nomi fisici.
2. Migrazioni con dipendenze e dati: prima colonna poi indici/vincoli; secondo
   diff vuoto; operazioni distruttive esplicite, diagnostica e recuperabilità.
3. View, funzioni e trigger SQL nativi accanto agli hook Python: identità,
   dipendenze, corpo/linguaggio, versione e gestione del diff. Importare un DB
   con oggetti non supportati deve segnalarli, non fingere equivalenza completa.
4. Partition fisiche: dichiarazione, introspezione, attach/detach, chiavi/vincoli,
   routing delle scritture e migrazioni; separate dalle subtables logiche.
5. Store/tenant successivi, chiarendo confini di transazione e risoluzione nomi.
6. Altri dialect dati, capability matrix verificata e fallimento esplicito dove
   manca un'operazione; DDL delegato agli adapter di sqlmigration.

**Criterio d'uscita per ogni capacità:** introspezione e dichiarazione producono
lo stesso modello supportato; query/CRUD operativi quando applicabili; diff,
apply e secondo diff coerenti; dipendenze non perse.

## Prestazioni: misurare durante tutte le tappe

Riutilizzare i casi legacy di path profondi e cache fredda/calda, ma introdurre
misure ripetibili: tempo di render, compilazione, esecuzione e materializzazione,
numero di roundtrip, memoria dei risultati e dimensione delle cache. Per SQL
confrontare piani e righe intermedie oltre al tempo totale.

Valutare cache di risoluzione e piano compilato soltanto con chiavi che includano
revisione del modello, dialect e opzioni che cambiano il piano. I valori bind
non devono contaminare le esecuzioni successive; l'environment può cambiare
policy e query. Testare invalidazione e limiti delle cache prima di dichiarare
un miglioramento. Nessuna promessa async o multithread precede questi risultati.

## Prossima attività concreta

Costruire i primi oracle della tappa A su transazioni, path e forma dei risultati.
Per ogni discrepanza, mostrare esempio legacy, comportamento attuale e modifica
proposta prima di cambiare un contratto. Poi correggere prodotto e manuale insieme.
L'audit consegnato qui non esegue questa implementazione e non effettua commit/push.
