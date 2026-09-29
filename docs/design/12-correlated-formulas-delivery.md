# 12 — Formule correlate select/exists guidate dal legacy

Incremento successivo ad [aliasColumn](11-alias-columns-delivery.md), senza
commit automatici. Le constatazioni del riesame 10 restano una fotografia della
baseline b023a9b; qui si registrano i requisiti recuperati e i limiti residui.

## Semantica recuperata

La sorgente primaria è `gnrsqldata/compiler.py:390` e seguenti del legacy
fa35e5adfa6ad1b269f3a22a9b12c4c1ee6513ea: formula select/exists, select_nome,
#THIS, cast, default delle sottoquery e compilazione nel contesto proprietario.
Sono state consultate anche dichiarazioni reali di `sys.task`, `adm.user`,
`adm.group` e `adm.notification`.

Implementati:

- `formulaColumn(select=dict(table=..., where=..., columns=...))` scalare;
- `formulaColumn(exists=dict(...))`, con proiezione costante di default;
- `sql_formula` con sottoquery nominate `select_nome`/`#nome`;
- `#THIS.field` e percorsi correlati, riferiti alla tabella/alias proprietari
  della formula, anche quando raggiunti attraverso una relazione;
- formule dentro formule, alias verso formule e cicli diagnosticati;
- espressioni aggregate senza AS dentro la sottoquery, come negli esempi legacy;
- order_by/limit/offset espliciti, cast scalari e cardinalità PostgreSQL;
- scope separati per alias SQL e parametri locali, con binding finale unico;
- dipendenze dell'ambiente propagate dalle sottoquery alla query esterna;
- segnaposto riconosciuti solo nel codice SQL, mai nei commenti o letterali.

La scalarità richiede una sola colonna ma non impone una sola riga tramite LIMIT:
più righe producono l'errore del database. Una query con due aggregati correlati
non viene trasformata in JOIN many che moltiplicano le righe esterne.

Il dialect rende ciascuna sottoquery in parti SQL/Parameter; il formatter del
driver interviene una volta sola sulla query finale. `plan_select` può quindi
rendere i piani figli pur lasciando la query radice ancora come QueryPlan.
Non si incorpora SQL già preparato per psycopg né si interpolano valori.

## Differenze volute e limiti

I default legacy interni `excludeDraft=False` e `excludeLogicalDeleted=False`
sono mantenuti. Il bypass implicito legacy `ignorePartition=True` **non** viene
copiato: prevale la semantica esplicita concordata dall'utente. Senza un contesto
richiesto si produce errore; il bypass richiede `ignorePartition=True` nella
definizione. Le opzioni non sono ereditate silenziosamente dalla query esterna.

`subtable='*'`, `addPkeyColumn=False`, `ignoreTableOrderBy=True` sono accettati
come valori di compatibilità. Non implementano altre forme di subtable o i
relativi automatismi legacy. Restano rifiutati GROUP BY/HAVING/DISTINCT nelle
sottoquery fino all'implementazione dei rispettivi contratti.

Callback `sql_formula=True`, provider `subquery_*`, varianti/var_*, pyColumn,
subQueryColumn raccolte, virtualRelation e altre macro non sono consegnati.
Combinazioni ambigue di sql_formula/select/exists sono errori espliciti, anche
per i descriptor costruiti manualmente. Cast in EXISTS viene rifiutato.

Il nuovo `RETURNING '*'` include **solo colonne fisiche**, superando il limite
annotato nel documento 11: aggiungere una formula, anche con dipendenze indirette
verso una sottoquery, non deve rompere CRUD. Formule SQL semplici sono ancora
restituibili esplicitamente; sottoquery strutturate in DML restano fuori profilo.
Anche i mapping di scrittura devono contenere solo dati scrivibili: non viene
emulata la rimozione silenziosa delle virtuali fatta da alcuni adapter legacy.

## Regressioni trovate durante la revisione

- Un parametro fornito come keyword alla query e usato solo nella sottoquery
  veniva considerato inutilizzato dopo la rinomina. QueryPlan e CompiledQuery
  ora conservano `input_parameters`, cioè i nomi originali realmente consumati.
  Un override locale non consuma per errore la keyword esterna omonima.
- Dichiarazioni select_nome presenti soltanto dentro commenti/stringhe potevano
  essere accettate e ignorate. Ora falliscono come sottoquery non utilizzate.
- Descriptor manuali con più definizioni eseguibili potevano ignorarne una:
  il compiler ora rifiuta la combinazione.
- RETURNING di default tentava di valutare formule con dipendenze indirette su
  sottoquery. La proiezione predefinita fisica elimina questa dipendenza.

## Evidenze

- `tests/native_model/test_subquery_model.py`: snapshot, grammatica,
  definizioni invalide, alias e mancata eredità delle definizioni operative.
- `tests/native_compiler/test_subqueries.py`: scope, parametri, correlazione,
  macro, policy, cast, opzioni rifiutate e DML.
- `tests/native_compiler/test_subquery_review.py`: regressioni indipendenti per
  dichiarazioni ignorate e descriptor ambigui.
- `tests/application_config/test_formula_bindings.py`: keyword usate nei figli,
  shadowing locale e collisioni con nomi generati.
- `tests/application_integration/test_formula_subqueries.py`: sei prove su
  PostgreSQL reale con risultati, NULL, EXISTS, nested, metadata, policy,
  cardinalità, cast e scritture fisiche.
- `tests/native_model/test_legacy_formula_declarations.py`: estrae quattro
  dizionari select reali da `sys.task` e li compila senza modificarli. Non
  importa il framework e non esegue il compiler legacy: è una prova sulle
  dichiarazioni originali, non un oracle SQL completo. Opzionale senza checkout.

Corrisponde a VIR-05/06/08/10 e a parte di VIR-03/09/11. La differenza partition
è deliberata e documentata; VIR-04/07/12/13/14 e le raccolte restano aperti.

Verifica finale: **510 test superati**, copertura **95%**, Ruff e mypy verdi,
build Sphinx rigorosa e primo esempio della guida eseguito offline. La suite
integra il lavoro sugli alias del precedente incremento. Nessun database
applicativo modificato: PostgreSQL temporaneo e fixture eliminate al termine.
