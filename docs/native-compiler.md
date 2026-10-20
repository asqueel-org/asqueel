# Compilatore nativo

Il percorso unico è descritto nella [guida al compilatore](guide/compiler.md).
`QueryCompiler` compila il modello gerarchico; `PostgresCompiler` seleziona gli
adapter PostgreSQL per lo stesso algoritmo. SQL e kwargs rimangono separati.

Il precedente compilatore a QueryPlan/Fragment, lo scanner e i metodi DML del
compilatore sono stati rimossi. Le descrizioni dei profili precedenti nei
rapporti di design sono documentazione storica.
