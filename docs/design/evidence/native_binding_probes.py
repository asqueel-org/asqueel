"""Execute isolated PostgreSQL binding probes; use ASQUEEL_TEST_DSN.

Creates and drops one uniquely named schema. Requires a disposable database.
Records native behavior only; this is not an executed legacy oracle.
"""
import json
import os
from uuid import uuid4

import psycopg
from psycopg import sql
from asqueel import Column, PostgresCompiler, PostgresDatabase, ResolvedModel, Table


def run():
    dsn = os.environ['ASQUEEL_TEST_DSN']
    schema = 'binding_audit_' + uuid4().hex
    results = []
    with psycopg.connect(dsn, autocommit=True) as setup:
        setup.execute(sql.SQL('CREATE SCHEMA {}').format(sql.Identifier(schema)))
        try:
            setup.execute(sql.SQL('CREATE TABLE {}.item (id integer PRIMARY KEY)').format(sql.Identifier(schema)))
            setup.execute(sql.SQL('INSERT INTO {}.item VALUES (1),(2),(3)').format(sql.Identifier(schema)))
            model = ResolvedModel({'app.item': Table('item', schema='app', sql_schema=schema,
                                  pkey=('id',), columns={'id': Column('id', 'I')})})
            compiler = PostgresCompiler(model)
            cases = [
                ('legacy_in_list', '$id IN :ids', [1, 2]),
                ('legacy_in_tuple', '$id IN :ids', (1, 2)),
                ('parenthesized_list', '$id IN (:ids)', [1, 2]),
                ('native_any_list', '$id = ANY(:ids)', [1, 2]),
                ('legacy_in_empty', '$id IN :ids', []),
                ('native_any_empty', '$id = ANY(:ids)', []),
            ]
            with PostgresDatabase(dsn) as db:
                for name, predicate, value in cases:
                    item = {'case': name, 'predicate': predicate, 'value': list(value)}
                    try:
                        query = compiler.select('app.item', columns='$id', where=predicate,
                                                sqlparams={'ids': value}, order_by='$id')
                        item['rows'] = db.execute(query).rows
                        item['status'] = 'executed'
                    except Exception as error:
                        item.update(status='error', error_type=type(error).__name__,
                                    sqlstate=getattr(error, 'sqlstate', None))
                    results.append(item)
        finally:
            setup.execute(sql.SQL('DROP SCHEMA {} CASCADE').format(sql.Identifier(schema)))
    return results


if __name__ == '__main__':
    print(json.dumps(run(), indent=2))
