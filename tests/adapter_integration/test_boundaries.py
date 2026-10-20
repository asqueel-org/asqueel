"""Verify the interfaces between planner, adapter, binding and structure."""
import ast
from pathlib import Path
import subprocess
import sys

import pytest

from asqueel.compiler import PostgresCompiler
from asqueel.contracts import CompiledQuery
from asqueel.adapters.postgres import SqlDbAdapter as PostgresAdapter
from asqueel.runtime import Database


def test_offline_postgres_facade_and_generic_pipeline_without_optional_dependencies():
    script = '''
import builtins
original = builtins.__import__
def no_clients(name, *args, **kwargs):
    if name.startswith(('psycopg', 'asqueel_migration')):
        raise ModuleNotFoundError(name=name)
    return original(name, *args, **kwargs)
builtins.__import__ = no_clients
from asqueel.compiler import PostgresCompiler, QueryCompiler
from asqueel import SqlDatabaseConfig, resolve_model
from asqueel.adapters.postgres import SqlDbAdapter as PostgresAdapter
source = SqlDatabaseConfig()
source.source.db('demo').packages().package('app').table('sample', pkey='id').column('id', dtype='L')
model = resolve_model(source)
facade = PostgresCompiler(model).select('app.sample', where='$id = :id', sqlparams={'id': 7})
generic = QueryCompiler(model, PostgresAdapter(None)).select(
    'app.sample', where='$id = :id', sqlparams={'id': 7})
assert facade == generic
assert dict(generic.params) == {'id': 7}
'''
    result = subprocess.run([sys.executable, '-c', script], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr


@pytest.mark.parametrize('name', ['order', 'a"b', '50%', 'ümlaut', 'with space'])
def test_data_and_structure_share_sql_quoting_but_not_driver_escaping(name):
    from asqueel_migration.writers.pg_writer import PgWriter

    quoted = PostgresAdapter(None).adaptSqlName(name)
    assert quoted == PgWriter.quote_identifier(name)
    prepared = PostgresAdapter(None).prepare_sql('SELECT ' + quoted, {}, {})
    assert prepared.sql == 'SELECT ' + quoted


def test_no_db_connection_for_binding():
    value = "Robert'); DROP TABLE sample; --"
    query = PostgresAdapter(None).prepare_sql('SELECT :actual AS value', {'actual': value}, {})
    assert query.sql == 'SELECT %(actual)s AS value'
    assert dict(query.params) == {'actual': value}


@pytest.mark.parametrize('field,value', [('dialect', 'other'), ('binding', 'qmark')])
def test_incompatible_statement_is_rejected_before_connection(field, value, monkeypatch):
    def connect(*args, **kwargs):
        raise AssertionError('A mismatched statement must not open a connection')
    monkeypatch.setattr(PostgresAdapter, 'connect', connect)

    def scenario():
        db = Database(implementation='postgres')
        try:
            query = CompiledQuery('SELECT 1', **{field: value})
            with pytest.raises(ValueError):
                db.execute(query)
        finally:
            db.closeConnection()
    scenario()


def test_runtime_has_no_client_or_sql_compiler_dependency():
    import asqueel.runtime as runtime

    tree = ast.parse(Path(runtime.__file__).read_text())
    imports = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            imports.append(node.module or '')
    assert not any(name == 'psycopg' or name.startswith('psycopg.') for name in imports)
    assert not any(name == 'compiler' or name.startswith('adapters') for name in imports)


def test_facade_keeps_existing_compiled_query_binding_contract():
    from asqueel import SqlDatabaseConfig, resolve_model
    source = SqlDatabaseConfig()
    table = source.source.db('demo').packages().package('app').table('sample', sqlname='50%')
    table.column('name')
    query = PostgresCompiler(resolve_model(source)).select(
        'app.sample', '$name', where='$name = :value', sqlparams={'value': '50%'})
    assert '"50%"' in query.sql
    assert '%(value)s' in query.sql
    assert query.binding == 'psycopg_named'
    assert query.dialect == 'postgres'
    assert query.params['value'] == '50%'
