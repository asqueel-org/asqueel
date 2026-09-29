# 01 — Finding: modello, importazione e interfaccia

Legenda e versioni: [fonti](00-sources-and-evidence.md).

## F-M01 — Il package attuale è una base dichiarativa, non l'intero ORM

**Evidenza:** COD, S01: `builder.py`, `catalog.py`, `reader.py`, `migration.py`.
Esistono costruzione, validazione, proiezione normalizzata, ricostruzione e
emissione Python. Non costituiscono un runtime equivalente a GnrSqlDb.
**Conseguenza:** conservare questa base, aggiungendo contratti semantici e runtime.
**Verifica necessaria:** un modello minimo usato realmente in lettura e scrittura.

## F-M02 — Gerarchia esplicita e namespace separati

**Evidenza:** COD, S01: `elements.py`, gerarchia db/schemas/schema/tables/table
e collezioni columns, virtual_columns, composites, constraints, indexes.
Le famiglie ripetute sono indirizzate per nome nelle proprie collezioni.
**Conseguenza:** la separazione evita collisioni fra famiglie, ma l'identità
persistente non deve dipendere esclusivamente da un percorso rinominabile.
**Verifica:** stessi riferimenti dopo rename logico/fisico e ricomposizione.

## F-M03 — Quattro mixin non sono quattro grammatiche montate

**Evidenza:** COD, S01: `SqlBuilder(DbElements, SchemaElements, TableElements,
ColumnElements, BuilderBase)` compone un vocabolario unico. Non usa ConfigHandler
né montaggi dinamici per schema e tabella.
**Conseguenza:** modularità del codice non equivale a grammatica distribuita.
**Verifica:** definire quali estensioni richiedono realmente un vocabolario proprio.

## F-M04 — Il montaggio non perde necessariamente gli indirizzi per nome

**Evidenza:** PRO, S03: due montaggi conservano il percorso della colonna id.
Il commento in SqlBuilder che esclude le sotto-grammatiche è troppo categorico.
**Conseguenza:** la decisione va basata sull'integrazione, non su quel limite presunto.
**Limite:** non provati ancora validatori SQL, emitter, default e serializzazione
delle classi montate. Il prototipo non dimostra una sostituzione pronta.

## F-M05 — Composizione delle ricette e grammatica sono due contratti

**Evidenza:** COD, S03: subbuilder per riferimento e ConfigHandler parents
sono meccanismi separati; il secondo unisce Bag per chiave/attributo.
**Conseguenza:** per il modello SQL servono anche conflitti, rimozioni e rename
espliciti. Non equiparare un nodo vuoto alla cancellazione di un oggetto.
**Verifica:** package/app/istanza con override, estensione e rimozione distinti.

## F-M06 — Il legacy costruisce un modello runtime più ricco della source

**Evidenza:** COD, S02: `gnrsqlmodel/model.py:DbModel.build` applica mixin,
config_db, personalizzazioni e callback, costruisce oggetti e registra relazioni.
**Conseguenza:** l'import statico dei file non ricostruisce sempre il modello effettivo.
**Verifica:** confrontare dichiarazioni e modello finale di una vera applicazione.

## F-M07 — Modello fisico e modello semantico non coincidono

**Evidenza:** COD, S01/S02: relazioni senza FK, virtuali, alias e callback sono
consumati dal compiler legacy ma non si riducono al JSON delle migrazioni.
**Conseguenza:** distinguere proiezione fisica e descrittori semantici; non generare
vincoli fisici da ogni relazione navigabile.
**Verifica:** stesso modello con relazione logica non vincolata e FK reale.

## F-M08 — I metadati applicativi hanno contratti non allineati

**Evidenza:** COD/DIS, S01 `validators.py` richiede x_ per extra sconosciuti;
S07 richiedeva preservazione degli attributi applicativi legacy.
**Conseguenza:** inventario e mappatura degli extra sono necessari per importare
senza perdita. La validazione nativa può essere rigorosa senza scartare dati importati.
**Verifica:** attributi noti, custom e sconosciuti, con provenienza e round-trip.

## F-M09 — UI e colonna devono condividere un'identità

**Evidenza:** COD/DIS, S02: formati, dtype ed etichette sono consumati nei risultati;
S08 richiede dichiarazione UI integrata o parallela con entità collegate.
**Conseguenza:** offrire una vista unificata dei metadati risolti; non duplicare
tipo, formula e vincoli nel descrittore UI. Gli override di vista restano contestuali.
**Verifica:** U01–U09 del corpus, comprese modalità headless e assenza di DDL per label.

## F-M10 — Una colonna derivata richiede metadati propri

**Evidenza:** COD/INF, S02: aliasDict e _prepColAttrs ricostruiscono la provenienza;
gli aggregatori legacy mostrano problemi di alias/dtype.
**Conseguenza:** un result plan deve conoscere tipo, origine e scrivibilità.
Un SUM non eredita automaticamente editor e capacità di modifica della colonna base.
**Verifica:** alias, formule, aggregati e colonne omonime di tabelle diverse.

## F-M11 — Database → modello recupera solo le informazioni presenti nel DB

