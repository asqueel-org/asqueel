# Audit della grammar SQL corrente

## 1. Risultato sintetico

`asqueel` è già predisposto correttamente. Non manca l'idea della grammar:
mancano il completamento del contratto dei parametri, i validatori semantici e
i consumer principali.

La struttura corrente comprende:

- `modern/builder.py`: `SqlBuilder` basato su `BuilderBase`;
- `modern/elements.py`: prima grammar moderna;
- `modern/renderer.py`: segnaposto del renderer DDL;
- `legacy/`: grammar compatibile con la forma storica;
- `roadmap/01`–`04`: inventari del sistema legacy;
- `roadmap/05_grammar_design.md`: disegno della nuova architettura;
- test di vocabolario, contenimento, cardinalità e collection key.

## 2. Vocabolario moderno già dichiarato

```text
db
├── schema
│   ├── table
│   │   ├── column
│   │   ├── aliasColumn
│   │   ├── formulaColumn
│   │   ├── subQueryColumn
│   │   ├── pyColumn
│   │   ├── compositeColumn
│   │   ├── constraint
│   │   ├── index
│   │   └── trigger
│   ├── view
│   ├── function
│   ├── sequence
│   └── dbtype
├── extension
└── eventTrigger
```

Una `relation` è figlia di un elemento della famiglia column ed è ammessa al
massimo una volta per colonna.

## 3. Decisioni architetturali già valide

### 3.1 Source tree unico

Il source tree deve alimentare più consumer, non essere duplicato in un secondo
modello strutturale mantenuto a mano.

### 3.2 Due piani di attributi

**Piano fisico:** informazioni necessarie a creare e confrontare il database,
come dtype, tipo SQL nativo, size, nullability, default, primary key, foreign
key, constraint e index.

**Piano semantico:** caption, gruppi UI, nomi localizzati, validatori,
relazioni navigabili, trigger applicativi, formule e metadati delle estensioni.

Ogni consumer deve dichiarare quale piano legge. Il renderer delle migrazioni
deve ignorare il piano semantico senza cancellarlo dal source tree.

### 3.3 Relazione logica e foreign key non coincidono

Una relazione è navigabile per default; diventa un vincolo fisico soltanto con
`foreign_key=True`. Questo preserva il comportamento storico e impedisce di
creare constraint involontari.

### 3.4 Core portabile ed estensioni di backend

Il vocabolario comune non deve assorbire indiscriminatamente opzioni
PostgreSQL. Elementi e parametri specifici del backend appartengono a mixin
componibili, per esempio `PostgresElements`.

### 3.5 Errori espliciti

Il nuovo modello usa keyword argument, tipi reali e fallimenti espliciti. Non
deve riprodurre coercizioni silenziose e fallback ambigui della legacy.

## 4. Punti forti già presenti

- gerarchia leggibile e compatta, senza container plurali obbligatori nella
  grammar moderna;
- collection key naturali per database, schema, tabelle e oggetti nominati;
- cardinalità della relation già testata;
- famiglie distinte per colonne fisiche e virtuali;
- supporto concettuale per chiavi composte;
- slot già previsti per entità oltre la legacy;
- documentazione architetturale ampia;
- grammar legacy disponibile come riferimento di compatibilità.

## 5. Lacune concrete

### 5.1 Firme moderne non ancora esplicite

I metodi di `modern/elements.py` hanno in gran parte firma `def element(self)` e
descrivono gli attributi soltanto nella docstring. La grammar legacy mostra il
modello desiderato: parametri noti espliciti e tipizzati, docstring esaustiva,
con eventuali metadati aperti conservati separatamente.

Conseguenze attuali:

- contratto incompleto per introspezione, GUI e LLM;
- validazione debole dei parametri;
- default e valori ammessi non formalizzati;
- documentazione automatica meno utile.

### 5.2 Validazione soltanto topologica

I test attuali dimostrano vocabolario e contenimento, ma non ancora invarianti
come:

- pkey riferita a colonne fisiche esistenti;
- numero e ordine delle colonne di una foreign key composta;
- target della relation esistente e compatibile;
- `foreign_key=True` vietato su colonne virtuali;
- colonne di constraint e index esistenti;
- CHECK con clausola e nome coerenti;
- unicità dei back reference;
- dipendenze e ordine di view, function, type e trigger.

### 5.3 Nessuna proiezione verso `asqueel-migration`

Il contratto è progettato ma il renderer manca. Questo impedisce alla nuova
grammar di raggiungere il percorso già funzionante diff → DDL → apply.

### 5.4 Renderer DDL segnaposto

`modern/renderer.py` non implementa ancora CREATE/ALTER. È utile, ma viene dopo
la proiezione verso il migratore: il migratore possiede già writer per più
dialetti e produce modifiche incrementali.

### 5.5 Round-trip assente

Mancano:

- normalized JSON → source tree;
- source tree → Python idiomatico;
- introspezione DB → normalized JSON → Python.

### 5.6 Backend mixin non ancora separato nel codice

La roadmap assegna a mixin backend-specifici extension, event trigger e tipi
PostgreSQL, mentre `modern/elements.py` li contiene ancora direttamente. Prima
di stabilizzare l'API occorre rendere esplicito il confine.

## 6. Divergenze da decidere prima di implementare

### 6.1 Foreign key multicolonna nel round-trip

Il JSON normalizzato rappresenta una FK come entità di tabella con liste
`columns` e `related_columns`. La grammar moderna la rappresenta come relation
figlia di una `compositeColumn`.

Un importer deve quindi:

- sintetizzare compositeColumn locali e target con nomi deterministici; oppure
- introdurre un elemento fisico di tabella per le FK importate; oppure
- definire una rappresentazione esplicita della relation composta che non
  perda il modello ergonomico.

Non scegliere implicitamente: creare prima fixture di round-trip e confrontare
le alternative.

### 6.2 `indexed=True` contro elemento `index`

Occorre stabilire se `indexed=True` è soltanto sugar che materializza un index
reale oppure metadato interpretato dal renderer. Il tree finale e il JSON
normalizzato devono avere una sola semantica canonica.

### 6.3 Tipo normalizzato contro tipo nativo

`dtype` offre portabilità; `sql_type` è l'escape hatch nativo. Definire:

- precedenza;
- mapping per dialetto;
- round-trip dei tipi non riconosciuti;
- comportamento di array, domain, enum, range e tipi custom.

### 6.4 Feature non ancora nel contratto 1.0

View, function, sequence, type e trigger sono previsti dalle roadmap ma non
tutti appartengono al contratto stabile corrente. Ogni nuova famiglia richiede
versionamento, capability flag, factory, reader, validator, writer e test di
idempotenza in `asqueel-migration`.

## 7. Criterio di grammar completa

La grammar non è completa perché possiede molti nomi. È completa quando, per
ogni elemento:

- significato fisico e semantico sono documentati;
- parametri, tipi, default ed enum sono esposti;
- parent, child e cardinalità sono formalizzati;
- portabilità e backend supportati sono dichiarati;
- invarianti locali e globali hanno un validator;
- esiste almeno un consumer verificato;
- esiste almeno un esempio e un errore negativo testato;
- export della grammar, GUI e LLM vedono lo stesso contratto.
