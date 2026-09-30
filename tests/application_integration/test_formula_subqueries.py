"""Formula select/exists acceptance with real correlations and nested policies."""
from decimal import Decimal
from uuid import uuid4

import psycopg
from psycopg import sql
import pytest

from asqueel import SqlDatabaseConfig, build_database
from tests.native_support import postgres_dsn

pytestmark = pytest.mark.postgresql


@pytest.fixture
def formula_database():
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
                    tables = root.db('subqueries', conninfo=dsn).schemas().schema(
                        'app', x_sql_schema=schema).tables()
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
                    virtual.formulaColumn('above_threshold', dtype='N', select=dict(
                        table='app.line', columns='SUM($amount)',
                        where='$invoice_id=#THIS.id AND $amount>:threshold', params={'threshold': 15},
                        cast='numeric'))
                    virtual.formulaColumn('single_amount', dtype='N', select=dict(
                        table='app.line', columns='$amount', where='$invoice_id=#THIS.id'))
                    virtual.formulaColumn('literal_marker', dtype='T', select=dict(
                        table='app.line', columns="'#THIS.id'", where='$invoice_id=#THIS.id /* #THIS.missing */',
                        limit=1))
                    line = tables.table('line', pkey='id',
                                        x_partition={'field': 'organization', 'current': 'organization'},
                                        x_draft_field='draft', x_logical_deletion_field='deleted_at')
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
                    receipt.virtual_columns().aliasColumn('invoice_total', relation_path='@invoice.total')

            with build_database(Recipe) as db:
                yield db
        finally:
            observer.execute(sql.SQL('DROP SCHEMA {} CASCADE').format(sql.Identifier(schema)))


def test_scalar_aggregate_exists_named_nested_formula_and_metadata(formula_database):
    db = formula_database
    with db.temp_env(organization=0):
        result = db.table('invoice').query(
            '$id,$total,$has_lines,$total_zero,$double_total', order_by='$id').execute()
        assert result.rows == [
            {'id': 1, 'total': Decimal(60), 'has_lines': True, 'total_zero': Decimal(60),
             'double_total': Decimal(120)},
            {'id': 2, 'total': Decimal(7), 'has_lines': True, 'total_zero': Decimal(7),
             'double_total': Decimal(14)},
            {'id': 3, 'total': None, 'has_lines': False, 'total_zero': Decimal(0), 'double_total': None},
        ]
        assert len(result.rows) == 3  # Child rows must not multiply the outer invoice rows.
        total_metadata = next(column for column in result.columns if column.name == 'total')
        assert total_metadata.source == 'app.invoice.total'
        assert total_metadata.dtype == 'N'


def test_correlated_owner_through_relation_and_alias(formula_database):
    with formula_database.temp_env(organization=0):
        rows = formula_database.table('receipt').query(
            '$id,@invoice.total AS related_total,$invoice_total', order_by='$id').fetch()
        assert rows == [
            {'id': 10, 'related_total': Decimal(60), 'invoice_total': Decimal(60)},
            {'id': 11, 'related_total': Decimal(7), 'invoice_total': Decimal(7)},
            {'id': 12, 'related_total': None, 'invoice_total': None},
        ]


def test_nested_policy_defaults_and_explicit_overrides(formula_database):
    db = formula_database
    query = db.table('invoice').query('$total,$filtered_total,$all_total', where='$id=1')
    with pytest.raises(ValueError):
        query.fetch()  # Outer unpartitioned table does not disable child partition scope.
    assert db.outcome == 'not_started'
    with db.temp_env(organization=0):
        assert query.fetch() == [{'total': Decimal(60), 'filtered_total': Decimal(10),
                                  'all_total': Decimal(100)}]
    assert db.table('invoice').query('$all_total', where='$id=1').fetch() == [{'all_total': Decimal(100)}]


def test_scalar_multiple_rows_raise_and_this_inside_literal_comment_survives(formula_database):
    db = formula_database
    with db.temp_env(organization=0):
        assert db.table('invoice').query('$literal_marker', where='$id=1').fetch() == [
            {'literal_marker': '#THIS.id'}]
        db.rollback()
        with pytest.raises(psycopg.errors.CardinalityViolation):
            with db.transaction():
                db.table('invoice').query('$single_amount', where='$id=1').fetch()
        assert db.outcome == 'rolled_back'


def test_default_returning_does_not_evaluate_subquery_virtuals(formula_database):
    db = formula_database
    with db.transaction():
        inserted = db.table('invoice').insert({'id': 4, 'name': 'new'})
        assert inserted.rows == [{'id': 4, 'name': 'new'}]
        updated = db.table('invoice').update({'name': 'updated'}, where='$id=4')
        assert updated.rows == [{'id': 4, 'name': 'updated'}]
        assert db.table('invoice').delete(4).rows == [{'id': 4, 'name': 'updated'}]


def test_subquery_local_params_are_isolated_from_outer_binding(formula_database):
    db = formula_database
    with db.temp_env(organization=0):
        query = db.table('invoice').query('$id,$above_threshold', where='$id<:threshold',
                                          params={'threshold': 2})
        assert query.fetch() == [{'id': 1, 'above_threshold': Decimal(50)}]
