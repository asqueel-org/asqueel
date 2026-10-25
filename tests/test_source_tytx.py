"""A recipe source saved with to_tytx() rebuilds the same database: AsqueelDb accepts the .tytx file."""
from genro_bag import Bag
from genro_bag.resolvers import EnvResolver
import pytest

from asqueel import AsqueelDb, SqlDatabaseConfig
from asqueel.builder import SqlSourceBag
from examples.sqlite.configure import Recipe
from examples.test_invoice_pg import source as invoice_source
from examples.two_schemas.configure import DatabaseConfiguration
from tests.model_cleanup_support import normalized, objects_dump


def created(recipe_class):
    recipe = recipe_class()
    recipe.create()
    return recipe


RECIPES = {
    'test_invoice_pg': invoice_source,
    'two_schemas': lambda: created(DatabaseConfiguration),
    'sqlite': lambda: created(Recipe),
}


def snapshot(source):
    db = AsqueelDb(source)
    try:
        return normalized(db.config.builder.render(mode='migration')), normalized(objects_dump(db))
    finally:
        db.closeConnection()


@pytest.mark.parametrize('label', sorted(RECIPES))
def test_a_saved_recipe_source_rebuilds_the_same_database(label, tmp_path):
    saved = tmp_path / f'{label}.tytx'
    saved.write_text(RECIPES[label]().source.to_tytx(), encoding='utf-8')
    assert snapshot(str(saved)) == snapshot(RECIPES[label]())


def test_the_source_decodes_as_a_sql_source_bag():
    assert type(Bag.from_tytx(RECIPES['sqlite']().source.to_tytx())) is SqlSourceBag


def test_environment_resolvers_stay_resolvers_in_the_saved_source():
    decoded = Bag.from_tytx(RECIPES['two_schemas']().source.to_tytx())
    connection = next(node for _, node in decoded.query('#p,#n', deep=True) if node.node_tag == 'connection')
    assert isinstance(connection.attr['password'], EnvResolver)


def test_the_saved_source_is_validated_by_the_grammar(tmp_path):
    config = SqlDatabaseConfig()
    config.source.db('bad').packages().package('app').table('item', pkey='id').column('id', dtype='L')
    tampered = Bag.from_tytx(config.source.to_tytx())
    next(node for _, node in tampered.query('#p,#n', deep=True) if node.node_tag == 'column').set_attr(foo=1)
    saved = tmp_path / 'bad.tytx'
    saved.write_text(tampered.to_tytx(), encoding='utf-8')
    with pytest.raises(ValueError, match="Element 'column' does not accept 'foo'"):
        AsqueelDb(str(saved))
