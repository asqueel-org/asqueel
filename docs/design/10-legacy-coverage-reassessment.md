# 10 — Riesame della copertura reale del legacy

29 settembre 2026. Baseline nuova: `b023a9bb25f3135ad1a10fb17a485eac27cf4237`,
committata e pubblicata su main. Questo incremento produce analisi e prove,
non nuove funzionalità del runtime.

## Conclusione e correzione della valutazione

Il codice attuale realizza un nucleo PostgreSQL sincrono e un primo percorso
applicativo coerente. **Non realizza ancora il nucleo funzionale completo del
Asqueel richiesto.** L'assenza operativa di aliasColumn non è un dettaglio di
compatibilità periferico: riguarda il modello che il compiler deve interpretare.
Lo stesso vale per famiglie di formule, sintassi delle relazioni, binding delle
collezioni e aggregazioni di uso ordinario.

I 421 test superati certificano i contratti implementati. Non sono una misura di
copertura del legacy, né provano equivalenza del linguaggio o dei comportamenti.
La precedente espressione «utilizzabile per applicazioni nuove» va delimitata a
un sottoinsieme dimostrato, non intesa come disponibilità generale delle primitive
asqueel necessarie alle applicazioni nuove.

Le specifiche precedenti contenevano già requisiti non implementati, per esempio
VIR-02 per aliasColumn. Il problema è stato anche di tracciabilità: tali requisiti
non erano collegati sistematicamente a stato del codice, test e limiti della
consegna. Non occorre riscrivere da zero una quarta specifica; occorre colmare e
verificare quella esistente, correggendo dove il legacy o le decisioni moderne
la rendono incompleta.

## Fonti e metodo

- Legacy letto: `/Users/gporcari/Sviluppo/Genropy/genropy`, commit
  `fa35e5adfa6ad1b269f3a22a9b12c4c1ee6513ea`. I file SQL esaminati non risultano
  modificati localmente. Tre file di `projects/test_invoice` modificati dal
  proprietario non sono usati come prova della baseline.
- Sorgenti nuovi: `src/asqueel`, test e guide al commit sopra.
- Specifica precedente: [legacy-compatible-spec](../compiler/legacy-compatible-spec.md)
  e [corpus](../compiler/compatibility-cases.md). La loro baseline storica
  `e12f2ce...` non viene confusa con il checkout legacy letto ora.
