"""Regression probes replayed on legacy; no historical dedicated tests exist."""

from copy import deepcopy
from dataclasses import replace
from types import MethodType

import pytest


def declare(tables):
    owner = tables.table('owner', pkey='id')
    owner.column('id', dtype='L')
    owner.formulaColumn('scalar', select='total', dtype='N')
    owner.formulaColumn('present', exists='present', dtype='B')
    owner.formulaColumn(
        'named', '#a + #b + :factor', select_a='total', select_b='total', var_factor=3, dtype='N'
    )
    owner.formulaColumn('from_formula', sql_formula=True, dtype='N')
    owner.formulaColumn(
        'nested',
        select=dict(table='app.line', columns='MAX(@owner_id.scalar)', where='$owner_id=#THIS.id'),
        dtype='N',
    )
    owner.aliasColumn('alias', relation_path='$scalar')
    for mode in [None, 'json']:
        owner.subQueryColumn('collection_' + str(mode), query='rows', mode=mode)
    for name in ['missing', 'invalid', 'raises', 'cycle']:
        owner.formulaColumn(name, select=name)
    line = tables.table('line', pkey='id')
    line.column('id', dtype='L')
    line.column('amount', dtype='N')
    line.column('owner_id', dtype='L').relation('app.owner.id')
    line.column('second_owner_id', dtype='L').relation('app.owner.id')


def install(db):
    calls = []
    for name, default in [('owner', 7), ('line', 11)]:
        table = db.table('app.' + name)
        table.method_factor = default
        table.saved_query = dict(
            table='app.line',
            columns='MAX($amount * :factor)',
            where='$owner_id=#THIS.id',
            sqlparams={'factor': default},
        )

        def total(self):
            calls.append(self.fullname)
            return dict(
                self.saved_query,
                sqlparams={'factor': self.db.currentEnv.get('factor', self.method_factor)},
            )

        def present(self):
            return dict(table='app.line', columns='$id', where='$owner_id=#THIS.id')

        def rows(self):
            calls.append(self.fullname)
            return dict(
                table='app.line',
                columns='$amount',
                where='$owner_id=#THIS.id',
                order_by='$id',
                limit=1,
            )

        def formula(self, attr):
            attr['select_result'] = 'total'
            attr['var_factor'] = 5
            return '#result + :factor'

        def invalid(self):
            return self.db.currentEnv.get('invalid')

        def raises(self):
            raise TypeError('method application error')

        def cycle(self):
            return dict(table='app.owner', columns='$cycle', where='$id=#THIS.id')

        for method_name, function in [
            ('subquery_total', total),
            ('subquery_present', present),
            ('subquery_rows', rows),
            ('sql_formula_from_formula', formula),
            ('subquery_invalid', invalid),
            ('subquery_raises', raises),
            ('subquery_cycle', cycle),
        ]:
            setattr(table, method_name, MethodType(function, table))
    return calls


@pytest.fixture(params=['postgresql', 'sqlite'])
def db(request, monkeypatch):
    from asqueel import SqlDatabaseConfig, build_database
    from asqueel.drivers.psycopg import PsycopgDriver
    from asqueel.drivers.sqlite import SqliteDriver

    def forbidden(*args, **kwargs):
        pytest.fail('Subquery method compilation attempted database I/O')

    for driver in [PsycopgDriver, SqliteDriver]:
        monkeypatch.setattr(driver, 'connect', forbidden)
        monkeypatch.setattr(driver, 'execute', forbidden)
    config = SqlDatabaseConfig()
    declare(config.source.db('methods', implementation=request.param).packages().package('app'))
    with build_database(config) as db:
        db.method_calls = install(db)
        yield db


class TestLegacySubqueryMethodContract:
    """Same test bodies replayed against original legacy compilers."""

    def test_select_and_named_methods(self, db):
        sql = db.table('app.owner').query(columns='$scalar,$named').sqltext
        assert 'MAX(' in sql
        assert db.method_calls and set(db.method_calls) == {'app.owner'}

    def test_exists_method(self, db):
        sql = db.table('app.owner').query(columns='$present').sqltext
        assert 'EXISTS' in sql

    def test_related_column_dispatches_on_select_root(self, db):
        db.table('app.line').query(columns='@owner_id.scalar').sqltext
        assert db.method_calls and set(db.method_calls) == {'app.line'}

    def test_nested_select_uses_its_own_root(self, db):
        db.table('app.owner').query(columns='$scalar,$nested').sqltext
        assert set(db.method_calls) == {'app.owner', 'app.line'}

    def test_sql_formula_can_supply_method_reference(self, db):
        sql = db.table('app.owner').query(columns='$from_formula').sqltext
        assert 'MAX(' in sql
        assert db.method_calls and set(db.method_calls) == {'app.owner'}

    @pytest.mark.parametrize('mode', ['None', 'json'])
    def test_subquery_column_method(self, db, mode):
        if getattr(db, 'dialect', None) and db.dialect.name == 'sqlite' and mode != 'None':
            from asqueel.contracts import UnsupportedFeatureError

            with pytest.raises(UnsupportedFeatureError, match='SQLite does not support'):
                db.table('app.owner').query(columns='$collection_' + mode).sqltext
        else:
            sql = db.table('app.owner').query(columns='$collection_' + mode).sqltext
            assert 'SELECT' in sql
            assert db.method_calls and set(db.method_calls) == {'app.owner'}


