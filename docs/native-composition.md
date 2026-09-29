# Composizione Builders: decisione V1 e prove sui consumer

**Decisione proposta per V1: mantenere il dialetto SQL unico, composto dai mixin
esistenti, e comporre le ricette tramite contributi espliciti.** I montaggi
annidati Builders funzionano nell'esperimento, ma richiedono lavoro sui consumer
prima di diventare un contratto pubblico SQL. Non è necessario introdurre una
grammatica diversa per ogni tabella per ottenere modelli modulari.

## Perimetro della prova

`tests/native_composition/test_composition.py` contiene sette test. Il prototipo
monta una grammatica a livello schema e una seconda a livello tabella usando
`_meta={'subbuilder': 'x_config:grammar'}`. Le classi di configurazione sono locali
al test: non viene cambiata la grammatica di produzione.

Sono coinvolti i consumer reali: `SqlModelCatalog`, `SqlModelValidator`,
`SqlPythonEmitter`, `SqlMigrationRenderer`, `resolve_model` e, per la composizione
di ricette, `to_physical_builder`. Non si eseguono DDL su un database: il round-trip
qui verificato è ricetta Python → modello → struttura normalizzata, distinto
dai test PostgreSQL delle migrazioni.

## Montaggi annidati: risultati e limiti osservati

| Aspetto | Esito verificato |
|---|---|
| Indirizzamento | Il percorso `db.schemas.sales.tables.customer.columns.id` resta valido. Non è corretto motivare l'esclusione dei mount dicendo che perdono necessariamente i nomi. |
| Catalogo | Le colonne vengono raccolte, il back-reference agli antenati funziona e `projects_column` viene conservato. |
| Validazione standard | Il modello montato con attributi SQL standard supera la validazione. |
| Proiezione migration | PK e colonne vengono proiettate nella struttura normalizzata. |
| Modello nativo/UI | `resolve_model` conserva i metadati `x_ui` della colonna montata. |
| Emitter dinamico | Il prototipo conserva una classe Python in `x_config`. L'emitter ne produce il repr `<class '...'>`, che non è Python compilabile. Il test caratterizza il limite con `SyntaxError`; non dichiara riuscito quel round-trip. |
| Firme locali | Un parametro `domain_hint` dichiarato dalla grammatica montata viene accettato da Builders ma respinto dal validatore SQL, che consulta ancora la firma del builder radice. |

Questi ultimi due limiti non dimostrano che ogni montaggio sia incompatibile.
Dimostrano che il montaggio dinamico provato non è già una soluzione completa:
servono una politica serializzabile per la configurazione e consumer che
risolvano la grammatica effettiva del nodo. Non sono stati verificati montaggi
statici via registry, nuove famiglie di elementi o emitter di dialetti eterogenei.

La descrizione storica in `SqlBuilder` secondo cui i montaggi perderebbero
l'indirizzamento nominale va considerata superata da questa prova; il motivo
concreto per mantenere il dialetto unico è l'assenza dei contratti completi sopra,
non una limitazione generale dei percorsi Builders.

## Composizione di ricette: percorso verificato per V1

Due funzioni indipendenti dichiarano clienti e fatture sul medesimo contenitore
`tables`. La seconda dichiara una relazione verso la tabella della prima.
Il livello applicativo sceglie esplicitamente quali contributi invocare.

Il test verifica:

- catalogo completo e validazione delle relazioni fra contributi;
- errore se manca il contributo che definisce la tabella referenziata;
- errore esplicito su una seconda dichiarazione della stessa tabella;
- emissione di Python compilabile e ricostruzione con struttura migration uguale;
- conservazione di `x_sql_schema`, `x_sql_prefix`, `x_sql_name` di tabella e colonna;
- identità stabile `x_identity` e UI inline `x_ui`, con overlay parallelo per identità;
- proiezione fisica coerente: `sales.customer` → `public.sales_customer`,
  override `sales.invoice` → `public.documents`, `label` → `display_name`;
- una modifica esclusivamente UI non modifica la struttura migration fisica.

La ricetta emessa viene appiattita in una classe: preserva dati e semantica del
modello collaudato, non ricostruisce i file sorgenti dei singoli contributi.

## Cosa non viene promesso

Questa composizione non è un merge arbitrario di package. Non implementa una
cascata generale con cancellazioni, override di qualsiasi attributo e provenance
storica completa. Gli overlay UI hanno il contratto già implementato nel modello
nativo; i contributi strutturali duplicati falliscono invece di sovrascriversi.

Per introdurre grammatiche montate in una versione successiva occorre prima
collaudare serializzazione delle configurazioni, risoluzione delle firme per nodo,
consumer/emitter, attributi di proiezione e diagnostiche dei conflitti. Il prototipo
resta materiale di prova e non diventa una nuova API supportata per effetto dei test.

## Riproduzione

```sh
python -m pytest tests/native_composition --confcutdir=tests/native_composition --no-cov
```

Nel runtime predisposto per la V1: **7 test superati**, controllo Ruff riuscito.
Nessuna grammatica di produzione né dipendenza modificata per questa prova.
