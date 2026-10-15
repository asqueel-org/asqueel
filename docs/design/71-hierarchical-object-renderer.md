# 71 — Renderer gerarchico alternativo

14 ottobre 2026. Implementato il percorso strutturale autorizzato nel
[piano 70](70-hierarchical-object-renderer-plan.md). Il renderer corrente
rimane il default; il compilatore non è stato modificato da questo incremento.

## Uso e risultato

```python
from examples.test_invoice_pg import source

recipe = source()
model = recipe.render(mode='objects_tree')

customer = model.package('invc').table('customer')
assert customer is model.obj['invc.tables.customer']
assert customer.column('id') is model.column('invc.customer.id')
assert customer.column('id').parent.parent is customer
assert customer.column('id').root is model.obj
assert customer.db.model is model

# Un'unica Bag globale, completata dopo la costruzione di tutti i package.
joiner = model.relations.get_node('invc.invoice.@customer_id').attr
assert joiner['mode'] == 'O'
assert joiner['one_relation'] == 'invc.customer.id'

# Vista lazy della tabella, ricavata dal ramo globale.
invoice = model.table('invc.invoice')
assert invoice.column('@customer_id.id') is customer.column('id')

# Il vecchio prodotto resta disponibile sulla stessa ricetta.
old_database = recipe.render()
old_database.close()
```

`model.obj` è la radice dei package, come nel legacy: non un registro di
nomi che puntano a un secondo modello. Package → tables → table → columns /
virtual_columns / indexes sono oggetti con genitore, radice e identità stabile.
Nel render offline la struttura `db` dichiarata, con attributi e options,
è accessibile come `model.db`. Il successivo [raccordo 74](74-hierarchical-table-binding.md)
crea anche le SqlTable in `.dbtable`, senza connessioni o RuntimeModel.
Quando il modello viene collegato a SqlDatabase, `model.db` indica il database
operativo; la dichiarazione rimane conservata internamente in `model._database`.
Il modello restituito non può essere passato al compilatore attuale.

La grammatica nativa conserva i contenitori già decisi: `composites` rimane
separato dalle virtual_columns; subtable e virtualRelation restano dichiarazioni
figlie della tabella. Non è un porting di tutti i rami e comportamenti Genropy:
table_aliases, system_records, diagnostica e gli altri rinvii non rientrano.
Gli schemi SQL dei package continuano a provenire da sqlschema; nessun nuovo
schema intermedio diventa genitore del package. È conservato anche il supporto
alla grammatica `schemas` già esistente.

## Decisione sul collegamento alla tabella operativa — 14 ottobre 2026

Confermato lo schema logico legacy: oggetto strutturale DbTableObj e tabella
operativa SqlTable distinti, con accesso alla struttura tramite `.model`.
La composizione dei mixin resta da decidere; non vengono introdotti namespace
logic/triggers né un meccanismo basato su `__init_subclass__`.

Implementato su SqlTable il fallback concordato `__getattr__`: se un membro
non viene trovato sulla tabella operativa, viene cercato su `.model`.
Attributi e metodi operativi hanno precedenza. I metodi ottenuti dal modello
restano legati al modello; quelli operativi mantengono self sulla tabella.
Un nome assente anche nel modello solleva AttributeError. Le assegnazioni
restano sulla tabella, senza inoltro al modello. Il riferimento a `.model`
viene letto senza riattivare il fallback, evitando ricorsione durante una
costruzione ancora incompleta.

Questo è il meccanismo di accesso approvato ora: nel legacy diversi accessi
erano esposti con proprietà e deleghe esplicite, come documentato
nell'[inventario 72](72-table-namespace-inventory.md).
Il fallback non interpreta le chiavi di `model.attributes` come attributi Python.

Il percorso operativo predefinito continua a utilizzare il precedente modello
Table/ResolvedModel. L'incremento del solo fallback non lo sostituiva con objects_tree:
il collegamento operativo al nuovo albero e l'adattamento del compilatore
restano da realizzare. I test verificano il database attuale e, separatamente,
il solo lookup sul nuovo albero, senza dichiarare completato quel raccordo.
Il collegamento successivo effettivo è descritto nel rapporto 74.

Verifica dell'incremento: sette test dedicati in
`tests/application_config/test_table_model_fallback.py`; **693 test superati**
complessivamente nelle suite application_config, object_tree, native_compiler,
sqlite e nelle integrazioni write_lifecycle e formula_subqueries, incluse le
prove PostgreSQL locali. Ruff e mypy sul codice interessato superati.

## Costruzione

1. Copia posseduta della ricetta e risoluzione degli attributi con gli strumenti
   esistenti di Builders. Le connessioni amministrative vengono escluse dalla
   copia visitata, prima che la walk possa valutarne i resolver.
2. Riutilizzo di prepare_source: tipi custom, options locali, gerarchie,
   contributi fra tabelle e riferimenti. Le options strutturali aggiungono
   colonne; le dichiarazioni restano presenti sui rispettivi proprietari.
3. RendererBase.render e render_children, **entrambi ereditati senza override**,
   raccolgono frammenti interni con tag, attributi, figli e nodo source.
   Nessun oggetto del modello viene inizializzato durante questa visita.
