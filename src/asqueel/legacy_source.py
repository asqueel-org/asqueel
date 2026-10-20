"""Optional, offline adapter for an *expanded* GenroPy model source.

This adapter imports no GenroPy code and never opens a connection. It consumes
source XML, not an extracted database schema. Legacy expansion is a prerequisite:
provider behavior is retained as metadata and is not executable by this adapter.
"""
from __future__ import annotations

from copy import deepcopy
from genro_bag import Bag

from .common import in_attribute_family, indexed_attributes, split_names
from .configuration import SqlDatabaseConfig
from .contracts import not_available



def from_expanded_legacy_xml(document: str, *, name: str = 'database', type_aliases=None):
    """Build an asqueel source from an expanded legacy source.

    Each legacy attribute is either consumed by this loader (structure, the
    kind of a virtual column) or passed to the element that declares it.

    Raises:
        ValueError: on the first legacy attribute that is neither, naming it
            and its element.
    """
    source = Bag.from_xml(document)
    packages = source.get_item('packages')
    if not isinstance(packages, Bag) or not len(packages):
        raise ValueError('Expected an expanded legacy source with packages')
    builder = SqlDatabaseConfig()
    db = builder.source.db(name)
    pending_relations = []
    for package in packages:
        attrs = _grammar(builder, 'package', package.label, package.attr, ('tag',))
        attrs.setdefault('sqlschema', 'public')
        pkg = db.packages().package(package.label, **attrs)
        for alias_name, spec in (type_aliases or {}).get(package.label, {}).items():
            pkg.options().type(alias_name, **_grammar(builder, 'type', f'{package.label}.{alias_name}', spec, ()))
        for original in package.value.get_item('tables') or ():
            raw = dict(original.attr)
            path = f'{package.label}.{original.label}'
            t = pkg.table(original.label,
                          **_grammar(builder, 'table', path, raw, ('tag', 'fullname', 'pkg')),
                          x_expanded_legacy=True)
            for column in original.value.get_item('columns') or ():
                data = dict(column.attr)
                physical = _grammar(builder, 'column', f'{path}.{column.label}', data, ('tag', 'indexed'))
                if physical.get('size') is not None:
                    physical['size'] = str(physical['size'])
                _normalize_physical(physical)
                if isinstance(physical.get('validate_notnull'), str):
                    physical['validate_notnull'] = bool(physical['validate_notnull'])
                index = None
                if data.get('indexed') and not data.get('unique') and column.label not in (raw.get('pkey') or '').split(','):
                    index = indexed_attributes([column.label], data['indexed'])
                    # legacy fill_json_column_index: unique without where is the column's own UNIQUE.
                    if index is None:
                        physical['unique'] = True
                c = t.column(column.label, **physical)
                if index is not None:
                    t.index(**index)
                for rel in column.value or ():
                    if rel.label != 'relation':
                        raise ValueError(f'{path}.{column.label}: unknown child {rel.label}')
                    pending_relations.append((package.label, t, c, rel))
            for column in original.value.get_item('virtual_columns') or ():
                data = dict(column.attr)
                label = f'{path}.{column.label}'
                if data.get('composed_of'):
                    common = _grammar(builder, 'compositeColumn', label, data,
                                      ('tag', 'virtual_column', 'composed_of', 'group'))
                    c = t.compositeColumn(column.label, columns=data['composed_of'], **common)
                    for rel in column.value or ():
                        pending_relations.append((package.label, t, c, rel))
                elif data.get('join_column'):
                    rel = column.value.get_node('relation')
                    if rel is None:
                        raise ValueError(f'{column.label}: join_column needs relation')
                    _grammar(builder, 'virtualRelation', f'{label}.relation', rel.attr,
                             ('tag', 'related_column', 'cnd'))
                    target = _target(package.label, rel.attr['related_column'])
                    t.virtualRelation(column.label, table='.'.join(target.split('.')[:2]),
                                      condition=rel.attr.get('cnd'))
                    t.aliasColumn(column.label, relation_path='@' + column.label + '.' + target.split('.')[-1],
                                  **_grammar(builder, 'aliasColumn', label, data,
                                             ('tag', 'virtual_column', 'join_column')))
                elif data.get('relation_path'):
                    t.aliasColumn(column.label, **_grammar(builder, 'aliasColumn', label, data,
                                                           ('tag', 'virtual_column')))
                elif any(k in data for k in ('sql_formula', 'select', 'exists')):
                    t.formulaColumn(column.label, **_grammar(builder, 'formulaColumn', label, data,
                                                             ('tag', 'virtual_column')))
                else:
                    common = _grammar(builder, 'pyColumn', label, data, ('tag', 'virtual_column', 'py_method'))
                    t.pyColumn(column.label, method=data.get('py_method') or 'pyColumn_' + column.label, **common)
            for alias in original.value.get_item('table_aliases') or ():
                _grammar(builder, 'virtualRelation', f'{path}.{alias.label}', alias.attr, ('tag', 'relation_path'))
                t.virtualRelation(alias.label.lstrip('@'), relation=alias.attr['relation_path'])
            for idx in original.value.get_item('indexes') or ():
                t.index(name=idx.label, **_grammar(builder, 'index', f'{path}.{idx.label}', idx.attr, ('tag',)))
            unknown = set(original.value.keys()) - {'columns', 'virtual_columns', 'indexes', 'table_aliases'}
            if unknown:
                raise ValueError(f'{path}: sections outside the asqueel grammar {sorted(unknown)}')
    for package, table, column, rel in pending_relations:
        data = dict(rel.attr)
        kwargs = {'to': _target(package, data['related_column']),
                  **_grammar(builder, 'relation', f'{column.fullpath}.relation', data,
                             ('tag', 'related_column', 'mode'))}
        if kwargs.get('one_one') != '*':
            kwargs['one_one'] = bool(kwargs.get('one_one'))
        if isinstance(kwargs.get('onDuplicate'), bool):
            kwargs['onDuplicate'] = 'copy' if kwargs['onDuplicate'] else 'ignore'
        if data.get('mode') == 'foreignkey':
            kwargs['deferred'] = bool(data.get('deferred', data.get('onDelete') == 'setnull' or data.get('onDelete_sql') == 'setnull'))
            column.relation(**kwargs)
        else:
            kwargs.pop('deferred', None)
            column.relation(foreign_key=False, x_weak=True, **kwargs)
            if column.node_tag == 'compositeColumn' and not column.get_attr('unique'):
                table.index(columns=dict.fromkeys(split_names(column.get_attr('columns'))))
    return builder


