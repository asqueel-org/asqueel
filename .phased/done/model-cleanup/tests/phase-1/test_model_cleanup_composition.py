"""Model cleanup, Phase 1: the recipe is composed once, before any render; no renderer composes."""
from pathlib import Path

import pytest

import asqueel
from asqueel import AsqueelDb, SqlDatabaseConfig
from tests.model_cleanup_support import example_sources, golden, normalized, objects_dump

PACKAGE = Path(asqueel.__file__).resolve().parent
COMPOSITION = ('_owned_handler', '_effective_model_builder', 'load_package_layouts', '_compose_source',
               '_validate_source_shape', 'configuration_source', 'self.config(')


def renderer_modules():
    names = {path.name for path in PACKAGE.glob('*renderer*.py')} | {'migration.py', 'emitter.py'}
    return sorted(PACKAGE / name for name in names if (PACKAGE / name).is_file())


def test_no_renderer_module_composes_the_recipe():
    for path in renderer_modules():
        text = path.read_text()
        found = [name for name in COMPOSITION if name in text]
        assert not found, f'{path.name} composes the recipe: {found}'


def base(tmp_path):
    recipe = SqlDatabaseConfig()
    root = recipe.source.db('composed', implementation='sqlite')
    root.connection('main', database=str(tmp_path / 'composed.sqlite'))
    table = root.packages().package('app', sqlschema='main', sqlprefix=False).table('item', pkey='id')
    table.column('id', dtype='serial')
    table.column('label')
    return recipe


@pytest.fixture
def compositions(monkeypatch):
    from asqueel import configuration
    calls = []
    original = configuration.load_package_layouts

    def spy(builder):
        calls.append(builder)
        return original(builder)

    monkeypatch.setattr(configuration, 'load_package_layouts', spy)
    return calls


def test_a_database_composes_its_recipe_once(tmp_path, compositions):
    db = AsqueelDb(base(tmp_path))
    assert len(compositions) == 1
    assert set(db.model.table('app.item').columns) == {'id', 'label'}


def test_parents_are_composed_once_with_the_recipe(tmp_path, compositions):
    overlay = SqlDatabaseConfig()
    overlay.source.db('composed').packages().package('app').table('item').column('note')
    db = AsqueelDb(overlay, parents=[base(tmp_path)])
    assert len(compositions) == 1
    assert set(db.model.table('app.item').columns) == {'id', 'label', 'note'}


@pytest.mark.parametrize('label', ['test_invoice_pg', 'two_schemas', 'sqlite'])
def test_the_examples_keep_their_model(label):
    db = AsqueelDb(example_sources()[label])
    try:
        assert normalized(objects_dump(db)) == golden(label, 'objects')
    finally:
        db.closeConnection()
