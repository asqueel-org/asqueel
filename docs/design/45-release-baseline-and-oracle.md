# 45 — Baseline della release e oracolo completo del modello

12 ottobre 2026. Esecuzione di P0 del piano 44.

## Base effettiva

Il checkout iniziale `92466b9` era precedente alla pubblicazione 0.5.2 e alla
correzione serial4. La prima baseline con PostgreSQL ha prodotto 866 passati,
1 skip e 2 fallimenti dovuti a serial4 nel migratore 0.2.1. Nessuna modifica del
nuovo lavoro era necessaria per correggerli: la correzione era già su main.

Il branch `codex/core-release-0.6` parte quindi da main
`4641a0e9a78a66cf1c52b808bd43fe23885e460c` (versione 0.5.2). Il precedente branch
e i file locali sono stati conservati. La baseline completa aggiornata ha dato
**876 passati, 1 skip**, compresi i cinque nuovi controlli dell'oracolo.
Questo è un risultato dei checkout locali, non una verifica della wheel pubblicata.

Ambiente: Python 3.12, genro-builders/genro-bag 0.27.0, migratore 0.2.1;
checkout migratore `13274dd` usato nel PYTHONPATH. Pytest dell'ambiente di audit
è 8.3.5: utile per questa baseline, da riallineare ai requirements del progetto
prima del gate della distribuzione (che richiede almeno 8.4).

Comando dalla radice core:

```sh
PYTHONPATH=src:../asqueel-migration/src PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 \
  /tmp/asqueel-repo-audit-env/bin/python -m pytest -q -o addopts=''
```

Il primo tentativo confinato nella sandbox non poteva raggiungere PostgreSQL
(`Operation not permitted`); il risultato valido è quello eseguito con accesso
al server locale, utilizzando i database temporanei dei fixture. Nessuna
migration o query è stata eseguita su test_invoice_pg.

## Oracolo indipendente

`scripts/capture_legacy_invoice.py` usa il vero GnrApp e model builder legacy
per caricare sys, adm, invc, le classi ereditate e il contributo adm→sys.task.
Le sole sostituzioni sono ambiente/configurazione sanitizzati, localizzazione
identità e soppressione dello startup applicativo dopo la costruzione del modello.
Non sono sostituiti sysFields, AttachmentTable, loader dei mixin, model builder
o OrmExtractor. Tentativi di SQL/network I/O producono errore, anche se catturati
internamente dal legacy. Non vengono letti i valori di connessione dell'istanza.

Profilo dichiarato: PostgreSQL, use_timezone=True, user_ins=True, user_upd=False,
nessuno schema tenant aggiuntivo. È un profilo riproducibile del modello dei
package; non pretende di ricostruire preferenze e servizi di un'istanza live.
Contributi Python custom/plugin dell'istanza, se presenti, richiedono cattura
esplicita: il generatore li rifiuta invece di ignorarli.

Fixture in `tests/oracles/test_invoice_pg/`:

| Artefatto | Contenuto |
| --- | --- |
| source.xml | Source legacy espansa: comprende colonne/virtuali prodotte da helper e mixin |
| model.json | Albero effettivo degli oggetti legacy, attributi e figli senza riferimenti runtime |
| physical.json | JSON normalizzato prodotto da OrmExtractor legacy, validato dal migratore moderno |
| manifest.json | Profilo, package/dipendenze, hash delle fonti e degli artefatti |

| Package | Tabelle | Colonne fisiche | FK fisiche |
| --- | ---: | ---: | ---: |
| sys | 17 | 195 | 7 |
| adm | 40 | 412 | 32 |
| invc | 18 | 189 | 19 |
| Totale | 75 | 796 | 58 |

Rigenerazione in un secondo processo: tutti e quattro gli artefatti identici
byte per byte. Nessun percorso della macchina o repr di oggetti Python negli
snapshot. Nessun dato applicativo, credenziale o risultato di query.

`tests/test_release_model_oracle.py`: cinque prove su perimetro, validità del
JSON fisico, FK inter-package, espansione allegati/gerarchie/dynamic fields,
validation/cifratura/virtuali/subtable e integrità degli artefatti. Queste prove
certificano le evidenze del legacy, **non** la nuova implementazione.

## Contratti di confine fissati per le prove successive

Le firme tipizzate del documento 42 costituiscono l'input alla grammatica;
le implementazioni successive devono trasformarle in validazione eseguibile.
Le seguenti osservazioni distinguono i contratti dalle assunzioni del vecchio
codice, prima di modificarlo:

| Confine | Risultato richiesto | Fase di verifica del nuovo codice |
| --- | --- | --- |
| Omissione | Non reimposta attributi; UNSET non viene serializzato come dato | P1 |
| None/False/reset | None ammesso solo dai tipi nullable; False disattiva; reset cancella configurazione accumulata | P1 |
| Contributi | Ordine esplicito, provenienza; conflitto nello stesso contributo, override fra contributi | P1 |
| Singleton | options/schemas/packages restituiscono lo stesso contenitore senza duplicarlo | P1 |
| Campi table | name_long/name_short/name_plural/caption_field sempre dichiarabili | P1 |
| Package/schema | Namespace logico distinto, mapping fisico e collisioni verificati | P2/P3 |
| Payload options | Firma per livello, bool distinti da int, dict dei sys fields a chiavi chiuse | P1/P5 |
| Connessione | Resolver amministrativi separati; costruzione del modello non li valuta | P1/P2 |
| PK | UUID esatto legacy, ID esplicito preservato; niente generazione nel render/compile | P5/P9 |
| RAW | Bypass applicativo esplicito, nessuna generazione UUID o hook impliciti | P9 |
| one_one | Asserzione, non UNIQUE implicito né scelta arbitraria del primo record | P3/P7 |
| Filtri | Nuovi default e profilo legacy distinti; non derivarli solo dal nome dei campi | P5/P9 |
| Source/modello/DDL | Formati distinti; oggetti completi anche quando non proiettano DDL | P2/P6 |
| Binding remoti | Tipi preservati; niente SQL, import, identità o autorizzazioni client autoattribuite | P8 |
| Provider | Registro/firma/versione, errore se manca una capability richiesta | P2/P5/P9 |

P0 non prova esecuzione di validation client, ricette o lifecycle nuovo. Il
confronto indipendente ora è disponibile per tutte le tabelle; l'implementazione
inizia con i contratti source di P1. Il target resta 0.6.0; nessun bump o tag è
stato creato per questa baseline.
