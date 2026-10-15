"""Native Bag extraction uses ordinary formulas and isolated parameter scopes."""
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from dataclasses import replace

import pytest

from asqueel import SqlDatabaseConfig, build_database
from asqueel.contracts import UnsupportedFeatureError
from asqueel.drivers.psycopg import PsycopgDriver
from asqueel.drivers.sqlite import SqliteDriver
from examples.test_invoice_pg import source as invoice_source


def source(backend='postgresql'):
    config = SqlDatabaseConfig()
    pkg = config.source.db('bags', implementation=backend).packages().package('app')
    pkg.options().type('money', dtype='N', size='14,2')
    table = pkg.table('item', pkey='id')
    table.column('id', dtype='L')
    table.column('details', dtype='X', sqlname='payload')
    table.column('parent_id', dtype='L').relation('app.item.id')
    specs = [('weight', 'specs.weight', 'N'), ('color', 'specs.color', 'T'),
             ('price', 'specs.price', 'money'), ('position', '#0.#1', 'T'),
             ('unit', 'specs.weight?unit', 'T'), ('first', 'repeated', 'T'),
             ('missing', 'absent', 'T'), ('integer', 'typed.integer', 'I'),
             ('bigint', 'typed.bigint', 'L'), ('real', 'typed.real', 'R'),
             ('boolean', 'typed.boolean', 'B'), ('date', 'typed.date', 'D'),
             ('time', 'typed.time', 'H'), ('stamp', 'typed.stamp', 'DH'),
             ('utc', 'typed.utc', 'DHZ')]
    for name, path, dtype in specs:
        table.bagItemColumn(name, bagcolumn='$details', itempath=path, dtype=dtype)
    table.bagItemColumn('default', bagcolumn='$details', itempath='specs.color')
    table.bagItemColumn('related', bagcolumn='@parent_id.details', itempath='specs.weight', dtype='N')
    table.aliasColumn('alias', '$weight')
    table.formulaColumn('total', '$weight + $price + :calculated_path', var_calculated_path=2, dtype='N')
    table.formulaColumn('nested', select=dict(table='app.item', columns='$weight',
                        where='$id=#THIS.parent_id'), dtype='N')
    return config


