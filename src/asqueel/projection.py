"""Explicit bridge from resolved names to the existing migration grammar."""
from __future__ import annotations

from .builder import SqlBuilder
from .common import sql_column_attributes
from .object_tree import DbModel


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


def _column_storage(column, *, packaged, implementation=None):
    metadata = column.attributes
    kwargs = {k: metadata[k] for k in ('size', 'notnull', 'unique', 'indexed', 'comment')
              if metadata.get(k) is not None}
    kwargs.update(sql_column_attributes(metadata, implementation))
    dtype = (_package_storage(column.dtype, kwargs)
             if packaged else column.dtype)
    return dtype, kwargs


def to_physical_builder(model: DbModel) -> SqlBuilder:
    """Project the single live model to a physical builder."""
    if not isinstance(model, DbModel):
        raise TypeError('to_physical_builder requires DbModel')
    from .object_tree_projection import project_tree
    return project_tree(model)
