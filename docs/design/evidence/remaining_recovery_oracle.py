"""Bounded execution of remaining original callers, not full application porting.

Uses the existing core/Bag oracle and unchanged caller AST at its recorded
revision. Mail, filesystem, record contexts and model lookup are fixture stubs.
SQL and hook effects execute on isolated PostgreSQL; no email or extension is installed.
"""
import argparse
from contextlib import contextmanager, redirect_stdout
from datetime import datetime
import io
import json
from pathlib import Path
import runpy
from types import SimpleNamespace, MethodType


EXTRA = {
    'old_imap': ('projects/gnrcore/packages/email/lib/utils.py', 'ImapReceiver', 'receive'),
    'mail_batch': ('gnrpy/gnr/web/batch/btcmail.py', 'BaseResourceMail', '_send_one_email_legacy'),
    'extensions': ('gnrpy/gnr/sql/gnrsqlutils.py', 'SqlModelChecker', 'addExtensions'),
    'create_extensions': ('gnrpy/gnr/sql/adapters/_gnrbasepostgresadapter.py', 'PostgresSqlDbBaseAdapter', 'createExtension'),
    'visitor': ('projects/gnrcore/packages/adm/model/userobject.py', 'Table', 'checkResourceUserObject'),
}


def old_imap(method, db, write, helpers, failure):
    helpers['inject_failure'](db, write, failure, 20)
    db.tables['email.mailbox'] = SimpleNamespace(readColumns=lambda **kw: 'mailbox')

    def parse(uid):
        if uid == b'1':
            db.insert({'id': 20, 'name': 'attachment'})
            raise ValueError('parse after attachment')
        return {'id': 21, 'name': 'next message'}

    receiver = SimpleNamespace(db=db, username='fixture', password='fixture', account_id='a',
        last_uid=None, imap=SimpleNamespace(login=lambda *a: None, select=lambda *a: None,
        uid=lambda *a: ('OK', [b'1 2'])), createMessageRecord=parse,
        messages_table=SimpleNamespace(checkDuplicate=lambda **kw: False, insert=db.insert),
        account_table=SimpleNamespace(update=lambda record: None))
    with redirect_stdout(io.StringIO()):
        method(receiver)


def mail_batch(method, db, write, helpers, failure):
    helpers['inject_failure'](db, write, failure, 20)
    calls = []

    def log(record):
        calls.append('success' if record['sent_ts'] else 'error')
        db.insert({'id': 20 if record['sent_ts'] else 21, 'name': calls[-1]})

    db.tables['adm.sent_email'] = SimpleNamespace(insert=log)
    batch = SimpleNamespace(db=db, tblobj=SimpleNamespace(fullname='app.item'),
        batch_parameters={}, mail_handler=SimpleNamespace(getDefaultMailAccount=lambda: {},
        sendmail=lambda **kw: None))
    try:
        method(batch, to_address='nobody@example.invalid')
    finally:
        db.currentEnv['fixture_log_attempts'] = calls


def smtp(method, db, write, helpers, bag, failure):
    helpers['inject_failure'](db, write, failure, 30)
    prefs = {key: None for key in ('system_debug_address', 'from_address', 'smtp_host',
                                  'port', 'user', 'password', 'ssl', 'tls')}
    message = {key: None for key in ('extra_headers', 'bcc_address', 'cc_address',
                                   'from_address', 'weak_attachments', 'sending_attempt')}
    message.update(id=20, account_id='a', to_address='nobody@example.invalid', subject='fixture', html=False)
    db.application.site.getService = lambda name: SimpleNamespace(sendmail=lambda **kw: None)
    db.tables['email.account'] = SimpleNamespace(getSmtpAccountPref=lambda account: prefs)
    db.tables['email.message_atc'] = SimpleNamespace(query=lambda **kw: SimpleNamespace(fetch=lambda: []))
    attempts = []

    def remove(key):
        attempts.append(key)
        db.insert({'id': 29 + len(attempts), 'name': 'queue removal'})

    db.tables['email.message_to_send'] = SimpleNamespace(removeMessageFromQueue=remove)

    @contextmanager
    def record_context(*args, **kw):
        yield message
        db.insert({'id': 20, 'name': message.get('error_msg', 'sent')})

    table = SimpleNamespace(db=db, recordToUpdate=record_context,
        record=lambda *a, **kw: SimpleNamespace(output=lambda mode: {'message_to_send': True}),
        getBody=lambda msg: 'body', newUTCDatetime=datetime.now)
    method(table, pkey=20)


def extensions(methods, db, write):
    write('earlier')
    db.application.config = {'db?extensions': '__asqueel_nonexistent_extension_for_recovery_test__'}
    adapter = SimpleNamespace(dbroot=db, listElements=lambda kind: [],
        createExtensionSql=lambda name: f'CREATE EXTENSION "{name}"')
    adapter.createExtension = MethodType(methods['create_extensions'], adapter)
    # Adapter facade is used only by this caller; the original core driver is untouched.
    db.adapter = adapter
    methods['extensions'](SimpleNamespace(db=db))
    write('recovered')
    db.commit()


