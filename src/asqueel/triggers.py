"""Application write-trigger call chains."""
from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
from typing import Any, Iterator


@dataclass(slots=True)
class TriggerStackItem:
    """One application write and its causal parent."""

    event: str
    table: str
    record: dict[str, Any] | None = None
    old_record: dict[str, Any] | None = None
    parent: TriggerStackItem | None = None
    level: int = 0


class TriggerStack:
    """Track nested insert/update/delete operations on the owning thread."""

    def __init__(self) -> None:
        self.stack: list[TriggerStackItem] = []

    def __len__(self) -> int:
        return len(self.stack)

    @property
    def parentItem(self) -> TriggerStackItem | None:
        """Legacy-compatible name for the current stack item."""
        return self.stack[-1] if self.stack else None

    def item(self, index: int) -> TriggerStackItem | None:
        try:
            return self.stack[index]
        except IndexError:
            return None

    @contextmanager
    def operation(self, event: str, table: str, record=None, old_record=None
                  ) -> Iterator[TriggerStackItem]:
        parent = self.parentItem
        item = TriggerStackItem(
            event=event,
            table=table,
            record=record,
            old_record=old_record,
            parent=parent,
            level=len(self.stack),
        )
        self.stack.append(item)
        try:
            yield item
        finally:
            popped = self.stack.pop()
            if popped is not item:  # pragma: no cover - defensive invariant
                raise RuntimeError('Trigger stack was modified out of order')
