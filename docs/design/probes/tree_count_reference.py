"""Freeze count contracts from legacy only; inventory experimental count blocks."""
import ast
import hashlib
import json
import sys

from rewrite_phase1_cases import case
from rewrite_phase1_compare import ROOT, SNAPSHOTS, compile_case, databases

CASES = [
    case('plain', 'invoice', '$id,$total', 'TestPhysicalColumns', count=True),
    case('where', 'invoice', '$id', 'TestWhereOrderBy', count=True,
         where='$total>:minimum', params={'minimum': 100}),
    case('empty', 'invoice', '$id', 'TestPhysicalColumns', count=True, where='1=0'),
    case('to_one', 'invoice', '$id,@customer_id.account_name', 'TestRelationNavigation', count=True,
         where='@customer_id.account_name IS NOT NULL'),
    case('projection_only', 'invoice', '@customer_id.account_name', 'SqlQueryCompiler.compiledQuery', count=True),
    case('group', 'invoice', '$customer_id,SUM($total) AS sum_total', 'TestCompiledQueryOptions', count=True,
         group_by='$customer_id'),
    case('having', 'invoice', '$customer_id,SUM($total) AS sum_total', 'TestGroupByHaving', count=True,
         group_by='$customer_id', having='SUM($total)>:minimum', params={'minimum': 100}),
    case('empty_group', 'invoice', '$customer_id,SUM($total) AS sum_total', 'TestCompiledQueryOptions', count=True,
         group_by='$customer_id', where='1=0'),
    case('group_relation', 'invoice', '@customer_id.account_name,SUM($total) AS n', 'TestGroupByHaving', count=True,
         group_by='@customer_id.account_name', having='SUM($total)>0'),
    case('distinct', 'invoice', '$customer_id', 'TestCompiledQueryOptions', count=True, distinct=True),
    case('distinct_relation', 'invoice', '@customer_id.account_name', 'TestCompiledQueryOptions', count=True, distinct=True),
    case('distinct_formula', 'invoice_row', '$line_total', 'TestFormulaSql', count=True, distinct=True),
    case('empty_distinct', 'invoice', '$customer_id', 'TestCompiledQueryOptions', count=True, distinct=True, where='1=0'),
    case('group_star', 'invoice', 'SUM($total) AS n', 'TestCompiledQueryOptions', count=True, group_by='*'),
    case('aggregate_projection', 'invoice', 'SUM($total) AS n', 'SqlQueryCompiler.compiledQuery', count=True),
    case('defaults', 'customer', '*', 'TestDraftField', count=True, defaults=True),
    case('mark', 'customer', '$id', 'TestExcludeLogicalDeletedMark', count=True, defaults=True, excludeLogicalDeleted='mark'),
    case('group_mark', 'customer', '$state,COUNT(*) AS n', 'TestCompiledQueryOptions', count=True, defaults=True,
         group_by='$state', excludeLogicalDeleted='mark'),
    case('distinct_mark', 'customer', '$state', 'TestCompiledQueryOptions', count=True, defaults=True,
         distinct=True, excludeLogicalDeleted='mark'),
    case('drop_order', 'invoice', '$id', 'SqlQueryCompiler.compiledQuery', count=True, order_by='@customer_id.account_name'),
    case('limit', 'invoice', '$id', 'SqlQueryCompiler.compiledQuery', count=True, limit=2),
    case('offset', 'invoice', '$id', 'SqlQueryCompiler.compiledQuery', count=True, limit=2, offset=1),
    case('distinct_limit', 'invoice', '$customer_id', 'SqlQueryCompiler.compiledQuery', count=True, distinct=True, limit=2),
]


def main():
    sys.path.insert(0, str(SNAPSHOTS/'legacy/gnrpy'))
    sys.path.append(str(SNAPSHOTS/'env/lib/python3.12/site-packages'))
    sys.path.insert(0, str(ROOT))
    evidence = ROOT/'docs/design/evidence/legacy-tree-count'
    definitions = {}
    for label in ('legacy', 'compound', 'v2', 'v3', 'v3_merged', 'v4', 'simplify', 'next'):
        path = SNAPSHOTS/label/'gnrpy/gnr/sql/gnrsqldata/compiler.py'
        tree = ast.parse(path.read_text())
        method = next(n for c in tree.body if isinstance(c, ast.ClassDef) for n in c.body
                      if isinstance(n, ast.FunctionDef) and n.name == 'compiledQuery')
        block = next(n for n in ast.walk(method) if isinstance(n, ast.If)
                     and isinstance(n.test, ast.Name) and n.test.id == 'count')
        # Only the count branch; the following addPkeyColumn else is unrelated.
        dump = ast.dump(ast.Module(body=block.body, type_ignores=[]), include_attributes=False)
        definitions[label] = dict(file=str(path), line=block.lineno,
            sha256=hashlib.sha256(dump.encode()).hexdigest(), code=ast.unparse(ast.Module(body=block.body,type_ignores=[])))
    (evidence/'branches.json').write_text(json.dumps(definitions, indent=2)+'\n')
    cases = []
    for dialect in ('sqlite', 'postgresql'):
        db = databases(dialect, legacy_only=True)['legacy']
        for request in CASES:
            cases.append(dict(dialect=dialect, request=request, expected=compile_case(db,'legacy',request)))
        db.closeConnection()
    destination = ROOT/'tests/oracles/legacy_tree_count.json'
    destination.write_text(json.dumps(dict(reference='fa35e5adfa6ad1b269f3a22a9b12c4c1ee6513ea',cases=cases),indent=2)+'\n')
    print(f'{len(cases)} frozen legacy contracts; {len(set(v["sha256"] for v in definitions.values()))} count algorithms across {len(definitions)} snapshots')


if __name__ == '__main__':
    main()
