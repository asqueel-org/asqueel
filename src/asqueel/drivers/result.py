"""Common row materialization for DB-API drivers, following the legacy index."""
from genro_toolbox import NamedList

from ..contracts import QueryResult, ResultColumn


def query_result(columns, names, cursor) -> QueryResult:
    """One column index per result set, shared by its mutable rows."""
    if names is None:
        if columns:
            raise ValueError('Compiled result columns supplied for a statement without a result set')
        return QueryResult([], cursor.rowcount, columns)
    if len(set(names)) != len(names):
        raise ValueError('Result columns must have unique names; use explicit aliases')
    if columns and [column.name for column in columns] != names:
        raise ValueError('Compiled result columns do not match cursor column names and order')
    index = {name: position for position, name in enumerate(names)}
    rows = [NamedList(index, row) for row in cursor.fetchall()]
    return QueryResult(rows, cursor.rowcount, columns or tuple(ResultColumn(name) for name in names))
