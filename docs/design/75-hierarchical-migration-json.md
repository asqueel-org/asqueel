# 75 — JSON migration dal nuovo albero gerarchico

14 ottobre 2026. Chiusa la fase 5 del [piano 70](70-hierarchical-object-renderer-plan.md):
il JSON prodotto dai 74 modelli nativi attraverso objects_tree coincide
integralmente con il JSON del percorso precedente e con l'oracolo fisico legacy,
escluso soltanto sys.locked_record, già fuori perimetro.

## Uso e artefatto

Si riutilizzano le API esistenti, senza una nuova grammatica:

```python
from asqueel import SqlMigrationRenderer, to_physical_builder
from examples.test_invoice_pg import source

model = source().render(mode='objects_tree')
structure = SqlMigrationRenderer(to_physical_builder(model)).render()
```

Lo stesso codice funziona sul modello già collegato a SqlDatabase: il database
operativo non partecipa alla proiezione. Il renderer objects resta predefinito;
il suo percorso di proiezione rimane disponibile.

- [JSON generato](../../artifacts/test_invoice_pg/objects_tree/migration.json)
- [Script riproducibile](../../scripts/export_invoice_tree_migration.py)
- [Test](../../tests/object_tree/test_migration.py)

```sh
PYTHONPATH=.:src:../asqueel-migration/src venv/bin/python scripts/export_invoice_tree_migration.py
```

## Algoritmo e riuso

Riferimento legacy: gnrsqlmigration/orm_extractor.py, commit
fa35e5adfa6ad1b269f3a22a9b12c4c1ee6513ea. In particolare fill_json_package,
fill_json_table, fill_json_column, fill_json_relations_and_indexes,
fill_multiple_unique_constraint e _relation_info_from_joiner.

La proiezione legge package e tabelle dall'albero, con i rispettivi sqlschema
e sqlname. Proietta solo colonne fisiche, espande le chiavi composite già
costruite e conserva indici, UNIQUE, CHECK ed estensioni già dichiarati.
Gli endpoint delle FK provengono dal ramo globale relations, solo nel verso O
con foreignkey=True; i dettagli SQL della dichiarazione sono letti dal relativo
oggetto figlio. Inverse e virtualRelation GEP non generano FK fisiche.

Il risultato intermedio è il SqlBuilder fisico già usato dal renderer migration,
non un secondo modello semantico. SqlMigrationRenderer e StructureValidator
rimangono responsabili del formato structure-1.0, dei nomi dei vincoli e della
normalizzazione finale. Non si costruisce un ResolvedModel.

Le regole di storage delle colonne sono condivise con la proiezione precedente:
X/Z/P → T, dimensioni min:max normalizzate a 0:max, A di lunghezza fissa → C,
precisione numerica senza scala → precisione,0. Sono riusati anche i rifiuti
delle conversioni di tipo o degli attributi importati che perderebbero semantica.
Gli oggetti mantengono i propri tipi logici e attributi originali.

Gli indici strutturali automatici su PK o colonne già UNIQUE non producono
indici ridondanti. Gli altri indici usano nomi e opzioni già presenti nel
contratto migration. Il rimando alla source di un indice è usato soltanto per
distinguere un nodo dichiarato da un indice generato; non se ne leggono attributi
né si rivisita la source. Restano i rifiuti esistenti di CHECK/indici parziali
con colonne rimappate, senza introdurre riscritture di espressioni SQL.

Nessuna riespansione delle options, analisi delle formule, chiamata al compilatore,
lettura di sorgenti legacy o apertura di connessioni durante la proiezione.

## Confronto completo

| Package | Tabelle | Colonne fisiche | FK | Indici |
| --- | ---: | ---: | ---: | ---: |
| sys | 16 | 188 | 7 | 56 |
| adm | 40 | 412 | 32 | 150 |
| invc | 18 | 189 | 19 | 76 |
| Totale | **74** | **789** | **58** | **282** |

Ogni tabella è confrontata separatamente; una prova confronta anche il JSON
completo, inclusi radice, schemi, estensioni e membership. Nessun attributo,
nome di vincolo o indice viene eliminato per ottenere l'uguaglianza. I JSON
di riferimento non sono stati modificati. **Nessuna nuova divergenza emersa
su test_invoice_pg da sottoporre a decisione.** Restano le esclusioni storiche
documentate nel [rapporto 53](53-native-invoice-render-and-migration.md).

Le prove bloccano resolve_model, QueryCompiler, il bridge legacy, l'apertura
degli oracoli e le connessioni. Dopo il render bloccano anche prepare_source,
expand_options e la ricostruzione del builder effettivo. Verificano che:

- la proiezione non modifichi attributi, colonne o joiner;
- modificare la source originale non cambi gli oggetti già costruiti;
- scollegare il riferimento model.src non impedisca la proiezione;
- collegare SqlDatabase non cambi il risultato;
- una modifica all'oggetto colonna venga riflessa nel JSON successivo.

Una configurazione ridotta verifica nomi SQL rimappati, schemi dedotti dai
package, override verso uno schema dichiarato, PK/FK composite, UNIQUE,
indici ordinati, deferred, azioni SQL ed estensioni.

## Verifica PostgreSQL e confini

Il test usa esclusivamente il database temporaneo della fixture test_asqueel_*:
applicazione del JSON, introspezione di 74 tabelle/789 colonne e seconda diff
vuota. Poi modifica full_update, dimensione di una colonna, UNIQUE, FK e indice
nella source nativa; ricostruisce l'albero, applica il nuovo JSON e ottiene
nuovamente una diff vuota. Il database applicativo test_invoice_pg non viene usato.

La proiezione non abilita compilazione o scritture applicative sul nuovo albero.
Mixin, RuntimeModel e raccordo del compilatore restano separati. Nessun cambio
di renderer predefinito, release, commit o push in questo incremento.

## Risultati riproducibili

**78 test dedicati superati**; suite completa **2.300 superati, 13 saltati**,
incluse le integrazioni PostgreSQL/SQLite. Ruff superato sui file Python
interessati, mypy superato sui 56 file sorgenti. Il diff del compilatore è
identico a quello salvato prima del lavoro.

[Comandi, membership e hash del confronto](evidence/hierarchical-migration/verification.json),
[test dedicati](evidence/hierarchical-migration/targeted.log),
[suite completa](evidence/hierarchical-migration/suite.log).
