"""Baseline benchmark for the query completion increment (plan 30, step 1).

Compares Asqueel with the direct driver (psycopg / sqlite3) on the same data,
on PostgreSQL and SQLite. It measures and never asserts thresholds: the JSON is
the before-image that Macro 2 phase F compares against, so the dataset, the
iteration counts and the statistic below must not change.

Model: the tutorial model in docs/guide/_examples/shop_tutorial.py.
Dataset: 2,000 customers and 10,000 invoices. Each benchmark runs one warm-up
run (excluded) and 5 timed runs; the reported value is the median run time in
seconds. Single-row benchmarks repeat the operation 500 times per run, the
10,000-row fetch 3 times. Compile-only benchmarks have no driver counterpart.
The direct driver executes the SQL text Asqueel compiled, so the comparison
isolates the Asqueel layer.

Run with ASQUEEL_DSN set to a disposable PostgreSQL database. The script creates
and drops only its own randomly named schema there, and its own temporary
directory for SQLite.
"""
import argparse
import importlib.util
import json
import os
import platform
import shutil
import sqlite3
import statistics
import sys
import tempfile
import time
from decimal import Decimal
from pathlib import Path
from uuid import uuid4

import psycopg

import asqueel
from asqueel import AsqueelDb, CompiledQuery, SqlDatabaseConfig

CUSTOMERS = 2000
INVOICES = 10000
SINGLE_ROW_ITERATIONS = 500
LARGE_FETCH_ITERATIONS = 3
RUNS = 5
WARMUP_RUNS = 1
INSERT_BASE_ID = 1_000_000

SQLITE_DDL = (
    'CREATE TABLE sales.customer (id INTEGER PRIMARY KEY, name TEXT NOT NULL)',
    'CREATE TABLE sales.invoice (id INTEGER PRIMARY KEY, '
    'customer_id INTEGER REFERENCES customer(id), total NUMERIC NOT NULL, note TEXT)',
    'CREATE TABLE sales.line (id INTEGER PRIMARY KEY, '
    'invoice_id INTEGER REFERENCES invoice(id), amount NUMERIC)',
)


