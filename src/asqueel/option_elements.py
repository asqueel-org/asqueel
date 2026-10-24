"""Declarative behavior options. Constructors never expand or execute them."""
from __future__ import annotations

from genro_builders.builder import element

from .elements import NON_NEGATIVE_INT, POSITIVE_INT

NAMED_OPTIONS = {'numbering': 'field'}


class BehaviorOptionElements:
    """Table options. The elements of this class and of its subclasses mixed into a builder are its table options."""

    @element(parent_tags='options', sub_tags='', node_label='hierarchical')
    def hierarchical(self, columns: str | list | tuple | None = None, *, parent: str = 'parent_id',
                     root_id: bool = False, virtual_roots: bool = False,
                     linked_to: str | None = None, depth: POSITIVE_INT | None = None,
                     caption_field: str | None = None, enabled: bool = True):
        """Declare a hierarchy; column entries are names or {name, unique} mappings."""
        ...

    @element(parent_tags='options', sub_tags='', node_label='counter')
    def counter(self, scope: str | list | tuple | None = None, *, field: str = '_row_count',
                enabled: bool = True):
        """Declare a counter and its scope; no value allocation during construction."""
        ...

    @element(parent_tags='options', sub_tags='', node_label='relidx')
    def relidx(self, relation: str | None = None, *, field: str = '_relidx',
               enabled: bool = True):
        """Declare a relative index; relation required when enabled."""
        ...

    @element(parent_tags='options, column', sub_tags='', node_label='df')
    def df(self, *, templates: dict | str | None = None,
           source: str | None = None, enabled: bool = True):
        """Table option uses templates; column declaration requires source."""
        ...

    @element(parent_tags='options', sub_tags='', node_label='fullUpd')
    def fullUpd(self, *, field: str = '__full_mod_ts', enabled: bool = True):
        """Declare the timestamp for updates including related content."""
        ...

    @element(parent_tags='options', sub_tags='', node_label='sysrecords')
    def sysrecords(self, *, records: dict | None = None, masterfield: str | None = None,
                   tag: str = 'superadmin', enabled: bool = True):
        """Declare system records or symbolic factories; never insert data at build time."""
        ...

    @element(parent_tags='options', sub_tags='', node_label='release')
    def release(self, *, handlers: dict | None = None, enabled: bool = True):
        """Declare version-to-handler references; no transformations run at build time."""
        ...

    @element(parent_tags='options', sub_tags='', node_label='retention')
    def retention(self, *, field: str | None = None, days: NON_NEGATIVE_INT | None = None,
                  enabled: bool = True):
        """Declare retention by field and nonnegative days."""
        ...

    @element(parent_tags='options', sub_tags='', node_label='broadcast')
    def broadcast(self, columns: str | list | tuple | None = None, *, enabled: bool = True):
        """Declare change events; no events emitted at build time."""
        ...

    @element(parent_tags='options', sub_tags='', node_label='archive')
    def archive(self, *, enabled: bool = True):
        """Declare the legacy archivable flag."""
        ...

    @element(parent_tags='options', sub_tags='', node_label='enabled_when')
    def enabled_when(self, *, preference: str | None = None, enabled: bool = True):
        """Declare a preference condition without evaluating it."""
        ...

    @element(parent_tags='options', sub_tags='')
    def numbering(self, field: str, *, parameters: dict | None = None, enabled: bool = True):
        """Declare the parameters of a named numbering rule."""
        ...
