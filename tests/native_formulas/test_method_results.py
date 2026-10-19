"""Method formulas return the legacy values, including NULL versus empty text."""
from decimal import Decimal
from uuid import uuid4

import psycopg
from psycopg import sql
import pytest

from asqueel import SqlDatabaseConfig, SqlTable, build_database
from tests.native_support import postgres_dsn


@pytest.fixture(params=['db_pg', 'db_sqlite'])
def invoice_db(request):
    return request.getfixturevalue(request.param)


def test_sys_fields_with_no_rules_return_null_not_false(invoice_db):
    rows = invoice_db.table('invc.customer').query(
        '$__protecting_reasons,$__invalid_reasons,$__is_protected_row,$__is_invalid_row').fetch()
    assert rows
    assert all(all(value is None for value in row.values()) for row in rows)


class Item(SqlTable):
    def sql_formula_adjusted(self, attr):
        attr['var_factor'] = self.db.currentEnv.get('multiplier', 2)
        return '$amount * :factor'

    def sql_formula_named(self, attr):
        attr['var_factor'] = 3
        attr['select_rows']['sqlparams']['factor'] = 4
        return 'COALESCE(#rows,0) + :factor'


@pytest.fixture(params=['postgres', 'sqlite'])
def rule_db(request, tmp_path):
    backend = request.param
    schema = 'method_formulas_' + uuid4().hex
    config = SqlDatabaseConfig()
    root = config.source.db('method_results', implementation=backend)
    root.connection(implementation=backend, **(
        {'dsn': postgres_dsn()} if backend == 'postgres'
        else {'database': str(tmp_path / 'rules.db')}))
    table = root.packages().package('app', sqlschema=schema, sqlprefix=False).table(
        'item', pkey='id', x_table_class=Item, protectionColumn='gate')
    for name, dtype in [('id', 'L'), ('amount', 'N'), ('gate', 'T'), ('flag', 'B')]:
        table.column(name, dtype=dtype)
    table.formulaColumn('adjusted', sql_formula=True, dtype='N')
    table.formulaColumn('named', sql_formula=True, dtype='N', select_rows=dict(
        table='app.item', columns='SUM($adjusted)',
        where='$id=#THIS.id AND $amount>:factor', sqlparams={'factor': 0}))
    table.aliasColumn('adjusted_alias', '$adjusted')
    table.formulaColumn('__protected_by_amount', '$adjusted>:threshold', var_threshold=10, dtype='B')
    table.formulaColumn("__invalid_by_one", '$flag', dtype='B')
    table.formulaColumn('__protecting_reasons', sql_formula=True)
    table.formulaColumn('__invalid_reasons', sql_formula=True)
    table.formulaColumn('__is_protected_row', "$__protecting_reasons!=''", dtype='B')
    table.formulaColumn('__is_invalid_row', "$__invalid_reasons!=''", dtype='B')
    admin = psycopg.connect(postgres_dsn(), autocommit=True) if backend == 'postgres' else None
    try:
        if admin is not None:
            admin.execute(sql.SQL('CREATE SCHEMA {}').format(sql.Identifier(schema)))
        db = build_database(config)
        try:
            target = f'"{schema}"."item"'
            db.execute(f'CREATE TABLE {target} (id BIGINT, amount NUMERIC, gate TEXT, flag BOOLEAN)')
            for values in [(1, 5, None, False), (2, 6, '', True), (3, None, 'locked', None)]:
                db.execute(f'INSERT INTO {target} VALUES (:id,:amount,:gate,:flag)',
                           dict(zip(('id', 'amount', 'gate', 'flag'), values)))
            db.commit()
            try:
                yield db
            finally:
                db.rollback()
        finally:
            db.closeConnection()
    finally:
        if admin is not None:
            try:
                admin.execute(sql.SQL('DROP SCHEMA {} CASCADE').format(sql.Identifier(schema)))
            finally:
                admin.close()


def test_reasons_and_method_dependencies_have_legacy_values(rule_db):
    rows = rule_db.table('app.item').query(
        '$id,$__protecting_reasons,$__invalid_reasons,$__is_protected_row,$__is_invalid_row',
        order_by='$id').fetch()
    assert [r['__protecting_reasons'] for r in rows] == ['', 'gate,amount', 'gate']
    assert [r['__invalid_reasons'] for r in rows] == ['', 'one', '']
    assert [bool(r['__is_protected_row']) for r in rows] == [False, True, True]
    assert [bool(r['__is_invalid_row']) for r in rows] == [False, True, False]


def test_method_alias_filter_order_and_new_environment(rule_db):
    def build():
        return rule_db.table('app.item').query(
            '$id,$adjusted_alias,:factor AS external', where='$adjusted>:minimum',
            order_by='$adjusted DESC', factor=99, minimum=11)
    query = build()
    assert [dict(row) for row in query.fetch()] == [dict(id=2, adjusted_alias=Decimal(12), external=99)]
    # The query keeps its first compilation; the new environment needs a new query.
    with rule_db.tempEnv(multiplier=3):
        assert [dict(row) for row in query.fetch()] == [dict(id=2, adjusted_alias=Decimal(12), external=99)]
        assert [dict(row) for row in build().fetch()] == [dict(id=2, adjusted_alias=Decimal(18), external=99),
                                 dict(id=1, adjusted_alias=Decimal(15), external=99)]
    assert [dict(row) for row in query.fetch()] == [dict(id=2, adjusted_alias=Decimal(12), external=99)]


def test_method_named_subquery_keeps_all_parameter_owners(rule_db):
    rows = rule_db.table('app.item').query('$id,$named,:factor AS external', factor=99, order_by='$id').fetch()
    assert [dict(row) for row in rows] == [dict(id=1, named=Decimal(13), external=99),
                    dict(id=2, named=Decimal(15), external=99),
                    dict(id=3, named=Decimal(3), external=99)]
