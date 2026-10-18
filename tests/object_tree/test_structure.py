"""Contracts of the alternative hierarchy, independently of the compiler."""
from genro_bag import BagResolver
from genro_bag.resolvers import BagCbResolver, EnvResolver
from genro_builders.renderer import RendererBase
import pytest

from asqueel import SqlDatabaseConfig
from asqueel.object_tree import DbModelObj, DbColumnObj, DbVirtualColumnObj
from asqueel.object_tree_renderer import SqlObjectTreeRenderer
from tests.application_config.test_render_structure import recipe


def test_parent_root_identity_and_independent_old_renderer():
    source, _, _ = recipe()
    model = source.render(mode='objects_tree')
    table = model.table('invc.customer')
    package = model.package('invc')
    column = table.column('id')
    assert model.obj['invc.tables.customer'] is table
    assert model.obj['invc.tables.customer.columns.id'] is column
    assert model.column('invc.customer.id') is column
    assert package.tables['customer'] is table
    assert column.parent.parent is table
    assert column.pkg is table.pkg is package
    assert column.root is model.obj
    assert column.db is model.db
    assert column.db.model is model
    assert model.obj.rootparent is model
    assert column['.invc.tables.customer'] is table
    assert isinstance(column, DbColumnObj)
    assert table.sqlname == 'invc_customer'
    assert model.table('invc.invoice').sqlname == 'invoices'
    assert model.table('adm.user').sqlname == 'user'
    assert model.package('empty') is not None
    assert model.db.get('connection') is None
    old = source.render()
    try:
        assert old.model.table('invc.customer').columns['id'].dtype == column.dtype
        assert source._default_render_mode == 'objects'
        assert set(source.materialized) == {'objects', 'objects_tree'}
        table.attributes['name_long'] = 'changed'
        assert old.model.table('invc.customer').attributes['name_long'] == 'Cliente'
        again = source.render(mode='objects_tree')
        assert again.table('invc.customer').attributes['name_long'] == 'Cliente'
        assert again.table('invc.customer') is not table
    finally:
        old.close()


def test_generic_walk_collects_fragments_then_finalize_constructs_objects(monkeypatch):
    assert SqlObjectTreeRenderer.render is RendererBase.render
    assert SqlObjectTreeRenderer.render_children is RendererBase.render_children
    events = []
    def before(self):
        events.append(('enter', self.name))
        if self.parent is not None:
            assert self.name not in self.parent.children
    def after(self):
        events.append(('exit', self.name))
    monkeypatch.setattr(DbModelObj, 'doInit', before)
    monkeypatch.setattr(DbModelObj, 'afterChildrenCreation', after)
    source, _, _ = recipe()
    fragments = source.materialize(mode='objects_tree')
    assert events == []
    model = source.get_renderer('objects_tree').finalize(fragments)
    assert events.index(('enter', 'columns')) < events.index(('enter', 'id'))
    assert events.index(('exit', 'id')) < events.index(('exit', 'columns'))
    assert model.table('invc.invoice').column('@customer_id.id') is model.column('invc.customer.id')
    # The complete global registry exists only after all packages were constructed.
    assert model.table('invc.invoice').column('@user_id.id') is model.column('adm.user.id')


def test_flat_resolvers_validation_options_and_source_ownership(monkeypatch):
    source, root, customer = recipe()
    calls = []
    def length():
        calls.append(1)
        return '3:40'
    monkeypatch.setenv('TREE_COLOR', 'blue')
    declared = customer.column('label', foo_bar_color=EnvResolver('TREE_COLOR'),
                               validate_len=BagCbResolver(length, cache_time=-1))
    declared.validation(notnull=True)
    root.connection('archive', database=BagCbResolver(lambda: pytest.fail('Connection evaluated')))
    customer.options().sys_fields(id=False, syscode=True)
    customer.options().audit(mode='lazy')
    model = source.render(mode='objects_tree')
    table = model.table('invc.customer')
    assert calls == [1]
    assert isinstance(declared.attr['validate_len'], BagResolver)
    assert table.column('label').attributes['foo_bar_color'] == 'blue'
    assert table.column('label').validations == {'len': '3:40', 'notnull': True}
    assert table.column('__syscode').attributes['unique'] is True
    assert table.indexes['customer___syscode_key'].attributes['unique'] is True
    assert table.column('__ins_ts').dtype == 'DHZ'
    assert table.options['audit'].attributes['mode'] == 'lazy'
    assert table.options.parent is table
    assert source.source.get_node('db.packages.invc.tables.customer.columns.__syscode') is None
    assert isinstance(table.virtual_columns['__record_pointer'], DbVirtualColumnObj)
    monkeypatch.setenv('TREE_COLOR', 'red')
    assert table.column('label').attributes['foo_bar_color'] == 'blue'


