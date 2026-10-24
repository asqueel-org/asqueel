"""Owned, layered SQL application configuration using Builders' read stack."""
from __future__ import annotations

from copy import deepcopy
from contextlib import contextmanager
from pathlib import Path
import sys

from genro_builders.builder import BuilderBase, element
from genro_builders.contrib.config import ConfigBuilder, ConfigHandler
from genro_bag import Bag, BagNode, BagResolver

from .builder import SqlBuilder
from .package_layout import load_package_layouts

_MISSING = object()


class SqlDatabaseElements:
    """Keep root grammar in a mixin so recipe subclasses retain its defaults."""

    @element(sub_tags='connection, packages[:1], extensions[:1], options[:1]', node_label='db')
    def db(self, name: str = 'db', implementation: str = 'sqlite', conninfo: str = '',
           connect_kwargs: dict | None = None, name_long: str | None = None,
           name_short: str | None = None, comment: str | None = None):
        ...

    @element(parent_tags='db', sub_tags='options[:1]')
    def connection(self, name: str | BagResolver = 'main', implementation: str | None = None,
                   host: str | BagResolver | None = None,
                   port: int | BagResolver | None = None,
                   user: str | BagResolver | None = None,
                   password: str | BagResolver | None = None,
                   database: str | BagResolver | None = None,
                   dsn: str | BagResolver | None = None, name_long: str | None = None,
                   name_short: str | None = None, comment: str | None = None):
        """Named connection; legacy declarations without database/dsn keep name as database."""
        ...


class SqlDatabaseConfig(SqlDatabaseElements, SqlBuilder, ConfigBuilder):
    """SQL application recipe: model grammar plus connection configuration."""


def _copy_recipe(recipe):
    # Renderer products and delivery targets are live resources, not declaration
    # state. Exclude them through deepcopy's memo without mutating the caller.
    memo = {id(recipe.materialized): {}, id(recipe._default_targets): {}}
    return deepcopy(recipe, memo)


def compose_recipe(source, parents=None):
    """The recipe a database is built from: ``source`` over ``parents``, with package layouts, validated.

    Works on owned copies; the authored recipes are not modified.
    """
    def own(recipe):
        return _copy_recipe(recipe) if isinstance(recipe, BuilderBase) else recipe
    sources = [configuration_source(item) for item in (*(parents or ()), source)]
    with _recipe_imports(sources):
        layers = [SqlConfigHandler(own(item)).builder for item in sources]
        recipe = layers[0]
        for index, layer in enumerate(layers[1:], 1):
            with recipe.contribution(f'layer[{index}]'):
                _compose_source(recipe, recipe.source, layer.source)
        load_package_layouts(recipe)
        _validate_source_shape(recipe)
        recipe.composed = True
        return recipe


def _validate_source_shape(builder):
    """Validate composition without resolving defaults, references or secrets."""
    for _, node in builder.source.query('#p,#n', deep=True):
        # Attributes written after the call (layout hooks, set_attr) meet the same signature.
        owner = node._resolve_builder()
        if owner._schema.get_node(node.node_tag) is None:
            owner = builder
        # Attributes kept from a redefined virtual column's previous kind stay valid.
        inherited = set((node.attr.get('_meta') or {}).get('inherited_attributes', ()))
        owner._validate_call_args(owner._get_schema_info(node.node_tag), None,
                                 {key: value for key, value in node.attr.items()
                                  if key != '_meta' and key not in inherited},
                                 node.node_tag)
        if node.node_tag == 'virtualRelation':
            condition = node.attr.get('condition')
            if node.attr.get('table') and (condition is None or
                    isinstance(condition, str) and not condition.strip()):
                raise ValueError('virtualRelation: table requires a nonempty condition')
        if builder.option_levels(node.node_tag) is not None:
            builder._validate_option(node.node_tag, node.parent_node, dict(node.attr))
        if node.node_tag == 'table' and isinstance(node.value, Bag):
            names = {}
            for container in node.value:
                if container.node_tag not in ('columns', 'virtual_columns', 'composites'):
                    continue
                for child in container.value or ():
                    if child.label in names:
                        raise ValueError(f'{node.fullpath}.{child.label}: conflicting element kinds '
                                         f'{names[child.label]!r} and {child.node_tag!r}')
                    names[child.label] = child.node_tag


class SqlConfigHandler(ConfigHandler):
    """Use Builders' loader/defaults, preserving explicit nullable SQL values."""

    def __call__(self, path, default=_MISSING):
        node_path, attribute = self._split_path(path)
        node = self.builder.source.get_node(node_path)
        if node is not None and attribute in node.attr:
            return node.get_value(_query_string=attribute)
        if default is _MISSING:
            return super().__call__(path)
        return super().__call__(path, default=default)


