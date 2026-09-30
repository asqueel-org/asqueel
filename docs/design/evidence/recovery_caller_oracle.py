"""Run selected original recovery callers against legacy and native PostgreSQL.

Caller method bodies are loaded from a pinned Git revision without editing.
Network, scheduling, table lookup and record-context helpers are fixture adapters.
Native rollbackAll maps ONLY to the selected single-store session's rollback;
this does not certify multi-store, full framework or integration-adapter support.
"""
import argparse
import ast
from contextlib import contextmanager, redirect_stdout
from datetime import datetime
import hashlib
import io
import json
import logging
import os
from pathlib import Path
import runpy
from smtplib import SMTPConnectError
import subprocess
from types import SimpleNamespace


CALLERS = {
    'imap': ('projects/gnrcore/packages/email/lib/imap.py', 'ImapReceiver', 'receive'),
    'upgrade': ('projects/gnrcore/packages/sys/model/upgrade.py', 'Table', 'runUpgrade'),
    'batch': ('gnrpy/gnr/web/batch/btcbase.py', 'BaseResourceBatch', '__call__'),
    'smtp': ('projects/gnrcore/packages/email/model/message.py', 'Table', 'sendMessage'),
    'logger': ('gnrpy/gnr/core/loghandlers/gnrapp.py', 'GnrAppLoggingHandler', '_process_record'),
}


def load_callers(root, revision, bag):
    methods, hashes = {}, {}
    for key, (relative, cls_name, method_name) in CALLERS.items():
        raw = subprocess.check_output(['git', '-C', str(root), 'show', f'{revision}:{relative}'])
        hashes[relative] = hashlib.sha256(raw).hexdigest()
        cls = next(n for n in ast.parse(raw).body if isinstance(n, ast.ClassDef) and n.name == cls_name)
        method = next(n for n in cls.body if isinstance(n, ast.FunctionDef) and n.name == method_name)
        logger = logging.getLogger('recovery_caller_oracle')
        logger.addHandler(logging.NullHandler())
        logger.propagate = False
        namespace = dict(Bag=bag, logger=logger, datetime=datetime, os=os,
                         SMTPConnectError=SMTPConnectError, public_method=lambda fn: fn)
        module = ast.Module(body=[ast.ImportFrom(module='__future__',
                            names=[ast.alias(name='annotations')], level=0), method], type_ignores=[])
        exec(compile(ast.fix_missing_locations(module), relative, 'exec'), namespace)
        methods[key] = namespace[method_name]
    return methods, hashes


class Facade:
    """Adapt fixture tables to the original callers; preserve transaction boundaries."""
    rootstore = '_main_db'

    def __init__(self, backend, kind):
        self.backend = backend
        self.kind = kind
        self.tables = {}
        self.rollbacks = 0
        self.application = SimpleNamespace(site=SimpleNamespace(debug=False))

    def __getattr__(self, name):
        return getattr(self.backend, name)

    def table(self, name):
        return self.tables[name]

    def rollbackAll(self):
        self.rollbacks += 1
        if self.kind == 'legacy':
            return self.backend.rollbackAll()
        return self.backend.rollback()  # Single store and selected named session only.

    def insert(self, record):
        values = {'id': record['id'], 'name': record.get('name', 'fixture')}
        if self.kind == 'legacy':
            return self.backend.insert(self.backend.item, values)
        return self.backend.item.insert(values)


def inject_failure(db, write, kind, record_id):
    def hook(record):
        if record['id'] != record_id:
            return
        write('hook')
        if kind == 'sql':
            db.execute('SELECT 1 / 0')
        elif kind == 'deferred':
            db.deferredRaise(ValueError('fixture failure'))
        else:
            raise ValueError('fixture failure')
    db.backend.item.trigger_onInserted = hook


