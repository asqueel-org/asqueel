"""Legacy method dispatch shares formula compilation, never its mutable state."""
from dataclasses import replace
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

import pytest

from asqueel import PostgresCompiler, SqlDatabaseConfig, SqlTable, build_database
from asqueel.drivers.psycopg import PsycopgDriver
from asqueel.drivers.sqlite import SqliteDriver
from asqueel.model_sections import thaw


class Owner(SqlTable):
    def __init__(self, *args):
        super().__init__(*args)
        self.calls = []

    def sql_formula_scaled(self, attr):
        self.calls.append('scaled')
        attr['var_factor'] = self.db.currentEnv.get('factor', 7)
        return '$amount * :factor'

    def sql_formula_total(self, attr):
        self.calls.append('total')
        attr['select_lines']['sqlparams']['factor'] = 5
        attr['var_factor'] = 3
        return 'COALESCE(#lines,0) + :factor'

    def sql_formula_member(self, attr):
        attr['var_items'].append(3)
        return '$id IN :items'

    def sql_formula_cycle(self, attr):
        return '$cycle_alias'

    def sql_formula_invalid(self, attr):
        return self.db.currentEnv['result']

    def sql_formula_raises(self, attr):
        raise TypeError('application failure')


class Line(SqlTable):
    def sql_formula_scaled(self, attr):
        attr['var_factor'] = 11
        return '$amount * :factor'