#: Legacy attributes of features absent from this release, refused by name as the grammar does.
_ABSENT_FEATURES = {'table': ('variant', 'mixin'), 'column': ('variant', 'localized', 'encrypted')}


def _grammar(builder, tag, path, attributes, consumed):
    """The legacy attributes element ``tag`` declares; raise on the first one neither declared nor consumed."""
    declared = builder._get_schema_info(tag).get('declared_names') or set()
    absent = _ABSENT_FEATURES.get(tag, ())
    for key in attributes:
        if key in absent or (absent and key.startswith('ext_')):
            raise not_available(f'{path}: {key}')
        if key not in consumed and key not in declared and not in_attribute_family(builder, tag, key):
            raise ValueError(f'{path}: legacy attribute {key!r} is outside the asqueel grammar')
    return {key: deepcopy(value) for key, value in attributes.items() if key not in consumed}


def _target(package, target):
    return target if len(target.split('.')) == 3 else package + '.' + target


def _normalize_physical(attributes):
    """Legacy storage semantics; logical metadata remains on the model column."""
    dtype = attributes.get('dtype')
    dtype = {'X': 'T', 'Z': 'T', 'P': 'T'}.get(dtype, dtype)
    size = attributes.get('size')
    if size:
        if ':' in size:
            attributes['size'] = '0:' + size.split(':')[1]
            dtype = 'A'
        elif ',' not in size:
            if dtype in (None, 'A', 'T'):
                dtype = 'C'
            elif dtype == 'N':
                attributes['size'] = size + ',0'
    elif dtype in ('A', 'C'):
        dtype = 'T'
    if dtype is not None:
        attributes['dtype'] = dtype
