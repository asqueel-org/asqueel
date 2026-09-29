# 02 — Finding: compiler, linguaggio e compatibilità

Fonti: [registro](00-sources-and-evidence.md). La
[specifica puntuale](../compiler/legacy-compatible-spec.md) contiene contratti
e casi limite; questo documento espone i finding e le conseguenze progettuali.

## F-C01 — Il linguaggio legacy è SQL esteso, non un DSL chiuso

**Evidenza:** COD, S02 compiler: SQL opaco con $campo, @relazione, parametri e macro.
Funzioni, CASE, cast, finestre e FILTER possono passare come SQL del dialetto.
**Conseguenza:** un elenco finito di funzioni non basta a garantirne la copertura.
**Verifica:** corpus SQL reale e lexer capace di preservare stringhe/commenti;
LEX-01–LEX-11 definiscono il confine fra parsing Genro e SQL opaco.

## F-C02 — Il compiler integra più responsabilità nello stesso passaggio

**Evidenza:** COD, S02 `compiledQuery`, `updateFieldDict`, `getFieldAlias`:
normalizzazione, risoluzione, effetti sui join e metadati procedono insieme.
**Conseguenza:** il nuovo nucleo dovrebbe separare parsing, modello, scope,
politiche, piano SQL e risultati. Copiare il flusso perpetuerebbe gli accoppiamenti.
**Verifica:** stesso resolver usato da frontend testuale, filtri Bag e formule.

## F-C03 — compiler_next non implementa ancora la nuova semantica

**Evidenza:** PRO/COD, S02 moduli compiler e test_compiler_next_sync.
I moduli risultano uguali dopo la normalizzazione upstream; classi indipendenti.
La factory seleziona next mediante experimental.db.next_sql_compiler.
**Conseguenza:** il punto di selezione è riutilizzabile, non prova di compiler nuovo finito.
**Verifica:** futuro collegamento coerente per query e record, con rollback controllato.

## F-C04 — Gli esperimenti storici sono filoni diversi

**Evidenza:** DIS/COD, S06/S07 e roadmap storiche: compiler_new, v2/v3,
compound query e sq_as_join non coincidono con compiler_next di settembre.
**Conseguenza:** recuperare idee e casi testati senza attribuire le feature
a develop o assumere che i branch siano componibili senza revisione.
**Verifica:** qualsiasi riuso richiede riferimento preciso a commit e test.

## F-C05 — La risoluzione delle relazioni costruisce JOIN con effetti collaterali

**Evidenza:** COD, S02 `_getRelationAlias`: LEFT JOIN, alias riusati per percorso
e base, direzioni O/M, composite, condizioni e tenant; many tracciate come esplosive.
**Conseguenza:** il nuovo grafo dei join deve conservare identità del percorso,
scope e cardinalità. Due FK alla stessa tabella non sono lo stesso join.
**Verifica:** J01–J30, comprese dipendenze generate dalle condizioni ON.

## F-C06 — Le virtuali hanno molteplici forme e scope

**Evidenza:** COD, S02 getFieldAlias e getVirtualColumn: alias, SQL formula,
callback, select/exists, select_nome, var_*, varianti da parametri e pyColumn.
**Conseguenza:** una virtuale non è semplicemente una stringa SQL; può dipendere
da provider e contesto. I cicli necessitano diagnostica.
**Verifica:** VIR-01–VIR-19, varianti concorrenti e relazioni verso virtuali.

## F-C07 — I default delle sottoquery differiscono da quelli esterni

**Evidenza:** COD, S02 select virtuali: partizione ignorata, draft/deleted inclusi,
subtable='*', niente pkey o ordine tabella aggiunti, salvo le opzioni applicabili.
#THIS si riferisce al proprietario della formula nel suo alias corrente.
**Conseguenza:** non propagare indiscriminatamente policy esterne alle sottoquery.
**Verifica:** V15–V17 e query con formula raggiunta attraverso più relazioni.

## F-C08 — Parametri e ambiente svolgono anche ruoli strutturali

**Evidenza:** COD, S02 embedFieldPars, var_*, queryCompile, execute:
alcuni parametri diventano campi, altri contengono varianti o stato di macro;
nomi generati possono usare id Python.
**Conseguenza:** il nuovo binder deve distinguere valori, riferimenti e contesto.
La cache non può ignorare le varianti strutturali né condividere valori fra utenti.
**Verifica:** P01–P15, V18–V20 e scope annidati.