def imap_case(method, db, write, failure):
    inject_failure(db, write, failure, 2)
    checkpoints = []
    db.tables['email.mailbox'] = SimpleNamespace(readColumns=lambda **kw: 'mailbox')
    receiver = SimpleNamespace(
        db=db, username='fixture', password='fixture', account_id='account', last_uid=None,
        messages_table=SimpleNamespace(checkDuplicate=lambda **kw: False, insert=db.insert),
        account_table=SimpleNamespace(update=lambda record: checkpoints.append(int(record['last_uid']))),
        imap=SimpleNamespace(login=lambda *a: None, select=lambda *a: None,
                             uid=lambda *a: ('OK', [b'1 2 3'])),
        createMessageRecord=lambda uid, mailbox: {'id': int(uid), 'name': 'message'},
    )
    method(receiver)
    return {'rollbacks': db.rollbacks, 'checkpoints': checkpoints}


def upgrade_case(method, db, write, failure):
    inject_failure(db, write, failure, 20)
    recorded = {}

    def upgrade(target):
        target.insert({'id': 20, 'name': 'upgrade'})

    @contextmanager
    def record_context(*args, **kwargs):
        yield recorded
        write('recovered')

    table = SimpleNamespace(db=db, upgradePath=lambda key: 'fixture', recordToUpdate=record_context)
    method.__globals__['gnrImport'] = lambda path: SimpleNamespace(main=upgrade)
    error = method(table, 'fixture|upgrade')
    return {'rollbacks': db.rollbacks, 'reported_error': bool(error),
            'recorded_error': bool(recorded.get('error'))}


def batch_case(method, db, write, bag):
    inject_failure(db, write, 'python', 20)
    failures = []
    batch = SimpleNamespace(
        db=db, batch_dblog=True, batch_log_id='log', batch_title='fixture',
        batch_local_cache=True, batch_hidden_transaction=True, batch_debug=bag(),
        tblobj=SimpleNamespace(fullname='app.item'),
        batch_logtbl=SimpleNamespace(newrecord=lambda **kw: kw, insert=lambda row: write('recovered')),
        run=lambda: db.insert({'id': 20, 'name': 'batch'}),
        result_handler=lambda: (None, None),
        page=SimpleNamespace(isDeveloper=lambda: False),
        batch_log_write=lambda message: None,
        btc=SimpleNamespace(exception_stopped=InterruptedError,
                            batch_error=lambda **kw: failures.append(kw['error'])),
    )
    method(batch)
    return {'reported_error': failures, 'selected_connection': db.currentConnectionName}


def smtp_case(method, db, bag):
    def fail(**kwargs):
        raise ValueError('SMTP service failure')
    prefs = {key: None for key in ('system_debug_address', 'from_address', 'smtp_host',
                                  'port', 'user', 'password', 'ssl', 'tls')}
    message = {key: None for key in ('extra_headers', 'bcc_address', 'cc_address', 'from_address',
                                    'weak_attachments', 'sending_attempt')}
    message.update(id=20, account_id='account', to_address='nobody@example.invalid',
                   subject='fixture', html=False)
    removed = []
    db.application.site.getService = lambda name: SimpleNamespace(sendmail=fail)
    db.tables['email.account'] = SimpleNamespace(getSmtpAccountPref=lambda account: prefs)
    db.tables['email.message_atc'] = SimpleNamespace(query=lambda **kw: SimpleNamespace(fetch=lambda: []))
    db.tables['email.message_to_send'] = SimpleNamespace(removeMessageFromQueue=lambda key: removed.append(key))

    @contextmanager
    def record_context(*args, **kwargs):
        yield message
        # The original table helper writes only when the context exits normally.
        db.insert({'id': 20, 'name': message['error_msg']})

    table = SimpleNamespace(db=db, recordToUpdate=record_context,
                            record=lambda *a, **kw: SimpleNamespace(output=lambda mode: {'message_to_send': True}),
                            getBody=lambda msg: 'body', newUTCDatetime=datetime.now)
    result = method(table, pkey=20)
    assert isinstance(result['sending_attempt'], bag)
    return {'reported_error': result['error_msg'], 'removed_from_queue': removed,
            'rollbacks': db.rollbacks}


