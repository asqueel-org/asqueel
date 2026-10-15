"""Native subqueries share SELECT semantics without sharing SQL/parameter scopes."""
from copy import deepcopy
from dataclasses import replace

import pytest

from asqueel import SqlDatabaseConfig, build_database
from asqueel.compiler import QueryCompiler
from asqueel.drivers.psycopg import PsycopgDriver
from asqueel.drivers.sqlite import SqliteDriver


def subquery(**options):
    return dict(table='app.item', columns='SUM($amount)',
                where='$owner_id=#THIS.id', **options)


@pytest.fixture(params=['postgresql', 'sqlite'])
def db(request, monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail('Compilation attempted database I/O')

    for driver in (PsycopgDriver, SqliteDriver):
        monkeypatch.setattr(driver, 'connect', forbidden)
        monkeypatch.setattr(driver, 'execute', forbidden)
    config = SqlDatabaseConfig()
    pkg = config.source.db('subqueries', implementation=request.param).packages().package('app')
    owner = pkg.table('owner', pkey='id')
    owner.column('id', dtype='L')
    owner.column('parent_id', dtype='L').relation('app.owner.id')
    owner.formulaColumn('total', select=subquery(), dtype='N')
    owner.formulaColumn('present', exists=dict(table='app.item', where='$owner_id=#THIS.id'), dtype='B')
    owner.aliasColumn('alias', '$total')
    owner.formulaColumn('named', 'COALESCE(#low,0)+COALESCE(#high,0)+:threshold',
                        var_threshold=7, dtype='N',
                        select_low=dict(table='app.item', columns='SUM($amount)',
                                        where='$owner_id=#THIS.id AND $amount>:threshold',
                                        sqlparams={'threshold': 3}),
                        select_high=dict(table='app.item', columns='SUM($amount)',
                                         where='$owner_id=#THIS.id AND $amount>:threshold',
                                         sqlparams={'threshold': 5}))
    item = pkg.table('item', pkey='id')
    item.column('id', dtype='L')
    item.column('owner_id', dtype='L').relation('app.owner.id')
    item.column('amount', dtype='N')
    item.formulaColumn('nested', select=dict(table='app.owner', columns='$id',
                                           where='$id=#THIS.owner_id AND $id>:floor'))
    with build_database(config) as database:
        yield database


def compiler_with(db, **attributes):
    """Replace one resolved declaration; this does not add a RuntimeModel API."""
    table = db.model.table('owner')
    column = table.columns['total']
    column = replace(column, attributes={
        **column.attributes, 'select': None, 'exists': None, 'sql_formula': None, **attributes})
    table = replace(table, columns={**table.columns, 'total': column})
    model = replace(db.model, tables={**db.model.tables, table.key: table})
    return QueryCompiler(model, db.dialect, db.driver, environment=db.environment)


def test_native_scalar_exists_and_alias_keep_shape_and_metadata(db):
    query = db.table('owner').query('$total,$present,$alias').compiled
    assert query.sql.count('SELECT') == 4
    assert 'EXISTS (SELECT 1 AS "__exists"' in query.sql
    assert 'LIMIT' not in query.sql and 'JOIN' not in query.sql
    assert [c.dtype for c in query.columns] == ['N', 'B', 'N']
    assert query.columns[-1].source == 'app.owner.alias'


def test_child_and_formula_and_caller_parameters_do_not_capture_one_another(db):
    query = db.table('owner').query('$named',
        where='$id=:threshold AND $id<>:f1_threshold AND $id<>:s2_threshold',
        threshold=9, f1_threshold=88, s2_threshold=99)
    before = deepcopy(dict(db.model.table('owner').columns['named'].attributes))
    first, second = query.compiled, query.compiled
    assert sorted(first.params.values()) == [3, 5, 7, 9, 88, 99]
    assert first.params['f1_threshold'] == 88 and first.params['s2_threshold'] == 99
    assert first.input_parameters == ('f1_threshold', 's2_threshold', 'threshold')
    assert first.sql == second.sql and first.params == second.params
    assert dict(db.model.table('owner').columns['named'].attributes) == before


def test_relation_alias_and_inner_join_have_distinct_owners(db):
    compiler = compiler_with(db, select=dict(table='app.item', columns='SUM(@owner_id.id)',
                                            where='$owner_id=#THIS.id'))
    query = compiler.select('item', '@owner_id.total')
    assert query.sql.count('LEFT JOIN') == 2
    assert '"s1_t0"."owner_id"="t1"."id"' in query.sql
    assert 'SUM("s1_t1"."id")' in query.sql
    assert '"s1_t1"."id" = "s1_t0"."owner_id"' in query.sql or \
           '"s1_t0"."owner_id" = "s1_t1"."id"' in query.sql


def test_this_relation_adds_join_to_outer_scope(db):
    compiler = compiler_with(db, select=dict(table='app.item', columns='SUM($amount)',
                                            where='$owner_id=#THIS.@parent_id.id'))
    query = compiler.select('owner', '$total')
    assert query.sql.count('LEFT JOIN') == 1
    assert '"s1_t0"."owner_id"="t1"."id"' in query.sql
    assert '"t0"."parent_id"' in query.sql


def test_nested_subqueries_keep_nearest_this_and_input_origin(db):
    compiler = compiler_with(db, select=dict(table='app.item', columns='SUM($nested)',
                                            where='$owner_id=#THIS.id'))
    query = compiler.select('owner', '$total', sqlparams={'floor': 2})
    assert query.sql.count('SELECT') == 3
    assert '"s1_t0"."owner_id"="t0"."id"' in query.sql
    assert '"s2_t0"."id"="s1_t0"."owner_id"' in query.sql
    assert list(query.params.values()) == [2]
    assert query.input_parameters == ('floor',)


def test_repeated_subqueries_in_clauses_allocate_fresh_sql_scopes(db):
    query = db.table('owner').query('$total', where='$total>0', order_by='$total').compiled
    assert query.sql.count('SELECT') == 4
    for prefix in ('s1', 's2', 's3'):
        assert f'"{prefix}_t0"."owner_id"="t0"."id"' in query.sql


def test_grouping_having_distinct_order_and_limits_use_child_fields(db):
    compiler = compiler_with(db, select=dict(
        table='app.item', columns='SUM($amount)', where='$owner_id=#THIS.id',
        group_by='$owner_id', having='SUM($amount)>:minimum', sqlparams={'minimum': 4},
        order_by='SUM($amount) DESC', limit=2, offset=1))
    query = compiler.select('owner', '$total')
    assert 'GROUP BY "s1_t0"."owner_id"' in query.sql
    assert 'HAVING SUM("s1_t0"."amount")' in query.sql
    assert 'ORDER BY SUM("s1_t0"."amount") DESC' in query.sql
    assert 'LIMIT 2' in query.sql and 'OFFSET 1' in query.sql
    assert list(query.params.values()) == [4]
    query = compiler_with(db, select=dict(table='app.item', columns='$amount',
        where='$owner_id=#THIS.id', distinct=True, order_by='$amount', limit=1)).select('owner', '$total')
    assert 'SELECT DISTINCT "s1_t0"."amount"' in query.sql


def test_local_collection_and_scalar_uses_are_isolated_from_query(db):
    compiler = compiler_with(db, sql_formula='#a+#b',
        select_a=dict(table='app.item', columns='COUNT(*)',
                      where='$owner_id=#THIS.id AND $id IN :ids', sqlparams={'ids': [1, 2]}),
        select_b=dict(table='app.item', columns='COUNT(*)',
                      where='$owner_id=#THIS.id AND $id=:ids', sqlparams={'ids': 3}))
    query = compiler.select('owner', '$total', where='$id=:ids', sqlparams={'ids': 4})
    assert sorted(query.params.values()) == [1, 2, 3, 4]
    assert query.params['ids'] == 4


def test_environment_is_refreshed_and_literals_are_not_rewritten(db):
    compiler = compiler_with(db, select=dict(table='app.item', columns="'50% #THIS.id :env_floor'",
        where='$owner_id=#THIS.id AND $amount>:env_floor /* #THIS.bad :env_bad */', cast='text'))
    with db.tempEnv(floor=1):
        first = compiler.select('owner', '$total')
    with db.tempEnv(floor=2):
        second = compiler.select('owner', '$total')
    assert first.sql == second.sql
    assert list(first.params.values()) == [1] and list(second.params.values()) == [2]
    assert first.environment.keys == ('floor',)
    assert '/* #THIS.bad :env_bad */' in first.sql
    assert 'CAST((SELECT' in first.sql
    assert ('50%%' if db.dialect.name == 'postgresql' else '50%') in first.sql


@pytest.mark.parametrize('options, message', [
    ({'having': 'COUNT(*)>0'}, 'having requires group_by'),
    ({'limit': -1}, 'LIMIT must be'),
    ({'offset': True}, 'OFFSET must be'),
    ({'distinct': 'yes'}, 'distinct must be'),
    ({'group_by': '*'}, "group_by='\\*' is unsupported"),
    ({'sqlparams': []}, 'sqlparams must be a mapping'),
    ({'columns': '$id,$amount'}, 'exactly one result column'),
    ({'join_to': '$owner_id'}, 'Unsupported subquery options'),
])
def test_invalid_or_unagreed_child_options_are_rejected(db, options, message):
    with pytest.raises(ValueError, match=message):
        compiler_with(db, select={**subquery(), **options}).select('owner', '$total')


def test_native_subquery_cycles_and_method_references_fail_explicitly(db):
    with pytest.raises(ValueError, match='Cyclic formula/alias'):
        compiler_with(db, select=dict(table='app.owner', columns='$total',
                                     where='$id=#THIS.id')).select('owner', '$total')
    with pytest.raises(ValueError, match='requires a database-bound table'):
        compiler_with(db, select='totals').select('owner', '$total')
