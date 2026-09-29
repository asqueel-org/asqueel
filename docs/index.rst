Genro SQL
=========

Declare a database configuration and render it into live Python objects. Use
``db.table('sales.customer').query(...).fetch()`` for synchronous PostgreSQL
access. Genro SQL keeps logical table and column names, physical database names,
and UI metadata together in one resolved model.

Start with :doc:`guide/installation` and the runnable :doc:`guide/quickstart`.
If you already have a database, see :doc:`guide/importing`.

The package is **alpha**. PostgreSQL is the supported execution backend.
The runtime runs on the calling thread; it does not provide an async API.
See :doc:`guide/limitations` before choosing features for your application.

.. toctree::
   :maxdepth: 2
   :caption: Getting started

   guide/installation
   guide/quickstart

.. toctree::
   :maxdepth: 2
   :caption: Application development

   guide/configuration
   guide/models
   guide/queries
   guide/transactions
   guide/environment
   guide/row-policies
   guide/importing
   guide/migrations

.. toctree::
   :maxdepth: 2
   :caption: Reference

   guide/adapters
   guide/limitations
   api
   grammar

The grammar reference covers the declarative vocabulary. Not every declaration
has runtime support: the model and query guides describe the supported subset.

Reference indexes
=================

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`
