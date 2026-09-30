"""Exercise original legacy saveRecordCluster/cleanup with the core PG fixture.

The original save handler and site cleanup bodies execute unchanged. Permissions,
page storage and the record-cluster-to-single-insert bridge are fixture stubs;
this is not a full HTTP/RPC/framework integration test. The underlying write,
commit and connection methods come from python_error_oracle's legacy factory.
"""
import argparse
import ast
import hashlib
import json
from pathlib import Path
import runpy
from types import SimpleNamespace


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--legacy-root', type=Path, required=True)
    parser.add_argument('--dsn', required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    core = runpy.run_path(str(Path(__file__).with_name('python_error_oracle.py')))
    factory, source = core['legacy_factory'](args.legacy_root, args.dsn)
    from gnr.core.gnrbag import Bag
    namespace = {'public_method': lambda fn: fn, 'Bag': Bag}
    for relative, name in (
        ('gnrpy/gnr/web/_gnrbasewebpage.py', 'saveRecordCluster'),
        ('gnrpy/gnr/web/gnrwsgisite.py', 'cleanup'),
    ):
        path = args.legacy_root / relative
        raw = path.read_bytes()
        source['sha256'][relative] = hashlib.sha256(raw).hexdigest()
        methods = [n for n in ast.walk(ast.parse(raw))
                   if isinstance(n, ast.FunctionDef) and n.name == name]
        assert len(methods) == 1
        exec(compile(ast.fix_missing_locations(ast.Module(body=methods, type_ignores=[])),
                     str(path), 'exec'), namespace)
    Page = type('FixturePage', (), {'saveRecordCluster': namespace['saveRecordCluster']})
    results = {}
    for stage in ('success', 'onSaving', 'before_hook', 'after_hook', 'onSaved', 'deferredRaise'):
        with core['fixture'](factory, args.dsn) as (db, visible, write):
            original = ValueError('save failure')
            calls = []
            original_commit = db.commit

            def commit():
                calls.append('commit')
                return original_commit()

            db.commit = commit
            db.table = lambda name: db.item
            db.item.pkey = 'id'
            db.item.pkeys = ['id']
            db.item.lastTS = None
            db.item.recordCaption = lambda record, rowcaption=None: 'fixture'

            def write_cluster(record, attributes):
                db.write('insert')
                return {'id': 20, 'name': 'changed'}

            db.item.writeRecordCluster = write_cluster
            page = Page()
            page.db = db
            page.maintable = 'app.item'
            page.checkTablePermission = lambda *args: True
            page.pageStore = Bag

            def fail(*args, **kwargs):
                write('hook')
                raise original

            if stage in ('onSaving', 'onSaved'):
                setattr(page, stage, fail)
            elif stage in ('before_hook', 'after_hook'):
                setattr(db.item, 'trigger_onInserting' if stage == 'before_hook'
                        else 'trigger_onInserted', fail)
            elif stage == 'deferredRaise':
                db.item.trigger_onInserted = lambda record: db.deferredRaise(original)
            data = Bag()
            data.setItem('record', Bag({'id': 20, 'name': 'changed'}), _newrecord=True)
            write('earlier')
            try:
                response = page.saveRecordCluster(data, table='app.item')
                assert response[0] == 20
                error_type = None
            except (ValueError, RuntimeError) as error:
                error_type = type(error).__name__
                if stage != 'deferredRaise':
                    assert error is original
            result = {'error': error_type, 'commit_calls': len(calls),
                      'visible_before_cleanup': visible()}
            if stage == 'deferredRaise':
                # Pending deferred errors remain a barrier even if a caller
                # catches the first commit failure and explicitly retries.
                try:
                    db.commit()
                except RuntimeError:
                    result['explicit_retry_blocked'] = True
                else:
                    raise AssertionError('Pending error allowed a commit')
            site = SimpleNamespace(currentPage=page, db=db)
            namespace['cleanup'](site)
            result['visible_after_cleanup'] = visible()
            if stage == 'success':
                assert error_type is None
                assert result['visible_after_cleanup']['items'] == [(10, 'original'), (20, 'changed')]
                assert result['visible_after_cleanup']['audit'] == ['earlier']
            else:
                assert error_type is not None
                assert result['visible_after_cleanup'] == {'items': [(10, 'original')], 'audit': []}
                assert result['commit_calls'] == (1 if stage == 'deferredRaise' else 0)
            results[stage] = result
    args.output.write_text(json.dumps({'source': source, 'results': results}, indent=2) + '\n')
    print('6 original save/cleanup scenarios passed; all five failed saves persisted no changes.')


if __name__ == '__main__':
    main()
