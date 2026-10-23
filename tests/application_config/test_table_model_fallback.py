"""Operational tables delegate missing reads, not method binding or writes."""
import pytest

from asqueel import AsqueelDb, SqlTable
from types import SimpleNamespace
from tests.application_config.test_application import Recipe


class StructuralTable:
    fullname = "app.item"
    name = "item"
    columns = {"id": SimpleNamespace(name="id")}
    attributes: dict = {}

    def column(self, name):
        return self.columns[name]

    def owner(self):
        return self

    def query(self):
        raise AssertionError('The operational query must take precedence')

    @property
    def broken(self):
        raise ValueError('model property error')


@pytest.fixture
def table():
    return SqlTable(StructuralTable())


def test_database_table_exposes_model_members_without_connecting():
    db = AsqueelDb(Recipe)
    driver = db.adapter
    try:
        table = db.table('app.item')
        assert table.model is db.model.table('app.item')
        assert table.name == table.model.name == 'item'
        assert table.pkey == table.model.pkey == 'id'
        assert table.attributes is table.model.attributes
        assert table.model is db.model.table('app.item')
        assert driver.calls == []
    finally:
        db.closeConnection()


def test_operational_members_take_precedence(table):
    assert table.query.__self__ is table
    assert table.query.__func__ is SqlTable.query
    assert table.column('id') is table.columns['id']
    assert table.columns['id'] is table.model.columns['id']
    assert table.columns is table.model.columns
    table.name = 'local name'
    assert table.name == 'local name'
    assert table.model.name == 'item'


def test_delegated_method_remains_bound_to_model(table):
    assert table.owner.__self__ is table.model
    assert table.owner() is table.model


def test_missing_members_raise_attribute_error(table):
    assert not hasattr(table, 'missing_member')
    assert getattr(table, 'missing_member', 'default') == 'default'
    with pytest.raises(AttributeError, match='missing_member'):
        table.missing_member


def test_model_property_errors_are_not_hidden(table):
    with pytest.raises(ValueError, match='model property error'):
        table.broken


def test_fallback_before_model_assignment_does_not_recurse():
    table = SqlTable.__new__(SqlTable)
    assert not hasattr(table, 'model')
    with pytest.raises(AttributeError):
        table.missing_member


def test_fallback_can_read_hierarchical_model_without_rebinding_its_methods():
    recipe = Recipe()
    recipe.create()
    model = AsqueelDb(recipe).model
    table = SqlTable.__new__(SqlTable)
    table.model = model.table('app.item')
    assert table.parent is table.model.parent
    assert table.root is model.obj
    assert table.getAttr.__self__ is table.model
    assert table.getAttr('pkey') == 'id'