@pytest.fixture(params=['postgresql', 'sqlite'])
def db(request, monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail('Method formula compilation attempted database I/O')

    for driver in (PsycopgDriver, SqliteDriver):
        monkeypatch.setattr(driver, 'connect', forbidden)
        monkeypatch.setattr(driver, 'execute', forbidden)
    config = SqlDatabaseConfig()
    pkg = config.source.db('methods', implementation=request.param).packages().package('app')
    owner = pkg.table('owner', pkey='id', x_table_class=Owner)
    owner.column('id', dtype='L')
    owner.column('amount', dtype='N')
    owner.formulaColumn('scaled', sql_formula=True, dtype='N', var_factor=0)
    owner.formulaColumn('combined', '$scaled + $total + :factor', var_factor=13)
    owner.formulaColumn('total', sql_formula=True, dtype='N', var_factor=0,
                        select_lines=dict(table='app.line', columns='SUM($scaled)',
                                          where='$owner_id=#THIS.id AND $amount>:factor',
                                          sqlparams={'factor': 0}))
    owner.formulaColumn('member', sql_formula=True, var_items=[1, 2])
    for name in ('cycle', 'missing', 'invalid', 'raises'):
        owner.formulaColumn(name, sql_formula=True)
    owner.aliasColumn('scaled_alias', '$scaled')
    owner.aliasColumn('cycle_alias', '$cycle')
    line = pkg.table('line', pkey='id', x_table_class=Line)
    line.column('id', dtype='L')
    line.column('amount', dtype='N')
    line.column('owner_id', dtype='L').relation('app.owner.id')
    line.column('second_owner_id', dtype='L').relation('app.owner.id')
    line.formulaColumn('scaled', sql_formula=True, dtype='N')
    line.aliasColumn('owner_scaled', '@owner_id.scaled')
    with build_database(config) as database:
        yield database


def test_methods_are_lazy_and_repeated_uses_share_only_one_compilation(db):
    table = db.table('owner')
    query = table.query('$scaled,$scaled_alias', where='$scaled>:factor', factor=2)
    assert table.calls == []
    first = query.compiled
    assert table.calls == ['scaled']
    assert sorted(first.params.values()) == [2, 7]
    with db.tempEnv(factor=17):
        second = query.compiled
        assert sorted(second.params.values()) == [2, 17]
    assert sorted(query.compiled.params.values()) == [2, 7]
    assert sorted(first.params.values()) == [2, 7]
    assert table.calls == ['scaled'] * 3


def test_method_edits_are_local_and_nested_scopes_do_not_mix(db):
    table = db.table('owner')
    original = thaw(table.model.columns['total'].attributes)
    query = table.query('$combined + :factor AS result', factor=19)
    first = query.compiled
    assert sorted(first.params.values()) == [3, 5, 7, 11, 13, 19]
    assert first.sql == query.compiled.sql
    assert dict(first.params) == dict(query.compiled.params)
    assert thaw(table.model.columns['total'].attributes) == original
    assert table.model.columns['scaled'].attributes['var_factor'] == 0
    assert db.currentEnv == {}


def test_method_gets_mutable_collections_without_changing_the_model(db):
    table = db.table('owner')
    query = table.query('$member', where='$id IN :items', items=[8, 9])
    first = query.compiled
    assert dict(first.params) == dict(query.compiled.params)
    assert sorted(first.params.values()) == [1, 2, 3, 8, 9]
    assert table.model.columns['member'].attributes['var_items'] == [1, 2]


def test_method_is_bound_to_the_related_table_and_row_alias(db):
    compiled = db.table('line').query(
        '$scaled,$owner_scaled,@second_owner_id.scaled AS second',
        where='@owner_id.scaled>:factor', factor=23).compiled
    assert sorted(compiled.params.values()) == [7, 7, 11, 23]
    assert compiled.sql.count('LEFT JOIN') == 2
    assert db.table('owner').calls == ['scaled']


def test_missing_method_and_standalone_compiler_are_explicit(db):
    with pytest.raises(ValueError, match=r'missing table method sql_formula_missing\(attr\)'):
        db.table('owner').query('$missing').compiled
    with pytest.raises(ValueError, match='requires a database-bound table'):
        PostgresCompiler(db.model).select('owner', '$scaled')


@pytest.mark.parametrize('result', [None, True, '', '  ', 42, {'sql': '$id'}])
def test_method_must_return_sql_text(db, result):
    with db.tempEnv(result=result), pytest.raises(ValueError, match='must return nonempty SQL'):
        db.table('owner').query('$invalid').compiled


def test_cycles_and_method_errors_keep_their_diagnostics(db):
    with pytest.raises(ValueError, match='Cyclic formula/alias'):
        db.table('owner').query('$cycle').compiled
    with pytest.raises(TypeError, match='application failure'):
        db.table('owner').query('$raises').compiled
    assert db.table('owner').query('$scaled').compiled


def test_new_effective_declaration_has_no_cached_formula_or_locals(db):
    # Exercise the existing model boundary, not a new RuntimeModel API.
    query = db.table('owner').query('$member')
    original_model = db.compiler.model
    table = original_model.table('owner')
    column = table.columns['member']
    updated = replace(column, attributes={**column.attributes, 'var_items': [10]})
    updated_table = replace(table, columns={**table.columns, 'member': updated})
    first = query.compiled
    try:
        db.compiler.model = replace(original_model, tables={**original_model.tables, table.key: updated_table})
        assert sorted(query.compiled.params.values()) == [3, 10]
    finally:
        db.compiler.model = original_model
    assert dict(query.compiled.params) == dict(first.params)


def test_same_query_compiles_with_thread_local_method_values(db):
    query = db.table('owner').query('$scaled')
    barrier = Barrier(2)

    def compile_in_env(value):
        with db.tempEnv(factor=value):
            barrier.wait(timeout=5)
            return list(query.compiled.params.values())

    with ThreadPoolExecutor(max_workers=2) as pool:
        assert list(pool.map(compile_in_env, [23, 29])) == [[23], [29]]
    assert list(query.compiled.params.values()) == [7]


def test_existing_schema_declaration_can_defer_a_method_until_compile():
    config = SqlDatabaseConfig()
    table = config.source.db('methods').schemas().schema('app').tables().table(
        'owner', pkey='id', x_table_class=Owner)
    table.column('id', dtype='L')
    table.column('amount', dtype='N')
    table.formulaColumn('scaled', sql_formula=True, dtype='N')
    with build_database(config) as db:
        assert db.table('owner').calls == []
        assert list(db.table('owner').query('$scaled').compiled.params.values()) == [7]
