# 33 — Piano: rettifica della struttura del modello

Stato: proposta, da approvare. Nessun passo è avviato.
Baseline: `04bef4c`, versione 0.4.0 pubblicata; 845 test.
Riferimento legacy: `origin/develop` di genropy (`51e4270c54`),
`gnrpy/gnr/sql/gnrsqlmodel/model.py` (`DbModelSrc`).
Precede il [piano 32](32-expression-resolver-plan.md): cambia la dichiarazione
del modello che il resolver legge.

## Obiettivo

Il modello si dichiara come nel legacy: colonne, colonne virtuali e indici si
dichiarano sulla tabella; i contenitori restano interni. Si aggiunge `colgroup`,
con la dichiarazione legacy e una rappresentazione interna senza i difetti
dell'attributo composito legacy.

Regola di compatibilità (piano 32): la sintassi legacy è quella di default;
asqueel non aggiunge grafie alternative; ogni divergenza ha una motivazione
esterna scritta.

Vincolo di progetto (2026-10-02): `virtualRelation` arriverà (proposta in
genropy/genropy_meta#1). Non si progetta né si implementa nulla che
`virtualRelation` renderebbe inutile: relazioni filtrate, collegamenti senza FK
verso target non unici, scelta di una riga per ordine e limite.

## Stato attuale e differenza dal legacy

Legacy (`model.py`):

```python
tbl = pkg.table('customer', pkey='id')
tbl.column('state', size=':5').relation('invc.state.code', relation_name='clients')
tbl.formulaColumn('full_address', sql_formula="$street || ', ' || $city", dtype='T')
tbl.aliasColumn('state_name', relation_path='@state.name')
addr = tbl.colgroup('address', name_long='Address')
addr.column('street')
addr.formulaColumn('label', sql_formula="$street || ' ' || $city")
```

`column` scrive in `columns.<nome>` (`:937-945`); le virtuali in
`virtual_columns.<nome>` (`:1022-1027`); `index` in `indexes.<nome>` (`:1335`).
Chi scrive il modello non vede i contenitori.

Asqueel (`elements.py:146-219`):

```python
columns = table.columns()
columns.column('state', ...)
virtuals = table.virtual_columns()
virtuals.formulaColumn('full_address', ...)
```

L'unica motivazione scritta dei contenitori espliciti è evitare collisioni fra
famiglie di nomi (`elements.py:37-41`, `01-findings-model.md:13-19` F-M02).
I contenitori interni la soddisfano allo stesso modo: i path dei nodi restano
`tables.<t>.columns.<c>`, `tables.<t>.virtual_columns.<v>`.

## Meccanismo verificato

genro-builders 0.27.0 non ha un parametro di instradamento in `@element`. Un
override di `SqlBuilder.set_child` (`builder.py:86-111`) può scegliere il
contenitore in base al tag e chiamare il `set_child` del framework sul
contenitore: tutti i controlli della grammatica valgono nella posizione finale.
Un prototipo in memoria ha verificato path invariati, `validate_model`, la
proiezione verso le migrazioni. Catalog, validatori, modello risolto,
migrazioni, configurazione e `application_table` leggono i path attuali e non
cambiano.

Non funzionano: un elemento contenitore con nome che inizia con `_`
(`_utilities.py:356`); un `@container` chiamato `column` accanto all'elemento
`column` (`source_bag.py:538-542`). Un elemento ridefinito in una sottoclasse
intermedia di `SqlBuilder` viene perso nella sottoclasse successiva
(`_utilities.py:378-408`): le modifiche vanno nei mixin di `elements.py`.

## Difetti del `colgroup` legacy da non riprodurre

Verificati in memoria sul codice di `origin/develop`:

1. L'ordine è codificato nella stringa `group='<nome>.<NNN>'` (`model.py:843`) e
   il contatore non avanza: conta i figli del nodo colgroup, che restano zero.
   Tutte le colonne ricevono `<nome>.001`.
2. L'etichetta del gruppo sta sulla tabella come attributo `group_<nome>`
   (`:831`), nello stesso spazio di `group_zzz`, `group_subtables`,
   `group_hierarchical_*`; si ritrova solo cercando il prefisso `group_`
   (`gnrsqltable/utils.py:616-620`).
3. L'etichetta è copiata in ogni colonna (`colgroup_label`,
   `colgroup_name_long`, `:844-847`) e può contraddire quella della tabella:
   `teamset ts_po/model/ordine_acquisto.py:67` e `:71` dichiarano `ts` due volte
   con etichette diverse.
