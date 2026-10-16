"""Resolved SELECT clauses, following GenroPy SqlCompiledQuery (fa35e5ad).

SQL clauses are plain strings and joins are an ordered list. The separate
params/result fields carry the existing compile-only contract to preparation;
they never participate in SQL assembly. There is no connection or model here.
"""
from dataclasses import dataclass, field

from .contracts import EnvironmentBinding, ResultColumn


@dataclass
class SqlCompiledQuery:
    maintable: str
    maintable_as: str = 't0'
    columns: str = ''
    distinct: str = ''
    joins: list[str] = field(default_factory=list)
    where: str = ''
    group_by: str = ''
    having: str = ''
    order_by: str = ''
    limit: int | None = None
    offset: int | None = None
    for_update: bool = False
    lock_column: str | None = None
    relationDict: dict[str, str] = field(default_factory=dict)
    aliasDict: dict[str, str] = field(default_factory=dict)
    params: dict = field(default_factory=dict)
    result_columns: tuple[ResultColumn, ...] = ()
    dialect: str = 'postgresql'
    environment: EnvironmentBinding | None = None
    input_parameters: tuple[str, ...] = ()
    local_parameters: tuple[str, ...] = ()

    def get_sqltext(self, adapter):
        """SqlCompiledQuery.get_sqltext: delegate only the resolved clauses."""
        return adapter.compile_sql(**{name: getattr(self, name) for name in (
            'maintable', 'maintable_as', 'columns', 'distinct', 'joins', 'where',
            'group_by', 'having', 'order_by', 'limit', 'offset', 'for_update')})
