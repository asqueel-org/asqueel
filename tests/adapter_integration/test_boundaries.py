"""Verify the interfaces between planner, dialect, binding and structure."""
import ast
import asyncio
from pathlib import Path
import subprocess
import sys

import pytest

from genro_sql.compiler import PostgresCompiler
from genro_sql.contracts import Column, CompiledQuery, ResolvedModel, Table
from genro_sql.dialects.postgres import PostgresDialect
from genro_sql.drivers.psycopg import PsycopgDriver
from genro_sql.query_plan import Parameter, SqlStatement
from genro_sql.runtime import ThreadedDatabase


def test_offline_postgres_facade_and_generic_pipeline_without_optional_dependencies():
    script = '''
import builtins
original = builtins.__import__
def no_clients(name, *args, **kwargs):
    if name.startswith(('psycopg', 'genro_sqlmigration')):
        raise ModuleNotFoundError(name=name)
    return original(name, *args, **kwargs)
builtins.__import__ = no_clients
from genro_sql.compiler import PostgresCompiler, QueryCompiler
from genro_sql.contracts import Column, ResolvedModel, Table
from genro_sql.dialects.postgres import PostgresDialect
from genro_sql.drivers.psycopg import PsycopgDriver
from genro_sql.runtime import ThreadedDatabase
table = Table('sample', columns={'id': Column('id', 'L')})
model = ResolvedModel({table.key: table})
facade = PostgresCompiler(model).select('sample', where='$id = :id', params={'id': 7})
generic = QueryCompiler(model, PostgresDialect(), PsycopgDriver()).select(
    'sample', where='$id = :id', params={'id': 7})
assert facade == generic
assert dict(generic.params) == {'id': 7}
'''
    result = subprocess.run([sys.executable, '-c', script], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr


@pytest.mark.parametrize('name', ['order', 'a"b', '50%', 'ümlaut', 'with space'])
def test_data_and_structure_share_sql_quoting_but_not_driver_escaping(name):
    from genro_sqlmigration.writers.pg_writer import PgWriter

    dialect = PostgresDialect()
    quoted = dialect.quote_identifier(name)
    assert quoted == PgWriter.quote_identifier(name)
    prepared = PsycopgDriver().prepare(SqlStatement(('SELECT ', quoted)))
    assert prepared.sql == 'SELECT ' + quoted.replace('%', '%%')


def test_no_db_connection_for_binding_and_no_textual_replacement_of_fake_placeholders():
    statement = SqlStatement((
        "SELECT '%(trap)s :fake 50%' AS text, ", Parameter('actual'),
        ' /* %(trap)s */',
    ), {'actual': "Robert'); DROP TABLE sample; --", 'unused': 1})
    query = PsycopgDriver().prepare(statement)
    assert query.sql == "SELECT '%%(trap)s :fake 50%%' AS text, %(actual)s /* %%(trap)s */"
    assert dict(query.params) == {'actual': "Robert'); DROP TABLE sample; --"}


@pytest.mark.parametrize('field,value', [('dialect', 'other'), ('binding', 'qmark')])
def test_incompatible_statement_is_rejected_before_connection(field, value):
    class NoConnect(PsycopgDriver):
        def connect(self, *args, **kwargs):
            raise AssertionError('A mismatched statement must not open a connection')

    async def scenario():
        async with ThreadedDatabase(driver=NoConnect()) as db:
            query = CompiledQuery('SELECT 1', **{field: value})
            with pytest.raises(ValueError):
                await db.execute(query)
    asyncio.run(scenario())


def test_runtime_has_no_client_or_sql_compiler_dependency():
    import genro_sql.runtime as runtime

    tree = ast.parse(Path(runtime.__file__).read_text())
    imports = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            imports.append(node.module or '')
    assert not any(name == 'psycopg' or name.startswith('psycopg.') for name in imports)
    assert not any(name == 'compiler' or name.startswith('dialects') for name in imports)


def test_facade_keeps_existing_compiled_query_binding_contract():
    table = Table('sample', sql_name='50%', columns={'odd name': Column('odd name')})
    model = ResolvedModel({table.key: table})
    compiler = PostgresCompiler(model)
    query = compiler.select('sample', where='$"odd name" = :value', params={'value': '50%'})
    assert '"50%%"' in query.sql
    assert '%(value)s' in query.sql
    assert query.binding == 'psycopg_named'
    assert query.dialect == 'postgresql'
    assert query.params['value'] == '50%'
