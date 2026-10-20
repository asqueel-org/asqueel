"""Differential ON-condition contracts, using the original fa35e5ad compiler.

Fixture adaptation: declare an additional predicate on an existing to-one
relation. Exercise root references discovered while resolving ON and parent
qualification through invoice_row. No joinConditions API or new grammar.
"""
import json
from pathlib import Path
import sys

sys.path.insert(0, '/tmp/asqueel-formula-baseline/legacy/gnrpy')
sys.path.append('/tmp/asqueel-formula-baseline/env/lib/python3.12/site-packages')
from rewrite_phase1_compare import databases, compile_case, normalized, populate, execute  # noqa: E402
from rewrite_phase1_cases import COMMON  # noqa: E402

OUT = Path(__file__).resolve().parents[1]/'evidence/legacy-rewrite-phase2/join-conditions.json'
results = []
for dialect in ('sqlite', 'postgresql'):
    dbs = databases(dialect)
    connection = populate(dbs['legacy']) if dialect == 'sqlite' else None
    try:
        for engine in ('legacy', 'tree'):
            table = dbs[engine].model.table('invc.invoice')
            condition = '$customer_id=@customer_id.id AND $total>:minimum'
            if engine == 'legacy':
                table.relations.getNode('@customer_id').attr['joiner']['join_on'] = condition
            else:
                # Native relation views are independent copies of the global
                # registry. Declare the condition there before resolving views.
                dbs[engine].model.relations.get_node('invc.invoice.@customer_id').attr['join_on'] = condition
        for name, table, columns in (
            ('on_root', 'invoice', '$id,@customer_id.account_name'),
            ('on_parent', 'invoice_row', '$id,@invoice_id.@customer_id.account_name'),
        ):
            case = dict(name=name, table='invc.'+table, columns=columns,
                        params={'minimum': 100}, defaults=False, count=False,
                        options=dict(COMMON, order_by='$id', limit=5))
            record = {'dialect': dialect, 'request': case}
            for engine in ('legacy', 'tree'):
                compiled = compile_case(dbs[engine], engine, case)
                record[engine] = compiled
                if connection:
                    compiled.update(execute(connection, compiled, count=False))
            left, right = record['legacy'], record['tree']
            assert normalized(left['sql']) == normalized(right['sql']), (left['sql'], right['sql'])
            assert {k: v for k, v in left['params'].items() if k != 'jc_kwargs'} == right['params']
            if connection:
                assert left['rows'] == right['rows']
            results.append(record)
    finally:
        if connection:
            connection.close()
        for engine in ('tree', 'current'):
            dbs[engine].close()
OUT.write_text(json.dumps(results, indent=2)+'\n')
print(f'{len(results)} ON-condition SQL/kwargs contracts passed; SQLite rows agree')
