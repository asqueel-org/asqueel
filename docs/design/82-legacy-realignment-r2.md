# 82 — R2: proiezioni e parametri simbolici legacy

14 ottobre 2026. **R2 completata nel perimetro locale.** Suite finale:
**3.791 test superati, 13 saltati**; lint dei nove file Python interessati
superato. Raccordo sul nuovo albero gerarchico, secondo il
[piano 79](79-legacy-compiler-realignment-plan.md). Riferimento vincolante:
GenroPy `fa35e5adfa6ad1b269f3a22a9b12c4c1ee6513ea`. Nessuna nuova sintassi.

## Proiezioni: conservare quello che faceva compiledQuery

Ripreso il blocco `col_list` / `col_dict` di `compiledQuery`: suddivisione legacy,
rimozione dei duplicati testuali prima dello strip, ordine conservato e ultima
proiezione per la stessa chiave AS. Se manca AS, l'alias è quello di `colToAs`,
quotato dall'adapter. Se AS compare, il testo della proiezione resta invariato.
La chiave legacy per i duplicati deriva dal **primo** ` AS `, anche interno.

In R1 il raccordo separava espressione e alias per poi ricostruire il SQL.
Questo cambiava gli alias espliciti e non permetteva un CAST senza alias esterno.
Ora `projection_columns` conserva il testo come il legacy; non aggiunge un AS
esterno a `CAST($total AS NUMERIC)` e non corregge SQL invalido.

Questo recupera anche le particolarità del legacy: due CAST con lo stesso tipo
possono avere la stessa chiave e lasciare solo l'ultimo. Non è stata introdotta
una deduplicazione alternativa basata sul nome restituito dal database.

### Adattamento interno, senza grammatica nuova

`Projection.alias=None` indica che l'espressione contiene già la proiezione
completa; l'adapter non deve aggiungere un altro AS. Il precedente compilatore
continua a fornire alias separati e mantiene le proprie verifiche.

I metadati vengono recuperati quando il nome del risultato è noto. Quando
dipende dal database, `Projection.column=None` fa lasciare vuoti i metadati
complessivi dello statement: i driver hanno già il percorso che legge i nomi
da `cursor.description`. Non viene inventato un nome né simulato il parser SQL.
In quel caso i metadati di modello delle altre proiezioni non sono allegati
al risultato compilato: resta il percorso esistente di descrizione dal cursore.

La verifica SQLite usa questo percorso direttamente. La fetch sul nuovo albero
rimane disabilitata; R2 produce SQL e kwargs e non abilita esecuzione implicita.
La verifica di unicità dei nomi nelle righe del driver rimane invariata.

## Parametri: embedFieldPars prima della risoluzione del WHERE

Portato `SqlQueryCompiler.embedFieldPars` in `embed_field_parameters`:

- esamina una copia della sequenza degli input;
- decodifica i valori `bytes` per il riconoscimento;
- riconosce `$campo` solo se presente fra colonne fisiche o virtuali;
- riconosce `@relazione.campo` controllando il primo tratto nel ramo relations;
- sostituisce `:nome` con il riferimento usando la stessa regex e il medesimo
  confine `\W|$`, senza interpretazioni aggiuntive;
- applica il passaggio **solo al WHERE**, prima di `updateFieldDict`;
- conserva i valori originali nella mappa del piano e non modifica gli input.

Il ramo relations viene consultato solo per un valore che inizia con `@`, come
nel legacy. Una normale query fisica non materializza quel ramo per questo passo.
La risoluzione SQL delle relazioni rimane R5: il riferimento riconosciuto arriva
al limite esplicito già presente, senza diventare silenziosamente un valore.
Lo stesso vale per le colonne virtuali ancora da raccordare.

I nomi sostituiti vengono registrati fra gli input consumati, usando il campo
già esistente del piano: la verifica dei kwargs non li scambia per inutilizzati
quando non ci sono più placeholder. I valori ancora usati in columns/order_by
rimangono binding ordinari. La preparazione dei driver è sempre unica, senza
mangling anticipato dei nomi simbolici.

