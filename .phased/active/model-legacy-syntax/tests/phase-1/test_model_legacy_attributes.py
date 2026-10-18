"""Table and column attributes in their legacy spelling (Macro 4, Phase 1)."""
import sqlite3
from datetime import datetime

import pytest

from asqueel import AsqueelDb, SqlDatabaseConfig
from asqueel.contracts import UnsupportedFeatureError
from tests.option_tables_support import IMPLEMENTATIONS, migrated_db


def package():
    config = SqlDatabaseConfig()
    root = config.source.db('legacy', implementation='sqlite')
    root.connection('main', database=':memory:')
    pkg = root.packages().package('app', sqlschema='main', sqlprefix=False)
    return config, pkg


def test_row_policy_fields_are_table_arguments_and_properties():
    config, pkg = package()
    table = pkg.table('note', pkey='id', lastTS='__mod_ts', logicalDeletionField='__del_ts',
                      draftField='__is_draft')
    table.column('id', dtype='L')
    table.column('__mod_ts', dtype='DH')
    table.column('__del_ts', dtype='DH')
    table.column('__is_draft', dtype='B')
    db = AsqueelDb(config)
    model = db.model.table('app.note')
    assert model.lastTS == '__mod_ts'
    assert model.logicalDeletionField == '__del_ts'
    assert model.draftField == '__is_draft'
    assert db.table('app.note').logicalDeletionField == '__del_ts'
    assert db.table('app.note').draftField == '__is_draft'


@pytest.mark.parametrize('key', ['x_draft_field', 'x_logical_deletion_field', 'x_partition', 'x_partitions',
                                 'x_sql_name', 'x_sql_schema'])
def test_internal_spellings_are_outside_the_grammar(key):
    _, pkg = package()
    with pytest.raises(ValueError, match=f"Element 'table' does not accept '{key}'"):
        pkg.table('note', pkey='id', **{key: 'value'})


def test_logical_deletion_declared_on_the_table_filters_the_query(tmp_path):
    def declare(pkg):
        table = pkg.table('note', pkey='id', logicalDeletionField='__del_ts')
        table.column('id', dtype='serial')
        table.column('title')
        table.column('__del_ts', dtype='DH')

    with migrated_db('sqlite', tmp_path, declare) as db:
        db.table('app.note').sql_insert([{'title': 'kept'}, {'title': 'gone', '__del_ts': datetime(2026, 1, 1)}])
        titles = [r['title'] for r in db.table('app.note').query(columns='$title').fetch()]
        assert titles == ['kept']


def partitioned(pkg):
    table = pkg.table('doc', pkey='id', partition_tenant='tenant')
    table.column('id', dtype='serial')
    table.column('tenant', dtype='A', size='0:10')
    table.column('title')


@pytest.mark.parametrize('implementation', IMPLEMENTATIONS)
def test_partition_field_filters_as_legacy(implementation, tmp_path):
    with migrated_db(implementation, tmp_path, partitioned) as db:
        doc = db.table('app.doc')
        doc.sql_insert([{'tenant': 'a', 'title': 'a1'}, {'tenant': 'b', 'title': 'b1'},
                        {'tenant': None, 'title': 'n1'}])
        db.commit()

        def titles():
            return sorted(r['title'] for r in doc.query(columns='$title').fetch())

        assert titles() == ['a1', 'b1', 'n1']
        db.updateEnv(current_tenant='a')
        assert titles() == ['a1']
        db.updateEnv(current_tenant=None, allowed_tenant=['b'])
        assert titles() == ['b1', 'n1']


def test_native_partition_option_is_gone():
    _, pkg = package()
    table = pkg.table('doc', pkey='id')
    with pytest.raises(AttributeError, match="'partition'"):
        table.options().partition('tenant', field='tenant', value='env.tenant')


def index_names(path):
    with sqlite3.connect(path) as conn:
        return {r[1]: r[2] for r in conn.execute("PRAGMA index_list('customer')")}


@pytest.mark.parametrize('value', ['y', 'Y', 'true', 'T'])
def test_indexed_and_unique_accept_legacy_true_strings(value, tmp_path):
    def declare(pkg):
        table = pkg.table('customer', pkey='id')
        table.column('id', dtype='serial')
        table.column('code', dtype='A', size='0:10', unique=value)
        table.column('name', indexed=value)

    with migrated_db('sqlite', tmp_path, declare):
        indexes = index_names(tmp_path / 'options.sqlite')
    assert any(unique for unique in indexes.values())
    assert len(indexes) >= 2


def test_ui_metadata_attributes_are_accepted():
    config, pkg = package()
    table = pkg.table('customer', pkey='id')
    table.column('id', dtype='L')
    table.column('amount', dtype='N', format='#,###.00', print_width=12)
    column = AsqueelDb(config).model.table('app.customer').column('amount')
    assert column.attributes['format'] == '#,###.00'
    assert column.print_width == 12


def test_encrypted_names_the_missing_feature():
    config, pkg = package()
    table = pkg.table('customer', pkey='id')
    table.column('id', dtype='L')
    with pytest.raises(UnsupportedFeatureError, match='encrypted is not available in this release'):
        table.column('secret', encrypted=True)
        AsqueelDb(config)


def test_names_fall_back_as_legacy():
    config, pkg = package()
    table = pkg.table('customer', pkey='id', name_short='Cust')
    table.column('id', dtype='L', name_short='Id')
    table.column('code', name_long='Code', name_full='Customer code')
    model = AsqueelDb(config).model.table('app.customer')
    assert model.name_long == 'Cust'
    assert model.name_full == 'Cust'
    assert model.name_plural == 'Cust'
    assert model.column('id').name_long == 'Id'
    assert model.column('code').name_short == 'Code'
    assert model.column('code').name_full == 'Customer code'


def test_pkeys_is_the_list_of_key_columns():
    config, pkg = package()
    table = pkg.table('customer', pkey='id')
    table.column('id', dtype='L')
    assert AsqueelDb(config).model.table('app.customer').pkeys == ['id']


def test_unknown_names_return_none_as_legacy():
    config, pkg = package()
    pkg.table('customer', pkey='id').column('id', dtype='L')
    model = AsqueelDb(config).model
    assert model.table('nopkg.customer') is None
    assert model.table('app.customer').column('nope') is None
    with pytest.raises(ValueError, match='app.nope'):
        model.table('app.nope')


@pytest.mark.parametrize('key', ['sqldefault', 'extra_sql', 'generated_expression'])
def test_old_sql_attribute_names_are_outside_the_grammar(key):
    _, pkg = package()
    table = pkg.table('customer', pkey='id')
    with pytest.raises(ValueError, match=f"Element 'column' does not accept '{key}'"):
        table.column('amount', dtype='L', **{key: '0'})


@pytest.mark.parametrize('implementation', IMPLEMENTATIONS)
def test_sql_attributes_and_their_dialect_versions(implementation, tmp_path):
    def declare(pkg):
        table = pkg.table('item', pkey='id')
        table.column('id', dtype='serial')
        table.column('qty', dtype='L', sql_default='1', sql_pg_default='2')
        table.column('double', dtype='L', sql_generatedExpression='qty * 2')
        table.column('note', sql_extra="CHECK (note <> 'x')")

    with migrated_db(implementation, tmp_path, declare) as db:
        item = db.table('app.item')
        item.sql_insert({'note': 'a'})
        stored = dict(item.query(columns='$qty,$double').fetch()[0])
    expected = 2 if implementation == 'postgres' else 1
    assert stored == {'qty': expected, 'double': expected * 2}
