# Dialetti dati e driver

Le responsabilità correnti sono nella [guida agli adapter](guide/adapters.md)
e nella [guida al compilatore](guide/compiler.md).

PostgreSQL e SQLite usano un solo compilatore del modello gerarchico.
L'adapter assembla le clausole con `compile_sql`; il driver prepara SQL e kwargs
con `prepare_sql`. Il precedente percorso `render(QueryPlan)` / `prepare(SqlStatement)`
è stato rimosso insieme allo scanner.

L'import di catalogo mantiene il proprio snapshot serializzabile e i controlli
di proiezione fisica. Non è una seconda costruzione degli oggetti vivi.
