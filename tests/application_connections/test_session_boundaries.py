"""The boundaries of a call: what one session or one call must never hand to the next."""
import contextvars
import gc
import logging
from concurrent.futures import ThreadPoolExecutor
import threading
import time

import pytest

from asqueel import AsqueelDb, AsqueelDbMixin, SqlDatabaseConfig, TransactionStateError
from tests.option_tables_support import migrated_db
from tests.package_layout_support import write_layout
from tests.test_formula_columns_legacy import CUSTOMER, declare


def note_db(database, aux=None):
    source = SqlDatabaseConfig()
    root = source.source.db('boundaries', implementation='sqlite')
    root.connection('main', database=database)
    if aux is not None:
        root.connection('aux', database=aux)
    note = root.packages().package('app', sqlschema='main', sqlprefix=False).table('note', pkey='id')
    note.column('id', size=':22')
    note.column('text')
    shared = AsqueelDb(source)
    with shared.session() as session:
        session.migrate()
        session.commit()
    return shared


@pytest.fixture
def shared(tmp_path):
    database = note_db(str(tmp_path / 'boundaries.sqlite'))
    yield database
    database.close()


@pytest.fixture
def memory():
    database = note_db(':memory:')
    yield database
    database.close()


def ids(session):
    return session.table('app.note').query(columns='$id', order_by='$id').fetchPkeys()


def test_a_reused_worker_starts_each_call_with_new_sessions(shared):
    def first_call():
        main = shared.session(user='alice')
        audit = shared.session('audit')
        audit.table('app.note').insert({'id': 'a1', 'text': 'pending'})
        main.close()
        audit.rollback()
        audit.close()
        return audit

    def second_call():
        shared.session(user='bob')
        return shared.session('audit')

    with ThreadPoolExecutor(max_workers=1) as pool:
        first = pool.submit(first_call).result()
        second = pool.submit(second_call).result()
    assert second is not first
    assert second.currentEnv.get('user') is None
    shared.close()


def test_a_named_session_opened_first_gives_way_to_the_main_one(shared):
    def call():
        alfa = shared.session('alfa')
        main = shared.session()
        assert shared._current_session.get() is main
        assert main.session('alfa') is alfa
        main.close()
        alfa.close()

    contextvars.Context().run(call)


def test_a_session_opened_by_routing_closes_with_its_caller(tmp_path):
    shared = note_db(str(tmp_path / 'main.sqlite'), aux=str(tmp_path / 'aux.sqlite'))
    main = shared.session()
    with main.tempEnv(connectionName='aux'):
        main.execute('SELECT 1').close()
    aux = main.session('aux')
    assert aux._target == 'aux'
    main.close()
    with pytest.raises(TransactionStateError):
        aux.execute('SELECT 1')
    shared.close()


def test_a_read_only_session_closes_without_warning(shared, caplog):
    with caplog.at_level(logging.WARNING):
        with shared.session() as session:
            assert ids(session) == []
    assert not [record for record in caplog.records if record.levelno >= logging.WARNING]


def test_a_refused_close_leaves_the_session_open(shared):
    session = shared.session()
    session.table('app.note').insert({'id': 'w', 'text': 'pending'})
    connection = session._connections['_main_connection']['connection']
    started = threading.Event()

    def slow():
        started.set()
        time.sleep(0.5)
        return 1

    connection.create_function('slow', 0, slow)
    worker = threading.Thread(target=contextvars.copy_context().run,
                              args=(lambda: session.execute('SELECT slow()').fetchall(),))
    worker.start()
    started.wait()
    with pytest.raises(TransactionStateError, match='executing'):
        session.close()
    worker.join()
    assert ids(session) == ['w']
    session.rollback()
    session.close()


def test_memory_work_left_by_an_abandoned_session_is_rolled_back(memory):
    def abandoned_call():
        memory.session().table('app.note').insert({'id': 'ghost', 'text': 'never committed'})

    contextvars.Context().run(abandoned_call)
    gc.collect()
    with memory.session() as session:
        session.table('app.note').insert({'id': 'mine', 'text': 'committed'})
        session.commit()
    with memory.session() as session:
        assert ids(session) == ['mine']


def test_memory_tables_migrated_by_a_session_outlive_it(memory):
    with memory.session() as session:
        assert ids(session) == []


