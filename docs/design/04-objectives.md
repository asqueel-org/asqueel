# 04 — Obiettivi e criteri di accettazione

Gli obiettivi derivano dalle indicazioni dell'utente (S08). I criteri di
accettazione sono la loro traduzione tecnica proposta; esempi e nomi di API
non sono approvati per il solo fatto di comparire nel documento.

## O-01 — Un Asqueel moderno e autonomo

**Richiesta:** conservare il meglio del legacy in un prodotto moderno.
**Risultato:** modello, compiler e runtime con confini dichiarati e utilizzabili
senza caricare obbligatoriamente l'intero framework legacy o un framework UI.
**Accettazione:** una piccola applicazione nativa usa modello, query e DML su
PostgreSQL senza dipendenze dal runtime legacy; il bridge resta opzionale.
**Motivazione:** F-M01/F-M06/F-R01/F-R02.

## O-02 — PostgreSQL prioritario in lettura e scrittura

**Richiesta:** PostgreSQL come backend principale per entrambe le direzioni.
**Risultato:** SELECT e primitive DML complete per il perimetro di release,
binding, tipi, transazioni e gestione corretta dei risultati.
**Accettazione:** SELECT, INSERT/UPDATE/DELETE, RETURNING, conflitti e rollback
su DB reale; modello e mapping identici per lettura e scrittura.
**Motivazione:** F-R01/F-R02/F-R04. Versione minima/driver: D-02.

## O-03 — Altri dialetti con copertura esplicita

**Richiesta:** altri backend ammessi anche se meno completi.
**Risultato:** capability per funzione, server, driver ed estensioni.
**Accettazione:** corpus eseguito nel sottoinsieme dichiarato; errori espliciti
fuori dal perimetro, senza emulazioni silenziose con risultati diversi.
**Motivazione:** F-R03. SQLite è ora un backend richiesto esplicitamente
dall'utente. Il supporto deve essere implementato e verificato; non è ancora
disponibile nel runtime attuale.

## O-04 — Costruzione del modello dal database

**Richiesta:** partire da database esistenti.
**Risultato:** introspezione e ricetta/modello riproducibile, con fedeltà dichiarata.
**Accettazione:** round-trip degli oggetti supportati senza diff inattesi;
oggetti ignoti conservati/segnalati; UI e arricchimenti sopravvivono al reimport.
**Motivazione:** F-M11/F-G01/F-G10.

## O-05 — Costruzione del modello da package e applicazioni legacy

**Richiesta:** importare anche da codice/applicativi legacy.
**Risultato:** inventario statico più esportazione dal modello runtime risolto
quando necessaria; dipendenze, callback e parti non risolte esplicite.
**Accettazione:** applicazione campione con relazioni, virtuali, personalizzazioni,
metadati e naming preservati; rapporto nativo/adattato/collegato/non risolto.
**Motivazione:** F-M06/F-M08/F-M12/F-M13.

## O-06 — Dichiarazione nativa e composizione del modello

**Contesto:** il prodotto conserva la costruzione nativa con Builders.
**Risultato proposto:** stesso contratto semantico per le tre origini e regole
esplicite di composizione dei contributi.
**Accettazione:** dominio campione equivalente dopo import DB, export legacy
e ricetta nativa; conflitti e rimozioni non dipendono da merge accidentali.
**Motivazione:** F-M02–F-M07. Montaggi distribuiti: raccomandazione da validare in D-04.

## O-07 — Informazioni complete della colonna, inclusa l'interfaccia

**Richiesta:** entità unica oppure due entità collegate, definibili insieme o parallelamente.
**Risultato:** identità comune e accesso unificato a dtype, formule, vincoli,
label, formati, editor, lookup, filtri e profili UI.
**Accettazione:** U01–U09; nessuna duplicazione autorevole del tipo/vincoli;
risultati derivati con provenienza; funzionamento headless e nessun DDL per label.
**Motivazione:** F-M08/F-M09/F-M10/F-R10. Forma API: D-05.

## O-08 — Nomi fisici indipendenti dall'identità logica

**Richiesta:** anche prefisso del nome tabella derivato dallo schema.
**Risultato:** schema logico, schema SQL, prefisso e sqlname separati; supporto
alla convenzione package legacy e agli override.
**Accettazione:** NM01–NM06 su query, DML, FK, import e diff; rename conserva
identità/UI; nessuna inferenza arbitraria dagli underscore.
**Motivazione:** F-M14/F-G04.

## O-09 — Compiler nuovo con frontend legacy adattabile

**Richiesta:** riscrittura da specifiche, compatibilità affidabile tramite mixin ammessi.
**Risultato:** nucleo semantico comune e adattatori sottili per sintassi, contesto,
risultati e consumer legacy selezionati.
**Accettazione:** corpus differenziale nel perimetro scelto, differenze dichiarate,
nessuna dipendenza del planner dagli automatismi legacy.
**Motivazione:** F-C01–F-C11/F-C14–F-C20. Profili: D-07.

## O-10 — Eliminazione di aggregateRows

**Vincolo acquisito:** nessuna ricomposizione automatica Python dei join
esplosivi, neppure nel bridge legacy o rinominata in un altro postprocessor.
**Risultato:** migrazione esplicita a aggregati SQL, raccolte definite o righe espanse.
**Accettazione:** C37–C39/L26; diagnostica per richieste del comportamento rimosso;
valori uguali appartenenti a record diversi non vengono persi.
**Motivazione:** F-C12/F-C13. Questo punto non è fra le decisioni aperte.

