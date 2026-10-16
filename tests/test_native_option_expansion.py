"""Native declarations compared with independently captured legacy output.

The XML is used only for expectations, never to construct the native source.
Additional variants cite gnrdbo.sysFields helpers and run without GenroPy.
"""
from pathlib import Path
import runpy

import pytest
from genro_bag import Bag
from genro_bag.resolvers import EnvResolver

from asqueel import SqlDatabaseConfig, SqlMigrationRenderer
from asqueel.configuration import build_database
from asqueel.model import resolve_model
from asqueel.projection import to_physical_builder
from asqueel.model_codec import model_from_json, model_to_json
from asqueel.contracts import UnsupportedFeatureError

ORACLE = Path(__file__).parent / 'oracles/test_invoice_pg/source.xml'
BASE_PHYSICAL = {'id', '__ins_ts', '__mod_ts', '__del_ts', '__ins_user'}
BASE_VIRTUAL = {'__record_pointer', '__protecting_reasons', '__is_protected_row',
                '__invalid_reasons', '__is_invalid_row'}


def source():
    builder = SqlDatabaseConfig()
    db = builder.source.db('options')
    return builder, db.packages()


def legacy_table(key):
    pkg, name = key.split('.')
    return Bag(ORACLE.read_text()).get_node(f'packages.{pkg}.tables.{name}')


def assert_legacy_columns(table, names, key):
    legacy = legacy_table(key)
    for name in names:
        column = table.column(name)
        collection = 'columns' if name in table.columns else 'virtual_columns'
        attrs = dict(legacy.value.get_node(f'{collection}.{name}').attr)
        dtype = attrs.get('dtype') or ('A' if attrs.get('size') else 'T')
        assert column.dtype == dtype, (key, name, 'dtype')
        for field in ('size', 'name_long', 'group', 'unique', 'indexed', 'select', 'sql_formula'):
            if field in attrs:
                expected = str(attrs[field]) if field == 'size' else attrs[field]
                assert column.attributes.get(field) == expected, (key, name, field)
        for field in ('onInserting', 'onUpdating', '_sysfield', '_sendback', 'counter', '_counter_fkey'):
            assert column.attributes.get('x_legacy_' + field) == attrs.get(field), (key, name, field)


@pytest.mark.parametrize('key,fields,counter,dynamic,audit', [
    ('invc.product_type', ['description'], True, True, False),
    ('invc.product_group', ['code', '_row_count'], True, False, False),
    ('sys.widget', ['name'], False, True, True),
    ('adm.htag', ['code', 'description'], True, False, False),
    ('adm.menu', ['label'], True, False, False),
])
def test_hierarchy_families_match_independent_legacy(key, fields, counter, dynamic, audit):
    builder, packages = source()
    pkg, name = key.split('.')
    table = packages.package(pkg).table(name)
    opts = table.options()
    opts.sys_fields(user_upd=False, group_name='!![en]System', syscode=name == 'htag')
    opts.hierarchical(fields)
    if counter:
        opts.auto_counter()
    if dynamic:
        opts.dynamic_fields()
    if audit:
        opts.audit('lazy')
    for field in fields:
        if field != '_row_count':
            table.column(field, name_long='!!' + field.title())
    raw = builder.source.to_json()
    model = resolve_model(builder)
    assert builder.source.to_json() == raw
    assert physical(resolve_model(builder)) == physical(model)
    resolved = model.table(key)
    names = BASE_PHYSICAL | BASE_VIRTUAL | {'parent_id', 'hierarchical_pkey', '_parent_h_pkey', 'child_count', 'hlevel'}
    for field in fields:
        names |= {'hierarchical_' + field, '_parent_h_' + field}
    if counter:
        names |= {'_row_count', '_h_count', '_parent_h_count', '_h_sortcol'}
    if dynamic:
        names |= {'df_fields', 'df_fbcolumns', 'df_custom_templates', 'df_colswidth'}
    if audit:
        names |= {'__version'}
    if name == 'htag':
        names |= {'__syscode'}
        assert '__protected_by_syscode' not in resolved.columns
    assert_legacy_columns(resolved, names, key)
    assert set(resolved.columns) | set(resolved.virtual_columns) == names | set(fields)
    assert resolved.column('@parent_id.id').table.fullname == key
    assert resolved.column('@_children.id').table.fullname == key
    assert resolved.relations.get_node('@parent_id').attr['joiner']['deferred'] is True
    assert resolved.attributes['group_zzz'] == '!![en]System'
    assert resolved.attributes['x_legacy_logicalDeletionField'] == '__del_ts'
    assert resolved.attributes['x_legacy_lastTS'] == '__mod_ts'
    assert resolved.attributes['order_by'] == ('$_h_sortcol' if counter else '$hierarchical_' + fields[0])
    assert physical(resolve_model(builder)) == physical(model)


