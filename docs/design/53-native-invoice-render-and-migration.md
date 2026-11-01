# 53 — Render nativo di test_invoice_pg e JSON migrations

13 ottobre 2026. **Verificati i 74 modelli nativi, gli oggetti e il JSON per
asqueel-migration.** Il JSON coincide esattamente con l'oracolo fisico legacy
rimuovendo soltanto `sys.locked_record`, come concordato. La verifica PostgreSQL
applica il modello su un database temporaneo, esegue l'introspezione e ottiene
una seconda diff vuota. Nessuna operazione sul database applicativo test_invoice_pg.

## Consegna e riproduzione

- [Source nativa](../../examples/test_invoice_pg/__init__.py), con dichiarazioni
  separate per [sys](../../examples/test_invoice_pg/packages/sys),
  [adm](../../examples/test_invoice_pg/packages/adm) e
  [invc](../../examples/test_invoice_pg/packages/invc), un modulo
  `model/<table>.py` per tabella.
- [JSON migrations nativo](../../artifacts/test_invoice_pg/native/migration.json).
- [Modello risolto serializzato](../../artifacts/test_invoice_pg/native/model.json),
  generato dal producer e non versionato, secondo il .gitignore degli artefatti.
- [Test del corpus](../../tests/test_native_invoice_migration.py).
- [Audit aggiornato](evidence/invoice-render-coverage.json), con membership dei
  74 modelli, hash della source nativa e confronto fisico indipendente.

```sh
PYTHONPATH=.:src:../asqueel-migration/src /tmp/asqueel-repo-audit-env/bin/python \
  scripts/export_invoice_migration.py
```

Il producer importa soltanto le dichiarazioni native e costruisce gli oggetti
con build_database. Da db.model passa alla proiezione fisica esistente e al
renderer migration. Non legge XML/JSON legacy, non importa GenroPy e non
riesegue le options durante la proiezione. Gli artefatti storici del bridge
rimangono nella directory superiore, distinti da quelli nativi.

| Package | Tabelle | Colonne fisiche | FK | Indici |
| --- | ---: | ---: | ---: | ---: |
| sys | 16 | 188 | 7 | 56 |
| adm | 40 | 412 | 32 | 150 |
| invc | 18 | 189 | 19 | 76 |
| Totale | **74** | **789** | **58** | **282** |

Il modello contiene inoltre **526 colonne virtuali**, due composite e una
UNIQUE composita. Le sei virtuali di system_records sono escluse; __syscode è
attivato esplicitamente con sys_fields(syscode=True) sulle tre tabelle previste.

## Provenienza e traduzione

Le configurazioni sono trascritte dai config_db originali non espansi; ogni
funzione riporta file e hash del manifest legacy. Le colonne generate non sono
copiate dalle catture: sys_fields, gerarchie, contatori, dynamic_fields, audit,
hash e allegati restano options della source e vengono espansi dal render.
Il contributo adm → sys.task rimane un contributo separato. Il profilo usa
user_upd=False esplicito, coerente con la cattura, senza cambiare il default
pubblico True. USE_ASYNC_TASKS è False nel profilo offline della cattura.

Rimangono valide le trasformazioni grammaticali già concordate:

- values → validate_values; readOnly/defaultFrom → read_only/default_from;
  validate_* raccolti nelle validations, senza interpretare o eseguire regole.
- Metadati con namespace piatto; batch_assign_tags conserva il tag originale.
  I nomi legacy privi di firma nativa usano il namespace x_legacy_* già presente.
- Le due espressioni string_agg sono la stringa prodotta dall'adapter PostgreSQL
  legacy; itemTypeValues restituisce una costante, trascritta come tale. Non sono
  introdotti resolver o metodi di runtime. Le partizioni usano EnvResolver.
- aliasTable(customer) diventa virtualRelation sul percorso esistente.
  joinColumn(discount_tier_id) diventa virtualRelation condizionale con var_* e
  alias della chiave. Non vengono generati inverse, limit, order_by o one_one
  sulle virtual relations.