def test_manglers_scopes_and_recompilation(db):
    query = db.table('owner').query(
        '$scalar,$named,$nested,$from_formula', where='$id=:factor', factor=19
    )
    first = query.compiled
    assert sorted(first.params.values()) == [3, 5, 7, 7, 7, 7, 11, 19]
    with db.tempEnv(factor=23):
        assert sorted(query.compiled.params.values()) == [3, 5, 19, 23, 23, 23, 23, 23]
    assert query.compiled == first
    assert db.model.table('owner').columns['scalar'].attributes['select'] == 'total'


def test_returned_mapping_and_model_remain_unchanged(db, monkeypatch):
    table = db.table('owner')
    before = deepcopy(table.saved_query)
    monkeypatch.setattr(table, 'subquery_total', lambda: table.saved_query)
    query = table.query('$scalar,$alias')
    assert list(query.compiled.params.values()) == [7, 7]
    assert table.saved_query == before
    table.saved_query['sqlparams']['factor'] = 29
    assert list(query.compiled.params.values()) == [29, 29]


def test_no_fallback_to_related_owner(db, monkeypatch):
    monkeypatch.setattr(db.table('line'), 'subquery_total', None)
    with pytest.raises(ValueError, match='app.line: missing table method subquery_total'):
        db.table('line').query('@owner_id.scalar').compiled


@pytest.mark.parametrize('value', [None, True, '', 'total', 42, [], [('table', 'app.line')]])
def test_method_must_return_mapping_without_recursive_dispatch(db, value):
    with (
        db.tempEnv(invalid=value),
        pytest.raises(ValueError, match='must return a subquery mapping'),
    ):
        db.table('owner').query('$invalid').compiled


def test_invalid_mapping_uses_common_validation(db):
    with db.tempEnv(invalid={}), pytest.raises(ValueError, match='nonempty table'):
        db.table('owner').query('$invalid').compiled


def test_errors_cycles_and_unbound_compiler(db):
    from asqueel import PostgresCompiler

    with pytest.raises(ValueError, match='missing table method subquery_missing'):
        db.table('owner').query('$missing').compiled
    with pytest.raises(TypeError, match='method application error'):
        db.table('owner').query('$raises').compiled
    with pytest.raises(ValueError, match='Cyclic formula/alias'):
        db.table('owner').query('$cycle').compiled
    with pytest.raises(ValueError, match='requires a database-bound table'):
        PostgresCompiler(db.model).select('owner', '$scalar')
    assert db.table('owner').query('$scalar').compiled


def test_effective_declaration_is_not_cached_between_compilations(db):
    # RuntimeModel is not introduced: exercise its existing resolved-model boundary.
    query = db.table('owner').query('$scalar')
    model = db.compiler.model
    table = model.table('owner')
    column = table.columns['scalar']
    changed = replace(column, attributes={**column.attributes, 'select': 'rows'})
    changed_table = replace(table, columns={**table.columns, 'scalar': changed})
    before = query.compiled
    try:
        db.compiler.model = replace(model, tables={**model.tables, table.key: changed_table})
        assert 'MAX(' not in query.compiled.sql
    finally:
        db.compiler.model = model
    assert query.compiled == before


def test_xml_method_reference_remains_outside_legacy_support():
    from asqueel import SqlDatabaseConfig, build_database

    config = SqlDatabaseConfig()
    table = config.source.db('xml').packages().package('app').table('owner')
    table.column('id')
    table.subQueryColumn('xml', mode='xml', query='rows')
    with (
        build_database(config) as db,
        pytest.raises(ValueError, match='legacy XML subQueryColumn requires a query mapping'),
    ):
        db.table('owner').query('$xml').compiled


def test_schema_entry_preserves_method_and_runs_only_at_compilation():
    from asqueel import SqlDatabaseConfig, build_database

    config = SqlDatabaseConfig()
    table = config.source.db('schema').schemas().schema('app').tables().table('owner')
    table.column('id')
    table.formulaColumn('value', select='total')
    with build_database(config) as db:
        calls = []

        def total():
            calls.append(True)
            return dict(table='app.owner', columns='COUNT(*)', where='$id=#THIS.id')

        db.table('owner').subquery_total = total
        query = db.table('owner').query('$value')
        assert not calls
        assert 'COUNT(*)' in query.compiled.sql
        assert calls == [True]


def test_same_query_uses_thread_local_method_values(db):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier

    barrier = Barrier(2)
    query = db.table('owner').query('$scalar')

    def compile_in_env(value):
        with db.tempEnv(factor=value):
            barrier.wait(timeout=5)
            return list(query.compiled.params.values())

    with ThreadPoolExecutor(max_workers=2) as pool:
        assert list(pool.map(compile_in_env, [23, 29])) == [[23], [29]]
    assert list(query.compiled.params.values()) == [7]
