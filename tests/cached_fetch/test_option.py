"""Option cachedFetch: schema _asql_ and table _asql_cached_fetch in the model, migrated on both backends."""
import json
from pathlib import Path

import pytest

from asqueel import SqlDatabaseConfig
from tests.option_tables_support import IMPLEMENTATIONS, migrated_db

FIXTURES = Path(__file__).parent / 'fixtures'
CATALOG_COLUMNS = {
    'id': 'A', 'owner': 'A', 'name': 'A', 'tablename': 'A', 'sqlschema': 'A', 'sqltable': 'A',
    'rowcount': 'L', 'created': 'DHZ', 'user': 'A', 'sort_sqltable': 'A', 'sort_order_by': 'T',
    'search_seed': 'T',
}


def declare(pkg):
    customer = pkg.table('customer', pkey='id')
    customer.options().sysFields()
    customer.column('name', indexed=True)
    invoice = pkg.table('invoice', pkey='id')
    invoice.column('id', dtype='L')
    invoice.column('customer_id', size='22').relation('app.customer.id', foreign_key=True)
    invoice.column('total', dtype='N', size='10,2')


def reference_model(implementation):
    """The model whose migration JSON the fixtures recorded before cachedFetch existed."""
    config = SqlDatabaseConfig()
    declare(config.source.db('reference', implementation=implementation).packages().package(
        'app', sqlschema='main' if implementation == 'sqlite' else 'app', sqlprefix=False))
    return config


@pytest.mark.parametrize('implementation', ['sqlite', 'postgres'])
def test_a_model_without_cached_fetch_renders_the_same_migration_json(implementation):
    expected = json.loads((FIXTURES / f'reference_migration_{implementation}.json').read_text())
    assert json.loads(json.dumps(reference_model(implementation).render('migration'))) == expected


@pytest.mark.parametrize('implementation', IMPLEMENTATIONS)
def test_cached_fetch_migrates_schema_asql_with_the_catalog_table(implementation, tmp_path):
    with migrated_db(implementation, tmp_path, declare, declare_db=lambda db: db.options().cachedFetch()) as db:
        model = db.table('_asql_._asql_cached_fetch').model
        assert (model.sqlschema, model.sqlname) == ('_asql_', '_asql_cached_fetch')
        assert {name: column.dtype for name, column in model.columns.items()} == CATALOG_COLUMNS
        assert model.pkey == 'id'
        assert model.columns['owner'].attributes['indexed'] is True
        columns = 'id, owner, name, tablename, sqlschema, sqltable, rowcount, created, "user", ' \
                  'sort_sqltable, sort_order_by, search_seed'
        assert db.execute(f'SELECT {columns} FROM _asql_._asql_cached_fetch').fetchall() == []


def test_cached_fetch_at_table_level_raises():
    config = SqlDatabaseConfig()
    table = config.source.db('m', implementation='sqlite').packages().package('app').table('t')
    with pytest.raises(ValueError, match='cachedFetch: option is not available at this level'):
        table.options().cachedFetch()