def visitor(method, db, write, failure):
    def hook(record):
        write('hook')
        if failure == 'sql':
            db.execute('SELECT 1 / 0')
        else:
            raise OSError('visitor hook')
    db.backend.item.trigger_onInserted = hook
    db.application.packages = {'fixture': SimpleNamespace(packageFolder='/fixture')}
    db.tableTreeBag = lambda **kw: {}
    real_globals = method.__globals__
    old_bag, old_os = real_globals['Bag'], real_globals['os']
    real_globals['Bag'] = lambda path: dict(pkey=20, id=20, code='x', objtype='x', pkg='fixture', tbl=None)
    real_globals['os'] = SimpleNamespace(sep='/', path=SimpleNamespace(
        join=old_os.path.join, exists=lambda path: True, isdir=lambda path: True), listdir=lambda path: ['target'])

    class Directory:
        def __init__(self, folder, **kw):
            self.custom = '_packages/target' in folder

        def __call__(self):
            return self

        def walk(self, callback, **kw):
            if self.custom:
                callback(SimpleNamespace(attr={'file_ext': 'xml', 'abs_path': '/fixture/userobjects/x.xml'}))

    real_globals['DirectoryResolver'] = Directory
    table = SimpleNamespace(db=db, uo_identifier=lambda record: 'fixture', checkDuplicate=lambda **kw: False,
        insert=lambda record: db.insert({'id': 20, 'name': 'visitor'}))
    try:
        method(table)
    finally:
        real_globals['Bag'], real_globals['os'] = old_bag, old_os


def run(core, helpers, methods, factory, dsn, kind, bag):
    results = {}
    cases = [(name, failure) for name in ('old_imap', 'mail_batch', 'smtp', 'visitor')
             for failure in ('python', 'sql')]
    cases.append(('extensions', 'sql'))
    for name, failure in cases:
        with core['fixture'](factory, dsn) as (backend, visible, write):
            db = helpers['Facade'](backend, kind)
            error = None
            try:
                if name == 'old_imap':
                    old_imap(methods[name], db, write, helpers, failure)
                elif name == 'mail_batch':
                    mail_batch(methods[name], db, write, helpers, failure)
                elif name == 'smtp':
                    smtp(methods[name], db, write, helpers, bag, failure)
                elif name == 'visitor':
                    visitor(methods[name], db, write, failure)
                else:
                    extensions(methods, db, write)
            except Exception as exc:
                error = type(exc).__name__
            before = visible()
            db.closeConnection()
            db.clearCurrentEnv()
            after = visible()
            # A subsequent request must be able to reuse this same DB/thread.
            backend.item.trigger_onInserted = lambda record: None
            db.updateEnv(user='next request')
            write('recovered')
            db.commit()
            recovered = visible()
            assert before == after  # Cleanup never adds a commit.
            assert recovered['audit'] == sorted(after['audit'] + ['recovered'])
            results[f'{name}/{failure}'] = dict(error=error, before_cleanup=before,
                after_cleanup=after, next_request=recovered)
    return results


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--legacy-root', type=Path, required=True)
    parser.add_argument('--dsn', required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    base = Path(__file__).parent
    core = runpy.run_path(str(base / 'python_error_oracle.py'))
    helpers = runpy.run_path(str(base / 'recovery_caller_oracle.py'))
    helpers['CALLERS'].update(EXTRA)
    factory, source = core['legacy_factory'](args.legacy_root, args.dsn)
    from gnr.core.gnrbag import Bag
    methods, hashes = helpers['load_callers'](args.legacy_root, source['commit'], Bag)
    source['caller_sha256'] = hashes
    native, _ = core['native_factory'](args.dsn)
    result = {'source': source, 'legacy': run(core, helpers, methods, factory, args.dsn, 'legacy', Bag),
              'native': run(core, helpers, methods, native, args.dsn, 'native', Bag)}
    # Assert the observed contract, not just successful execution of the harness.
    for kind in ('legacy', 'native'):
        for name in ('old_imap', 'mail_batch', 'smtp', 'visitor'):
            row = result[kind][f'{name}/python']
            assert row['error'] == ('TransactionStateError' if kind == 'native' else None)
            assert row['before_cleanup']['audit'] == ([] if kind == 'native' else ['hook'])
            if kind == 'native':
                assert row['before_cleanup']['items'] == [(10, 'original')]
        for name in ('old_imap', 'mail_batch', 'smtp', 'visitor', 'extensions'):
            row = result[kind][f'{name}/sql']
            assert row['error'] == ('DivisionByZero' if name == 'visitor' else None)
            assert row['before_cleanup'] == result['native'][f'{name}/sql']['before_cleanup']
    args.output.write_text(json.dumps(result, indent=2) + '\n')
    for name in result['native']:
        print(name, 'legacy:', result['legacy'][name]['error'], 'native:', result['native'][name]['error'])
    print('9 scenarios per implementation recorded; cleanup and next-request reuse verified.')


if __name__ == '__main__':
    main()
