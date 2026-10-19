"""Owned, layered SQL application configuration using Builders' read stack."""
from __future__ import annotations

from copy import deepcopy
from contextlib import contextmanager
import inspect
from pathlib import Path
import sys
from typing import Any, Callable

from genro_builders.builder import BuilderBase, element
from genro_builders.contrib.config import ConfigBuilder, ConfigHandler
from genro_bag import Bag, BagNode, BagResolver

from .builder import SqlBuilder
from .package_layout import load_package_layouts

_MISSING = object()


class ConfigurationView:
    """A relative read view over a configuration reader."""

    def __init__(self, handler: Callable[..., Any], prefix: str = '', *, fallback=None):
        self.handler = handler
        self.prefix = prefix.strip('.')
        self._fallback = fallback

    def __call__(self, path: str, default=_MISSING):
        if not isinstance(path, str) or not path:
            raise ValueError('configuration path must be a non-empty string')
        fullpath = f'{self.prefix}.{path}' if self.prefix else path
        if self._fallback is None and default is not _MISSING:
            return self.handler(fullpath, default=default)
        try:
            return self.handler(fullpath)
        except KeyError:
            if self._fallback is not None:
                try:
                    return self._fallback()(path)
                except KeyError:
                    pass
            if default is _MISSING:
                raise
            return default

    def scope(self, prefix: str) -> ConfigurationView:
        fallback = (lambda: self._fallback().scope(prefix)) if self._fallback is not None else None
        return ConfigurationView(self.handler, '.'.join(filter(None, (self.prefix, prefix))),
                                 fallback=fallback)


class SqlDatabaseElements:
    """Keep root grammar in a mixin so recipe subclasses retain its defaults."""

    @element(sub_tags='connection, schemas[:1], packages[:1], extensions[:1], options[:1]', node_label='db')
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
                   options: dict | None = None, database: str | BagResolver | None = None,
                   dsn: str | BagResolver | None = None, name_long: str | None = None,
                   name_short: str | None = None, comment: str | None = None):
        """Named connection; legacy declarations without database/dsn keep name as database."""
        ...


class SqlDatabaseConfig(SqlDatabaseElements, SqlBuilder, ConfigBuilder):
    """SQL application recipe: model grammar plus connection configuration."""

    _default_render_mode = 'objects'

    @property
    def renderer_objects(self):
        from .object_renderer import SqlObjectRenderer
        return SqlObjectRenderer(self)

    @property
    def renderer_objects_tree(self):
        from .object_tree_renderer import SqlObjectTreeRenderer
        return SqlObjectTreeRenderer(self)


def _copy_recipe(recipe):
    # Renderer products and delivery targets are live resources, not declaration
    # state. Exclude them through deepcopy's memo without mutating the caller.
    memo = {id(recipe.materialized): {}, id(recipe._default_targets): {}}
    return deepcopy(recipe, memo)


def _owned_handler(source, parents=None):
    def own(recipe):
        return _copy_recipe(recipe) if isinstance(recipe, BuilderBase) else recipe
    sources = [configuration_source(item) for item in (*(parents or ()), source)]
    with _recipe_imports(sources):
        layers = [SqlConfigHandler(own(item)) for item in sources]
        handler = layers[0]
        for index, layer in enumerate(layers[1:], 1):
            with handler.builder.contribution(f'layer[{index}]'):
                _compose_source(handler.builder, handler.builder.source, layer.builder.source)
        _normalize_connection_options(handler)
        load_package_layouts(handler.builder)
        _validate_source_shape(handler.builder)
        return handler


def _validate_source_shape(builder):
    """Validate composition without resolving defaults, references or secrets."""
    tags = {node.node_tag for _, node in builder.source.query('#p,#n', deep=True)}
    if 'packages' in tags and 'schemas' in tags:
        raise ValueError('Package configuration derives schemas from package.sqlschema; '
                         'remove the explicit schemas section')
    for _, node in builder.source.query('#p,#n', deep=True):
        if node.node_tag in ('context', 'generation', 'behavior', 'pkey_from', 'macro',
                             'normalize', 'aliasTable', 'table_alias', 'metadata', 'diagnostics'):
            raise ValueError(f'{node.node_tag}: removed from the source grammar')
        if node.node_tag == 'virtualRelation':
            owner = node._resolve_builder()
            owner._validate_call_args(owner._get_schema_info(node.node_tag), None,
                                     dict(node.attr), node.node_tag)
            condition = node.attr.get('condition')
            if node.attr.get('table') and (condition is None or
                    isinstance(condition, str) and not condition.strip()):
                raise ValueError('virtualRelation: table requires a nonempty condition')
        if (node.node_tag in builder.table_options or node.node_tag == 'encryption') and 'provider' in node.attr:
            raise ValueError(f'{node.node_tag}: provider removed from the source grammar')
        if builder.option_levels(node.node_tag) is not None:
            if node.node_tag in builder.table_options:
                owner = node._resolve_builder()
                owner._validate_call_args(owner._get_schema_info(node.node_tag), None,
                    {key: value for key, value in node.attr.items() if key != '_meta'}, node.node_tag)
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