**Evidenza:** INF, S01 reader di strutture normalizzate e natura delle informazioni.
Il DB può descrivere vincoli/default e oggetti nativi, non ricostruire callback
Python, package originari o UI mai memorizzata.
**Conseguenza:** import fisico più arricchimenti separati, rapporto di fedeltà e
gestione degli oggetti non supportati. Un nome *_id è solo un indizio di relazione.
**Verifica:** reimport senza sovrascrivere gli arricchimenti e senza DDL sul sorgente.

## F-M12 — L'export dal runtime legacy richiede un ambiente controllato

**Evidenza:** COD/INF, S02 DbModel.build e callback; S07 obiettivo di sostituire la source.
Avviare un'applicazione può eseguire codice, aprire servizi e richiedere dipendenze.
**Conseguenza:** esportatore dedicato, contesto dichiarato e classificazione
nativo/adattato/collegato/non risolto. Non promettere serializzazione universale.
**Verifica:** package isolato e app completa, con dipendenze mancanti e provider Python.

## F-M13 — La provenienza non è sempre ricostruibile dal modello finale

**Evidenza:** INF, S02 ordine di composizione e personalizzazioni.
Il valore finale di un attributo non identifica necessariamente chi lo ha sovrascritto.
**Conseguenza:** catturare contributi e override durante la composizione quando
possibile; distinguere provenienza certa da sconosciuta.
**Verifica:** due package e un'applicazione che modificano la stessa proprietà.

## F-M14 — Nomi logici, schema fisico e prefisso sono separati

**Evidenza:** COD, S02 `gnrsqlmodel/obj.py:tableSqlName` e `table.py`.
sqlprefix True usa il package, False nessun prefisso, stringa prefisso custom;
sqlname esplicito prevale. sqlschema è indipendente. S08 richiede anche prefisso
derivato dallo schema logico.
**Conseguenza:** una mappa risolta unica per compiler, DML, FK, import e migrazione.
**Verifica:** NM01–NM06; underscore non bastano a inferire la separazione dei nomi.

## F-M15 — La subtable di tabella è un sottoinsieme nominato

**Evidenza:** COD, S02 `model.py:_subtable_table`: condizione, condition_*,
metadati e formula booleana subtable_<nome>.
**Conseguenza:** non ridurla a view SQL né perdere la colonna virtuale associata.
**Verifica:** condizioni parametrizzate, default, contesto, negazione e composizione.

## F-M16 — La subtable di package è una specializzazione distinta

**Evidenza:** COD, S02 `_subtable_package`: maintable, sql_inherited,
__subtable, _main e default_subtable; esclusione degli attributi partition_* dalla copia.
`table.py:_refsqltable` rimanda alla maintable per la mappatura fisica.
**Conseguenza:** non inventare una nuova tabella fisica o INHERITS PostgreSQL.
**Verifica:** lettura e scrittura con discriminatore e hook effettivi; non basta SELECT.

## F-M17 — Partition legacy è uno scope logico con particolarità importanti

**Evidenza:** COD, S02 `gnrsqltable/columns.py:getPartitionCondition`.
Current truthy precede allowed truthy; allowed ammette anche campo NULL;
fallback verso __allowed_partition, altrimenti può mancare la condizione.
partitionParameters sceglie la prima dichiarazione partition_*.
**Conseguenza:** non attribuire a liste vuote, current falsy o più dimensioni
garanzie non presenti; non considerarlo automaticamente un controllo autorizzativo completo.
**Verifica:** SP04–SP07 con contesti e NULL espliciti.

## F-M18 — Scope, tenant, store e partizioni fisiche hanno effetti diversi

**Evidenza:** COD/INF, S02 selezione schema tenant, store e filtri; S09 partizionamento.
Uno modifica il predicato, un altro il nome schema, un altro la connessione,
il partizionamento fisico richiede oggetti e DDL propri.
**Conseguenza:** descrittori distinti e bypass circoscritti; subtable='*' non deve
disabilitare altri filtri per associazione implicita.
**Verifica:** SP03/SP09 e combinazioni di tutti i contesti, incluse scritture.

## F-M19 — VirtualRelation è un requisito nuovo con scope dichiarati

**Evidenza:** DIS, S06/S08: relation= oppure table=; condition nel target;
var_* come espressioni sorgente; composizione, ordine/limite, sola lettura.
**Conseguenza:** un oggetto semantico di primo livello, riusabile da compiler e UI,
senza FK automatica e senza salvataggio attraverso record-cluster.
**Verifica:** VR01–VR08; le decisioni GEP ancora aperte restano tali.

## F-M20 — Cardinalità dichiarata e unicità provata non coincidono

**Evidenza:** COD/DIS, S02 one_one modifica tracciamento; S06 distingue garanzie
reali e limit=1. Un'etichetta one_one non crea un vincolo nel database.
**Conseguenza:** conservare evidenza della cardinalità; richiedere ordine totale
per scegliere l'ultimo/primo record. Non ottimizzare assumendo unicità non provata.
**Verifica:** dati che violano la cardinalità dichiarata e parità nelle date di ordinamento.
