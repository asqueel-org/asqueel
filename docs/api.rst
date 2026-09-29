API reference
=============

The reference below is generated from the public Python interfaces. PostgreSQL
and migration dependencies are optional; importing the core does not connect
to a database.

Application configuration and objects
-------------------------------------

.. automodule:: genro_sql.configuration
   :members: SqlDatabaseConfig, ConfigurationView, build_database

.. automodule:: genro_sql.application
   :members: SqlDatabase

.. automodule:: genro_sql.application_table
   :members: SqlTable, SqlColumn, SqlRelation, SqlQuery, SqlRecord, RecordNotFoundError, RecordMultipleRowsError

Compiler
--------

.. automodule:: genro_sql.compiler
   :members: QueryCompiler, PostgresCompiler

Synchronous runtime
-------------------

.. automodule:: genro_sql.runtime
   :members: Database, PostgresDatabase, Transaction, DatabaseClosedError, TransactionStateError

Environment
-----------

.. automodule:: genro_sql.environment
   :members: SqlEnvironment

Model and query contracts
-------------------------

.. automodule:: genro_sql.model
   :members: resolve_model

.. automodule:: genro_sql.contracts
   :members: Column, Relation, Table, ResolvedModel, PartitionScope, RowPolicies, CompiledQuery, QueryResult, ResultColumn, EnvironmentMismatchError

Database inspection
-------------------

.. automodule:: genro_sql.importers
   :members: inspect_postgres, ImportResult

.. automodule:: genro_sql.projection
   :members: to_physical_builder
