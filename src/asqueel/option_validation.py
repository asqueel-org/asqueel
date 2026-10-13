"""Syntax validation only: no model expansion, provider lookup or I/O."""
from __future__ import annotations

import math
from genro_bag import BagResolver

from .option_elements import TABLE_OPTIONS, NAMED_OPTIONS

REQUIRED = {
    'relative_index': ('relation',),
    'audit': ('mode',), 'system_records': ('records',),
    'release': ('handlers',), 'partition': ('field',),
    'retention': ('field', 'days'),
    'enabled_when': ('preference',), 'attachments': ('master',),
}


def option_label(tag, attributes):
    key = NAMED_OPTIONS.get(tag)
    return f'{tag}_{attributes[key]}' if key else tag


def source_payload(value, path):
    if isinstance(value, BagResolver):
        return  # Preserve existing resolvers without calling or serializing them.
    if value is None or type(value) in (str, bool, int):
        return
    if isinstance(value, float) and math.isfinite(value):
        return
    if isinstance(value, (list, tuple)):
        for item in value:
            source_payload(item, path)
        return
    if isinstance(value, dict) and all(isinstance(k, str) for k in value):
        for key, item in value.items():
            source_payload(item, f'{path}.{key}')
        return
    raise ValueError(f'{path}: expected source data or BagResolver, not bare callbacks or live objects')


def nonempty(value, path):
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f'{path}: expected a nonempty string')


def names(value, path, *, hierarchical=False):
    if value is None:
        return
    items = value.split(',') if isinstance(value, str) else value
    if not isinstance(items, (list, tuple)):
        raise ValueError(f'{path}: expected field names')
    seen = set()
    for item in items:
        if hierarchical and isinstance(item, dict):
            if set(item) - {'name', 'unique'} or 'name' not in item:
                raise ValueError(f'{path}: hierarchical columns accept only name and unique')
            if 'unique' in item and not isinstance(item['unique'], bool):
                raise ValueError(f'{path}: unique requires bool')
            item = item['name']
        nonempty(item, path)
        if item.strip() in seen:
            raise ValueError(f'{path}: duplicate field {item!r}')
        seen.add(item.strip())


def validate_option(tag, parent, attributes):
    if tag not in TABLE_OPTIONS:
        return
    if parent is not None and parent.node_tag == 'column':
        if tag != 'dynamic_fields':
            raise ValueError(f'{tag}: option is not available at this level')
        existing = parent.value.get_node('dynamic_fields') if parent.value is not None else None
    else:
        existing = parent.value.get_node(option_label(tag, attributes)) if parent.value is not None else None
    spec = {**(existing.attr if existing is not None else {}), **attributes}
    if spec.get('enabled', True):
        required = REQUIRED.get(tag, ())
        if tag == 'dynamic_fields' and parent.node_tag == 'column':
            required = ('source',)
        for key in required:
            if spec.get(key) is None or spec[key] == '' or spec[key] == [] or spec[key] == ():
                raise ValueError(f'{tag}.{key}: required when enabled')
    for key in ('master', 'linked_to', 'preference',
                'field', 'parent', 'version_field', 'relation', 'source', 'caption_field', 'masterfield'):
        if spec.get(key) is not None:
            nonempty(spec[key], f'{tag}.{key}')
    for key in ('enabled', 'required', 'root_id', 'virtual_roots'):
        if key in spec and not isinstance(spec[key], bool):
            raise ValueError(f'{tag}.{key}: expected bool')
    for key in ('days', 'depth'):
        if spec.get(key) is not None and (type(spec[key]) is not int or spec[key] < (1 if key == 'depth' else 0)):
            raise ValueError(f'{tag}.{key}: expected {"positive" if key == "depth" else "nonnegative"} integer')
    for key in ('columns', 'scope'):
        names(spec.get(key), f'{tag}.{key}', hierarchical=tag == 'hierarchical' and key == 'columns')
    if spec.get('rules') is not None:
        for rule in spec['rules']:
            if not isinstance(rule, BagResolver):
                nonempty(rule, f'{tag}.rules')
    if spec.get('records') is not None:
        for code, record in spec['records'].items():
            nonempty(code, f'{tag}.records')
            if not isinstance(record, (dict, str, BagResolver)):
                raise ValueError('system_records.records: expected values mapping, reference or BagResolver')
            if isinstance(record, str):
                nonempty(record, f'{tag}.records.{code}')
    if spec.get('handlers') is not None:
        for version, handler in spec['handlers'].items():
            if not isinstance(version, str) or not version.isdecimal():
                raise ValueError('release.handlers: keys must be version numbers written as strings')
            if not isinstance(handler, BagResolver):
                nonempty(handler, 'release.handlers')
    if tag == 'dynamic_fields':
        if parent.node_tag == 'column' and spec.get('templates') is not None:
            raise ValueError('column.dynamic_fields accepts source, not templates')
        if parent.node_tag == 'options' and spec.get('source') is not None:
            raise ValueError('table dynamic_fields accepts templates, not source')
    for key, value in spec.items():
        if key != '_meta':
            source_payload(value, f'{tag}.{key}')
