"""Materialize SQL configuration into a context-owned application object."""
from genro_builders.renderer import RendererBase

from .configuration import _effective_model_builder, _owned_handler
from .model import resolve_model


class SqlObjectRenderer(RendererBase):
    """Resolve the complete graph before publishing its live database facade."""

    mode = 'objects'
    render_type = 'object'

    def render_children(self, nodes, *, config=None, driver=None, dialect=None,
                        environment=None, **opts):
        # Relations require the complete model, so materialize the document once,
        # rather than publishing partially initialized objects during a node walk.
        from .application import SqlDatabase
        config = config if config is not None else _owned_handler(self.builder)
        model = resolve_model(_effective_model_builder(config))
        return [SqlDatabase(model=model, config=config, driver=driver,
                            dialect=dialect, environment=environment)]

    def finalize(self, result, target=None, **opts):
        if target is not None:
            raise ValueError('SQL object rendering returns its database; targets are unsupported')
        if len(result) != 1:
            raise ValueError('SQL object rendering requires exactly one database')
        return result[0]
