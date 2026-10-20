# 69 — bagItemColumn native e guide connessioni

14 ottobre 2026. Raccordata la dichiarazione esistente
`bagItemColumn(name, bagcolumn=..., itempath=..., dtype=...)` al compilatore,
seguendo il legacy corrente. Nessuna nuova sintassi, API pubblica di helper,
macro o conversione Python. Query concatenate e operatori restano rinviati.

## Confronto legacy e branch

Il riferimento `fa35e5adfa6ad1b269f3a22a9b12c4c1ee6513ea` traduce la colonna
in una formula SQL tramite `gnrsqlmodel/helpers.py:34`, richiamato da
`model.py:1131` e `table.py:744`. L'algoritmo:

1. divide il percorso Bag sui punti;
2. traduce `#n` in `*[n+1]`, mantenendo la base zero della dichiarazione;
3. traduce il suffisso `?nome` in un attributo XPath, altrimenti usa `text()`;
4. assegna `/GenRoBag/...` a `var_calculated_path`;
5. prende il primo risultato di `xpath(:calculated_path, CAST(bagcolumn AS XML))`;
6. converte in text e, quando necessario, nel tipo SQL della mappa legacy.

Legacy corrente e `next` hanno gli stessi corpi per helper, dichiarazione e
metodo della tabella. Entrambi risolvono i tipi custom prima del cast e hanno
la mappa estesa, con fallback text per i tipi sconosciuti all'helper.
Compound, v2, v3, v3_merged, v4 e simplify conservano l'estrazione ma usano
la vecchia mappa indicizzata direttamente: non gestiscono I, DH o money.
Non viene importata questa regressione né una trasformazione sperimentale
in JOIN. La traduzione resta una formula nel percorso comune.

| Snapshot | Replay dei sette test helper del legacy corrente |
| --- | --- |
| legacy, next | 7/7 ciascuno |
| compound, v2, v3, v3_merged, v4, simplify | 4/7 ciascuno; KeyError su I, DH e money |

Questo confronto esegue gli helper originali; non dichiara rieseguite le intere
suite dei branch. Il censimento comprende gli usi nei test presenti in tutti
gli otto snapshot. Commit, percorsi, righe e hash sono nel
[confronto riproducibile](evidence/native-bag-items/legacy-comparison.json).

## Raccordo al compilatore

La source e il modello mantengono bagcolumn/itempath e il tipo già risolto dal
render. Non generano SQL durante il render. `_Context.formula_definition`
prepara una copia degli attributi e la passa alla normalizzazione delle formule
esistente. La traduzione del percorso è separata dalla stringa SQL PostgreSQL.
Il dialetto mantiene i cast della mappa legacy; non viene aggiunto un secondo
compilatore né modificato il formato del QueryPlan.

Il parametro generato usa gli stessi scope e mangler di var_*: isolamento dal
chiamante, da altre colonne e dalle SELECT annidate, riuso per la stessa colonna
sullo stesso alias. bagcolumn attraversa il normale risolutore di espressioni:
nomi fisici, alias e relazioni ordinarie sono trattati come nelle altre formule.
Il percorso XPath non viene interpolato nel SQL. Le verifiche coprono anche
cicli, dipendenze, ricompilazione e uso concorrente della stessa query.

La cache dura una compilazione. La prova di sostituzione del modello effettivo
verifica che la compilazione successiva veda un itempath diverso; non introduce
né certifica un RuntimeModel. Il suo raccordo completo resta aperto.

## Risultati e limiti preservati

- Le tre dichiarazioni native `invc.product.detail_weight`, `detail_color` e
  `detail_price` compilano su PostgreSQL. `money` è già risolto dal render a N,
  conservando size 14,2; non viene richiamato un nuovo provider durante la query.
- Il primo nodo XPath viene convertito come nel legacy. NULL, percorso assente
  e elemento senza testo producono NULL. Nessuna normalizzazione di XML non valido
  o di valori non convertibili: PostgreSQL segnala l'errore all'esecuzione.
- Il testo conserva le entità XML, per esempio `&amp;`; non è decodificato in
  Python. Date, numeri e timestamp usano i cast PostgreSQL e i codec esistenti.
- SQLite non ha l'equivalente XPath nel legacy. La selezione di bagItemColumn
  produce `UnsupportedFeatureError` alla compilazione, anziché SQL ineseguibile.
  Non vengono registrate funzioni SQLite o introdotte emulazioni Python.
- Non cambia la selezione delle virtuali statiche in `*`, il significato di
  bagFields, il JSON strutturale per migration o il comportamento delle scritture.
  BAG/BAGCOLS e pyColumn restano fuori da questo incremento.

## Test e copertura

Rieseguiti i **15 test originali pertinenti** del legacy corrente: tutti superati,
con le fixture originali di `test_compiler_coverage.py` e `test_model_structure.py`.
Due warning di deprecazione legacy, nessun fallimento o test pertinente saltato.

Gli stessi 15 casi sono portati in Asqueel:

- quattro test di risultato conservano i corpi originali, con fixture native e
  CSV congelati già usati dal corpus delle formule;
- sette test helper conservano i corpi originali, con un adattatore solo nei
  test verso il traduttore del percorso e il dialetto;
- quattro test strutturali sono adattati agli oggetti nativi e al SQL prodotto
  alla compilazione. Non viene aggiunto `table.bagItemFormula` per riprodurre
  un'API non concordata; nessun SQL viene memorizzato nella colonna.

[Provenienza e adattamenti](evidence/native-bag-items/legacy-tests.json).
I test storici di risultato verificano soprattutto assenza di errori: sono
integrati da **10 test di compilazione senza I/O** e **9 prove PostgreSQL sui
valori**, comprese cardinalità, attributi, posizioni, tipi, NULL, testo escapato,
WHERE/GROUP/HAVING/ORDER, DISTINCT count, relazioni, sottoquery e errori SQL.

Suite completa: **1974 superati, 13 saltati**. Ruff, mypy e Sphinx strict
superati; **10 test documentali** rieseguiti sulle guide finali. Il censimento senza I/O sulle
virtuali native conferma **3/3 bagItemColumn**, 460/462 formulaColumn,
45/46 aliasColumn e 3/3 subQueryColumn compilabili. Gli altri blocchi sono
invariati: #PREF rinviato, ambiente mancante nella sonda, virtualRelation e
pyColumn. Questi numeri attestano compilazione, non equivalenza di ogni risultato.

Comandi ed esiti finali: [verification.json](evidence/native-bag-items/verification.json).

## Documentazione CLI e configurazione

Corrette le guide rispetto alle API già implementate: connessioni nominate,
name logico distinto da database/dsn, main esplicita, selezione con
`tempEnv(connectionName=...)`, stesso dialetto, eredità di implementation e
`connection.options().driver(...)`. Documentata la compatibilità con le forme
precedenti e l'esclusione reciproca con conninfo/connect_kwargs. Nessun codice
di configurazione o CLI è stato cambiato. Conservazione di None esplicito
riallineata a SqlConfigHandler; guida transazioni collegata alle dichiarazioni.

## Riproduzione

```sh
venv/bin/python docs/design/probes/replay_bag_items.py \
  --snapshots /tmp/asqueel-formula-baseline
PYTHONPATH=src:../asqueel-migration/src venv/bin/python -m pytest -q -o addopts= \
  tests/native_compiler/test_legacy_bag_items.py \
  tests/native_compiler/test_bag_items.py \
  tests/native_formulas/test_legacy_bag_items.py \
  tests/native_formulas/test_bag_item_results.py
```
