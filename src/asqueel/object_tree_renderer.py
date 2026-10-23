"""Hierarchical object construction over RendererBase's unmodified walk."""
from copy import deepcopy

from genro_builders.renderer import RendererBase

from .model_source import prepare_source
from .object_tree import DbModel, _Fragment


def prepare_render_source(renderer):
    """The prepared, validated copy of the renderer's composed recipe, without connection nodes.

    Every renderer of the source starts from it, so options and package rules
    act the same way for the live model and for the migration structure. The
    composed recipe the database keeps is not mutated.
    """
    db = renderer.builder.source.get_node('db')
    connection = db.value.get_node('connection') if db.value is not None else None
    implementation = ((connection.get_attr('implementation') if connection is not None else None)
                      or db.get_attr('implementation') or 'sqlite')
    prepared = prepare_source(renderer.builder, implementation=implementation, options_first=True)
    prepared.validate_model()
    root = prepared.source.get_node('db').value
    for node in list(root or ()):
        if node.node_tag == 'connection':
            root.pop_node(node.label)
    renderer.add_render(prepared, renderer)
    # Mounted SQL grammars supply their own defaults and node semantics.
    # Their nodes are rendered by the same renderer, not by a renderer of their own.
    for _, node in prepared.source.query('#p,#n', deep=True):
        renderer.add_render(node.builder, renderer)
    return prepared.source


class SqlObjectRenderer(RendererBase):
    mode = 'objects'
    render_type = 'object'

    def preprocess(self, source):
        return prepare_render_source(self)

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
        from .application import AsqueelDb
        if not isinstance(target, AsqueelDb):
            raise TypeError('Object rendering builds the model into a database: use AsqueelDb(recipe)')
        fragments = result if isinstance(result, list) else [result]
        if len(fragments) != 1 or fragments[0].tag != 'db':
            raise ValueError('Object rendering requires exactly one database root')
        # Objects are constructed here, parent before children. The base walk
        # collected fragments only and has not initialized any model object.
        # Builders may use different renderer instances for materialize/finalize.
        # The fragment retains its owned source; finalize needs no walk state.
        target.model = DbModel(target)
        target.model.build(fragments[0])
        return target
