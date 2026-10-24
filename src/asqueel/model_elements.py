"""Package and option declarations of the complete model source grammar.

Elements describe source only. Model expansions belong to rendering after
composition, never to an element constructor. No execution binding is defined.
"""
from __future__ import annotations

from genro_builders.builder import element

from .elements import DTYPE, NON_NEGATIVE_INT, NON_NEGATIVE_NUMBER, SQL_PREFIX


OPTION_LEVELS = {
    'requires': {'package'},
    'type': {'package'},
    'sysFields': {'table'},
    'driver': {'connection'},
}

SYS_FIELD_KEYS = {'name_long', 'name_short', 'comment', 'group', 'indexed'}
SYS_FIELDS = ('id', 'ins', 'upd', 'user_ins', 'user_upd', 'ldel', 'draft', 'syscode')


class ModelElements:
    @element(parent_tags='table', sub_tags='', _meta={'attribute_families': ['col_']})
    def colgroup(self, name: str, name_long: str | None = None,
                 name_short: str | None = None, comment: str | None = None,
                 **col_defaults):
        """Ordered group handle; col_* defaults apply to declarations made through it."""
        ...

    @element(parent_tags='db', sub_tags='package', collection_key='name', node_label='packages')
    def packages(self):
        """Logical packages; distinct from physical schemas."""
        ...

    @element(parent_tags='packages', sub_tags='tables[:1], options[:1]')
    def package(self, name: str, sqlschema: str | None = None,
                sqlprefix: bool | SQL_PREFIX = True, name_long: str | None = None,
                name_short: str | None = None, name_full: str | None = None,
                comment: str | None = None, path: str | None = None):
        """Logical table namespace with an explicit physical placement.

        Args:
            name: semantic; package identifier.
            sqlschema: physical schema name, inferred without a schema declaration;
                None selects the dialect default. Packages can share a schema.
            sqlprefix: True uses the package name, False omits the prefix.
            name_long: semantic; human label.
            name_short: semantic; short label.
            comment: semantic; package description.
            path: folder in the legacy layout (``main.py`` with class ``Package``,
                ``model/<table>.py`` with class ``Table``) whose tables the package loads.
        """
        ...

    @element(parent_tags='db, connection, package, table',
             sub_tags='*',
             node_label='options')
    def options(self):
        """Singleton section of typed functions, validated for its owning level."""
        ...

    @element(parent_tags='options', sub_tags='')
    def reset(self, name: str):
        """Remove an accumulated option before subsequent declarations rebuild it."""
        ...

    @element(parent_tags='options', sub_tags='', node_label='driver')
    def driver(self, connect_timeout: NON_NEGATIVE_INT | None = None,
               application_name: str | None = None, sslmode: str | None = None,
               sslrootcert: str | None = None, options: str | None = None,
               timeout: NON_NEGATIVE_NUMBER | None = None, cached_statements: NON_NEGATIVE_INT | None = None,
               foreignKeys: bool | None = None):
        """Driver options, checked against the connection's configured dialect."""
        ...

    @element(parent_tags='options', sub_tags='', node_label='requires')
    def requires(self, packages: str | list[str] | tuple[str, ...]):
        """Names of packages that must be present when resolving the model."""
        ...

    @element(parent_tags='options', sub_tags='')
    def type(self, name: str, dtype: DTYPE, size: str | None = None,
             name_long: str | None = None, name_short: str | None = None):
        """Package-local column type and its explicit presentation defaults."""
        ...

    @element(parent_tags='options', sub_tags='', node_label='sysFields')
    def sysFields(self, id: bool | dict = True, ins: bool | dict = True,
                  upd: bool | dict = True, user_ins: bool | dict = True,
                  user_upd: bool | dict = True, ldel: bool | dict = True,
                  draft: bool | dict = False,
                  group: str = 'zzz', group_name: str = 'System', enabled: bool = True,
                  syscode: bool = False):
        """Describe system fields; expansion happens only during rendering.

        syscode opts into __syscode, A size :20, indexed and unique.
        It adds no system-record behavior, virtual columns or generated values.
        """
        ...
