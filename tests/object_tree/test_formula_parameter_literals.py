"""Issue #35 across formula scopes, runtime environment and actual SQLite SQL."""
import sqlite3

import pytest

from asqueel import AsqueelDb, SqlDatabaseConfig


@pytest.mark.parametrize('dialect', ['postgres', 'sqlite'])
def test_literal_formula_with_local_parameters_and_environment(dialect):
    config = SqlDatabaseConfig()
    pkg = config.source.db('literal_formulas', implementation=dialect).packages().package(
        'app', sqlschema='main', sqlprefix=True)
    table = pkg.table('document', pkey='id')
    table.column('id', dtype='L')
    table.formulaColumn('literal', "'prefix' || 'doc:xyz' || 'suffix'")
    table.formulaColumn('local', "'doc:xyz' || :xyz", var_xyz='bound')
    table.formulaColumn('env_literal', "':env_secret'")
    table.formulaColumn('actual_env', ':env_value')
    db = AsqueelDb(config)
    try:
        with db.tempEnv(secret='never bound', value='context'):
            query = db.table('app.document').query('$literal,$local,$env_literal,$actual_env').compiled
        assert query.sql.count("'doc:xyz'") == 2
        assert "':env_secret'" in query.sql
        assert set(query.params.values()) == {'bound', 'context'}
        assert query.environment_keys == ('value',)
        assert query.input_parameters == ()
        plain = db.table('app.document').query('$literal,$env_literal').compiled
        assert plain.params == {}
        assert plain.environment_keys == ()
        if dialect == 'sqlite':
            with sqlite3.connect(':memory:') as conn:
                conn.execute('CREATE TABLE app_document (id INTEGER)')
                conn.execute('INSERT INTO app_document VALUES (1)')
                assert conn.execute(query.sql, dict(query.params)).fetchone() == (
                    'prefixdoc:xyzsuffix', 'doc:xyzbound', ':env_secret', 'context')
    finally:
        db.closeConnection()
