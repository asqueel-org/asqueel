"""Read-only comparison of existing compilers; no production monkeypatching.

Usage (from repository root):
 PYTHONPATH=src venv/bin/python docs/design/probes/compare_scanners.py \
   --legacy /tmp/asqueel-formula-baseline/legacy \
   --legacy-site /tmp/asqueel-formula-baseline/env/lib/python3.12/site-packages \
   --out docs/design/evidence/scanner-comparison --postgres --benchmark

PostgreSQL creates only session-local TEMP tables; SQLite uses :memory:.
Legacy execute is called with a recording cursor to capture the real argument
preparation, including escaped prefixes/colons. Compilation itself cannot
connect: its adapter connection methods and Asqueel drivers are guarded.
"""
from __future__ import annotations
import argparse
from copy import deepcopy
from decimal import Decimal
import gc
import hashlib
import json
import os
from pathlib import Path
import platform
import statistics
import sys
import time
from types import SimpleNamespace

from scanner_corpus import CASES, FIELDS, ROWS, CUSTOMERS


def encode(value):
    if isinstance(value, Decimal):
        return {'type':'Decimal','value':str(value)}
    raise TypeError(type(value).__name__)


def normal(value):
    if isinstance(value, Decimal):
        return int(value) if value == int(value) else float(value)
    if isinstance(value,(list,tuple)):
        return [normal(v) for v in value]
    return value


class Capture:
    def __init__(self):
        self.connection=SimpleNamespace(committed=True)
    def execute(self, sql, params):
        self.sql,self.params=sql,params


def deny(*args,**kwargs):
    raise AssertionError('Compiler attempted I/O')


def models(dialect,include_tree=False):
    from gnr.sql.gnrsql import GnrSqlDb
    from asqueel import SqlDatabaseConfig
    legacy=GnrSqlDb(implementation='postgres' if dialect=='postgresql' else 'sqlite',dbname='unused')
    schema='pg_temp' if dialect=='postgresql' else 'main'
    lpkg=legacy.model.src.package('app',sqlschema=schema,sqlprefix=True)
    config=SqlDatabaseConfig()
    root=config.source.db('scanner_probe',implementation=dialect)
    apkg=root.packages().package('app',sqlschema=schema,sqlprefix=True)
    for pkg in (lpkg,apkg):
        customer=pkg.table('customer',pkey='id')
        customer.column('id',dtype='L')
        customer.column('name',dtype='T')
        table=pkg.table('invoice',pkey='id')
        for name,dtype in FIELDS:
            col=table.column(name,dtype=dtype)
            if name=='customer_id':
                col.relation('app.customer.id')
    legacy.startup()
    current=config.render()
    legacy.adapter.connect=deny
    legacy.adapter.connection=deny
    current.driver.connect=deny
    if include_tree:
        from asqueel import SqlDatabase
        from asqueel.configuration import _owned_handler
        tree=SqlDatabase(model=config.render(mode='objects_tree'),config=_owned_handler(config))
        tree.driver.connect=deny
        return legacy,current,tree
    return legacy,current


def compile_case(db,engine,case):
    options=deepcopy(case['options'])
    options.pop('execute',None)
    params=deepcopy(case['params'])
    query=db.table('app.invoice').query(columns=case['columns'],where=case['where'],
        sqlparams=params,**options,**({'addPkeyColumn':False} if engine=='legacy' else {}))
    if engine=='legacy':
        raw=query.sqltext
        capture=Capture()
        db.execute(raw,query.sqlparams,cursor=capture)
        return {'sql':capture.sql,'params':capture.params,'raw_sql':raw,
                'input_after':params}
    compiled=query.compiled
    return {'sql':compiled.sql,'params':dict(compiled.params),
            'input_parameters':compiled.input_parameters,'input_after':params,
            'result_columns':[c.name for c in compiled.columns]}


def connect(dialect,engine):
    if dialect=='sqlite':
        import sqlite3
        from gnr.sql.adapters.gnrsqlite import GnrSqliteConnection
        if engine=='legacy':
            return sqlite3.connect(':memory:',factory=GnrSqliteConnection,
                                   detect_types=sqlite3.PARSE_DECLTYPES | sqlite3.PARSE_COLNAMES)
        from asqueel.drivers.sqlite import SqliteDriver
        return SqliteDriver().connect(':memory:')
    params={k:os.environ.get(env,default) for k,env,default in (
        ('host','GNR_TEST_PG_HOST','127.0.0.1'),('port','GNR_TEST_PG_PORT','5432'),
        ('user','GNR_TEST_PG_USER','postgres'))}
    if os.environ.get('GNR_TEST_PG_PASSWORD'):
        params['password']=os.environ['GNR_TEST_PG_PASSWORD']
    # Session-local data, no persistent CREATE/DROP/ALTER DATABASE or schema.
    if engine=='legacy':
        import psycopg2
        conn=psycopg2.connect(dbname='postgres',**params)
        conn.autocommit=True
        return conn
    import psycopg
    return psycopg.connect(dbname='postgres',autocommit=True,**params)