4. Due codifiche parallele: l'albero dei campi legge `group` e `group_*`;
   mkthresource legge `colgroup_label` (`dev/makers/resource.py:488-495`).
   Nessuno legge il contenitore `colgroups`.
5. `relation()` riscrive il gruppo della colonna in `'_'` e sposta il valore in
   `one_group` (`:1388-1392`): una FK nel gruppo diventa riservata ed esce dalle
   viste di base e dai form automatici.
6. Il `group` proprio della colonna viene sempre sovrascritto (`:843`); un
   `group=` passato a `colgroup()` resta sul nodo e non ha effetto (11 chiamate
   reali in anaci, teamset, gbs).
7. I default `col_*` non si applicano ai parametri con nome di `column()`
   (`size`, `dtype`, `name_long`, ...), perché `setdefault` trova la chiave già
   presente con `None`; si applicano a `formulaColumn`.
8. Il decoratore modifica anche i nodi strutturali creati attraverso il gruppo:
   `column_list` e `index_list` della tabella ricevono gli attributi dell'ultimo
   gruppo.
9. I metodi chiamati sul gruppo usano il gruppo come se fosse la tabella:
   `index()` prende il nome dal gruppo (`:1331`); `compositeColumn` non trova le
   colonne (`:1099-1130`); `subQueryColumn(mode='json')` alza `AttributeError`
   (`:1219`); il controllo `_override` fra colonna fisica e virtuale viene
   saltato (`:1007-1019`).
10. Nessun test (`gnrpy/tests`).

Uso reale: 477 chiamate `.colgroup(` in 197 file di 24 repository indicizzati
(teamset 187, anaci 96, erpylight 43, ...). La dichiarazione va conservata.

## Passo 1 — Contratto della dichiarazione

- Elenco dei metodi di tabella del legacy (`DbModelSrc`) con la firma, e per
  ciascuno: supportato, non ancora presente, divergenza motivata.
- In questo incremento: `column`, `formulaColumn`, `aliasColumn`,
  `subQueryColumn`, `pyColumn`, `index`, `colgroup`, `relation` sulla colonna.
- Non ancora presenti (la grammatica non li conosce): `joinColumn`, `bagItemColumn`, `toolColumn`,
  `aliasTable`, `subtable`, `virtual_column` generico.
- `compositeColumn` come nel legacy (D3); `constraint` non accettato (D12).

**Uscita:** tabella nel documento [adattamenti legacy](../adattamenti-legacy.md).

## Passo 2 — Dichiarazione sulla tabella

- `table` accetta direttamente gli elementi del passo 1.
- `SqlBuilder.set_child` instrada ogni elemento nel suo contenitore interno:
  `column` → `columns`; colonne virtuali → `virtual_columns`; `index` →
  `indexes`; `compositeColumn` → contenitore interno delle composite. Il contenitore viene
  creato alla prima colonna.
- La forma esplicita `table.columns()` / `table.virtual_columns()` non è più
  accettata (nessuna grafia alternativa). Il test di contratto
  `tests/test_wf_phase18_explicit_collections.py:88-141` si inverte.
- Path, catalog, validatori, modello risolto, migrazioni e configurazione
  restano invariati.

**Uscita:** la dichiarazione del tutorial in forma legacy produce lo stesso
modello risolto e lo stesso JSON di migrazione di oggi.

## Passo 3 — Nomi unici nella tabella

- Un nome usato da una colonna fisica e da una virtuale → errore in validazione.
  Oggi passa e la virtuale sostituisce la fisica senza segnalazione
  (`catalog.py:130`, `model.py:58`). Il legacy lo rifiuta salvo `_override`
  (`model.py:1007-1019`).
- Da decidere (D4): se portare `_override`.

**Uscita:** test di collisione fra famiglie e fra gruppi.

## Passo 4 — `colgroup`

