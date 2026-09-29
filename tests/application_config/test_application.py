from concurrent.futures import ThreadPoolExecutor

import pytest

from genro_sql import (
    DatabaseClosedError, SqlDatabaseConfig, SqlTable, TransactionStateError,
    UnsupportedFeatureError, build_database,
)
from tests.application_session.test_session import Driver


class Recipe(SqlDatabaseConfig):
    def main(self, root):
        table = root.db('demo').schemas().schema('app').tables().table('item', pkey='id')
        table.columns().column('id', dtype='I')


def test_database_owns_graph_environment_and_lazy_lifetime():
    driver = Driver()
    db = build_database(Recipe, driver=driver)
    assert db.tables['app.item'] is db.table('item')
    with pytest.raises(TypeError):
        db.tables['app.item'] = None
    assert db.current_env == db.currentEnv == {}
    with db.tempEnv(company=0):
        assert db.current_env == {'company': 0}
    assert db.current_env == {}
    assert db.outcome == 'not_started'
    with db.transaction():
        pass
    assert driver.calls == []
    with db:
        db.table('item').query().fetch()
    assert driver.calls[-2:] == ['rollback', 'close']
    assert db.outcome == 'rolled_back'
    db.close()
    with pytest.raises(DatabaseClosedError):
        db.table('item')


def test_database_and_handles_reject_cross_thread_operations_before_io():
    driver = Driver()
    db = build_database(Recipe, driver=driver)
    table = db.table('item')
    query = table.query()
    with ThreadPoolExecutor(max_workers=1) as pool:
        for call in (lambda: db.table('item'), table.query, query.fetch, db.close):
            with pytest.raises(TransactionStateError, match='constructing thread'):
                pool.submit(call).result()
    assert driver.calls == []
    db.close()


def test_invalid_implementation_and_table_class_fail_before_connection():
    driver = Driver()
    recipe = Recipe()
    recipe.create()
    recipe.source.get_node('db').attr['implementation'] = 'unsupported'
    with pytest.raises(UnsupportedFeatureError):
        build_database(recipe, driver=driver)
    recipe.source.get_node('db').attr['implementation'] = 'postgresql'
    recipe.source.get_node('db.schemas.app.tables.item').attr['x_table_class'] = str
    with pytest.raises(TypeError, match='SqlTable subclass'):
        build_database(recipe, driver=driver)
    assert driver.calls == []


def test_custom_constructor_cannot_execute_on_partially_published_graph():
    class Premature(SqlTable):
        def __init__(self, db, model):
            super().__init__(db, model)
            db.table('item')

    recipe = Recipe()
    recipe.create()
    recipe.source.get_node('db.schemas.app.tables.item').attr['x_table_class'] = Premature
    driver = Driver()
    with pytest.raises(TransactionStateError, match='not ready'):
        build_database(recipe, driver=driver)
    assert driver.calls == []


def test_rollback_only_session_rejects_write_before_calling_hooks():
    calls = []

    class Failing(SqlTable):
        def trigger_onInserting(self, record):
            calls.append(record['id'])
            raise ValueError('domain validation failed')

    recipe = Recipe()
    recipe.create()
    recipe.source.get_node('db.schemas.app.tables.item').attr['x_table_class'] = Failing
    driver = Driver()
    db = build_database(recipe, driver=driver)
    with pytest.raises(ValueError, match='domain validation'):
        db.table('item').insert({'id': 1})
    with pytest.raises(TransactionStateError, match='rollback-only'):
        db.table('item').insert({'id': 2})
    assert calls == [1]
    assert driver.calls == []
    db.rollback()
    with pytest.raises(ValueError, match='domain validation'):
        db.table('item').insert({'id': 3})
    assert calls == [1, 3]
    db.close()