def populate(conn,dialect):
    cursor=conn.cursor()
    temp='TEMP' if dialect=='postgresql' else ''
    cursor.execute(f'CREATE {temp} TABLE app_customer (id INTEGER PRIMARY KEY,name TEXT)')
    definitions=','.join('"'+name+'" '+('INTEGER' if dtype=='L' else 'NUMERIC' if dtype=='N' else 'TEXT') for name,dtype in FIELDS)
    cursor.execute(f'CREATE {temp} TABLE app_invoice ({definitions})')
    placeholder='%s' if dialect=='postgresql' else '?'
    cursor.executemany('INSERT INTO app_customer VALUES ('+','.join([placeholder]*2)+')',CUSTOMERS)
    cursor.executemany('INSERT INTO app_invoice VALUES ('+','.join([placeholder]*len(FIELDS))+')',ROWS)
    cursor.close()
    conn.commit()


def execute(conn,dialect,engine,compiled):
    params=deepcopy(compiled['params'])
    if dialect=='sqlite' and engine=='legacy':
        from gnr.sql.adapters.gnrsqlite import GnrSqliteCursor
        cursor=conn.cursor(GnrSqliteCursor)
    else:
        cursor=conn.cursor()
    if dialect=='sqlite' and engine!='legacy':
        from asqueel.drivers.sqlite import SqliteDriver
        params={k:SqliteDriver._value(v) for k,v in params.items()}
    try:
        cursor.execute(compiled['sql'],params)
        rows=cursor.fetchall()
        return {'rows':normal(rows),'columns':[c[0] for c in cursor.description],
                'types':[[type(v).__name__ for v in row] for row in rows]}
    finally:
        cursor.close()


def compare(dbs,dialect,with_execution):
    connections={}
    if with_execution:
        for engine in ('legacy','current'):
            connections[engine]=connect(dialect,engine)
            populate(connections[engine],dialect)
    result=[]
    try:
        for case in CASES:
            if dialect not in case['dialects']:
                continue
            entry={'name':case['name'],'dialect':dialect,'origin':case['origin'],
                   'request':case,'engines':{}}
            for engine,db in zip(('legacy','current'),dbs):
                stage='compile'
                try:
                    compiled=compile_case(db,engine,case)
                    value={'compile':'ok',**compiled}
                    entry['engines'][engine]=value
                    if with_execution and case['options'].get('execute',True):
                        stage='execute'
                        value.update(execute(connections[engine],dialect,engine,compiled))
                        value['execute']='ok'
                        if case['expected'] is not None:
                            value['matches_expected']=value['rows']==case['expected']
                except Exception as exc:
                    value=entry['engines'].setdefault(engine,{})
                    value[stage]='error'
                    value['error']={'type':type(exc).__name__,'message':str(exc)}
            a,b=entry['engines']['legacy'],entry['engines']['current']
            if a.get('execute')==b.get('execute')=='ok':
                entry['same_rows']=a['rows']==b['rows']
                entry['same_columns']=a['columns']==b['columns']
                entry['same_types']=a['types']==b['types']
            entry['same_outcome']=(a.get('compile'),a.get('execute'))==(b.get('compile'),b.get('execute'))
            result.append(entry)
    finally:
        for conn in connections.values():
            conn.close()
    return result


