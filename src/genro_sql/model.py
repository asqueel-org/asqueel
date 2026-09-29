"""Resolve declarative models into the deliberately small native SQL profile."""
from __future__ import annotations

from dataclasses import replace
import re
from typing import Any, Mapping

from .catalog import SqlModelCatalog
from .contracts import (
    Column, PartitionScope, Relation, ResolvedModel, RowPolicies, Table, UnsupportedFeatureError,
)


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
    policy_keys = {'x_partition', 'x_partitions', 'x_draft_field', 'x_logical_deletion_field'}
    for path, node in catalog.nodes:
        misplaced = policy_keys.intersection(node.attr) if node.node_tag != 'table' else set()
        if misplaced:
            raise ValueError(f'{path}: row policies belong to a table, not {node.node_tag}')
        if any(key.startswith(('x_virtualRelation', 'x_virtual_relation')) for key in node.attr):
            raise UnsupportedFeatureError(f'{path}: virtualRelation is outside V1')
    tables: dict[str, Table] = {}
    identities: set[str] = set()
    physical: set[tuple[str, str]] = set()
    for (schema, name), entry in catalog.tables.items():
        attrs = dict(entry['node'].attr)
        inherited = dict(catalog.schemas[schema].attr)
        for key in {**inherited, **attrs}:
            if key not in policy_keys and key.startswith(('x_partition', 'x_subtable', 'x_tenant', 'x_store', 'x_virtualRelation', 'x_virtual_relation')):
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
                      prefix, attrs.get('x_identity', f'{schema}.{name}'), attrs, _parse_row_policies(attrs))
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
    return validate_row_policies(ResolvedModel(tables, catalog.db_name or 'database'))


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


_ENV_KEY = re.compile(r'[A-Za-z_][A-Za-z0-9_]*\Z')
_RELATION_FIELD = re.compile(r'@[A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*)+\Z')


def _policy_field(value, label: str) -> str:
    if not isinstance(value, str) or not value or '\x00' in value:
        raise ValueError(f'{label} must name a column or forward relation path')
    if value.startswith('$"'):
        if not re.fullmatch(r'\$"(?:[^"]|"")+"', value):
            raise ValueError(f'{label}: malformed quoted field')
        return value[2:-1].replace('""', '"')
    return value[1:] if value.startswith('$') else value


def _parse_row_policies(attributes: Mapping[str, Any]) -> RowPolicies:
    if 'x_partition' in attributes and 'x_partitions' in attributes:
        raise ValueError('x_partition and x_partitions are mutually exclusive')
    definitions = []
    if 'x_partition' in attributes:
        definitions = [attributes['x_partition']]
    elif 'x_partitions' in attributes:
        definitions = attributes['x_partitions']
        if not isinstance(definitions, (list, tuple)) or not definitions:
            raise ValueError('x_partitions must be a nonempty list of partition mappings')
    partitions = []
    for definition in definitions:
        if not isinstance(definition, Mapping):
            raise ValueError('Each partition must be a mapping')
        unknown = definition.keys() - {'field', 'current', 'allowed', 'include_null'}
        if unknown:
            raise ValueError(f'Unknown partition options: {sorted(unknown)}')
        if not {'field', 'current'} <= definition.keys():
            raise ValueError('Partition requires field and current environment key')
        partitions.append(PartitionScope(
            _policy_field(definition['field'], 'partition field'), definition['current'],
            definition.get('allowed'), definition.get('include_null', True),
        ))
    markers = {}
    for key, target in [('x_draft_field', 'draft_field'),
                        ('x_logical_deletion_field', 'logical_deletion_field')]:
        if key in attributes:
            markers[target] = _policy_field(attributes[key], key)
    return RowPolicies(tuple(partitions), **markers)


def _physical_policy_column(model: ResolvedModel, table: Table, field: str,
                            *, relational: bool) -> Column:
    name = _policy_field(field, 'policy field')
    if name.startswith('@'):
        if not relational or not _RELATION_FIELD.fullmatch(name):
            raise ValueError(f'{table.key}: invalid policy relation path {name!r}')
        segments = name[1:].split('.')
        for relation_name in segments[:-1]:
            relation = table.relations.get(relation_name)
            if relation is None:
                raise ValueError(f'{table.key}: unknown policy relation {relation_name!r}')
            target = model.table(relation.target)
            if (not relation.columns or len(relation.columns) != len(relation.target_columns)
                    or any(c not in table.columns or table.columns[c].formula is not None
                           for c in relation.columns)
                    or any(c not in target.columns or target.columns[c].formula is not None
                           for c in relation.target_columns)
                    or not _unique_target(target, relation.target_columns)):
                raise ValueError(f'{table.key}.{relation_name}: policy path requires a physical to-one relation')
            table = target
        name = segments[-1]
    column = table.columns.get(name)
    if column is None or column.formula is not None:
        raise ValueError(f'{table.key}: policy field {name!r} must be a physical column')
    return column


def validate_row_policies(model: ResolvedModel) -> ResolvedModel:
    """Validate both resolved declarations and manually constructed contracts.

    Policies affect row visibility, not DDL. They must never be inferred from
    similarly named columns in a database catalog.
    """
    for table in model.tables.values():
        policies = table.policies
        if not isinstance(policies, RowPolicies):
            raise ValueError(f'{table.key}: policies must be RowPolicies')
        if not isinstance(policies.partitions, tuple):
            raise ValueError(f'{table.key}: partitions must be an immutable tuple')
        fields = set()
        for partition in policies.partitions:
            if not isinstance(partition, PartitionScope):
                raise ValueError(f'{table.key}: partitions must contain PartitionScope')
            field = _policy_field(partition.field, 'partition field')
            if field in fields:
                raise ValueError(f'{table.key}: duplicate partition field {field!r}')
            fields.add(field)
            _physical_policy_column(model, table, partition.field, relational=True)
            for role, key in [('current', partition.current), ('allowed', partition.allowed)]:
                if role == 'allowed' and key is None:
                    continue
                if not isinstance(key, str) or not _ENV_KEY.fullmatch(key):
                    raise ValueError(f'{table.key}: policy environment keys must be identifiers')
            if partition.current == partition.allowed:
                raise ValueError(f'{table.key}: current and allowed must use different environment keys')
            if not isinstance(partition.include_null, bool):
                raise ValueError(f'{table.key}: include_null must be boolean')
        if policies.draft_field is not None:
            column = _physical_policy_column(model, table, policies.draft_field, relational=False)
            if column.dtype not in {'B', 'boolean', 'bool'}:
                raise ValueError(f'{table.key}: draft field must have boolean type')
        if policies.logical_deletion_field is not None:
            name = _policy_field(policies.logical_deletion_field, 'logical deletion field')
            column = _physical_policy_column(model, table, name, relational=False)
            if column.attributes.get('notnull') or name in table.pkey:
                raise ValueError(f'{table.key}: logical deletion field must be nullable')
        if (policies.draft_field is not None and policies.logical_deletion_field is not None
                and _policy_field(policies.draft_field, 'draft field')
                == _policy_field(policies.logical_deletion_field, 'logical deletion field')):
            raise ValueError(f'{table.key}: draft and logical deletion must use distinct columns')
    return model
