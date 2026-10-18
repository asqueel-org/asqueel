"""Existing native/legacy method contracts on the hierarchical compiler."""
from copy import deepcopy

import pytest

from asqueel import SqlDatabase, SqlDatabaseConfig, UnsupportedFeatureError
from asqueel.configuration import _owned_handler
from asqueel.compiler import _TreeContext
from tests.native_compiler.test_subquery_methods import (
    declare, install, TestLegacySubqueryMethodContract as TestLegacySubqueryMethodContract,
)
from tests.object_tree.test_minimal_select import no_io as no_io


@pytest.fixture(params=['postgres', 'sqlite'])
def db(request, no_io):
    config = SqlDatabaseConfig()
    pkg = config.source.db('phase3', implementation=request.param).packages().package('app')
    declare(pkg)
    owner = pkg.table('owner')
    owner.column('parent_id', dtype='L').relation('app.owner.id', relation_name='children')
    owner.formulaColumn('many_op', '@children.sum($id)')
    owner.subQueryColumn('xml_method', mode='xml', query='rows')
    owner.formulaColumn('list_columns', select=dict(table='app.line', columns=['MAX($amount)'],
                                                    where='$owner_id=#THIS.id'))
    owner.formulaColumn('__protected_by_rule', '$id>0', dtype='B')
    owner.formulaColumn('__protecting_reasons', sql_formula=True, dtype='T')
    owner.formulaColumn('local', '$id*:factor', var_factor=5, dtype='N')
    owner.formulaColumn('composed', '$local + :factor', var_factor=3, dtype='N')
    owner.formulaColumn('this_parent', select=dict(table='app.line', columns='SUM($amount)',
                                                 where='$owner_id=#THIS.@parent_id.id'))
    owner.formulaColumn('this_parent_id', '#THIS.@parent_id.id', dtype='L')
    owner.formulaColumn('casted', select=dict(table='app.line', columns='MAX($amount)',
                                             where='$owner_id=#THIS.id', cast='numeric'))
    owner.formulaColumn('grouped', select=dict(table='app.line', columns='SUM($amount)',
        where='$owner_id=#THIS.id', group_by='$owner_id', having='SUM($amount)>:minimum',
        sqlparams={'minimum': 4}, order_by='SUM($amount) DESC', limit=2, offset=1))
    owner.formulaColumn('distinct_child', select=dict(table='app.line', columns='$amount',
        where='$owner_id=#THIS.id', distinct=True, order_by='$amount', limit=1))
    owner.formulaColumn('collections', '#a+#b',
        select_a=dict(table='app.line', columns='COUNT(*)',
                      where='$owner_id=#THIS.id AND $id IN :ids', sqlparams={'ids': [1, 2]}),
        select_b=dict(table='app.line', columns='COUNT(*)',
                      where='$owner_id=#THIS.id AND $id=:ids', sqlparams={'ids': 3}))
    with SqlDatabase(model=config.render(mode='objects_tree'), config=_owned_handler(config)) as database:
        database.method_calls = install(database)
        yield database


def test_locals_in_formula_dependency_child_siblings_and_caller_are_isolated(db):
    query = db.table('app.owner').query('$scalar,$named,$nested,$from_formula,$composed',
                                       where='$id=:factor AND $id<>:f1_factor',
                                       factor=19, f1_factor=101)
    first = query.compiled
    assert sorted(first.params.values()) == [3, 3, 5, 5, 7, 7, 7, 7, 11, 19, 101]
    assert first.input_parameters == ('f1_factor', 'factor')
    assert first.params['f1_factor'] == 101
    assert '"t0_t0"' in first.sql and '"t0_t1_t0"' in first.sql
    assert query.compiled == first
    with db.tempEnv(factor=23):
        assert sorted(query.compiled.params.values()) == [3, 3, 5, 5, 19, 23, 23, 23, 23, 23, 101]
    assert query.compiled == first


def test_this_relation_belongs_to_outer_context(db):
    compiled = db.table('app.owner').query('$this_parent').compiled
    assert compiled.sql.count('LEFT JOIN') == 1
    assert '"t0_t0"."owner_id"="t1"."id"' in compiled.sql
    assert '"t0"."parent_id"' in compiled.sql


def test_this_relation_in_sql_formula_reuses_the_direct_join(db):
    # GenroPy ba377674f7, TestFormulaSqlThisRelation: expand THIS before refs.
    compiled = db.table('app.owner').query(
        '$this_parent_id,@parent_id.id AS direct,$this_parent_id AS repeated').compiled
    assert '#THIS' not in compiled.sql
    assert '$' not in compiled.sql
    assert compiled.sql.count('LEFT JOIN') == 1
    assert '( "t1"."id" ) AS "this_parent_id"' in compiled.sql
    assert '"t1"."id" AS direct' in compiled.sql
    assert '( "t1"."id" ) AS repeated' in compiled.sql
    assert compiled.params == {}