## F-C09 — Le macro non sono abilitate uniformemente nelle clausole

**Evidenza:** COD, S02 chiamate esplicite agli expander: PERIOD nel WHERE query,
ENV/PREF nelle formule, BAG nelle proiezioni, rank in contesti dedicati.
GROUP BY/HAVING e WHERE record non ricevono una pipeline generale identica.
**Conseguenza:** definire firme, contesti, dipendenze e fasi, mantenendo il
frontend legacy aderente alla matrice quando richiesto.
**Verifica:** MAC-01–MAC-25 e M18 per i contesti non ammessi.

## F-C10 — Full-text ha due trasformatori che possono interferire

**Evidenza:** COD/INF, S02 base PostgreSQL MacroExpander e psycopg2
TsVectorCompiler finale. Sintassi, default e momento della sostituzione differiscono.
L'espansione rank tardiva può reintrodurre token logici dal contesto.
**Conseguenza:** il solo test dell'expander non dimostra SQL finale eseguibile.
**Verifica:** M19–M23/M29–M30 su driver reali, forma diretta e formula; anomalie A14/A18.

## F-C11 — Vector registra una ricerca, non una soglia automatica

**Evidenza:** COD, S02 VECQUERY genera IS NOT NULL e conserva canale/target;
VECRANK genera la similarità. Canale mancante può produrre KeyError.
**Conseguenza:** filtro di soglia, ordinamento e top-k sono intenzioni distinte.
**Verifica:** M24–M26 su PostgreSQL con estensione pertinente, non solo regex.

## F-C12 — Aggregare un join piatto cambia l'insieme su cui si calcola

**Evidenza:** PRO/DIS, dataset del corpus e issue legacy #1354.
Per C1: totale fatture 250; sul join fatture-righe 550; SUM DISTINCT 150.
Sono risultati di insiemi diversi, non differenze di formattazione.
**Conseguenza:** aggregati per relazione nel modello nativo, scope annidati espliciti.
**Verifica:** C35–C36 e casi con due many indipendenti, NULL e valori ripetuti.

## F-C13 — aggregateRows perde informazione: rimozione già decisa

**Evidenza:** COD/DIS, S02 selection._aggregateRows deduplica per valore;
problemi di dtype e alias sono documentati anche in #1354. S08 ne impone l'eliminazione.
**Conseguenza:** nessuna emulazione nel bridge. Migrare gli usi verso aggregati SQL,
raccolte esplicite o righe espanse; segnalare richieste del comportamento rimosso.
**Verifica:** C37–C39 e L26 diventano casi di migrazione, non di parità con il difetto.

## F-C14 — Pkey, DISTINCT e count hanno automatismi non uniformi

**Evidenza:** COD, S02 compiledQuery normalizza distinct falsy, rileva SUM/COUNT
testualmente e decide alcune opzioni prima di tale rilevamento. count ha un
percorso separato e mantiene limiti; può contare righe/gruppi o leggere una cella.
**Conseguenza:** definire conteggi nativi espliciti; nel bridge caratterizzare
ogni combinazione senza fidarsi dei commenti del codice.
**Verifica:** C16–C34 con risultati esatti, non soltanto n>0; A04–A06/A11.

## F-C15 — Alias e wildcard hanno anomalie di compatibilità

**Evidenza:** COD, S02 expandMultipleColumns: *prefix principale non filtra
come documentato; AS è analizzato testualmente; alias duplicati sovrascrivono;
auto-DISTINCT può aggiungere __ord_col_N.
**Conseguenza:** distinguere alias pubblici da interni e dare una politica
esplicita alle collisioni. Un nuovo parser migliore può cambiare casi accidentali.
**Verifica:** L03/L13–L16/L22, C24 e decisioni A01–A03.

## F-C16 — Intervalli e date non hanno un'unica semantica implicita

**Evidenza:** COD, S02 IN_RANGE include high, between della relazione lo esclude;
PERIOD delega al decoder localizzato con workdate. Query Bag può cambiare operatore.
**Conseguenza:** conservare distinzioni nel bridge; nel nativo rendere espliciti
tipo di intervallo, locale e trattamento timestamp/timezone.
**Verifica:** M01–M11, B10, confini anno/mese e valori NULL.

## F-C17 — Query Bag è un linguaggio di ingresso autonomo

