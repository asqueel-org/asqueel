"""Declarative behavior options. Constructors never expand or execute them."""
from __future__ import annotations

from typing import Literal
from genro_builders.builder import element

NAMED_OPTIONS = {'partition': 'name', 'numbering': 'field'}


class BehaviorOptionElements:
    """Table options. The elements of this class and of its subclasses mixed into a builder are its table options."""

    @element(parent_tags='options', sub_tags='', node_label='hierarchical')
    def hierarchical(self, columns: str | list | tuple | None = None, *, parent: str = 'parent_id',
                     root_id: bool = False, virtual_roots: bool = False,
                     linked_to: str | None = None, depth: int | None = None,
                     caption_field: str | None = None, enabled: bool = True):
        """Declare a hierarchy; column entries are names or {name, unique} mappings."""
        ...

    @element(parent_tags='options', sub_tags='', node_label='auto_counter')
    def auto_counter(self, scope: str | list | tuple | None = None, *, field: str = '_row_count',
                     enabled: bool = True):
        """Declare a counter and its scope; no value allocation during construction."""
        ...

    @element(parent_tags='options', sub_tags='', node_label='relative_index')
    def relative_index(self, relation: str | None = None, *, field: str = '_relidx',
                       enabled: bool = True):
        """Declare a relative index; relation required when enabled."""
        ...

    @element(parent_tags='options, column', sub_tags='', node_label='dynamic_fields')
    def dynamic_fields(self, *, templates: dict | str | None = None,
                       source: str | None = None, enabled: bool = True):
        """Table option uses templates; column declaration requires source."""
        ...

    @element(parent_tags='options', sub_tags='', node_label='record_hash')
    def record_hash(self, *, field: str = '__rec_md5', columns: str | list | tuple | None = None,
                    algorithm: Literal['md5'] = 'md5', enabled: bool = True):
        """Declare a record comparison hash, independent of SQL defaults."""
        ...

    @element(parent_tags='options', sub_tags='', node_label='full_update')
    def full_update(self, *, field: str = '__full_mod_ts', enabled: bool = True):
        """Declare the timestamp for updates including related content."""
        ...

    @element(parent_tags='options', sub_tags='', node_label='audit')
    def audit(self, mode: Literal['full', 'lazy'] | None = None, *, version_field: str = '__version',
              enabled: bool = True):
        """Declare audit; mode required when enabled."""
        ...

    @element(parent_tags='options', sub_tags='', node_label='system_records')
    def system_records(self, *, records: dict | None = None, masterfield: str | None = None,
                       tag: str = 'superadmin', enabled: bool = True):
        """Declare system records or symbolic factories; never insert data at build time."""
        ...

    @element(parent_tags='options', sub_tags='', node_label='protection')
    def protection(self, *, rules: list | tuple | None = None, tag: str | None = None,
                   enabled: bool = True):
        """Declare protection expressions or symbolic rules."""
        ...

    @element(parent_tags='options', sub_tags='', node_label='release')
    def release(self, *, handlers: dict | None = None, enabled: bool = True):
        """Declare version-to-handler references; no transformations run at build time."""
        ...

    @element(parent_tags='options', sub_tags='')
    def partition(self, name: str, *, field: str | None = None, value: object = None,
                  required: bool = False, enabled: bool = True):
        """Declare a logical partition with a value or an existing lazy resolver."""
        ...

    @element(parent_tags='options', sub_tags='', node_label='retention')
    def retention(self, *, field: str | None = None, days: int | None = None,
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

    @element(parent_tags='options', sub_tags='', node_label='attachments')
    def attachments(self, *, master: str | None = None, enabled: bool = True):
        """Declare attachment expansion for its master table."""
        ...

    @element(parent_tags='options', sub_tags='')
    def numbering(self, field: str, *, parameters: dict | None = None, enabled: bool = True):
        """Declare the parameters of a named numbering rule."""
        ...
