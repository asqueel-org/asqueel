# 11 — AliasColumn: primo completamento guidato dal legacy

Questo incremento implementa aliasColumn nel percorso operativo, dopo il
[riesame della copertura](10-legacy-coverage-reassessment.md). La matrice 10
fotografa la baseline precedente `b023a9b`: i suoi finding sugli alias e sui
percorsi multi-hop vengono superati nei limiti specificati qui. Gli altri gap
restano aperti.

## Contratto recuperato

Riferimenti legacy: `gnrsqlmodel/table.py:514` (`column`),
`gnrsqlmodel/columns.py:342` (`AliasColumnWrapper`) e
`gnrsqldata/compiler.py` (`getFieldAlias`). Baseline Genropy
`fa35e5adfa6ad1b269f3a22a9b12c4c1ee6513ea`.

L'alias è un tipo di colonna virtuale distinto dalla formula:

- conserva `relation_path`, identità e provenienza della propria dichiarazione;
- risolve la colonna destinazione dopo la costruzione delle relazioni;
- eredita dtype, UI e attributi descrittivi, con override locali non-None;
- mantiene il legame alla destinazione immediata (`alias_target`,
  `SqlColumn.originalColumn`), anche quando questa è un altro alias o una formula;
- si usa come `$alias` in proiezioni, filtri, ordinamento e formule;
- attraversa i percorsi legacy `@a.@b.field` e la forma nativa `@a.b.field`;
- usa LEFT JOIN riutilizzati e conserva il risultato NULL in assenza di una
  riga correlata, indipendentemente dal notnull descrittivo ereditato;
- resta non scrivibile e non viene proiettato come colonna fisica per migration.

I cicli tra alias vengono rilevati in risoluzione; quelli che coinvolgono anche
formule sono rilevati dal compiler. I target mancanti producono errori espliciti.

## Integrazione e confini

La configurazione della colonna alias prova prima il proprio percorso, poi la
configurazione della destinazione. `model.ui` espone l'overlay UI risolto.
Gli snapshot per gli hook update/delete contengono solo colonne fisiche: aggiungere
un alias non introduce JOIN o colonne non scrivibili nella preparazione dei dati.

`RETURNING '*'` esclude gli alias, mantenendo invariato il precedente trattamento
delle formule. Un alias locale esplicito è restituibile; un alias che richiede un
JOIN è rifiutato in DML. SELECT `*` conserva il comportamento nativo precedente:
tutte le colonne risolte, non soltanto le virtuali statiche legacy. Questa
convenzione resta una differenza dichiarata, non viene presentata come equivalenza.

I target locali `name`/`$name` sono una comodità nativa; non se ne dichiara
l'equivalenza con ogni percorso di `DbTableObj.column` legacy. L'identità dell'alias
rimane separata dal target, necessaria per i consumer moderni dei metadati.
Non sono implementati to-many, virtualRelation, formule select/exists, pyColumn
o altri costrutti del riesame.

Durante l'integrazione è stato corretto un difetto dei default di configurazione:
il default fisico `indexed=True` della grammatica relation veniva materializzato
anche su relazioni puramente logiche, rendendole invalide. Ora quel default non
viene materializzato quando foreign_key è falso e indexed non è stato dichiarato.
Un'opzione fisica scritta esplicitamente su una relazione logica resta rifiutata.

## Prove e tracciabilità

- `tests/native_model/test_alias_model.py`: target, metadati/override, catene,
  cicli, errori, separazione dei nomi fisici.
- `tests/native_compiler/test_aliases.py`: risoluzione nello scope proprietario,
  JOIN riutilizzati, formule, clausole, metadata, percorsi a più @, cicli misti,
  vincoli DML/policy.
- `tests/application_integration/test_alias_columns.py`: PostgreSQL reale,
  valori, filtri, ordine, NULL, metadati, oggetti vivi, snapshot hook e DDL.
- `tests/application_integration/test_legacy_alias_oracle.py`: esegue la vera
  classe legacy estratta mediante AST e confronta ereditarietà/override con il
  nuovo resolver. Lo stub sostituisce solo la base di framework e la colonna
  originale: non è una prova dell'intero compiler legacy. Il test è opzionale
  quando il checkout indicato da `GENRO_LEGACY_ROOT` non è disponibile.
- `tests/application_config/test_configuration.py`: ereditarietà della vista
  config e relazione logica senza vincolo fisico.

Corrisponde a VIR-02 e alla parte alias di VIR-19 della specifica esistente;
non chiude l'intera famiglia VIR. Migliora inoltre la navigazione multi-hop,
senza dichiarare coperte tutte le condizioni di JOIN del corpus.

Verifica integrata: **456 test superati**, copertura **95%**, Ruff, mypy e Sphinx
rigoroso superati. Riferimento grammaticale rigenerato. Nessuna modifica o
migrazione a database applicativi: solo fixture PostgreSQL temporanee.
