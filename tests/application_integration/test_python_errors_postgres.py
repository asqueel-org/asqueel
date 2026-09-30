"""Observe Python failure and recovery effects through independent PostgreSQL reads."""
from pathlib import Path
import runpy

import psycopg
import pytest

from asqueel import CompiledQuery, DeferredCommitError, TransactionStateError
from tests.application_integration.test_write_hooks import (
    audit_events, hooked_database as hooked_database, persisted,
)
from tests.native_support import postgres_dsn

pytestmark = pytest.mark.postgresql


def test_python_failure_matrix_keeps_current_native_rollback_contract():
    oracle = runpy.run_path(str(Path(__file__).resolve().parents[2]
                               / 'docs/design/evidence/python_error_oracle.py'))
    factory, _ = oracle['native_factory'](postgres_dsn())
    cases = oracle['scenarios'](factory, postgres_dsn())
    initial = {'items': [(10, 'original')], 'audit': []}
    assert len(cases) == 16
    for operation, hooks in oracle['HOOKS'].items():
        for hook in hooks:
            for completion in ('rollback', 'commit'):
                result = cases[f'{hook}/{completion}']
                assert result['visible_after_error'] == initial, (operation, hook)
                assert result['visible_after_completion'] == initial, (operation, hook)
                assert result['trigger_depth'] == 0
                assert result['callbacks'] == []
                assert result['completion_error'] == (
                    'TransactionStateError' if completion == 'commit' else None)
    for queue in ('before', 'after'):
        for new_write in (False, True):
            result = cases[f'{queue}/write={new_write}']
            visible = {'items': [(10, 'original')],
                       'audit': ['earlier'] if queue == 'after' else []}
            assert result['visible_after_error'] == visible
            assert result['visible_after_retry'] == visible
            assert result['retry_error'] == (
                'TransactionStateError' if queue == 'before' or new_write else None)
            assert result['visible_after_recovery']['audit'] == (
                ['earlier', 'recovered'] if queue == 'after' else ['recovered'])
            assert result['callbacks_after_error'] == []
            assert result['callbacks_after_retry'] == []
            assert result['callbacks_after_recovery'] == []


@pytest.mark.parametrize('hook', ['trigger_onUpdating', 'trigger_onUpdated'])
def test_other_connection_sql_failure_aborts_outer_hook_but_not_independent_work(
        hooked_database, hook):
    db, observer, schema = hooked_database
    events = []
    db.table('audit').insert({'event': 'earlier A'})
    db.deferAfterCommit(lambda: events.append('A committed'))
    with db.tempEnv(connectionName='independent'):
        db.table('audit').insert({'event': 'independent'})

    def fail(record, old_record=None):
        db.table('audit').insert({'event': 'hook A'})
        with db.tempEnv(connectionName='failed'):
            db.table('audit').insert({'event': 'failed B'})
            db.execute(CompiledQuery('SELECT 1 / 0'))

    setattr(db.table('item'), hook, fail)
    with pytest.raises(psycopg.errors.DivisionByZero):
        db.table('item').update({'org': 0, 'id': 0, 'name': 'must not persist'})
    with pytest.raises(TransactionStateError, match='rollback-only'):
        db.commit()
    assert persisted(observer, schema)[0] == (0, 0, 'original')
    assert audit_events(observer, schema) == []
    assert events == []
    with db.tempEnv(connectionName='independent'):
        db.commit()
    assert audit_events(observer, schema) == [('independent',)]
    with db.tempEnv(connectionName='failed'):
        db.table('audit').insert({'event': 'recovered B'})
        db.commit()
    db.rollback()
    assert audit_events(observer, schema) == [('independent',), ('recovered B',)]
    assert events == []
    assert db.currentTrigger is None


@pytest.mark.parametrize('failure', ['python', 'sql', 'deferred'])
def test_failed_batch_item_can_be_rolled_back_logged_and_skipped(hooked_database, failure):
    db, observer, schema = hooked_database
    table = db.table('item')
    callbacks = []

    def after_update(record, old_record=None):
        if record['id'] != 0:
            return
        db.table('audit').insert({'event': 'failed hook'})
        db.deferAfterCommit(lambda: callbacks.append('failed item'))
        if failure == 'sql':
            db.execute(CompiledQuery('SELECT 1 / 0'))
        elif failure == 'deferred':
            db.deferredRaise(ValueError('invalid item'))
        else:
            raise ValueError('invalid item')

    table.trigger_onUpdated = after_update
    error = {'sql': psycopg.errors.DivisionByZero,
             'deferred': DeferredCommitError, 'python': ValueError}[failure]
    with pytest.raises(error):
        table.update({'org': 0, 'id': 0, 'name': 'must not persist'})
        db.commit()
    db.rollback()
    db.table('audit').insert({'event': 'item skipped'})
    db.commit()
    table.update({'org': 0, 'id': 1, 'name': 'next item'})
    db.commit()
    assert persisted(observer, schema) == [
        (0, 0, 'original'), (0, 1, 'next item'), (1, 0, 'other partition')]
    assert audit_events(observer, schema) == [('item skipped',), ('updating',)]
    assert callbacks == []


def test_failed_batch_can_commit_error_log_on_system_connection(hooked_database):
    db, observer, schema = hooked_database
    table = db.table('item')
    table.fail = True
    with pytest.raises(ValueError, match='hook failure'):
        try:
            table.update({'org': 0, 'id': 0, 'name': 'must not persist'})
        finally:
            with db.tempEnv(connectionName='system'):
                db.table('audit').insert({'event': 'batch failed'})
                db.commit()
    assert audit_events(observer, schema) == [('batch failed',)]
    db.rollback()
    assert persisted(observer, schema)[0] == (0, 0, 'original')
    assert audit_events(observer, schema) == [('batch failed',)]


def test_handled_external_failure_can_be_saved_as_status(hooked_database):
    db, observer, schema = hooked_database

    def prepare_status(record, old_record=None):
        try:
            raise OSError('SMTP unavailable')
        except OSError as error:
            record['name'] = str(error)

    db.table('item').trigger_onUpdating = prepare_status
    db.table('item').update({'org': 0, 'id': 0, 'name': 'sending'})
    db.commit()
    assert persisted(observer, schema)[0] == (0, 0, 'SMTP unavailable')
    assert audit_events(observer, schema) == [('updated',)]