def _compose_source(builder, target, incoming):
    """Fold explicit attributes, retaining reset directives until layers meet.

    Work on owned sources only. Walking static values avoids resolving secrets
    or importing a provider as a side effect of the merge.
    """
    for node in incoming:
        existing = target.get_node(node.label)
        if node.node_tag == 'connection' and not {'database', 'dsn'}.intersection(node.attr):
            name = node.get_attr('name')
            if isinstance(name, str) and name != 'main':
                named = target.get_node(f'connection_{name}')
                if named is not None and {'database', 'dsn'}.intersection(named.attr):
                    existing = named
                elif existing is not None and {'database', 'dsn'}.intersection(existing.attr):
                    raise ValueError('Ambiguous connection override: declare database or dsn explicitly')
        if existing is None:
            value = node.get_value(static=True)
            added = target.set_item(node.label, None if isinstance(value, Bag) else deepcopy(value),
                                    _attributes=deepcopy(dict(node.attr)), _remove_null_attributes=False,
                                    node_tag=node.node_tag)
            builder._attribute_origins.update({(builder._node_path(added), key): builder._contribution
                                               for key in added.attr if key != '_meta'})
            if isinstance(value, Bag):
                added.value = type(value)(builder=builder)
                _compose_source(builder, added.value, value)
            continue
        attributes = dict(node.attr)
        if existing.node_tag != node.node_tag:
            group = (node.attr.get('_meta') or {}).get('colgroup')
            if group and (existing.get_attr('group') or '').startswith(group + '.'):
                attributes.pop('group', None)
        builder._compose_attributes(existing, attributes, node_tag=node.node_tag)
        value = node.get_value(static=True)
        previous = existing.get_value(static=True)
        if node.node_tag == 'options' and isinstance(previous, Bag):
            resets = (node.attr.get('_meta') or {}).get('option_resets', ())
            for child in list(previous):
                if child.node_tag in resets:
                    previous.pop(child.label)
            if resets:
                meta = deepcopy(existing.attr.get('_meta') or {})
                meta['option_resets'] = sorted(set(meta.get('option_resets', ())) | set(resets))
                existing.attr['_meta'] = meta
        if isinstance(value, Bag):
            if previous is None:
                existing.value = type(value)(builder=builder)
                _compose_source(builder, existing.value, value)
            elif isinstance(previous, Bag):
                _compose_source(builder, previous, value)
            else:
                raise ValueError(f'{existing.fullpath}: a model node cannot replace a scalar')


def configuration_source(source):
    """Resolve a registered name, a recipe path/directory, a Python class or a mounted ``db`` node."""
    if isinstance(source, BagNode):
        return _recipe_from_node(source)
    if isinstance(source, str) and ':' in source and not source.endswith('.py'):
        from pkgutil import resolve_name
        return resolve_name(source)
    if isinstance(source, str) and '/' not in source and '\\' not in source and source not in ('.', '..') and not source.endswith('.py'):
        from .registry import DatabaseRegistry
        return DatabaseRegistry().resolve(source)
    if isinstance(source, (str, Path)):
        path = Path(source).expanduser().resolve()
        return path / 'configure.py' if path.is_dir() else path
    return source


def _recipe_from_node(node):
    """Recipe that rebuilds a ``db`` subtree written in a host document.

    A host configuration mounts ``AsqueelDb.grammar`` and writes the database
    under its own node; this replays that subtree, element by element, into a
    standalone recipe, so the database is built exactly as from a recipe class.
    """
    if node.node_tag != 'db':
        raise TypeError(f"a mounted Asqueel database starts at a 'db' node, not {node.node_tag!r}")

    recipe = SqlDatabaseConfig()
    _replay_node(node, recipe.source)
    return recipe


def _replay_node(node, target):
    """Call the element of ``node`` on ``target`` with its attributes, then its children."""
    attributes = {key: value for key, value in node.attr.items() if key != '_meta'}
    value = node.value
    if value is not None and not isinstance(value, Bag):
        raise TypeError(f"{node.node_tag!r} carries a value: only attributes and children can be replayed")
    child = getattr(target, node.node_tag)(**attributes)
    if node.node_tag == 'options':
        for name in (node.attr.get('_meta') or {}).get('option_resets', ()):
            child.reset(name)
    if isinstance(value, Bag):
        for subnode in value:
            _replay_node(subnode, child)


@contextmanager
def _recipe_imports(sources):
    """Let the standard file loader import packages containing its recipe.

    ConfigHandler remains the recipe loader; file recipes use absolute imports.
    Only Python package roots (directories with __init__.py) are inferred.
    """
    added = []
    for source in sources:
        if not isinstance(source, Path):
            continue
        root = source.parent
        while (root / '__init__.py').is_file():
            root = root.parent
        if str(root) not in sys.path:
            sys.path.insert(0, str(root))
            added.append(str(root))
    try:
        yield
    finally:
        for root in added:
            sys.path.remove(root)
