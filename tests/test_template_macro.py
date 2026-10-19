"""#TEMPLATE composes text from named expressions in the dialect's SQL."""
import sqlite3

import psycopg
import pytest

from asqueel import SqlDatabaseConfig, build_database
from tests.native_support import postgres_dsn

LABEL = "#TEMPLATE('${n} - ${s} (${c})', $name AS n, $surname AS s, @city_id.name AS c)"


def source(backend):
    config = SqlDatabaseConfig()
    pkg = config.source.db('template_macro', implementation=backend).packages().package(
        'app', sqlschema='pg_temp' if backend == 'postgres' else 'main')
    city = pkg.table('city', pkey='id')
    city.column('id', dtype='L')
    city.column('name')
    person = pkg.table('person', pkey='id')
    person.column('id', dtype='L')
    person.column('name')
    person.column('surname')
    person.column('city_id', dtype='L').relation('app.city.id')
    person.formulaColumn('label', LABEL, dtype='T')
    return config


@pytest.fixture(scope='module', params=['sqlite', pytest.param('postgres', marks=pytest.mark.postgresql)])
def backend(request):
    return request.param


@pytest.fixture(scope='module')
def connection(backend):
    connection = (psycopg.connect(postgres_dsn()) if backend == 'postgres'
                  else sqlite3.connect(':memory:'))
    try:
        cursor = connection.cursor()
        kind = 'TEMP ' if backend == 'postgres' else ''
        cursor.execute(f'CREATE {kind}TABLE app_city (id BIGINT, name TEXT)')
        cursor.execute(f'CREATE {kind}TABLE app_person (id BIGINT, name TEXT, surname TEXT, city_id BIGINT)')
        cursor.execute("INSERT INTO app_city VALUES (1, 'Roma')")
        cursor.execute("INSERT INTO app_person VALUES (1, 'Ada', 'Lovelace', 1), (2, 'Bob', NULL, NULL)")
        yield connection
    finally:
        connection.rollback()
        connection.close()


@pytest.fixture(scope='module')
def model(backend):
    database = build_database(source(backend))
    try:
        yield database
    finally:
        database.closeConnection()


def rows(connection, query):
    compiled = query.compiled
    cursor = connection.cursor()
    cursor.execute(compiled.sql, dict(compiled.params))
    return cursor.fetchall()


def test_model_keeps_template_placeholders_literal(model):
    assert model.table('app.person').column('label').attributes['sql_formula'] == LABEL


def test_template_in_a_formula_column_reads_columns_and_relations(model, connection):
    query = model.table('app.person').query('$label', order_by='$id')
    assert rows(connection, query) == [('Ada - Lovelace (Roma)',), ('Bob -  ()',)]


def test_template_in_columns_where_and_order_by(model, connection):
    query = model.table('app.person').query(
        "#TEMPLATE('${i}: ${n}', $id AS i, $name AS n) AS tag",
        where="#TEMPLATE('${n}!', $name AS n) = :value", sqlparams={'value': 'Ada!'},
        order_by="#TEMPLATE('${s}', $surname AS s)")
    assert rows(connection, query) == [('1: Ada',)]


def test_literal_marker_and_quotes(model, connection):
    query = model.table('app.person').query(
        "#TEMPLATE('$$ it''s ${n}', $name AS n) AS tag", where='$id=1')
    assert rows(connection, query) == [("$ it's Ada",)]


@pytest.mark.parametrize('expression, message', [
    ("#TEMPLATE('${a}', $name AS b)", 'has no argument'),
    ("#TEMPLATE('${a}', $name AS a, $id AS b)", 'unused arguments'),
    ("#TEMPLATE('${a}', $name)", 'needs "AS <name>"'),
    ("#TEMPLATE('${a}', $name AS a, $id AS a)", 'duplicate name'),
    ("#TEMPLATE($name AS a)", 'quoted template'),
    ("#TEMPLATE('${a}', $name AS a", 'missing closing parenthesis'),
])
def test_template_errors(model, expression, message):
    with pytest.raises(ValueError, match=message):
        model.table('app.person').query(expression).compiled
