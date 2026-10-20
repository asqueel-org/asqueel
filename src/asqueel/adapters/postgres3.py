"""The legacy name ``postgres3``: the same psycopg 3 adapter as ``postgres``."""
from .postgres import SqlDbAdapter

__all__ = ['SqlDbAdapter']
