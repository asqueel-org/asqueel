"""Compare original legacy queue methods with native Session queue dispatch.

The legacy mode executes an AST-extracted, unmodified TransactionMixin using
its real legacy Bag. This probes queues, not the complete framework/SQL commit.
Run with --legacy-root using a Python that has legacy dependencies; without it,
use the native development Python. Both modes print the same contract results.
"""
import argparse
import ast
import hashlib
import json
from pathlib import Path
from uuid import uuid4


def scenarios(backend):
    results = {}
    trace = []

    def append(value):
        trace.append(value)

    backend.defer(append, 'last', _deferredBlock='z')
    backend.defer(append, 'first', _deferredBlock='a')
    backend.defer(append, 'second', _deferredBlock='a')
    backend.drain()
    results['block_and_insertion_order'] = trace[:]
    trace.clear()

    def keyword(value):
        trace.append(value)

    first = backend.defer(keyword, value='first', _deferredId='same')
    second = backend.defer(keyword, value='ignored', _deferredId='same')
    results['shared_kwargs'] = first is second
    second['value'] = 'merged'
    backend.drain()
    results['deduplicated_values'] = trace[:]
    numeric = backend.defer(keyword, value='numeric', _deferredId=1)
    textual = backend.defer(keyword, value='textual', _deferredId='1')
    results['normalized_id'] = numeric is textual
    backend.drain()
    trace.clear()
    for empty in (None, '', 0, False):
        backend.defer(append, 'one', _deferredId=empty)
        backend.defer(append, 'two', _deferredId=empty)
    backend.drain()
    results['false_ids_are_unique'] = trace[:]

    for recursive in (False, True):
        trace.clear()

        def again():
            trace.append('call')
            if len(trace) < 3:
                backend.defer(again, _deferredId='same')

        again.deferredCommitRecursion = recursive
        backend.defer(again, _deferredId='same')
        backend.drain()
        results[f'recursive_{recursive}'] = trace[:]
    return results


def native_backend():
    from asqueel.session import Session
    from tests.application_session.test_session import Driver
    session = Session(Driver())
    session.defer = session.defer_to_commit
    session.drain = lambda: session._invoke_deferred('before')
    return session


def legacy_backend(root):
    import sys
    sys.path.insert(0, str(root / 'gnrpy'))
    from gnr.core.gnrbag import Bag
    import gnr.core.gnrbag as bag_module
    assert Path(bag_module.__file__).resolve().is_relative_to(root.resolve())
    path = root / 'gnrpy/gnr/sql/gnrsql/transactions.py'
    raw = path.read_bytes()
    cls = next(n for n in ast.parse(raw).body if isinstance(n, ast.ClassDef) and n.name == 'TransactionMixin')
    module = ast.Module(body=[ast.ImportFrom(module='__future__', names=[ast.alias(name='annotations')], level=0), cls], type_ignores=[])
    namespace = {'GnrSqlDbBaseMixin': object, 'Bag': Bag, 'getUuid': lambda: uuid4().hex}
    exec(compile(ast.fix_missing_locations(module), str(path), 'exec'), namespace)

    class Legacy(namespace['TransactionMixin']):
        QUEUE_DEFER_TO_COMMIT = 'before'
        currentEnv = {}

        def connectionKey(self):
            return 'main'

        def defer(self, callback, *args, **kwargs):
            return self.deferToCommit(callback, *args, **kwargs)

        def drain(self):
            self._invoke_deferred_cbs(self.QUEUE_DEFER_TO_COMMIT)

    return Legacy(), {'transactions_sha256': hashlib.sha256(raw).hexdigest(),
                      'bag_sha256': hashlib.sha256(Path(bag_module.__file__).read_bytes()).hexdigest()}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--legacy-root', type=Path)
    args = parser.parse_args()
    backend, source = legacy_backend(args.legacy_root) if args.legacy_root else (native_backend(), {})
    print(json.dumps({'source': source, 'results': scenarios(backend)}, indent=2))
