"""Named connection recipes keep physical settings separate from model identity."""
import pytest
from genro_bag.resolvers import EnvResolver
from genro_builders.contrib.config import ConfigHandler

from asqueel import SqlDatabaseConfig
from asqueel.configuration import connection_settings, configuration_source, _owned_handler


def recipe(implementation='postgres'):
    builder = SqlDatabaseConfig()
    return builder, builder.source.db('invoice', implementation=implementation)


def test_named_connections_select_their_own_settings_and_driver_options():
    builder, db = recipe()
    db.connection('main', database='invoice', host='primary').options().driver(connect_timeout=3)
    db.connection('reporting', database='invoice_replica', host='replica').options().driver(
        application_name='reports')
    config = ConfigHandler(builder)
    assert connection_settings(config) == ('postgres', '', {
        'dbname': 'invoice', 'host': 'primary', 'connect_timeout': 3})
    assert connection_settings(config, 'reporting') == ('postgres', '', {
        'dbname': 'invoice_replica', 'host': 'replica', 'application_name': 'reports'})


def test_dsn_is_passed_separately_from_driver_parameters():
    builder, db = recipe()
    db.connection('main', dsn='dbname=invoice service=local').options().driver(connect_timeout=2)
    assert connection_settings(ConfigHandler(builder)) == (
        'postgres', 'dbname=invoice service=local', {'connect_timeout': 2})
    with pytest.raises(ValueError, match='cannot be combined'):
        db.connection('bad', dsn='dbname=invoice', host='localhost')


def test_sqlite_has_its_own_closed_driver_options():
    builder, db = recipe('sqlite')
    connection = db.connection('main', database=':memory:')
    connection.options().driver(timeout=2.5, cached_statements=64)
    assert connection_settings(ConfigHandler(builder)) == (
        'sqlite', '', {'dbname': ':memory:', 'timeout': 2.5, 'cached_statements': 64})
    with pytest.raises(ValueError, match='unsupported sqlite'):
        connection.options().driver(connect_timeout=3)


@pytest.mark.parametrize('kwargs', [{'connect_timeout': -1}, {'connect_timeout': True},
                                    {'application_nam': 'x'}, {'timeout': 1.2}])
def test_invalid_driver_options_are_rejected(kwargs):
    _, db = recipe()
    with pytest.raises(ValueError):
        db.connection('main', database='invoice').options().driver(**kwargs)


def test_named_connection_cannot_change_database_dialect():
    builder, db = recipe()
    db.connection('main', database=':memory:', implementation='sqlite')
    with pytest.raises(ValueError, match='database dialect'):
        connection_settings(ConfigHandler(builder))


def test_secret_resolvers_are_not_read_while_building_or_replaying(monkeypatch):
    calls = []
    original = EnvResolver.load

    def load(self):
        calls.append(True)
        return original(self)

    monkeypatch.setattr(EnvResolver, 'load', load)
    monkeypatch.setenv('ASQUEEL_RECIPE_TEST_PASSWORD', 'example-secret')
    builder, db = recipe()
    db.connection('main', database='invoice', password=EnvResolver('ASQUEEL_RECIPE_TEST_PASSWORD'))
    config = ConfigHandler(configuration_source(db))
    assert not calls
    assert isinstance(config.builder.source['db.connection'].get_attr('password'), EnvResolver)
    assert connection_settings(config)[2]['password'] == 'example-secret'
    assert calls


def test_missing_database_resolver_never_falls_back_to_logical_name(monkeypatch):
    monkeypatch.delenv('ASQUEEL_RECIPE_TEST_DATABASE', raising=False)
    builder, db = recipe()
    db.connection('main', database=EnvResolver('ASQUEEL_RECIPE_TEST_DATABASE'))
    with pytest.raises(ValueError, match='nonempty database name'):
        connection_settings(ConfigHandler(builder))


def test_old_and_new_driver_options_are_not_implicitly_merged():
    _, db = recipe()
    connection = db.connection(name='invoice', options={'connect_timeout': 2})
    with pytest.raises(ValueError, match='not both'):
        connection.options().driver(application_name='invoice')


def test_named_connection_contributions_keep_omitted_settings():
    builder, db = recipe()
    reports = db.connection('reporting', database='invoice_replica', host='first')
    assert db.connection('reporting') is reports
    with builder.contribution('deployment'):
        assert db.connection('reporting', host='second') is reports
    assert connection_settings(ConfigHandler(builder), 'reporting')[2] == {
        'dbname': 'invoice_replica', 'host': 'second'}


def test_named_connection_overlay_is_addressed_by_logical_name():
    base, db = recipe()
    db.connection('main', database='invoice')
    db.connection('reporting', database='invoice_replica', host='first')
    overlay, db = recipe()
    db.connection('reporting', host='second')
    config = _owned_handler(overlay, [base])
    assert connection_settings(config)[2] == {'dbname': 'invoice'}
    assert connection_settings(config, 'reporting')[2] == {
        'dbname': 'invoice_replica', 'host': 'second'}
    with pytest.raises(ValueError, match='Unknown named connection'):
        connection_settings(config, 'typo')


def test_missing_main_connection_does_not_select_an_implicit_database():
    builder, db = recipe()
    db.connection('reporting', database='replica')
    with pytest.raises(ValueError, match='explicit main connection'):
        connection_settings(ConfigHandler(builder))


def test_legacy_options_normalize_to_driver_on_an_owned_source():
    builder, db = recipe()
    original = db.connection(name='invoice', options={'connect_timeout': 2})
    config = _owned_handler(builder)
    connection = config.builder.source['db.connection']
    assert 'options' not in connection.attr
    assert config('connection.options.driver.connect_timeout') == 2
    assert original.get_attr('options') == {'connect_timeout': 2}
    assert connection_settings(config)[2] == {'dbname': 'invoice', 'connect_timeout': 2}


def test_driver_options_do_not_prevent_building_the_existing_runtime_profile():
    from asqueel import build_database
    builder, db = recipe('sqlite')
    db.connection('main', database=':memory:').options().driver(timeout=1.5)
    db.schemas().schema('public').tables().table('t', pkey='id').column('id', dtype='L')
    database = build_database(builder)
    try:
        assert not database._connections
        assert database._connection_settings()[1]['timeout'] == 1.5
    finally:
        database.closeConnection()


def test_named_runtime_connections_reach_distinct_sqlite_databases(tmp_path):
    import sqlite3
    from asqueel import build_database

    builder, db = recipe('sqlite')
    for name in ('main', 'reporting'):
        path = tmp_path / f'{name}.db'
        connection = sqlite3.connect(path)
        connection.execute('CREATE TABLE marker(value TEXT)')
        connection.execute('INSERT INTO marker VALUES (?)', (name,))
        connection.commit()
        connection.close()
        db.connection(name, database=str(path)).options().driver(timeout=1)
    database = build_database(builder)
    try:
        assert [dict(row) for row in database.execute('SELECT value FROM marker').rows] == [{'value': 'main'}]
        database.commit()
        with database.tempEnv(connectionName='reporting'):
            assert [dict(row) for row in database.execute('SELECT value FROM marker').rows] == [{'value': 'reporting'}]
            database.commit()
        assert [dict(row) for row in database.execute('SELECT value FROM marker').rows] == [{'value': 'main'}]
    finally:
        database.closeConnection()
