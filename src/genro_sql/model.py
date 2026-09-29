"""Resolve declarative models into the deliberately small native SQL profile."""
from __future__ import annotations

from dataclasses import replace
from typing import Any, Mapping

from .catalog import SqlModelCatalog
from .contracts import Column, Relation, ResolvedModel, Table, UnsupportedFeatureError


def _names(value) -> tuple[str, ...]:
    return tuple(part.strip() for part in (value or '').split(',') if part.strip())


def column_ui(attributes: Mapping[str, Any], path: str, identity: str,
              ui: Mapping[str, Mapping[str, Any]] | None) -> dict[str, Any]:
    """Apply inline metadata, then path overlay, then stable identity overlay."""
    result = dict(attributes.get('x_ui') or {})
    overlays = ui or {}
    result.update(overlays.get(path, {}))
    if identity != path:
        result.update(overlays.get(identity, {}))
    forbidden = {'dtype', 'formula', 'sql_name', 'notnull', 'unique', 'pkey'} & result.keys()
    if forbidden:
        raise ValueError(f'UI metadata cannot override column semantics: {sorted(forbidden)}')
    return result


def resolve_model(builder, *, ui=None) -> ResolvedModel:
    """Resolve a built SqlBuilder; unsupported executable semantics raise errors.

    x_sql_schema/x_sql_prefix inherit from schema to table, x_sql_name is an
    explicit physical table/column override. No physical prefix is inferred.
    """
    builder.validate_model()
    catalog = SqlModelCatalog(builder)
    for path, node in catalog.nodes:
        if any(key.startswith(('x_virtualRelation', 'x_virtual_relation')) for key in node.attr):
            raise UnsupportedFeatureError(f'{path}: virtualRelation is outside V1')
    tables: dict[str, Table] = {}
    identities: set[str] = set()
    physical: set[tuple[str, str]] = set()
    for (schema, name), entry in catalog.tables.items():
        attrs = dict(entry['node'].attr)
        inherited = dict(catalog.schemas[schema].attr)
        for key in {**inherited, **attrs}:
            if key.startswith(('x_partition', 'x_subtable', 'x_tenant', 'x_store', 'x_virtualRelation', 'x_virtual_relation')):
                raise UnsupportedFeatureError(f'{schema}.{name}: unsupported scope {key}')
        columns = {}
        for colname, node in entry['family'].items():
            if node.node_tag == 'compositeColumn':
                continue
            metadata = dict(node.attr)
            formula = None
            if node.node_tag != 'column':
                if (node.node_tag != 'formulaColumn' or not metadata.get('sql_formula')
                        or metadata.get('select') or metadata.get('exists')):
                    raise UnsupportedFeatureError(f'{schema}.{name}.{colname}: {node.node_tag}')
                formula = metadata['sql_formula']
            path = f'{schema}.{name}.{colname}'
            identity = metadata.get('x_identity', path)
            if identity in identities:
                raise ValueError(f'Duplicate column identity: {identity}')
            identities.add(identity)
            metadata['provenance'] = {'kind': 'builder', 'path': catalog.path(node)}
            columns[colname] = Column(
                colname, metadata.get('dtype') or ('A' if metadata.get('size') else 'T'), metadata.get('x_sql_name'),
                formula, column_ui(metadata, path, identity, ui), identity, metadata,
            )
        attrs['provenance'] = {'kind': 'builder', 'path': entry['path']}
        attrs['indexes'] = tuple(dict(node.attr) for _, node in entry['indexes'])
        attrs['constraints'] = tuple(dict(node.attr) for _, node in entry['constraints']) + tuple(
            {'constraint_type': 'UNIQUE', 'columns': node.get_attr('columns')}
            for node in entry['composites'].values() if node.get_attr('unique')
        )
        attrs['relations'] = tuple(dict(node.attr) for _, _, node in entry['relations'])
        prefix = attrs.get('x_sql_prefix', inherited.get('x_sql_prefix', ''))
        if prefix is True:
            prefix = schema + '_'
        elif prefix is False or prefix is None:
            prefix = ''
        if not isinstance(prefix, str):
            raise ValueError('x_sql_prefix must be a string or boolean')
        table = Table(name, schema, columns, {}, _names(attrs.get('pkey')),
                      attrs.get('x_sql_name'),
                      attrs.get('x_sql_schema', inherited.get('x_sql_schema')),
                      prefix, attrs.get('x_identity', f'{schema}.{name}'), attrs)
        physical_key = (table.physical_schema, table.physical_name)
        if physical_key in physical:
            raise ValueError(f'Duplicate physical table: {physical_key}')
        physical.add(physical_key)
        physical_columns = [c.physical_name for c in columns.values() if c.formula is None]
        if len(physical_columns) != len(set(physical_columns)):
            raise ValueError(f'Duplicate physical columns: {table.key}')
        tables[table.key] = table
    for (schema, name), entry in catalog.tables.items():
        table = tables[f'{schema}.{name}']
        relations = {}
        for _, owner, node in entry['relations']:
            attrs = dict(node.attr)
            if attrs.get('case_insensitive'):
                raise UnsupportedFeatureError('case_insensitive relations are outside V1')
            target_parts = attrs['to'].split('.')
            target_key = '.'.join(target_parts[:2])
            target = tables[target_key]
            target_cols = _names(target_parts[2]) if len(target_parts) > 2 else target.pkey
            target_entry = catalog.tables[tuple(target_parts[:2])]
            if len(target_cols) == 1 and target_cols[0] in target_entry['composites']:
                target_cols = _names(target_entry['composites'][target_cols[0]].get_attr('columns'))
            owner_node = entry['family'][owner]
            local_cols = (_names(owner_node.get_attr('columns'))
                          if owner_node.node_tag == 'compositeColumn' else (owner,))
            if not _unique_target(target, target_cols):
                raise UnsupportedFeatureError(f'{table.key}.{owner}: target must have a unique key')
            relation_name = attrs.get('x_name') or owner
            if relation_name in relations:
                raise ValueError(f'Duplicate relation: {relation_name}')
            relations[relation_name] = Relation(relation_name, target_key, local_cols, target_cols)
        tables[table.key] = replace(table, relations=relations)
    return ResolvedModel(tables, catalog.db_name or 'database')


def _unique_target(table: Table, columns: tuple[str, ...]) -> bool:
    if not columns:
        return False
    if columns == table.pkey:
        return True
    if len(columns) == 1 and columns[0] in table.columns and table.columns[columns[0]].attributes.get('unique'):
        return True
    for constraint in table.attributes.get('constraints', ()):
        members = constraint.get('columns', ())
        members = _names(members) if isinstance(members, str) else tuple(members)
        if members == columns and (constraint.get('kind') == 'u'
                                   or constraint.get('constraint_type', '').upper() == 'UNIQUE'):
            return True
    for index in table.attributes.get('indexes', ()):
        members = index.get('columns', ())
        members = _names(members) if isinstance(members, str) else tuple(members)
        if (members == columns and index.get('unique') and index.get('valid', True)
                and not index.get('predicate') and not index.get('where')):
            return True
    return False
