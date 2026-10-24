"""Column rules and non-DDL declarations in the model grammar."""
from __future__ import annotations

from genro_builders.builder import element


class SemanticElements:
    @element(parent_tags='virtual_columns', sub_tags='relation')
    def bagItemColumn(self, name: str, bagcolumn: str, itempath: str,
                      dtype: str | None = None, group: str | None = None,
                      name_long: str | None = None, name_short: str | None = None,
                      comment: str | None = None):
        ...

    @element(parent_tags='table', sub_tags='', _meta={'attribute_families': ['var_']})
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
