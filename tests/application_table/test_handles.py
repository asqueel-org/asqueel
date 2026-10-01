from asqueel.writes import WriteMixin
from contextlib import contextmanager
from copy import deepcopy
from dataclasses import replace

import pytest

from asqueel.application_table import (
    RecordMultipleRowsError, RecordNotFoundError, SqlRecord, SqlTable,
)
from asqueel.compiler import PostgresCompiler
from asqueel.contracts import Column, QueryResult, Relation, ResolvedModel, Table, UnsupportedFeatureError
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


def test_stable_live_handles_and_shared_configuration(db):
    table = db.table('customer')
    assert table is db.table('app.customer')
    assert table.column('name') is table.columns['name']
    assert table.column('name').table is table
    assert table.column('name').db is db
    relation = db.table('invoice').relation('customer')
    assert relation is db.table('invoice').relations['customer']
    assert relation.target is table
    assert table.config.handler is table.column('name').config.handler is db.config
    db.config.values['schemas.app.tables.customer.columns.name.name_long'] = 'Customer name'
    db.config.values['schemas.app.tables.customer.virtual_columns.label.name_long'] = 'Label'
    assert table.column('name').config('name_long') == 'Customer name'
    assert table.column('label').config('name_long') == 'Label'
    with pytest.raises(ValueError, match='Unknown column'):
        table.column('missing')


def test_query_is_lazy_inspection_does_not_pin_environment_and_fetch_reexecutes(db):
    query = db.table('customer').query('$id, $name', where='$id=:env_customer')
    assert not db.executions
    with db.environment.temp_env(customer=1):
        inspected = query.compiled
        assert inspected.params['env_customer'] == 1
        assert query.sqltext.startswith('SELECT ')
    assert not db.executions
    with db.environment.temp_env(customer=2):
        db.results = [[{'id': 2, 'name': 'Two'}], [{'id': 2, 'name': 'Changed'}]]
        assert query.fetch()[0]['name'] == 'Two'
        assert query.execute().rows[0]['name'] == 'Changed'
    assert [q.params['env_customer'] for q in db.executions] == [2, 2]


def test_detached_parameters_and_legacy_keyword_bindings(db):
    params = {'ids': [0, 1]}
    query = db.table('customer').query('$id', where='$id=ANY(:ids)', sqlparams=params)
    params['ids'].append(2)
    assert query.compiled.params['ids'] == [0, 1]
    assert db.table('customer').query('$id', where='$id=:id', id=0).compiled.params['id'] == 0
    with pytest.raises(ValueError, match='Duplicate parameter'):
        db.table('customer').query(where='$id=:id', sqlparams={'id': 1}, id=2)
    with pytest.raises(UnsupportedFeatureError, match='unused keyword'):
        db.table('customer').query(nonsense=True).compiled


@pytest.mark.parametrize('option', ['aggregateRows', '_aggregateRows', 'relationDict', 'addPkeyColumn'])
def test_unsupported_options_are_not_silently_treated_as_bindings(db, option):
    with pytest.raises(UnsupportedFeatureError):
        db.table('customer').query(**{option: True})


def test_alias_conflicts_and_no_fake_selection(db):
    table = db.table('customer')
    assert table.query('$id', excludeDraft=False, excludeLogicalDeleted=False, ignorePartition=True).compiled
    with pytest.raises(ValueError, match='Conflicting'):
        table.query(excludeDraft=False, exclude_draft=False)
    with pytest.raises(UnsupportedFeatureError):
        table.query().selection()


def test_record_is_lazy_cached_defensive_and_explicitly_refreshable(db):
    db.results = [[{'id': 0, 'name': 'Before'}], [{'id': 0, 'name': 'After'}]]
    record = db.table('customer').record(0)
    assert isinstance(record, SqlRecord) and not db.executions
    first = record.output('dict')
    first['name'] = 'Caller mutation'
    assert record.output('dict')['name'] == 'Before'
    assert len(db.executions) == 1
    assert record.refresh() is record
    assert record.output('dict')['name'] == 'After'
    assert len(db.executions) == 2
    assert 'LIMIT 1' not in db.executions[0].sql
    assert 0 in db.executions[0].params.values()


def test_record_errors_and_unsupported_modes(db):
    table = db.table('customer')
    with pytest.raises(ValueError, match='requires a primary key'):
        table.record()
    with pytest.raises(ValueError, match='nonempty selector'):
        table.record(where='')
    with pytest.raises(UnsupportedFeatureError):
        table.record(1, limit=1)
    with pytest.raises(UnsupportedFeatureError):
        table.record(1, mode='bag')
    assert not db.executions
    with pytest.raises(RecordNotFoundError):
        table.record(1).output('dict')
    db.results = [[{'id': 1}, {'id': 2}]]
    with pytest.raises(RecordMultipleRowsError):
        table.record(where='TRUE', mode='dict')


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
    assert ' WHERE ' in db.executions[-1].sql
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


def test_cycles_resolve_relation_target_only_after_handle_registration():
    a = Table('a', columns={'id': Column('id')}, pkey=('id',))
    b = Table('b', columns={'id': Column('id')}, pkey=('id',))
    a = replace(a, relations={'b': Relation('b', b.key, ('id',), ('id',))})
    b = replace(b, relations={'a': Relation('a', a.key, ('id',), ('id',))})
    app = Application(ResolvedModel({a.key: a, b.key: b}))
    assert app.table('a').relation('b').target.relation('a').target is app.table('a')


def test_record_cannot_hide_duplicates_behind_an_aggregate_projection(db):
    with pytest.raises(UnsupportedFeatureError, match='complete row'):
        db.table('customer').record(where='TRUE', columns='COUNT(*) AS count')
    assert not db.executions


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
