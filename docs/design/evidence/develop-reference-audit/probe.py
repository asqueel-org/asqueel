import json, sqlite3
from asqueel import SqlDatabase, SqlDatabaseConfig
from asqueel.configuration import _owned_handler
from asqueel.drivers.psycopg import PsycopgDriver
from asqueel.drivers.sqlite import SqliteDriver

results = {}
def capture(name, fn):
    try: results[name] = fn()
    except Exception as e: results[name] = {'error': type(e).__name__, 'message': str(e)}
def source(backend='sqlite'):
    config = SqlDatabaseConfig()
    table = config.source.db('audit', implementation=backend).packages().package('app', sqlschema='main').table('item', pkey='id')
    table.column('id', dtype='L')
    table.column('parent_id', dtype='L').relation('app.item.id')
    return config, table

def compiled(config, columns):
    with SqlDatabase(model=config.render(mode='objects_tree'), config=_owned_handler(config)) as db:
        q = db.table('app.item').query(columns).compiled
        return {'sql': q.sql, 'params': dict(q.params)}

def this(backend):
    c,t=source(backend); t.formulaColumn('this_relation','#THIS.@parent_id.id',dtype='L')
    return compiled(c,'$this_relation')

def group():
    c,t=source(); g=t.colgroup('details')
    g.aliasColumn('label', '@parent_id.id'); g.formulaColumn('twice','$id*2',dtype='L')
    model=c.render(mode='objects_tree').table('app.item')
    return dict(groups={name:model.column(name).attributes['group'] for name in ('label','twice')}, **compiled(c,'$label,$twice'))

def override(grouped,reverse):
    c,t=source(); target=t.colgroup('details') if grouped else t
    if reverse:
        target.formulaColumn('label','42',dtype='L'); target.aliasColumn('label','@parent_id.id')
    else:
        target.aliasColumn('label','@parent_id.id'); target.formulaColumn('label','42',dtype='L')
    return compiled(c,'$label')

def reason():
    c,t=source(); t.formulaColumn('__protected_by_rule','$id>1',dtype='B')
    t.formulaColumn('__protecting_reasons',sql_formula=True)
    t.formulaColumn('__invalid_reasons',sql_formula=True)
    q=compiled(c,'$id,$__protecting_reasons AS reasons,$__invalid_reasons AS invalid')
    with sqlite3.connect(':memory:') as db:
        db.execute('CREATE TABLE app_item(id INTEGER,parent_id INTEGER)')
        db.executemany('INSERT INTO app_item VALUES (?,NULL)',[(1,),(2,)])
        rows=db.execute(q['sql'],q['params']).fetchall()
    assert rows == [(1,'',None),(2,'rule',None)], rows
    return dict(q, rows=rows)

for backend,driver in [('sqlite',SqliteDriver()),('postgresql',PsycopgDriver())]:
    capture('this_'+backend,lambda b=backend:this(b))
    for i,params in enumerate((None,{}, {'root_fkey':None})):
        def missing(p=params,d=driver,b=backend):
            q=d.prepare_sql('SELECT :root_fkey IS NULL AS missing',p,{})
            data={'sql':q.sql,'params':dict(q.params)}
            if b=='sqlite':
                with sqlite3.connect(':memory:') as conn:
                    try: data['rows']=conn.execute(q.sql,dict(q.params)).fetchall()
                    except Exception as e:data['execution_error']=type(e).__name__+': '+str(e)
            return data
        capture('missing_'+backend+'_'+str(i),missing)
capture('new_virtuals_in_colgroup',group)
for g in (False,True):
    for r in (False,True):capture('override_group_%s_reverse_%s'%(g,r),lambda g=g,r=r:override(g,r))
capture('tree_reasons_sqlite',reason)
print(json.dumps(results,indent=2))
