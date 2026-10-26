from tests.unit_of_work import completed
from concurrent.futures import ThreadPoolExecutor

import pytest

from asqueel import (
    SqlDatabaseConfig, TransactionStateError,
    AsqueelDb,
)
from tests.application_connections.test_connections import FAKE, SqlDbAdapter
from tests.package_layout_support import write_layout


class Recipe(SqlDatabaseConfig):
    def main(self, root):
        table = root.db('demo', implementation=FAKE).packages().package('app', sqlschema='app', sqlprefix=False).tables().table('item', pkey='id')
        table.columns().column('id', dtype='I')


def layout_recipe(folder, item):
    """``Recipe`` with ``app.item`` declared by the package folder ``folder``."""
    recipe = SqlDatabaseConfig()
    root = recipe.source.db('demo', implementation=FAKE)
    root.packages().package('app', sqlschema='app', sqlprefix=False, path=write_layout(folder, item=item))
    return recipe


def test_database_owns_graph_environment_and_lazy_lifetime():
    db = AsqueelDb(Recipe).session()
    driver = db.adapter
    assert db.tables['app.item'] is db.table('app.item')
    with pytest.raises(TypeError):
        db.tables['app.item'] = None
    assert db.currentEnv == {}
    with db.tempEnv(company=0):
        assert db.currentEnv == {'company': 0}
    assert db.currentEnv == {}
    assert not hasattr(db, 'transaction')
    with completed(db):
        pass
    assert driver.calls == []
    db.table('app.item').query().fetch()
    db.closeConnection()
    assert driver.calls[-2:] == ['rollback', 'close']


def test_database_and_handles_can_be_used_by_another_thread():
    db = AsqueelDb(Recipe).session()
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


def test_invalid_implementation_fails_before_connection(monkeypatch):
    def connect(*args, **kwargs):
        pytest.fail('Construction must not connect')
    monkeypatch.setattr(SqlDbAdapter, 'connect', connect)
    recipe = Recipe()
    recipe.create()
    recipe.source.get_node('db').attr['implementation'] = 'unsupported'
    with pytest.raises(ModuleNotFoundError, match='asqueel.adapters.unsupported'):
        AsqueelDb(recipe)


def test_custom_constructor_cannot_execute_on_partially_published_graph(monkeypatch, tmp_path):
    recipe = layout_recipe(tmp_path / 'app', '''
        class Table:
            def config_db(self, pkg):
                pkg.tables().table('item', pkey='id').columns().column('id', dtype='I')

            def __init__(self, *tblobj):
                # The package loader builds Table() without arguments to run config_db.
                super().__init__(*tblobj)
                if tblobj:
                    self.query().compiled
    ''')
    def connect(*args, **kwargs):
        pytest.fail('Construction must not connect')
    monkeypatch.setattr(SqlDbAdapter, 'connect', connect)
    with pytest.raises(TransactionStateError, match='not ready'):
        AsqueelDb(recipe)


def test_rollback_only_session_rejects_write_before_calling_hooks(tmp_path):
    recipe = layout_recipe(tmp_path / 'app', '''
        class Table:
            calls = []

            def config_db(self, pkg):
                pkg.tables().table('item', pkey='id').columns().column('id', dtype='I')

            def trigger_onInserting(self, record):
                self.calls.append(record['id'])
                raise ValueError('domain validation failed')
    ''')
    db = AsqueelDb(recipe).session()
    calls = db.table('app.item').calls
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