def load_tutorial():
    path = Path(__file__).resolve().parents[2] / 'guide' / '_examples' / 'shop_tutorial.py'
    spec = importlib.util.spec_from_file_location('shop_tutorial', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def sqlite_shop(tutorial, path):
    class Deployment(SqlDatabaseConfig):
        def main(self, root):
            root.db('shop').connection(name=str(path), implementation='sqlite')

    return AsqueelDb(Deployment, parents=[tutorial.Shop])


def dataset():
    customers = [(i, f'Customer {i:04d}') for i in range(1, CUSTOMERS + 1)]
    invoices = [(i, (i % CUSTOMERS) + 1, str(Decimal(i % 997) + Decimal('0.50')),
                 None if i % 3 else f'Note {i}') for i in range(1, INVOICES + 1)]
    return customers, invoices


def timed(operation, iterations, reset):
    """Warm-up runs excluded; reset runs outside the timed region after each run."""
    runs = []
    for index in range(WARMUP_RUNS + RUNS):
        start = time.perf_counter()
        for step in range(iterations):
            operation(index, step)
        elapsed = time.perf_counter() - start
        reset()
        if index >= WARMUP_RUNS:
            runs.append(round(elapsed, 6))
    return {'median': round(statistics.median(runs), 6), 'runs': runs}


def benchmarks(db, driver):
    """Yield (name, iterations, asqueel operation, asqueel reset, driver op or None)."""
    invoice = db.table('sales.invoice')
    customer = db.table('sales.customer')

    def compile_simple(index, step):
        invoice.query(columns='$id, $total', where='$id = :id', params={'id': 1}).compiled

    def compile_complex(index, step):
        invoice.query(columns='$id, @customer.name AS customer_name, $line_total, $has_lines',
                      where='$id = :id', params={'id': 1}).compiled

    yield 'compile_simple', SINGLE_ROW_ITERATIONS, compile_simple, db.rollback, None
    yield 'compile_relation_two_subqueries', SINGLE_ROW_ITERATIONS, compile_complex, db.rollback, None

    repeated = invoice.query(columns='$id, $total, $note', where='$id = :id', params={'id': 42})
    repeated_sql = repeated.compiled

    def driver_fetch(index, step):
        driver.execute(repeated_sql.sql, dict(repeated_sql.params)).fetchall()

    yield ('repeated_fetch_same_query', SINGLE_ROW_ITERATIONS,
           lambda index, step: repeated.fetch(), db.rollback, driver_fetch)

    record_sql = customer.record(1).query.compiled

    def asqueel_record(index, step):
        customer.record(step % CUSTOMERS + 1, mode='dict')

    def driver_record(index, step):
        params = {name: step % CUSTOMERS + 1 for name in record_sql.params}
        driver.execute(record_sql.sql, params).fetchone()

    yield 'record_pkey', SINGLE_ROW_ITERATIONS, asqueel_record, db.rollback, driver_record

    insert_sql = db.compiler.insert('sales.customer', {'id': 0, 'name': ''})
    param_by_value = {value: name for name, value in insert_sql.params.items()}
    id_param, name_param = param_by_value[0], param_by_value['']

    def new_id(index, step):
        return INSERT_BASE_ID + index * SINGLE_ROW_ITERATIONS + step

    def asqueel_insert(index, step):
        customer.insert({'id': new_id(index, step), 'name': 'Bench'})

    def driver_insert(index, step):
        driver.execute(insert_sql.sql, {id_param: new_id(index, step), name_param: 'Bench'}).fetchall()

    yield 'insert_single_row', SINGLE_ROW_ITERATIONS, asqueel_insert, db.rollback, driver_insert

    large = invoice.query(columns='$id, $total, @customer.name AS customer_name', order_by='$id')
    large_sql = large.compiled

    def asqueel_large(index, step):
        rows = large.fetch()
        assert len(rows) == INVOICES

    def driver_large(index, step):
        rows = driver.execute(large_sql.sql, dict(large_sql.params)).fetchall()
        assert len(rows) == INVOICES

    yield ('fetch_10000_rows_to_one_join', LARGE_FETCH_ITERATIONS, asqueel_large, db.rollback,
           driver_large)


def measure(db, driver):
    results = {}
    for name, iterations, operation, reset, driver_operation in benchmarks(db, driver):
        db.rollback()
        entry = {'iterations': iterations, 'asqueel_s': timed(operation, iterations, reset),
                 'driver_s': None, 'ratio': None}
        if driver_operation is not None:
            entry['driver_s'] = timed(driver_operation, iterations, driver.rollback)
            entry['ratio'] = round(entry['asqueel_s']['median'] / entry['driver_s']['median'], 3)
        results[name] = entry
    db.rollback()
    return results


def run_postgres(tutorial, dsn):
    schema = 'genro_tutorial_' + uuid4().hex
    with tutorial.open_shop(dsn, schema) as db:
        try:
            tutorial.create_tables(db, schema)
            customers, invoices = dataset()
            with psycopg.connect(dsn) as driver:
                with driver.cursor() as cursor:
                    cursor.executemany(f'INSERT INTO "{schema}".customer VALUES (%s, %s)',
                                       customers)
                    cursor.executemany(f'INSERT INTO "{schema}".invoice VALUES (%s, %s, %s, %s)',
                                       invoices)
                driver.commit()
                server_version = driver.execute('SHOW server_version').fetchone()[0]
                driver.rollback()
                results = measure(db, driver)
            return results, server_version
        finally:
            db.rollback()
            db.execute(CompiledQuery(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE'))
            db.commit()


def run_sqlite(tutorial):
    directory = Path(tempfile.mkdtemp(prefix='asqueel_benchmark_'))
    path = directory / 'shop.db'
    try:
        db = sqlite_shop(tutorial, path)
        try:
            for statement in SQLITE_DDL:
                db.execute(statement)
            db.commit()
            driver = sqlite3.connect(path)
            try:
                driver.execute('ATTACH DATABASE ? AS sales', (str(directory / 'shop_sales.db'),))
                customers, invoices = dataset()
                driver.executemany('INSERT INTO sales.customer VALUES (?, ?)', customers)
                driver.executemany('INSERT INTO sales.invoice VALUES (?, ?, ?, ?)', invoices)
                driver.commit()
                return measure(db, driver)
            finally:
                driver.close()
        finally:
            db.close()
    finally:
        shutil.rmtree(directory)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('--output', help='write the JSON here instead of stdout')
    args = parser.parse_args(argv)
    dsn = os.environ.get('ASQUEEL_DSN')
    if not dsn:
        raise SystemExit('Set ASQUEEL_DSN to a disposable PostgreSQL database')
    tutorial = load_tutorial()
    postgres_results, server_version = run_postgres(tutorial, dsn)
    sqlite_results = run_sqlite(tutorial)
    document = {
        'generated_by': 'docs/design/evidence/query_benchmark.py',
        'configuration': {
            'model': 'docs/guide/_examples/shop_tutorial.py',
            'dataset': {'customers': CUSTOMERS, 'invoices': INVOICES},
            'iterations': {'single_row': SINGLE_ROW_ITERATIONS,
                           'fetch_10000_rows': LARGE_FETCH_ITERATIONS},
            'runs': RUNS, 'warmup_runs': WARMUP_RUNS, 'statistic': 'median seconds per run',
        },
        'versions': {'python': platform.python_version(), 'asqueel': asqueel.__version__,
                     'psycopg': psycopg.__version__, 'sqlite': sqlite3.sqlite_version,
                     'postgresql': server_version},
        'results': {'postgresql': postgres_results, 'sqlite': sqlite_results},
    }
    text = json.dumps(document, indent=2) + '\n'
    if args.output:
        Path(args.output).write_text(text, encoding='utf-8')
    else:
        sys.stdout.write(text)


if __name__ == '__main__':
    main()