@pytest.fixture(autouse=True)
def no_io(monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail('Bag column compilation attempted database I/O')
    for driver in [PsycopgDriver, SqliteDriver]:
        monkeypatch.setattr(driver, 'connect', forbidden)
        monkeypatch.setattr(driver, 'execute', forbidden)


@pytest.fixture
def db():
    with build_database(source()) as database:
        yield database


def test_native_invoice_columns_preserve_custom_dtype_and_source():
    config = invoice_source()
    nodes = [node for _, node in config.source.query('#p,#n', deep=True)
             if node.node_tag == 'bagItemColumn']
    before = [deepcopy(dict(node.attr)) for node in nodes]
    with build_database(config) as db:
        table = db.model.table('invc.product')
        saved = {name: dict(table.columns[name].attributes)
                 for name in ('detail_weight', 'detail_color', 'detail_price')}
        result = db.table('invc.product').query('$detail_weight,$detail_color,$detail_price').compiled
        assert [c.dtype for c in result.columns] == ['N', 'T', 'N']
        assert table.columns['detail_price'].attributes['size'] == '14,2'
        assert set(result.params.values()) == {
            '/GenRoBag/specs/weight/text()', '/GenRoBag/specs/color/text()',
            '/GenRoBag/specs/price/text()'}
        assert result.sql.count('AS numeric') == 2
        assert result.input_parameters == ()
        for name, attributes in saved.items():
            assert dict(table.columns[name].attributes) == attributes
            assert 'sql_formula' not in attributes
            assert 'var_calculated_path' not in attributes
    assert [dict(node.attr) for node in nodes] == before


def test_dependencies_aliases_and_caller_have_separate_bindings(db):
    compiled = db.table('item').query('$total,$alias,$weight',
        where='$id=:calculated_path AND $id<>:f1_calculated_path',
        calculated_path=3, f1_calculated_path=4).compiled
    assert set(compiled.params.values()) == {
        2, 3, 4, '/GenRoBag/specs/weight/text()', '/GenRoBag/specs/price/text()'}
    assert len(compiled.params) == 5
    assert compiled.input_parameters == ('calculated_path', 'f1_calculated_path')
    assert compiled.columns[1].dtype == 'N'
    assert '"t0"."payload"' in compiled.sql


def test_relation_ownership_and_join_reuse(db):
    result = db.table('item').query('$related,@parent_id.weight AS parent,$weight',
                                    where='$related>0', order_by='$related').compiled
    assert result.sql.count('LEFT JOIN') == 1
    assert 'CAST("t1"."payload" AS XML)' in result.sql
    assert 'CAST("t0"."payload" AS XML)' in result.sql
    assert len(result.params) == 3
    assert set(result.params.values()) == {'/GenRoBag/specs/weight/text()'}


def test_nested_select_has_its_own_bindings(db):
    result = db.table('item').query('$weight,$nested', where='$id=:calculated_path',
                                    calculated_path=5).compiled
    assert result.sql.count('SELECT') == 2
    assert len(result.params) == 3
    assert list(result.params.values()).count('/GenRoBag/specs/weight/text()') == 2
    assert result.params['calculated_path'] == 5


def test_where_group_having_order_count_and_star(db):
    table = db.table('item')
    result = table.query('$color,COUNT(*) AS n', where='$weight>0', group_by='$color',
                         having='COUNT(*)>1', order_by='$color').compiled
    assert set(result.params.values()) == {'/GenRoBag/specs/weight/text()', '/GenRoBag/specs/color/text()'}
    assert 'GROUP BY' in result.sql and 'HAVING' in result.sql
    star = table.query('*', bagFields=True).compiled
    assert 'payload' in star.sql
    # Only static virtual columns are included in *, as before this increment.
    assert 'weight' not in [c.name for c in star.columns]
    count = db.compiler.count('app.item', columns='$color', distinct=True)
    assert 'xpath(' in count.sql and 'count(*)' in count.sql


def test_recompile_uses_effective_model_not_stale_generated_formula(db):
    query = db.table('item').query('$weight')
    first = query.compiled
    table = db.model.table('app.item')
    original = table.columns['weight']
    changed = replace(original, attributes={**original.attributes, 'itempath': 'specs.price'})
    replacement = replace(table, columns={**table.columns, 'weight': changed})
    # Existing effective-model boundary, not a RuntimeModel API.
    db.compiler.model = replace(db.model, tables={**db.model.tables, 'app.item': replacement})
    second = query.compiled
    assert set(first.params.values()) == {'/GenRoBag/specs/weight/text()'}
    assert set(second.params.values()) == {'/GenRoBag/specs/price/text()'}
    assert original.attributes['itempath'] == 'specs.weight'


def test_same_query_is_repeatable_and_thread_scopes_are_independent(db):
    query = db.table('item').query('$total', where='$id=:env_id')
    def compile_for(id):
        with db.tempEnv(id=id):
            result = query.compiled
            return result.sql, dict(result.params)
    with ThreadPoolExecutor(max_workers=2) as pool:
        first, second = list(pool.map(compile_for, [3, 5]))
    assert first[0] == second[0]
    assert set(first[1].values()) - set(second[1].values()) == {3}
    assert compile_for(3) == first


def test_path_is_bound_not_interpolated():
    config = source()
    path = "specs.name') -- $id :calculated_path"
    config.source['db'].packages().package('app').table('item').bagItemColumn(
        'quoted', bagcolumn='$details', itempath=path)
    with build_database(config) as db:
        compiled = db.table('item').query('$quoted').compiled
        assert path not in compiled.sql
        assert set(compiled.params.values()) == {f'/GenRoBag/{path.replace(".", "/")}/text()'}


def test_cycle_uses_existing_formula_guard():
    config = source()
    config.source['db'].packages().package('app').table('item').bagItemColumn(
        'cycle', bagcolumn='$cycle', itempath='value')
    with build_database(config) as db, pytest.raises(ValueError, match='Cyclic formula/alias'):
        db.table('item').query('$cycle').compiled


def test_sqlite_rejects_extraction_at_compile_time_without_emulation():
    with build_database(source('sqlite')) as db:
        assert db.table('item').query('$id').compiled.sql
        with pytest.raises(UnsupportedFeatureError, match='SQLite.*bagItemColumn'):
            db.table('item').query('$weight').compiled
