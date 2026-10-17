"""Replay native option contracts on the hierarchy; no driver I/O."""
import pytest

from asqueel import SqlDatabase
from asqueel.configuration import _owned_handler
from tests.native_compiler import test_native_options as original
from tests.native_compiler.test_native_options import (
    backend as backend,
    test_partition_alias_reuses_join_without_filtering_joined_table as test_partition_alias_reuses_join_without_filtering_joined_table,
    test_present_scalar_is_bound_even_when_falsy as test_present_scalar_is_bound_even_when_falsy,
    test_optional_missing_and_disabled_partitions_do_not_filter as test_optional_missing_and_disabled_partitions_do_not_filter,
    test_required_missing_is_explicit_and_can_be_bypassed as test_required_missing_is_explicit_and_can_be_bypassed,
    test_collection_partition_has_no_implicit_allowed_values_semantics as test_collection_partition_has_no_implicit_allowed_values_semantics,
    test_existing_resolver_is_evaluated_by_render_not_compiler as test_existing_resolver_is_evaluated_by_render_not_compiler,
    test_names_alone_do_not_create_filters as test_names_alone_do_not_create_filters,
    test_partition_value_never_becomes_sql_text as test_partition_value_never_becomes_sql_text,
)


def tree_database(config):
    return SqlDatabase(model=config.render(mode='objects_tree'), config=_owned_handler(config))


@pytest.fixture(autouse=True)
def use_tree(monkeypatch):
    monkeypatch.setattr(original, 'build_database', tree_database)


def test_disabled_sys_fields_does_not_activate_read_markers(backend):
    config = original.source(backend, value=None)
    table = config.source['db'].packages().package('sales').table('customer', pkey='id')
    table.options().sys_fields(enabled=False)
    table.column('id')
    with tree_database(config) as db:
        assert 'WHERE' not in db.table('sales.customer').query('$id').compiled.sql


def test_read_options_do_not_change_source_or_model(backend):
    config = original.source(backend)
    before = config.source.to_json()
    with tree_database(config) as db:
        from copy import deepcopy
        attrs = {name: deepcopy(table.attributes) for name, table in db.model.tables.items()}
        relations = db.model.relations.to_xml()
        query = db.table('sales.invoice').query('$state,$visible_customers', where='$id=:__policy_0', __policy_0='id')
        first = query.compiled
        assert first.params['__policy_0'] == 'id'
        assert first.input_parameters == ('__policy_0',)
        assert query.compiled == first
        assert db.model.relations.to_xml() == relations
        assert {n: t.attributes for n, t in db.model.tables.items()} == attrs
        assert not db._connections
    assert config.source.to_json() == before


def test_generated_markers_and_scalar_partition(backend):
    with tree_database(original.source(backend)) as db:
        table = db.table('sales.customer')
        query = table.query('$id', where='$state=:state OR $state IS NULL', state='VIC').compiled
        # SQLite preparation retains the R3 legacy IS NOT TRUE -> IS NULL OR !=1.
        draft = 'IS NOT TRUE' if backend == 'postgres' else '!=1'
        assert f'"__is_draft" {draft}' in query.sql
        assert '"__del_ts" IS NULL' in query.sql
        assert set(query.params.values()) == {'NSW', 'VIC'}
        assert ') AND (' in query.sql
        included = table.query('$id', excludeDraft=False, excludeLogicalDeleted=False, ignorePartition=True).compiled
        assert 'WHERE' not in included.sql and not included.params


def test_child_defaults_and_overrides_keep_partition_bindings_isolated(backend):
    with tree_database(original.source(backend)) as db:
        table = db.table('sales.invoice')
        default = table.query('$all_customers').compiled
        assert '__is_draft' not in default.sql
        assert list(default.params.values()) == ['NSW']
        query = table.query('$visible_customers').compiled
        draft = 'IS NOT TRUE' if backend == 'postgres' else '!=1'
        assert f'"__is_draft" {draft}' in query.sql
        assert query.sql.count('"__del_ts" IS NULL') == 2
        assert list(query.params.values()) == ['NSW', 'NSW']
        assert len(query.params) == 2
        assert table.query('$visible_customers').compiled == query
