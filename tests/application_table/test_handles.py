from asqueel.writes import WriteMixin
from contextlib import contextmanager
from copy import deepcopy

import pytest

from asqueel.application_table import (
    RecordMultipleRowsError, RecordNotFoundError, SqlTable,
)
from asqueel.compiler import PostgresCompiler
from asqueel.contracts import Column, QueryResult, Relation, ResolvedModel, Table
from asqueel.environment import SqlEnvironment


class Config:
    def __init__(self):
        self.values = {}

    def __call__(self, path, default=None):
        return self.values.get(path, default)


class Application(WriteMixin):
    def __init__(self, model):
        self.model = model
        self.environment = SqlEnvironment()
        self.compiler = PostgresCompiler(model, environment=self.environment)
        self.config = Config()
        self.closed = False
        self.handles = {}
        self.table_classes = {}
        self.executions = []
        self.results = []
        self.depth = 0
        self.failed = False

    def _check_open(self):
        if self.closed:
            raise RuntimeError('closed')

    def table(self, name):
        self._check_open()
        model = self.model.table(name)
        if model.key not in self.handles:
            self.handles[model.key] = self.table_classes.get(model.key, SqlTable)(self, model)
        return self.handles[model.key]

    def execute(self, query):
        self._check_open()
        if query.environment:
            query.environment.validate(self.environment.snapshot())
        self.executions.append(query)
        rows = self.results.pop(0) if self.results else []
        return QueryResult(deepcopy(rows), len(rows), query.columns)

    @contextmanager
    def _write_operation(self):
        self._check_open()
        self.depth += 1
        try:
            yield
        except BaseException:
            self.failed = True
            raise
        finally:
            self.depth -= 1


@pytest.fixture
def db():
    customer = Table('customer', schema='app', pkey=('id',), columns={
        'id': Column('id', 'I'), 'name': Column('name'),
        'label': Column('label', formula='$name'),
    })
    invoice = Table('invoice', schema='app', pkey=('id',), columns={
        'id': Column('id', 'I'), 'customer_id': Column('customer_id', 'I'),
    }, relations={'customer': Relation('customer', customer.key, ('customer_id',), ('id',))})
    return Application(ResolvedModel({customer.key: customer, invoice.key: invoice}))


def test_composite_selector_requires_complete_keys_and_uses_named_physical_resolution(db):
    table = Table('compound', columns={'left': Column('left', sql_name='L'), 'right': Column('right')},
                  pkey=('left', 'right'))
    app = Application(ResolvedModel({table.key: table}))
    live = app.table('compound')
    with pytest.raises(ValueError, match='Incomplete primary key'):
        live.record({'left': 0})
    app.results = [[{'left': 0, 'right': 'x'}]]
    assert live.record({'left': 0, 'right': 'x'}, mode='dict')['left'] == 0
    assert '"t0"."L"' in app.executions[0].sql
    with pytest.raises(ValueError, match='Incomplete primary key'):
        live.update({'left': 0})
    app.results = [[{'left': 0, 'right': 'x'}], [{'left': 0, 'right': 'x'}]]
    live.delete({'left': 0, 'right': 'x'})
    assert app.executions[-1].sql.startswith('DELETE ')


def test_update_record_and_delete_pkey_zero_keep_explicit_selectors(db):
    table = db.table('customer')
    db.results = [[{'id': 0, 'name': 'Before'}], [{'id': 0}]]
    table.update({'id': 0, 'name': 'Zero'}, returning='$id')
    assert '\nWHERE ' in db.executions[-1].sql
    db.results = [[{'id': 0, 'name': 'Zero'}], [{'id': 0}]]
    table.delete(0, returning=None)
    assert list(db.executions[-1].params.values()) == [0]
    with pytest.raises(ValueError):
        table.delete()
    assert db.failed


def test_insert_hooks_share_session_and_failure_propagates_without_mutating_input(db):
    seen = []

    class Customer(SqlTable):
        def trigger_onInserting(self, record):
            seen.append(('before', self.db.depth))
            record['name'] = 'Changed'

        def trigger_onInserted(self, record):
            seen.append(('after', self.db.depth, record['id']))
            self.db.table('invoice').insert({'id': 10, 'customer_id': record['id']})
            raise RuntimeError('hook failed')

    db.table_classes['app.customer'] = Customer
    db.results = [[{'id': 7, 'name': 'Changed'}], [{'id': 10, 'customer_id': 7}]]
    values = {'name': 'Original'}
    with pytest.raises(RuntimeError, match='hook failed'):
        db.table('customer').insert(values)
    assert values == {'name': 'Original'}
    assert seen == [('before', 1), ('after', 1, 7)]
    assert len(db.executions) == 2 and db.failed and db.depth == 0


