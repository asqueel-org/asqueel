"""Model cleanup, Phase 3: one database class, built before its model, as GnrSqlDb then DbModel(db).build()."""
import importlib
import inspect

import pytest

import asqueel
from asqueel import AsqueelDb, SqlDatabaseConfig, SqlTable
from asqueel.object_tree import DbModel

REMOVED = {'asqueel': ('Database', 'SqlDatabase', 'SqlEnvironment', 'ApplicationEnvironment'),
           'asqueel.runtime': ('Database',),
           'asqueel.application': ('SqlDatabase',),
           'asqueel.environment': ('SqlEnvironment', 'ApplicationEnvironment'),
           'asqueel.object_tree': ('DbDatabaseObj',)}


def declare(root):
    table = root.packages().package('app', sqlschema='main', sqlprefix=False).table('item', pkey='id')
    table.column('id', dtype='serial')
    table.column('label')


def recipe(tmp_path):
    config = SqlDatabaseConfig()
    root = config.source.db('items', implementation='sqlite', name_long='Item register')
    root.connection('main', database=str(tmp_path / 'items.sqlite'))
    declare(root)
    return config


def test_one_database_class():
    for module_name, names in REMOVED.items():
        try:
            module = importlib.import_module(module_name)
        except ModuleNotFoundError:
            continue
        for name in names:
            assert not hasattr(module, name), f'{module_name}.{name}'
    for name in REMOVED['asqueel']:
        assert name not in asqueel.__all__
    assert {cls.__name__ for cls in AsqueelDb.__mro__}.isdisjoint(
        {'Database', 'SqlDatabase', 'SqlEnvironment', 'ApplicationEnvironment'})


def test_model_and_table_take_their_owner_only():
    assert list(inspect.signature(DbModel.__init__).parameters) == ['self', 'db']
    assert list(inspect.signature(SqlTable.__init__).parameters) == ['self', 'tblobj', 'db']


def test_the_database_exists_before_its_model_is_built(tmp_path, monkeypatch):
    seen = []
    original = DbModel.build

    def spy(self, *args, **kwargs):
        seen.append((type(self.db), self.db))
        return original(self, *args, **kwargs)

    monkeypatch.setattr(DbModel, 'build', spy)
    db = AsqueelDb(recipe(tmp_path))
    assert seen == [(AsqueelDb, db)]
    assert db.model.db is db
    assert db.table('app.item').db is db


def test_the_db_node_describes_the_database(tmp_path):
    db = AsqueelDb(recipe(tmp_path))
    assert db.name_long == 'Item register'
    assert db.implementation == 'sqlite'


def test_the_environment_lives_on_the_database(tmp_path):
    db = AsqueelDb(recipe(tmp_path))
    db.currentEnv['factor'] = 3
    with db.tempEnv(factor=4):
        assert db.currentEnv['factor'] == 4
    assert db.currentEnv['factor'] == 3


class ItemsDb(AsqueelDb):
    def main(self, root):
        root = root.db('items', implementation='sqlite')
        root.connection('main', database=':memory:')
        declare(root)


def test_a_database_subclass_writes_its_own_source():
    db = ItemsDb()
    assert type(db) is ItemsDb
    assert set(db.model.table('app.item').columns) == {'id', 'label'}
    assert db.table('app.item').db is db


def test_a_database_subclass_refuses_a_second_source(tmp_path):
    with pytest.raises(TypeError):
        ItemsDb(recipe(tmp_path))
