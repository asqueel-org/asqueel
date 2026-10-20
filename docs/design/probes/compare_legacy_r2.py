"""R2: call original embedFieldPars and compiledQuery in each frozen snapshot.

The oracle is written only from the reference GenroPy outputs. No connections.
"""
import argparse
import json
from pathlib import Path
import sys
from types import SimpleNamespace


PROJECTIONS = [
    '$id', '$id,$total,$label', '$id AS code,$total AS amount',
    '$id as code, $total as amount', '$total * 2', 'COALESCE($total,0)',
    'CASE WHEN $total>0 THEN $id ELSE 0 END', '$id AS value,$total AS value',
    '$id,$total,$id', ' $id , $id ', '$id AS "code",$total AS code',
    '$id AS CamelCase', '$id AS "CamelCase"', '$id AS "display name"',
    '$id AS "a""b"', 'CAST($total AS NUMERIC)',
    'CAST($total AS NUMERIC) AS amount',
    'CAST($id AS NUMERIC),CAST($total AS NUMERIC)',
    "'$id AS text'", "' AS ' AS label", "'a,b' AS label,$id",
    '$id As code', '$id AS code AS other', '$id,\n$total',
    '$id,, $total,', '$id AS "one",$total AS "one"',
    '$id AS a, $total AS b, $total AS a', '42',
]
EMBED = [
    ('local', '$total>:threshold', {'threshold': '$id'}),
    ('local_bytes', '$total>:threshold', {'threshold': b'$id'}),
    ('relation', '$total=:price', {'price': '@customer_id.name'}),
    ('virtual', '$total=:price', {'price': '$double_total'}),
    ('unknown_column', '$total=:price', {'price': '$absent'}),
    ('unknown_relation', '$total=:price', {'price': '@absent.name'}),
    ('relation_tail', '$total=:price', {'price': '@customer_id.absent'}),
    ('prefix', ':p,:p2,:p_suffix,:p,:pé', {'p': '$id'}),
    ('unicode', ':soglia_è,:soglia_è2', {'soglia_è': '$total'}),
    ('repeated', ':p+:p+:p', {'p': '$id'}),
    ('quotes', "':p' = ':p'", {'p': '$id'}),
    ('cast', ':p::numeric', {'p': '$total'}),
    ('sql_escape', r'\:p=:p', {'p': '$id'}),
    ('escaped_column', ':p', {'p': r'\$id'}),
    ('escaped_relation', ':p', {'p': r'\@customer_id.name'}),
    ('ordinary', ':p', {'p': 3}), ('none', ':p', {'p': None}),
    ('collection', ':p', {'p': ['$id']}),
    ('unused', ':q', {'p': '$id'}), ('empty_where', '', {'p': '$id'}),
    ('non_field_text', ':p', {'p': '$id + 1'}),
    ('invalid_bytes', ':p', {'p': b'\xff'}),
]


def encode(value):
    if isinstance(value, bytes):
        return {'bytes_hex': value.hex()}
    raise TypeError(type(value).__name__)


def capture(func):
    try:
        return {'value': func()}
    except Exception as error:
        return {'error': type(error).__name__}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--snapshot', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--write-oracle', type=Path)
    args = parser.parse_args()
    sys.path.insert(0, str(args.snapshot / 'gnrpy'))
    sys.path.append('/tmp/asqueel-formula-baseline/env/lib/python3.12/site-packages')
    from gnr.sql.gnrsql import GnrSqlDb
    from gnr.sql.gnrsqldata.compiler import SqlQueryCompiler
    from asqueel._legacy_sql import embed_field_parameters
    from asqueel import SqlDatabase, SqlDatabaseConfig
    from asqueel.configuration import _owned_handler

    class LegacyColumns(dict):
        def keys(self):
            return list(super().keys())

    table = SimpleNamespace(columns=LegacyColumns(id=1, total=1),
                            virtual_columns=LegacyColumns(double_total=1),
                            relations={'@customer_id': True})
    records = []
    for name, where, params in EMBED:
        ctx = SimpleNamespace(tblobj=table, sqlparams=params.copy())
        old = capture(lambda: SqlQueryCompiler.embedFieldPars(ctx, where))
        new = capture(lambda: embed_field_parameters(where, params.copy(), table)[0])
        records.append(dict(kind='embed', name=name, where=where, params=params,
                            legacy=old, current=new))

    def denied(*args, **kwargs):
        raise AssertionError('R2 compilation attempted database I/O')

    for dialect in ('postgresql', 'sqlite'):
        legacy = GnrSqlDb(implementation='postgres' if dialect == 'postgresql' else 'sqlite', dbname='unused')
        source = SqlDatabaseConfig()
        pkg = source.source.db('r2', implementation=dialect).packages().package(
            'sales', sqlschema='main', sqlprefix=True)
        lpkg = legacy.model.src.package('sales', sqlschema='main', sqlprefix=True)
        for package in (pkg, lpkg):
            tbl = package.table('invoice', pkey='id')
            tbl.column('id', dtype='L')
            tbl.column('total', dtype='N')
            tbl.column('label', sqlname='label_sql')
        legacy.startup()
        legacy.adapter.connect = legacy.adapter.connection = denied
        with SqlDatabase(model=source.render(mode='objects_tree'), config=_owned_handler(source)) as db:
            db.driver.connect = denied
            for index, columns in enumerate(PROJECTIONS):
                def old_projection():
                    q = legacy.table('sales.invoice').query(columns=columns, addPkeyColumn=False)
                    return q.compiled.columns

                def new_projection():
                    plan = db.compiler.plan_select('sales.invoice', columns=columns)
                    return ',\n'.join(''.join(p.expression.parts) for p in plan.projections)

                old = capture(old_projection)
                new = capture(new_projection)
                records.append(dict(kind='projection', name=str(index), dialect=dialect,
                                    columns=columns, legacy=old, current=new))
        legacy.closeConnection()
    # Whitespace around the complete projection list is formatting, not syntax.
    def normalized(result):
        return {'value': result['value'].strip()} if 'value' in result else result
    mismatches = [r for r in records if normalized(r['legacy']) != normalized(r['current'])]
    report = dict(snapshot=str(args.snapshot), checks=len(records), mismatches=mismatches, records=records)
    args.output.write_text(json.dumps(report, indent=2, default=encode)+'\n')
    if args.write_oracle:
        assert args.snapshot.name == 'legacy' and not mismatches
        args.write_oracle.write_text(json.dumps(dict(reference='fa35e5ad', records=[
            {k:v for k,v in r.items() if k != 'current'} for r in records]), indent=2, default=encode)+'\n')
    print(json.dumps(dict(snapshot=args.snapshot.name, checks=len(records), mismatches=len(mismatches))))
    if mismatches:
        print(json.dumps(mismatches, indent=2, default=encode))
        raise SystemExit(1)


if __name__ == '__main__':
    main()