def test_update_hooks_receive_locked_old_record_and_detached_complete_values(db):
    seen = []

    class Customer(SqlTable):
        def trigger_onUpdating(self, record, old_record=None):
            seen.append(('before', dict(record), dict(old_record)))
            old_record['name'] = 'must not escape'
            record['name'] = record['name'].upper()

        def trigger_onUpdated(self, record, old_record=None):
            seen.append(('after', dict(record), dict(old_record)))

    db.table_classes['app.customer'] = Customer
    db.results = [[{'id': 0, 'name': 'old'}], [{'id': 0, 'name': 'NEW'}]]
    values = {'id': 0, 'name': 'new'}
    db.table('customer').update(values)
    assert values == {'id': 0, 'name': 'new'}
    assert seen == [
        ('before', {'id': 0, 'name': 'new'}, {'id': 0, 'name': 'old'}),
        ('after', {'id': 0, 'name': 'NEW'}, {'id': 0, 'name': 'old'}),
    ]
    assert 'FOR UPDATE' in db.executions[0].sql
    assert '$label' not in db.executions[0].sql
    assert len(db.executions) == 2


@pytest.mark.parametrize('rows, error', [([], RecordNotFoundError),
    ([{'id': 0, 'name': 'a'}, {'id': 1, 'name': 'b'}], RecordMultipleRowsError)])
def test_hooked_write_rejects_missing_or_multiple_records_before_hooks(db, rows, error):
    class Customer(SqlTable):
        def trigger_onDeleting(self, record):
            raise AssertionError('must not run')

    db.table_classes['app.customer'] = Customer
    db.results = [rows]
    with pytest.raises(error):
        db.table('customer').delete(where='TRUE')
    assert len(db.executions) == 1 and db.failed


@pytest.mark.parametrize('operation', ['update', 'delete'])
def test_locked_write_rowcount_mismatch_fails_before_after_hook(db, operation):
    class Customer(SqlTable):
        def trigger_onUpdated(self, record, old_record=None):
            raise AssertionError('after hook must not run')

        def trigger_onDeleted(self, record):
            raise AssertionError('after hook must not run')

    db.table_classes['app.customer'] = Customer
    db.results = [[{'id': 0, 'name': 'old'}], []]
    with pytest.raises(RecordNotFoundError, match='exactly one'):
        if operation == 'update':
            db.table('customer').update({'id': 0, 'name': 'new'})
        else:
            db.table('customer').delete(0)
    assert len(db.executions) == 2 and db.failed


def test_delete_hook_cannot_redirect_the_saved_key(db):
    class Customer(SqlTable):
        def trigger_onDeleting(self, record):
            record['id'] = 123

    db.table_classes['app.customer'] = Customer
    db.results = [[{'id': 0, 'name': 'old'}], [{'id': 0, 'name': 'old'}]]
    db.table('customer').delete(0)
    assert 0 in db.executions[-1].params.values()
    assert 123 not in db.executions[-1].params.values()


def test_post_insert_hook_maps_returning_alias_to_column_identity(db):
    seen = []

    class Customer(SqlTable):
        def trigger_onInserted(self, record):
            seen.append(dict(record))

    db.table_classes['app.customer'] = Customer
    db.results = [[{'name': 7}]]
    result = db.table('customer').insert({'name': 'Original'}, returning='$id AS name')
    assert result.rows == [{'name': 7}]
    assert seen == [{'id': 7, 'name': 'Original'}]


def test_post_insert_hook_does_not_treat_computed_alias_as_a_record_field(db):
    seen = []

    class Customer(SqlTable):
        def trigger_onInserted(self, record):
            seen.append(dict(record))

    db.table_classes['app.customer'] = Customer
    db.results = [[{'name': 'computed'}]]
    db.table('customer').insert({'name': 'Original'}, returning="'computed' AS name")
    assert seen == [{'name': 'Original'}]


def test_poisoned_application_session_rejects_insert_before_running_hooks():
    from asqueel.application import SqlDatabase
    from asqueel.runtime import TransactionStateError

    seen = []

    class Customer(SqlTable):
        def trigger_onInserting(self, record):
            seen.append(dict(record))

    descriptor = Table('customer', columns={'id': Column('id', 'I')}, pkey=('id',),
                       attributes={'x_table_class': Customer})
    db = SqlDatabase(model=ResolvedModel({descriptor.key: descriptor}), config=Config())
    try:
        db._mark_connection_failed(db._connection_state)
        with pytest.raises(TransactionStateError, match='rollback-only'):
            db.table('customer').insert({'id': 1})
        assert seen == []
    finally:
        db.close()
