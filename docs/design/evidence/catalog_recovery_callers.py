"""Inventory lexical recovery candidates in tracked legacy Python sources.

This is an auditable search index, not control-flow or alias analysis. Each try
is reported with calls in its body, handlers, else and finally, plus syntactically
later calls in its enclosing scope. Nested functions get separate scope names.
False positives and syntax failures remain visible for manual classification.
"""
import argparse
import ast
from collections import Counter
import hashlib
import json
import io
import tarfile
from pathlib import Path
import subprocess

WRITES = {'insert', 'insertMany', 'update', 'delete', 'raw_insert', 'raw_update',
          'raw_delete', 'batchUpdate', 'batchDelete', 'writeRecordCluster',
          'saveRecordCluster', 'recordToUpdate', 'insertOrUpdate', 'execute',
          'executeDeferred', '_invoke_deferred_cbs', 'protect_update', 'protect_delete'}
BOUNDARIES = {'commit', 'rollback', 'rollbackAll', 'closeConnection', 'autoCommit',
              'deferToCommit', 'deferAfterCommit', 'deferredRaise'}


def walk_scope(nodes):
    for node in nodes:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Lambda)):
            continue
        yield node
        yield from walk_scope(ast.iter_child_nodes(node))


def calls(nodes):
    return [{'line': n.lineno, 'call': ast.unparse(n.func)}
            for n in walk_scope(nodes) if isinstance(n, ast.Call)
            and isinstance(n.func, ast.Attribute) and n.func.attr in WRITES | BOUNDARIES]


def inventory(root):
    revision = subprocess.check_output(['git', '-C', str(root), 'rev-parse', 'HEAD'], text=True).strip()
    archive = subprocess.check_output(['git', '-C', str(root), 'archive', revision, '*.py'])
    with tarfile.open(fileobj=io.BytesIO(archive)) as tree_archive:
        sources = {member.name: tree_archive.extractfile(member).read()
                   for member in tree_archive.getmembers() if member.isfile()}
    paths = sorted(sources)
    failures = []
    candidates = []
    hashes = {}
    total_handlers = 0

    def visit_scope(nodes, scope, relative):
        nonlocal total_handlers
        all_calls = calls(nodes)
        has_boundary = any(c['call'].split('.')[-1] in BOUNDARIES for c in all_calls)
        for node in walk_scope(nodes):
            if not isinstance(node, (ast.Try, ast.TryStar)):
                continue
            total_handlers += len(node.handlers)
            body_calls = calls(node.body)
            handler_calls = calls(node.handlers)
            if not (body_calls or handler_calls or has_boundary
                    or scope.split('.')[-1].startswith(('trigger_', 'onCommitting'))):
                continue
            candidates.append({
                'file': relative, 'scope': scope, 'try_line': node.lineno,
                'body_calls': body_calls,
                'handlers': [{'line': h.lineno,
                              'type': ast.unparse(h.type) if h.type else 'bare',
                              'calls': calls(h.body),
                              'exits': [{'line': n.lineno, 'kind': type(n).__name__}
                                        for n in walk_scope(h.body)
                                        if isinstance(n, (ast.Raise, ast.Return, ast.Continue, ast.Break))]}
                             for h in node.handlers],
                'else_calls': calls(node.orelse), 'finally_calls': calls(node.finalbody),
                'later_calls': [c for c in all_calls if c['line'] > node.end_lineno],
            })
        # Traverse definitions even when they occur inside a conditional/try.
        def definitions(items):
            for n in items:
                if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                    visit_scope(n.body, f'{scope}.{n.name}' if scope else n.name, relative)
                else:
                    definitions(ast.iter_child_nodes(n))
        definitions(nodes)

    for relative in paths:
        try:
            raw = sources[relative]
            hashes[relative] = hashlib.sha256(raw).hexdigest()
            tree = ast.parse(raw, filename=relative)
        except (OSError, SyntaxError) as error:
            failures.append({'file': relative, 'error': str(error)})
            continue
        visit_scope(tree.body, '', relative)
    return {'revision': revision, 'tracked_python_files': len(paths),
            'parsed_files': len(paths) - len(failures), 'handler_count': total_handlers,
            'worktree_changes_excluded': subprocess.check_output(
                ['git', '-C', str(root), 'status', '--porcelain', '--', '*.py'], text=True).splitlines(),
            'syntax_or_read_failures': failures,
            'candidate_count': len(candidates),
            'candidate_source_sha256': {p: hashes[p] for p in sorted({c['file'] for c in candidates})},
            'candidates': candidates}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('legacy_root', type=Path)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    result = inventory(args.legacy_root)
    args.output.write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps({k: v for k, v in result.items() if k not in ('candidates', 'candidate_source_sha256')}, indent=2))
    print('Candidate roots:', dict(Counter(c['file'].split('/')[0] for c in result['candidates'])))


if __name__ == '__main__':
    main()
