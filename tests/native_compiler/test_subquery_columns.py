"""Native subQueryColumn reuses child SELECT scopes and dialect aggregation."""


import pytest

from asqueel import SqlDatabaseConfig, build_database
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
