"""F1 context contract: no locale validation or process-global locale mutation."""
from concurrent.futures import ThreadPoolExecutor
from datetime import date
import locale
from threading import Barrier

import pytest

from asqueel import AsqueelDb, EnvironmentMismatchError, SqlDatabaseConfig
from tests.application_config.test_application import Recipe
from tests.application_session.test_session import Driver
from tests.native_support import postgres_dsn


@pytest.mark.parametrize('configured,system,expected', [
    (None, 'it_IT', 'it_IT'), (None, None, 'en_GB'),
    ('', 'it_IT', 'en_GB'), ('fr_FR', 'it_IT', 'fr_FR'),
    ('application-locale', 'it_IT', 'application-locale'),
    (None, 'unknown-system-locale', 'unknown-system-locale'),
])
def test_locale_fallback_without_validation(monkeypatch, configured, system, expected):
    monkeypatch.setattr(locale, 'getlocale', lambda: (system, 'UTF-8'))
    if configured is None:
        monkeypatch.delenv('GNR_LOCALE', raising=False)
    else:
        monkeypatch.setenv('GNR_LOCALE', configured)
    db = AsqueelDb(Recipe, driver=Driver())
    try:
        assert db.locale == expected
        assert db.currentEnv == {}  # Reading defaults does not populate the live mapping.
        db.locale = 'custom-explicit-value'
        assert db.locale == 'custom-explicit-value'
        for empty in (None, '', False, 0):
            db.locale = empty
            assert db.locale == expected
        assert db.environment.snapshot()['locale'] == expected
    finally:
        db.close()


def test_workdate_defaults_are_dynamic_and_values_are_not_coerced(monkeypatch):
    import datetime

    class Clock(date):
        today_value = date(2026, 9, 30)

        @classmethod
        def today(cls):
            return cls.today_value

    monkeypatch.setattr(datetime, 'date', Clock)
    db = AsqueelDb(Recipe, driver=Driver())
    try:
        assert db.workdate == date(2026, 9, 30)
        query = db.table('item').query(columns=':env_workdate AS day').compiled
        Clock.today_value = date(2026, 10, 1)
        assert db.workdate == Clock.today_value
        with pytest.raises(EnvironmentMismatchError):
            db.execute(query)
        for empty in (None, '', False, 0):
            db.workdate = empty
            assert db.workdate == Clock.today_value
        db.workdate = 'application-business-date'
        assert db.workdate == 'application-business-date'
    finally:
        db.close()


def test_nested_scopes_restore_context_after_error_and_reject_stale_query():
    db = AsqueelDb(Recipe, driver=Driver())
    db.workdate, db.locale = date(2024, 1, 1), 'outer'
    try:
        with pytest.raises(RuntimeError, match='cancel'):
            with db.tempEnv(workdate=date(2024, 2, 1), locale='middle'):
                with db.tempEnv(workdate=date(2024, 3, 1), locale='inner'):
                    query = db.table('item').query(
                        columns=':env_workdate AS day, :env_locale AS lang').compiled
                    assert query.params == {'env_workdate': date(2024, 3, 1), 'env_locale': 'inner'}
                assert (db.workdate, db.locale) == (date(2024, 2, 1), 'middle')
                raise RuntimeError('cancel')
        assert (db.workdate, db.locale) == (date(2024, 1, 1), 'outer')
        with pytest.raises(EnvironmentMismatchError):
            db.execute(query)
        db.clearCurrentEnv()
        with db.tempEnv(workdate=date(2024, 4, 1), locale='temporary'):
            pass
        assert db.currentEnv == {}
        with db.tempEnv(locale='temporary'):
            db.locale = 'changed'  # Legacy preserves changes to newly introduced keys.
        assert db.locale == 'changed'
    finally:
        db.close()


def test_dates_and_locales_are_isolated_between_live_threads():
    db = AsqueelDb(Recipe, driver=Driver())
    db.workdate, db.locale = date(2024, 1, 1), 'main'
    barrier = Barrier(2)

    def worker(day, language):
        try:
            assert db.currentEnv == {}
            db.workdate, db.locale = day, language
            with db.tempEnv(locale=language + '-temporary'):
                barrier.wait(timeout=10)
                assert (db.workdate, db.locale) == (day, language + '-temporary')
            return db.workdate, db.locale
        finally:
            db.close()

    try:
        with ThreadPoolExecutor(max_workers=2) as pool:
            a = pool.submit(worker, date(2024, 2, 1), 'alice')
            b = pool.submit(worker, date(2024, 3, 1), 'bob')
            assert a.result() == (date(2024, 2, 1), 'alice')
            assert b.result() == (date(2024, 3, 1), 'bob')
        assert (db.workdate, db.locale) == (date(2024, 1, 1), 'main')
    finally:
        db.close()


@pytest.mark.parametrize('backend', ['sqlite', pytest.param('postgresql', marks=pytest.mark.postgresql)])
def test_context_binding_on_real_database(backend):
    class Configuration(SqlDatabaseConfig):
        def main(self, root):
            if backend == 'sqlite':
                root.db().connection(name=':memory:', implementation='sqlite')
            else:
                root.db(conninfo=postgres_dsn())

    db = AsqueelDb(Configuration)
    try:
        with db.tempEnv(workdate=date(2024, 6, 1), locale="custom'locale"):
            row = db.execute('SELECT :env_workdate AS day, :env_locale AS lang').rows[0]
            assert str(row['day']) == '2024-06-01'
            assert row['lang'] == "custom'locale"
            row = db.execute('SELECT :env_locale AS lang', {'env_locale': 'explicit'}).rows[0]
            assert row['lang'] == 'explicit'
            db.rollback()
        assert db.currentEnv == {}
    finally:
        db.close()
