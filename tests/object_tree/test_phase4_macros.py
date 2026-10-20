"""Macro scopes and pkey opt-in on the tree, using legacy syntax only."""
from datetime import date

import pytest

from asqueel import SqlDatabaseConfig, UnsupportedFeatureError
from tests.object_tree.test_minimal_select import db as db, no_io as no_io
from tests.object_tree.test_phase4_options import tree_database


@pytest.mark.parametrize('period, dates, operator', [
    ('oggi', [date(2026, 10, 14)], '='),
    ('mese scorso', [date(2026, 9, 1), date(2026, 9, 30)], 'BETWEEN'),
    ('2025', [date(2025, 1, 1), date(2025, 12, 31)], 'BETWEEN'),
    ('2026-01-01;2026-01-31', [date(2026, 1, 1), date(2026, 1, 31)], 'BETWEEN'),
    ('2026-01-01,2026-01-31', [date(2026, 1, 1), date(2026, 1, 31)], 'BETWEEN'),
    ('dal 2026-01-01', [date(2026, 1, 1)], '>='),
    ('al 2026-01-31', [date(2026, 1, 31)], '<='),
    ('sempre', [], 'true'), (None, [], 'true'),
])
def test_period_uses_existing_decoder(db, period, dates, operator):
    db.currentEnv['locale'] = 'it'
    query = db.table('sales.invoice').query('$id', where='#PERIOD($issued,:period)', period=period).compiled
    assert operator in query.sql and '#PERIOD' not in query.sql
    # R2 retains unused caller kwargs, including the decoded period text.
    assert query.params['period'] == period
    assert [v for k,v in query.params.items() if k != 'period'] == dates
    assert query.input_parameters == ('period',)
    assert query.environment_keys == ('locale', 'workdate')


def test_period_repeat_collision_and_environment_refresh(db):
    db.currentEnv['locale'] = 'it'
    def build():
        return db.table('sales.invoice').query('$id',
            where='(#PERIOD($issued,period) OR #PERIOD($issued,:period)) AND $id=:period_from',
            period='oggi', period_from=41)
    query = build()
    first = query.compiled
    with db.tempEnv(workdate=date(2026, 10, 15)):
        second = build().compiled
    assert first.params['period_from'] == second.params['period_from'] == 41
    assert date(2026, 10, 14) in first.params.values()
    assert date(2026, 10, 15) in second.params.values()
    assert first.sql == second.sql
    assert first.input_parameters == ('period', 'period_from')
    assert query.compiled is first
    assert len([v for v in first.params.values() if isinstance(v, date)]) == 1


def test_child_period_formula_ranges_and_this_keep_scopes(no_io):
    config = SqlDatabaseConfig()
    pkg = config.source.db('scope').packages().package('app')
    owner = pkg.table('owner', pkey='id')
    owner.column('id', dtype='L')
    owner.formulaColumn('within', '#IN_RANGE($id,:low,:high)', var_low=0, var_high=9, dtype='B')
    owner.formulaColumn('a', select=dict(table='app.item', columns='COUNT(*)',
        where='$owner_id=#THIS.id AND #PERIOD($issued,period)', sqlparams={'period':'oggi'}))
    owner.formulaColumn('b', select=dict(table='app.item', columns='COUNT(*)',
        where='$owner_id=#THIS.id AND #PERIOD($issued,period)', sqlparams={'period':'ieri'}))
    item = pkg.table('item')
    item.column('owner_id', dtype='L')
    item.column('issued', dtype='D')
    db = tree_database(config)
    try:
        db.currentEnv.update(workdate=date(2026, 10, 14), locale='it')
        query = db.table('app.owner').query('$within,$a,$b', where='$id=:s2_period_from', s2_period_from=11)
        compiled = query.compiled
        assert compiled.params['s2_period_from'] == 11
        assert date(2026, 10, 14) in compiled.params.values()
        assert date(2026, 10, 13) in compiled.params.values()
        assert 0 in compiled.params.values() and 9 in compiled.params.values()
        assert '#THIS' not in compiled.sql and '#PERIOD' not in compiled.sql and '#IN_RANGE' not in compiled.sql
        assert compiled.input_parameters == ('s2_period_from',)
        assert query.compiled == compiled
    finally:
        db.closeConnection()


@pytest.mark.parametrize('macro', ['#PREF(company)', '#TSQUERY($total,:search)'])
def test_unported_macros_remain_explicit(db, macro):
    with pytest.raises(UnsupportedFeatureError):
        db.table('sales.invoice').query('$id', where=macro).compiled


@pytest.mark.parametrize('macro', ['#ENV(company)', '#BAG($total)', '#BAGCOLS($total)'])
def test_ported_macros_in_a_where_clause_raise(db, macro):
    with pytest.raises(ValueError, match='is expanded only in'):
        db.table('sales.invoice').query('$id', where=macro).compiled


def test_pkey_is_opt_in_and_uses_legacy_alias(db):
    table = db.table('sales.invoice')
    assert [c.name for c in table.query('$label').compiled.columns] == ['label']
    assert [c.name for c in table.query('$label', addPkeyColumn=False).compiled.columns] == ['label']
    result = table.query('$label', addPkeyColumn=True).compiled
    assert [c.name for c in result.columns] == ['label', 'pkey']
    assert '"t0"."id" AS "pkey"' in result.sql
    aggregate = table.query('COUNT(*) AS n', group_by='*', addPkeyColumn=True).compiled
    assert [c.name for c in aggregate.columns] == ['n']
    distinct = table.query('$label', distinct=True, addPkeyColumn=True).compiled
    assert [c.name for c in distinct.columns] == ['label']
    with pytest.raises(ValueError, match='addPkeyColumn must be a boolean'):
        table.query('$label', addPkeyColumn='yes').compiled
