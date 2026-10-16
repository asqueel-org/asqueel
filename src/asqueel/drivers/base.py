"""No database package is required to import these protocols."""
from typing import Any, Protocol, Mapping

from ..contracts import CompiledQuery, QueryResult


class BindingFormatter(Protocol):
    dialect: str
    binding: str


    def prepare_sql(self, sql: str, sqlargs: Mapping[str, Any] | None,
                    snapshot: Mapping[str, Any]) -> CompiledQuery: ...


class SyncDriver(BindingFormatter, Protocol):
    def validate(self, query: CompiledQuery) -> None: ...

    def connect(self, conninfo: str, **kwargs: Any) -> Any: ...

    def execute(self, connection: Any, query: CompiledQuery) -> QueryResult: ...

    def executemany(self, connection: Any, query: CompiledQuery,
                    params_seq: Any) -> QueryResult: ...

    def commit(self, connection: Any) -> None: ...

    def rollback(self, connection: Any) -> None: ...

    def close(self, connection: Any) -> None: ...