@pytest.mark.parametrize('reverse', [False, True])
def test_attachments_expand_base_options_before_cross_table_link(reverse):
    builder, packages = source()
    pkg = packages.package('adm')
    for name in (['htmltemplate_atc', 'htmltemplate'] if reverse else ['htmltemplate', 'htmltemplate_atc']):
        table = pkg.table(name)
        if name == 'htmltemplate':
            table.attr['name_long'] = '!!Letterhead'
            table.options().sys_fields(user_upd=False)
        else:
            table.options().sys_fields(user_upd=False, group_name='!![en]System')
            table.options().attachments(master='adm.htmltemplate')
    db = build_database(builder)
    try:
        attachment = db.table('adm.htmltemplate_atc')
        expected = legacy_table('adm.htmltemplate_atc')
        names = {node.label for collection in ('columns', 'virtual_columns') for node in expected.value.get_item(collection)}
        assert set(attachment.columns) | set(attachment.virtual_columns) == names
        # Structural defaults are still present despite earlier signature defaults.
        assert_legacy_columns(attachment.model, names - {'maintable_id', 'fileurl', 'full_external_url'}, 'adm.htmltemplate_atc')
        assert attachment.model['options']['auto_counter'].attributes['scope'] == 'maintable_id'
        assert attachment.column('@maintable_id.id') is db.table('adm.htmltemplate').column('id')
        assert attachment.relations.get_node('@maintable_id').attr['joiner']['onDuplicate'] is False
        assert db.table('adm.htmltemplate').attributes['atc_attachmenttable'] == 'adm.htmltemplate_atc'
        assert attachment.column('fileurl').attributes['method'] == 'filepath_endpoint_url'
        assert attachment.column('__ins_ts').attributes['indexed'] is True
    finally:
        db.close()


def test_attachment_implicit_options_are_owned_and_default_user_upd_is_preserved():
    builder, packages = source()
    pkg = packages.package('adm')
    pkg.table('master').options().sys_fields()
    attachment = pkg.table('master_atc')
    attachment.options().attachments(master='adm.master')
    before = builder.source.to_json()
    model = resolve_model(builder)
    assert '__mod_user' in model.table('adm.master_atc').columns  # approved Asqueel default
    assert model.table('adm.master_atc')['options']['sys_fields'].attributes['enabled']
    assert builder.source.to_json() == before


def test_counter_audit_hash_full_update_and_dynamic_column_are_structure_only():
    builder, packages = source()
    pkg = packages.package('app')
    table = pkg.table('item', pkey='code')
    table.column('code', dtype='L')
    table.column('parent_id', dtype='L')
    table.column('details', dtype='X').dynamic_fields(source='parent_id')
    opts = table.options()
    opts.sys_fields(id=False)
    opts.auto_counter('parent_id')
    opts.audit('lazy')
    opts.full_update()
    opts.record_hash()
    opts.dynamic_fields(templates='compact')
    model = resolve_model(builder).table('app.item')
    assert model.columns['__version'].dtype == 'L'
    assert model.columns['__full_mod_ts'].dtype == 'DHZ'
    assert model.columns['__full_mod_ts'].attributes['indexed'] is True
    assert model.columns['__rec_md5'].dtype == 'T'
    assert model.columns['_row_count'].attributes['x_legacy__counter_fkey'] == 'parent_id'
    assert model.columns['details'].attributes['x_legacy_subfields'] == 'parent_id'
    assert model.columns['details']['dynamic_fields'].attributes['source'] == 'parent_id'
    assert model.columns['df_custom_templates'].attributes['x_legacy_templates'] == 'compact'
    assert model.virtual_columns['__record_pointer'].attributes['sql_formula'] == " 'app.item.' || $code "
    assert 'id' not in model.columns


