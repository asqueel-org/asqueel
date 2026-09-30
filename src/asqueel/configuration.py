"""Owned, layered SQL application configuration using Builders' read stack."""
from __future__ import annotations

from copy import deepcopy
from contextlib import contextmanager
from pathlib import Path
import sys

from genro_builders.builder import BuilderBase, element
from genro_builders.contrib.config import ConfigBuilder, ConfigHandler
from genro_bag import BagResolver

from .builder import SqlBuilder

_MISSING = object()


class ConfigurationView:
    """A relative read view over one ConfigHandler, without copied attributes."""

    def __init__(self, handler: ConfigHandler, prefix: str = '', *, fallback=None):
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

    @element(sub_tags='connection[:1], schemas[:1], extensions[:1]', node_label='db')
    def db(self, name: str = 'db', implementation: str = 'postgresql', conninfo: str = '',
           connect_kwargs: dict | None = None):
        ...

    @element(parent_tags='db', sub_tags='', node_label='connection')
    def connection(self, name: str | BagResolver, implementation: str = 'postgresql',
                   host: str | BagResolver | None = None,
                   port: int | BagResolver | None = None,
                   user: str | BagResolver | None = None,
                   password: str | BagResolver | None = None,
                   options: dict | None = None):
        """Single connection configuration; name is the physical database name."""
        ...


class SqlDatabaseConfig(SqlDatabaseElements, SqlBuilder, ConfigBuilder):
    """SQL application recipe: model grammar plus connection configuration."""

    _default_render_mode = 'objects'

    @property
    def renderer_objects(self):
        from .object_renderer import SqlObjectRenderer
        return SqlObjectRenderer(self)


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
        return ConfigHandler(own(sources[-1]), parents=[own(item) for item in sources[:-1]])


def configuration_source(source):
    """Resolve a registered name, a recipe path/directory or a Python class."""
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


def connection_settings(config):
    """Read standard config attributes, resolving EnvResolver via ConfigHandler."""
    implementation = config('connection.implementation', default=None)
    if implementation is None:
        return (config('implementation', default='postgresql'),
                config('conninfo', default=''), config('connect_kwargs', default=None))
    if config('conninfo', default='') or config('connect_kwargs', default=None):
        raise ValueError('Use connection or legacy conninfo/connect_kwargs, not both')
    options = dict(config('connection.options', default=None) or {})
    reserved = {'dbname', 'host', 'port', 'user', 'password'} & options.keys()
    if reserved:
        raise ValueError('Connection fields must be declared directly, not inside options')
    name = config('connection.name', default=None)
    if not isinstance(name, str) or not name.strip():
        raise ValueError('connection.name must resolve to a nonempty database name')
    options['dbname'] = name
    for name in ('host', 'port', 'user', 'password'):
        value = config(f'connection.{name}', default=None)
        if value is not None:
            expected = int if name == 'port' else str
            if not isinstance(value, expected) or isinstance(value, bool):
                raise ValueError(f'connection.{name} resolved to an invalid type')
            options[name] = value
    if options.get('autocommit'):
        raise ValueError('Asqueel requires transactional connections, not autocommit')
    return implementation, '', options


def build_database(source, *, parents=None, driver=None, dialect=None, environment=None):
    """Compatibility factory; new application code can instantiate AsqueelDb."""
    from .application import AsqueelDb
    return AsqueelDb(source, parents=parents, driver=driver, dialect=dialect,
                     environment=environment)


def _effective_model_builder(config):
    """Resolve read-time signature defaults on a private model-only source."""
    builder = _copy_recipe(config.builder)
    for path, node in builder.source.query('#p,#n', deep=True, iter=True):
        owner = (node.parent_bag._builder if node._get_meta('subbuilder')
                 else node._resolve_builder())
        info = owner._get_schema_info(node.node_tag)
        relative = path.split('.', 1)[1] if '.' in path else ''
        for name in info.get('call_args_validations') or {}:
            # indexed is a physical-FK default. Materializing it on a logical
            # relation would turn an omitted option into a forbidden declaration.
            if (node.node_tag == 'relation' and name == 'indexed' and name not in node.attr
                    and not config(f'{relative}.foreign_key', default=False)):
                continue
            key = f'{relative}.{name}' if relative else name
            try:
                value = config(key)
            except KeyError:
                continue
            node.attr[name] = deepcopy(value)
    return builder
