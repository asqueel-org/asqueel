"""Explicit bridge from resolved names to the existing migration grammar."""
from __future__ import annotations

from .builder import SqlBuilder
from .common import sql_column_attributes
from .contracts import UnsupportedFeatureError
from .object_tree import DbModel


_ACTIONS = {'a': 'no action', 'r': 'restrict', 'c': 'cascade', 'n': 'setnull', 'd': 'setdefault'}


def _package_storage(dtype, attributes):
    """Legacy logical types -> storage; never change the resolved column."""
    dtype = {'X': 'T', 'Z': 'T', 'P': 'T'}.get(dtype, dtype)
    size = attributes.get('size')
    if size:
        if ':' in size:
            attributes['size'] = '0:' + size.split(':')[1]
            dtype = 'A'
        elif ',' not in size:
            if dtype in ('A', 'T'):
                dtype = 'C'
            elif dtype == 'N':
                attributes['size'] = size + ',0'
    elif dtype in ('A', 'C'):
        dtype = 'T'
    return dtype


def _column_storage(column, *, path, packaged, implementation=None):
    metadata = column.attributes
    if metadata.get('identity_kind') or metadata.get('generated'):
        raise UnsupportedFeatureError(f'{path}: identity/generated DDL')
    if metadata.get('default_collation') is False:
        raise UnsupportedFeatureError(f'{path}: custom column collation')
    if metadata.get('owned_sequence') or metadata.get('sequence_default'):
        raise UnsupportedFeatureError(f'{path}: sequence ownership/default not modeled')
    raw = metadata.get('raw_type', '')
    if raw in {'smallint', 'real'} or (raw.startswith(('time', 'timestamp')) and '(' in raw):
        raise UnsupportedFeatureError(f'{path}: lossy type projection {raw}')
    kwargs = {k: metadata[k] for k in ('size', 'notnull', 'unique', 'indexed', 'comment')
              if metadata.get(k) is not None}
    kwargs.update(sql_column_attributes(metadata, implementation))
    if metadata.get('catalog_default') is not None and metadata.get('raw_type'):
        kwargs['sql_default'] = metadata['catalog_default']
    dtype = (_package_storage(column.dtype, kwargs)
             if packaged else column.dtype)
    return dtype, kwargs


def _constraint_index_feature(item):
    """The first introspected property of a constraint-owned index the builder cannot declare."""
    checks = [
        ('storage options', item.get('options')),
        ('a tablespace', item.get('tablespace')),
        ('included columns', len(item.get('columns', ())) != item.get('key_count')),
        (f'method {item.get("method")}', item.get('method') != 'btree'),
        ('non-default operator classes', item.get('default_opclasses') is False),
        ('non-default collations', item.get('default_collations') is False),
        ('non-default ordering', any(v != 0 for v in item.get('ordering', ()))),
        ('NOT VALID', item.get('valid') is False),
        ('NULLS NOT DISTINCT', item.get('nulls_not_distinct')),
    ]
    return next((name for name, present in checks if present), None)


def _index_feature(item):
    """The first introspected property of an index the builder cannot declare."""
    columns = item['columns']
    checks = [
        ('expression columns', not all(columns)),
        ('included columns', len(columns) != item['key_count']),
        ('NULLS FIRST/LAST ordering', any(v not in (0, 3) for v in item['ordering'])),
        ('non-default operator classes', not item['default_opclasses']),
        ('non-default collations', not item['default_collations']),
        ('NOT VALID', not item['valid']),
        ('NULLS NOT DISTINCT', item['nulls_not_distinct']),
        ('storage options', item['options']),
        ('a tablespace', item['tablespace']),
    ]
    return next((name for name, present in checks if present), None)


def to_physical_builder(model: DbModel, *, allow_constraint_rename=False) -> SqlBuilder:
    """Project the single live model, preserving catalog fidelity checks."""
    if not isinstance(model, DbModel):
        raise TypeError('to_physical_builder requires DbModel')
    from .catalog_model import validate_catalog_projection
    from .object_tree_projection import project_tree
    validate_catalog_projection(model, allow_constraint_rename=allow_constraint_rename)
    return project_tree(model)