def _normalize_connection_options(handler):
    """Translate the 0.5 connection dictionary on an owned administrative source."""
    for _, node in list(handler.builder.source.query('#p,#n', deep=True)):
        if node.node_tag != 'connection' or node.get_attr('options') is None:
            continue
        values = deepcopy(node.get_attr('options'))
        existing = node.value.get_node('options.driver') if isinstance(node.value, Bag) else None
        if existing is not None:
            raise ValueError('Use connection.options().driver() or legacy options, not both')
        del node.attr['options']
        node.options().driver(**values)


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
            for other, key in builder._validation_overrides(added, dict(node.attr)):
                other.attr.pop(key, None)
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
    """Recipe class that rebuilds a ``db`` subtree written in a host document.

    A host configuration mounts ``AsqueelDb.grammar`` and writes the database
    under its own node; this replays that subtree, element by element, into a
    standalone recipe, so the database is built exactly as from a recipe class.
    """
    if node.node_tag != 'db':
        raise TypeError(f"a mounted Asqueel database starts at a 'db' node, not {node.node_tag!r}")

    class MountedDatabase(SqlDatabaseConfig):
        def main(self, root):
            _replay_node(node, root)

    return MountedDatabase


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


def connection_settings(config, connection_name='main'):
    """Read standard config attributes, resolving EnvResolver via ConfigHandler."""
    prefix = 'connection'
    if connection_name not in ('main', '_main_connection') and isinstance(config, ConfigHandler):
        candidate = f'connection_{connection_name}'
        node = config.builder.source.get_node(f'{config.root_label}.{candidate}')
        if node is not None:
            prefix = candidate
        else:
            root = config.builder.source.get_node(config.root_label)
            if root is not None and isinstance(root.value, Bag) and any(
                    child.node_tag == 'connection' and {'database', 'dsn'}.intersection(child.attr)
                    for child in root.value):
                raise ValueError(f'Unknown named connection: {connection_name!r}')
    return _connection_settings(config, prefix)


