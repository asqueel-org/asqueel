# Copyright 2025 Softwell S.r.l. - SPDX-License-Identifier: Apache-2.0
"""SqlBuilder — SQL model dialect for genro-builders.

Grammar only: the vocabulary lives in the four mixins of
:mod:`asqueel.elements`, rendering in :class:`SqlRenderer` exposed
via the ``renderer_sql`` property.
"""

from __future__ import annotations

from contextlib import contextmanager
from copy import deepcopy
from typing import cast, get_args

from genro_bag import BagNode

from genro_builders.builder import BuilderBase, SourceBag
from genro_builders.builder.base import SOURCE_ROOT

from .elements import ColumnElements, DbElements, SchemaElements, TableElements
from .model_elements import ModelElements, OPTION_LEVELS, SYS_FIELDS, SYS_FIELD_KEYS
from .renderer import SqlRenderer
from .validators import SqlModelValidator


class SqlSourceBag(SourceBag):
    """Source bag whose bracket access is name addressing over NODES.

    ``model.source["db.public.author"]`` returns the grammar node — its
    attributes, ``_meta`` flags and children — because the SQL model is a
    name-keyed catalog, not a value store: every consumer (renderer,
    validators, emitter) reads nodes. ``get_item``/``get`` keep the plain
    Bag value semantics. Sub-bags inherit this class automatically (the
    grammar spawns them as ``type(node.parent_bag)``), so the whole tree
    is addressed the same way.

    The override also reshapes every Bag form that reads through
    ``__getitem__``: the ``?attr`` path suffix and ``bag(path)`` return
    the node instead of value/attribute, an empty path returns the
    owning node, and the scoped ``query``/``digest`` form
    (``"where:what"``) is unsupported — scope with ``get_item(where)``
    or walk from a node's ``.value`` instead.
    """

    def __getitem__(self, path: str) -> BagNode | None:
        return cast(BagNode | None, self.get_node(path))