def benchmark(dbs,dialect,with_execution):
    workloads=[
        dict(name='distinct_7',columns='$id,$amount,$unit_price,$quantity,$title,$year,$customer_id',
             where='$id=:id',params={'id':1},options={'order_by':'$id'},size=7,
             expected=[list(ROWS[0][:7])]),
        dict(name='common_select',columns='$id,$title,COALESCE($amount,0) AS amount,'
             'CASE WHEN $quantity>:n THEN 1 ELSE 0 END AS big',where='$year=:year',
             params={'year':2005,'n':2},options={'order_by':'$id'},size=4,
             expected=[[1,'Alpha',10,0],[3,'$unit_price',0,1]]),
    ]
    for size in (1,10,50,100):
        workloads.append(dict(name=f'repeated_{size}',columns=','.join(f'$amount AS c{i}' for i in range(size)),
            where='$id=:id',params={'id':1},options={'order_by':'$id'},size=size))
    workloads.append(dict(name='case_20',columns=','.join(
        f'CASE WHEN $amount>=:threshold THEN COALESCE($amount,0) ELSE 0 END AS c{i}' for i in range(20)),
        where='$id>=:id',params={'id':1,'threshold':15},options={'order_by':'$id'},size=20))
    result=[]
    engine_names=('legacy','current','tree')[:len(dbs)]
    by_engine=dict(zip(engine_names,dbs))
    for case in workloads:
        equal=None
        if with_execution:
            observed=[]
            for engine,db in by_engine.items():
                conn=connect(dialect,engine)
                try:
                    populate(conn,dialect)
                    observed.append(execute(conn,dialect,engine,compile_case(db,engine,case)))
                finally:
                    conn.close()
            expected=case.get('expected', ([[10]*case['size']] if case['name'].startswith('repeated_')
                      else [[value]*20 for value in (0,20,0,0)]))
            assert all(item['rows']==expected for item in observed)
            assert all(item['columns']==observed[0]['columns'] for item in observed)
            equal=True
        # Never benchmark a case that fails to compile on one of the engines.
        for engine,db in by_engine.items():
            for _ in range(10):
                compile_case(db,engine,case)
        samples={name:[] for name in engine_names}
        iterations=100 if case['size']<50 else 30
        for repeat in range(9):
            engines=engine_names[repeat%len(dbs):]+engine_names[:repeat%len(dbs)]
            for engine in engines:
                db=by_engine[engine]
                gc.collect()
                gc.disable()
                try:
                    start=time.perf_counter_ns()
                    for _ in range(iterations):
                        compile_case(db,engine,case)
                    elapsed=time.perf_counter_ns()-start
                finally:
                    gc.enable()
                samples[engine].append(elapsed/iterations/1000)
        medians={engine:statistics.median(values) for engine,values in samples.items()}
        result.append({'name':case['name'],'dialect':dialect,'iterations_per_round':iterations,
                       'rounds':9,'same_rows_columns_expected':equal,'microseconds_samples':samples,'median_us':medians,
                       'current_over_legacy':medians['current']/medians['legacy'],
                       'tree_over_legacy':medians.get('tree',0)/medians['legacy']})
    return result


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--legacy',type=Path,required=True)
    parser.add_argument('--legacy-site',type=Path,required=True)
    parser.add_argument('--out',type=Path,required=True)
    parser.add_argument('--postgres',action='store_true')
    parser.add_argument('--benchmark',action='store_true')
    args=parser.parse_args()
    sys.path.insert(0,str(args.legacy/'gnrpy'))
    sys.path.append(str(args.legacy_site))
    args.out.mkdir(parents=True,exist_ok=True)
    from gnr.sql.gnrsql import GnrSqlDb
    from asqueel import SqlDatabase
    results=[]
    benches=[]
    for dialect in ('sqlite','postgresql'):
        dbs=models(dialect,include_tree=args.benchmark)
        results.extend(compare(dbs[:2],dialect,dialect=='sqlite' or args.postgres))
        if args.benchmark:
            benches.extend(benchmark(dbs,dialect,dialect=='sqlite' or args.postgres))
        for db in dbs[1:]:
            db.close()
    inventory={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for directory in ('src','tests','examples')
               for p in Path(directory).rglob('*.py')}
    before=json.loads((args.out/'code-before.json').read_text())
    assert inventory==before,'Production/tests/examples changed during comparison'
    import sqlite3
    import psycopg
    import psycopg2
    metadata={'drivers':{'sqlite':sqlite3.sqlite_version,'psycopg2':psycopg2.__version__,'psycopg':psycopg.__version__},
              'python':sys.version,'platform':platform.platform(),
              'legacy_class':str(Path(sys.modules[GnrSqlDb.__module__].__file__)),
              'current_class':str(Path(sys.modules[SqlDatabase.__module__].__file__)),
              'postgres_executed':args.postgres,'code_unchanged':True,
              'benchmark_scope':'Fresh query -> driver-ready SQL/kwargs, model construction and SQL execution excluded; same Python process, alternating order, 10 warmups, GC off only while timed. Not scanner-only or query reuse timing.'}
    outputs=[('results.json',results),('metadata.json',metadata)]
    if args.benchmark:
        outputs.append(('benchmark.json',benches))
    for name,data in outputs:
        (args.out/name).write_text(json.dumps(data,indent=2,ensure_ascii=False,default=encode)+'\n')
    print(json.dumps({'cases':len(results),'benchmarks':len(benches),'unchanged':True}))


if __name__=='__main__':
    main()
