# 67 — Riferimenti stringa ai metodi subquery_*

14 ottobre 2026. Raccordo delle forme già dichiarate dalla grammatica:
`select='nome'`, `exists='nome'`, `select_<alias>='nome'` e
`subQueryColumn(query='nome')` semplice/JSON. Nessuna nuova firma o registro.
Query concatenate e operatori restano rinviati secondo R-09.

## Algoritmo legacy e confronto dei branch

Il riferimento `fa35e5a`, in `gnrsqldata/compiler.py:406–420`, chiama
`getattr(self.tblobj.dbtable, 'subquery_' + nome)()` quando la dichiarazione è
una stringa. Copia il risultato, poi percorre la normale compilazione della
sottoquery. Non passa argomenti al metodo e non interpreta il nome come SQL.

La tabella della chiamata è **la root della SELECT corrente**, anche quando
la formula è raggiunta tramite una relazione. Una SELECT figlia ha la propria
root. Non è la stessa regola di `sql_formula_<nome>(attr)`, che viene cercato
sulla tabella proprietaria della formula. Non si aggiunge un fallback implicito.

Tutti gli otto riferimenti mantengono questo dispatch. Il preprocessamento dei
refactor v2/v3/v3_merged/v4 tenta però di aggiungere `exists=True` alla stringa,
prima di risolverla, e fallisce. Si mantiene il percorso funzionante del legacy
corrente, presente anche in next e compound, senza importare JOIN/LATERAL o
normalizzazioni sperimentali. Hash, commit e righe delle funzioni sono nel
[confronto riproducibile](evidence/native-subquery-methods/legacy-comparison.json).

Un limite distinto riguarda XML: il costruttore legacy `subQueryColumn`
(`gnrsqlmodel/model.py:1221`) legge immediatamente `query['columns']` per costruire
XMLFOREST. Una stringa non è supportata. Asqueel conserva la dichiarazione ma
la rifiuta esplicitamente alla compilazione; non abilita una nuova variante.
La forma XML con dict resta funzionante come nel rapporto 66.

## Raccordo implementato

Il render conserva i riferimenti; anche l'ingresso tramite schema li rinvia
alla compilazione, mantenendo la validazione strutturale delle formule.
`_subquery_definition` conserva una stringa non vuota. La cache delle formule
conserva questa dichiarazione, non il risultato del metodo.

`_Context.subquery` risolve il metodo sulla tabella della SELECT corrente,
richiede un mapping e ne acquisisce una copia prima di validarlo con il percorso
esistente. Clausole, correlazione, policy, cast, dialetto e mangler non hanno
un secondo algoritmo. Liste e mapping restituiti dall'applicazione non vengono
modificati; il nome del metodo non viene risolto ricorsivamente se il risultato
è un'altra stringa.

I metodi sono valutati quando l'espressione viene compilata, anche più volte
nella stessa compilazione come nel legacy. Ogni compilazione successiva li
rivaluta. Non vengono eseguiti dal render né memorizzati nella colonna.
Un metodo SQL può impostare `select_*='nome'` nella propria copia degli attributi:
il riferimento segue poi le stesse regole. I parametri locali non catturano
quelli delle altre formule, sottoquery o del chiamante.

Metodo mancante, risultato non mapping, mapping incompleto e compilatore senza
tabella applicativa producono errori espliciti. Le eccezioni applicative non
sono nascoste. Come per `sql_formula_*`, i metodi sono codice Python fidato e
devono costruire dichiarazioni senza I/O; non viene introdotta una sandbox.

## RuntimeModel

Riesaminati `gnrsql/runtime_model.py` e i relativi test del branch v4: overlay
temporaneo di colonne/relazioni, visibilità nel blocco, ripristino e riuso.
La risoluzione dei metodi resta sulla tabella applicativa; non appartiene
all'overlay delle colonne. Nessuna API RuntimeModel è introdotta in questo passo.

La prova sul modello effettivo sostituisce una dichiarazione risolta e verifica
che la compilazione successiva usi il nuovo riferimento, senza una cache del
risultato precedente. Sono verificati anche ambiente temporaneo, riuso e due
thread sulla stessa query. Queste prove non certificano un RuntimeModel completo.
Il suo futuro raccordo dovrà esporre lo stesso modello effettivo al compilatore
e alla tabella vista dal metodo, soprattutto se quest'ultimo legge `self.model`.
Cambiare soltanto `compiler.model` non risolve quel requisito.

## Test: provenienza ed esiti

La ricerca testuale e AST nelle suite `gnrpy/tests` e `projects/*/tests` degli
otto snapshot non ha trovato test dedicati che dichiarino metodi `subquery_*`
o riferimenti stringa nelle formule. Il
[censimento](evidence/native-subquery-methods/test-inventory.json) registra file
esaminati e risultati. Non si dichiarano portati test storici inesistenti.

Sono state create **sette prove di contratto**, eseguite con gli stessi corpi
sui compilatori originali e su Asqueel: select/named, exists, tabella correlata,
SELECT figlia, riferimento prodotto da sql_formula e subQueryColumn semplice/JSON.
La sola compilazione legacy usa SQLite in memoria e non esegue il SQL prodotto.
Le prove sui valori e le capacità effettive dei dialetti sono separate.

| Riferimento | Prove superate | Differenze osservate |
| --- | --- | --- |
| legacy, next, compound | 7/7 ciascuno | Dispatch e lookup confermati |
| v2, v3, v3_merged, v4 | 6/7 ciascuno | `exists='nome'` fallisce nel preprocessamento |
| simplify | 0/7 | Le virtuali vengono trattate come colonne fisiche; i metodi non sono chiamati |

In Asqueel:

- **44 test di compilazione**, incluse le sette prove su ciascun dialetto:
  nessun I/O dei driver, scope e mangler distinti, mapping non mutati,
  ambiente/thread, riuso, alias, errori, cicli, ingresso tramite schema,
  sostituzione della dichiarazione e limite XML esplicito;
- **6 test sui risultati PostgreSQL/SQLite**, in schemi temporanei: valori
  scalari, EXISTS, sottoquery nominate, correlazione dopo JOIN e annidamento,
  JSON con DISTINCT su PostgreSQL, assenza di righe, riuso e isolamento dei
  parametri. SQLite rifiuta esplicitamente la forma JSON;
- test del modello aggiornati: conservazione dei tre riferimenti
  select/exists/select_* senza esecuzione e rifiuto dei riferimenti vuoti.

Suite completa: **1922 superati, 13 saltati**. Ruff, mypy e Sphinx strict superati;
esiti nel [riepilogo](evidence/native-subquery-methods/verification.json).
I 74 modelli nativi non sono cambiati; il lavoro aggiunge la risoluzione
dei riferimenti stringa, non modifica le formule di test_invoice_pg.

Riproduzione del confronto, con gli snapshot e l'ambiente del rapporto 59:

```sh
venv/bin/python docs/design/probes/replay_subquery_methods.py \
  --snapshots /tmp/asqueel-formula-baseline
```

Il probe estrae i corpi dai test Asqueel, li esegue senza modificare il legacy
e salva log, XML, commit e hash degli algoritmi nella cartella delle evidenze.
