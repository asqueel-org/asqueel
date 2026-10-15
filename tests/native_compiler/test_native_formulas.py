"""Native formulas preserve legacy ownership without sharing parameter state."""
from dataclasses import replace
from datetime import date

import pytest

from asqueel import PostgresCompiler, SqlDatabaseConfig, build_database
from asqueel.drivers.psycopg import PsycopgDriver
from asqueel.drivers.sqlite import SqliteDriver


@pytest.fixture(params=['postgresql', 'sqlite'])
def db(request, monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail('Formula compilation attempted database I/O')

    for driver in (PsycopgDriver, SqliteDriver):
        monkeypatch.setattr(driver, 'connect', forbidden)
        monkeypatch.setattr(driver, 'execute', forbidden)
    config = SqlDatabaseConfig()
    pkg = config.source.db('formulas', implementation=request.param).packages().package('sales')
    owner = pkg.table('owner', pkey='id')
    owner.column('id', dtype='L')
    owner.formulaColumn('scaled', '$id * :factor', var_factor=2, dtype='N')
    owner.formulaColumn('other', '$id * :factor', var_factor=5, dtype='N')
    owner.formulaColumn('combined', '$scaled + $other + :factor', var_factor=7, dtype='N')
    owner.formulaColumn('external', '$id + :factor', dtype='N')
    owner.formulaColumn('nested', '$external + :factor', var_factor=11, dtype='N')
    owner.formulaColumn('member', '$id IN :items', var_items=[1, 2], dtype='B')
    owner.formulaColumn('scalar', '$id + :items', var_items=8, dtype='L')
    owner.formulaColumn('day', ':env_workdate', dtype='D')
    owner.formulaColumn('parameters', '$id * :factor', parameters={'factor': 13}, dtype='N')
    owner.formulaColumn('expression', expression='$id + :offset', var_offset=1, dtype='N')
    owner.formulaColumn('duplicate', ':factor', var_factor=2, parameters={'factor': 3})
    owner.formulaColumn('mixed', '$id IN :items AND $id=:items', var_items=[1, 2])
    owner.formulaColumn('inherited_list', '$id IN :items')
    owner.formulaColumn('literal', ":text || ':text' /* :text $id */", var_text='$id')
    owner.aliasColumn('alias', '$scaled')
    owner.formulaColumn('cycle_a', '$cycle_b', dtype='N')
    owner.formulaColumn('cycle_b', '$cycle_a', dtype='N')
    child = pkg.table('child', pkey='id')
    child.column('id', dtype='L')
    child.column('owner_id', dtype='L').relation('sales.owner.id')
    child.column('other_owner_id', dtype='L').relation('sales.owner.id')
    child.formulaColumn('related', '@owner_id.scaled + :factor', var_factor=17, dtype='N')
    child.aliasColumn('related_alias', '@owner_id.scaled')
    with build_database(config) as database:
        yield database


def test_local_values_are_isolated_from_dependencies_and_query(db):
    compiled = db.table('owner').query('$combined, $scaled', where='$id=:factor', factor=19).compiled
    assert sorted(compiled.params.values()) == [2, 5, 7, 19]
    assert compiled.params['factor'] == 19
    assert compiled.input_parameters == ('factor',)
    assert compiled.sql.count('SELECT') == 1


def test_dependencies_do_not_inherit_calling_formula_locals(db):
    compiled = db.table('owner').query('$nested', factor=3).compiled
    assert sorted(compiled.params.values()) == [3, 11]
    assert compiled.input_parameters == ('factor',)
    with pytest.raises(ValueError, match='Missing query parameter: factor'):
        db.table('owner').query('$nested').compiled


def test_collection_and_scalar_names_are_separate_by_origin(db):
    compiled = db.table('owner').query(
        '$member, $scalar', where='$id=:items AND $id<>:f1_items', items=9, f1_items=10).compiled
    assert sorted(compiled.params.values()) == [1, 2, 8, 9, 10]
    assert compiled.params['items'] == 9
    assert compiled.params['f1_items'] == 10
    assert compiled.input_parameters == ('f1_items', 'items')


def test_alias_uses_target_formula_without_inheriting_executable_attributes(db):
    column = db.model.table('owner').columns['alias']
    assert not any(k.startswith(('var_', 'x_requires_compilation')) for k in column.attributes)
    compiled = db.table('owner').query('$scaled, $alias').compiled
    assert list(compiled.params.values()) == [2]
    assert compiled.columns[1].dtype == 'N'
    assert compiled.columns[1].source == 'sales.owner.alias'


def test_formula_binding_scope_does_not_create_or_duplicate_sql_joins(db):
    compiled = db.table('child').query(
        '$related, $related_alias, @owner_id.scaled AS direct',
        where='$related > 0', order_by='$related_alias').compiled
    assert compiled.sql.count('LEFT JOIN') == 1
    assert sorted(compiled.params.values()) == [2, 17]
    assert compiled.sql.count('SELECT') == 1


def test_existing_parameters_spelling_and_query_reuse(db):
    query = db.table('owner').query('$parameters, $day')
    before = dict(db.model.table('owner').columns['parameters'].attributes)
    with db.tempEnv(workdate=date(2026, 1, 1)):
        first = query.compiled
    with db.tempEnv(workdate=date(2026, 1, 2)):
        second = query.compiled
    assert first.sql == second.sql
    assert set(first.params.values()) == {13, date(2026, 1, 1)}
    assert set(second.params.values()) == {13, date(2026, 1, 2)}
    assert dict(db.model.table('owner').columns['parameters'].attributes) == before


def test_cycles_remain_explicit(db):
    with pytest.raises(ValueError, match='Cyclic formula/alias'):
        db.table('owner').query('$cycle_a').compiled


def test_existing_expression_alias_and_duplicate_local_declarations(db):
    compiled = db.table('owner').query('$expression').compiled
    assert list(compiled.params.values()) == [1]
    with pytest.raises(ValueError, match='repeated formula parameters'):
        db.table('owner').query('$duplicate').compiled


def test_a_local_does_not_consume_or_accept_an_external_override(db):
    with pytest.raises(ValueError, match='unused keyword'):
        db.table('owner').query('$scaled', factor=99).compiled
    compiled = db.table('owner').query('$scaled', sqlparams={'factor': 99}).compiled
    assert list(compiled.params.values()) == [2]
    assert compiled.input_parameters == ()


def test_same_parameter_origin_cannot_be_scalar_and_collection(db):
    with pytest.raises(ValueError, match='Parameter items is used both'):
        db.table('owner').query('$mixed').compiled
    with pytest.raises(ValueError, match='Parameter items is used both'):
        db.table('owner').query('$inherited_list', where='$id=:items', items=[1]).compiled


def test_formula_text_and_local_strings_are_not_sql_substitutions(db):
    compiled = db.table('owner').query('$literal').compiled
    assert "':text' /* :text $id */" in compiled.sql
    assert list(compiled.params.values()) == ['$id']


def test_two_relations_have_distinct_aliases_and_local_parameters(db):
    compiled = db.table('child').query(
        '@owner_id.scaled AS first, @other_owner_id.scaled AS second').compiled
    assert compiled.sql.count('LEFT JOIN') == 2
    assert list(compiled.params.values()) == [2, 2]
    assert '"t1"."id"' in compiled.sql and '"t2"."id"' in compiled.sql


def test_compilation_cannot_mutate_local_collections_or_environment(db):
    query = db.table('owner').query('$member, $scalar')
    with db.tempEnv(workdate=date(2026, 1, 1)):
        before = dict(db.currentEnv)
        first = query.compiled
        second = query.compiled
        assert dict(db.currentEnv) == before
    assert first.sql == second.sql
    assert first.params == second.params
    assert list(db.model.table('owner').columns['member'].attributes['var_items']) == [1, 2]


def test_a_replacement_model_does_not_reuse_compilation_state(db):
    # Future RuntimeModel must be able to supply another resolved model.
    # This tests the existing compiler contract, not a new overlay API.
    original = db.model.table('owner')
    old = original.columns['scaled']
    changed = replace(old, attributes={**old.attributes, 'var_factor': 23})
    table = replace(original, columns={**original.columns, 'scaled': changed})
    model = replace(db.model, tables={**db.model.tables, table.key: table})
    first = PostgresCompiler(db.model).select('owner', '$scaled')
    second = PostgresCompiler(model).select('owner', '$scaled')
    assert list(first.params.values()) == [2]
    assert list(second.params.values()) == [23]
    assert list(PostgresCompiler(db.model).select('owner', '$scaled').params.values()) == [2]
