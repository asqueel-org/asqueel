"""Model cleanup, Phase 2: one object renderer, reached only through builder.render()."""
import importlib

import pytest

import asqueel
from asqueel import AsqueelDb, SqlBuilder, SqlDatabaseConfig
from asqueel.builder import SqlSourceBag

REMOVED_NAMES = ('build_database', 'resolve_model', 'render_model', 'SqlRenderer')
REMOVED_MODULES = ('asqueel.renderer', 'asqueel.object_renderer', 'asqueel.model')


class Plain(SqlBuilder):
    def main(self, root):
        table = root.db('plain').schemas().schema('main').tables().table('item', pkey='id')
        table.columns().column('id', dtype='I')


def recipe(tmp_path):
    config = SqlDatabaseConfig()
    root = config.source.db('rendered', implementation='sqlite')
    root.connection('main', database=str(tmp_path / 'rendered.sqlite'))
    table = root.packages().package('app', sqlschema='main', sqlprefix=False).table('item', pkey='id')
    table.column('id', dtype='serial')
    return config


def test_the_builder_owns_its_source_class():
    assert SqlBuilder._source_class is SqlSourceBag
    assert type(SqlBuilder().source) is SqlSourceBag


def test_objects_is_the_only_object_mode():
    assert SqlBuilder._default_render_mode == 'objects'
    assert 'renderer_objects' in dir(SqlBuilder)
    for builder in (SqlBuilder, SqlDatabaseConfig):
        assert 'renderer_sql' not in dir(builder)
        assert 'renderer_objects_tree' not in dir(builder)


def test_the_removed_entry_points_are_gone():
    for name in REMOVED_NAMES:
        assert name not in asqueel.__all__
        assert not hasattr(asqueel, name)
    for module in REMOVED_MODULES:
        with pytest.raises(ModuleNotFoundError):
            importlib.import_module(module)


@pytest.fixture
def deliveries(monkeypatch):
    renderer = type(SqlBuilder().get_renderer('objects'))
    calls = []
    original = renderer.finalize

    def spy(self, result, target=None, **opts):
        calls.append(target)
        return original(self, result, target, **opts)

    monkeypatch.setattr(renderer, 'finalize', spy)
    return calls


def test_the_database_is_the_target_of_the_render(tmp_path, deliveries):
    db = AsqueelDb(recipe(tmp_path))
    assert type(db) is AsqueelDb
    assert deliveries == [db]


def test_a_plain_model_recipe_builds_a_database(deliveries):
    db = AsqueelDb(Plain)
    assert type(db) is AsqueelDb
    assert db.implementation == 'sqlite'
    assert deliveries == [db]


def test_rendering_objects_needs_a_database(tmp_path):
    with pytest.raises(TypeError, match='AsqueelDb'):
        recipe(tmp_path).render()
