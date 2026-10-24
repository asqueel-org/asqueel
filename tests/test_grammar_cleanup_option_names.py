"""Grammar cleanup, Phase 1: table options carry the legacy sysFields names; md5, audit, useProtectionTag and attachments are out."""
import pytest

from asqueel import AsqueelDb, SqlDatabaseConfig
from tests.option_tables_support import IMPLEMENTATIONS, migrated_db

RENAMED = {
    'sys_fields': 'sysFields', 'auto_counter': 'counter', 'relative_index': 'relidx',
    'dynamic_fields': 'df', 'full_update': 'fullUpd', 'system_records': 'sysrecords',
}
REMOVED = ['md5', 'audit', 'useProtectionTag', 'attachments',
           'record_hash', 'protection']


def table():
    config = SqlDatabaseConfig()
    root = config.source.db('names', implementation='sqlite')
    root.connection('main', database=':memory:')
    pkg = root.packages().package('app', sqlschema='main', sqlprefix=False)
    return config, pkg.table('item', pkey='id')


@pytest.mark.parametrize('old', sorted(RENAMED))
def test_the_old_option_name_is_outside_the_grammar(old):
    _, item = table()
    with pytest.raises(AttributeError, match=f"'{old}'"):
        getattr(item.options(), old)()


@pytest.mark.parametrize('name', REMOVED)
def test_the_removed_option_is_outside_the_grammar(name):
    _, item = table()
    with pytest.raises(AttributeError, match=f"'{name}'"):
        getattr(item.options(), name)()


def test_the_legacy_names_are_the_option_keys_of_the_live_table():
    config, item = table()
    options = item.options()
    options.sysFields()
    options.counter()
    options.fullUpd()
    options.df()
    item.column('code')
    live = AsqueelDb(config).model.table('app.item')
    assert set(live.options) == {'sysFields', 'counter', 'fullUpd', 'df'}


def test_sysfields_expands_the_same_system_columns():
    config, item = table()
    item.options().sysFields()
    item.column('code')
    live = AsqueelDb(config).model.table('app.item')
    assert sorted(live.columns) == ['__del_ts', '__ins_ts', '__ins_user', '__mod_ts', '__mod_user', 'code', 'id']


def test_sysrecords_is_declared_with_its_legacy_name():
    _, item = table()
    item.options().sysrecords(records={'ADMIN': {'code': 'admin'}})


def test_df_is_also_the_column_declaration():
    config, item = table()
    item.column('id', dtype='L')
    item.column('extra', dtype='X').df(source='app.template')
    AsqueelDb(config).model


def ranked(package):
    item = package.table('item', name_long='Item')
    item.options().sysFields()
    item.options().counter(scope='scope')
    item.column('scope')


@pytest.mark.parametrize('implementation', IMPLEMENTATIONS)
def test_counter_still_executes_on_write(implementation, tmp_path):
    with migrated_db(implementation, tmp_path, ranked) as db:
        item = db.table('app.item')
        item.insert({'scope': 'a'})
        assert item.insert({'scope': 'a'})['_row_count'] == 2
