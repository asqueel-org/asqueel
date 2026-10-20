from tests.unit_of_work import completed
from concurrent.futures import ThreadPoolExecutor

import pytest

from asqueel import (
    SqlDatabaseConfig, SqlTable, TransactionStateError,
    UnsupportedFeatureError, build_database,
)
from tests.application_connections.test_connections import FAKE, SqlDbAdapter


class Recipe(SqlDatabaseConfig):
    def main(self, root):
        table = root.db('demo', implementation=FAKE).schemas().schema('app').tables().table('item', pkey='id')
        table.columns().column('id', dtype='I')


def test_database_owns_graph_environment_and_lazy_lifetime():
    db = build_database(Recipe)
    driver = db.adapter
    assert db.tables['app.item'] is db.table('app.item')
    with pytest.raises(TypeError):
        db.tables['app.item'] = None
    assert db.current_env == db.currentEnv == {}
    with db.tempEnv(company=0):
        assert db.current_env == {'company': 0}
    assert db.current_env == {}
    assert not hasattr(db, 'transaction')
    with completed(db):
        pass
    assert driver.calls == []
    db.table('app.item').query().fetch()
    db.closeConnection()
    assert driver.calls[-2:] == ['rollback', 'close']


def test_database_and_handles_can_be_used_by_another_thread():
    db = build_database(Recipe)
    driver = db.adapter
    table = db.table('app.item')
    query = table.query()

    def worker():
        assert db.table('app.item') is table
        query.fetch()
        db.closeConnection()

    with ThreadPoolExecutor(max_workers=1) as pool:
        pool.submit(worker).result()
    assert driver.calls[-2:] == ['rollback', 'close']
    table.query().fetch()
    db.closeConnection()
    assert driver.calls.count('connect') == 2


def test_invalid_implementation_and_table_class_fail_before_connection(monkeypatch):
    def connect(*args, **kwargs):
        pytest.fail('Construction must not connect')
    monkeypatch.setattr(SqlDbAdapter, 'connect', connect)
    recipe = Recipe()
    recipe.create()
    recipe.source.get_node('db').attr['implementation'] = 'unsupported'
    with pytest.raises(ModuleNotFoundError, match='asqueel.adapters.unsupported'):
        build_database(recipe)
    recipe.source.get_node('db').attr['implementation'] = FAKE
    recipe.source.get_node('db.schemas.app.tables.item').attr['x_table_class'] = str
    with pytest.raises(TypeError, match='SqlTable subclass'):
        build_database(recipe)


def test_custom_constructor_cannot_execute_on_partially_published_graph(monkeypatch):
    class Premature(SqlTable):
        def __init__(self, db, model):
            super().__init__(db, model)
            self.query().compiled

    recipe = Recipe()
    recipe.create()
    recipe.source.get_node('db.schemas.app.tables.item').attr['x_table_class'] = Premature
    def connect(*args, **kwargs):
        pytest.fail('Construction must not connect')
    monkeypatch.setattr(SqlDbAdapter, 'connect', connect)
    with pytest.raises(UnsupportedFeatureError, match='not bound'):
        build_database(recipe)


def test_rollback_only_session_rejects_write_before_calling_hooks():
    calls = []

    class Failing(SqlTable):
        def trigger_onInserting(self, record):
            calls.append(record['id'])
            raise ValueError('domain validation failed')

    recipe = Recipe()
    recipe.create()
    recipe.source.get_node('db.schemas.app.tables.item').attr['x_table_class'] = Failing
    db = build_database(recipe)
    driver = db.adapter
    with pytest.raises(ValueError, match='domain validation'):
        db.table('app.item').insert({'id': 1})
    with pytest.raises(TransactionStateError, match='rollback-only'):
        db.table('app.item').insert({'id': 2})
    assert calls == [1]
    assert driver.calls == []
    db.rollback()
    with pytest.raises(ValueError, match='domain validation'):
        db.table('app.item').insert({'id': 3})
    assert calls == [1, 3]
    db.closeConnection()
