"""Replay the portable oracle against real legacy code, with no database I/O.

Run with Asqueel's interpreter and PYTHONPATH=src:.:docs/design/probes.
The historical dependency path is used only to import the original GenroPy.
"""
import json
from pathlib import Path
import sys

import pytest

sys.path.insert(0, '/tmp/asqueel-formula-baseline/legacy/gnrpy')
sys.path.append('/tmp/asqueel-formula-baseline/env/lib/python3.12/site-packages')

from rewrite_phase1_compare import compile_case, databases, normalized  # noqa: E402
from tests.object_tree.test_legacy_rewrite_contracts import local_bindings  # noqa: E402

ROOT = Path(__file__).resolve().parents[3]
ORACLE = json.loads((ROOT/'tests/oracles/legacy_rewrite_phase1.json').read_text())


@pytest.fixture(scope='module', params=['sqlite', 'postgresql'])
def database(request):
    return databases(request.param, legacy_only=True)['legacy']


@pytest.mark.parametrize('name', [c['request']['name'] for c in ORACLE['cases']
                                 if c['dialect'] == 'sqlite'])
def test_reference_contract(database, name):
    dialect = 'postgresql' if database.implementation == 'postgres' else 'sqlite'
    case = next(c for c in ORACLE['cases'] if c['dialect'] == dialect and c['request']['name'] == name)
    expected = case['expected']
    actual = compile_case(database, 'legacy', case['request'])
    sql, params = actual['sql'], {k: v for k, v in actual['params'].items() if k != 'jc_kwargs'}
    expected_sql = expected['sql']
    expected_params = {k: v for k, v in expected['params'].items() if k != 'jc_kwargs'}
    if name == 'formula_parameters':
        sql, params = local_bindings(sql, params, dialect)
        expected_sql, expected_params = local_bindings(expected_sql, expected_params, dialect)
    assert normalized(sql) == normalized(expected_sql)
    assert params == expected_params
    assert actual['stable']
    clauses = actual['clauses']
    joins = clauses['joins']
    if name in ('direct', 'reuse_across_clauses', 'inverse_reuse', 'alias_and_direct_reuse'):
        assert len(joins) == 1
    elif name == 'two_hops':
        assert len(joins) == 2
    elif name in ('three_hops', 'inverse_forward', 'composite_two_paths'):
        assert len(joins) == 3
    elif name == 'composite_join':
        assert len(joins) == 1
        assert 'product_id' in joins[0] and 'year' in joins[0] and ' AND ' in joins[0]
    if name == 'inverse_reuse':
        assert set(clauses['explodingColumns']) >= {'_rows_quantity', '_rows_unit_price'}
    if name == 'implicit_distinct_hidden_order':
        assert clauses['distinct'].strip() == 'DISTINCT'
        assert '__ord_col_0' in clauses['columns']
    if name == 'symbolic_relation_parameter':
        assert ':other' not in actual['raw_sql']
        assert actual['params']['other'] == '@customer_id.id'
