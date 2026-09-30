"""Symbolic configuration, resolver semantics and terminal resource ownership."""
from pathlib import Path

import pytest
from genro_bag.resolvers import EnvResolver

from asqueel import SqlDatabaseConfig, build_database
from asqueel.cli import main
from asqueel.configuration import connection_settings
from asqueel.registry import DatabaseRegistry

EXAMPLE = Path(__file__).resolve().parents[2] / 'examples' / 'two_schemas'


def test_registry_loads_recipe_from_another_directory_without_secrets(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv('ASQUEEL_HOME', str(tmp_path / 'home'))
    monkeypatch.setenv('PGPASSWORD', 'do-not-store-this')
    monkeypatch.setenv('PGPORT', '5432')
    assert main(['register', 'demo', str(EXAMPLE)]) == 0
    monkeypatch.chdir(tmp_path)
    with build_database('demo') as db:
        assert len(db.model.tables) == 6
        assert connection_settings(db.config)[2]['password'] == 'do-not-store-this'
    assert main(['check', 'demo']) == 0
    assert main(['list']) == 0
    card = tmp_path / 'home/databases/demo.json'
    assert 'do-not-store-this' not in card.read_text()
    output = capsys.readouterr()
    assert 'do-not-store-this' not in output.out + output.err
    assert main(['register', 'demo', str(EXAMPLE)]) == 1
    assert main(['unregister', 'demo']) == 0
    assert not card.exists()
    assert (EXAMPLE / 'configure.py').is_file()
    assert main(['check', 'demo']) == 1


@pytest.mark.parametrize('name', ['../escape', '/absolute', '.', 'a/b', 'a\\b', ''])
def test_registry_rejects_non_symbolic_names(tmp_path, name):
    with pytest.raises(ValueError):
        DatabaseRegistry(tmp_path).register(name, EXAMPLE)
    assert not (tmp_path / 'databases').exists()


def test_connection_resolvers_and_override_layer_use_the_same_read_stack(monkeypatch):
    class Recipe(SqlDatabaseConfig):
        def main(self, root):
            root.db().connection(name=EnvResolver('ASQUEEL_TEST_NAME', default='fallback'),
                                 port=EnvResolver('ASQUEEL_TEST_PORT', dtype='L', default=5432),
                                 password=EnvResolver('ASQUEEL_TEST_PASSWORD'))

    class Overlay(SqlDatabaseConfig):
        def main(self, root):
            root.db().connection(name='deployment')

    monkeypatch.setenv('ASQUEEL_TEST_NAME', 'physical')
    monkeypatch.setenv('ASQUEEL_TEST_PORT', '55584')
    monkeypatch.setenv('ASQUEEL_TEST_PASSWORD', 'secret')
    with build_database(Recipe) as db:
        _, dsn, kwargs = connection_settings(db.config)
        assert dsn == ''
        assert kwargs == {'dbname': 'physical', 'port': 55584, 'password': 'secret'}
    with build_database(Overlay, parents=[Recipe]) as db:
        assert connection_settings(db.config)[2] == {
            'dbname': 'deployment', 'port': 55584, 'password': 'secret'}


def test_mixed_connection_forms_are_rejected():
    class Recipe(SqlDatabaseConfig):
        def main(self, root):
            root.db(conninfo='dbname=old').connection(name='new')
    with pytest.raises(ValueError, match='not both'):
        build_database(Recipe)


def test_check_is_offline_and_does_not_expose_invalid_secret(tmp_path, monkeypatch, capsys):
    import psycopg

    def forbidden(*args, **kwargs):
        raise AssertionError('Offline check must not connect')

    monkeypatch.setattr(psycopg, 'connect', forbidden)
    monkeypatch.setenv('PGPORT', '5432')
    assert main(['check', '--config', str(EXAMPLE)]) == 0
    bad = tmp_path / 'configure.py'
    bad.write_text('raise ValueError("secret-sentinel")\n')
    assert main(['check', str(bad)]) == 1
    output = capsys.readouterr()
    assert 'secret-sentinel' not in output.out + output.err


def test_shell_closes_database_on_system_exit(monkeypatch):
    observed = []
    monkeypatch.setenv('PGPORT', '5432')

    def interact(**kwargs):
        observed.append(kwargs['local']['db'])
        raise SystemExit(0)

    monkeypatch.setattr('asqueel.cli.code.interact', interact)
    with pytest.raises(SystemExit):
        main(['shell', str(EXAMPLE)])
    assert observed[0]._closed


def test_module_entry_point_uses_registration_from_any_working_directory(tmp_path, monkeypatch):
    import os
    import subprocess
    import sys

    monkeypatch.setenv('ASQUEEL_HOME', str(tmp_path / 'registry'))
    monkeypatch.setenv('PGPORT', '5432')
    DatabaseRegistry().register('sample', EXAMPLE)
    environment = dict(os.environ)
    environment['PYTHONPATH'] = str(EXAMPLE.parents[1] / 'src')
    result = subprocess.run(
        [sys.executable, '-m', 'asqueel', 'check', 'sample'], cwd=tmp_path,
        env=environment, capture_output=True, text=True,
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == 'Configuration valid: 6 tables.'


def test_missing_connection_name_and_invalid_resolved_type_are_rejected(monkeypatch):
    class Missing(SqlDatabaseConfig):
        def main(self, root):
            root.db().connection(name=EnvResolver('ASQUEEL_MISSING_DB_NAME'))

    monkeypatch.delenv('ASQUEEL_MISSING_DB_NAME', raising=False)
    with pytest.raises(ValueError, match='nonempty database name'):
        build_database(Missing)

    class Invalid(SqlDatabaseConfig):
        def main(self, root):
            root.db().connection(name='demo', port=EnvResolver('ASQUEEL_BAD_PORT'))

    monkeypatch.setenv('ASQUEEL_BAD_PORT', 'not-an-integer')
    with pytest.raises(ValueError, match='invalid type'):
        build_database(Invalid)


def test_asqueel_db_is_a_real_persistent_class_with_owned_handles(tmp_path, monkeypatch):
    import psycopg
    from asqueel import AsqueelDb, SqlDatabase

    def forbidden(*args, **kwargs):
        raise AssertionError('Constructing AsqueelDb must not connect')

    monkeypatch.setattr(psycopg, 'connect', forbidden)
    monkeypatch.setenv('ASQUEEL_HOME', str(tmp_path))
    monkeypatch.setenv('PGPORT', '5432')
    DatabaseRegistry().register('shop', EXAMPLE)
    db = AsqueelDb('shop')
    try:
        assert type(db) is AsqueelDb
        assert isinstance(db, SqlDatabase)
        assert db.table('sales.invoice').db is db
        assert db.table('sales.invoice').rows_query(7).compiled.params == {'invoice_id': 7}
        assert not db._sessions
    finally:
        db.close()
    assert db._closed


def test_asqueel_db_supports_subclassing_and_compatibility_factory(monkeypatch):
    from asqueel import AsqueelDb

    class ApplicationDb(AsqueelDb):
        def customers(self):
            return self.table('sales.customer')

    monkeypatch.setenv('PGPORT', '5432')
    db = ApplicationDb(EXAMPLE)
    legacy = build_database(EXAMPLE)
    try:
        assert db.customers().db is db
        assert isinstance(legacy, AsqueelDb)
        assert db.table('sales.customer') is not legacy.table('sales.customer')
        assert legacy.table('sales.customer').db is legacy
    finally:
        db.close()
        legacy.close()
