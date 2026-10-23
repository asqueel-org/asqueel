API reference
=============

The reference below is generated from the public Python interfaces. PostgreSQL
and migration dependencies are optional; importing the core does not connect
to a database.

Application configuration and objects
-------------------------------------

.. automodule:: asqueel.configuration
   :members: SqlDatabaseConfig

.. automodule:: asqueel.application
   :members: AsqueelDb

.. automodule:: asqueel.application_table
   :members: SqlTable, SqlQuery, RecordNotFoundError, RecordMultipleRowsError

Compiler
--------

.. automodule:: asqueel.compiler
   :members: QueryCompiler

Synchronous runtime
-------------------

.. automodule:: asqueel.runtime
   :members: SqlCursor, session, TransactionStateError

Model and query contracts
-------------------------

.. automodule:: asqueel.contracts
   :members: RowPolicies, CompiledQuery, ResultColumn

Hierarchical model
------------------

.. automodule:: asqueel.object_tree
   :members: DbModel, DbModelObj, DbTableObj, DbColumnObj