def _connection_settings(config, prefix):
    def read(path, default=None):
        # ConfigHandler's generic None-as-missing semantics must not replace a
        # failed explicit resolver with the signature's default connection name.
        if isinstance(config, ConfigHandler):
            head, _, attribute = path.rpartition('.')
            node_path = '.'.join(filter(None, (config.root_label, prefix, head)))
            node = config.builder.source.get_node(node_path)
            if node is not None and attribute in node.attr:
                return node.get_value(_query_string=attribute)
        return config(f'{prefix}.{path}', default=default)

    name = read('name')
    has_connection = (isinstance(config, ConfigHandler)
                      and config.builder.source.get_node(f'{config.root_label}.{prefix}') is not None)
    if not has_connection and name is None:
        if isinstance(config, ConfigHandler):
            root = config.builder.source.get_node(config.root_label)
            if root is not None and isinstance(root.value, Bag) and any(
                    child.node_tag == 'connection' for child in root.value):
                raise ValueError('Named connections require an explicit main connection')
        return (config('implementation', default='sqlite'),
                config('conninfo', default=''), config('connect_kwargs', default=None))
    implementation = read('implementation')
    if implementation is None:
        implementation = config('implementation', default='sqlite')
    if config('conninfo', default='') or config('connect_kwargs', default=None):
        raise ValueError('Use connection or legacy conninfo/connect_kwargs, not both')
    options = dict(read('options') or {})
    fields = ('connect_timeout', 'application_name', 'sslmode', 'sslrootcert',
              'options', 'timeout', 'cached_statements', 'foreignKeys')
    driver_options = {field: value for field in fields
                      if (value := read(f'options.driver.{field}')) is not None}
    if driver_options:
        if options:
            raise ValueError('Use connection.options().driver() or legacy options, not both')
        options = driver_options
    reserved = {'dbname', 'host', 'port', 'user', 'password'} & options.keys()
    if reserved:
        raise ValueError('Connection fields must be declared directly, not inside options')
    database = read('database')
    dsn = read('dsn')
    connection_node = (config.builder.source.get_node(f'{config.root_label}.{prefix}')
                       if isinstance(config, ConfigHandler) else None)
    explicit_database = connection_node is not None and 'database' in connection_node.attr
    explicit_dsn = connection_node is not None and 'dsn' in connection_node.attr
    if explicit_database and database is None:
        raise ValueError('connection.database must resolve to a nonempty database name')
    if explicit_dsn and dsn is None:
        raise ValueError('connection.dsn must resolve to a nonempty string')
    if (database is not None or dsn is not None) and implementation != config('implementation', default='sqlite'):
        raise ValueError('Named connections must use the database dialect')
    if dsn is not None:
        if database is not None or any(read(field) is not None
                                       for field in ('host', 'port', 'user', 'password')):
            raise ValueError('dsn and individual connection fields cannot be combined')
        if not isinstance(dsn, str) or not dsn.strip():
            raise ValueError('connection.dsn must resolve to a nonempty string')
        if implementation.partition(':')[0] not in ('postgres', 'postgres3'):
            raise ValueError('dsn requires a PostgreSQL connection')
        return implementation, dsn, options
    name = database if database is not None else name
    if not isinstance(name, str) or not name.strip():
        raise ValueError('connection.name must resolve to a nonempty database name')
    options['dbname'] = name
    if implementation.partition(':')[0] == 'sqlite':
        if any(read(key) is not None
               for key in ('host', 'port', 'user', 'password')):
            raise ValueError('SQLite uses a filename, not host/user/password/port')
        if set(options) - {'dbname', 'timeout', 'cached_statements', 'foreignKeys'}:
            raise ValueError('Unsupported SQLite connection options')
        return implementation, '', options
    for name in ('host', 'port', 'user', 'password'):
        value = read(name)
        if value is not None:
            expected = int if name == 'port' else str
            if not isinstance(value, expected) or isinstance(value, bool):
                raise ValueError(f'connection.{name} resolved to an invalid type')
            options[name] = value
    if options.get('autocommit'):
        raise ValueError('Asqueel requires transactional connections, not autocommit')
    return implementation, '', options


def build_database(source, *, parents=None, environment=None):
    """Compatibility factory; new application code can instantiate AsqueelDb."""
    from .application import AsqueelDb
    return AsqueelDb(source, parents=parents, environment=environment)


def _effective_model_builder(config):
    """Apply signature defaults and Builders' renderer semantics on an owned source."""
    builder = _copy_recipe(config.builder)
    for _, node in builder.source.query('#p,#n', deep=True, iter=True):
        current = node
        while current is not None and current.node_tag != 'connection':
            current = current.parent_node
        if current is not None:
            continue
        owner = (node.parent_bag._builder if node._get_meta('subbuilder')
                 else node._resolve_builder())
        info = owner._get_schema_info(node.node_tag)
        signature_defaults = []
        for name, (_, _, default) in (info.get('call_args_validations') or {}).items():
            if (name in node.attr or default is inspect.Parameter.empty or default is None
                    or node.node_tag == 'validation'):
                continue
            # indexed is a physical-FK default. Materializing it on a logical
            # relation would turn an omitted option into a forbidden declaration.
            if (node.node_tag == 'relation' and name == 'indexed'
                    and not node.attr.get('foreign_key')):
                continue
            node.attr[name] = deepcopy(default)
            signature_defaults.append(name)
        if signature_defaults:
            node.attr.setdefault('_meta', {})['signature_defaults'] = signature_defaults
        # Administrative root attributes belong to connection_settings, not the model.
        if node.node_tag == 'db':
            for name in ('conninfo', 'connect_kwargs'):
                node.attr.pop(name, None)
        _, values = owner.runtime_values(node)
        meta = node.attr.get('_meta')
        node.attr.clear()
        node.attr.update(deepcopy(values))
        if meta is not None:
            node.attr['_meta'] = meta
    return builder