Decisioni del 2026-10-01 (D1, D5).

Nel legacy `group` fa tre lavori con sintassi diverse: raggruppa le colonne;
decide la visibilità nell'interfaccia (`'_'` riservato, `'*'` nascosto);
posiziona i nodi delle relazioni nell'albero dei campi (`one_group`,
`many_group`, riscrittura in `relation()`, `model.py:1388-1392`). Gli ultimi due
sono problemi di interfaccia. In asqueel `colgroup` raggruppa e basta.

```python
addr = tbl.colgroup('address', name_long='Address')
addr.column('street')                        # colonna dichiarata nel gruppo
addr.formulaColumn('label', sql_formula="$street || ' ' || $city")
tbl.column('city', colgroup='address')       # colonna sulla tabella, con il nome del gruppo
```

- Il gruppo si dichiara una volta con `tbl.colgroup(nome, name_long=...)`.
  Altri attributi del gruppo: da decidere.
- Una colonna, fisica o virtuale, entra nel gruppo in due modi: dichiarata con
  un metodo del gruppo, oppure dichiarata sulla tabella con `colgroup='<nome>'`.
  La seconda forma serve anche ai metodi che aggiungono colonne fuori dal blocco
  del gruppo.
- L'ordine delle colonne nel gruppo è l'ordine di dichiarazione. Non esistono
  numeri di posizione: per cambiare l'ordine si cambia la dichiarazione.
- `colgroup='<nome>'` di un gruppo non dichiarato nella tabella → errore di
  validazione. Una colonna dichiarata in un gruppo con un attributo `colgroup`
  diverso → errore. Un gruppo dichiarato due volte → errore.
- Le colonne restano nei loro contenitori, con i path di oggi: identità e chiave
  di configurazione non dipendono dal gruppo.
- Il modello risolto espone per ogni tabella i gruppi in ordine di
  dichiarazione, ciascuno con nome, `name_long` e colonne in ordine.
- I metodi chiamati sul gruppo si comportano come sulla tabella (difetto 9). I
  default `col_*` valgono per tutti i parametri (difetto 7). `relation()` non
  cambia il gruppo della colonna (difetto 5).
- Non si accettano `group=` sulla colonna né `group_<nome>=` sulla tabella. È
  una divergenza dal legacy: la codifica legacy mette in stringhe ordine,
  gerarchia e visibilità, e mescola raggruppamento e interfaccia. Un importatore
  legacy converte `group='x'` con `group_x='L'` in `colgroup('x', name_long='L')`
  più `colgroup='x'` sulle colonne. Visibilità e posizione delle relazioni
  restano al livello dell'interfaccia (`x_ui`).

**Uscita:** test su ordine, appartenenza nelle due forme, errori, default
`col_*`, metodi chiamati sul gruppo, FK nel gruppo.

## Passo 4b — Relazioni e migrazione

Decisione del 2026-10-02 (D7).

- Ogni relazione, con o senza FK, produce un indice sulle sue colonne sorgente,
  come nel legacy (`gnrsqlmigration/orm_extractor.py:256-257`). Motivo:
  PostgreSQL non indicizza le colonne referenzianti; senza indice la navigazione
  inversa e ogni `DELETE`/`UPDATE` della chiave referenziata leggono tutta la
  tabella sorgente.
- L'indice non viene creato quando le colonne sorgente sono già le prime
  colonne della chiave primaria, di un vincolo `UNIQUE` o di un indice
  dichiarato. Il legacy controlla l'appartenenza alla pkey, non la posizione
  iniziale (`:281`): con pkey `(a, b)` salta l'indice anche per una FK su `b`.
- L'opzione `indexed=False` su una relazione (`migration.py:173`) si rimuove: è
  un'estensione di asqueel senza motivo esterno.
- Oggi asqueel indicizza solo le relazioni con `foreign_key=True`
  (`migration.py:146-175`).

**Uscita:** test di proiezione per relazione con e senza FK, semplice e
composta, con colonne coperte e non coperte da pkey, `UNIQUE` e indice.

## Passo 4c — `relation` e `weak_relation`

Decisione del 2026-10-02 (D11).

- `relation()` produce sempre una FK nel database. Il target deve avere una
  chiave unica: il database lo richiede.
