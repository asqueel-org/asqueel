"""asqueel#56: AsqueelDb shared by every call, SessionDb per call."""
import contextvars
import logging
import sqlite3
from concurrent.futures import ThreadPoolExecutor

import pytest

from asqueel import AsqueelDb, SessionDb, SqlDatabaseConfig, TransactionStateError


def declare(root):
    note = root.packages().package('app', sqlschema='main', sqlprefix=False).table('note', pkey='id')
    note.column('id', dtype='L')
    note.column('text')


@pytest.fixture
def db(tmp_path):
    source = SqlDatabaseConfig()
    root = source.source.db('runtime', implementation='sqlite')
    root.connection('main', database=str(tmp_path / 'runtime.sqlite'))
    declare(root)
    shared = AsqueelDb(source)
    with shared.session() as session:
        session.migrate()
        session.commit()
    yield shared
    shared.close()


@pytest.fixture
def memory_db():
    source = SqlDatabaseConfig()
    source.source.db('memory', implementation='sqlite', conninfo=':memory:')
    shared = AsqueelDb(source)
    yield shared
    shared.close()


def texts(session):
    return [row['text'] for row in session.table('app.note').query(columns='$text', order_by='$id').fetch()]


def test_the_shared_database_holds_no_connection(db):
    with pytest.raises(TransactionStateError):
        db.execute('SELECT 1')
    with pytest.raises(TransactionStateError):
        db.commit()
    with pytest.raises(TransactionStateError):
        db.rollback()
    with pytest.raises(TransactionStateError):
        db.table('app.note').insert({'id': 1, 'text': 'x'})


def test_the_main_session_is_one_per_call(db):
    session = db.session()
    assert isinstance(session, SessionDb)
    assert isinstance(session, AsqueelDb)
    assert db.session() is session
    assert session.session() is session
    assert session.model is db.model
    session.close()


def test_a_named_session_is_independent_and_reused(db):
    main = db.session()
    alfa = db.session('alfa')
    assert alfa is not main
    assert db.session('alfa') is alfa
    assert main.session('alfa') is alfa
    alfa.table('app.note').insert({'id': 1, 'text': 'from alfa'})
    assert texts(main) == []
    alfa.commit()
    assert texts(main) == ['from alfa']
    alfa.close()
    main.close()


def test_tables_are_bound_to_their_session(db):
    main = db.session()
    alfa = db.session('alfa')
    table = main.table('app.note')
    assert main.table('app.note') is table
    assert alfa.table('app.note') is not table
    assert table.model is db.table('app.note').model
    assert table.db is main
    assert main.tables['app.note'] is table
    assert alfa.tables['app.note'] is alfa.table('app.note')
    alfa.close()
    main.close()


def test_a_closed_session_refuses_any_use(db):
    with db.session('beta') as beta:
        beta.execute('SELECT 1').close()
    with pytest.raises(TransactionStateError):
        beta.execute('SELECT 1')
    with pytest.raises(TransactionStateError):
        beta.table('app.note')


def test_a_new_main_session_follows_a_closed_one(db):
    first = db.session()
    first.close()
    second = db.session()
    assert second is not first
    second.close()


def test_clean_close_with_pending_work_rolls_back_and_warns(db, caplog):
    with caplog.at_level(logging.WARNING):
        with db.session('pending') as pending:
            pending.table('app.note').insert({'id': 1, 'text': 'lost'})
    warnings = [record.getMessage() for record in caplog.records if record.levelno == logging.WARNING]
    assert len(warnings) == 1
    assert 'runtime' in warnings[0] and 'pending' in warnings[0]
    with db.session() as main:
        assert texts(main) == []


def test_close_by_exception_rolls_back_without_warning(db, caplog):
    with caplog.at_level(logging.WARNING):
        with pytest.raises(LookupError):
            with db.session('failing') as failing:
                failing.table('app.note').insert({'id': 1, 'text': 'lost'})
                raise LookupError('body failed')
    assert not [record for record in caplog.records if record.levelno >= logging.WARNING]
    with db.session() as main:
        assert texts(main) == []


def test_close_closes_the_open_cursors_without_error(db):
    session = db.session('cursors')
    cursor = session.execute('SELECT id FROM note')
    session.close()
    with pytest.raises(sqlite3.ProgrammingError):
        cursor.fetchall()


