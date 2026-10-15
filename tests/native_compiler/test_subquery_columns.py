"""Native subQueryColumn reuses child SELECT scopes and dialect aggregation."""

from copy import deepcopy

import pytest

from asqueel import SqlDatabaseConfig, build_database
from asqueel.contracts import UnsupportedFeatureError
from asqueel.drivers.psycopg import PsycopgDriver
from asqueel.drivers.sqlite import SqliteDriver


def source(backend='postgresql'):
    config = SqlDatabaseConfig()
    pkg = config.source.db('subquery_columns', implementation=backend).packages().package('app')
    owner = pkg.table('owner', pkey='id')
    owner.column('id', dtype='L')
    owner.column('parent_id', dtype='L').relation('app.owner.id')
    item = pkg.table('item', pkey='id')
    item.column('id', dtype='L')
    item.column('owner_id', dtype='L').relation('app.owner.id')
    item.column('amount', dtype='N')
    item.column('label')
    item.options().sys_fields(id=False, draft=True)
    item.options().partition('scope', field='owner_id', value=99)
    scalar = dict(table='app.item', columns='MAX($amount)', where='$owner_id=#THIS.id')
    owner.subQueryColumn('maximum', query=scalar, dtype='N')
    owner.subQueryColumn('other_mode', query=scalar, mode='sum', dtype='N')
    owner.subQueryColumn(
        'twice',
        query=dict(table='app.item', columns='SUM($amount * :factor)', where='$owner_id=#THIS.id'),
        var_factor=2,
        dtype='N',
    )
    owner.subQueryColumn(
        'triple',
        query=dict(table='app.item', columns='SUM($amount * :factor)', where='$owner_id=#THIS.id'),
        var_factor=3,
        dtype='N',
    )
    owner.aliasColumn('max_alias', '$maximum')
    owner.formulaColumn('dependent', '$maximum + $twice')
    owner.subQueryColumn('missing')
    owner.subQueryColumn('method_reference', query='pending_method')
    owner.subQueryColumn(
        'cycle', query=dict(table='app.owner', columns='$cycle', where='$id=#THIS.id')
    )
    for mode in ['json', 'xml']:
        owner.subQueryColumn(
            mode,
            query=dict(
                table='app.item',
                columns='$id,$label,$amount',
                where='$owner_id=#THIS.id',
                order_by='$id DESC',
                limit=2,
                offset=1,
            ),
            mode=mode,
        )
        owner.subQueryColumn(
            mode + '_locals',
            query=dict(
                table='app.item', columns='$amount * :factor AS value', where='$owner_id=#THIS.id'
            ),
            mode=mode,
            var_factor=4,
        )
        owner.subQueryColumn(
            mode + '_group',
            query=dict(
                table='app.item',
                columns='$owner_id,SUM($amount) AS total',
                where='$owner_id=#THIS.id',
                group_by='$owner_id',
                having='SUM($amount)>:minimum',
                sqlparams={'minimum': 10},
            ),
            mode=mode,
        )
        owner.subQueryColumn(
            mode + '_join',
            query=dict(
                table='app.item', columns='@owner_id.id AS owner,$label', where='$owner_id=#THIS.id'
            ),
            mode=mode,
        )
        owner.subQueryColumn(
            mode + '_visible',
            query=dict(
                table='app.item',
                columns='$id',
                where='$owner_id=#THIS.id',
                ignorePartition=False,
                excludeDraft=True,
                excludeLogicalDeleted=True,
            ),
            mode=mode,
        )
    owner.subQueryColumn(
        'nested_json',
        query=dict(table='app.owner', columns='$id,$maximum,$json', where='$parent_id=#THIS.id'),
        mode='json',
    )
    return config


