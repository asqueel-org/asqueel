"""Read-only diagnostic of the interrupted deferred implementation.

Run from the repository root with PYTHONPATH=. and the development Python.
Uses only the in-memory test driver; no database or external effects.
These observations are not passing acceptance tests.
"""
from genro_sql import build_database, CompiledQuery
from genro_sql.session import Session
from tests.application_config.test_application import Recipe
from tests.application_session.test_session import Driver

def probe_hook_registration():
    db=build_database(Recipe,driver=Driver())
    try:
        with db._write_operation():
            db.deferToCommit(lambda:None)
    except Exception as error:
        print('hook_registration:',type(error).__name__,str(error))
    finally:db.close()

def probe_failed_atomic_completion():
    driver=Driver();session=Session(driver)
    def fail():raise ValueError('pre-commit hook')
    try:
        with session.transaction():
            session.execute(CompiledQuery('write'))
            session.defer_to_commit(fail)
    except ValueError:
        print('failed_atomic_completion:', 'pending=',session._pending,'rollback_calls=',driver.calls.count('rollback'))
    finally:session.close()

def probe_caught_sql_error():
    driver=Driver();session=Session(driver);events=[]
    session.execute(CompiledQuery('write'))
    def before():
        try:session.execute(CompiledQuery('fail'))
        except LookupError:pass
        session.defer_after_commit(lambda:events.append('after'))
    session.defer_to_commit(before)
    try:
        session.commit()
        print('caught_sql_error:', 'after_events=',events,'physical_commits=',driver.calls.count('commit'),'outcome=',session.outcome)
    finally:session.close()

def probe_committing_environment():
    db=build_database(Recipe,driver=Driver());observed=[]
    db.execute(CompiledQuery('write'))
    db.deferToCommit(lambda:observed.append(db.currentEnv.get('onCommittingStep')))
    db.commit()
    print('committing_environment:',observed)
    db.close()

for probe in (probe_hook_registration,probe_failed_atomic_completion,probe_caught_sql_error,probe_committing_environment):
    try:probe()
    except Exception as error:print(probe.__name__,'unexpected:',type(error).__name__,str(error))
