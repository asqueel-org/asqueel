import pytest

from asqueel import SqlDatabase, SqlDatabaseConfig, SqlTable
from asqueel.application_table import RecordMultipleRowsError, RecordNotFoundError
from asqueel.configuration import _owned_handler
from asqueel.runtime import TransactionStateError


def recipe(path, customer_class=None):
    source = SqlDatabaseConfig()
    db = source.source.db('handles', implementation='sqlite')
    db.connection(name=str(path), implementation='sqlite')
    pkg = db.packages().package('app', sqlprefix=True)
    options = {'x_table_class': customer_class} if customer_class else {}
    customer = pkg.table('customer', pkey='id', **options)
    customer.column('id', dtype='I')
    customer.column('name')
    customer.column('state', sqldefault="'new'")
    customer.formulaColumn('label', sql_formula='$name')
    invoice = pkg.table('invoice', pkey='id')
    invoice.column('id', dtype='I')
    invoice.column('customer_id', dtype='I').relation('app.customer.id')
    compound = pkg.table('compound', pkey='pk')
    compound.column('left', dtype='I', x_sql_name='L')
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

    def make(customer_class=None):
        source = recipe(tmp_path / f'handles{len(opened)}.db', customer_class)
        database = SqlDatabase(model=source.render(mode='objects_tree'), config=_owned_handler(source))
        opened.append(database)
        for statement in DDL:
            database.execute(statement)
        database.commit()
        return database

    yield make
    for database in opened:
        database.rollback()
        database.close()


@pytest.fixture
def db(make_db):
    return make_db()


def test_composite_selector_requires_complete_keys_and_uses_named_physical_resolution(db):
    live = db.table('app.compound')
    with pytest.raises(ValueError, match='Incomplete primary key'):
        live.record({'left': 0})
    with pytest.raises(KeyError, match='right'):
        live.update({'left': 0})
    db.rollback()
    db.execute("INSERT INTO app_compound (\"L\", \"right\") VALUES (0, 'x')")
    live.delete({'left': 0, 'right': 'x'})
    assert db.execute('SELECT * FROM app_compound').rows == []


@pytest.mark.xfail(strict=True, reason='issue draft 10: a SELECT on a table whose pkey is a compositeColumn '
                                       'fails, composite columns are not connected in the read compiler')
def test_composite_record_reads_through_the_physical_names(db):  # wf:phase-2:new
    live = db.table('app.compound')
    db.execute("INSERT INTO app_compound (\"L\", \"right\") VALUES (0, 'x')")
    assert live.record({'left': 0, 'right': 'x'}, mode='dict')['left'] == 0
    assert '"t0"."L"' in live.record({'left': 0, 'right': 'x'}).query.sqltext


def test_update_record_and_delete_pkey_zero_keep_explicit_selectors(db):
    table = db.table('app.customer')
    db.execute("INSERT INTO app_customer (id, name) VALUES (0, 'Before'), (1, 'Sibling')")
    table.update({'id': 0, 'name': 'Zero'})
    assert [dict(row) for row in db.execute('SELECT id, name FROM app_customer ORDER BY id').rows] == [
        {'id': 0, 'name': 'Zero'}, {'id': 1, 'name': 'Sibling'}]
    table.delete({'id': 0})
    assert [dict(row) for row in db.execute('SELECT id FROM app_customer').rows] == [{'id': 1}]
    with pytest.raises(TypeError):
        table.delete()


def test_insert_hooks_share_session_and_failure_propagates_with_the_input_modified(make_db):
    seen = []

    class Customer(SqlTable):
        def trigger_onInserting(self, record):
            seen.append(('before', self.db._write_depth))
            record['name'] = 'Changed'

        def trigger_onInserted(self, record):
            seen.append(('after', self.db._write_depth, record['id']))
            self.db.table('app.invoice').insert({'id': 10, 'customer_id': record['id']})
            raise RuntimeError('hook failed')

    db = make_db(Customer)
    values = {'name': 'Original'}
    with pytest.raises(RuntimeError, match='hook failed'):
        db.table('app.customer').insert(values)
    assert values['name'] == 'Changed' and values['id'] == 1
    assert seen == [('before', 1), ('after', 1, 1)]
    assert db._write_depth == 0
    with pytest.raises(TransactionStateError, match='rollback-only'):
        db.commit()


def test_update_hooks_receive_the_callers_old_record_and_values(make_db):
    seen = []

    class Customer(SqlTable):
        def trigger_onUpdating(self, record, old_record=None):
            seen.append(('before', old_record))
            record['name'] = record['name'].upper()

        def trigger_onUpdated(self, record, old_record=None):
            seen.append(('after', old_record))

    db = make_db(Customer)
    db.execute("INSERT INTO app_customer (id, name) VALUES (0, 'old')")
    old_record = {'id': 0, 'name': 'old'}
    values = {'id': 0, 'name': 'new'}
    assert db.table('app.customer').update(values, old_record=old_record) is values
    assert values == {'id': 0, 'name': 'NEW'}
    assert seen == [('before', old_record), ('after', old_record)]
    assert seen[0][1] is old_record and seen[1][1] is old_record
    assert db.table('app.customer').record(0).output('dict')['name'] == 'NEW'


@pytest.mark.parametrize('keys, error', [((), RecordNotFoundError), ((0, 0), RecordMultipleRowsError)])
def test_hooked_delete_rejects_missing_or_multiple_records_before_hooks(make_db, keys, error):
    class Customer(SqlTable):
        def trigger_onDeleting(self, record):
            raise AssertionError('must not run')

    db = make_db(Customer)
    db.execute('DROP TABLE app_customer')
    db.execute('CREATE TABLE app_customer (id INTEGER, name TEXT, state TEXT)')
    for key in keys:
        db.execute('INSERT INTO app_customer (id, name) VALUES (:id, :name)', {'id': key, 'name': 'a'})
    with pytest.raises(error):
        db.table('app.customer').delete({'id': 0})


def test_delete_of_a_missing_row_fails_before_the_after_hook(make_db):
    class Customer(SqlTable):
        def trigger_onDeleted(self, record):
            raise AssertionError('after hook must not run')

    db = make_db(Customer)
    with pytest.raises(RecordNotFoundError, match='instead of 1'):
        db.table('app.customer').delete({'id': 0, 'name': 'old', 'state': 'new'})
    with pytest.raises(TransactionStateError, match='rollback-only'):
        db.commit()


def test_post_insert_hook_sees_the_columns_the_database_decides(make_db):
    seen = []

    class Customer(SqlTable):
        def trigger_onInserted(self, record):
            seen.append(dict(record))

    db = make_db(Customer)
    values = {'id': 7, 'name': 'Original'}
    assert db.table('app.customer').insert(values) is values
    assert seen == [{'id': 7, 'name': 'Original', 'state': 'new'}]


def test_post_insert_hook_does_not_treat_computed_alias_as_a_record_field(make_db):
    seen = []

    class Customer(SqlTable):
        def trigger_onInserted(self, record):
            seen.append(dict(record))

    db = make_db(Customer)
    db.table('app.customer').insert({'name': 'Original'})
    assert seen == [{'name': 'Original', 'id': 1, 'state': 'new'}]


def test_poisoned_application_session_rejects_insert_before_running_hooks(make_db):
    seen = []

    class Customer(SqlTable):
        def trigger_onInserting(self, record):
            seen.append(dict(record))

    db = make_db(Customer)
    db._mark_connection_failed(db._connection_state)
    with pytest.raises(TransactionStateError, match='rollback-only'):
        db.table('app.customer').insert({'id': 1})
    assert seen == []
