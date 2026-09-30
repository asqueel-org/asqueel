"""Owned, layered SQL application configuration using Builders' read stack."""
from __future__ import annotations

from copy import deepcopy

from genro_builders.builder import BuilderBase, element
from genro_builders.contrib.config import ConfigBuilder, ConfigHandler

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

    @element(sub_tags='schemas[:1], extensions[:1]', node_label='db')
    def db(self, name: str, implementation: str = 'postgresql', conninfo: str = '',
           connect_kwargs: dict | None = None):
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
    return ConfigHandler(own(source), parents=[own(item) for item in (parents or ())])


def build_database(source, *, parents=None, driver=None, dialect=None, environment=None):
    """Build a live SQL application without connecting or applying migrations.

    Recipe instances are copied before ConfigHandler merges parent layers.
    Paths and recipe classes are instantiated by ConfigHandler itself.
    """
    from .object_renderer import SqlObjectRenderer
    config = _owned_handler(source, parents)
    renderer = SqlObjectRenderer(config.builder)
    result = renderer.render_children(config.builder.source, config=config,
                                      driver=driver, dialect=dialect, environment=environment)
    return renderer.finalize(result, None)


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
