"""Column rules and non-DDL declarations in the model grammar."""
from __future__ import annotations

from typing import Literal
from genro_builders.builder import element


class SemanticElements:
    @element(parent_tags='column', sub_tags='', node_label='validation')
    def validation(self, **rules):
        """Preserve column validation declarations without interpreting rules.

        Embedded validate_* attributes produce the same dictionary, stripping
        only the prefix. Names and values are retained without vocabulary or
        rule-specific type checks. Translation never executes these rules.
        """
        ...

    @element(parent_tags='column', sub_tags='', node_label='encryption')
    def encryption(self, mode: Literal['X', 'R', 'Q']):
        ...

    @element(parent_tags='column, compositeColumn, aliasColumn, formulaColumn, subQueryColumn, pyColumn, bagItemColumn', sub_tags='')
    def weak_relation(self, to: str, name: str | None = None, inverse: str | None = None,
                      indexed: bool = True, one_one: bool = False, on_delete: str | None = None,
                      on_update: str | None = None, on_duplicate: str | bool | None = None,
                      one_name: str | None = None, many_name: str | None = None,
                      one_group: str | None = None, many_group: str | None = None):
        ...

    @element(parent_tags='virtual_columns', sub_tags='relation')
    def bagItemColumn(self, name: str, bagcolumn: str, itempath: str,
                      dtype: str | None = None, group: str | None = None,
                      name_long: str | None = None, name_short: str | None = None,
                      comment: str | None = None, **extra):
        ...

    @element(parent_tags='table', sub_tags='')
    def subtable(self, name: str, condition: str, parameters: dict | None = None,
                 name_long: str | None = None, name_short: str | None = None,
                 comment: str | None = None, **extra):
        ...

    @element(parent_tags='table', sub_tags='')
    def virtualRelation(self, name: str, relation: str | None = None, table: str | None = None,
                        condition: str | None = None, ask: dict | None = None,
                        name_long: str | None = None, name_short: str | None = None,
                        comment: str | None = None, **bindings):
        """GEP virtual relation; var_* binds source expressions as declaration data.

        table names a direct target and requires a nonempty condition in the
        completed source. condition refers to the target. var_* expressions refer to the source
        and are used as :var_* in condition. An ask field named <name> is
        referenced as :ask_<name>. This namespace is provisional until compiler
        design. ask and bindings are preserved as data, without SQL rewriting.
        Unlike the GEP, order_by, limit and one_one are deferred, along with
        virtual inverses.
        """
        ...
