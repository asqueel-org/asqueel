# 47 — JSON completo di test_invoice_pg e verifica migrations

**Aggiornamento successivo:** il producer scripts/export_invoice_migration.py ora
usa la source nativa e scrive in artifacts/test_invoice_pg/native. Questo
rapporto resta la verifica storica del bridge; il percorso nativo è verificato
nel [rapporto 53](53-native-invoice-render-and-migration.md).

**Aggiornamento del 13 ottobre:** questo report attesta il percorso dal legacy
già espanso. Le successive decisioni grammaticali prevalgono sui riferimenti
storici a normalize/provider e altre proposte. La
[fase 0 del render nativo](52-invoice-render-coverage.md) verifica la copertura
e registra gli scarti da decidere prima di attestare parità nativa.

12 ottobre 2026. **P1 chiusa nel commit `d88c822`; traguardo richiesto
“produrre e verificare il JSON di tutti i package” raggiunto.**
Questo incremento non chiude automaticamente P2–P5, né annuncia la release 0.6.0.
Il gate fisico di P6 è verificato sul profilo legacy espanso qui descritto;
la configurazione interamente nativa della specifica 42 resta da completare.

## Risultato concreto

[JSON per asqueel-migration](../../artifacts/test_invoice_pg/migration.json),
formato `structure-1.0`, accettato da `StructureValidator` e dal migratore.

| Package / schema fisico | Tabelle | Colonne fisiche | FK | Indici | UNIQUE composite |
| --- | ---: | ---: | ---: | ---: | ---: |
| sys | 17 | 195 | 7 | 56 | 0 |
| adm | 40 | 412 | 32 | 150 | 0 |
| invc | 18 | 189 | 19 | 76 | 1 |
| Totale | **75** | **796** | **58** | **282** | **1** |

SHA-256 di `migration.json`:
`bf8820723ca5a4de9938bcf6e10a725ed8629a9719158808f14b90f537c3bf82`.

Il confronto strutturale con l'oracolo indipendente
`tests/oracles/test_invoice_pg/physical.json` è esatto, senza rimuovere campi,
rinominare hash o filtrare differenze. L'artefatto è anche confrontato nei test
con una nuova produzione, per rilevarne l'obsolescenza.

## Percorso di produzione e confine del bridge

1. La source XML espansa, catturata in P0 costruendo realmente i tre package
   legacy offline, entra in `from_expanded_legacy_xml`.
2. Il bridge opzionale costruisce una source Asqueel con schemi e package
   distinti, colonne, composite, relazioni, virtuali e metadati.
3. `resolve_model` produce gli oggetti indipendenti dalla source; la proiezione
   fisica passa al renderer esistente e alle factory di `asqueel-migration`.
4. Il JSON fisico legacy è letto **solo dai test**, mai dal producer.
   Anche `model.json` dell'oracolo non è un ingresso del producer.

Il bridge non importa GenroPy, non apre connessioni e non esegue provider.
Le espansioni legacy devono essere già presenti nella source. I tipi `money`
e `perc`, assenti nell'XML, sono dichiarati esplicitamente nel profilo
`adapter-profile.json`, trascrivendo `custom_type_money` e `custom_type_perc`
da `projects/test_invoice/packages/invc/main.py` censito nel manifest P0.

Il profilo conserva il contratto fisico dell'`OrmExtractor` legacy:
`CHAR(22)` per le chiavi di lunghezza fissa, `:n` normalizzato a `0:n`,
X/Z/P come storage testo, indici sulle relazioni deboli e deferrability
implicita legacy per `setnull`. Non converte default applicativi in default SQL.
L'indice di tabella `sys.locked_record.locked_record_lock_table_lock_pkey_key`
è una dichiarazione che quell'estrattore non proietta: resta esplicitamente
nei metadati legacy del modello. Gli indici della nuova grammatica nativa
vengono invece proiettati normalmente. Questa differenza di profilo non va
confusa con la possibilità di ignorare un indice nativo.

Il modello conserva i **534 elementi virtuali legacy**: 532 colonne virtuali
e 2 composite, oltre a 4 subtables, una relazione condizionale e un alias di
relazione. I riferimenti ai metodi e i dettagli applicativi legacy rimangono
simbolici/metadati. Il compilatore rifiuta questo profilo espanso finché non
sono disponibili i provider runtime; esportare DDL non abilita quei comportamenti.