- `weak_relation()` è una relazione logica, senza vincolo nel database.
  Accetta il parametro `insensitive=True` per il join senza distinzione fra
  maiuscole e minuscole.
- Divergenza dal legacy: in GenroPy `relation()` senza `mode` è logica
  (`mode='relation'` di default, `model.py:1338-1342`); la FK richiede
  `mode='foreignkey'`. Motivo: sugli 8 repository applicativi più grandi
  indicizzati da Sourcerer, 3555 dichiarazioni `.relation(` su 4134 (86%)
  usano `mode='foreignkey'`; `mode='insensitive'` non compare in nessun
  modello. Il default di asqueel copre il caso comune senza parametri.
- Un importatore legacy traduce `mode='foreignkey'` in `relation`,
  `mode='relation'` in `weak_relation`, `mode='insensitive'` in
  `weak_relation(insensitive=True)`.
- Oggi asqueel ha `relation(foreign_key=False, case_insensitive=False)`
  (`elements.py:391`): `foreign_key` e `case_insensitive` si rimuovono.

**Uscita:** test di modello e di proiezione per i due elementi; errore per
`relation` verso un target senza chiave unica.

## Passo 5 — Emitter, reader, proiezione, documentazione della grammatica

- `emitter.py:169-194`: emette la forma legacy, con i gruppi.
- `reader.py` e `projection.py`: costruiscono con la forma legacy.
- `grammar_doc.py`: documenta i contenitori come interni.

**Uscita:** roundtrip modello → Python → modello invariato, gruppi compresi.

## Passo 6 — Migrazione di test, guide ed esempi

- Test: 40 file usano `.columns()` / `.virtual_columns()` (154 occorrenze);
  11 file contengono path letterali con i contenitori, che restano validi.
- Guide e documenti: 14 file; esempi: 7 file; README.
- `x_name` come nome di navigazione viene rimosso qui (decisione D2 del
  piano 32), insieme alle dichiarazioni del modello che lo usano.

**Uscita:** suite verde; build Sphinx rigorosa.

## Passo 7 — Accettazione

- [Adattamenti legacy](../adattamenti-legacy.md): tabella dei metodi di tabella e
  divergenze di `colgroup` rispetto alla codifica legacy.
- Release notes: breaking change della dichiarazione per asqueel 0.4.
- Piano 15: stato di F2 per la parte struttura.

## Fuori da questo incremento

- La semantica d'interfaccia dell'attributo `group` legacy (`'_'` riservato,
  `'*'` nascosto, `'zz'`, `one_group`/`many_group`): livello dell'interfaccia,
  non nucleo di asqueel (D5).
- `joinColumn`, `bagItemColumn`, `toolColumn`, `aliasTable`, `subtable`.
- Colonne `localized` e `ext_*`.

## Decisioni aperte

- **D1 — Rappresentazione di `colgroup` — DECISA (2026-10-01).** Gruppo
  dichiarato con `colgroup`; appartenenza dichiarata nel gruppo o con
  `colgroup='<nome>'`; ordine di dichiarazione, nessun numero di posizione;
  colonne nei contenitori di oggi. Dettagli nel passo 4.
- **D2 — Forma esplicita dei contenitori — DECISA (2026-10-02).** Rifiutata:
  `tbl.columns()` e `tbl.virtual_columns()` non sono più accettati (nessuna
  grafia alternativa). È un breaking change per asqueel 0.4.
- **D3 — `compositeColumn` — DECISA (2026-10-02).** Identico al legacy, un solo
  concetto per ogni chiave su più colonne: colonna virtuale con il valore
  serializzato `'["P1", 2024]'`, `static=True` di default (presente in `*`);
  `unique=True` produce il vincolo `UNIQUE`; `.relation(...)` fa la relazione su
  più colonne verso un altro `compositeColumn`; `pkey` nomina sempre una sola
  colonna, fisica o `compositeColumn` (`pkey='product_year_key'`). Il valore è
  l'identità del record con pkey composta (`gnrsqltable/utils.py:84-91`
  `compositeKey`, `query.py:47-60` `parseSerializedKey`). Oggi asqueel dichiara
  `pkey='product_id,year'` e il `compositeColumn` non è una colonna: breaking
  change per asqueel 0.4.
