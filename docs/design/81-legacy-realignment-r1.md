# 81 — R1: risoluzione legacy sulla SELECT fisica gerarchica

14 ottobre 2026. **R1 completata.** Il nucleo del compilatore sul nuovo albero
raccoglie i riferimenti, li risolve una volta per campo distinto e li sostituisce
seguendo gli algoritmi GenroPy. Non usa più lo scanner precedente per questi
passaggi. Il [piano 79](79-legacy-compiler-realignment-plan.md) applica il legacy
come specifica: le aggiunte non concordate non sono una coda di nuove decisioni.

Il risultato resta SQL e kwargs, senza esecuzione. Il percorso precedente resta
disponibile; renderer predefinito, modello, scritture e RuntimeModel non cambiano.
R2–R5 rimangono aperte: questo risultato non certifica l'intero compilatore.

## Provenienza degli algoritmi

Riferimento: GenroPy `fa35e5adfa6ad1b269f3a22a9b12c4c1ee6513ea`.
Gli altri sette snapshot del confronto 78 sono verifiche ulteriori, non una
specifica alternativa. Le impronte originali restano negli
[anchor R0](evidence/legacy-realignment-r0/algorithm-anchors.json).

| Algoritmo legacy | Raccordo | Verifica |
| --- | --- | --- |
| `SqlQueryCompiler.updateFieldDict` | Stesse regex, mappa dei riferimenti locali e appiattimento dei percorsi `@` in `FieldReferences.discover` | Confronto con il metodo originale negli otto snapshot |
| Ciclo `colPars` in `compiledQuery` | `FieldReferences.resolve`: risoluzione distinta e ciclo sui riferimenti aggiunti durante l'espansione | 100 occorrenze risolte una volta per campo; nuova compilazione con stato nuovo; dipendenze introdotte durante la risoluzione |
| `getFieldAlias`, ramo fisico | Accesso al `DbColumnObj` effettivo, nomi SQL e quoting delegato all'adapter | 74 modelli nativi per due dialetti; nessuna conversione a ResolvedModel |
| `gnrstring.templateReplace` / `conditionalTemplate` | Ramo SQL con dizionario di stringhe risolte: shortcut della mappa vuota, `${...}`, `$$`, safe per columns e strict per clausole | Valori e classi di errore confrontati con gli originali |
| `gnrstring.split`, normalizzazione columns, `colToAs` | Stessa scansione di parentesi/quadre/virgolette, normalizzazione legacy, alias impliciti e ultima proiezione per AS duplicato | Oracle legacy e casi eseguiti SQLite |

Le utilità di testo sono isolate in `src/asqueel/_legacy_sql.py`; la navigazione
del modello rimane in `object_tree_compiler.py`. Toolbox ha `smartsplit` per
separatori con escape, ma non l'equivalente di questi contratti: non è stato
usato come sostituto. Non sono state portate le parti Bag/localizzazione del
templating, estranee al dizionario di stringhe SQL qui risolte.

## Correzioni e responsabilità

- Riferimenti logici `$campo` e `@relazione.campo`, senza interpretazione di
  `$"nome"`. Come nel legacy, il testo non riconosciuto può rimanere nel SQL:
  compilare non significa validare o eseguire un SQL corretto.
- Sostituzioni dei campi anche in stringhe e commenti secondo il legacy;
  eliminate dal nucleo le protezioni non concordate dello scanner precedente.
- Nessun riconoscimento aggiuntivo di `As` misto; il legacy normalizza `as`.
  Nessuna correzione automatica del SQL invalido con AS ripetuto.
- Mappa per singola SELECT, senza cache o stato SQL sul modello. Il ciclo per
  nuovi riferimenti è presente; non abilita anticipatamente formule o JOIN.
- Assemblaggio tramite adapter, poi `prepare_sql` una sola volta. I parametri
  non vengono prima manglizzati nel nucleo e poi preparati una seconda volta.
  Lo snapshot di ambiente è quello della pianificazione.
- Il formatter restituisce anche i nomi degli input utilizzati, necessari a
  conservare la verifica dei kwargs dopo la delega. `prepare_sql` appartiene
  al protocollo del formatter, disponibile senza connessione.

Il test delle 74 tabelle costruiva esso stesso riferimenti `$"nome"`: ora usa
`$nome`. La prova del quoting fisico usa invece un nome logico ordinario con un
`sqlname` contenente virgolette, responsabilità già prevista dell'adapter.
I test di protezione dei letterali sono sostituiti da aspettative legacy,
comprese le eccezioni per campi sconosciuti. Nessun xfail aggiunto per nascondere
queste differenze. I test del precedente percorso restano disponibili.

## Verifiche e limiti delle prove

| Verifica | Risultato |
| --- | --- |
| Suite completa Asqueel, inclusi i test PostgreSQL locali | **3.681 superati, 13 saltati** |
| Helper di testo contro le funzioni originali | **1.323 confronti per snapshot × 8 = 10.584, zero differenze** |
| SELECT delle colonne fisiche dei 74 modelli nativi, PostgreSQL e SQLite | **148 confronti SQL e nomi delle colonne, zero differenze** |
| Casi mirati di espressioni e binding contro il compilatore legacy reale | **47 compilazioni comparate** |
| Sottoinsieme eseguito su SQLite in memoria | **23 casi, stessi risultati e nomi delle colonne** |
| Lint dei nove file Python aggiunti/modificati in R1 | Superato |

