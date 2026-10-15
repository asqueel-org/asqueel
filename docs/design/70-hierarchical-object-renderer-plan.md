# 70 — Piano del renderer gerarchico alternativo

Stato al 14 ottobre 2026: implementazione strutturale alternativa autorizzata
ed eseguita; verifiche e limiti nel [rapporto 71](71-hierarchical-object-renderer.md).
Disponibile con `recipe.render(mode='objects_tree')`, senza cambiare il default.
Fasi 1–4 coperte nel perimetro strutturale descritto nel rapporto; fase 5 (nuovo
JSON migration) completata e verificata nel [rapporto 75](75-hierarchical-migration-json.md).
Il raccordo del compilatore resta aperto. Il primo collegamento
operativo DbTableObj ↔ SqlTable ↔ SqlDatabase è implementato nel
[rapporto 74](74-hierarchical-table-binding.md), senza abilitare query SQL o scritture.

## Direzione richiesta e vincoli

Costruire un renderer oggetti alternativo usando la walk generica di
`genro_builders.renderer.RendererBase`. Gli oggetti devono conservare la
gerarchia del modello legacy, i legami verso genitore/package/database e
l'identità degli oggetti raggiunti attraverso percorsi diversi.

Il modello delle relazioni deve comprendere il ramo globale e la navigazione
per tabella usata dal compilatore legacy. Una raccolta locale di archi per
ciascuna tabella non sostituisce quel contratto.

Il renderer corrente rimane disponibile durante la costruzione e il confronto.
Non cambiare il default, non sostituire gli oggetti correnti e non eliminare
codice/test prima della revisione e dell'accordo dell'utente. Nessun nuovo
provider, grammatica, contenitore generico o protocollo pubblico. Utilizzare
Bag, resolver e strumenti di Builders già esistenti.

## Differenze accertate, non ipotesi

Riferimento legacy: `fa35e5adfa6ad1b269f3a22a9b12c4c1ee6513ea`, snapshot del
censimento 59. I riferimenti sotto sono relativi a quel sorgente.

| Aspetto | Legacy | Asqueel attuale |
| --- | --- | --- |
| Costruzione | DbModelObj/GnrStructObj materializzano nodi tipizzati con parent/root/children | SqlObjectRenderer.render_children ignora la visita dei nodi e chiama resolve_model sull'intero documento |
| Package e tabelle | DbPackageObj contiene gli oggetti tabella; DbTableObj conosce pkg/db e conserva dbtable | Package contiene nomi di tabelle; ResolvedModel e SqlDatabase hanno registri distinti di tabelle |
| Colonne | Figli tipizzati della tabella, fisiche e virtuali in contenitori distinti | Descrittori Column e separati SqlColumn; raccolta unificata |
| Relazioni globali | DbModel.relations è una Bag indicizzata per package/tabella/relazione, completata da addRelation dopo la costruzione dell'albero | Nessun ramo equivalente; Table.relations contiene descrittori Relation locali |
| Navigazione relazionale | RelationTreeResolver costruisce una vista Bag con campi e resolver per le relazioni, attributi joiner e contesto della tabella | _Context.related percorre direttamente Table.relations e consulta self.model.table(target) |
| Compilazione dei JOIN | getFieldAlias → _findRelationAlias → _getRelationAlias legge il relation tree e joiner | _Context.related costruisce uguaglianze sulle coppie di chiavi e oggetti Join del QueryPlan; cache per alias/nome |

Il compilatore attuale usa dunque un percorso architetturale diverso. Le
regressioni SQL e le singole regole portate non dimostrano equivalenza della
struttura o fedeltà dell'algoritmo di navigazione. La separazione tra DbTableObj
e SqlTable, invece, esiste già nel legacy: non è di per sé la divergenza.

Fonti legacy: `gnrsqlmodel/model.py:166–179` e `:182` (addRelation),
`gnrsqlmodel/obj.py:148` (DbPackageObj), `gnrsqlmodel/table.py:105`,
`gnrsqlmodel/resolvers.py:38`, `gnrsqldata/compiler.py:229`, `:273`, `:455`, `:507`.
Fonti attuali: `src/asqueel/object_renderer.py`, `contracts.py`,
`model_sections.py`, `application.py`, `application_table.py`, `compiler.py`.

## Struttura di riferimento

Schema concettuale legacy, omettendo solo i contenitori intermedi:

```text
database
└── model
    ├── source
    ├── obj
    │   └── package
    │       └── table
    │           ├── columns
    │           ├── virtual_columns
    │           ├── indexes e altri nodi già ammessi
    │           └── dbtable → tabella operativa
    └── relations
        └── package
            └── table
                └── relazione con attributi one/many
```

