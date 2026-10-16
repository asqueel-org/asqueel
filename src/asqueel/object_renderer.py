"""Operational output of the single hierarchical object renderer."""
from .configuration import _owned_handler
from .object_tree_renderer import SqlObjectTreeRenderer


class SqlObjectRenderer(SqlObjectTreeRenderer):
    mode = 'objects'

    def finalize(self, result, target=None, *, config=None, driver=None, dialect=None,
                 environment=None, **opts):
        from .application import SqlDatabase
        model = super().finalize(result, target=target, **opts)
        config = config if config is not None else self.config
        if config is None:
            # Builders can use separate renderer instances for walk and delivery.
            config = _owned_handler(self.builder)
        return SqlDatabase(model=model, config=config, driver=driver,
                           dialect=dialect, environment=environment)
