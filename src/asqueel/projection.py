"""Explicit bridge from resolved names to the existing migration grammar."""
from __future__ import annotations

from collections.abc import Mapping

from .builder import SqlBuilder
from .contracts import ResolvedModel, UnsupportedFeatureError
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


def _column_storage(column, *, path, packaged):
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
    kwargs = {k: metadata[k] for k in (
        'size', 'notnull', 'unique', 'indexed', 'sqldefault',
        'extra_sql', 'generated_expression', 'comment',
    ) if metadata.get(k) is not None}
    if metadata.get('default') is not None and metadata.get('raw_type'):
        kwargs['sqldefault'] = metadata['default']
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


def to_physical_builder(model: ResolvedModel | DbModel, *, allow_constraint_rename=False) -> SqlBuilder:
    """Project supported physical semantics, rejecting anything lossy.

    Arbitrary imported PK/FK/UNIQUE names are not representable by the current
    emitter. Opt in only when the migration comparison ignores constraint names.
    Views/formulas/UI are semantic and deliberately excluded from physical DDL.
    """
    if isinstance(model, DbModel):
        from .object_tree_projection import project_tree
        return project_tree(model)
    if model.warnings:
        raise UnsupportedFeatureError('Incomplete model with import warnings cannot be projected: ' + '; '.join(model.warnings))

    class PhysicalBuilder(SqlBuilder):
        def main(self, root):
            db = root.db(model.name)
            for extension in model.extensions:
                db.extensions().extension(extension)
            schemas = db.schemas()
            schema_nodes = {}
            for schema in model.schemas.values():
                schema_nodes[schema.physical_name] = schemas.schema(schema.physical_name).tables()
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
                    if column.is_virtual:
                        continue
                    dtype, kwargs = _column_storage(
                        column, path=f'{table.key}.{column.name}', packaged=bool(table.package_name))
                    column_nodes[(table.key, column.name)] = cols.column(
                        column.physical_name, dtype=dtype, **kwargs)
                constraints_node = None
                constraints = table.attributes.get('constraints', ())
                for index, constraint in enumerate(constraints):
                    kind = constraint.get('kind')
                    if kind:
                        if kind in {'p', 'u', 'f'} and not allow_constraint_rename:
                            raise UnsupportedFeatureError(
                                f'{table.key}: imported constraint names require allow_constraint_rename=True')
                        if kind in {'p', 'u'} and constraint.get('deferrable'):
                            raise UnsupportedFeatureError(
                                f'{table.key}.{constraint["name"]}: DEFERRABLE primary/unique constraint '
                                'is not available in this release')
                        if 'NULLS NOT DISTINCT' in constraint.get('definition', ''):
                            raise UnsupportedFeatureError(
                                f'{table.key}.{constraint["name"]}: NULLS NOT DISTINCT constraint '
                                'is not available in this release')
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
                    constraints_node.constraint(constraint.get('name') or f'unique_{index}',
                                                x_auto_name=constraint.get('x_auto_name', False), **data)
                indexes = table.attributes.get('indexes', ())
                idx_node = None
                for item in indexes:
                    if item.get('primary') or item.get('constraint_owned'):
                        feature = _constraint_index_feature(item)
                        if feature:
                            raise UnsupportedFeatureError(
                                f'{table.key}.{item["name"]}: constraint index with {feature} '
                                'is not available in this release')
                        continue
                    if idx_node is None:
                        idx_node = node.indexes()
                    if 'definition' in item:
                        columns = item['columns']
                        ordering = list(item['ordering'])
                        feature = _index_feature(item)
                        if feature:
                            raise UnsupportedFeatureError(
                                f'{table.key}.{item["name"]}: index with {feature} is not available in this release')
                        data = {'columns': {n: 'DESC' if o == 3 else None
                                            for n, o in zip(columns, ordering)},
                                'unique': item['unique'], 'method': None if item['method'] == 'btree' else item['method'],
                                'where': item['predicate']}
                    else:
                        data = {k: v for k, v in item.items() if k in {
                            'columns', 'unique', 'method', 'where', 'tablespace', 'with_options'}}
                        names = data.get('columns', '')
                        data['columns'] = ({table.columns[n].physical_name: order for n, order in names.items()}
                                           if isinstance(names, Mapping) else mapped(names.split(',')))
                        if data.get('where') and any(c.physical_name != c.name for c in table.columns.values()):
                            raise UnsupportedFeatureError(f'{table.key}: partial index with remapped columns')
                    idx_node.index(item['name'], x_auto_name=item.get('x_auto_name', False), **data)
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
                    if relation.kind in ('inverse', 'virtual'):
                        continue
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
                        'onDelete_sql', 'onUpdate_sql', 'deferrable', 'initially_deferred', 'deferred', 'indexed', 'constraint_name'
                    ) if k in declaration}
                    if imported:
                        if declaration.get('delete_set_columns'):
                            raise UnsupportedFeatureError(f'{table.key}.{relation.name}: column subset SET NULL/DEFAULT')
                        kwargs['indexed'] = False
                        for field, code in (('onDelete_sql', 'on_delete_code'), ('onUpdate_sql', 'on_update_code')):
                            kwargs[field] = _ACTIONS[declaration[code]]
                    if len(relation.columns) == 1:
                        owner = column_nodes[(table.key, relation.columns[0])]
                    else:
                        owner = composite(table, relation.columns)[1]
                    owner.relation(target_ref, foreign_key=True, **kwargs)
    result = PhysicalBuilder()
    result.create()
    result.validate_model()
    return result