- **D12 — `constraint` — DECISA (2026-10-02).** Esce dal modello in questo
  incremento, con entrambi i tipi. La chiave unica su più colonne è
  `compositeColumn(..., unique=True)`. `CHECK` torna nel modello insieme agli
  altri oggetti nativi del database (trigger, funzioni, view). `asqueel-migration`
  gestisce già i `CHECK` (`readers/base_reader.py:215-221`,
  `command_builder.py:311-331`), salvo il reader SQLite
  (`readers/sqlite_reader.py:35`). L'importatore di asqueel non porta i `CHECK`
  e avvisa con il nome del vincolo; la migrazione è additiva
  (`removed_constraint` è un no-op, `command_builder.py:905-907`), quindi il
  vincolo resta nel database.
- **D4 — `_override` — DECISA (2026-10-02).** In questo incremento un nome
  usato da una colonna fisica e da una virtuale dà sempre errore. Gli usi reali
  di `_override=True` (`frigel_cont`, `icond`) stanno in `_packages/`, dove un
  package modifica la tabella di un altro: `_override` arriva con la
  composizione fra package, con la sintassi legacy.
- **D5 — Attributo `group` legacy — DECISA (2026-10-01).** Non accettato:
  `colgroup` è l'unica sintassi di raggruppamento. Visibilità e posizione delle
  relazioni appartengono al livello dell'interfaccia.
- **D6 — Attributi di `colgroup` — DECISA (2026-10-02).** Solo `name_long` e i
  default `col_*`. `group=` non è accettato (nel legacy non ha effetto sulle
  colonne). Eventuali attributi d'interfaccia passano da `x_ui`.
- **D7 — Indice delle relazioni — DECISA (2026-10-02).** Vedi passo 4b.
- **D10 — Nomi dei parametri di `relation` e `weak_relation` — DECISA
  (2026-10-02).** Nome legacy in forma snake: `related_column`,
  `relation_name`, `one_name`, `many_name`, `one_one`, `on_delete`/`on_update`
  (azioni Python sui collegati, legacy `onDelete`/`onUpdate`),
  `on_delete_sql`/`on_update_sql` (azioni SQL della FK, legacy
  `onDelete_sql`/`onUpdate_sql`), `deferred`, `deferrable`,
  `initially_deferred`. Oggi in asqueel `on_delete` è l'azione SQL: breaking
  change per asqueel 0.4. Principio generale: nel dubbio prevale la versione
  Python rispetto a quella affidata all'SQL. `on_update_sql` vale `'cascade'` di
  default, come nel legacy (`model.py:1352`): ogni FK nasce con
  `ON UPDATE CASCADE` (deciso 2026-10-02; da spiegare nella guida).
  `on_delete`/`on_update` (azioni Python) fanno parte dell'API obiettivo ed
  entrano nella firma con il ciclo delle scritture (`deleteRelated`/
  `updateRelated`, F4). Nessun codice provvisorio: fino ad allora il validatore
  esistente li rifiuta come attributi sconosciuti (`validators.py:106-120`).
- **D11 — `relation` = FK, `weak_relation` logica con `insensitive` — DECISA
  (2026-10-02).** Vedi passo 4c.
- **D8 — `weak_relation` verso un target non unico — DECISA (2026-10-02).**
  `weak_relation` tratta il target come unico sulla fiducia: nessun controllo
  della chiave del target. Un collegamento verso un target non unico (caso
  `anaci organo_carica.py:29-30`) e la scelta di una riga per ordine non sono
  parametri di `weak_relation`: appartengono a `virtualRelation`
  (`table=`/`condition`, `order_by`/`limit`, genropy/genropy_meta#1). Fino ad
  allora non esistono.
- **D9 — Indice sulle colonne di destinazione — DECISA (2026-10-02).** Una
  `weak_relation` crea un indice sulle colonne di destinazione, come nel legacy
  (`orm_extractor.py:273-279`, `:441-443`), salvo che siano già le prime
  colonne di una pkey, di un `UNIQUE` o di un indice. Con `relation` la
  destinazione è una chiave unica e ha già il suo indice.
