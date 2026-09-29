Genro SQL
=========

Modello SQL dichiarativo, compiler PostgreSQL e runtime sincrono per applicazioni
Genro nuove. Lo stato corrente è alpha; la compatibilità completa con le
applicazioni legacy resta un obiettivo successivo.

Le guide native descrivono il codice disponibile. I dossier di analisi e le
specifiche legacy distinguono comportamento storico e obiettivi futuri.
Il runtime corrente è **sincrono**, sul thread chiamante.

.. toctree::
   :maxdepth: 2
   :caption: Guida al nucleo nativo

   native-model
   native-composition
   native-compiler
   native-runtime
   sql-environment
   row-policies
   grammar

.. toctree::
   :maxdepth: 2
   :caption: Adapter e API

   data-dialects
   data-driver
   api

.. toctree::
   :maxdepth: 1
   :caption: Stato e verifiche

   synchronous-policies-delivery
   data-adapters-delivery
   native-v1-delivery
   delivery
   ecosystem-alignment
   documentation

.. toctree::
   :maxdepth: 1
   :caption: Analisi e progetto
   :glob:

   genro-sql-target-architecture
   legacy-sql-compiler-analysis
   compiler/*
   design/README
   design/0*

Indici
======

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`
