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
