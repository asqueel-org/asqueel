"""Ordered source layers compose explicit values before defaults/expansion."""
from copy import deepcopy

import pytest

from asqueel import AsqueelDb, SqlDatabaseConfig
from asqueel.configuration import _owned_handler
from genro_builders.builder import element
from genro_builders.contrib.config import ConfigBuilder, ConfigHandler


class Base(SqlDatabaseConfig):
    def main(self, root):
        table = root.db('invoice').packages().package('invc').table('customer', name_long='Cliente')
        table.options().sys_fields(id={'type': 'uuid', 'indexed': True}, draft=True)
        table.options().metadata('ui', {'color': 'blue', 'position': 2})


class Overlay(SqlDatabaseConfig):
    def main(self, root):
        table = root.db('invoice').packages().package('invc').table('customer', name_long=None)
        table.options().sys_fields(id={'name_short': 'ID'})
        table.options().metadata('ui', {'color': 'green'})


PATH = 'packages.invc.tables.customer'


def test_owned_layers_merge_dictionary_keys_and_preserve_explicit_none():
    base = Base()
    base.create()
    overlay = Overlay()
    overlay.create()
    config = _owned_handler(overlay, [base])
    assert config(PATH + '.name_long') is None
    assert config(PATH + '.options.sys_fields.id') == {
        'type': 'uuid', 'indexed': True, 'name_short': 'ID'}
    assert config(PATH + '.options.sys_fields.draft') is True
    assert config(PATH + '.options.metadata_ui.values') == {'color': 'green', 'position': 2}
    assert base.source['db.' + PATH].get_attr('name_long') == 'Cliente'
    assert 'draft' not in overlay.source['db.' + PATH + '.options.sys_fields'].attr


def test_reset_in_a_later_recipe_erases_only_its_option_before_defaults():
    class Reset(SqlDatabaseConfig):
        def main(self, root):
            opts = root.db('invoice').packages().package('invc').table('customer').options()
            opts.reset('sys_fields')
            opts.sys_fields(id=False)

    config = _owned_handler(Reset, [Base, Overlay])
    assert config(PATH + '.options.sys_fields.id') is False
    assert config(PATH + '.options.sys_fields.draft') is False
    assert config(PATH + '.options.metadata_ui.values')['color'] == 'green'


def test_reset_without_reactivation_keeps_the_option_absent():
    class Reset(SqlDatabaseConfig):
        def main(self, root):
            opts = root.db('invoice').packages().package('invc').table('customer').options()
            opts.reset('sys_fields')

    config = _owned_handler(Reset, [Base])
    assert config.builder.source.get_node('db.' + PATH + '.options.sys_fields') is None
    recomposed = _owned_handler(config.builder, [Base])
    assert recomposed.builder.source.get_node('db.' + PATH + '.options.sys_fields') is None


def test_copying_a_source_does_not_lose_same_contribution_conflict_detection():
    source = Base()
    source.create()
    with source.contribution('custom'):
        source.source['db.' + PATH].set_attr(name_long='Custom')
        source.source['db.packages.invc'].table('customer', name_short='C')
    copy = deepcopy(source)
    with copy.contribution('custom'), pytest.raises(ValueError, match='conflicting'):
        copy.source['db.packages.invc'].table('customer', name_short='D')


def test_omission_does_not_materialize_option_defaults_in_source():
    config = _owned_handler(Overlay, [Base])
    option = config.builder.source['db.' + PATH + '.options.sys_fields']
    assert 'timestamp_type' not in option.attr
    assert config(PATH + '.options.sys_fields.timestamp_type') == 'DHZ'


def test_nonnullable_options_reject_none():
    source = Base()
    source.create()
    with pytest.raises(ValueError, match='None'):
        source.source['db.' + PATH].options().sys_fields(group=None)


def test_mounted_and_standalone_source_preserve_packages_groups_and_options():
    class HostElements:
        @element(_meta={'subbuilder': 'db_class:grammar'})
        def database(self, db_class: type):
            ...

    class Host(HostElements, ConfigBuilder):
        def main(self, root):
            populate(root.database(db_class=AsqueelDb))

    def populate(root):
        db = root.db('invoice')
        db.schemas().schema('sales').options().metadata('ui', {'label': 'Sales'})
        db.connection('main', database='invoice').options().driver(connect_timeout=2)
        pkg = db.packages().package('invc', sqlschema='sales')
        table = pkg.table('customer', caption_field='name')
        table.colgroup('details', col_dtype='T').column('name')
        table.options().sys_fields(id={'type': 'uuid'})

    class Standalone(SqlDatabaseConfig):
        def main(self, root):
            populate(root)

    hosted = ConfigHandler(Host)
    mounted = _owned_handler(hosted.builder.source.get_node('database_0.db'))
    standalone = _owned_handler(Standalone)

    def declarations(handler):
        return [(path, node.node_tag, {k: v for k, v in node.attr.items() if k != '_meta'})
                for path, node in handler.builder.source.query('#p,#n', deep=True)]

    assert declarations(mounted) == declarations(standalone)
