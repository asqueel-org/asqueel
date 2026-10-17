"""Optional, offline adapter for an *expanded* GenroPy model source.

This adapter imports no GenroPy code and never opens a connection. It consumes
source XML, not an extracted database schema. Legacy expansion is a prerequisite:
provider behavior is retained as metadata and is not executable by this adapter.
"""
from __future__ import annotations

from copy import deepcopy
from genro_bag import Bag

from .configuration import SqlDatabaseConfig


def from_expanded_legacy_xml(document: str, *, name: str = 'database', type_aliases=None):
    source = Bag.from_xml(document)
    packages = source.get_item('packages')
    if not isinstance(packages, Bag) or not len(packages):
        raise ValueError('Expected an expanded legacy source with packages')
    builder = SqlDatabaseConfig()
    db = builder.source.db(name, x_legacy_expanded=True)
    pending_relations = []
    for package in packages:
        attrs = dict(package.attr)
        schema = attrs.get('sqlschema') or 'public'
        pkg = db.packages().package(package.label, sqlschema=schema,
                sqlprefix=attrs.get('sqlprefix', True), **{f'x_legacy_{key}': value for key, value in attrs.items()})
        for alias_name, spec in (type_aliases or {}).get(package.label, {}).items():
            # The captured adapter profile predates flat namespace attributes.
            # Translate that fixture at this boundary; keep the oracle unchanged.
            spec = dict(spec)
            spec.update({f'x_ui_{key}': value for key, value in spec.pop('x_ui', {}).items()})
            pkg.options().type(alias_name, **spec)
        for original in package.value.get_item('tables') or ():
            raw = dict(original.attr)
            t = pkg.table(original.label, **_selected(raw, ('pkey', 'name_long', 'name_short',
                    'name_plural', 'caption_field', 'sqlname')), **{f'x_legacy_{key}': value for key, value in raw.items()},
                    x_expanded_legacy=True)
            for column in original.value.get_item('columns') or ():
                data = dict(column.attr)
                physical = _selected(data, ('dtype', 'size', 'notnull', 'unique', 'sqldefault',
                                            'sqlname', 'extra_sql', 'generated_expression', 'default',
                                            'name_long', 'name_short', 'group'))
                if physical.get('size') is not None:
                    physical['size'] = str(physical['size'])
                _normalize_physical(physical)
                # Runtime defaults/hooks are deliberately not SQL defaults.
                embedded = {key: value for key, value in data.items()
                    if key.startswith('validate_')}
                if isinstance(embedded.get('validate_notnull'), str):
                    embedded['validate_notnull'] = bool(embedded['validate_notnull'])
                c = t.column(column.label, **physical, **embedded, **{f'x_legacy_{key}': value for key, value in data.items()})
                if data.get('indexed') and not data.get('unique') and column.label not in (raw.get('pkey') or '').split(','):
                    _index(t, column.label, data['indexed'])
                for rel in column.value or ():
                    if rel.label != 'relation':
                        raise ValueError(f'{package.label}.{original.label}.{column.label}: unknown child {rel.label}')
                    pending_relations.append((package.label, t, c, rel))
            for column in original.value.get_item('virtual_columns') or ():
                data = dict(column.attr)
                common = {**{f'x_legacy_{key}': value for key, value in data.items()},
                          **_selected(data, ('name_long', 'name_short', 'group'))}
                if data.get('composed_of'):
                    common.pop('group', None)
                if data.get('composed_of'):
                    c = t.compositeColumn(column.label, columns=data['composed_of'],
                                          unique=data.get('unique', False), **common)
                    for rel in column.value or ():
                        pending_relations.append((package.label, t, c, rel))
                elif data.get('join_column'):
                    rel = column.value.get_node('relation')
                    if rel is None:
                        raise ValueError(f'{column.label}: join_column needs relation')
                    target = _target(package.label, rel.attr['related_column'])
                    t.virtualRelation(column.label, table='.'.join(target.split('.')[:2]),
                        condition=rel.attr.get('cnd'),
                        **{f'x_legacy_{key}': value for key, value in dict(rel.attr).items()})
                    t.aliasColumn(column.label, relation_path='@' + column.label + '.' + target.split('.')[-1], **common)
                elif data.get('relation_path'):
                    t.aliasColumn(column.label, relation_path=data['relation_path'], **common)
                elif any(k in data for k in ('sql_formula', 'select', 'exists')):
                    t.formulaColumn(column.label, **_selected(data, ('sql_formula', 'select', 'exists')),
                                    **common)
                else:
                    t.pyColumn(column.label, method=data.get('py_method') or 'pyColumn_' + column.label,
                               **common)
            for alias in original.value.get_item('table_aliases') or ():
                t.virtualRelation(alias.label.lstrip('@'), relation=alias.attr['relation_path'],
                                  **{f'x_legacy_{key}': value for key, value in dict(alias.attr).items()})
            for subtable in original.value.get_item('subtables') or ():
                t.subtable(subtable.label, condition=subtable.attr['condition'],
                           **{f'x_legacy_{key}': value for key, value in dict(subtable.attr).items()})
            # Legacy table indexes are descriptive source declarations; retain them.
            # OrmExtractor's physical contract projects column/composite indexes only.
            if original.value.get_item('indexes'):
                for idx in original.value['indexes']:
                    for key, value in idx.attr.items():
                        t.attr[f'x_legacy_index_{idx.label}_{key}'] = deepcopy(value)
            unknown = set(original.value.keys()) - {'columns', 'virtual_columns', 'indexes', 'subtables', 'table_aliases'}
            if unknown:
                raise ValueError(f'{package.label}.{original.label}: unhandled sections {sorted(unknown)}')
    for package, table, column, rel in pending_relations:
        data = dict(rel.attr)
        kwargs = {'to': _target(package, data['related_column']),
                  'inverse': data.get('relation_name'), 'one_one': bool(data.get('one_one')),
                  **{f'x_legacy_{key}': value for key, value in data.items()}}
        for source_key, dest in (('onDelete', 'on_delete'), ('onDelete_sql', 'on_delete_sql'),
                                ('onUpdate_sql', 'on_update_sql'), ('onDuplicate', 'on_duplicate')):
            if data.get(source_key) is not None:
                kwargs[dest] = {'setnull': 'set_null', 'setdefault': 'set_default'}.get(data[source_key], data[source_key])
        if isinstance(kwargs.get('on_duplicate'), bool):
            kwargs['on_duplicate'] = 'copy' if kwargs['on_duplicate'] else 'ignore'
        if data.get('mode') == 'foreignkey':
            kwargs['deferred'] = bool(data.get('deferred', data.get('onDelete') == 'setnull' or data.get('onDelete_sql') == 'setnull'))
            column.relation(**kwargs)
        else:
            column.relation(foreign_key=False, x_weak=True, **kwargs)
            if column.node_tag == 'compositeColumn' and not column.get_attr('unique'):
                _index(table, column.get_attr('columns'), True)
    return builder


def _selected(mapping, names):
    return {key: deepcopy(mapping[key]) for key in names if key in mapping}


def _target(package, target):
    return target if len(target.split('.')) == 3 else package + '.' + target


def _index(table, columns, spec):
    data = {} if spec is True else dict(spec)
    sorting = data.pop('sorting', None)
    names = columns.split(',')
    members = dict(zip(names, sorting.split(',') if sorting else [None] * len(names)))
    with_options = {key[5:]: data.pop(key) for key in list(data) if key.startswith('with_')}
    if with_options:
        data['with_options'] = with_options
    table.index(columns=members, **data)


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