## O-11 — VirtualRelation della nuova proposta GEP

**Richiesta:** includerle nel modello moderno.
**Risultato:** relation=/table=, target e sorgente distinti, binding var_*,
condizioni, composizione, ordine/limite, cardinalità, UI e aggregati.
**Accettazione:** VR01–VR08; sola lettura, nessuna FK/cluster-write automatica,
nessun aggregateRows; ordine deterministico per limit=1.
**Motivazione:** F-M19/F-M20/F-C20/F-C21. Punti GEP aperti: D-08.

## O-12 — Semantica esplicita di subtable e scope

**Richiesta:** prestare attenzione a subtable, partition e concetti collegati.
**Risultato:** distinguere subset, specializzazione con maintable, scope logico,
tenant/store, virtualRelation e storage partitioning.
**Accettazione:** SP01–SP09, comprese scritture e bypass separati; nessuna
tabella fisica generata soltanto per una specializzazione logica.
**Motivazione:** F-M15–F-M18/F-R04/F-G09.

## O-13 — Scritture con contratti di dominio e concorrenza

**Derivazione tecnica:** la priorità alla scrittura richiede più del rendering DML.
**Risultato proposto:** primitive SQL e operazioni con hook distinti; unità
transazionale, record correlati, versioni attese e conflitti descritti.
**Accettazione:** operazione multi-record atomica, rollback, errore di conflitto
riconoscibile e politica bulk esplicita. Perimetro preciso: D-09.
**Motivazione:** F-R02/F-R04/F-R06/F-R07.

## O-14 — View, trigger e funzioni native in prospettiva

**Richiesta differita:** convivono con hook/funzioni Python; non obbligatori nel primo rilascio.
**Risultato:** oggetti del modello con identità, firme, dipendenze, proprietà,
capability e regole di convivenza. Materialized view è un'estensione proposta.
**Accettazione futura:** DB01–DB05, round-trip e comportamento su DB reale,
nessuna duplicazione delle regole fra trigger e Python.
**Motivazione:** F-R07/F-G06–F-G08. Fasi e proprietà: D-11.

## O-15 — Migrazioni coerenti con l'intero modello fisico supportato

**Richiesta:** asqueel-migration deve poter sostenere l'evoluzione.
**Risultato:** contratto versionato, reader/validator/diff/planner/writer coerenti;
separazione di oggetti gestiti, esterni e ignoti.
**Accettazione:** difetti noti riesaminati e corretti per la release; round-trip,
secondo diff vuoto dove previsto, piano corretto per dipendenze e rename.
**Motivazione:** F-G01–F-G10. Oggetti nativi e partizioni avanzate seguono il calendario differito.

## O-16 — Miglioramenti di sintassi proposti e valutabili

**Richiesta:** proporre ciò che può migliorare la sintassi.
**Proposte:** riferimenti familiari, espressioni a oggetti opzionali, cardinalità
esplicita, EXISTS, raccolte, count distinti, query componibili, parametri-campo
espliciti, alias controllati, one/first distinti, intervalli dichiarati.
**Accettazione della progettazione:** esempi sul medesimo dominio e descrizione
delle differenze legacy. Non tutti i nomi proposti sono requisiti già approvati.
**Motivazione:** F-C08/F-C12/F-C14–F-C21. Decisioni: D-06/D-07/D-08.

## O-17 — Prestazioni misurate senza sacrificare la semantica

**Richiesta:** proporre miglioramenti di prestazioni.
**Proposte:** aggregati per relazione, batch load, proiezioni minime, keyset,
streaming, batch/COPY, cache del compiler e strategie SQL confrontabili.
**Accettazione:** benchmark ripetibile su carichi rappresentativi e confronto
dei risultati prima di dichiarare un miglioramento. Nessun fattore di velocità promesso a priori.
**Motivazione:** F-C22/F-R05/F-R06/F-R08/F-R09. Budget misurabili: D-10.

## O-18 — Tracciabilità, diagnostica e adozione progressiva

**Derivazione tecnica:** serve per verificare importatori, compiler e bridge.
**Risultato proposto:** provenienza, rapporti di import, diagnostiche di scope,
SQL/bind oscurati, effetti delle policy e differenze dal legacy.
**Accettazione:** ogni limite rilevato è visibile; un'applicazione campione può
adottare il nuovo percorso nel perimetro scelto con rollback controllato.
**Motivazione:** F-M13/F-C03/F-C22/F-R08/F-G10. Nessuna doppia esecuzione automatica di DML.

## Perimetro temporale

- Fondamentali iniziali: modello comune, identità/UI/naming, distinzione degli
  scope, PostgreSQL read/write, query semantiche e importazioni su un dominio piccolo.
- Crescita del primo prodotto: bridge selezionato, virtualRelation e aggregati,
  runtime di dominio, verifiche del migratore e applicazione campione.
- Prospettiva: oggetti nativi completi, storage partitioning avanzato e altri
  dialetti secondo necessità. Il modello deve poterli ospitare già nella progettazione.

Questa ripartizione è proposta. Non rinvia i vincoli fondamentali: aggregateRows
resta escluso in ogni fase e UI/naming non sono accessori da aggiungere a posteriori.