def test_record_hash_matches_user_legacy_declaration():
    builder, packages = source()
    table = packages.package('adm').table('user')
    table.options().sys_fields(user_upd=False, group_name='!![en]System')
    table.options().record_hash()
    assert_legacy_columns(resolve_model(builder).table('adm.user'), {'__rec_md5'}, 'adm.user')


def test_declarative_options_are_preserved_without_new_columns_or_runtime_effects(monkeypatch):
    monkeypatch.setenv('INVC_STATE', 'MI')
    builder, packages = source()
    table = packages.package('invc').table('customer', pkey='id')
    table.column('id', dtype='L')
    table.column('state')
    opts = table.options()
    opts.partition('state', field='state', value=EnvResolver('INVC_STATE'))
    opts.tenant()
    opts.retention(field='id', days=60)
    opts.broadcast('state')
    opts.archive()
    opts.enabled_when(preference='adm.dev.connection_log_enabled')
    opts.numbering('id', parameters={'format': '$YYYY$NNNNN', 'starting_value': 1})
    opts.protection(rules=['protect_validate'])
    db = build_database(builder)
    try:
        item = db.table('invc.customer')
        assert set(item.columns) == {'id', 'state'}
        assert set(item.model.options) == {'partition_state', 'tenant', 'retention', 'broadcast', 'archive', 'enabled_when', 'numbering_id', 'protection'}
        assert item.model.options['partition_state'].attributes['value'] == 'MI'
        assert item.model.options['protection'].attributes['rules'] == ['protect_validate']
        assert item.model.options['numbering_id'].attributes['parameters']['format'] == '$YYYY$NNNNN'
        assert item.model.options['retention'].attributes['days'] == 60
        with pytest.raises(UnsupportedFeatureError):
            item.insert({'id': 1})
    finally:
        db.close()


@pytest.mark.xfail(strict=True, reason='issue draft 2: the hierarchical DbModel has no JSON round trip')
def test_declarative_options_survive_a_json_round_trip():  # wf:phase-2:new
    builder, packages = source()
    table = packages.package('invc').table('customer', pkey='id')
    table.column('id', dtype='L')
    table.options().retention(field='id', days=60)
    db = build_database(builder)
    try:
        assert model_from_json(model_to_json(db.model)) == db.model
    finally:
        db.close()


@pytest.mark.parametrize('name,kwargs', [
    ('hierarchical', {}), ('auto_counter', {}), ('relative_index', {}),
    ('dynamic_fields', {}), ('record_hash', {}), ('full_update', {}), ('audit', {}),
    ('attachments', {}), ('protection', {}), ('release', {}), ('system_records', {}),
])
def test_disabled_options_remain_data_and_generate_nothing(name, kwargs):
    builder, packages = source()
    table = packages.package('app').table('item')
    table.column('explicit', dtype='L')
    getattr(table.options(), name)(enabled=False, **kwargs)
    resolved = resolve_model(builder).table('app.item')
    assert set(resolved.columns) == {'explicit'}
    assert resolved['options'][name].attributes['enabled'] is False


