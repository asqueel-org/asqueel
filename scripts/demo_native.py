"""Run the native PostgreSQL vertical in an isolated, disposable schema.

Set ASQUEEL_DEMO_DSN to a test database. No existing schema is modified.
"""
import argparse
import os
from uuid import uuid4

from asqueel import (
    CompiledQuery, PostgresCompiler, PostgresDatabase, PostgresDialect, PsycopgDriver,
    QueryCompiler, SqlBuilder, Database, resolve_model,
)


def main(*, explicit_adapters=False):
    dsn = os.environ.get('ASQUEEL_DEMO_DSN')
    if not dsn:
        raise SystemExit('Set ASQUEEL_DEMO_DSN to a test PostgreSQL database')
    schema = 'genro_demo_' + uuid4().hex
    builder = SqlBuilder()
    columns = builder.source.db('demo').schemas().schema(
        'sales', x_sql_schema=schema, x_sql_prefix=True,
    ).tables().table('customer', pkey='id').columns()
    columns.column('id', dtype='L')
    columns.column('name', dtype='T', x_ui={'label': 'Cliente'})
    model = resolve_model(builder)
    if explicit_adapters:
        driver = PsycopgDriver()
        compiler = QueryCompiler(model, PostgresDialect(), driver)
        database = Database(dsn, driver=driver)
    else:
        compiler = PostgresCompiler(model)
        database = PostgresDatabase(dsn)

    with database:
        database.execute(CompiledQuery(f'CREATE SCHEMA "{schema}"'))
        try:
            database.execute(CompiledQuery(
                f'CREATE TABLE "{schema}"."sales_customer" (id bigint PRIMARY KEY, name text)'))
            with database.transaction() as tx:
                tx.execute(compiler.insert('sales.customer', {'id': 1, 'name': 'Ada'}))
                tx.execute(compiler.update(
                    'sales.customer', {'name': "Ada, 100% Genro"},
                    where='$id = :id', params={'id': 1},
                ))
            try:
                with database.transaction() as tx:
                    tx.execute(compiler.insert('sales.customer', {'id': 2, 'name': 'Rollback'}))
                    raise RuntimeError('Demonstration rollback')
            except RuntimeError:
                pass
            result = database.execute(compiler.select('sales.customer', order_by='$id'))
            assert result.rows == [{'id': 1, 'name': 'Ada, 100% Genro'}]
            assert result.columns[1].ui['label'] == 'Cliente'
            print(result.rows)
            print('Native model, naming, compiler, synchronous CRUD and rollback passed.')
        finally:
            database.execute(CompiledQuery(f'DROP SCHEMA "{schema}" CASCADE'))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--explicit-adapters', action='store_true',
                        help='exercise the common compiler/runtime with injected adapters')
    args = parser.parse_args()
    main(explicit_adapters=args.explicit_adapters)