## Test originali, port e sonde

| Provenienza | Verifica R2 |
| --- | --- |
| `test_compiler_coverage.TestEmbedFieldPars.test_column_param_pg/sqlite` | Port della comparazione fra due campi fisici; compilazione senza I/O in entrambi i dialetti; invariante `gt + le` eseguito su dati temporanei SQLite |
| `TestEmbedFieldPars.test_relation_param_pg/sqlite` | Baseline originale eseguita; riconoscimento del riferimento verificato, JOIN sul nuovo albero ancora R5 |
| `h_query_surface_test.BaseQuerySurface.test_columns_with_as_alias` | Port del contratto AS; modello di prova minimo, senza importare selection/fetch legacy |
| `compiledQuery`, blocco delle proiezioni | 28 casi contro il compilatore originale, per entrambi i dialetti: alias impliciti/espliciti, normalizzazione, duplicati, CAST e testo conservato |
| `embedFieldPars` originale | 22 casi: fisici, virtuali, relazioni, sconosciuti, bytes, confini/prefissi, Unicode, escape e parametri non usati |

La sonda importa ed esegue il codice originale di ciascuno degli otto snapshot:
**78 confronti × 8 = 624, senza differenze**. L'oracle portabile
`tests/oracles/legacy_r2.json` è prodotto dai risultati del riferimento legacy;
i test non lo rigenerano da Asqueel. Non si tratta di otto suite GenroPy complete.

La baseline dei **quattro test originali TestEmbedFieldPars è passata**, con
fixture SQLite/PostgreSQL del legacy e dati `test_invoice`. I due test locali
portati non dichiarano copertura delle JOIN né dell'intero dataset originale:
per l'esecuzione Asqueel impiegano una fixture deterministica di quattro righe.

Rieseguita anche la sonda delle **148 SELECT fisiche sui 74 modelli nativi**:
nessuna differenza. Nei 47 casi mirati di compilazione, i 23 eseguibili SQLite
mantengono risultati e nomi delle colonne del legacy. Il confronto normalizza
solo spaziatura e quoting dell'alias radice, come in R1.

I test R1 che aspettavano virgolette aggiunte attorno agli AS espliciti sono
stati corretti al testo legacy. Non sono stati rimossi contratti del precedente
compilatore né aggiunti skip/xfail per le differenze recuperate.

## Confine con R3

La distinzione tra riferimento simbolico e valore è chiusa in R2 per i campi
locali. Sono fissati anche i casi di nomi Unicode e valori con `\$`/`\@`, e
l'arrivo invariato di `\:` al confine dell'adapter. `$$` resta nel templating
legacy già portato in R1.

La decodifica finale dei bytes ordinari, la rimozione di `\$`/`\@` dai **valori**,
`\:` nel SQL, percentuali, placeholder Unicode ordinari, collection e
`REGEXP`/`ILIKE` sono responsabilità di R3, come nel piano: nel legacy stavano
nella preparazione comune di `execute` e negli adapter. I driver attuali non
sono ancora integralmente riallineati. R2 non dichiara parità dei kwargs finali
su questi casi e non sposta la loro gestione nel risolutore dei campi.

Nessuna decisione aggiuntiva richiesta. Prima delle relazioni restano R3 e R4;
query concatenate, operatori, mixin e RuntimeModel mantengono il perimetro deciso.

## Evidenze

- [Confronto riproducibile](probes/compare_legacy_r2.py).
- [Riferimento legacy: risultati e casi](evidence/legacy-realignment-r2/legacy.json).
- [Baseline originale](evidence/legacy-realignment-r2/original-tests.log).
- [SELECT native e casi mirati](evidence/legacy-realignment-r2/native/select-summary.json).
- [Suite completa](evidence/legacy-realignment-r2/full-tests.log).
- [Verifica finale e impronte](evidence/legacy-realignment-r2/verification.json).

Le impronte isolano questo passo dalle modifiche già presenti nel working tree.
Nessun commit o push; evidenze R0/R1 conservate.