## Incrementi nativi implementati

- Oggetti Schema, Package, Option e Declaration; sezioni vuote conservate;
  mapping logico/fisico, collisioni, dipendenze di package mancanti.
- Attributi profondamente immutabili, con liste ancora compatibili con
  uguaglianza e binding dei driver. Source del chiamante non modificata.
- Codec separato `model_to_json` / `model_from_json`, formato `asqueel.model`
  versione 1, con record ammessi espliciti e senza import dinamici. Nessuna
  configurazione di connessione nel modello esportato. Il codec non costituisce
  un confine di autorizzazione per modelli ricevuti da client non fidati.
- Espansione deterministica di `sys_fields`, dichiarazione del generatore
  `legacy22` senza generare valori, alias di tipo locali al package.
- Inferenza di tipo e size per FK dichiarate senza tipo; PK composite,
  UNIQUE composite, azioni applicative separate da quelle SQL, relazioni
  deboli e inverse. `one_one` non crea una UNIQUE.
- Indici con nome automatico nei package; errore esplicito se un indice parziale
  o di metodo diverso non copre quello completo richiesto: il formato attuale
  del migratore identifica un indice attraverso il solo insieme ordinato di colonne.
- Validation esplicita/embedded con messaggi, normalizzazione separata,
  verifiche locali deterministiche e distinzione di nodup/exists server.
- Descrittori di calcolo Python, subquery, bag item, subtables e virtual relations;
  risoluzione di alias, target e cicli delle relazioni virtuali. Le compilazioni
  ancora mancanti producono un errore, non una falsa colonna SQL.
- Le scritture con nuovi comportamenti dichiarati e non ancora eseguibili
  si fermano prima di hook/I/O. La source storica continua a passare la regressione.

## Verifiche PostgreSQL

`tests/test_release_invoice_migration.py` usa il fixture `pg_database`, che
crea e distrugge un database `test_asqueel_*`. Non modifica `test_invoice_pg`.

La prova verifica: applicazione dei 75 modelli; introspezione di 75 tabelle e
796 colonne; seconda diff vuota e nessun warning; reader → emitter Python →
builder → JSON ancora senza differenze; ampliamento di una colonna, aggiunta
di UNIQUE, FK e indice, nuova applicazione e nuova diff vuota. Una view,
una funzione e un trigger SQL non gestiti restano presenti dopo l'evoluzione.

Le altre prove confrontano tutto il JSON con l'oracolo indipendente, modificano
la source per dimostrare che il producer non riproduce uno snapshot, verificano
il round-trip del modello completo e i contratti nativi sopra elencati.

Per rigenerare gli artefatti con l'ambiente di sviluppo installato:

```sh
python scripts/export_invoice_migration.py
pytest -q tests/test_release_invoice_migration.py tests/test_release_model_semantics.py
```

Il producer genera anche `artifacts/test_invoice_pg/model.json`: snapshot
semantico di circa 3 MB, ignorato da Git perché rigenerabile. Il JSON fisico
richiesto è invece versionato. PostgreSQL è necessario soltanto per il test
marcato `postgresql`; la produzione e il confronto con l'oracolo sono offline.

## Parti ancora da chiudere per la release

Il piano 44 resta vincolante. Non sono completati il registro versionato delle
estensioni/provider, tutte le espansioni native delle options avanzate, la piena
traduzione dei comportamenti legacy in quelle options e tutti i contratti
P2–P5. L'XML espanso è un ponte verificabile, non la loro implementazione.
Restano inoltre compilazione completa, ricette delle operazioni e ciclo di
scrittura P7–P9, quindi collaudo/distribuzione P10–P12. Il traguardo di questo
incremento è il modello completo esportabile e la prova reale delle migrations.

Verifica finale dell’incremento: **944 test passati, 1 skip** in 31,08 s;
Ruff senza rilievi e Mypy senza errori su 48 file. Comando della suite:

```sh
PYTHONPATH=src:../asqueel-migration/src PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python -m pytest -q -o addopts=''
```

Ambiente: Python 3.12, genro-builders/genro-bag 0.27, asqueel-migration 0.2.1
(checkout `13274dd`). Pytest nell'ambiente di audit è 8.3.5: prima della release
va ripetuta la matrice con la dipendenza dichiarata >=8.4 e le versioni CI.
