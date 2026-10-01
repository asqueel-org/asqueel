"""Current-behaviour probes for the query completion increment (plan 30, step 1).

Each probe runs one query construct against HEAD on PostgreSQL and SQLite and
records the input, the produced SQL and parameters, the result or the exception,
and a classification (bug / missing-feature / intentional) with the source line
that justifies it. Phase 2 cites the probes by their stable ``id``.

Run with ASQUEEL_DSN set to a disposable PostgreSQL database. The script creates
and drops only its own randomly named schema there, and its own temporary
directory for SQLite. The output is deterministic: the PostgreSQL schema name is
written as ``<schema>``, SQLite file paths as ``<file>``, and an error message is
recorded as its first line.
"""
import argparse
import json
import os
import shutil
import sys
import tempfile
from decimal import Decimal
from pathlib import Path
from uuid import uuid4

from asqueel import AsqueelDb, CompiledQuery, SqlDatabaseConfig

CUSTOMERS = [(1, 'Ada'), (2, 'Grace'), (3, 'Linus')]
INVOICES = [
    (10, 1, Decimal('125.00'), 'First order'),
    (11, 2, Decimal('40.00'), None),
    (12, 1, Decimal('15.50'), 'Second order'),
    (13, None, Decimal('7.00'), 'No customer'),
]

PG_DDL = (
    'CREATE SCHEMA "{schema}"',
    'CREATE TABLE "{schema}".customer (id bigint PRIMARY KEY, name text NOT NULL)',
    'CREATE TABLE "{schema}".invoice (id bigint PRIMARY KEY, '
    'customer_id bigint REFERENCES "{schema}".customer(id), '
    'total numeric(12,2) NOT NULL, note text)',
)
SQLITE_DDL = (
    'CREATE TABLE sales.customer (id INTEGER PRIMARY KEY, name TEXT NOT NULL)',
    'CREATE TABLE sales.invoice (id INTEGER PRIMARY KEY, '
    'customer_id INTEGER REFERENCES customer(id), total NUMERIC NOT NULL, note TEXT)',
)


def declare_tables(schema_node):
    tables = schema_node.tables()
    customer = tables.table('customer', pkey='id').columns()
    customer.column('id', dtype='L')
    customer.column('name', dtype='T', notnull=True)
    invoice = tables.table('invoice', pkey='id')
    columns = invoice.columns()
    columns.column('id', dtype='L')
    columns.column('customer_id', dtype='L').relation(
        'sales.customer.id', foreign_key=True, x_name='customer')
    columns.column('total', dtype='N', size='12,2', notnull=True)
    columns.column('note', dtype='T')
    virtuals = invoice.virtual_columns()
    virtuals.formulaColumn('double_total', dtype='N', sql_formula='$total * 2')
    virtuals.aliasColumn('client_name', relation_path='@customer.name')


def postgres_recipe(dsn, schema):
    class Recipe(SqlDatabaseConfig):
        def main(self, root):
            declare_tables(root.db('probe', conninfo=dsn).schemas().schema(
                'sales', x_sql_schema=schema))
    return Recipe


def sqlite_recipe(path):
    class Recipe(SqlDatabaseConfig):
        def main(self, root):
            db = root.db('probe')
            db.connection(name=str(path), implementation='sqlite')
            declare_tables(db.schemas().schema('sales'))
    return Recipe


def seed(db):
    for row in CUSTOMERS:
        db.table('sales.customer').insert(dict(zip(('id', 'name'), row)))
    for row in INVOICES:
        db.table('sales.invoice').insert(dict(zip(('id', 'customer_id', 'total', 'note'), row)))
    db.commit()


def record(backend, construct, inputs, classification, source):
    suffix = 'pg' if backend == 'postgresql' else 'sqlite'
    return {'id': f'{construct}_{suffix}', 'backend': backend, 'input': inputs,
            'sql': None, 'params': None, 'status': None,
            'classification': classification, 'source': source}