def test_formula_columns_of_a_named_session_use_its_environment(tmp_path):
    path = write_layout(tmp_path / 'app', customer=CUSTOMER)
    with migrated_db('sqlite', tmp_path, declare, path=path) as main:
        main.table('app.customer').sql_insert([{'id': 1, 'code': 'a', 'year': 2025}])
        main.commit()
        assert main.table('app.customer').query(columns='$scaled').fetch()[0]['scaled'] == 2025
        audit = main.session('audit', factor=10)
        assert audit.table('app.customer').query(columns='$scaled').fetch()[0]['scaled'] == 20250
        assert '_virtual_columns_app_customer' in audit.currentEnv
        audit.close()


def busy(session, seconds=0.5):
    """Run a slow statement of ``session`` in another thread of the call; return the thread once it runs."""
    started = threading.Event()

    def slow():
        started.set()
        time.sleep(seconds)
        return 1

    session._connections[session.currentConnectionName]['connection'].create_function('slow', 0, slow)
    worker = threading.Thread(target=contextvars.copy_context().run,
                              args=(lambda: session.execute('SELECT slow()').fetchall(),))
    worker.start()
    started.wait()
    return worker


def test_a_close_refused_by_a_routed_session_leaves_both_open(tmp_path):
    shared = note_db(str(tmp_path / 'main.sqlite'), aux=str(tmp_path / 'aux.sqlite'))
    main = shared.session()
    with main.tempEnv(connectionName='aux'):
        main.execute('SELECT 1').close()
    aux = main.session('aux')
    worker = busy(aux)
    with pytest.raises(TransactionStateError, match='executing'):
        main.close()
    worker.join()
    assert not main._closed and not aux._closed
    main.close()
    assert aux._closed
    shared.close()


def test_a_commit_is_refused_while_another_thread_executes(shared):
    session = shared.session()
    session.table('app.note').insert({'id': 'c', 'text': 'pending'})
    worker = busy(session)
    with pytest.raises(TransactionStateError, match='executing'):
        session.commit()
    worker.join()
    session.commit()
    assert ids(session) == ['c']
    session.close()


def test_a_close_is_refused_while_a_fetch_runs(shared):
    session = shared.session()
    session.table('app.note').insert({'id': 'f1', 'text': 'pending'})
    session.table('app.note').insert({'id': 'f2', 'text': 'pending'})
    connection = session._connections['_main_connection']['connection']
    started = threading.Event()
    calls = []

    def slow(value):
        # SQLite computes the first row in execute: the second one is computed by the fetch.
        calls.append(value)
        if len(calls) == 2:
            started.set()
            time.sleep(0.5)
        return value

    connection.create_function('slow_text', 1, slow)
    cursor = session.execute('SELECT slow_text(text) AS text FROM note')
    worker = threading.Thread(target=contextvars.copy_context().run, args=(cursor.fetchall,))
    worker.start()
    started.wait()
    with pytest.raises(TransactionStateError, match='executing'):
        session.close()
    worker.join()
    assert not session._closed
    session.rollback()
    session.close()


def test_vacuum_under_routing_is_refused_with_pending_work_of_the_caller(tmp_path):
    shared = note_db(str(tmp_path / 'main.sqlite'), aux=str(tmp_path / 'aux.sqlite'))
    main = shared.session()
    main.table('app.note').insert({'id': 'v', 'text': 'pending'})
    with main.tempEnv(connectionName='aux'):
        with pytest.raises(TransactionStateError, match='pending work'):
            main.vacuum()
    assert 'aux' not in main._call_sessions
    main.rollback()
    main.close()
    shared.close()


@pytest.mark.parametrize('sql, warned', [
    ('PRAGMA user_version = 7', True),
    ('PRAGMA user_version', False),
    ('WITH t AS (SELECT 1 AS x) SELECT x FROM t', False),
    ("WITH t AS (SELECT 'w' AS id) INSERT INTO note (id) SELECT id FROM t", True),
])
def test_the_close_warning_tells_writes_from_reads(shared, caplog, sql, warned):
    with caplog.at_level(logging.WARNING):
        with shared.session() as session:
            session.execute(sql).close()
    assert bool([record for record in caplog.records if record.levelno >= logging.WARNING]) is warned


class Host(AsqueelDbMixin):
    @property
    def asqueel_owner_name(self):
        return ''

    def asqueel_owner(self, name):
        return self


def test_release_closes_the_named_sessions_after_the_application_closed_the_main_one(tmp_path):
    host = Host()
    host.asqueel_dbs['default'] = note_db(str(tmp_path / 'hosted.sqlite'))
    main = host.db
    audit = main.session('audit')
    audit.execute('SELECT 1').close()
    main.close()
    host.release_databases()
    assert audit._closed
    assert host.taken_databases == []
    host.asqueel_dbs['default'].close()