- GEP locali: `genropy_meta`, commit `d18f3423240dc8c435dd8f7d16f0e76766f8fce9`:
  GEP 1 e GEP 2 sono proposte. Riletta via API anche la
  [revisione virtualRelation](https://github.com/genropy/genropy_meta/issues/1#issuecomment-5803053743).
- Le conversazioni già indicizzate nel precedente audit aiutano a recuperare
  l'intenzione; non certificano funzioni eseguite. Non è stata riletta ogni
  conversazione storica né ogni applicazione cliente.

Tre approfondimenti documentano i percorsi sorgente e le differenze:

1. [Modello, colonne e relazioni](10a-model-feature-audit.md).
2. [Compiler, linguaggio e query](10b-compiler-feature-audit.md).
3. [Runtime, record e scritture](10c-runtime-feature-audit.md).

Per ogni capacità distinguere **D** dichiarazione, **R** risoluzione del modello,
**C** compilazione, **E** esecuzione/consumer. Un successo in D non dimostra R/C/E;
una stringa SQL prodotta in C non dimostra E. Le letture del sorgente legacy sono
prove di implementazione osservata, non un oracle differenziale eseguito.

## Matrice riassuntiva dello stato operativo

| Famiglia | Stato attuale e lacuna sostanziale | Priorità |
|---|---|---|
| Configurazione → oggetti | Percorso presente e verificato; non equivale alla composizione di package/mixin legacy | Base da conservare |
| Colonne fisiche, naming, UI | Supportate; import e override dei metadati applicativi non ancora completi | Base + verifiche |
| aliasColumn | D presente, R rifiutata. Nel legacy eredita attributi della colonna destinazione e applica gli override dell'alias | Fondamentale |
| formulaColumn SQL | Espressioni e riferimenti ad altre formule supportati, cicli rilevati; non tutte le forme legacy | Fondamentale, parziale |
| Formule select/exists | D presente in forma ridotta, R rifiutata; mancano scope correlato, default e binding locali | Fondamentale |
| Formula callback/varianti | Mancano provider, variabili locali e istanze parametrizzate equivalenti | Contratto da selezionare |
| subQueryColumn | D presente, R rifiutata | Fondamentale per raccolte esplicite |
| pyColumn | D presente, R rifiutata; manca anche la fase di calcolo sui risultati | Contratto da selezionare |
| Colonna composita | Vincoli/relazioni composte supportati nel sottoinsieme; il valore virtuale legacy non è disponibile come `$composite` | Distinguere le due semantiche |
| Percorsi to-one | Supportati nel dialetto sintattico nuovo; non equivalenti a tutte le forme legacy multi-hop | Fondamentale |
| Reverse/to-many | Non implementati come navigazione generale del modello/linguaggio | Fondamentale per asqueel |
| virtualRelation | Richiesta moderna/GEP, non funzione già presente nel nuovo modello | Fondamentale nel percorso relazioni |
| Parametri scalari | Binding supportato | Base da conservare |
| Parametri lista/tupla | La forma legacy `IN :ids` fallisce su PostgreSQL nel nuovo percorso; `ANY` non è equivalenza sintattica | Fondamentale |
| DISTINCT/GROUP BY/HAVING | Opzioni native rifiutate | Fondamentale |
| COUNT SQL / terminale count | SQL aggregato semplice possibile; `.count()` assente, semantica con filtri/gruppi da definire | Fondamentale |
| Wildcard/alias impliciti/PK/default order | Convenzioni differenti; non qualificare SELECT come equivalente senza precisarle | Contratto nativo + bridge |
| Filtri Bag/dizionari/operatori | Traduttore applicativo legacy non ricostruito | Nuove app se usano filtri strutturati |
| Macro legacy | PERIOD, ENV/PREF/BAG e altri contesti non equivalenti; distinguere dal binding `:env_*` | Inventario d'uso e selezione |
| Record e risultati | Dict, cardinalità e refresh presenti; niente Bag/Selection/resolver, niente invalidazione automatica | Profilo risultati da completare |
| Sessione e lock | Transazione condivisa, rollback e lock PostgreSQL verificati | Base da conservare |
| Sei hook di tabella | Presenti; protezioni, field trigger, callback di package, contatori e cascata assenti | Lifecycle da selezionare |
| Conversioni adapter | SQL e binding separati; non tutte le conversioni applicative legacy trasferite | Fondamentale per tipi scelti |
| Policy | Partition logiche/draft/deleted presenti, semantica moderna deliberata | Base da conservare |
| Subtable/partizioni fisiche | Assenti, non assimilabili alle partition logiche | Requisiti distinti |
| Modello da DB | Introspezione disponibile per sottoinsieme; non equivale a import applicazione o sua logica | Integrazione da completare |
| Modello da package legacy | Assente | Traguardo successivo esplicito |
| View/funzioni/trigger nativi | Manca un lifecycle completo modello/introspezione/diff/applicazione | Traguardo futuro concordato |
| Altri dialetti/store/tenant/async | Non implementati; rinvii già acquisiti | Non distrarre dal nucleo |
| aggregateRows | Escluso deliberatamente, anche dal bridge | Non recuperare |

Le priorità non affermano che ogni convenzione legacy vada copiata. Separano
concetti fondamentali, forme compatibili opzionali e funzionalità esplicitamente
rinviate dall'utente. La compatibilità sintattica richiede test distinti anche
quando il nuovo sistema offre un'espressione alternativa equivalente.

## Prove riproducibili di questo audit

### Dichiarazione / risoluzione / compilazione

[evidence/native_feature_probes.py](evidence/native_feature_probes.py) esegue
15 sonde senza DB; l'[output](evidence/native_feature_probes.json) registra fase,
SQL oppure classe/descrizione dell'errore. La formula semplice, la catena di
formule e una proiezione to-one arrivano alla compilazione. Alias, select/exists,
subquery e Python column sono fermate dal resolver; altri casi falliscono nel
costruire o compilare la query. aggregateRows è un rifiuto atteso per decisione,
non una funzionalità da recuperare. Non è una percentuale di conformità.

### Binding su PostgreSQL reale

[evidence/native_binding_probes.py](evidence/native_binding_probes.py) crea uno
schema temporaneo univoco, lo elimina al termine e usa solo un DB di test indicato
in `ASQUEEL_TEST_DSN`. L'[output](evidence/native_binding_probes.json) riporta:

| Input | Risultato nativo PostgreSQL |
|---|---|
| `$id IN :ids`, lista `[1,2]` | SyntaxError |
| `$id IN :ids`, tupla `(1,2)` | SyntaxError |
| `$id IN (:ids)`, lista `[1,2]` | UndefinedFunction |
| `$id = ANY(:ids)`, lista `[1,2]` | Righe 1 e 2 |
| `$id IN :ids`, lista vuota | SyntaxError |
| `$id = ANY(:ids)`, lista vuota | Nessuna riga |

Queste prove misurano il nuovo percorso, non eseguono il legacy. L'adattamento
legacy delle collezioni è analizzato nel documento 10b. NULL, NOT IN e binding
ripetuti richiedono ulteriori casi prima di scegliere la traduzione moderna.

## virtualRelation: requisito moderno da integrare nel modello

La proposta riletta distingue relazioni derivate da `relation=` e relazioni
funzionali dichiarate con `table=`/`condition=`, con variabili correlate. Introduce
`order_by`/`limit`, `one_one` e possibili parametri richiesti da `ask`. `limit=1`
implica una vista a una riga; `one_one` senza limite è una garanzia sui dati da
verificare, non un vincolo SQL automaticamente presente.

Il GEP 1 porta funzioni su percorsi, aggregazioni e risultati espliciti. Il modello
nuovo deve poter rappresentare cardinalità, correlazione e dipendenze necessarie,
prima di scegliere la resa SQL. Una relazione virtuale non è aliasColumn; un'alias
non è `AS`; una collezione esplicita non è aggregateRows. La soluzione non va
ridotta ad aggiungere più stringhe speciali a un campo `formula`.

## Nuova sequenza proposta, con prove di completamento

| Passo | Obiettivo | Gate concreto |
|---|---|---|
| A. Contratti delle colonne | Fisica / alias / formula / sottoquery / Python distinti; dtype/UI/lineage e cicli; errori prima dell'esecuzione | Alias semplice, su formula e annidato; target nullable; override metadata; cicli; tutte le clausole supportate |
| B. Linguaggio di base | Percorsi legacy selezionati, binding collezioni, distinct/group/having/count | Corpus differenziale per righe, NULL, parametri e metadati; niente sola uguaglianza di stringhe SQL |
| C. Relazioni e correlazione | Reverse/to-many, virtualRelation, scope sottoquery e aggregati/raccolte espliciti | Due relazioni many indipendenti senza moltiplicazione indebita; where/order su risultati; contesti e alias di correlazione |
| D. Consumer e lifecycle | Record/Selection/Bag scelti, conversioni, filtri strutturati e callback fondamentali | Flusso completo di una nuova applicazione, lettura-modifica-scrittura con formule e relazioni, rollback e fine sessione |
| E. Import / bridge | Package campione e configurazione prodotta, mapping di comportamenti, perdite dichiarate | Applicazione campione riproducibile, nessuna funzione dichiarata ma ignorata |
| F. Estensioni già rinviate | Prestazioni misurate, altri dialetti, oggetti SQL nativi, partizioni fisiche | Gate autonomi per ogni famiglia, senza trasformarle in copertura fittizia del nucleo |

A e B possono essere scomposti, ma nessun alias viene considerato concluso solo
perché una SELECT produce il testo atteso. Prima di ogni implementazione si
scrive il contratto del consumer e il relativo caso osservabile.

## Come evitare un'altra sovrastima

1. Collegare gli ID già presenti nella specifica e nel corpus a test eseguibili;
   quelli mancanti restano **non verificati**, non coperti da un test generico.
2. Per il linguaggio compatibile acquisire output legacy su fixture controllate;
   ogni differenza viene classificata come voluta, lacuna o difetto legacy.
3. Esporre i limiti nella documentazione applicativa e nella diagnostica: le
   dichiarazioni conservabili per migration non sono automaticamente eseguibili.
4. Separare stato storico e attuale dei piani. Il documento 07 è una proposta
   precedente: le sue esclusioni V1 non giustificano automaticamente nuove
   esclusioni di concetti fondamentali.
5. Misurare copertura dei requisiti scelti, non soltanto line coverage. Non
   assegnare ora una percentuale di completamento del prodotto.

Restano da eseguire l'oracle legacy completo, la verifica di un'applicazione
campione e la revisione degli usi nei repository dei clienti. Questo audit
riduce le lacune note; non dichiara «esaminato tutto il legacy».