La vista `table.relations` viene costruita dal resolver usando gli oggetti e
il ramo globale. Contiene campi e navigazione, non soltanto un elenco di FK.
Il ramo non va espanso ricorsivamente all'infinito: autoriferimenti e cicli
sono gestiti con la risoluzione lazy del legacy.

Gli schemi SQL continuano a essere dedotti dai package secondo la decisione
già acquisita. Non introdurre schema come genitore del package. Rispettare le
options già ammesse su db/package/tabella e la loro collocazione nella source.

## Fase 1 — Contratti degli oggetti e ordine di costruzione

Prima di scrivere il nuovo renderer:

- censire classi, contenitori, lookup, parent/root/pkg/db, identità e legami
  DbTableObj ↔ SqlTable nel legacy;
- elencare ciò che è già dichiarabile nella grammatica attuale e le esclusioni
  concordate, senza reintrodurre tutto Genropy;
- fissare prove strutturali indipendenti dai descrittori di ResolvedModel:
  navigazione package → tabella → colonna, risalita, stessa istanza raggiunta
  da lookup diversi, fisiche/virtuali, metadati e options conservate;
- confrontare ordine di inizializzazione e callback, indicando i requisiti
  realmente necessari alla grammatica corrente.

**Correzione dopo la rilettura della walk e degli esempi:** l'ordine della
visita non impone l'ordine di costruzione degli oggetti definitivi.
RendererBase raccoglie i risultati di rendered_item; il renderer decide cosa
rappresentano e come comporre la lista finale. I frammenti possono conservare
figli, tag e attributi risolti senza inizializzare ancora gli oggetti SQL.

Il renderer alternativo può quindi usare la walk generica per produrre la
struttura intermedia e poi costruire da quel risultato l'albero degli oggetti
nell'ordine legacy: genitore e inizializzazione, figli, completamento dopo i
figli. Questa elaborazione del risultato appartiene al renderer; non è una
walk sostitutiva della source. Non richiede, sulla base del problema esaminato,
un nuovo hook di Builders né una modifica di RendererBase. L'equivalenza del
lifecycle resta un requisito da verificare, non un impedimento della walk.

Esempi letti:

- `genro_builders/renderer/yaml.py`: rendered_item restituisce frammenti
  strutturati; finalize compone il documento dalla lista.
- `genro_builders/contrib/css/css_renderer.py`: rendered_item conserva
  frammenti con struttura; finalize/_emit_sequence li percorre per produrre
  il risultato, mantenendo render/render_children generici.
- `genro_textual/textual_renderer.py`: renderer a oggetti; rendered_item
  costruisce widget dai figli e finalize gestisce la lista dei widget radice.
  Mostra un'altra composizione possibile, non un ordine obbligatorio per SQL.
- `genro-builders/roadmap/render-architecture.md`, sezioni 1–3: separazione
  tra visita, risultato del singolo nodo e composizione finale. Le sezioni
  storiche sul rendering parziale non sono usate come contratto corrente.

**Uscita:** tabella dei contratti e prove sull'ordine legacy, da realizzare
nella composizione del risultato senza sostituire la walk base.

## Fase 2 — Renderer alternativo sulla walk generica

- Usare preprocess, rendered_item e finalize nei ruoli previsti dal renderer
  base; lasciare render/render_children alla visita generica.
- In rendered_item conservare la struttura dei frammenti, con tag, attributi
  già risolti e figli; nessuna inizializzazione anticipata degli oggetti SQL.
  È un risultato interno del renderer, non un nuovo modello pubblico,
  una nuova grammatica o una conversione in ResolvedModel.
- In finalize comporre dalla lista risultante l'albero di oggetti,
  rispettando l'ordine legacy fissato nella fase 1. Il dispatch per tag
  appartiene al renderer; nessun framework di provider.
- Collegare i nodi, la radice e il database rispettando il contratto della
  fase 1; mantenere gli stessi oggetti nei lookup e nei riferimenti.
- Non produrre prima ResolvedModel per poi ricostruire un albero apparente.
  L'input della costruzione alternativa è la source.
- Tenere distinte la dichiarazione originale e le copie di lavoro; resolver
  sugli attributi tramite il comportamento esistente di Builders, attributi
  piatti e namespace con extract_kwargs. Nessuna risoluzione ricorsiva inventata.
- Rendere selezionabili entrambe le costruzioni senza cambiare il default.
  Il modo alternativo è `objects_tree`; `objects` resta il default.

**Verifica:** piccoli modelli, grammatiche montate, identità e risalita,
traccia verificabile dell’ordine di inizializzazione e completamento,
nessun I/O, nessuna mutazione della source, due render indipendenti. Verificare
anche le cache di renderer/materializzazione di Builders: i due prodotti non
devono sovrascriversi o condividere oggetti mutabili.