def test_child_clauses_and_cast_use_legacy_aliases(db):
    compiled = db.table('app.owner').query('$grouped,$distinct_child,$casted').compiled
    assert 'GROUP BY "t0_t0"."owner_id"' in compiled.sql
    assert 'HAVING SUM("t0_t0"."amount")' in compiled.sql
    assert 'ORDER BY SUM("t0_t0"."amount") DESC' in compiled.sql
    assert 'LIMIT 2' in compiled.sql and 'OFFSET 1' in compiled.sql
    assert 'SELECT DISTINCT "t0_t0"."amount"' in compiled.sql
    assert 'CAST( ( SELECT' in compiled.sql and 'AS numeric)' in compiled.sql
    assert list(compiled.params.values()) == [4]
    assert not compiled.input_parameters


def test_collection_and_scalar_parameter_with_same_name_do_not_mix(db):
    compiled = db.table('app.owner').query('$collections', where='$id=:ids', ids=4).compiled
    assert sorted(compiled.params.values()) == [1, 2, 3, 4]
    assert compiled.params['ids'] == 4
    assert compiled.input_parameters == ('ids',)


def test_method_mapping_and_model_are_not_mutated_or_cached_between_compiles(db, monkeypatch):
    table = db.table('app.owner')
    before = deepcopy(table.saved_query)
    attrs = deepcopy(table.model.virtual_columns['scalar'].attributes)
    monkeypatch.setattr(table, 'subquery_total', lambda: table.saved_query)
    query = table.query('$scalar,$alias')
    assert list(query.compiled.params.values()) == [7, 7]
    assert table.saved_query == before
    table.saved_query['sqlparams']['factor'] = 29
    assert list(query.compiled.params.values()) == [29, 29]
    assert table.model.virtual_columns['scalar'].attributes == attrs
    # Same existing RuntimeModel boundary: effective declarations are read
    # afresh on the next compile; no overlay API is added by this test.
    column = table.model.virtual_columns['local']
    column.attributes['var_factor'] = 31
    assert list(table.query('$local').compiled.params.values()) == [31]


def test_no_method_fallback_and_no_many_handler(db, monkeypatch):
    monkeypatch.setattr(db.table('app.line'), 'subquery_total', None)
    with pytest.raises(UnsupportedFeatureError, match='app.line: missing table method subquery_total'):
        db.table('app.line').query('@owner_id.scalar').compiled
    assert {name for name in vars(_TreeContext) if name.startswith('many_')} == {'many_aggr'}


def test_cycles_and_method_errors_remain_explicit(db):
    with pytest.raises(ValueError, match='Cyclic formula/alias'):
        db.table('app.owner').query('$cycle').compiled
    with pytest.raises(TypeError, match='method application error'):
        db.table('app.owner').query('$raises').compiled
    assert db.table('app.owner').query('$scalar').compiled.sql


def test_many_operations_inside_owner_and_related_formulas_have_no_handlers(db):
    for columns in ('$many_op', '@parent_id.many_op'):
        with pytest.raises(UnsupportedFeatureError, match='many_sum not yet supported'):
            db.table('app.owner').query(columns).compiled


def test_xml_method_reference_keeps_existing_legacy_limit(db):
    with pytest.raises(UnsupportedFeatureError, match='XML subQueryColumn requires a query mapping'):
        db.table('app.owner').query('$xml_method').compiled


def test_sequence_columns_use_same_subquery_path(db):
    compiled = db.table('app.owner').query('$list_columns').compiled
    assert 'MAX("t0_t0"."amount")' in compiled.sql


def test_builtin_method_reads_tree_virtual_columns(db):
    compiled = db.table('app.owner').query('$__protecting_reasons').compiled
    assert 'CASE WHEN ( "t0"."id">0 ) IS TRUE THEN' in compiled.sql
    assert "'rule'" in compiled.sql


def test_only_final_sql_is_prepared_by_driver(db, monkeypatch):
    calls = []
    original = db.compiler.adapter.prepare_sql

    def prepare(sql, params, snapshot):
        calls.append((sql, deepcopy(params)))
        return original(sql, params, snapshot)

    monkeypatch.setattr(db.compiler.adapter, 'prepare_sql', prepare)
    compiled = db.table('app.owner').query('$named,$nested,$collections').compiled
    assert len(calls) == 1
    assert calls[0][0].count('SELECT') > 3
    assert compiled.params
