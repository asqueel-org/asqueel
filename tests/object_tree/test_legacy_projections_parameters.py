"""R2 ports: GenroPy TestEmbedFieldPars and query-surface AS, plus differential cases.

Reference fa35e5ad, tests/sql/test_compiler_coverage.py:2507 and
h_query_surface_test.py:350. Relation execution remains in R5; the original
predicate comparisons are ported here to physical SELECT SQL without count().
"""
from copy import deepcopy
from decimal import Decimal
import json
from pathlib import Path
import sqlite3
from types import SimpleNamespace

import pytest

from asqueel._legacy_sql import embed_field_parameters
from asqueel.contracts import UnsupportedFeatureError
from asqueel.adapters.base import query_result
from tests.object_tree import test_minimal_select as minimal


db = minimal.db
no_io = minimal.no_io
ORACLE = json.loads((Path(__file__).parents[1] / 'oracles/legacy_r2.json').read_text())


def decode(value):
    if isinstance(value, dict) and set(value) == {'bytes_hex'}:
        return bytes.fromhex(value['bytes_hex'])
    return value


@pytest.mark.parametrize('record', [r for r in ORACLE['records'] if r['kind'] == 'embed'],
                         ids=lambda r: r['name'])
def test_embed_original_function_oracle(record):
    table = SimpleNamespace(columns={'id': 1, 'total': 1},
                            virtual_columns={'double_total': 1}, relations={'@customer_id': True})
    params = {key: decode(value) for key, value in record['params'].items()}
    before = deepcopy(params)
    expected = record['legacy']
    if 'error' in expected:
        with pytest.raises(Exception) as caught:
            embed_field_parameters(record['where'], params, table)
        assert type(caught.value).__name__ == expected['error']
    else:
        actual, _ = embed_field_parameters(record['where'], params, table)
        assert actual == expected['value']
    assert params == before


@pytest.mark.parametrize('record', [r for r in ORACLE['records']
                                   if r['kind'] == 'projection' and r['dialect'] == 'postgres'],
                         ids=lambda r: r['name'])
def test_projection_from_original_compiled_query(db, record):
    plan = db.compiler.plan_select('sales.invoice', columns=record['columns'])
    actual = plan.columns
    # Approved correction: AS inside CAST no longer prevents an output alias
    # or makes two casts overwrite each other. Keep the legacy oracle intact.
    corrected = {
        'CAST($total AS NUMERIC)': 'CAST("t0"."total" AS NUMERIC) AS "CAST__total_AS_NUMERIC_"',
        'CAST($id AS NUMERIC),CAST($total AS NUMERIC)':
            'CAST("t0"."id" AS NUMERIC) AS "CAST__id_AS_NUMERIC_",\n'
            'CAST("t0"."total" AS NUMERIC) AS "CAST__total_AS_NUMERIC_"',
    }
    # The same splitter also ignores AS inside a quoted literal (oracle 18).
    if record['columns'] == "'$id AS text'":
        expected = record['legacy']['value'] + ' AS "__id_AS_text_"'
    else:
        expected = corrected.get(record['columns'], record['legacy']['value'])
    assert actual.strip() == expected.strip()
    sql = plan.get_sqltext(db.compiler.adapter)
    assert sql.startswith('SELECT ')
    # The adapter must render authored projections without appending another AS.
    assert sql.split('\n FROM ', 1)[0] == 'SELECT ' + actual


@pytest.mark.parametrize('operator', ['>', '<='])
def test_original_local_field_parameter(db, operator):
    # TestEmbedFieldPars.test_column_param_{pg,sqlite}: same local-field comparison.
    query = db.table('sales.invoice').query(columns='$id', where=f'$total {operator} :threshold',
                                          threshold='$id')
    first = query.compiled
    assert f'"t0"."total" {operator} "t0"."id"' in first.sql
    assert ':threshold' not in first.sql and '%(threshold)' not in first.sql
    assert first.params == {'threshold': '$id'}
    assert first.input_parameters == ('threshold',)
    assert query.compiled == first


def test_symbolic_binding_only_replaces_where_and_preserves_input(db):
    params = {'threshold': '$id'}
    query = db.table('sales.invoice').query(
        columns=':threshold AS value', where='$total > :threshold',
        order_by=':threshold', sqlparams=params)
    compiled = query.compiled
    assert '"t0"."total" > "t0"."id"' in compiled.sql
    assert compiled.params == params
    assert compiled.input_parameters == ('threshold',)
    assert params == {'threshold': '$id'}
    assert compiled.sql.count('%(threshold)s' if db.adapter.dialect == 'postgres' else ':threshold') == 2


def test_symbolic_bytes_and_prefix_boundaries(db):
    compiled = db.table('sales.invoice').query(
        columns='$id', where='$total>:p AND $total<:p2', p=b'$id', p2=Decimal('20')).compiled
    assert '"t0"."total">"t0"."id"' in compiled.sql
    assert compiled.params == {'p': '$id', 'p2': Decimal('20')}
    assert compiled.input_parameters == ('p', 'p2')


