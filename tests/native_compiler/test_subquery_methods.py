"""Regression probes replayed on legacy; no historical dedicated tests exist."""

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


@pytest.fixture(params=['postgres', 'sqlite'])
def db(request, monkeypatch):
    from asqueel import SqlDatabaseConfig, AsqueelDb
    from asqueel.adapters.postgres import SqlDbAdapter as PostgresAdapter
    from asqueel.adapters.sqlite import SqlDbAdapter as SqliteAdapter

    def forbidden(*args, **kwargs):
        pytest.fail('Subquery method compilation attempted database I/O')

    for driver in [PostgresAdapter, SqliteAdapter]:
        monkeypatch.setattr(driver, 'connect', forbidden)
        monkeypatch.setattr(driver, 'execute', forbidden)
    config = SqlDatabaseConfig()
    declare(config.source.db('methods', implementation=request.param).packages().package('app'))
    db = AsqueelDb(config)
    try:
        db.method_calls = install(db)
        yield db
    finally:
        db.closeConnection()


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
        if db.adapter.dialect == 'sqlite' and mode != 'None':
            from asqueel.contracts import UnsupportedFeatureError

            with pytest.raises(UnsupportedFeatureError, match='SQLite does not support'):
                db.table('app.owner').query(columns='$collection_' + mode).sqltext
        else:
            sql = db.table('app.owner').query(columns='$collection_' + mode).sqltext
            assert 'SELECT' in sql
            assert db.method_calls and set(db.method_calls) == {'app.owner'}
