API native
==========

Riferimento estratto dal codice. Le dipendenze PostgreSQL e migration restano
opzionali: questa pagina documenta il nucleo senza aprire connessioni.

Compiler
--------

.. automodule:: genro_sql.compiler
   :members: QueryCompiler, PostgresCompiler

Runtime sincrono
----------------

.. automodule:: genro_sql.runtime
   :members: Database, PostgresDatabase, Transaction, DatabaseClosedError, TransactionStateError

Ambiente
--------

.. automodule:: genro_sql.environment
   :members: SqlEnvironment

Modello e contratti
-------------------

.. automodule:: genro_sql.model
   :members: resolve_model

.. automodule:: genro_sql.contracts
   :members: Column, Relation, Table, ResolvedModel, PartitionScope, RowPolicies, CompiledQuery, QueryResult, ResultColumn, EnvironmentMismatchError
