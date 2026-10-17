"""db.adapter: one adapter object per implementation, loaded as legacy."""
import pytest

from asqueel import SqlDatabaseConfig, build_database
from asqueel.adapters.postgres import SqlDbAdapter as PostgresAdapter
from asqueel.adapters.sqlite import SqlDbAdapter as SqliteAdapter
from asqueel.runtime import Database


@pytest.mark.parametrize(('implementation', 'adapter_class'), [
    ('sqlite', SqliteAdapter), ('postgres', PostgresAdapter), ('postgres3', PostgresAdapter)])
def test_one_adapter_per_implementation(implementation, adapter_class):
    db = Database(implementation=implementation)
    try:
        assert db.implementation == implementation
        assert type(db.adapter) is adapter_class
        assert db.adapter.dbroot is db
        assert db.adapter is db.adapter
    finally:
        db.close()


def test_default_implementation_is_sqlite():
    db = Database()
    assert db.implementation == 'sqlite'
    assert type(db.adapter) is SqliteAdapter
    db.close()
    config = SqlDatabaseConfig()
    config.source.db('demo').packages().package('app').table('item', pkey='id').column('id', dtype='L')
    with build_database(config) as database:
        assert database.config('implementation') == 'sqlite'
        assert type(database.adapter) is SqliteAdapter


def test_postgresql_is_not_an_implementation():
    with pytest.raises(ModuleNotFoundError, match='asqueel.adapters.postgresql'):
        Database(implementation='postgresql')


def test_external_module_supplies_the_adapter():
    db = Database(implementation='postgres:tests.application_connections.test_connections')
    try:
        assert db.implementation == 'postgres'
        assert type(db.adapter).__module__ == 'tests.application_connections.test_connections'
        assert isinstance(db.adapter, PostgresAdapter)
    finally:
        db.close()


def test_current_implementation_selects_the_adapter_on_demand():
    db = Database(implementation='sqlite')
    try:
        main = db.adapter
        assert list(db.adapters) == ['sqlite']
        with db.tempEnv(currentImplementation='postgres'):
            assert type(db.adapter) is PostgresAdapter
            assert db.adapter is db.adapters['postgres']
        assert db.adapter is main
        with db.tempEnv(currentImplementation='postgres'):
            assert db.adapter is db.adapters['postgres']
    finally:
        db.close()
