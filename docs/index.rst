Asqueel
=========

.. image:: ../assets/asqueel/svg/asqueel-wordmark-primary.svg
   :alt: Asqueel
   :width: 360px

Build a database model from configuration, render it into live Python objects,
and work with PostgreSQL through a synchronous application API:

.. code-block:: python

   rows = db.table('sales.customer').query(
       columns='$id, $name', order_by='$id',
   ).fetch()

The model brings together logical and physical names, relations, computed columns
and UI metadata. The database object owns the environment and transaction session.
Construction never connects or creates tables.

This manual presents the intended delivery contract. Implementation availability
and open decisions are collected in :doc:`guide/limitations`.

Choose your starting point
--------------------------

* **New to Asqueel?** Read :doc:`guide/overview` and :doc:`guide/concepts`, then run the
  :doc:`guide/quickstart` and the step-by-step :doc:`guide/tutorial`.
* **Building an application?** Start with :doc:`guide/configuration` and
  :doc:`guide/models`, then use :doc:`guide/queries` and :doc:`guide/writes`.
* **Already have PostgreSQL tables?** Start with :doc:`guide/importing`.
* **Coming from Genropy legacy?** Read :doc:`guide/legacy` before porting code.
* **Diagnosing unexpected behavior?** See :doc:`guide/troubleshooting`.

.. toctree::
   :maxdepth: 1
   :caption: Learn

   guide/overview
   guide/installation
   guide/concepts
   guide/quickstart
   guide/tutorial

.. toctree::
   :maxdepth: 1
   :caption: Build applications

   guide/configuration
   guide/models
   guide/queries
   guide/writes
   guide/transactions
   guide/hooks
   guide/formulas
   guide/environment
   guide/row-policies

.. toctree::
   :maxdepth: 1
   :caption: Work with existing databases

   guide/importing
   guide/migrations

.. toctree::
   :maxdepth: 1
   :caption: Coming from another data layer

   guide/legacy
   guide/for-sqlalchemy
   guide/for-django
   guide/for-peewee

.. toctree::
   :maxdepth: 1
   :caption: Advanced integration

   guide/configuration-grammars
   guide/compiler
   guide/low-level-runtime
   guide/adapters

.. toctree::
   :maxdepth: 1
   :caption: Look up and troubleshoot

   guide/cheatsheet
   guide/troubleshooting
   api
   grammar

.. toctree::
   :maxdepth: 1
   :caption: Release information

   guide/limitations

The API reference describes Python interfaces. The grammar reference describes
the declarative vocabulary.

Reference indexes
-----------------

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`
