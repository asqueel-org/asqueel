"""Formula select/exists acceptance with real correlations and nested policies."""
from tests.unit_of_work import completed
from uuid import uuid4

import psycopg
from psycopg import sql
import pytest

from asqueel import SqlDatabaseConfig, build_database
from tests.native_support import postgres_dsn

pytestmark = pytest.mark.postgresql


@pytest.fixture(params=['schema', 'package'])
def formula_database(request):
    schema = 'formula_subqueries_' + uuid4().hex
    dsn = postgres_dsn()
    with psycopg.connect(dsn, autocommit=True) as observer:
        observer.execute(sql.SQL('CREATE SCHEMA {}').format(sql.Identifier(schema)))
        try:
            statements = [
                'CREATE TABLE {0}.invoice (id integer PRIMARY KEY, name text)',
                'CREATE TABLE {0}.line (id integer PRIMARY KEY, invoice_id integer REFERENCES {0}.invoice(id), '
                'amount numeric, organization integer, draft boolean, deleted_at timestamptz)',
                'CREATE TABLE {0}.receipt (id integer PRIMARY KEY, invoice_id integer REFERENCES {0}.invoice(id))',
                "INSERT INTO {0}.invoice VALUES (1,'first'),(2,'second'),(3,'empty')",
                "INSERT INTO {0}.line VALUES (1,1,10,0,false,NULL),(2,1,20,0,true,NULL),"
                "(3,1,30,0,false,'2026-01-01'),(4,1,40,1,false,NULL),(5,2,7,0,false,NULL)",
                'INSERT INTO {0}.receipt VALUES (10,1),(11,2),(12,NULL)',
            ]
            for statement in statements:
                observer.execute(sql.SQL(statement).format(sql.Identifier(schema)))

            class Recipe(SqlDatabaseConfig):
                def main(self, root):
                    database = root.db('subqueries', implementation='postgres', conninfo=dsn)
                    if request.param == 'package':
                        tables = database.packages().package(
                            'app', sqlschema=schema, sqlprefix=False).tables()
                    else:
                        tables = database.schemas().schema('app', sqlname=schema).tables()
                    invoice = tables.table('invoice', pkey='id')
                    columns = invoice.columns()
                    columns.column('id', dtype='I')
                    columns.column('name', dtype='T')
                    virtual = invoice.virtual_columns()
                    total = dict(table='app.line', columns='SUM($amount)', where='$invoice_id=#THIS.id')
                    virtual.formulaColumn('total', dtype='N', select=total)
                    virtual.formulaColumn('has_lines', dtype='B', exists=dict(
                        table='app.line', where='$invoice_id=#THIS.id'))
                    virtual.formulaColumn('total_zero', dtype='N', sql_formula='COALESCE(#sum,0)',
                                          select_sum=total)
                    virtual.formulaColumn('double_total', dtype='N', select=dict(
                        table='app.line', columns='SUM($double_amount)', where='$invoice_id=#THIS.id'))
                    virtual.formulaColumn('filtered_total', dtype='N', select=dict(
                        **total, excludeDraft=True, excludeLogicalDeleted=True))
                    virtual.formulaColumn('all_total', dtype='N', select=dict(**total, ignorePartition=True))
                    virtual.formulaColumn('scoped_total', dtype='N', select=dict(**total, ignorePartition=False))
                    virtual.formulaColumn('above_threshold', dtype='N', select=dict(
                        table='app.line', columns='SUM($amount)',
                        where='$invoice_id=#THIS.id AND $amount>:threshold', sqlparams={'threshold': 15},
                        cast='numeric'))
                    virtual.formulaColumn('single_amount', dtype='N', select=dict(
                        table='app.line', columns='$amount', where='$invoice_id=#THIS.id'))
                    virtual.formulaColumn('literal_marker', dtype='T', select=dict(
                        table='app.line', columns="'#THIS.id'", where='$invoice_id=#THIS.id /* #THIS.missing */',
                        limit=1))
                    line = tables.table('line', pkey='id',
                                        partition_organization='organization',
                                        draftField='draft', logicalDeletionField='deleted_at')
                    columns = line.columns()
                    for name, dtype in [('id', 'I'), ('invoice_id', 'I'), ('amount', 'N'),
                                        ('organization', 'I'), ('draft', 'B'), ('deleted_at', 'DHZ')]:
                        columns.column(name, dtype=dtype)
                    line.virtual_columns().formulaColumn('double_amount', sql_formula='$amount*2', dtype='N')
                    receipt = tables.table('receipt', pkey='id')
                    columns = receipt.columns()
                    columns.column('id', dtype='I')
                    columns.column('invoice_id', dtype='I').relation('app.invoice.id', foreign_key=True,
                                                                    x_name='invoice')
                    receipt.virtual_columns().aliasColumn('invoice_total', relation_path='@invoice_id.total')

            db = build_database(Recipe)
            try:
                yield db
            finally:
                db.closeConnection()
        finally:
            observer.execute(sql.SQL('DROP SCHEMA {} CASCADE').format(sql.Identifier(schema)))


def test_default_returning_does_not_evaluate_subquery_virtuals(formula_database):
    db = formula_database
    with completed(db):
        invoice = db.table('app.invoice')
        assert invoice.insert({'id': 4, 'name': 'new'}) == {'id': 4, 'name': 'new'}
        assert invoice.update({'id': 4, 'name': 'updated'}) == {'id': 4, 'name': 'updated'}
        invoice.delete({'id': 4, 'name': 'updated'})
        assert invoice.query(where='$id=4').fetch() == []