def fail(outcome, error):
    outcome['status'] = 'error'
    outcome['error_type'] = type(error).__name__
    # psycopg appends a 'LINE n:' excerpt of the SQL (already recorded in 'sql')
    # cut at a position that splits the random schema name; keep the first line.
    outcome['error'] = str(error).split('\n', 1)[0]
    return outcome


def query_probe(db, backend, construct, classification, source, *, columns='*', where=None,
                params=None, options=None, env=None, terminal='fetch'):
    """Build the query, compile it, then run the terminal; every stage may fail."""
    options = dict(options or {})
    inputs = {'columns': columns, 'where': where, 'params': params, 'options': options,
              'terminal': terminal}
    if env is not None:
        inputs['env'] = env
    outcome = record(backend, construct, inputs, classification, source)
    try:
        with db.temp_env(**(env or {})):
            query = db.table('sales.invoice').query(columns=columns, where=where,
                                                    sqlparams=params, **options)
            if terminal == 'count':
                outcome['result'] = query.count()
                outcome['status'] = 'returned'
                return outcome
            compiled = query.compiled
            outcome['sql'] = compiled.sql
            outcome['params'] = dict(compiled.params)
            outcome['result'] = db.execute(compiled).rows
            outcome['status'] = 'returned'
    except Exception as error:
        fail(outcome, error)
    finally:
        db.rollback()
    return outcome


def recompilation_probe(db, backend):
    inputs = {'columns': '$id', 'where': '$id = :id', 'params': {'id': 10}, 'options': {},
              'terminal': 'compiled x2'}
    outcome = record(backend, 'recompilation', inputs, 'intentional',
                     'src/asqueel/application_table.py:120')
    calls = []
    compiler_select = db.compiler.select

    def counting_select(*args, **kwargs):
        calls.append(args[0])
        return compiler_select(*args, **kwargs)

    db.compiler.select = counting_select
    try:
        query = db.table('sales.invoice').query(columns='$id', where='$id = :id',
                                                sqlparams={'id': 10})
        first, second = query.compiled, query.compiled
        outcome['sql'] = first.sql
        outcome['params'] = dict(first.params)
        outcome['result'] = {'compile_calls': len(calls), 'same_object': first is second,
                             'same_sql': first.sql == second.sql,
                             'same_params': first.params == second.params}
        outcome['status'] = 'compiled_only'
    except Exception as error:
        fail(outcome, error)
    finally:
        del db.compiler.select
        db.rollback()
    return outcome


