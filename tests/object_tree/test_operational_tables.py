"""Legacy table/model identities, without adapting or invoking the compiler."""
import pytest

from asqueel import SqlDatabase, SqlTable, UnsupportedFeatureError
from asqueel.configuration import _owned_handler
from asqueel.errors import DatabaseClosedError
from asqueel.object_tree import DbTableObj
from examples.test_invoice_pg import source as invoice_source
from tests.application_config.test_render_structure import recipe
from tests.object_tree.test_invoice import TABLES


@pytest.fixture(scope='module', autouse=True)
def no_connections():
    def denied(*args, **kwargs):
        pytest.fail('Object binding must not connect or execute SQL')
    with pytest.MonkeyPatch.context() as patch:
        patch.setattr('sqlite3.connect', denied)
        patch.setattr('psycopg.connect', denied)
        patch.setattr(SqlDatabase, 'execute', denied)
        yield


def bind(source, **kwargs):
    config = _owned_handler(source)
    model = source.render(mode='objects_tree')
    return SqlDatabase(model=model, config=config, **kwargs)


def test_creation_precedes_children_and_does_not_load_relations(monkeypatch):
    original = SqlTable.__init__
    seen = []
    def init(self, db, model):
        if isinstance(model, DbTableObj):
            assert model.children == {}
            assert model._model.relations.keys() == []
            seen.append(model.fullname)
        original(self, db, model)
    monkeypatch.setattr(SqlTable, '__init__', init)
    source, _, _ = recipe()
    model = source.render(mode='objects_tree')
    assert set(seen) == set(model.tables)
    for table in model.tables.values():
        assert table.dbtable.model is table
        assert table._relation_tree is None
        with pytest.raises(UnsupportedFeatureError, match='not bound'):
            table.dbtable.query()


def test_binding_reuses_table_column_and_relation_objects(monkeypatch):
    source, _, customer = recipe()
    customer.aliasColumn('copied_id', relation_path='id')
    customer.formulaColumn('double_id', sql_formula='$id * 2', dtype='L')
    customer.options().audit(mode='lazy')
    config = _owned_handler(source)
    model = source.render(mode='objects_tree')
    structural = model.table('invc.customer')
    table = structural.dbtable
    relations = table.relations
    def denied(*args, **kwargs):
        pytest.fail('Binding must not build a compiler or reconstruct tables')
    monkeypatch.setattr('asqueel.application.QueryCompiler', denied)
    monkeypatch.setattr(SqlTable, '__init__', denied)
    db = SqlDatabase(model=model, config=config)
    try:
        assert db.table('invc.customer') is db.tables['invc.customer'] is table
        assert table.model is db.model.table('invc.customer') is structural
        assert model.db is db
        assert table.db is structural.db is table.column('id').db is db
        assert table.pkg is db.package('invc')
        assert table.columns is structural.columns
        assert table.virtual_columns is structural.virtual_columns
        assert table.options is structural.options
        assert table.relations is relations is structural.relations
        assert table.column('id') is structural.column('id')
        assert table.column('double_id') is structural.virtual_columns['double_id']
        assert table.column('copied_id').originalColumn is structural.column('id')
        assert db.table('invc.invoice').column('@customer_id.id') is table.column('id')
        assert table.column('@invoices.id') is db.table('invc.invoice').column('id')
        assert table.getAttr.__self__ is structural
        assert table.trigger_onInserting.__self__ is table
        assert db._connection_settings()[1]['schemas'] == ['main']
        assert db._connections == {}
    finally:
        db.close()
    with pytest.raises(DatabaseClosedError):
        table.query()


def test_binding_is_single_owner_and_failure_does_not_rebind():
    source, _, _ = recipe()
    db = bind(source)
    table = db.table('invc.customer')
    try:
        with pytest.raises(ValueError, match='already bound'):
            SqlDatabase(model=db.model, config=db.config)
        assert table.db is db
        assert table.model.dbtable is table
    finally:
        db.close()


def test_bad_implementation_leaves_tree_unbound():
    source, _, _ = recipe()
    model = source.render(mode='objects_tree')
    config = _owned_handler(source)
    implementation = model.implementation
    config.builder.source.get_node(config.root_label).attr['implementation'] = 'unsupported'
    model.implementation = 'unsupported'
    with pytest.raises(ModuleNotFoundError, match='asqueel.adapters.unsupported'):
        SqlDatabase(model=model, config=config)
    assert model._operational_db is None
    config.builder.source.get_node(config.root_label).attr['implementation'] = implementation
    model.implementation = implementation
    db = SqlDatabase(model=model, config=config)
    db.close()


def test_query_compiles_without_execution_or_writes():
    source, _, _ = recipe()
    db = bind(source)
    try:
        table = db.table('invc.customer')
        query = table.query(columns='$id', where='$id = :id', id=3)
        assert query.table is table
        assert query.db is db
        compiled = query.compiled
        assert compiled.params == {'id': 3}
        assert 'SELECT' in compiled.sql
        record = table.record(pkey=3)
        assert record.query.compiled.params == {'__record_key_0': 3}
        assert db._connections == {}
    finally:
        db.close()


def test_default_renderer_uses_the_same_hierarchy():
    source, _, _ = recipe()
    tree_db = bind(source)
    old_db = source.render()
    try:
        assert source._default_render_mode == 'objects'
        old = old_db.table('invc.customer')
        new = tree_db.table('invc.customer')
        assert old is not new
        assert old.model is not new.model
        assert old.column('id') is old.model.columns['id']
        assert type(old.model) is type(new.model)
        assert new.column('id') is new.model.columns['id']
        assert old.query(columns='$id').compiled.sql
    finally:
        old_db.close()
        tree_db.close()


@pytest.fixture(scope='module')
def invoice_db():
    db = bind(invoice_source())
    yield db
    db.close()


@pytest.mark.parametrize('key', TABLES)
def test_all_native_tables_keep_legacy_identity_contract(invoice_db, key):
    db = invoice_db
    table = db.table(key)
    model = db.model.table(key)
    assert isinstance(table, SqlTable)
    assert table is model.dbtable is db.tables[key]
    assert table.model is model
    assert table.db is model.db is db
    assert table.pkg is db.package(key.split('.')[0])
    assert table.columns is model.columns
    assert table.virtual_columns is model.virtual_columns
    assert table.relations is model.relations
    assert table.indexes is model.indexes
    if model.get('options') is None:
        assert table.options == model.options == {}
    else:
        assert table.options is model.options
    for name in table.columns:
        assert table.column(name) is model.column(name)