## Fase 3 — Options e modello completo

- Riesaminare preparazione, tipi custom ed espansioni già implementate contro
  l'ordine legacy. Non assumere corrette le funzioni esistenti solo perché
  producono gli stessi campi in alcuni test.
- Espandere le options strutturali sulla copia di lavoro nel punto definito
  dal lifecycle, prima della chiusura delle relazioni che ne dipendono.
- Conservare le altre options e dichiarazioni sugli oggetti proprietari.
- Non generare nuovi nomi, resolver, valori di ambiente o comportamenti runtime.

**Verifica:** tutti i 74 modelli nativi, colonne aggiunte dalle options,
attributi e tipi, inventario delle dichiarazioni conservate. Differenze da
legacy e vecchio renderer classificate, non normalizzate per nasconderle.

## Fase 4 — Ramo globale relations e RelationTreeResolver

- Dopo la costruzione degli oggetti registrare le relazioni, seguendo
  DbModel.addRelation: chiavi dei due lati, mode O/M, one_relation,
  many_relation, nomi e attributi pertinenti al perimetro concordato.
- Riprodurre controlli e segnalazioni del legacy, incluse collisioni e target;
  ogni divergenza necessaria va presentata prima di implementarla.
- Portare la vista di navigazione RelationTreeResolver con gli strumenti
  resolver già disponibili: campi, nodi di relazione, joiner, contesto
  package/tabella, caricamento lazy e collegamento alla radice.
- Verificare relazioni incrociate fra package, due collegamenti alla stessa
  tabella, autoriferimenti, cicli, chiavi composte già ammesse e inverse ordinarie.
- Separare le virtualRelation della GEP dalle inverse ordinarie: restano
  escluse inverse automatiche, limit/order_by/one_one sulle virtuali.

**Verifica:** snapshot strutturali del ramo globale e della vista navigabile
confrontati con il legacy; identità degli oggetti, attributi joiner e navigazione
su più livelli. Un risultato SQL uguale non sostituisce queste prove.

## Fase 5 — Due prodotti confrontabili e JSON migration

**Completata il 14 ottobre 2026:** uguaglianza integrale sui 74 modelli,
applicazione/introspezione/seconda diff vuota PostgreSQL e prova di evoluzione.
Dettagli nel rapporto 75. Vecchio renderer e oracoli conservati.

- Costruire vecchio e nuovo prodotto dalla medesima source nativa.
- Eseguire i confronti sui 74 modelli senza usare la source legacy già espansa.
- Dal nuovo albero produrre la proiezione fisica per migration e confrontare
  il JSON con quello verificato, distinguendo differenze d'ordine irrilevanti
  da differenze di semantica.
- Qualsiasi adattamento necessario all'esportatore è esplicito e verificato;
  la sua rappresentazione intermedia non diventa il modello del compilatore.

**Uscita:** renderer alternativo completo nel perimetro concordato, ramo
relations utilizzabile, elenco delle differenze e JSON verificato. Vecchio
renderer ancora disponibile; nessun cambio del default.

## Fase successiva — Compilatore sul nuovo albero, da rivedere separatamente

Il piano dettagliato di questa fase è ora il
[piano 76](76-hierarchical-compiler-plan.md), redatto dopo il completamento
del JSON migration. È pianificazione, non un raccordo già implementato.

La disponibilità dei due renderer non rende automaticamente il compilatore
corrente aderente al legacy. Preparare il raccordo prendendo come riferimento
getFieldAlias, _findRelationAlias e _getRelationAlias e il loro accesso alla
vista relazionale. Le decisioni dei branch sperimentali sono materiale di
confronto, non autorizzazioni a cambiare comportamento.

Per ogni parte attuale classificare l'esito: riuso verificato, adattamento o
sostituzione. In particolare: risoluzione campi/alias/formule, lookup dei metodi,
contesto delle sottoquery, JOIN, identità dei percorsi, mangler, dialetti e
metadati di risultato. Il compiler alternativo deve consumare il nuovo albero
relazionale; convertire tutto nel vecchio Table.relations e richiamare related
non soddisfa l'obiettivo.

Il riuso di tokenizer, formattatori di parametri, driver o singoli algoritmi
rimane un'ipotesi da verificare con i contratti, non una conclusione anticipata.
Non aggiungere ora RuntimeModel: verificare il suo riferimento legacy e non
imporre un'architettura che lo renda impossibile. Catene/operatori, pyColumn,
#PREF, system_records e gli altri rinvii restano tali.

Il passaggio definitivo al nuovo percorso e l'eventuale eliminazione del
precedente richiedono revisione dei risultati e accordo dell'utente.
