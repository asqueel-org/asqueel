"""Column rules and non-DDL declarations in the model grammar."""
from __future__ import annotations

from typing import Literal
from genro_builders.builder import element


class SemanticElements:
    @element(parent_tags='column', sub_tags='', node_label='validation')
    def validation(self, notnull: bool = False, len: int | str | None = None,
                   min: object = None, max: object = None, regex: str | None = None,
                   email: bool = False, values: list | None = None, nodup: bool = False,
                   exists: str | None = None, messages: dict | None = None):
        ...

    @element(parent_tags='column', sub_tags='', node_label='normalize')
    def normalize(self, case: Literal['upper', 'lower', 'title'] | None = None, trim: bool = False):
        ...

    @element(parent_tags='column', sub_tags='', node_label='encryption')
    def encryption(self, mode: Literal['X', 'R', 'Q'], provider: str | None = None):
        ...

    @element(parent_tags='column, compositeColumn, virtual_columns', sub_tags='')
    def weak_relation(self, to: str, name: str | None = None, inverse: str | None = None,
                      indexed: bool = True, one_one: bool = False, on_delete: str | None = None,
                      on_update: str | None = None, on_duplicate: str | None = None,
                      one_name: str | None = None, many_name: str | None = None,
                      one_group: str | None = None, many_group: str | None = None):
        ...

    @element(parent_tags='virtual_columns', sub_tags='')
    def bagItemColumn(self, name: str, bagcolumn: str, itempath: str,
                      dtype: str | None = None, group: str | None = None,
                      name_long: str | None = None, name_short: str | None = None,
                      comment: str | None = None, x_ui: dict | None = None, metadata: dict | None = None):
        ...

    @element(parent_tags='table', sub_tags='')
    def subtable(self, name: str, condition: str, parameters: dict | None = None,
                 name_long: str | None = None, name_short: str | None = None,
                 comment: str | None = None, x_ui: dict | None = None, metadata: dict | None = None):
        ...

    @element(parent_tags='table', sub_tags='')
    def virtualRelation(self, name: str, relation: str | None = None, table: str | None = None,
                        condition: str | None = None, parameters: dict | None = None,
                        source_parameters: dict | None = None, ask: dict | None = None,
                        order_by: str | tuple | list | None = None, limit: int | None = None,
                        one_one: bool = False, inverse: str | None = None,
                        name_long: str | None = None, name_short: str | None = None,
                        comment: str | None = None, x_ui: dict | None = None, metadata: dict | None = None):
        ...
