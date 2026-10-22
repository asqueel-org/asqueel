"""Translate catalog rows into the same hierarchy as authored model declarations."""
from genro_bag import Bag, BagNode

from .contracts import UnsupportedFeatureError
from .object_tree import DbModel, _Fragment


def _fragment(name, tag, attributes=None, children=()):
    attributes = dict(attributes or {})
    node = BagNode(None, name, attr=attributes, node_tag=tag)
    return _Fragment(name, tag, attributes, tuple(children), node, tag == 'column')


def catalog_model(tables, *, name, warnings):
    # These are catalog records and declaration fragments, never a second model.
    keys, composites, owners = {}, {}, {}
    for key, table in tables.items():
        keys[key], composites[key] = {}, []
        owners[key] = {column: [] for column in table['columns']}

    def key_column(key, columns):
        columns = tuple(columns)
        if len(columns) == 1:
            return columns[0]
        if columns not in keys[key]:
            name = '_catalog_key_' + str(len(keys[key]))
            while name in owners[key]:
                name += '_'
            keys[key][columns] = name
            owners[key][name] = []
            composites[key].append((name, columns))
        return keys[key][columns]

    for key, table in tables.items():
        if table['pkey']:
            key_column(key, table['pkey'])
        for constraint in table['attributes']['constraints']:
            if constraint['kind'] != 'f':
                continue
            target = f"{constraint['target_schema']}.{constraint['target_table']}"
            if target not in tables:
                continue
            owner = key_column(key, constraint['columns'])
            # Multiple FKs on the same scalar need distinct declared owners.
            if owners[key][owner]:
                owner = '_catalog_fk_' + str(len(composites[key]))
                while owner in owners[key]:
                    owner += '_'
                composites[key].append((owner, tuple(constraint['columns'])))
                owners[key][owner] = []
            remote = key_column(target, constraint['target_columns'])
            from .projection import _ACTIONS
            attrs = dict(name=constraint['name'], to=f'{target}.{remote}',
                         foreign_key=True, indexed=False,
                         relation_name=f"{table['name']}_{constraint['name']}",
                         deferrable=constraint['deferrable'],
                         initially_deferred=constraint['initially_deferred'],
                         onDelete_sql=_ACTIONS[constraint['on_delete_code']],
                         onUpdate_sql=_ACTIONS[constraint['on_update_code']])
            owners[key][owner].append(_fragment(constraint['name'], 'relation', attrs))

    schemas = {}
    for key, table in tables.items():
        columns = []
        for column_name, column in table['columns'].items():
            attrs = {**column['attributes'], 'dtype': column['dtype'],
                     'ui': column['ui'], 'identity': column['identity']}
            default = attrs.pop('default', None)
            attrs['catalog_default'] = default
            if attrs.get('generated'):
                attrs['sql_generatedExpression'] = default
            elif default is not None:
                attrs['sql_default'] = default
            columns.append(_fragment(column_name, 'column', attrs, owners[key][column_name]))
        children = [_fragment('columns', 'columns', children=columns)]
        children.append(_fragment('composites', 'composites', children=[
            _fragment(n, 'compositeColumn', {'columns': ','.join(fields)}, owners[key][n])
            for n, fields in composites[key]]))
        constraints = [_fragment(c['name'], 'constraint',
                       {'constraint_type': 'UNIQUE', 'columns': ','.join(c['columns'])})
                       for c in table['attributes']['constraints'] if c['kind'] == 'u']
        children.append(_fragment('constraints', 'constraints', children=constraints))
        indexes = []
        from .projection import _index_feature
        for item in table['attributes']['indexes']:
            if item['primary'] or item['constraint_owned'] or _index_feature(item):
                continue
            attrs = {'columns': {n: 'DESC' if order == 3 else None
                                 for n, order in zip(item['columns'], item['ordering'])},
                     'unique': item['unique'], 'where': item['predicate'],
                     'method': None if item['method'] == 'btree' else item['method']}
            indexes.append(_fragment(item['name'], 'index', attrs))
        children.append(_fragment('indexes', 'indexes', children=indexes))
        attrs = {**table['attributes'], 'pkey': key_column(key, table['pkey']) if table['pkey'] else None}
        schemas.setdefault(table['schema'], []).append(_fragment(table['name'], 'table', attrs, children))
    namespaces = _fragment('schemas', 'schemas', children=[
        _fragment(schema, 'schema', children=[_fragment('tables', 'tables', children=items)])
        for schema, items in schemas.items()])
    root = _fragment(name, 'db', {'name': name, 'implementation': 'postgres',
                                 'catalog_warnings': tuple(warnings)}, [namespaces])
    return DbModel(root, source=Bag())


def validate_catalog_projection(model, *, allow_constraint_rename):
    """Refuse every lossy catalog projection even though SELECT remains usable."""
    from .projection import _constraint_index_feature, _index_feature
    if model.warnings:
        raise UnsupportedFeatureError('Incomplete model with import warnings cannot be projected: ' + '; '.join(model.warnings))
    for table in model.tables.values():
        for constraint in table.attributes.get('constraints', ()):
            kind = constraint.get('kind')
            if not kind:
                continue
            label = f'{table.fullname}.{constraint["name"]}'
            if kind in {'p', 'u', 'f'} and not allow_constraint_rename:
                raise UnsupportedFeatureError(f'{table.fullname}: imported constraint names require allow_constraint_rename=True')
            if kind in {'p', 'u'} and constraint.get('deferrable'):
                raise UnsupportedFeatureError(f'{label}: DEFERRABLE primary/unique constraint is not available in this release')
            if 'NULLS NOT DISTINCT' in constraint.get('definition', ''):
                raise UnsupportedFeatureError(f'{label}: NULLS NOT DISTINCT constraint is not available in this release')
            if not constraint.get('validated', True):
                raise UnsupportedFeatureError(f'{label}: NOT VALID constraint')
            if kind == 'f':
                if constraint.get('match_type', 's') != 's':
                    raise UnsupportedFeatureError(f'{label}: non-simple FK match')
                if constraint.get('delete_set_columns'):
                    raise UnsupportedFeatureError(f'{label}: column subset SET NULL/DEFAULT')
            elif kind not in {'p', 'u'}:
                raise UnsupportedFeatureError(f'{label}: constraint kind {kind}')
        for item in table.attributes.get('indexes', ()):
            owned = item.get('primary') or item.get('constraint_owned')
            feature = _constraint_index_feature(item) if owned else _index_feature(item)
            if feature:
                subject = 'constraint index' if owned else 'index'
                raise UnsupportedFeatureError(f'{table.fullname}.{item["name"]}: {subject} with {feature} is not available in this release')