@pytest.mark.parametrize('reverse', [False, True])
@pytest.mark.parametrize('qualified', [False, True])
def test_relative_index_contributes_to_existing_master_extension(reverse, qualified):
    builder, packages = source()
    pkg = packages.package('app')
    for name in (['detail', 'master_xtd', 'master'] if reverse else ['master', 'master_xtd', 'detail']):
        tbl = pkg.table(name, pkey='id', name_long=name)
        tbl.column('id', dtype='L')
        if name == 'detail':
            tbl.column('master_id', dtype='L').relation('app.master.id' if qualified else 'master.id')
            tbl.options().relative_index('master_id')
    model = resolve_model(builder)
    assert model.table('app.detail').columns['_relidx'].dtype == 'L'
    assert model.table('app.master_xtd').columns['app_detail_relidx'].dtype == 'L'
    assert model.table('app.detail').columns['_relidx'].attributes['x_legacy_format'] == '0000'


def test_native_invoice_example_builds_live_objects_with_its_targets(monkeypatch):
    example = Path(__file__).resolve().parents[1] / 'examples/model_grammar/configure.py'
    monkeypatch.setenv('INVC_STATE', 'IT')
    config = runpy.run_path(str(example))['source']()
    # The grammar example is deliberately partial. Supply only the target
    # columns it uses, with types from invc/model/{state,product}.py.
    invc = config.source.get_node('db.packages.invc')
    invc.table('state', pkey='code').column('code', size=':5')
    product = invc.table('product', pkey='id')
    product.options().sys_fields(user_upd=False)
    product.column('description', size=':80')
    before = config.source.to_json()
    db = build_database(config)
    try:
        assert len(db.model.tables) == 10
        assert db.table('adm.htmltemplate_atc').column('@maintable_id.id') is db.table('adm.htmltemplate').column('id')
        assert db.table('invc.invoice_row').column('@invoice_id.id') is db.table('invc.invoice').column('id')
        assert db.table('invc.product_type').column('hierarchical_description').dtype == 'T'
        assert config.source.to_json() == before
    finally:
        db.close()


def test_linked_hierarchy_and_legacy_variants():
    builder, packages = source()
    pkg = packages.package('app')
    tree = pkg.table('tree', name_long='Tree')
    tree.options().sys_fields()
    tree.options().hierarchical([{'name': 'code', 'unique': True}], root_id=True, virtual_roots=True,
                                linked_to='app.master', depth=3, caption_field='hierarchical_code')
    tree.column('code')
    master = pkg.table('master', name_long='Master')
    master.options().sys_fields()
    model = resolve_model(builder)
    tree = model.table('app.tree')
    assert tree.columns['hierarchical_code'].attributes['unique'] is True
    assert tree.columns['hierarchical_code'].attributes['x_legacy_variant_hdepth_levels'] == 3
    assert tree.columns['_virtual_node'].dtype == 'B'
    assert tree.column('@master_id.id').table.fullname == 'app.master'
    assert model.table('app.master').column('@root_tree_id.id').table.fullname == 'app.tree'
    assert model.table('app.master').relations.get_node('@root_tree_id').attr['joiner']['deferred'] is True
    assert tree.column('@root_id.id').table.fullname == 'app.tree'


def test_protection_tag_preserves_the_legacy_formula_without_execution():
    builder, packages = source()
    table = packages.package('app').table('item')
    table.options().protection(tag='staff')
    resolved = resolve_model(builder).table('app.item')
    assert set(resolved.columns) | set(resolved.virtual_columns) == {'__protection_tag', '__protected_by_tag'}
    assert resolved.virtual_columns['__protected_by_tag'].dtype == 'B'
    assert ':env_userTags' in resolved.virtual_columns['__protected_by_tag'].attributes['sql_formula']
    assert resolved['options']['protection'].attributes['tag'] == 'staff'


