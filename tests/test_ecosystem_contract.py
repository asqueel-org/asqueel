"""Regression coverage for the published Bag/Builders 0.27 APIs."""

from datetime import date
from decimal import Decimal

import pytest
from asqueel import SqlBuilder
from asqueel.catalog import SqlModelCatalog
from asqueel.grammar_doc import generate_grammar_md


def test_catalog_paths_and_typed_extension_metadata():
    model = SqlBuilder()
    table = model.source.db('demo').schemas().schema('public').tables().table('invoice', pkey='id')
    columns = table.columns()
    columns.column('id', dtype='L')
    metadata = {'created': date(2026, 9, 29), 'amount': Decimal('12.50'), 'tags': ['a', 'b']}
    columns.column('total', dtype='N', x_business=metadata)
    model.validate_model()
    catalog = SqlModelCatalog(model)
    node = catalog.physical_columns['public', 'invoice', 'total']
    assert catalog.path(node) == 'db.schemas.public.tables.invoice.columns.total'
    assert node.get_attr('x_business') == metadata
    assert catalog.children(columns) == list(columns.value)
    assert list(catalog.tables) == [('public', 'invoice')]


def test_documentation_keeps_parameter_descriptions_and_semantic_plane():
    document = generate_grammar_md()
    assert 'the database name' in document
    assert '| semantic | source-only free description;' in document


def test_direct_sql_render_is_explicitly_unimplemented():
    model = SqlBuilder()
    model.source.db('demo')
    assert model.renderer_sql.mode == 'sql'
    with pytest.raises(NotImplementedError, match='rendered_item'):
        model.render(target=False)
