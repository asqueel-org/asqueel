"""Explicit bridge from resolved names to the existing migration grammar."""
from __future__ import annotations

from .builder import SqlBuilder
from .contracts import ResolvedModel, UnsupportedFeatureError


_ACTIONS = {'a': None, 'r': 'RESTRICT', 'c': 'CASCADE', 'n': 'SET NULL', 'd': 'SET DEFAULT'}


def to_physical_builder(model: ResolvedModel, *, allow_constraint_rename=False) -> SqlBuilder:
    """Project supported physical semantics, rejecting anything lossy.

    Arbitrary imported PK/FK/UNIQUE names are not representable by the current
    emitter. Opt in only when the migration comparison ignores constraint names.
    Views/formulas/UI are semantic and deliberately excluded from physical DDL.
    """
    if model.warnings:
        raise UnsupportedFeatureError('Incomplete model with import warnings cannot be projected: ' + '; '.join(model.warnings))

    class PhysicalBuilder(SqlBuilder):
        def main(self, root):
            schemas = root.db(model.name).schemas()
            schema_nodes = {}
            table_nodes = {}
            column_nodes = {}
            composite_nodes = {}
            composite_keys = {}
            for table in model.tables.values():
                schema = table.physical_schema
                if schema not in schema_nodes:
                    schema_nodes[schema] = schemas.schema(schema).tables()
                def mapped(names, t=table):
                    return ','.join(t.columns[n.strip()].physical_name for n in names)
                attrs = {}
                if table.attributes.get('comment'):
                    attrs['comment'] = table.attributes['comment']
                node = schema_nodes[schema].table(table.physical_name,
                                                  pkey=mapped(table.pkey) or None, **attrs)
                table_nodes[table.key] = node
                cols = node.columns()
                for column in table.columns.values():
                    if column.formula is not None:
                        continue
                    metadata = column.attributes
                    if metadata.get('identity_kind') or metadata.get('generated'):
                        raise UnsupportedFeatureError(f'{table.key}.{column.name}: identity/generated DDL')
                    if metadata.get('default_collation') is False:
                        raise UnsupportedFeatureError(f'{table.key}.{column.name}: custom column collation')
                    if metadata.get('owned_sequence') or metadata.get('sequence_default'):
                        raise UnsupportedFeatureError(f'{table.key}.{column.name}: sequence ownership/default not modeled')
                    raw = metadata.get('raw_type', '')
                    if raw in {'smallint', 'real'} or (raw.startswith(('time', 'timestamp')) and '(' in raw):
                        raise UnsupportedFeatureError(f'{table.key}.{column.name}: lossy type projection {raw}')
                    kwargs = {k: metadata[k] for k in (
                        'size', 'notnull', 'unique', 'indexed', 'sqldefault',
                        'extra_sql', 'generated_expression', 'comment',
                    ) if metadata.get(k) is not None}
                    if metadata.get('default') is not None:
                        kwargs['sqldefault'] = metadata['default']
                    column_nodes[(table.key, column.name)] = cols.column(
                        column.physical_name, dtype=column.dtype, **kwargs)
                constraints_node = None
                constraints = table.attributes.get('constraints', ())
                for index, constraint in enumerate(constraints):
                    kind = constraint.get('kind')
                    if kind:
                        if kind in {'p', 'u', 'f'} and not allow_constraint_rename:
                            raise UnsupportedFeatureError(
                                f'{table.key}: imported constraint names require allow_constraint_rename=True')
                        if (kind in {'p', 'u'} and constraint.get('deferrable')
                                or 'NULLS NOT DISTINCT' in constraint.get('definition', '')):
                            raise UnsupportedFeatureError(f'{table.key}: advanced unique/primary constraint')
                        if not constraint.get('validated', True):
                            raise UnsupportedFeatureError(f'{table.key}: NOT VALID constraint')
                        if kind == 'f' and constraint['name'] not in table.relations:
                            raise UnsupportedFeatureError(f'{table.key}: foreign key target outside model')
                        if kind in {'p', 'f'}:
                            continue
                        if kind != 'u':
                            raise UnsupportedFeatureError(f'{table.key}: constraint kind {kind}')
                        if constraint.get('deferrable'):
                            raise UnsupportedFeatureError(f'{table.key}: deferrable UNIQUE')
                        data = {'constraint_type': 'UNIQUE',
                                'columns': mapped(constraint['columns'])}
                    else:
                        data = {k: v for k, v in constraint.items()
                                if k in {'constraint_type', 'columns', 'check_clause'}}
                        if data.get('columns'):
                            data['columns'] = mapped(data['columns'].split(','))
                        if data.get('check_clause') and any(c.physical_name != c.name for c in table.columns.values()):
                            raise UnsupportedFeatureError(f'{table.key}: CHECK with remapped columns')
                    if constraints_node is None:
                        constraints_node = node.constraints()
                    constraints_node.constraint(constraint.get('name') or f'unique_{index}', **data)
                indexes = table.attributes.get('indexes', ())
                idx_node = None
                for item in indexes:
                    if item.get('primary') or item.get('constraint_owned'):
                        if (item.get('options') or item.get('tablespace')
                                or len(item.get('columns', ())) != item.get('key_count')
                                or item.get('method') != 'btree'
                                or item.get('default_opclasses') is False
                                or item.get('default_collations') is False
                                or any(v != 0 for v in item.get('ordering', ()))
                                or item.get('valid') is False or item.get('nulls_not_distinct')):
                            raise UnsupportedFeatureError(f'{table.key}.{item["name"]}: advanced constraint index')
                        continue
                    if idx_node is None:
                        idx_node = node.indexes()
                    if 'definition' in item:
                        columns = item['columns']
                        ordering = list(item['ordering'])
                        if (not all(columns) or len(columns) != item['key_count']
                                or any(v not in (0, 3) for v in ordering)
                                or not item['default_opclasses'] or not item['default_collations'] or not item['valid']
                                or item['nulls_not_distinct'] or item['options'] or item['tablespace']):
                            raise UnsupportedFeatureError(f'{table.key}.{item["name"]}: advanced index semantics')
                        data = {'columns': {n: 'DESC' if o == 3 else None
                                            for n, o in zip(columns, ordering)},
                                'unique': item['unique'], 'method': None if item['method'] == 'btree' else item['method'],
                                'where': item['predicate']}
                    else:
                        data = {k: v for k, v in item.items() if k in {
                            'columns', 'unique', 'method', 'where', 'tablespace', 'with_options'}}
                        names = data.get('columns', '')
                        data['columns'] = ({table.columns[n].physical_name: order for n, order in names.items()}
                                           if isinstance(names, dict) else mapped(names.split(',')))
                        if data.get('where') and any(c.physical_name != c.name for c in table.columns.values()):
                            raise UnsupportedFeatureError(f'{table.key}: partial index with remapped columns')
                    idx_node.index(item['name'], **data)
            def composite(table, names):
                key = (table.key, names)
                if key not in composite_keys:
                    if table.key not in composite_nodes:
                        composite_nodes[table.key] = table_nodes[table.key].composites()
                    name = '_native_key_' + str(len(composite_keys))
                    while name in table.columns:
                        name += '_'
                    owner = composite_nodes[table.key].compositeColumn(
                        name, columns=','.join(table.columns[c].physical_name for c in names))
                    composite_keys[key] = (name, owner)
                return composite_keys[key]

            for table in model.tables.values():
                for relation in table.relations.values():
                    target = model.table(relation.target)
                    declarations = table.attributes.get('relations', ())
                    imported = [c for c in table.attributes.get('constraints', ())
                                if c.get('kind') == 'f' and c['name'] == relation.name]
                    declaration = imported[0] if imported else next((
                        d for d in declarations if (d.get('x_name') or relation.columns[0]) == relation.name
                    ), {})
                    if not imported and not declaration.get('foreign_key'):
                        continue
                    if imported and declaration.get('match_type', 's') != 's':
                        raise UnsupportedFeatureError(f'{table.key}.{relation.name}: non-simple FK match')
                    target_ref = f'{target.physical_schema}.{target.physical_name}'
                    if relation.target_columns != target.pkey:
                        target_col = (target.columns[relation.target_columns[0]].physical_name
                                      if len(relation.target_columns) == 1
                                      else composite(target, relation.target_columns)[0])
                        target_ref += '.' + target_col
                    kwargs = {k: declaration[k] for k in (
                        'on_delete', 'on_update', 'deferrable', 'initially_deferred', 'deferred', 'indexed'
                    ) if k in declaration}
                    if imported:
                        if declaration.get('delete_set_columns'):
                            raise UnsupportedFeatureError(f'{table.key}.{relation.name}: column subset SET NULL/DEFAULT')
                        kwargs['indexed'] = False
                        for field in ('on_delete', 'on_update'):
                            action = _ACTIONS[declaration[field + '_code']]
                            if action:
                                kwargs[field] = action
                    if len(relation.columns) == 1:
                        owner = column_nodes[(table.key, relation.columns[0])]
                    else:
                        owner = composite(table, relation.columns)[1]
                    owner.relation(target_ref, foreign_key=True, **kwargs)
    result = PhysicalBuilder()
    result.create()
    result.validate_model()
    return result