def logger_case(method, db, write, failure):
    inject_failure(db, write, failure, 1)
    db.tables['fixture_log'] = SimpleNamespace(insert=db.insert)
    handler = SimpleNamespace(gnrapp=SimpleNamespace(db=db), table_name='fixture_log')
    output = io.StringIO()
    with redirect_stdout(output):
        method(handler, SimpleNamespace(id=1, name='failed log'))
        method(handler, SimpleNamespace(id=2, name='next log'))
    return {'reported_failures': len(output.getvalue().splitlines()), 'rollbacks': db.rollbacks}


def run_cases(core, methods, factory, dsn, kind, bag):
    results = {}
    cases = [('imap', f) for f in ('python', 'sql', 'deferred')]
    cases += [('upgrade', f) for f in ('python', 'deferred')]
    cases += [('batch', 'python'), ('smtp', 'external')]
    cases += [('logger', f) for f in ('python', 'sql')]
    for caller, failure in cases:
        with core['fixture'](factory, dsn) as (backend, visible, write):
            db = Facade(backend, kind)
            if caller == 'imap':
                result = imap_case(methods[caller], db, write, failure)
            elif caller == 'upgrade':
                result = upgrade_case(methods[caller], db, write, failure)
            elif caller == 'batch':
                result = batch_case(methods[caller], db, write, bag)
            elif caller == 'smtp':
                result = smtp_case(methods[caller], db, bag)
            else:
                result = logger_case(methods[caller], db, write, failure)
            result['visible_before_cleanup'] = visible()
            db.close()
            result['visible_after_cleanup'] = visible()
            results[f'{caller}/{failure}'] = result
    return results


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--legacy-root', type=Path, required=True)
    parser.add_argument('--dsn', required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    core = runpy.run_path(str(Path(__file__).with_name('python_error_oracle.py')))
    legacy_factory, source = core['legacy_factory'](args.legacy_root, args.dsn)
    from gnr.core.gnrbag import Bag
    methods, hashes = load_callers(args.legacy_root, source['commit'], Bag)
    source['caller_sha256'] = hashes
    native_factory, _ = core['native_factory'](args.dsn)
    legacy = run_cases(core, methods, legacy_factory, args.dsn, 'legacy', Bag)
    native = run_cases(core, methods, native_factory, args.dsn, 'native', Bag)
    result = {'source': source, 'legacy': legacy, 'native': native,
              'different_cases': [key for key in legacy if legacy[key] != native[key]]}
    for results in (legacy, native):
        for failure in ('python', 'sql', 'deferred'):
            row = results[f'imap/{failure}']
            assert row['visible_after_cleanup'] == {
                'items': [(1, 'message'), (3, 'message'), (10, 'original')], 'audit': []}
            assert row['checkpoints'] == ([1, 2, 2, 3, 3] if failure == 'deferred' else [1, 2, 3, 3])
            assert row['rollbacks'] == 1
        for failure in ('python', 'deferred'):
            row = results[f'upgrade/{failure}']
            assert row['reported_error'] and row['recorded_error']
            assert row['visible_after_cleanup'] == {'items': [(10, 'original')], 'audit': ['recovered']}
        row = results['batch/python']
        assert row['reported_error'] == ['fixture failure']
        assert row['visible_before_cleanup'] == row['visible_after_cleanup'] == {
            'items': [(10, 'original')], 'audit': ['recovered']}
        assert results['smtp/external']['visible_after_cleanup']['items'] == [
            (10, 'original'), (20, 'SMTP service failure')]
        assert results['logger/sql']['visible_after_cleanup'] == {
            'items': [(2, 'next log'), (10, 'original')], 'audit': []}
    assert result['different_cases'] == ['logger/python']
    assert legacy['logger/python']['visible_after_cleanup'] == {
        'items': [(1, 'failed log'), (2, 'next log'), (10, 'original')], 'audit': ['hook']}
    assert native['logger/python']['visible_after_cleanup'] == {'items': [(10, 'original')], 'audit': []}
    args.output.write_text(json.dumps(result, indent=2) + '\n')
    print('9 original-caller scenarios per backend verified; only logger/Python failure differs.')


if __name__ == '__main__':
    main()