- L'alias invoice_row.customer_id naviga @invoice_id.customer_id; la navigazione
  al cliente è già la virtualRelation customer. La relazione aggiuntiva che il
  legacy dichiarava sull'alias non crea un nuovo collegamento/inversa nella
  grammatica corrente: target, relation_name e many_group originali sono
  conservati nei suoi attributi piatti x_legacy_relation_*. Riferimento: regola
  aliasColumn del contratto 42, che non porta una propria relazione.
- SubQueryColumn e bagItemColumn conservano query/mode e bagcolumn/itempath;
  non sono sostituite con le espressioni SQL generate dalla cattura legacy.
  Formule, select_*, var_* e riferimenti Python rimangono dichiarazioni.
- Gli alias ereditano tipo e attributi dal target salvo override esplicito.
  Il dtype T delle dichiarazioni alias grezze nel dump legacy non è usato per
  annullare tale eredità; le prove verificano il target effettivamente risolto.

System_records, release, diagnostica opzionale e locked_record restano fuori
perimetro. Nessuna nuova firma applicativa, ricerca automatica di metodi o
esecuzione di callback sui record.

## Correzioni del render e della proiezione

Le verifiche sul corpus hanno completato punti già previsti dal piano 51:

1. weak_relation sulle formule scalari ora supera la grammatica e verifica il
   target; una FK fisica sulla formula resta vietata.
2. static degli alias viene accettato e conservato; un default implicito non
   annulla l'attributo ereditato dal target.
3. Gli alias di tipo dei package si applicano anche alle colonne virtuali,
   conservando size e formato: money/perc non restano dtype irrisolti.
4. Gli indici delle weak relations vengono completati anche sulle composite,
   senza duplicare indici già presenti o trattare indici parziali/non-btree
   come il normale indice richiesto. Le formule non ricevono indici fisici.
5. subtable genera le virtuali booleane subtable_<nome> come
   DbModelSrc._subtable_table, conservando anche la dichiarazione originale.
6. La relazione eredita il gruppo della FK quando one_group è omesso, secondo
   DbModelSrc.relation; è verificato anche il caso degli allegati.
7. La proiezione normalizza i tipi di storage dei package come l'estrattore
   legacy: A con lunghezza fissa → C; :n → 0:n; X/Z/P → T; N con precisione
   senza scala → precisione,0. Gli oggetti mantengono i tipi logici. Il percorso
   fisico di basso livello con schema esplicito mantiene il proprio contratto.

Il confronto JSON è una uguaglianza completa dei dict, senza mascherare nomi,
indici, vincoli o attributi. Gli oracoli indipendenti non sono stati modificati.

## Prove e limite del risultato

La suite del corpus verifica separatamente tutti i 74 modelli: membership delle
colonne fisiche e virtuali, tipi, composite, subtables e conservazione degli
attributi originali. Controlla anche relazioni fra package, alias su composite,
virtual relations, options dichiarative, codec del modello e immutabilità.
Una prova vieta lettura degli oracoli, connessioni e analisi delle formule durante
la costruzione nativa; dopo il render vieta ulteriori espansioni e risoluzioni,
modifica la source originale e verifica lo stesso JSON dagli oggetti.

Il gate PostgreSQL verifica applicazione, introspezione e seconda diff vuota,
poi modifica una vera option (full_update), colonna, UNIQUE, FK e indice.
Dopo l'applicazione la diff torna vuota e una view esterna rimane presente.
La suite storica del bridge continua a passare sui 75 modelli originali.

Suite completa: **1278 test superati, 1 saltato**; Ruff e mypy su 50 file
superati nell'ambiente di verifica. Dopo la correzione finale dell'eredità di
static, ripetuti anche i test del corpus e degli alias: **165 superati**, gate
PostgreSQL escluso da questa ripetizione perché già passato e DDL invariato.

Questo chiude le fasi 4–6 del piano strutturale. Non certifica compilazione o
esecuzione delle formule, hook, validazioni sui record o scritture applicative.