@pytest.fixture(params=['postgresql', 'sqlite'])
def db(request, monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail('subQueryColumn compilation attempted database I/O')

    for driver in [PsycopgDriver, SqliteDriver]:
        monkeypatch.setattr(driver, 'connect', forbidden)
        monkeypatch.setattr(driver, 'execute', forbidden)
    with build_database(source(request.param)) as db:
        yield db


def test_plain_mode_alias_and_formula_dependency(db):
    table = db.table('app.owner')
    query = table.query('$maximum,$max_alias,$dependent').compiled
    assert [c.dtype for c in query.columns[:2]] == ['N', 'N']
    assert 'MAX(' in query.sql and 'SUM(' in query.sql
    assert 'LIMIT' not in query.sql
    plain = table.query('$maximum AS result').compiled
    other = table.query('$other_mode AS result').compiled
    assert plain.sql == other.sql  # mode='sum' must not invent a SUM wrapper.
    assert not plain.params
    assert 'IS NOT TRUE' not in plain.sql and 'IS NULL' not in plain.sql


def test_local_bindings_do_not_capture_sibling_or_caller_parameters(db):
    table = db.table('app.owner')
    before = deepcopy(dict(table.model.columns['twice'].attributes))
    query = table.query(
        '$twice,$triple', where='$id=:factor AND $id<>:f1_factor', factor=5, f1_factor=88
    )
    first, second = query.compiled, query.compiled
    assert first == second
    assert sorted(first.params.values()) == [2, 3, 5, 88]
    assert first.params['f1_factor'] == 88
    assert first.input_parameters == ('f1_factor', 'factor')
    assert dict(table.model.columns['twice'].attributes) == before


def test_missing_query_and_method_reference_remain_explicit_errors(db):
    with pytest.raises(ValueError, match='subquery must be a mapping'):
        db.table('owner').query('$missing').compiled
    with pytest.raises(UnsupportedFeatureError, match='missing table method subquery_pending_method'):
        db.table('owner').query('$method_reference').compiled


def test_cycles_use_existing_formula_guard(db):
    with pytest.raises(ValueError, match='Cyclic formula/alias'):
        db.table('owner').query('$cycle').compiled


@pytest.mark.parametrize('mode', ['json', 'xml'])
def test_aggregate_uses_same_child_plan_with_pagination_and_defaults(db, mode):
    table = db.table('owner')
    if db.dialect.name == 'sqlite':
        with pytest.raises(
            UnsupportedFeatureError, match='SQLite does not support legacy subQueryColumn'
        ):
            table.query('$' + mode).compiled
        return
    query = table.query('$' + mode, distinct=True).compiled
    assert query.sql.startswith('SELECT DISTINCT')
    assert query.sql.count('SELECT') == 3
    assert 'ORDER BY' in query.sql and 'LIMIT 2\nOFFSET 1' in query.sql
    assert 'IS NOT TRUE' not in query.sql and 'IS NULL' not in query.sql
    assert '#THIS' not in query.sql and not query.params
    if mode == 'json':
        assert 'jsonb_agg(row_to_json(' in query.sql
    else:
        assert 'CAST(xmlagg(xmlelement(name "app_owner_xml_xml"' in query.sql
        assert 'AS text)' in query.sql


@pytest.mark.parametrize('mode', ['json', 'xml'])
@pytest.mark.parametrize('db', ['postgresql'], indirect=True)
def test_aggregate_grouping_joins_and_policy_overrides(db, mode):
    table = db.table('owner')
    group = table.query('$' + mode + '_group').compiled
    assert 'GROUP BY' in group.sql and 'HAVING' in group.sql
    assert list(group.params.values()) == [10]
    joined = (
        db.table('item')
        .query(
            '@owner_id.' + mode + '_join',
            ignorePartition=True,
            excludeDraft=False,
            excludeLogicalDeleted=False,
        )
        .compiled
    )
    assert joined.sql.count('LEFT JOIN') == 2
    assert '"owner_id"="t1"."id"' in joined.sql
    visible = table.query('$' + mode + '_visible').compiled
    assert 'IS NOT TRUE' in visible.sql and 'IS NULL' in visible.sql
    assert list(visible.params.values()) == [99]


@pytest.mark.parametrize('db', ['postgresql'], indirect=True)
def test_json_xml_and_nested_scopes_keep_parameters_distinct(db):
    query = (
        db.table('owner')
        .query('$json_locals,$xml_locals,$twice,$nested_json', where='$id=:factor', factor=7)
        .compiled
    )
    assert sorted(query.params.values()) == [2, 4, 4, 7]
    assert query.sql.count('jsonb_agg') == 3
    assert '#THIS' not in query.sql
    assert '"s' in query.sql


def test_multicolumn_plain_subquery_still_requires_one_result(db):
    config = source(db.dialect.name)
    config.source['db'].packages().package('app').table('owner').subQueryColumn(
        'multi', query=dict(table='app.item', columns='$id,$amount', where='$owner_id=#THIS.id')
    )
    with pytest.raises(ValueError, match='exactly one result column'):
        build_database(config).table('owner').query('$multi').compiled
