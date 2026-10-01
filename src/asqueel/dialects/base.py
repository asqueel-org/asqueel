"""Data dialect interface; capability checks describe implemented operations."""
from typing import Iterable, Protocol

from ..query_plan import QueryPlan, SqlStatement


class DataDialect(Protocol):
    name: str
    capabilities: frozenset[str]

    def quote_identifier(self, name: str) -> str: ...

    def tokens(self, expression: str) -> Iterable[tuple[str, str]]: ...

    def empty_collection(self, negated: bool) -> str: ...

    def render(self, plan: QueryPlan) -> SqlStatement: ...
