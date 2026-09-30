"""F1 contracts: named connections and legacy application environment."""
from datetime import date

import pytest

from genro_sql import build_database
from genro_sql.contracts import CompiledQuery
from tests.application_config.test_application import Recipe
from tests.application_session.test_session import Driver


def test_named_transactions_commit_independently_and_reuse_connections():
    driver = Driver()
    db = build_database(Recipe, driver=driver)
    db.execute(CompiledQuery('main'))
    with db.tempEnv(connectionName='other') as scoped:
        assert scoped is db
        db.execute(CompiledQuery('other'))
        db.commit()
        assert driver.persisted == ['other']
        db.execute(CompiledQuery('other_again'))
        db.rollback()
    assert db.currentConnectionName == '_main_connection'
    assert db.outcome == 'active'
    db.rollback()
    assert driver.persisted == ['other']
    assert driver.calls.count('connect') == 2
    assert driver.calls.count('close') == 0
    db.close()
    assert driver.calls.count('close') == 2


def test_sql_error_rolls_back_current_name_and_allows_retry():
    driver = Driver()
    db = build_database(Recipe, driver=driver)
    db.execute(CompiledQuery('main'))
    with db.tempEnv(connectionName='other'):
        db.execute(CompiledQuery('discard'))
        with pytest.raises(LookupError):
            db.execute(CompiledQuery('fail'))
        assert db.outcome == 'rolled_back'
        db.execute(CompiledQuery('recovered'))
        db.commit()
    db.commit()
    assert driver.persisted == ['recovered', 'main']
    db.close()


def test_legacy_environment_scope_preserves_unrelated_changes():
    db = build_database(Recipe, driver=Driver())
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
    snapshot = db.current_env
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
    compiled = db.table('item').query(columns=':env_workdate AS day, :env_locale AS lang').compiled
    assert compiled.params == {'env_workdate': date(2024, 1, 2), 'env_locale': 'it_IT'}
    db.close()


def test_store_switch_is_explicitly_unsupported_not_silently_same_database():
    from genro_sql import UnsupportedFeatureError
    driver = Driver()
    db = build_database(Recipe, driver=driver)
    with db.tempEnv(storename='another_store'):
        with pytest.raises(UnsupportedFeatureError):
            db.execute(CompiledQuery('wrong_store'))
    assert not driver.calls
    db.close()


def test_close_cleans_every_named_connection_after_one_failure():
    driver = Driver()
    db = build_database(Recipe, driver=driver)
    db.execute(CompiledQuery('first'))
    with db.tempEnv(connectionName='other'):
        db.execute(CompiledQuery('second'))
    driver.rollback_error = OSError('rollback failed')
    with pytest.raises(OSError):
        db.close()
    assert driver.calls.count('rollback') == driver.calls.count('close') == 2
    db.close()


def test_repeated_commits_never_replay_prior_writes():
    driver = Driver()
    db = build_database(Recipe, driver=driver)
    db.execute(CompiledQuery('first'))
    db.commit()
    db.commit()
    db.execute(CompiledQuery('second'))
    db.commit()
    assert driver.persisted == ['first', 'second']
    assert driver.calls.count('connect') == 1
    assert driver.calls.count('commit') == 2
    db.close()


def test_rollback_failure_preserves_sql_error_and_requires_explicit_recovery():
    from genro_sql import TransactionStateError
    driver = Driver()
    db = build_database(Recipe, driver=driver)
    driver.rollback_error = OSError('rollback failed')
    with pytest.raises(LookupError) as error:
        db.execute(CompiledQuery('fail'))
    assert isinstance(error.value.__cause__, OSError)
    assert db.outcome == 'unknown'
    assert driver.calls[-1] == 'close'
    with pytest.raises(TransactionStateError):
        db.execute(CompiledQuery('not yet'))
    driver.rollback_error = None
    db.rollback()
    db.execute(CompiledQuery('recovered'))
    db.commit()
    db.close()


def test_close_connection_releases_all_names_and_database_can_reopen():
    driver = Driver()
    db = build_database(Recipe, driver=driver)
    db.execute(CompiledQuery('first'))
    with db.tempEnv(connectionName='other'):
        db.execute(CompiledQuery('second'))
    db.closeConnection()
    assert driver.persisted == []
    assert driver.calls.count('rollback') == driver.calls.count('close') == 2
    db.execute(CompiledQuery('reopened'))
    db.commit()
    assert driver.persisted == ['reopened']
    assert driver.calls.count('connect') == 3
    db.close()


def test_default_workdate_binding_and_stale_snapshot_rejection():
    from genro_sql import EnvironmentMismatchError
    driver = Driver()
    db = build_database(Recipe, driver=driver)
    query = db.table('item').query(columns=':env_workdate AS day').compiled
    assert query.params['env_workdate'] == date.today()
    db.workdate = date(2000, 1, 1)
    with pytest.raises(EnvironmentMismatchError):
        db.execute(query)
    assert not driver.calls
    db.close()


def test_direct_environment_assignment_shares_identity_like_legacy():
    db = build_database(Recipe, driver=Driver())
    source = {'user': 'a'}
    db.currentEnv = source
    source['user'] = 'b'
    assert db.currentEnv is source
    assert db.currentEnv['user'] == 'b'
    with db.tempEnv(temporary=1):
        db.clearCurrentEnv()
        db.updateEnv(user='c')
    assert db.currentEnv == {'user': 'c'}
    db.close()
