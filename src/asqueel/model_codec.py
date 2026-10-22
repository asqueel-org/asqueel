"""Portable hierarchical model data, without connections or executable objects."""
from __future__ import annotations

from collections.abc import Mapping
import json

from genro_bag import Bag, BagNode

from .object_tree import DbModel, DbColumnObj, _Fragment


def _value(value):
    if isinstance(value, Mapping):
        if any(not isinstance(key, str) for key in value):
            raise TypeError('Model mappings require string keys')
        return {key: _value(item) for key, item in value.items()}
    if isinstance(value, (tuple, list)):
        return [_value(item) for item in value]
    if value is None or isinstance(value, (str, bool, int, float)):
        return value
    raise TypeError(f'Model export requires symbolic data, not {type(value).__name__}')


def _node(node):
    defaults = ((node.structnode.attr.get('_meta') or {}).get('signature_defaults', ())
                if node.structnode is not None else ())
    return dict(name=node.name, tag=node.tag, attributes=_value(node.attributes),
                children=[_node(child) for child in node.values()],
                signatureDefaults=list(defaults), generated=node.structnode is None,
                physicalColumn=type(node) is DbColumnObj)


def _relations(model):
    return [dict(path=f'{package.label}.{table.label}.{relation.label}',
                 attributes=_value(dict(relation.attr)))
            for package in model.relations for table in package.value for relation in table.value]


def model_to_json(model: DbModel, *, indent=2) -> str:
    if not isinstance(model, DbModel):
        raise TypeError('model_to_json requires DbModel')
    document = dict(format='asqueel-model', version=2,
                    database=_node(model._database), namespaces=_node(model.obj),
                    relations=_relations(model))
    # Configuration (including credentials) never enters this envelope.
    for key in ('conninfo', 'connect_kwargs'):
        document['database']['attributes'].pop(key, None)
    return json.dumps(document, ensure_ascii=False, allow_nan=False, indent=indent) + '\n'


def _fragment(data):
    required = {'name', 'tag', 'attributes', 'children', 'signatureDefaults', 'generated', 'physicalColumn'}
    if (not isinstance(data, dict) or set(data) != required
            or not isinstance(data['name'], str) or not isinstance(data['tag'], str)
            or not isinstance(data['attributes'], dict) or not isinstance(data['children'], list)
            or not isinstance(data['signatureDefaults'], list)
            or any(not isinstance(x, str) for x in data['signatureDefaults'])
            or type(data['generated']) is not bool or type(data['physicalColumn']) is not bool):
        raise ValueError('Invalid hierarchical model node')
    attributes = data['attributes']
    if any(key in attributes for key in ('x_table_class', 'conninfo', 'connect_kwargs')):
        raise ValueError('Runtime classes and connection configuration are not model data')
    node = None if data['generated'] else BagNode(None, data['name'], attr={
        **attributes, '_meta': {'signature_defaults': data['signatureDefaults']}}, node_tag=data['tag'])
    return _Fragment(data['name'], data['tag'], attributes,
                     tuple(_fragment(child) for child in data['children']), node, data['physicalColumn'])


def model_from_json(document: str) -> DbModel:
    data = json.loads(document, parse_constant=lambda value: (_ for _ in ()).throw(ValueError(f'Invalid number: {value}')))
    if (not isinstance(data, dict) or set(data) != {'format', 'version', 'database', 'namespaces', 'relations'}
            or data['format'] != 'asqueel-model' or type(data['version']) is not int or data['version'] != 2):
        raise ValueError('Unsupported hierarchical model format/version')
    database, namespaces = _fragment(data['database']), _fragment(data['namespaces'])
    if database.tag != 'db' or namespaces.tag not in ('schemas', 'packages'):
        raise ValueError('Expected a database and its namespaces')
    root = _Fragment(database.name, database.tag, database.attributes,
                     (*database.children, namespaces), database.node)
    model = DbModel(root, source=Bag())
    if _relations(model) != data['relations']:
        raise ValueError('Relation registry does not match the model declarations')
    return model
