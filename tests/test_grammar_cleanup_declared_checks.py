"""Grammar cleanup, Phase 4: expressible checks live in the grammar; SqlModelValidator keeps the referential ones; connection_settings is runtime."""
import importlib
import json

import pytest

from asqueel import SqlBuilder, SqlDatabaseConfig
from asqueel.validators import SqlModelValidator

SQL_COLUMN_PARAMETERS = {
    'sql_pg_default', 'sql_pg_extra', 'sql_pg_generatedExpression',
    'sql_sqlite_default', 'sql_sqlite_extra', 'sql_sqlite_generatedExpression',
}


@pytest.fixture(scope='module')
def grammar(tmp_path_factory):
    path = tmp_path_factory.mktemp('grammar') / 'sqlmodel.json'
    SqlBuilder.to_grammar(path)
    return json.loads(path.read_text())['elements']


def parameter(grammar, element, name):
    found = [item for item in grammar[element]['attributes']['parameters'] if item['name'] == name]
    assert len(found) == 1, f'{element}.{name}'
    return found[0]


def descriptor_kinds(annotation):
    kinds = set()
    if isinstance(annotation, dict):
        kinds.add(annotation.get('kind'))
        for value in annotation.values():
            kinds |= descriptor_kinds(value)
    elif isinstance(annotation, list):
        for value in annotation:
            kinds |= descriptor_kinds(value)
    return kinds


@pytest.mark.parametrize('element, name', [
    ('retention', 'days'), ('hierarchical', 'depth'), ('package', 'sqlprefix'),
    ('driver', 'connect_timeout'), ('driver', 'timeout'), ('driver', 'cached_statements'),
])
def test_the_check_is_declared_in_the_grammar(grammar, element, name):
    kinds = descriptor_kinds(parameter(grammar, element, name)['annotation'])
    assert kinds & {'custom', 'range', 'regex'}, kinds


def test_the_dialect_column_attributes_are_explicit_parameters(grammar):
    names = {item['name'] for item in grammar['column']['attributes']['parameters']}
    assert SQL_COLUMN_PARAMETERS <= names
    assert grammar['column']['_meta']['attribute_families'] == ['validate_']


def table():
    config = SqlDatabaseConfig()
    root = config.source.db('checks', implementation='sqlite')
    root.connection('main', database=':memory:')
    return root.packages().package('app', sqlschema='main', sqlprefix=False).table('item', pkey='id')


def test_an_undeclared_dialect_attribute_is_outside_the_grammar():
    with pytest.raises(ValueError, match="Element 'column' does not accept 'sql_pg_foo'"):
        table().column('code', sql_pg_foo='x')


def test_a_declared_dialect_attribute_is_accepted():
    table().column('code', sql_pg_default="'x'")


@pytest.mark.parametrize('days', [-1, True])
def test_retention_days_is_checked_at_declaration(days):
    with pytest.raises(ValueError):
        table().options().retention(field='code', days=days)


@pytest.mark.parametrize('depth', [0, True])
def test_hierarchical_depth_is_checked_at_declaration(depth):
    with pytest.raises(ValueError):
        table().options().hierarchical('code', depth=depth)


def test_sqlprefix_is_checked_at_declaration():
    config = SqlDatabaseConfig()
    with pytest.raises(ValueError):
        config.source.db('checks').packages().package('app', sqlprefix='ab_')


def test_the_validator_keeps_no_attribute_check():
    assert not hasattr(SqlModelValidator, '_check_attributes')


def test_connection_settings_lives_in_the_runtime_layer():
    runtime = importlib.import_module('asqueel.runtime')
    configuration = importlib.import_module('asqueel.configuration')
    assert callable(runtime.connection_settings)
    assert not hasattr(configuration, 'connection_settings')