@pytest.mark.parametrize('kind', ['column', 'virtual', 'unknown', 'counter_scope'])
def test_structural_conflicts_fail_without_modifying_source(kind):
    builder, packages = source()
    table = packages.package('app').table('item')
    table.options().sys_fields()
    if kind == 'column':
        table.column('__mod_ts', dtype='I')
    elif kind == 'virtual':
        table.column('__invalid_reasons')
    elif kind == 'unknown':
        table.options().hierarchical('missing')
    else:
        table.options().hierarchical()
        table.options().auto_counter('another_id')
    before = builder.source.to_json()
    with pytest.raises(ValueError):
        build_database(builder)
    assert builder.source.to_json() == before


def test_sysfield_generation_does_not_treat_signature_defaults_as_explicit_overrides():
    builder, packages = source()
    table = packages.package('app').table('item')
    table.column('__syscode', name_long='Code')
    table.column('__ins_ts', name_long='Created')
    table.options().sys_fields(syscode=True)
    db = build_database(builder)
    try:
        assert db.table('app.item').column('__syscode').attributes['unique'] is True
        assert db.table('app.item').column('__syscode').attributes['name_long'] == 'Code'
        assert db.table('app.item').column('__ins_ts').attributes['indexed'] is True
    finally:
        db.close()


@pytest.mark.parametrize('name,kwargs', [('system_records', {'records': {'x': {}}}), ('release', {'handlers': {'1': 'upgrade'}})])
def test_deferred_families_stay_out_of_object_creation(name, kwargs):
    builder, packages = source()
    getattr(packages.package('app').table('item').options(), name)(**kwargs)
    with pytest.raises(UnsupportedFeatureError, match='deferred'):
        resolve_model(builder)


def test_option_columns_indexes_and_foreign_keys_reach_physical_projection():
    builder, packages = source()
    pkg = packages.package('app')
    pkg.table('master').options().sys_fields()
    pkg.table('master_atc').options().attachments(master='app.master')
    table = SqlMigrationRenderer(builder).render()['root']['schemas']['public']['tables']['app_master_atc']
    assert '_row_count' in table['columns']
    assert 'info' in table['columns']
    assert 'adapted_url' not in table['columns']
    assert '__protecting_reasons' not in table['columns']
    assert any(r['attributes'].get('on_delete') == 'CASCADE' for r in table['relations'].values())
    assert table['indexes']


@pytest.mark.parametrize('objects', [False, True])
def test_package_types_precede_expansion_and_legacy_setnull_defaults(objects):
    builder, packages = source()
    pkg = packages.package('app')
    pkg.options().type('uuid', dtype='A', size='22')
    master = pkg.table('master')
    master.column('id', dtype='uuid')
    master.options().sys_fields()
    detail = pkg.table('detail', pkey='id')
    detail.column('id', dtype='L')
    detail.column('master_id').relation('app.master.id', on_delete='set_null', on_duplicate='recursive')
    detail.column('other_id').relation('app.master.id', on_delete='set_null', deferred=False)
    db = build_database(builder) if objects else None
    try:
        model = db.model if db is not None else resolve_model(builder)
        assert model.table('app.master').columns['id'].attributes['size'] == '22'
        relation = model.table('app.detail').relations.get_node('@master_id').attr['joiner']
        assert relation['deferred'] is True
        assert relation['onDuplicate'] == 'recursive'
        assert model.table('app.detail').relations.get_node('@other_id').attr['joiner']['deferred'] is False
    finally:
        if db is not None:
            db.close()


def test_expanding_options_does_not_connect_or_run_declared_hooks(monkeypatch):
    import psycopg
    def forbidden(*a, **k):
        pytest.fail('Object expansion must not connect')
    monkeypatch.setattr(psycopg, 'connect', forbidden)
    builder, packages = source()
    table = packages.package('app').table('item')
    table.options().sys_fields()
    table.options().audit('full')
    table.options().record_hash()
    db = build_database(builder)
    try:
        assert db.table('app.item').column('__rec_md5').attributes['x_legacy_onInserting'] == 'setRecordMd5'
        assert db.table('app.item').model['options']['audit'].attributes['mode'] == 'full'
    finally:
        db.close()


def physical(model):
    return SqlMigrationRenderer(to_physical_builder(model)).render()
