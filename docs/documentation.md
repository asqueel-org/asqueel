# Compilare e pubblicare la documentazione

La configurazione deriva da `kajenn/kajenn`: Sphinx, tema Read the Docs,
MyST per Markdown, autodoc, Napoleon, type hints, intersphinx e Mermaid.
Il CSS di leggibilità è condiviso con quell'impostazione; identità e indice
sono specifici di genro-sql.

## Build locale

Dalla radice del repository, in un ambiente virtuale dedicato:

```sh
python -m pip install -e ".[docs]"
python -m sphinx -W --keep-going -b html docs docs/_build/html
```

Aprire `docs/_build/html/index.html`. La build tratta i warning come errori.
Le guide Markdown esistenti restano la fonte; `index.rst` ne definisce la
navigazione e `api.rst` estrae il riferimento dal codice. Non serve un database.

## Read the Docs

`.readthedocs.yaml` usa Ubuntu 24.04, Python 3.12, l'extra `docs` e
`docs/conf.py`, con `fail_on_warning: true`. Per la pubblicazione occorre
importare il repository nel progetto Read the Docs, autorizzare l'integrazione
GitHub e abilitare il branch/versione desiderato. Il file di configurazione
nel repository non crea automaticamente il progetto o il webhook sul servizio.

La CI GitHub esegue inoltre la stessa build Sphinx a ogni push e pull request.

## Esempi verificabili

Il tutorial pubblico include porzioni di `guide/_examples/shop_tutorial.py` con
`literalinclude`: codice mostrato e file scaricabile provengono dalla stessa fonte.
I test in `tests/documentation/test_examples.py` eseguono il tutorial, il quickstart,
le query e gli esempi di environment su PostgreSQL, oltre agli esempi offline e
alla verifica sintattica dei frammenti Python delle guide. Usano schemi temporanei.

```sh
GNR_TEST_PG_PORT=5432 python -m pytest tests/documentation tests/test_wf_phase8_doc.py
```

In alternativa impostare `GENRO_SQL_TEST_DSN` per il database di test. Le nuove
pagine pubbliche vanno in `docs/guide/` e nel toctree di `index.rst`; mantenere le
note interne fuori dall'indice pubblico. Le guide utente restano in inglese.