@pytest.mark.parametrize('value', ['$absent', '@absent.name', '$id + 1', r'\$id', r'\@customer_id.name'])
def test_unrecognized_or_escaped_reference_remains_a_value_in_plan(db, value):
    plan = db.compiler.plan_select('sales.invoice', columns='$id', where='$label=:value',
                                  sqlparams={'value': value})
    assert ':value' in plan.where
    assert plan.params['value'] == value


def test_unicode_symbolic_parameter_follows_legacy_boundary(db):
    compiled = db.table('sales.invoice').query(
        columns='$id', where='$total>:soglia_è', sqlparams={'soglia_è': '$id'}).compiled
    assert '"t0"."total">"t0"."id"' in compiled.sql
    assert compiled.params == {'soglia_è': '$id'}
    assert compiled.input_parameters == ('soglia_è',)


def test_unicode_value_and_sql_escape_reach_adapter_unchanged(db):
    # Actual placeholder preparation, \: and percent escaping belong to R3.
    plan = db.compiler.plan_select('sales.invoice', columns='$id',
                                  where=r'$total>:soglia_è AND $label=\:literal',
                                  sqlparams={'soglia_è': Decimal('12.50')})
    assert ':soglia_è' in plan.where
    assert r'\:literal' in plan.where
    assert plan.params['soglia_è'] == Decimal('12.50')


def test_symbolic_formula_is_resolved_in_where(db):
    compiled = db.table('sales.invoice').query(
        '$id', where='$total=:other', other='$double_total').compiled
    assert '( "t0"."total" * 2 )' in compiled.sql
    assert compiled.input_parameters == ('other',)


def test_embedded_input_does_not_hide_unused_keyword(db):
    with pytest.raises(UnsupportedFeatureError, match="query keyword 'unused' is neither a query option nor a parameter"):
        db.table('sales.invoice').query(columns='$id', where='$total>:threshold',
                                       threshold='$id', unused='$id').compiled


def test_explicit_environment_parameter_remains_a_caller_input(db):
    compiled = db.table('sales.invoice').query(columns='$id', where='$total>:env_value',
                                              env_value='$id').compiled
    assert compiled.input_parameters == ('env_value',)
    assert compiled.environment is None
    assert compiled.params == {'env_value': '$id'}


def test_original_local_comparisons_partition_sqlite_rows():
    # Same gt + le invariant as the two original column-param tests. Use physical
    # fields from the legacy test, compile only through Asqueel, then SQLite directly.
    source, table = minimal.recipe('sqlite')
    table.column('quantity', dtype='N')
    table.column('unit_price', dtype='N')
    with minimal.bind(source) as database, sqlite3.connect(':memory:') as conn:
        conn.execute('CREATE TABLE sales_invoice (id INTEGER, quantity NUMERIC, unit_price NUMERIC)')
        conn.executemany('INSERT INTO sales_invoice VALUES (?,?,?)',
                         [(1, 2, 1), (2, 2, 2), (3, 1, 3), (4, 10, 4)])
        counts = []
        for operator in ['>', '<=']:
            compiled = database.table('sales.invoice').query(
                columns='$id', where=f'$quantity {operator} :threshold',
                sqlparams={'threshold': '$unit_price'}).compiled
            counts.append(len(conn.execute(compiled.sql, dict(compiled.params)).fetchall()))
        assert counts == [2, 2]
        assert sum(counts) == 4


def test_authored_projection_names_are_obtained_from_sqlite_cursor():
    source, _ = minimal.recipe('sqlite')
    with minimal.bind(source) as database, sqlite3.connect(':memory:') as conn:
        conn.execute('CREATE TABLE sales_invoice (id INTEGER, total NUMERIC)')
        conn.execute('INSERT INTO sales_invoice VALUES (1, 4)')
        for columns, expected_values in [
            ('CAST($total AS NUMERIC)', [4]),
            ('CAST($id AS NUMERIC),CAST($total AS NUMERIC)', [1, 4]),
            ('$id AS CamelCase,$total', [1, 4]),
            ('$id AS "code",$total AS code', [1, 4]),
        ]:
            compiled = database.table('sales.invoice').query(columns=columns).compiled
            cursor = conn.execute(compiled.sql, dict(compiled.params))
            names = [item[0] for item in cursor.description]
            row = cursor.fetchone()
            assert list(row) == expected_values
            if compiled.columns:
                assert [c.name for c in compiled.columns] == names
            # Duplicate names are legal at this compile-only boundary. Existing
            # fetch's uniqueness check is outside R2 and is not changed here.
            if len(set(names)) == len(names):
                cursor = conn.execute(compiled.sql, dict(compiled.params))
                result = query_result(compiled.columns, names, cursor)
                assert list(result.rows[0]) == expected_values
