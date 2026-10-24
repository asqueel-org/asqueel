import textwrap

import pytest

from asqueel import AsqueelDb, SqlDatabaseConfig
from asqueel.application_table import RecordMultipleRowsError, RecordNotFoundError
from asqueel.runtime import TransactionStateError
from tests.package_layout_support import write_layout


CUSTOMER = '''
class Table:
    def config_db(self, pkg):
        customer = pkg.table('customer', pkey='id')
        customer.column('id', dtype='I')
        customer.column('name')
        customer.column('state', sql_default="'new'")
        customer.formulaColumn('label', sql_formula='$name')
'''


def recipe(path, folder, customer_methods=''):
    source = SqlDatabaseConfig()
    db = source.source.db('handles', implementation='sqlite')
    db.connection(name=str(path), implementation='sqlite')
    methods = textwrap.indent(textwrap.dedent(customer_methods), '    ')
    pkg = db.packages().package('app', sqlprefix=True, path=write_layout(folder, customer=CUSTOMER + methods))
    invoice = pkg.table('invoice', pkey='id')
    invoice.column('id', dtype='I')
    invoice.column('customer_id', dtype='I').relation('app.customer.id')
    compound = pkg.table('compound', pkey='pk')
    compound.column('left', dtype='I', sqlname='L')
    compound.column('right')
    compound.compositeColumn('pk', columns='left,right')
    return source


DDL = (
    "CREATE TABLE app_customer (id INTEGER PRIMARY KEY, name TEXT, state TEXT DEFAULT 'new')",
    'CREATE TABLE app_invoice (id INTEGER PRIMARY KEY, customer_id INTEGER)',
    'CREATE TABLE app_compound ("L" INTEGER, "right" TEXT, PRIMARY KEY ("L", "right"))',
)


@pytest.fixture
def make_db(tmp_path):
    opened = []

    def make(customer_methods=''):
        source = recipe(tmp_path / f'handles{len(opened)}.db', tmp_path / f'app{len(opened)}', customer_methods)
        database = AsqueelDb(source)
        opened.append(database)
        for statement in DDL:
            database.execute(statement)
        database.commit()
        return database

    yield make
    for database in opened:
        database.rollback()
        database.closeConnection()


@pytest.fixture
def db(make_db):
    return make_db()


def test_composite_selector_requires_complete_keys_and_uses_named_physical_resolution(db):
    live = db.table('app.compound')
    with pytest.raises(KeyError, match='right'):
        live.update({'left': 0})
    db.rollback()
    db.execute("INSERT INTO app_compound (\"L\", \"right\") VALUES (0, 'x')")
    live.delete({'left': 0, 'right': 'x'})
    assert db.execute('SELECT * FROM app_compound').fetchall() == []


def test_composite_fetch_record_reads_through_the_physical_names(db):
    live = db.table('app.compound')
    db.execute("INSERT INTO app_compound (\"L\", \"right\") VALUES (0, 'x')")
    query = live.query(where="$left=0 AND $right='x'")
    assert query.fetchRecord()['left'] == 0
    assert '"t0"."L"' in query.sqltext


def test_update_record_and_delete_pkey_zero_keep_explicit_selectors(db):
    table = db.table('app.customer')
    db.execute("INSERT INTO app_customer (id, name) VALUES (0, 'Before'), (1, 'Sibling')")
    table.update({'id': 0, 'name': 'Zero'})
    assert [dict(row) for row in db.execute('SELECT id, name FROM app_customer ORDER BY id').fetchall()] == [
        {'id': 0, 'name': 'Zero'}, {'id': 1, 'name': 'Sibling'}]
    table.delete({'id': 0})
    assert [dict(row) for row in db.execute('SELECT id FROM app_customer').fetchall()] == [{'id': 1}]
    with pytest.raises(TypeError):
        table.delete()


