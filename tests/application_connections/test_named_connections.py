"""F1 contracts: named connections and legacy application environment."""
from datetime import date

import pytest

from asqueel import AsqueelDb, TransactionStateError
from asqueel.contracts import CompiledQuery
from tests.application_config.test_application import Recipe


def test_named_transactions_commit_independently_and_reuse_connections():
    db = AsqueelDb(Recipe).session()
    driver = db.adapter
    db.execute(CompiledQuery('main'))
    other = db.session('other')
    other_driver = other.adapter
    assert db.session('other') is other
    other.execute(CompiledQuery('other'))
    other.commit()
    assert other_driver.persisted == ['other']
    other.execute(CompiledQuery('other_again'))
    other.rollback()
    assert db.currentConnectionName == '_main_connection'
    assert other.currentConnectionName == 'other'
    db.rollback()
    assert driver.persisted == []
    assert other_driver.persisted == ['other']
    assert driver.calls.count('connect') == other_driver.calls.count('connect') == 1
    assert driver.calls.count('close') == other_driver.calls.count('close') == 0
    db.closeConnection()
    other.close()
    assert driver.calls.count('close') == other_driver.calls.count('close') == 1


def test_sql_error_rolls_back_current_name_and_allows_retry():
    db = AsqueelDb(Recipe).session()
    driver = db.adapter
    db.execute(CompiledQuery('main'))
    other = db.session('other')
    other.execute(CompiledQuery('discard'))
    with pytest.raises(LookupError):
        other.execute(CompiledQuery('fail'))
    other.execute(CompiledQuery('recovered'))
    other.commit()
    db.commit()
    assert other.adapter.persisted == ['recovered']
    assert driver.persisted == ['main']
    other.close()
    db.closeConnection()


def test_legacy_environment_scope_preserves_unrelated_changes():
    db = AsqueelDb(Recipe).session()
    db.currentEnv = {'user': 'original', 'options': []}
    original = db.currentEnv
    with pytest.raises(RuntimeError):
        with db.tempEnv(user='temporary', introduced=1):
            db.currentEnv['introduced'] = 2
            db.currentEnv['unrelated'] = 'keep'
            db.currentEnv['options'].append('keep')
            with db.tempEnv(user='nested'):
                assert db.currentEnv['user'] == 'nested'
            assert db.currentEnv['user'] == 'temporary'
            raise RuntimeError('scope')
    assert db.currentEnv is original
    assert db.currentEnv == {'user': 'original', 'options': ['keep'],
                             'introduced': 2, 'unrelated': 'keep'}
    snapshot = db.environment_snapshot()
    snapshot['options'].append('detached')
    assert db.currentEnv['options'] == ['keep']
    db.updateEnv(_excludeNoneValues=True, user=None, zero=0, flag=False)
    assert db.currentEnv['user'] == 'original'
    assert db.currentEnv['zero'] == 0 and db.currentEnv['flag'] is False
    db.clearCurrentEnv()
    assert db.currentEnv == {}
    assert db.workdate == date.today()
    db.workdate = date(2024, 1, 2)
    db.locale = 'it_IT'
    compiled = db.table('app.item').query(columns=':env_workdate AS day, :env_locale AS lang').compiled
    assert compiled.params == {'env_workdate': date(2024, 1, 2), 'env_locale': 'it_IT'}
    db.closeConnection()


def test_store_switch_is_explicitly_unsupported_not_silently_same_database():
    from asqueel import UnsupportedFeatureError
    db = AsqueelDb(Recipe).session()
    driver = db.adapter
    with db.tempEnv(storename='another_store'):
        with pytest.raises(UnsupportedFeatureError):
            db.execute(CompiledQuery('wrong_store'))
    assert not driver.calls
    db.closeConnection()


def test_closing_the_database_closes_every_session_after_one_failure():
    shared = AsqueelDb(Recipe)
    db = shared.session()
    db.execute(CompiledQuery('first'))
    other = db.session('other')
    other.execute(CompiledQuery('second'))
    for session in (db, other):
        session.adapter.rollback_error = OSError('rollback failed')
    with pytest.raises(OSError):
        shared.close()
    for session in (db, other):
        assert session.adapter.calls.count('rollback') == session.adapter.calls.count('close') == 1
        with pytest.raises(TransactionStateError):
            session.execute(CompiledQuery('closed'))


def test_repeated_commits_never_replay_prior_writes():
    db = AsqueelDb(Recipe).session()
    driver = db.adapter
    db.execute(CompiledQuery('first'))
    db.commit()
    db.commit()
    db.execute(CompiledQuery('second'))
    db.commit()
    assert driver.persisted == ['first', 'second']
    assert driver.calls.count('connect') == 1
    assert driver.calls.count('commit') == 2
    db.closeConnection()


def test_rollback_failure_preserves_sql_error_and_requires_explicit_recovery():
    from asqueel import TransactionStateError
    db = AsqueelDb(Recipe).session()
    driver = db.adapter
    driver.rollback_error = OSError('rollback failed')
    with pytest.raises(LookupError) as error:
        db.execute(CompiledQuery('fail'))
    assert isinstance(error.value.__cause__, OSError)
    assert driver.calls[-1] == 'close'
    with pytest.raises(TransactionStateError):
        db.execute(CompiledQuery('not yet'))
    driver.rollback_error = None
    db.rollback()
    db.execute(CompiledQuery('recovered'))
    db.commit()
    db.closeConnection()


def test_closing_the_database_releases_every_session_and_a_new_one_reopens():
    shared = AsqueelDb(Recipe)
    db = shared.session()
    db.execute(CompiledQuery('first'))
    other = db.session('other')
    other.execute(CompiledQuery('second'))
    shared.close()
    for session in (db, other):
        assert session.adapter.persisted == []
        assert session.adapter.calls.count('rollback') == session.adapter.calls.count('close') == 1
    reopened = shared.session()
    assert reopened is not db
    reopened.execute(CompiledQuery('reopened'))
    reopened.commit()
    assert reopened.adapter.persisted == ['reopened']
    assert reopened.adapter.calls.count('connect') == 1
    reopened.close()


def test_default_workdate_binding_is_read_again_at_execution():
    db = AsqueelDb(Recipe).session()
    driver = db.adapter
    query = db.table('app.item').query(columns=':env_workdate AS day').compiled
    assert query.params['env_workdate'] == date.today()
    db.workdate = date(2000, 1, 1)
    db.execute(query)
    assert driver.executed_params[-1]['env_workdate'] == date(2000, 1, 1)
    db.rollback()
    db.closeConnection()


def test_direct_environment_assignment_shares_identity_like_legacy():
    db = AsqueelDb(Recipe).session()
    source = {'user': 'a'}
    db.currentEnv = source
    source['user'] = 'b'
    assert db.currentEnv is source
    assert db.currentEnv['user'] == 'b'
    with db.tempEnv(temporary=1):
        db.clearCurrentEnv()
        db.updateEnv(user='c')
    assert db.currentEnv == {'user': 'c'}
    db.closeConnection()
