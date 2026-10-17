"""Inverse traversal uses the existing join tree and parameter allocator."""

import pytest

from asqueel import SqlDatabaseConfig, build_database
from asqueel.contracts import UnsupportedFeatureError
from asqueel.adapters.postgres import SqlDbAdapter as PostgresAdapter
from asqueel.adapters.sqlite import SqlDbAdapter as SqliteAdapter


@pytest.fixture(params=['postgres', 'sqlite'])
def db(request, monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail('Inverse compilation attempted database I/O')

    for driver in (PostgresAdapter, SqliteAdapter):
        monkeypatch.setattr(driver, 'connect', forbidden)
        monkeypatch.setattr(driver, 'execute', forbidden)
    config = SqlDatabaseConfig()
    pkg = config.source.db('inverses', implementation=request.param).packages().package('app')
    owner = pkg.table('owner', pkey='id')
    owner.column('id', dtype='L')
    owner.column('parent_id', dtype='L').relation('app.owner.id', inverse='children')
    owner.formulaColumn('child_count', select=dict(
        table='app.owner', columns='COUNT(*)', where='@children.parent_id=#THIS.id'))
    owner.formulaColumn('filtered_count', select=dict(
        table='app.owner', columns='COUNT(*)',
        where='@children.parent_id=#THIS.id AND @children.id>:minimum', sqlparams={'minimum': 5}))
    owner.aliasColumn('child_alias', '@children.id')
    line = pkg.table('line', pkey='id')
    line.column('id', dtype='L')
    line.column('owner_id', dtype='L').relation('app.owner.id', back_reference='lines')
    line.column('other_id', dtype='L').relation('app.owner.id', inverse='other_lines')
    line.column('amount', dtype='N')
    line.formulaColumn('scaled', '$amount * :factor', var_factor=3)
    with build_database(config) as database:
        yield database


def test_inverse_does_not_enable_joined_dml(db):
    query = db.table('app.owner').query(where='@children.id=:child', child=2)
    with pytest.raises(UnsupportedFeatureError, match='many relation'):
        query.sql_update({'parent_id': 1})