def probes(db, backend):
    collection = 'src/asqueel/compiler.py:152; docs/guide/limitations.md:185'
    any_source = 'src/asqueel/compiler.py:4'
    rejected = 'src/asqueel/application_table.py:35'
    env_source = 'src/asqueel/compiler.py:156'
    yield query_probe(db, backend, 'in_list', 'missing-feature', collection, columns='$id',
                      where='$id IN :ids', params={'ids': [10, 11]}, options={'order_by': '$id'})
    yield query_probe(db, backend, 'not_in_list', 'missing-feature', collection, columns='$id',
                      where='$id NOT IN :ids', params={'ids': [10, 11]},
                      options={'order_by': '$id'})
    yield query_probe(db, backend, 'any_list', 'intentional', any_source, columns='$id',
                      where='$id = ANY(:ids)', params={'ids': [10, 11]},
                      options={'order_by': '$id'})
    yield query_probe(db, backend, 'any_empty', 'intentional', any_source, columns='$id',
                      where='$id = ANY(:ids)', params={'ids': []}, options={'order_by': '$id'})
    yield query_probe(db, backend, 'any_none_member', 'intentional', any_source, columns='$id',
                      where='$id = ANY(:ids)', params={'ids': [10, None]},
                      options={'order_by': '$id'})
    yield query_probe(db, backend, 'relation_auto_name', 'bug',
                      'src/asqueel/compiler.py:552; docs/guide/compiler.md:128',
                      columns='$id, @customer.name', options={'order_by': '$id'})
    yield query_probe(db, backend, 'star_virtual_columns', 'missing-feature',
                      'src/asqueel/compiler.py:530; docs/guide/limitations.md:179',
                      columns='*', options={'order_by': '$id'})
    yield query_probe(db, backend, 'option_distinct', 'missing-feature', rejected,
                      columns='$customer_id', options={'distinct': True})
    yield query_probe(db, backend, 'option_group_by', 'missing-feature', rejected,
                      columns='$customer_id, SUM($total) AS total',
                      options={'group_by': '$customer_id'})
    yield query_probe(db, backend, 'option_having', 'missing-feature', rejected,
                      columns='$customer_id, SUM($total) AS total',
                      options={'group_by': '$customer_id', 'having': 'SUM($total) > 50'})
    yield query_probe(db, backend, 'option_having_only', 'missing-feature', rejected,
                      columns='SUM($total) AS total', options={'having': 'SUM($total) > 50'})
    yield query_probe(db, backend, 'count_terminal', 'missing-feature',
                      'src/asqueel/application_table.py:145', columns='$id', terminal='count')
    yield recompilation_probe(db, backend)
    yield query_probe(db, backend, 'env_present', 'intentional', env_source, columns='$id',
                      where='$customer_id = :env_customer', env={'customer': 1},
                      options={'order_by': '$id'})
    yield query_probe(db, backend, 'env_absent', 'intentional', env_source, columns='$id',
                      where='$customer_id = :env_customer', options={'order_by': '$id'})
    yield query_probe(db, backend, 'env_overridden', 'intentional', env_source, columns='$id',
                      where='$customer_id = :env_customer', params={'env_customer': 2},
                      env={'customer': 1}, options={'order_by': '$id'})


def run_postgres(dsn):
    schema = 'asqueel_probe_' + uuid4().hex
    db = AsqueelDb(postgres_recipe(dsn, schema))
    try:
        try:
            for statement in PG_DDL:
                db.execute(CompiledQuery(statement.format(schema=schema)))
            db.commit()
            seed(db)
            return list(probes(db, 'postgresql')), [schema]
        finally:
            db.rollback()
            db.execute(CompiledQuery(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE'))
            db.commit()
    finally:
        db.close()


def run_sqlite():
    directory = Path(tempfile.mkdtemp(prefix='asqueel_probe_'))
    path = directory / 'probe.db'
    try:
        db = AsqueelDb(sqlite_recipe(path))
        try:
            for statement in SQLITE_DDL:
                db.execute(statement)
            db.commit()
            seed(db)
            outcomes = list(probes(db, 'sqlite'))
        finally:
            db.close()
    finally:
        shutil.rmtree(directory)
    return outcomes, [str(directory / 'probe_sales.db'), str(path), str(directory)]


def deterministic(text, schemas, paths):
    for schema in schemas:
        text = text.replace(schema, '<schema>')
    for path in paths:
        for variant in (os.path.realpath(path), path):
            text = text.replace(variant, '<file>')
    return text


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('--output', help='write the JSON here instead of stdout')
    args = parser.parse_args(argv)
    dsn = os.environ.get('ASQUEEL_DSN')
    if not dsn:
        raise SystemExit('Set ASQUEEL_DSN to a disposable PostgreSQL database')
    pg_outcomes, schemas = run_postgres(dsn)
    sqlite_outcomes, paths = run_sqlite()
    document = {'generated_by': 'docs/design/evidence/query_completion_probes.py',
                'probes': pg_outcomes + sqlite_outcomes}
    text = json.dumps(document, indent=2, ensure_ascii=False, default=str) + '\n'
    text = deterministic(text, schemas, paths)
    if args.output:
        Path(args.output).write_text(text, encoding='utf-8')
    else:
        sys.stdout.write(text)


if __name__ == '__main__':
    main()