I 148 confronti disattivano esplicitamente i filtri impliciti, omettono l'aggiunta
automatica della pkey legacy e selezionano tutte le colonne fisiche. Normalizzano
solo spaziatura e quoting dell'alias radice `AS t0` / `AS "t0"`. Non attestano
formule, relazioni o options di lettura sul nuovo albero.

Le 47 prove mirate non sono l'intero corpus dei 71 casi del rapporto 78. La parte
PostgreSQL di questa sonda è di sola compilazione; la suite Asqueel comprende
separatamente le integrazioni PostgreSQL già esistenti. I 10.584 confronti
misurano gli helper, non diecimila query né otto suite GenroPy complete.

L'oracle portabile `tests/oracles/legacy_sql_text.json` è stato prodotto dalle
funzioni originali del riferimento, non dai risultati Asqueel. In CI i test
non richiedono i checkout locali GenroPy né rigenerano l'oracle.

Le prime esecuzioni senza accesso alla porta PostgreSQL hanno errori di permesso
del sandbox, conservati nei log intermedi. La verifica completa finale è stata
eseguita con accesso autorizzato al database locale e termina senza errori.

## Costi misurati

Ripetuto il benchmark del rapporto 78: query nuove, stessi workload, nove round
da cento compilazioni, senza esecuzione. Mediane in microsecondi:

| Dialetto / caso | Legacy | Percorso precedente | Nuovo albero R1 |
| --- | ---: | ---: | ---: |
| SQLite, SELECT ordinaria | 864,8 | 296,3 | 238,3 |
| SQLite, un riferimento | 496,5 | 147,5 | 161,8 |
| SQLite, 100 riferimenti ripetuti | 912,1 | 2.325,4 | 1.480,1 |
| SQLite, 20 CASE | 738,5 | 2.560,8 | 1.114,6 |
| PostgreSQL, SELECT ordinaria | 863,1 | 294,3 | 232,4 |
| PostgreSQL, un riferimento | 483,5 | 145,2 | 159,0 |
| PostgreSQL, 100 riferimenti ripetuti | 796,2 | 2.359,3 | 1.481,9 |
| PostgreSQL, 20 CASE | 685,4 | 2.659,8 | 1.140,3 |

La risoluzione distinta recupera l'algoritmo legacy: non è una nuova cache.
Il nuovo albero riduce il costo rispetto al precedente sui casi ripetuti, ma
resta più lento del legacy su 100 riferimenti e 20 CASE. Non è dimostrata una
superiorità generale. I tempi assoluti differiscono dalla sessione del rapporto
78: non attribuire tale variazione a R1. La pipeline residua degli adapter va
ancora raccordata e profilata in R3/R4; il gate prestazionale R4 resta aperto.

Il file `scanner-benchmark/results.json` conserva anche la ripetizione del
confronto precedente legacy/scanner: **non** rappresenta 132 prove sul nuovo
albero. Le prove nuove sul nuovo albero sono in `select-cases.json` e
`native-selects.json`; il benchmark include invece tutti e tre i percorsi.

## Cosa resta

- **R2:** `embedFieldPars`, convenzioni dei parametri e completamento delle
  proiezioni. In particolare AS interno senza alias esterno, per esempio CAST,
  ha ancora il limite esplicito del raccordo dei metadati. Split, alias impliciti
  e AS duplicati sono stati anticipati in R1 perché necessari a togliere il
  vecchio scanner dalla risoluzione.
- **R3:** gli adapter attuali usano ancora il tokenizer nella preparazione.
  Restano da raccordare escape dei valori, nomi Unicode, percentuali,
  `REGEXP`/`ILIKE` e casi di collection/binding secondo il legacy. La delega
  una sola volta è verificata; la parità completa della preparazione non lo è.
- **R4:** corpus integrato dopo R2/R3 e analisi dei costi residui prima delle JOIN.
- **R5:** relations, formule, sottoquery, options, `*` e macro sul nuovo albero.
  Nessun avvio anticipato; alias delle tabelle separati dai mangler dei parametri.

Non ci sono nuove decisioni richieste per R1. Query concatenate, operatori,
mixin e RuntimeModel rimangono nel perimetro già concordato, senza estensioni.

## Riproducibilità

- [Sonda helper](probes/compare_legacy_r1_text.py): import effettivo delle funzioni
  di ciascuno snapshot; esiti `text-*.json` nella cartella delle evidenze.
- [Sonda SELECT](probes/verify_legacy_r1_select.py): modelli nativi e casi mirati.
- [Riepilogo SELECT](evidence/legacy-realignment-r1/select-summary.json).
- [Benchmark completo](evidence/legacy-realignment-r1/scanner-benchmark/benchmark.json).
- [Verifica e impronte](evidence/legacy-realignment-r1/verification.json).
- [Suite finale](evidence/legacy-realignment-r1/full-tests-final.log).

Comando della suite dalla radice del repository:

```sh
PYTHONPATH=src:../asqueel-migration/src venv/bin/python -m pytest -q -o addopts=''
```

Le evidenze R0 sono conservate. Le impronte prima/dopo isolano R1 rispetto alle
molte modifiche già presenti nel working tree: non viene attribuito a questo
passo tutto il diff Git accumulato. Nessun commit o push in questo passo.