def test_insert_hooks_share_session_and_failure_propagates_with_the_input_modified(make_db):
    db = make_db('''
        seen = []

        def trigger_onInserting(self, record):
            self.seen.append(('before', self.db._write_depth))
            record['name'] = 'Changed'

        def trigger_onInserted(self, record):
            self.seen.append(('after', self.db._write_depth, record['id']))
            self.db.table('app.invoice').insert({'id': 10, 'customer_id': record['id']})
            raise RuntimeError('hook failed')
    ''')
    seen = db.table('app.customer').seen
    values = {'name': 'Original'}
    with pytest.raises(RuntimeError, match='hook failed'):
        db.table('app.customer').insert(values)
    assert values['name'] == 'Changed' and values['id'] == 1
    assert seen == [('before', 1), ('after', 1, 1)]
    assert db._write_depth == 0
    with pytest.raises(TransactionStateError, match='rollback-only'):
        db.commit()


def test_update_hooks_receive_the_callers_old_record_and_values(make_db):
    db = make_db('''
        seen = []

        def trigger_onUpdating(self, record, old_record=None):
            self.seen.append(('before', old_record))
            record['name'] = record['name'].upper()

        def trigger_onUpdated(self, record, old_record=None):
            self.seen.append(('after', old_record))
    ''')
    seen = db.table('app.customer').seen
    db.execute("INSERT INTO app_customer (id, name) VALUES (0, 'old')")
    old_record = {'id': 0, 'name': 'old'}
    values = {'id': 0, 'name': 'new'}
    assert db.table('app.customer').update(values, old_record=old_record) is values
    assert values == {'id': 0, 'name': 'NEW'}
    assert seen == [('before', old_record), ('after', old_record)]
    assert seen[0][1] is old_record and seen[1][1] is old_record
    assert db.table('app.customer').query(where='$id=0').fetchRecord()['name'] == 'NEW'


@pytest.mark.parametrize('keys', [(), (0, 0)])
def test_hooked_delete_of_a_key_rereads_it_before_hooks(make_db, keys):
    db = make_db('''
        def trigger_onDeleting(self, record):
            raise AssertionError('must not run')
    ''')
    db.execute('DROP TABLE app_customer')
    db.execute('CREATE TABLE app_customer (id INTEGER, name TEXT, state TEXT)')
    for key in keys:
        db.execute('INSERT INTO app_customer (id, name) VALUES (:id, :name)', {'id': key, 'name': 'a'})
    if not keys:
        assert db.table('app.customer').delete('0') is None
        return
    with pytest.raises(RecordMultipleRowsError):
        db.table('app.customer').delete('0')


def test_delete_of_a_missing_row_fails_before_the_after_hook(make_db):
    db = make_db('''
        def trigger_onDeleted(self, record):
            raise AssertionError('after hook must not run')
    ''')
    with pytest.raises(RecordNotFoundError, match='instead of 1'):
        db.table('app.customer').delete({'id': 0, 'name': 'old', 'state': 'new'})
    with pytest.raises(TransactionStateError, match='rollback-only'):
        db.commit()


def test_post_insert_hook_sees_the_columns_the_database_decides(make_db):
    db = make_db('''
        seen = []

        def trigger_onInserted(self, record):
            self.seen.append(dict(record))
    ''')
    seen = db.table('app.customer').seen
    values = {'id': 7, 'name': 'Original'}
    assert db.table('app.customer').insert(values) is values
    assert seen == [{'id': 7, 'name': 'Original', 'state': 'new'}]


def test_post_insert_hook_does_not_treat_computed_alias_as_a_record_field(make_db):
    db = make_db('''
        seen = []

        def trigger_onInserted(self, record):
            self.seen.append(dict(record))
    ''')
    seen = db.table('app.customer').seen
    db.table('app.customer').insert({'name': 'Original'})
    assert seen == [{'name': 'Original', 'id': 1, 'state': 'new'}]


def test_poisoned_application_session_rejects_insert_before_running_hooks(make_db):
    db = make_db('''
        seen = []

        def trigger_onInserting(self, record):
            self.seen.append(dict(record))
    ''')
    seen = db.table('app.customer').seen
    db._mark_connection_failed(db._connection_state)
    with pytest.raises(TransactionStateError, match='rollback-only'):
        db.table('app.customer').insert({'id': 1})
    assert seen == []