def test_lazy_cycles_default_inverse_and_parentpath():
    source = SqlDatabaseConfig()
    pkg = source.source.db().packages().package('app')
    parent = pkg.table('parent', pkey='id')
    parent.column('id', dtype='L')
    parent.column('parent_id', dtype='L').relation('app.parent.id')
    model = source.render(mode='objects_tree')
    table = model.table('app.parent')
    assert table.relations.keys() == ['id', 'parent_id', '@parent_id', '@app_parent_parent_id']
    node = table.relations.get_node('@parent_id')
    resolver = node.resolver
    assert isinstance(resolver, BagResolver)
    assert resolver.parentpath == [table.column('parent_id')]
    assert resolver.path == ['*O', 'app_parent']
    assert resolver._model is model
    assert table.column('@parent_id.@parent_id.id') is table.column('id')
    assert table.column('@app_parent_parent_id.id') is table.column('id')
    child = node.value
    assert child.get_node('id').attr['prfx'] == 'parent'
    assert child.get_node('@parent_id').resolver is not resolver
    assert table.relations.get_node('@app_parent_parent_id').attr['joiner']['private_relation']


def test_alias_view_preserves_target_identity_and_explicit_dtype():
    source, _, customer = recipe()
    customer.aliasColumn('copy', relation_path='id')
    customer.aliasColumn('copy_text', relation_path='id', dtype='T')
    model = source.render(mode='objects_tree')
    table = model.table('invc.customer')
    assert table.column('copy').originalColumn is table.column('id')
    assert table.column('copy').dtype == 'L'
    assert table.column('copy_text').dtype == 'T'
    assert table.virtual_columns['copy'].parent.parent is table


def test_composite_relations_keep_declared_structural_key():
    source = SqlDatabaseConfig()
    pkg = source.source.db().packages().package('app')
    owner = pkg.table('owner', pkey='key')
    for name in ('a', 'b'):
        owner.column(name, dtype='L')
    owner.compositeColumn('key', columns='a,b')
    item = pkg.table('item', pkey='id')
    for name in ('id', 'a', 'b'):
        item.column(name, dtype='L')
    item.compositeColumn('ref', columns='a,b').relation('app.owner.key', foreign_key=True)
    model = source.render(mode='objects_tree')
    joiner = model.table('app.item').relations.get_node('@ref').attr['joiner']
    assert joiner['many_relation'] == 'app.item.ref'
    assert joiner['one_relation'] == 'app.owner.key'
    assert model.table('app.owner').pkey == 'key'
    assert model.physical_columns(model.table('app.owner'), 'key') == ('a', 'b')
    assert model.table('app.item').column('@ref.a') is model.column('app.owner.a')


def test_invalid_relation_and_target_fail_without_database_io():
    source, _, customer = recipe()
    customer.column('missing_id', dtype='L').relation('missing.table.id')
    with pytest.raises(ValueError):
        source.render(mode='objects_tree')
    source, _, _ = recipe()
    with pytest.raises(ValueError, match='targets'):
        source.render(mode='objects_tree', target=object())


def test_mounted_grammar_uses_its_own_defaults_and_same_generic_walk():
    from tests.application_config.test_configuration import MountedRecipe
    source = MountedRecipe()
    source.create()
    model = source.render(mode='objects_tree')
    table = model.table('sales.customer')
    assert model.obj['sales.tables.customer'] is table
    assert table.column('label').dtype == 'I'
    assert table.column('label').attributes['ui_hint'] == 'mounted default'
    assert table.column('id').attributes['ui_hint'] == 'explicit'
    assert isinstance(table.column('label'), DbColumnObj)
    assert source.source.get_node('db.schemas.sales.tables.customer.columns.label').attr.get('dtype') is None


def test_two_links_to_same_table_remain_distinct_and_collision_is_rejected():
    source, _, _ = recipe()
    invoice = source.source.get_node('db.packages.invc.tables.invoice')
    invoice.column('other_customer_id', dtype='L').relation('invc.customer.id', relation_name='other_invoices')
    model = source.render(mode='objects_tree')
    table = model.table('invc.invoice')
    assert table.column('@customer_id.id') is table.column('@other_customer_id.id')
    first = table.relations.get_node('@customer_id')
    second = table.relations.get_node('@other_customer_id')
    assert first.resolver is not second.resolver
    assert first.attr['joiner']['many_relation'] != second.attr['joiner']['many_relation']
    invoice.column('collision_id', dtype='L').relation('invc.customer.id', relation_name='invoices')
    with pytest.raises(ValueError, match='Duplicate|already used'):
        source.render(mode='objects_tree')


def test_defaults_and_explicit_relation_flags_are_distinguished():
    source, _, _ = recipe()
    invoice = source.source.get_node('db.packages.invc.tables.invoice')
    invoice.column('explicit_id', dtype='L').relation('invc.customer.id', deferred=False, one_one=False)
    model = source.render(mode='objects_tree')
    implicit = model.relations.get_node('invc.invoice.@customer_id').attr
    explicit = model.relations.get_node('invc.invoice.@explicit_id').attr
    assert 'deferred' not in implicit and 'one_one' not in implicit
    assert explicit['deferred'] is False and explicit['one_one'] is False
    assert implicit['onUpdate_sql'] == 'cascade'


def test_empty_table_containers_and_detached_operational_table_are_created():
    source = SqlDatabaseConfig()
    source.source.db().packages().package('app').table('empty')
    model = source.render(mode='objects_tree')
    table = model.table('app.empty')
    for name in ('columns', 'virtual_columns', 'indexes'):
        assert table[name].parent is table
        assert len(table[name]) == 0
    assert not hasattr(table, 'query')
    assert table.dbtable.model is table
    assert table.dbtable.columns is table.columns
    assert model._operational_db is None
    assert not hasattr(model.db, 'execute')
