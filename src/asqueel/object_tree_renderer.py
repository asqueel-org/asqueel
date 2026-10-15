"""Alternative object construction over RendererBase's unmodified walk."""
from copy import deepcopy

from genro_builders.renderer import RendererBase

from .configuration import _effective_model_builder, _owned_handler
from .model_source import prepare_source
from .object_tree import DbModel, _Fragment


class SqlObjectTreeRenderer(RendererBase):
    mode = 'objects_tree'
    render_type = 'object'

    def preprocess(self, source):
        # Reuse the agreed source expansions, not resolve_model or SqlDatabase.
        # Work on an owned recipe: neither render can mutate the authored source.
        self.config = _owned_handler(self.builder)
        self.prepared = prepare_source(_effective_model_builder(self.config), options_first=True)
        self.prepared.validate_model()
        root = self.prepared.source.get_node('db').value
        for node in list(root):
            if node.node_tag == 'connection':
                root.pop_node(node.label)
        self.add_render(self.prepared, self)
        # Mounted SQL grammars supply their own defaults and node semantics.
        # Their nodes use this object output mode too, not a string renderer.
        for _, node in self.prepared.source.query('#p,#n', deep=True):
            self.add_render(node.builder, self)
        return self.prepared.source

    def rendered_item(self, node, item, runtime_attrs, *, tag, **opts):
        children = list(item) if isinstance(item, list) else []
        # Options have already produced their structural effects in preprocess.
        # Retain their declarations first, then consume only the other children;
        # the generic walk never applies an option a second time.
        options = next((child for child in children if child.tag == 'options'), None)
        if options is not None:
            children.remove(options)
            children.insert(0, options)
        return _Fragment(node.label, tag, deepcopy(runtime_attrs), tuple(children), node,
                         physical_column=bool(node._get_meta('projects_column')))

    def finalize(self, result, target=None, **opts):
        if target is not None:
            raise ValueError('Object tree rendering returns its model; targets are unsupported')
        fragments = result if isinstance(result, list) else [result]
        if len(fragments) != 1 or fragments[0].tag != 'db':
            raise ValueError('Object tree rendering requires exactly one database root')
        # Objects are constructed here, parent before children. The base walk
        # collected fragments only and has not initialized any model object.
        # Builders may use different renderer instances for materialize/finalize.
        # The fragment retains its owned source; finalize needs no walk state.
        return DbModel(fragments[0], source=fragments[0].node.parent_bag)
