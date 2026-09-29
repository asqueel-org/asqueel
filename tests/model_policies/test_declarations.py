"""Native policy declarations must be explicit and refer to validated fields."""
from dataclasses import replace

import pytest

from genro_sql import SqlBuilder
from genro_sql.contracts import Column, PartitionScope, Relation, ResolvedModel, RowPolicies, Table
from genro_sql.model import resolve_model, validate_row_policies


def declared(**attributes):
    class Example(SqlBuilder):
        def main(self, root):
            tables = root.db('policy_example').schemas().schema('app').tables()
            organization = tables.table('organization', pkey='id')
            org_columns = organization.columns()
            org_columns.column('id', dtype='I')
            org_columns.column('region', dtype='I')
            item = tables.table('item', pkey='id', **attributes)
            columns = item.columns()
            columns.column('id', dtype='I')
            columns.column('organization_id', dtype='I').relation('app.organization.id', x_name='organization')
            columns.column('scope value', dtype='I')
            columns.column('draft', dtype='B')
            columns.column('deleted_at', dtype='DHZ')
            columns.column('not_nullable', dtype='DHZ', notnull=True)
            item.virtual_columns().formulaColumn('computed', sql_formula='$id + 1', dtype='I')
    builder = Example()
    builder.create()
    return builder


def test_multiple_dimensions_and_markers_preserve_metadata_and_defaults():
    declarations = [
        {'field': '$organization_id', 'current': 'current_org', 'allowed': 'allowed_org'},
        {'field': '@organization.region', 'current': 'current_region', 'include_null': False},
        {'field': '$"scope value"', 'current': 'current_scope'},
    ]
    model = resolve_model(declared(x_partitions=declarations,
                                   x_draft_field='draft', x_logical_deletion_field='deleted_at'))
    table = model.table('item')
    assert table.policies == RowPolicies((
        PartitionScope('organization_id', 'current_org', 'allowed_org', True),
        PartitionScope('@organization.region', 'current_region', None, False),
        PartitionScope('scope value', 'current_scope', None, True),
    ), 'draft', 'deleted_at')
    assert table.attributes['x_partitions'] == declarations
    assert table.attributes['provenance']['kind'] == 'builder'
    assert not model.table('organization').policies.partitions


def test_single_partition_and_no_implicit_policy_from_column_names():
    model = resolve_model(declared(x_partition={'field': 'organization_id', 'current': 'org'}))
    assert model.table('item').policies == RowPolicies((PartitionScope('organization_id', 'org'),))
    plain = resolve_model(declared()).table('item')
    assert plain.policies == RowPolicies()


@pytest.mark.parametrize('attributes', [
    {'x_partition': {}, 'x_partitions': []},
    {'x_partition': False}, {'x_partitions': []}, {'x_partitions': {}},
    {'x_partition': {'field': 'organization_id'}},
    {'x_partition': {'field': 'organization_id', 'current': 'current', 'ignored': 1}},
    {'x_partition': {'field': 'organization_id', 'current': None}},
    {'x_partition': {'field': 'organization_id', 'current': ''}},
    {'x_partition': {'field': 'organization_id', 'current': 'current-org'}},
    {'x_partition': {'field': 'organization_id', 'current': 'org', 'allowed': 'org'}},
    {'x_partition': {'field': 'organization_id', 'current': 'org', 'include_null': 1}},
    {'x_partition': {'field': 'missing', 'current': 'org'}},
    {'x_partition': {'field': 'computed', 'current': 'org'}},
    {'x_partition': {'field': '@missing.id', 'current': 'org'}},
    {'x_partition': {'field': '@organization.missing', 'current': 'org'}},
    {'x_partitions': [{'field': 'organization_id', 'current': 'org'},
                      {'field': '$organization_id', 'current': 'other'}]},
    {'x_draft_field': 'organization_id'}, {'x_draft_field': 'computed'},
    {'x_draft_field': '@organization.region'}, {'x_draft_field': False},
    {'x_logical_deletion_field': 'not_nullable'}, {'x_logical_deletion_field': 'id'},
    {'x_logical_deletion_field': 'computed'},
    {'x_logical_deletion_field': 'draft', 'x_draft_field': 'draft'},
    {'x_partition_legacy': 'org'}, {'x_tenant': 'tenant'}, {'x_store': 'store'},
])
def test_invalid_or_unimplemented_semantics_cannot_be_ignored(attributes):
    with pytest.raises(ValueError):
        resolve_model(declared(**attributes))


def test_schema_policy_is_rejected_instead_of_accidentally_inherited():
    class SchemaPolicy(SqlBuilder):
        def main(self, root):
            schema = root.db('example').schemas().schema('app',
                x_partition={'field': 'id', 'current': 'org'})
            schema.tables().table('item').columns().column('id', dtype='I')
    builder = SchemaPolicy()
    builder.create()
    with pytest.raises(ValueError, match='belong to a table'):
        resolve_model(builder)


def test_manual_contract_relation_must_be_to_one():
    target = Table('target', columns={'id': Column('id', 'I')})
    source = Table('source', columns={'ref': Column('ref', 'I')},
                   relations={'target': Relation('target', target.key, ('ref',), ('id',))},
                   policies=RowPolicies((PartitionScope('@target.id', 'target'),)))
    model = ResolvedModel({source.key: source, target.key: target})
    with pytest.raises(ValueError, match='to-one'):
        validate_row_policies(model)
    target = replace(target, pkey=('id',))
    valid = ResolvedModel({source.key: source, target.key: target})
    assert validate_row_policies(valid) is valid


def test_policy_metadata_changes_no_physical_ddl():
    from genro_sql.projection import to_physical_builder
    from genro_sql.catalog import SqlModelCatalog
    plain = resolve_model(declared())
    scoped = resolve_model(declared(x_partition={'field': 'organization_id', 'current': 'org'},
                                    x_draft_field='draft', x_logical_deletion_field='deleted_at'))
    plain_catalog = SqlModelCatalog(to_physical_builder(plain))
    scoped_catalog = SqlModelCatalog(to_physical_builder(scoped))
    assert [(path, dict(node.attr)) for path, node in plain_catalog.nodes] == [
        (path, dict(node.attr)) for path, node in scoped_catalog.nodes]
