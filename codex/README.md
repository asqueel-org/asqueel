# Codex dossier — completamento di asqueel

**Data dell'analisi:** 20 agosto 2026
**Perimetro:** grammar SQL, proiezione verso `asqueel-migration`, creazione di
database da ricette Builder e round-trip JSON → Python.

## Scopo

Questa cartella raccoglie il contesto operativo per completare `asqueel`
senza ripartire da zero e senza duplicare responsabilità già implementate in
`genro-builders` o `asqueel-migration`.

La visione da preservare è:

```text
ricetta Python
      ↓
SqlBuilder + grammar documentata
      ↓
source tree semantico unico
      ├──→ modello runtime
      ├──→ DDL per dialetto
      ├──→ documentazione / GUI / introspezione
      └──→ normalized JSON per asqueel-migration
                         ↓
          confronto con il database reale
                         ↓
                  migrazioni SQL
```

Il source tree è il prodotto primario. SQL, JSON e oggetti runtime sono
consumer o rappresentazioni differenti dello stesso modello.

## Documenti

1. [Audit della grammar](01_GRAMMAR_AUDIT.md) — ciò che esiste, ciò che è
   incompleto e le decisioni ancora aperte.
2. [Piano di completamento](02_COMPLETION_PLAN.md) — ordine di implementazione,
   confini fra core portabile e PostgreSQL, criteri di accettazione.
3. [Casi d'uso](03_USE_CASES.md) — ricette Builder per creare ed evolvere un
   database.
4. [Transpiler JSON → Python](04_JSON_TO_PYTHON_TRANSPILER.md) — reader,
   emitter, limiti del round-trip e test.
5. [Mappa della documentazione PostgreSQL](05_POSTGRESQL_REFERENCE_MAP.md) —
   fonti ufficiali da cui derivare firme, enum e vincoli.

## Fonti di verità, in ordine

1. test e codice correnti dei tre repository;
2. contratti versionati, soprattutto
   `asqueel-migration/schemas/structure-1.0.json`;
3. factory e `StructureValidator` di `asqueel-migration`;
4. decisioni approvate in `roadmap/05_grammar_design.md`;
5. inventari legacy `roadmap/01`–`04`;
6. documentazione ufficiale PostgreSQL della versione minima supportata;
7. esempi e documenti in questa cartella.

Se due fonti divergono, non scegliere silenziosamente: aggiungere un test che
esponga la divergenza e registrare la decisione.

## Regole di lavoro per un LLM

- Non generare una seconda grammar parallela: completare `modern/elements.py`.
- Non far dipendere `asqueel-migration` da `asqueel`.
- Il renderer di proiezione vive in `asqueel` e consuma le API pubbliche di
  `asqueel-migration`.
- Non copiare a mano hashing e normalizzazione: usare le factory `new_*_item`.
- Non mescolare attributi fisici e metadati applicativi.
- Non modellare tutta la sintassi PostgreSQL nel core portabile.
- Ogni elemento deve documentare significato, parametri, default, vincoli e
  portabilità.
- Implementare una slice alla volta con test, documentazione ed esempio.
- Il codice prodotto dal transpiler deve essere deterministico, valido e
  semanticamente equivalente; l'eleganza viene dopo la fedeltà.

## Prima consegna consigliata

La prima milestone utile non è un renderer DDL completo. È questa:

```text
SqlBuilder recipe
    → source tree
    → SqlMigrationRenderer
    → normalized JSON valido
    → diff di asqueel-migration
```

Dimostra immediatamente il valore del modello, riusa l'infrastruttura esistente
e consente di creare o allineare database reali a partire da ricette Python.

## Stato corrente — 29 settembre 2026

Questo dossier conserva le analisi precedenti alla pipeline canonica introdotta
nel commit remoto `64e53af`. Per lo stato effettivo dopo l’allineamento vedere
[risultati e limiti verificati](../docs/ecosystem-alignment.md). Non ripristinare
i dialetti legacy/modern descritti dai documenti storici.