def test_close_connection_keeps_the_legacy_meaning(db):
    session = db.session()
    session.table('app.note').insert({'id': 1, 'text': 'rolled back'})
    session.closeConnection()
    assert texts(session) == []
    session.table('app.note').insert({'id': 2, 'text': 'kept'})
    session.commit()
    assert texts(session) == ['kept']
    session.close()


def test_one_call_from_two_threads_in_sequence_shares_one_transaction(db):
    call = contextvars.copy_context()
    session = call.run(db.session)
    session.table('app.note').insert({'id': 1, 'text': 'first thread'})

    def second_thread():
        same = db.session()
        same.table('app.note').insert({'id': 2, 'text': 'second thread'})
        return same, texts(same)

    with ThreadPoolExecutor(max_workers=1) as pool:
        same, seen = pool.submit(call.run, second_thread).result()
    assert same is session
    assert seen == ['first thread', 'second thread']
    session.commit()
    session.close()
    with db.session() as main:
        assert texts(main) == ['first thread', 'second thread']


def test_two_calls_on_one_thread_see_two_sessions(db):
    first = contextvars.Context().run(db.session)
    second = contextvars.Context().run(db.session)
    assert first is not second
    first.close()
    second.close()


def test_memory_database_keeps_its_data_across_sessions(memory_db):
    with memory_db.session() as first:
        first.execute('CREATE TABLE item (id INTEGER)').close()
        first.execute('INSERT INTO item VALUES (1)').close()
        first.commit()
    with memory_db.session() as second:
        assert [row['id'] for row in second.execute('SELECT id FROM item').fetchall()] == [1]


def test_memory_database_refuses_a_second_open_session(memory_db):
    with memory_db.session():
        with pytest.raises(TransactionStateError):
            memory_db.session('other')


def test_closing_the_memory_database_closes_its_open_session(memory_db):
    session = memory_db.session()
    session.execute('SELECT 1').close()
    memory_db.close()
    with pytest.raises(TransactionStateError):
        session.execute('SELECT 1')


def test_each_session_has_an_adapter_bound_to_it(db):
    main = db.session()
    alfa = db.session('alfa')
    assert main.adapter.dbroot is main
    assert alfa.adapter.dbroot is alfa
    main.setConstraintsDeferred()
    alfa.close()
    main.close()


def test_the_hierarchical_handler_belongs_to_the_session_table(tmp_path):
    source = SqlDatabaseConfig()
    root = source.source.db('tree', implementation='sqlite')
    root.connection('main', database=str(tmp_path / 'tree.sqlite'))
    table = root.packages().package('app', sqlschema='main', sqlprefix=False).table('category')
    table.options().sysFields()
    table.options().hierarchical('code')
    table.column('code')
    shared = AsqueelDb(source)
    with shared.session() as session:
        session.migrate()
        session.commit()
    alfa = shared.session('alfa')
    category = alfa.table('app.category')
    assert category.hierarchicalHandler.tblobj is category
    category.insert({'code': 'a'})
    alfa.commit()
    alfa.close()
    with shared.session() as main:
        assert [row['code'] for row in main.table('app.category').query(columns='$code').fetch()] == ['a']
    shared.close()


def test_table_methods_called_by_the_compiler_run_on_the_session_table():
    # wf:contract: a sql_formula_<name>, env_<name> or subquery_<name> method of a package
    # wf:contract: Table class, reached while a SessionDb compiles a query, is called on the
    # wf:contract: table of that SessionDb: inside the method self.db is that SessionDb, and a
    # wf:contract: query the method runs executes on its connection.
    pytest.fail('phase 3 pending')


def test_formula_column_methods_are_cached_in_the_session_environment():
    # wf:contract: the formulaColumn_<name>() columns of a table are cached in currentEnv of
    # wf:contract: the SessionDb that compiles the query, not of the shared AsqueelDb: two
    # wf:contract: sessions with different environments each get the columns of their own env.
    pytest.fail('phase 3 pending')


def test_concurrent_use_of_one_session_is_refused():
    # wf:contract: while one thread is inside session.execute, a second thread calling
    # wf:contract: session.execute on the same SessionDb raises TransactionStateError at once
    # wf:contract: (the executing flag); the first statement completes normally.
    pytest.fail('phase 3 pending')