**Evidenza:** COD, S02 GnrWhereTranslator: gruppi, operatori, dtype, conversioni,
parametri, cifratura Q e callback; prima della traduzione risolve la colonna sul modello.
**Conseguenza:** non basta accettare nuove espressioni nel compiler testuale:
l'editor delle query deve accedere allo stesso resolver e ai metadati UI.
**Verifica:** B01–B14 e filtri sulle nuove relazioni/virtuali.

## F-C18 — Il record singolo ha un contratto diverso dalla query limitata

**Evidenza:** COD, S02 compiledRecordQuery/SqlRecord: resultmap, alias strutturali,
modalità DynItem, virtuali statiche, lazy/eager, errori e filtri costruiti dal wrapper.
**Conseguenza:** non sostituire con SELECT LIMIT 1. Il bridge deve preservare
i consumer rilevanti oppure dichiarare una migrazione della loro API.
**Verifica:** R01–R14, anche aliasPrefix, nomi fisici e duplicati logicamente cancellati.

## F-C19 — I risultati richiedono metadati e trasformazioni espliciti

**Evidenza:** COD, S02 fetch/selection: pyColumn, decifratura, Bag, colAttrs;
cursor e multistore possono percorrere rami diversi.
**Conseguenza:** result plan con tipo, origine, conversioni e consumer supportati.
Queste trasformazioni restano distinte dall'aggregateRows rimosso.
**Verifica:** O01–O07 e U06, alias di colonne cifrate e pyColumn correlate.

## F-C20 — GEP e vecchia sintassi non vanno sovrapposti implicitamente

**Evidenza:** DIS/COD, S06 funzioni sui percorsi e virtualRelation;
S02 SUM(@rel.total) resta aggregazione SQL sul join.
**Conseguenza:** una nuova forma @rel.sum($total) deve avere semantica propria.
var_* come espressioni sorgente nelle virtualRelation non equivale al var_* costante legacy.
**Verifica:** confronti intenzionali delle due sintassi, VR01–VR08 e aggregati annidati.

## F-C21 — La grammatica nuova deve distinguere esistenza e molteplicità

**Evidenza:** INF da F-C05/F-C12: due predicati sullo stesso figlio non equivalgono
necessariamente a due predicati soddisfatti da figli diversi.
**Conseguenza:** EXISTS, NOT EXISTS, aggregato, raccolta ed espansione devono
conservare scope espliciti. Nessuna riscrittura indiscriminata da many join a EXISTS.
**Verifica:** due figli che soddisfano separatamente A e B, ma nessuno entrambi.

## F-C22 — SQL valido non dimostra equivalenza né prestazioni

**Evidenza:** COD/INF, test upstream esaminati includono asserzioni deboli;
il nuovo compiler non è ancora eseguito. Il piano fisico dipende da dati e statistiche.
**Conseguenza:** test differenziali su risultati/duplicati/metadati più benchmark
separati. Nessuna promessa che LATERAL, CTE o join preaggregato sia sempre migliore.
**Verifica:** dataset avverso, query applicative, EXPLAIN e misure del carico reale.

## Registro delle anomalie già censite

Il dettaglio resta nella specifica; qui è mantenuta la copertura tematica.

| Anomalie | Finding pertinenti | Stato |
|---|---|---|
| A01 wildcard; A02 lexer; A03 alias | F-C01, F-C15 | Da caratterizzare e decidere per il bridge. |
| A04 aggregazione/pkey; A05 DISTINCT; A06 count | F-C14 | Risposte esatte da fissare con oracle. |
| A07 aggregateRows | F-C13 | Rimozione acquisita, anche nel bridge. |
| A08 ENV/PREF; A09 nomi parametri | F-C08, F-C09 | Contratto nativo esplicito, differenze legacy da registrare. |
| A10 join particolari/composite | F-C05 | Prove reali necessarie. |
| A11 falsy/record; A12 liste/NULL driver | F-C14, F-C18; F-R03 | Verifiche per ingresso e driver. |
| A13 macro registry; A14 rank; A18 doppio full-text | F-C09, F-C10 | Distinguere unit test e integrazione. |
| A15 parametri-campo; A16 subtable | F-C08; F-M15 | Scope e parsing da esplicitare. |
| A17 postprocessing; A19 record naming | F-C19, F-C18 | Matrice dei consumer. |