class SqlBuilder(DbElements, SchemaElements, TableElements, ColumnElements, ModelElements,
                 BuilderBase):
    """SQL model dialect builder.

    One dialect, one flat namespace: the grammar is split into mixins by
    containment level for readability. Mounted dialects preserve name paths,
    but root-signature validation and serialization of dynamic configuration
    are not yet compatible with every mount; see docs/native-composition.md.
    """

    _name = "sqlmodel"
    _default_render_mode = "sql"
    _name_label_tags = frozenset({
        "schema", "package", "table", "column", "aliasColumn", "formulaColumn",
        "subQueryColumn", "pyColumn", "compositeColumn", "extension",
        "constraint", "index",
    })
    _positional_arguments = {
        **dict.fromkeys(_name_label_tags | {"db"}, "name"),
        "relation": "to",
        'context': 'name', 'type': 'name', 'macro': 'name',
        'metadata': 'namespace', 'requires': 'packages', 'reset': 'name', 'colgroup': 'name',
        'connection': 'name',
    }
    _singletons = frozenset({'schemas', 'packages', 'extensions', 'tables',
                            'columns', 'virtual_columns', 'composites',
                            'constraints', 'indexes', 'options'})
    _table_routes = {
        'column': 'columns', 'formulaColumn': 'virtual_columns',
        'aliasColumn': 'virtual_columns', 'subQueryColumn': 'virtual_columns',
        'pyColumn': 'virtual_columns', 'compositeColumn': 'composites',
        'index': 'indexes',
    }

    def __init__(self, name: str | None = None) -> None:
        super().__init__(name)
        source = SqlSourceBag(builder=self)
        self._sourceroot[SOURCE_ROOT] = source
        self.source = source
        self._contribution = 'main'
        self._attribute_origins: dict[tuple[str, str], str] = {}

    @staticmethod
    def _node_path(node):
        return node.fullpath or node.label

    def main(self, root):
        pass

    def __getattr__(self, name):
        handler = super().__getattr__(name)
        fields = {
            'metadata': ('namespace', 'values'), 'context': ('name', 'dtype'),
            'column': ('name', 'dtype'), 'formulaColumn': ('name', 'sql_formula'),
            'aliasColumn': ('name', 'relation_path'), 'subQueryColumn': ('name', 'query'),
            'compositeColumn': ('name', 'columns'),
        }.get(name)

        def call(destination, *args, **kwargs):
            if name == 'requires' and args:
                if 'packages' in kwargs:
                    raise ValueError('requires: packages passed twice')
                kwargs['packages'] = args[0] if len(args) == 1 else list(args)
                args = ()
            elif fields is not None:
                if len(args) > len(fields):
                    raise TypeError(f'{name}: too many positional arguments')
                for field, value in zip(fields, args):
                    if field in kwargs:
                        raise ValueError(f'{name}: {field} passed twice')
                    kwargs[field] = value
                args = ()
            elif len(args) > 1:
                raise TypeError(f'{name}: at most one positional argument is allowed')
            return handler(destination, *args, **kwargs)

        return call

    @contextmanager
    def contribution(self, name: str):
        """Apply an explicitly ordered contribution to this source."""
        if not isinstance(name, str) or not name.strip():
            raise ValueError('contribution name must be nonempty')
        previous = self._contribution
        self._contribution = name
        try:
            yield self.source
        finally:
            self._contribution = previous

    def _compose_attributes(self, node, attributes):
        result = deepcopy(dict(node.attr))
        changes = {}
        replaced = set()
        for key, value in attributes.items():
            if key == '_meta':
                continue
            merge_dict = (key in ('x_ui', 'metadata', 'values')
                          or (node.node_tag == 'sys_fields' and key in SYS_FIELDS))
            updates = ({f'{key}.{part}': item for part, item in value.items()}
                       if merge_dict and isinstance(value, dict) and isinstance(result.get(key), dict)
                       else {key: value})
            for attribute, item in updates.items():
                part = attribute[len(key) + 1:] if attribute != key else None
                present = part in result[key] if part is not None else key in result
                old = result[key].get(part) if part is not None else result.get(key)
                origin_key = (self._node_path(node), attribute)
                previous = self._attribute_origins.get(origin_key,
                            self._attribute_origins.get((self._node_path(node), key), 'main'))
                if present and old != item and previous == self._contribution:
                    raise ValueError(f'{self._node_path(node)}: conflicting {attribute!r} '
                                     f'in contribution {self._contribution!r}')
                if part is not None:
                    result[key][part] = deepcopy(item)
                else:
                    result[key] = deepcopy(item)
                    replaced.add(key)
                changes[origin_key] = self._contribution
        node.attr.update(result)
        self._attribute_origins = {key: value for key, value in self._attribute_origins.items()
                                   if not (key[0] == self._node_path(node)
                                           and any(key[1].startswith(name + '.') for name in replaced))}
        self._attribute_origins.update(changes)
        return node

    @staticmethod
    def _package_ancestor(node):
        while node is not None:
            if node.node_tag == 'package':
                return node
            node = node.parent_node
        return None

    @staticmethod
    def _validate_option(tag, parent, attributes):
        owner = parent.parent_node if parent is not None else None
        if owner is None or owner.node_tag not in OPTION_LEVELS[tag]:
            raise ValueError(f'{tag}: option is not available at this level')
        if tag == 'driver':
            if owner.get_attr('options') is not None:
                raise ValueError('Use driver() or legacy connection options, not both')
            dialect = owner.get_attr('implementation') or owner.parent_node.get_attr('implementation') or 'postgresql'
            allowed = ({'timeout', 'cached_statements'} if dialect == 'sqlite' else
                       {'connect_timeout', 'application_name', 'sslmode', 'sslrootcert', 'options'})
            unknown = attributes.keys() - allowed - {'_meta'}
            if unknown:
                raise ValueError(f'driver: unsupported {dialect} options {sorted(unknown)}')
            for key in ('connect_timeout', 'timeout', 'cached_statements'):
                if key in attributes and (isinstance(attributes[key], bool)
                                          or attributes[key] is not None and attributes[key] < 0):
                    raise ValueError(f'driver.{key}: expected a nonnegative number')
        if tag == 'sys_fields':
            if attributes.get('timestamp_type', 'DHZ') not in ('DH', 'DHZ'):
                raise ValueError('sys_fields.timestamp_type must be DH or DHZ')
            for field in SYS_FIELDS:
                value = attributes.get(field, True)
                if not isinstance(value, (dict, bool)):
                    raise ValueError(f'sys_fields.{field}: expected bool or dict')
                if isinstance(value, dict):
                    allowed = SYS_FIELD_KEYS | ({'type'} if field == 'id' else set())
                    unknown = value.keys() - allowed
                    if unknown:
                        raise ValueError(f'sys_fields.{field}: unknown fields {sorted(unknown)}')
                    if field == 'id' and value.get('type', 'uuid') != 'uuid':
                        raise ValueError('sys_fields.id.type must be uuid')
                    for key, item in value.items():
                        expected = dict if key in ('x_ui', 'metadata') else bool if key == 'indexed' else str
                        if not isinstance(item, expected):
                            raise ValueError(f'sys_fields.{field}.{key}: expected {expected.__name__}')

    def _validate_call_args(self, info, node_value, attr, node_tag=""):
        parameter = self._positional_arguments.get(node_tag)
        if parameter is not None and node_value is not None:
            if parameter in attr:
                raise ValueError(f"'{node_tag}': {parameter} passed twice")
            attr[parameter] = node_value
            node_value = None
        if node_tag in OPTION_LEVELS or node_tag in ('package', 'colgroup'):
            for key, value in attr.items():
                entry = (info.get('call_args_validations') or {}).get(key)
                if value is None and entry is not None:
                    annotation = entry[0]
                    if annotation is not object and type(None) not in get_args(annotation):
                        raise ValueError(f'{node_tag}.{key}: None is not allowed')
        return super()._validate_call_args(info, node_value, attr, node_tag)

    def set_child(self, build_where, node_tag, node_value=None, node_label=None,
                  node_position=None, **attr):
        """Apply SQL path and namespace rules before framework insertion."""
        positional = self._positional_arguments.get(node_tag)
        if positional is not None and attr.get(positional) == node_value:
            node_value = None
        parent = build_where.parent_node
        if node_tag == 'connection':
            if node_label is not None:
                raise ValueError('connection: node_label is fixed by its name')
            named = 'database' in attr or 'dsn' in attr
            name = attr.get('name', 'main')
            candidate = build_where.node('connection' if name == 'main' else f'connection_{name}') if isinstance(name, str) else None
            if candidate is not None and ('database' in candidate.attr or 'dsn' in candidate.attr):
                named = True
            if named and (not isinstance(name, str) or not name.strip() or any(c in name for c in '.@$/\\')):
                raise ValueError('connection: logical name must be a nonempty identifier')
            node_label = f'connection_{name}' if named and name != 'main' else 'connection'
            if attr.get('dsn') is not None and any(key in attr for key in ('database', 'host', 'port', 'user', 'password')):
                raise ValueError('dsn and individual connection fields cannot be combined')
            if named and candidate is not None:
                merged = {**candidate.attr, **attr}
                if merged.get('dsn') is not None and any(merged.get(key) is not None for key in ('database', 'host', 'port', 'user', 'password')):
                    raise ValueError('dsn and individual connection fields cannot be combined')
                return self._compose_attributes(candidate, attr)
        if parent is not None and parent.node_tag == 'colgroup' and node_tag in self._table_routes:
            table = parent.parent_node
            declarations = list(table.value.query('#n', deep=True))
            prefix = parent.get_attr('name') + '.'
            members = [n for n in declarations if (n.get_attr('group') or '').startswith(prefix)]
            existing = table.value.get_node(f'{self._table_routes[node_tag]}.{attr.get("name")}')
            group = existing.get_attr('group') if existing is not None else None
            if group is not None and not group.startswith(prefix):
                raise ValueError(f'{attr.get("name")!r}: conflicting column group')
            group = group or f'{prefix}{len(members) + 1:03d}'
            if 'group' in attr and attr['group'] != group:
                raise ValueError(f'{attr.get("name")!r}: conflicting column group')
            declared = self._get_schema_info(node_tag).get('declared_names') or set()
            defaults = {key[4:]: value for key, value in parent.attr.items()
                        if key.startswith('col_') and key[4:] in declared
                        and (existing is None or key[4:] not in existing.attr)}
            values = () if node_value is None else (node_value,)
            return getattr(table, node_tag)(*values, **{**defaults, **attr, 'group': group})
        if node_tag == 'colgroup':
            name = attr.get('name')
            if not isinstance(name, str) or not name or '.' in name:
                raise ValueError('colgroup: name must be a nonempty identifier')
            if node_label is not None:
                raise ValueError('colgroup: node_label is fixed by the group name')
            declared = self._get_schema_info('column').get('declared_names') or set()
            for key in attr:
                if key in ('name', 'name_long', 'x_ui', '_meta'):
                    continue
                if not key.startswith('col_') or key[4:] not in declared or key == 'col_name':
                    raise ValueError(f'colgroup: unknown column default {key!r}')
            defaults = {key[4:]: value for key, value in attr.items() if key.startswith('col_')}
            self._validate_call_args(self._get_schema_info('column'), None,
                                     {'name': '__group_default__', **defaults}, 'column')
            node_label = f'colgroup_{name}'
            existing = build_where.node(node_label)
            if existing is not None:
                if dict(existing.attr) != {**dict(existing.attr), **attr}:
                    raise ValueError(f'colgroup {name!r}: conflicting definition')
                return existing
        if node_tag == 'reset':
            self._validate_parent_tags(self._get_schema_info(node_tag), parent)
            name = attr['name']
            owner = parent.parent_node
            if name not in OPTION_LEVELS or owner.node_tag not in OPTION_LEVELS[name]:
                raise ValueError(f'Cannot reset unknown option {name!r} at this level')
            nodes = [node for node in build_where if node.node_tag == name]
            for node in nodes:
                path = self._node_path(node)
                build_where.pop(node.label)
                self._attribute_origins = {
                    key: value for key, value in self._attribute_origins.items() if key[0] != path}
            meta = deepcopy(parent.attr.get('_meta') or {})
            meta['option_resets'] = sorted(set(meta.get('option_resets', ())) | {name})
            parent.attr['_meta'] = meta
            return parent
        if parent is not None and parent.node_tag == 'table' and node_tag in self._table_routes:
            container = getattr(parent, self._table_routes[node_tag])()
            values = () if node_value is None else (node_value,)
            return getattr(container, node_tag)(*values, node_label=node_label,
                                                node_position=node_position, **attr)
        if parent is not None and parent.node_tag == 'package' and node_tag == 'table':
            return parent.tables().table(node_value, node_label=node_label,
                                         node_position=node_position, **attr)
        if node_tag in self._singletons and node_label is None:
            existing = build_where.node(node_tag)
            if existing is not None:
                self._validate_parent_tags(self._get_schema_info(node_tag), parent)
                if existing.node_tag != node_tag:
                    raise ValueError(f'conflicting element kind for {node_tag!r}')
                return existing
        if node_tag in OPTION_LEVELS:
            self._validate_option(node_tag, parent, attr)
            if node_label is not None:
                raise ValueError(f'{node_tag}: node_label is fixed by the option identity')
            identity = attr.get('namespace' if node_tag == 'metadata' else 'name')
            if identity is not None:
                if not isinstance(identity, str) or not identity or '.' in identity:
                    raise ValueError(f'{node_tag}: invalid option identifier')
                node_label = f'{node_tag}_{identity}'
            else:
                existing = build_where.node(node_tag)
                if existing is not None:
                    return self._compose_attributes(existing, attr)
            existing = build_where.node(node_label) if node_label is not None else None
            if existing is not None:
                return self._compose_attributes(existing, attr)
        if node_tag == 'package':
            prefix = attr.get('sqlprefix', True)
            if isinstance(prefix, str) and (not prefix or prefix.endswith('_')):
                raise ValueError('sqlprefix must be nonempty and must not end in an underscore')
            if not isinstance(prefix, (bool, str)):
                raise ValueError('sqlprefix must be a boolean or string')
        positional = self._positional_arguments.get(node_tag)
        if positional is not None and attr.get(positional) == node_value:
            node_value = None
        if node_tag == "db" and build_where.node("db") is not None:
            raise ValueError("a database is already present in this SQL model")
        name = attr.get("name")
        if node_tag in self._name_label_tags:
            if isinstance(name, str) and "." in name:
                raise ValueError(
                    f"'{node_tag}' name {name!r} contains the Bag path separator '.'",
                )
            if node_label is not None:
                raise ValueError(
                    f"'{node_tag}': node_label is fixed by its SQL name",
                )
            if (node_tag in ('schema', 'package') or self._package_ancestor(parent) is not None) and name:
                existing = build_where.node(name)
                if existing is not None:
                    if existing.node_tag != node_tag:
                        raise ValueError(f'conflicting element kind for {name!r}')
                    return self._compose_attributes(existing, attr)
        if node_label is not None and build_where.node(node_label) is not None:
            raise ValueError(
                f"duplicate {node_tag} name {name!r} in the same SQL namespace",
            )
        child = super().set_child(
            build_where, node_tag, node_value, node_label=node_label,
            node_position=node_position, **deepcopy(attr),
        )
        # Bag drops None attributes by default; here omission and explicit None
        # are different contributions and must survive composition.
        child.attr.update({key: None for key, value in attr.items() if value is None})
        self._attribute_origins.update({(self._node_path(child), key): self._contribution for key in attr})
        return child

    def validate_model(self):
        """Run the domain validation on this model and return it.

        Convenience over ``SqlModelValidator().validate(self)``; raises
        :class:`~asqueel.validators.SqlModelValidationError`
        listing every violation.
        """
        return SqlModelValidator().validate(self)

    @property
    def renderer_sql(self) -> SqlRenderer:
        """Fresh ``SqlRenderer`` instance bound to this builder.

        Each access returns a new instance: the renderer is meant to be
        ephemeral, used for a single ``render`` call and discarded.

        Today ``SqlRenderer`` is a placeholder that renders nothing: DDL
        rendering is out of scope until its own slice lands. Database work
        goes through :class:`~asqueel.migration.SqlMigrationRenderer`.
        """
        return SqlRenderer(builder=self)
