"""Legacy star and Bag extraction on the hierarchical SELECT recursion."""
from copy import deepcopy
from concurrent.futures import ThreadPoolExecutor

import pytest

from asqueel import UnsupportedFeatureError
from tests.native_compiler import test_native_star as stars
from tests.native_compiler.test_native_star import (
    table as table,
    test_star_selects_physical_then_static_virtual_columns as test_star_selects_physical_then_static_virtual_columns,
    test_bag_fields_requires_boolean as test_bag_fields_requires_boolean,
    test_static_alias_uses_existing_relation_join as test_static_alias_uses_existing_relation_join,
    test_subquery_star_uses_same_bag_fields_option as test_subquery_star_uses_same_bag_fields_option,
)
from tests.native_compiler.test_bag_items import source
from tests.object_tree.test_phase4_options import tree_database
from tests.object_tree.test_minimal_select import no_io as no_io


@pytest.fixture(autouse=True)
def use_tree(monkeypatch, no_io):
    monkeypatch.setattr(stars, 'build_database', tree_database)


def test_unsupported_static_is_not_silently_dropped(table):
    table.model.virtual_columns['not_implemented'].attributes['static'] = True
    with pytest.raises(UnsupportedFeatureError):
        table.query().compiled


@pytest.fixture
def bagdb():
    db = tree_database(source())
    try:
        yield db
    finally:
        db.closeConnection()


def test_bag_dependency_alias_relation_and_scope(bagdb):
    table = bagdb.table('app.item')
    query = table.query('$total,$alias,$weight',
        where='$id=:calculated_path AND $id<>:f1_calculated_path', calculated_path=3, f1_calculated_path=4)
    compiled = query.compiled
    assert set(compiled.params.values()) == {2, 3, 4, '/GenRoBag/specs/weight/text()', '/GenRoBag/specs/price/text()'}
    assert len(compiled.params) == 5
    assert compiled.input_parameters == ('calculated_path', 'f1_calculated_path')
    assert compiled.columns[1].dtype == 'N'
    assert '"t0"."payload"' in compiled.sql
    assert query.compiled == compiled
    related = table.query('$related,@parent_id.weight AS parent,$weight', where='$related>0', order_by='$related').compiled
    assert related.sql.count('LEFT JOIN') == 1
    assert 'CAST("t1"."payload" AS XML)' in related.sql
    assert 'CAST("t0"."payload" AS XML)' in related.sql
    assert len(related.params) == 3
    nested = table.query('$weight,$nested', where='$id=:calculated_path', calculated_path=5).compiled
    assert nested.sql.count('SELECT') == 2
    assert list(nested.params.values()).count('/GenRoBag/specs/weight/text()') == 2
    assert nested.params['calculated_path'] == 5


def test_bag_model_untouched_and_effective_declaration_reloaded(bagdb):
    table = bagdb.table('app.item')
    column = table.model.virtual_columns['weight']
    before = deepcopy(column.attributes)
    query = table.query('$weight')
    assert list(query.compiled.params.values()) == ['/GenRoBag/specs/weight/text()']
    assert column.attributes == before
    column.attributes['itempath'] = 'specs.price'
    assert list(table.query('$weight').compiled.params.values()) == ['/GenRoBag/specs/price/text()']
    assert 'sql_formula' not in column.attributes


def test_bag_compilation_scopes_are_thread_local(bagdb):
    def compile_for(id):
        with bagdb.tempEnv(id=id):
            result = bagdb.table('app.item').query('$total', where='$id=:env_id').compiled
            return result.params['env_id'], result.sql
    with ThreadPoolExecutor(max_workers=2) as pool:
        first, second = pool.map(compile_for, [1, 2])
    assert first[0] == 1 and second[0] == 2
    assert first[1] == second[1]
    assert 'id' not in bagdb.currentEnv


def test_bag_sqlite_explicitly_unsupported():
    db = tree_database(source('sqlite'))
    try:
        with pytest.raises(UnsupportedFeatureError, match='XPath'):
            db.table('app.item').query('$weight').compiled
    finally:
        db.closeConnection()


@pytest.mark.parametrize('implementation', ['postgres', 'sqlite'])
@pytest.mark.parametrize('bag_fields', [False, True])
def test_locked_star_includes_x_fields_as_legacy(implementation, bag_fields):
    # gnrsqldata/query.py: self.bagFields = bagFields or for_update.
    from tests.object_tree.test_minimal_select import recipe, bind

    source, table = recipe(implementation)
    table.column('payload', dtype='X')
    db = bind(source)
    try:
        query = db.table('sales.invoice').query('*', for_update=True, bagFields=bag_fields)
        assert 'payload' in [column.name for column in query.compiled.columns]
        ordinary = db.table('sales.invoice').query('*').compiled
        assert 'payload' not in [column.name for column in ordinary.columns]
        explicit = db.table('sales.invoice').query('$id', for_update=True).compiled
        assert [column.name for column in explicit.columns] == ['id']
        assert db._connections == {}
    finally:
        db.closeConnection()
