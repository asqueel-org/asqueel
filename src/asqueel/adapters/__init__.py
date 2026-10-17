"""Database adapters: one module per implementation, each exposing ``SqlDbAdapter``.

The database loads ``asqueel.adapters.<implementation>``, or the module named
in ``<implementation>:<module>``, and builds ``SqlDbAdapter(db)``, as legacy.
"""
