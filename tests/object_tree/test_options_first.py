"""Options precede ordinary declarations without mutating the authored recipe."""
import pytest

from asqueel import AsqueelDb, SqlDatabaseConfig
from asqueel.catalog import SqlModelCatalog
from asqueel.model_expansion import _TableExpansion
from examples.test_invoice_pg import source
from tests.object_tree.test_invoice import TABLES


@pytest.mark.parametrize('position', ['before', 'between', 'after'])
def test_options_are_consumed_once_before_columns(position, monkeypatch):
    config = SqlDatabaseConfig()
    table = config.source.db('test').packages().package('pkg').table('item')

    def options():
        table.options().sys_fields(user_upd=False, syscode=True)
        table.options().audit(mode='lazy')

    if position == 'before':
        options()
    table.column('name')
    if position == 'between':
        options()
    # A declaration of an option-generated field contributes attributes,
    # but is consumed with the option rather than emitted twice.
    table.column('id', size='22', name_long='Identifier', validate_notnull=True)
    table.column('description')
    if position == 'after':
        options()
    before = config.source.to_json()
    calls = []
    original = _TableExpansion.sys_fields

    def sys_fields(self):
        calls.append(self.key)
        return original(self)

    monkeypatch.setattr(_TableExpansion, 'sys_fields', sys_fields)
    for _ in range(2):
        model = AsqueelDb(config).model
        item = model.table('pkg.item')
        assert list(item.columns) == [
            'id', '__ins_ts', '__del_ts', '__mod_ts', '__ins_user', '__syscode',
            '__version', 'name', 'description',
        ]
        assert list(item)[0] == 'options'
        assert item.column('id').attributes['name_long'] == 'Identifier'
        assert item.column('id').validations == {'notnull': True}
        assert item.options['audit'].attributes['mode'] == 'lazy'
        assert item.options['sys_fields'].attributes['syscode'] is True
        assert config.source.to_json() == before
    assert calls == ['pkg.item', 'pkg.item']


def test_disabled_options_do_not_create_or_move_columns():
    config = SqlDatabaseConfig()
    table = config.source.db().packages().package('pkg').table('item')
    table.column('name')
    table.column('id', size='22')
    table.options().sys_fields(enabled=False)
    model = AsqueelDb(config).model
    assert list(model.table('pkg.item').columns) == ['name', 'id']
    assert model.table('pkg.item').options['sys_fields'].attributes['enabled'] is False


@pytest.fixture(scope='module')
def invoice_models():
    config = source()
    before = config.source.to_json()
    authored = {}
    for package, table, column in SqlModelCatalog(config).physical_columns:
        authored.setdefault(f'{package}.{table}', []).append(column)
    first = AsqueelDb(config).model
    second = AsqueelDb(config).model
    assert config.source.to_json() == before
    return first, second, authored


@pytest.mark.parametrize('key', TABLES)
def test_every_native_table_retains_options_and_repeatable_order(invoice_models, key):
    first, second, authored = invoice_models
    first, second = first.table(key), second.table(key)
    assert list(first.columns) == list(second.columns)
    assert list(first.virtual_columns) == list(second.virtual_columns)
    # All new fields precede ordinary authored columns. Explicit declarations
    # enriching system fields are consumed with the option, not emitted again.
    names = list(first.columns)
    generated = set(names) - set(authored.get(key, ()))
    ordinary = [name for name in authored.get(key, ())
                if not first.column(name).attributes.get('x_legacy__sysfield')]
    if generated and ordinary:
        assert max(names.index(name) for name in generated) < min(names.index(name) for name in ordinary)
    assert [name for name in names if name in ordinary] == ordinary
    if first.get('options') is not None:
        assert list(first)[0] == 'options'
        assert list(first.options) == list(second.options)


def test_cross_table_options_keep_dependencies_and_relations():
    config = SqlDatabaseConfig()
    pkg = config.source.db().packages().package('pkg')
    master = pkg.table('master')
    master.column('name')
    master.options().sys_fields()
    attachment = pkg.table('attachment')
    attachment.column('extra')
    attachment.options().attachments(master='pkg.master')
    before = config.source.to_json()
    model = AsqueelDb(config).model
    table = model.table('pkg.attachment')
    assert list(table.columns)[-1] == 'extra'
    assert table.column('@maintable_id.name') is model.table('pkg.master').column('name')
    assert config.source.to_json() == before
