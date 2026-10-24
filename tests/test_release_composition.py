"""Ordered source layers compose explicit values before defaults/expansion."""
from copy import deepcopy

import pytest

from asqueel import AsqueelDb, SqlDatabaseConfig
from asqueel.configuration import SqlConfigHandler, compose_recipe
from genro_builders.builder import element
from genro_builders.contrib.config import ConfigBuilder, ConfigHandler


class Base(SqlDatabaseConfig):
    def main(self, root):
        table = root.db('invoice').packages().package('invc').table('customer', name_long='Cliente')
        table.options().sysFields(id={'type': 'uuid', 'indexed': True}, draft=True)
        table.attr.update(comment='blue', name_short='Cust')


class Overlay(SqlDatabaseConfig):
    def main(self, root):
        table = root.db('invoice').packages().package('invc').table('customer', name_long=None)
        table.options().sysFields(id={'name_short': 'ID'})
        table.attr.update(comment='green')


PATH = 'packages.invc.tables.customer'


def test_owned_layers_merge_dictionary_keys_and_preserve_explicit_none():
    base = Base()
    base.create()
    overlay = Overlay()
    overlay.create()
    config = SqlConfigHandler(compose_recipe(overlay, [base]))
    assert config(PATH + '.name_long') is None
    assert config(PATH + '.options.sysFields.id') == {
        'type': 'uuid', 'indexed': True, 'name_short': 'ID'}
    assert config(PATH + '.options.sysFields.draft') is True
    assert config(PATH + '.comment') == 'green'
    assert config(PATH + '.name_short') == 'Cust'
    assert base.source['db.' + PATH].get_attr('name_long') == 'Cliente'
    assert 'draft' not in overlay.source['db.' + PATH + '.options.sysFields'].attr


def test_reset_in_a_later_recipe_erases_only_its_option_before_defaults():
    class Reset(SqlDatabaseConfig):
        def main(self, root):
            opts = root.db('invoice').packages().package('invc').table('customer').options()
            opts.reset('sysFields')
            opts.sysFields(id=False)

    config = SqlConfigHandler(compose_recipe(Reset, [Base, Overlay]))
    assert config(PATH + '.options.sysFields.id') is False
    assert config(PATH + '.options.sysFields.draft') is False
    assert config(PATH + '.comment') == 'green'


def test_reset_without_reactivation_keeps_the_option_absent():
    class Reset(SqlDatabaseConfig):
        def main(self, root):
            opts = root.db('invoice').packages().package('invc').table('customer').options()
            opts.reset('sysFields')

    config = SqlConfigHandler(compose_recipe(Reset, [Base]))
    assert config.builder.source.get_node('db.' + PATH + '.options.sysFields') is None
    recomposed = SqlConfigHandler(compose_recipe(config.builder, [Base]))
    assert recomposed.builder.source.get_node('db.' + PATH + '.options.sysFields') is None


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
    config = SqlConfigHandler(compose_recipe(Overlay, [Base]))
    option = config.builder.source['db.' + PATH + '.options.sysFields']
    assert 'group' not in option.attr
    assert config(PATH + '.options.sysFields.group') == 'zzz'


def test_nonnullable_options_reject_none():
    source = Base()
    source.create()
    with pytest.raises(ValueError, match='None'):
        source.source['db.' + PATH].options().sysFields(group=None)


def test_mounted_and_standalone_source_preserve_packages_groups_and_options():
    class HostElements:
        @element(_meta={'subbuilder': 'db_class:grammar'})
        def database(self, db_class: type):
            ...

    class Host(HostElements, ConfigBuilder):
        def main(self, root):
            populate(root.database(db_class=AsqueelDb))

    def populate(root):
        db = root.db('invoice', implementation='postgres')
        db.connection('main', database='invoice').options().driver(connect_timeout=2)
        pkg = db.packages().package('invc', sqlschema='sales')
        table = pkg.table('customer', caption_field='name')
        table.colgroup('details', col_dtype='T').column('name')
        table.options().sysFields(id={'type': 'uuid'})

    class Standalone(SqlDatabaseConfig):
        def main(self, root):
            populate(root)

    hosted = ConfigHandler(Host)
    mounted = SqlConfigHandler(compose_recipe(hosted.builder.source.get_node('database_0.db')))
    standalone = SqlConfigHandler(compose_recipe(Standalone))

    def declarations(handler):
        return [(path, node.node_tag, {k: v for k, v in node.attr.items() if k != '_meta'})
                for path, node in handler.builder.source.query('#p,#n', deep=True)]

    assert declarations(mounted) == declarations(standalone)


def test_declared_attributes_compose_by_attribute():
    source = SqlDatabaseConfig()
    pkg = source.source.db('d').packages().package(
        'p', comment='blue', name_short='P')
    with source.contribution('later'):
        source.source['db.packages'].package('p', comment='green')
    assert pkg.get_attr('comment') == 'green'
    assert pkg.get_attr('name_short') == 'P'


def test_field_disable_and_reenable_preserves_configuration_until_reset():
    source = Base()
    source.create()
    opts = source.source['db.' + PATH].options()
    with source.contribution('disable'):
        opts.sysFields(id=False, enabled=False)
    with source.contribution('enable'):
        fields = opts.sysFields(id=True, enabled=True)
    assert fields.get_attr('id') == {'type': 'uuid', 'indexed': True}
    with source.contribution('restart'):
        opts.reset('sysFields')
        assert opts.sysFields(id=True).get_attr('id') is True


def test_layered_change_of_column_kind_is_rejected_before_model_resolution():
    class Physical(SqlDatabaseConfig):
        def main(self, root):
            root.db('d').packages().package('p').table('t').column('value', 'T')

    class Virtual(SqlDatabaseConfig):
        def main(self, root):
            root.db('d').packages().package('p').table('t').formulaColumn('value', '1')

    with pytest.raises(ValueError, match='conflicting element kinds'):
        compose_recipe(Virtual, [Physical])


@pytest.mark.parametrize('name', ['', ' ', 'bad.name', 'bad@name', '$name', 'bad/name', 'bad\\name'])
def test_logical_package_names_are_not_paths(name):
    builder = SqlDatabaseConfig()
    with pytest.raises(ValueError, match='name|separator'):
        builder.source.db('d').packages().package(name)


def test_common_metadata_is_declared_on_db_package_table_and_column():
    builder = SqlDatabaseConfig()
    meta = {'name_long': 'Long', 'name_short': 'Short', 'comment': 'Comment'}
    db = builder.source.db('d', **meta)
    pkg = db.packages().package('p', **meta)
    pkg.table('t', **meta).column('id', dtype='L', **meta)
    builder.validate_model()
