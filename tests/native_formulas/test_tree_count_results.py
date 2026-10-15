"""Execute frozen legacy and hierarchical count SQL on the same real fixtures."""
import pytest

from asqueel.contracts import CompiledQuery
from tests.object_tree.test_count import ORACLE, CASES
from tests.native_formulas.test_tree_phase4_results import bind


@pytest.fixture(scope='module', params=['db_pg', 'db_sqlite'])
def databases(request):
    execution = request.getfixturevalue(request.param)
    yield from bind(execution)


@pytest.mark.parametrize('case', CASES, ids=lambda c: c['request']['name'])
def test_count_matches_legacy_rows_and_value(databases, case):
    tree, execution = databases.tree, databases.executor
    request = case['request']
    expected = next(c['expected'] for c in ORACLE['cases']
                    if c['dialect'] == tree.dialect.name and c['request']['name'] == request['name'])
    actual = tree.table(request['table']).query(request['columns'], sqlparams=request['params'],
                                               **request['options'])._compile(tree.compiler.count)
    reference = CompiledQuery(expected['sql'],
        {k:v for k,v in expected['params'].items() if k != 'jc_kwargs'},
        dialect=execution.dialect.name, binding=execution.driver.binding)
    result, legacy = execution.execute(actual), execution.execute(reference)
    assert [list(row) for row in result.rows] == [list(row) for row in legacy.rows]
    assert [c.name for c in result.columns] == [c.name for c in legacy.columns]
    legacy_count = (legacy.rows[0][0] if len(legacy.rows) == 1
                    and legacy.columns[0].name == 'gnr_row_count' else len(legacy.rows))
    assert databases.table(request['table']).query(request['columns'], sqlparams=request['params'],
                                                  **request['options']).count() == legacy_count
    assert not tree._connections
