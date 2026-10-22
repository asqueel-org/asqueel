API reference
=============

The reference below is generated from the public Python interfaces. PostgreSQL
and migration dependencies are optional; importing the core does not connect
to a database.

Application configuration and objects
-------------------------------------

.. automodule:: asqueel.configuration
   :members: SqlDatabaseConfig, build_database

.. automodule:: asqueel.application
   :members: AsqueelDb, SqlDatabase

.. automodule:: asqueel.application_table
   :members: SqlTable, SqlQuery, RecordNotFoundError, RecordMultipleRowsError

Compiler
--------

.. automodule:: asqueel.compiler
   :members: QueryCompiler

Synchronous runtime
-------------------

.. automodule:: asqueel.runtime
   :members: Database, SqlCursor, session, TransactionStateError

Environment
-----------

.. automodule:: asqueel.environment
   :members: SqlEnvironment

Model and query contracts
-------------------------

.. automodule:: asqueel.model
   :members: resolve_model

.. automodule:: asqueel.contracts
   :members: RowPolicies, CompiledQuery, ResultColumn

.. automodule:: asqueel.projection
   :members: to_physical_builder

Hierarchical model
------------------

.. automodule:: asqueel.object_tree
   :members: DbModel, DbModelObj, DbTableObj, DbColumnObj