4. finalize costruisce il genitore, inizializza, costruisce i figli e completa
   il genitore; un figlio è registrato nel genitore dopo la propria costruzione,
   seguendo GnrStructObj. Le colonne indicizzate producono nodi index.
5. Dopo tutti i package, registrazione delle relazioni globali nei due versi.
   La navigazione di ciascuna tabella viene caricata da RelationTreeResolver.

finalize non dipende dallo stato dell'istanza usata durante preprocess:
Builders usa istanze distinte per materialize e finalize. Anche la coppia
`materialize(mode='objects_tree')` + `get_renderer(...).finalize(...)` è verificata.
I due modi di rendering conservano prodotti indipendenti e non modificano la
source originale. Nessuna conversione preventiva in ResolvedModel.

Nel riuso dell'espansione è stato corretto un accesso a `.value` quando una
tabella è ancora priva di figli. La correzione è limitata al caso vuoto e non
introduce espansioni nuove.

## Relazioni: riferimento e confronto eseguibile

Riferimento: `fa35e5adfa6ad1b269f3a22a9b12c4c1ee6513ea`:

- `gnr/core/gnrstructures.py`: costruzione parent/children e lookup;
- `gnr/sql/gnrsqlmodel/table.py`: completamento dei contenitori e degli indici;
- `gnr/sql/gnrsqlmodel/columns.py`: relazioni su colonne fisiche e virtuali;
- `gnr/sql/gnrsqlmodel/model.py`: addRelation e checkRelationIndex;
- `gnr/sql/gnrsqlmodel/resolvers.py`: RelationTreeResolver._fields.

Il [probe](probes/object_tree_legacy.py) esegue il builder originale sulla source
legacy congelata, con esecuzione SQL e connessioni bloccate. Produce
[148 nodi e 75 viste](evidence/object-tree/legacy.json), includendo il package sys
originale. La fixture legacy è solo un oracolo dei test: il nuovo renderer
costruisce il modello esclusivamente dai 74 modelli nativi.

**I 144 nodi delle relazioni ordinarie coincidono esattamente negli attributi**,
senza eliminare chiavi diverse per far passare il confronto. Compresi O/M,
one_relation/many_relation, nomi, azioni, gruppi, private_relation e virtual.
Le firme native che materializzano False per one_one/deferred omessi vengono
tradotte in assenza dell'attributo legacy; False esplicitamente dichiarato resta.
Il default onUpdate_sql=cascade è conservato anche sulle relazioni logiche,
come nella firma legacy, senza produrre DDL o eseguire azioni.

Le quattro voci escluse dal confronto sono i due versi delle vecchie
`invoice.discount_tier_id` e `invoice_row.customer_id`: la source nativa le ha
già sostituite con le due dichiarazioni GEP. Le dichiarazioni sono conservate;
non sono reinterpretate come joinColumn e non generano inverse automatiche.
Il significato SQL delle virtualRelation resta al compilatore futuro.

Le viste per tabella conservano gli stessi campi e le stesse relazioni del
legacy nel perimetro ammesso. L'ordine segue la source nativa: campo fisico,
eventuale collegamento, collegamenti virtuali, inverse. Non si impone l'ordine
delle dichiarazioni di un file legacy diverso. Il test su un modello piccolo
controlla anche questa sequenza. Il caricamento ricorsivo resta lazy; sono
verificati autoriferimenti, cicli, due percorsi allo stesso target, parentpath,
prefix e identità del campo raggiunto. Le chiavi composite mantengono il nome
della dichiarazione e i rispettivi campi fisici.

Le collisioni interrompono la costruzione: sono già rifiutate dalla validazione
nativa e dal legacy in modalità debug. Non viene importato il catch/log/continue
della modalità non-debug legacy. Gli indici rispettano l'esclusione nativa
`indexed=False` già disponibile. Non vengono creati indici su formule SQL.

## Verifiche e lavoro successivo

161 test dedicati superati: 74 confronti di struttura, 74 confronti delle viste
relazionali, confronto globale e prove di lifecycle, isolamento, options,
resolver, alias, chiavi composite, grammatiche montate e collisioni.
Totali nativi: **74 tabelle, 789 colonne fisiche, 526 virtuali**.

Suite completa: **2135 superati, 13 saltati**. Ruff, mypy (55 file) e Sphinx
strict superati. Il primo tentativo Sphinx era bloccato esclusivamente dal DNS
del sandbox per l'inventario Python; rieseguito con accesso di rete, senza
cambiare documentazione o disabilitare controlli. I dossier interni design non
sono inclusi nella pubblicazione Sphinx, come da configurazione esistente.
[Comandi e risultati](evidence/object-tree/verification.json).

Il compilatore, il renderer `objects` e il JSON migration corrente restano sul
percorso precedente. La fase 5 del piano — esportatore fisico dal nuovo albero
e confronto del suo JSON — è stata successivamente completata e verificata nel
[rapporto 75](75-hierarchical-migration-json.md); le prove strutturali qui descritte
restano distinte dalla verifica migration.
Il raccordo del compilatore e dei metodi operativi richiede una fase distinta.
