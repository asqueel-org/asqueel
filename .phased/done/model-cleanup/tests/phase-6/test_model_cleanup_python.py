"""Model cleanup, Phase 6: the Python recipe is rendered from the source by a RendererBase renderer."""
from genro_builders.renderer import RendererBase

from asqueel import SqlBuilder, SqlModelReader, SqlPythonEmitter
from tests.model_cleanup_support import GOLDEN, golden


def small_recipe():
    builder = SqlBuilder()
    table = (builder.source.db('x').schemas().schema('s', sqlname='phys_s')
             .tables().table('t', pkey='id', sqlname='phys_t'))
    columns = table.columns()
    columns.column('id', dtype='I')
    columns.column('name', dtype='A', size='0:20', sqlname='phys_name')
    return builder


def test_the_python_renderer_is_a_builders_renderer():
    assert RendererBase in SqlPythonEmitter.__mro__
    assert type(SqlBuilder().get_renderer('python')) is SqlPythonEmitter
    assert not hasattr(SqlPythonEmitter, 'emit')


def test_a_recipe_renders_the_module_it_emitted_before():
    text = small_recipe().render(mode='python')
    assert text == (GOLDEN / 'small.recipe.py.txt').read_text()


def test_a_read_structure_renders_under_its_class_name():
    builder = SqlModelReader(golden('two_schemas', 'migration')).to_builder()
    text = builder.render(mode='python', class_name='TwoSchemas')
    assert text == (GOLDEN / 'two_schemas.recipe.py.txt').read_text()


def test_the_rendered_module_rebuilds_the_same_structure():
    namespace = {}
    exec(compile(small_recipe().render(mode='python'), '<rendered recipe>', 'exec'), namespace)
    rebuilt = namespace['ImportedDatabase']()
    rebuilt.create()
    assert rebuilt.render(mode='migration') == small_recipe().render(mode='migration')
