"""Execute tree SQL separately; compare with the frozen legacy SQL on both engines."""
import csv
from pathlib import Path

import pytest

from asqueel import AsqueelDb
from asqueel.contracts import CompiledQuery
from examples.test_invoice_pg import source
from tests.native_formulas.conftest import SQL_TYPES
from tests.object_tree.test_legacy_rewrite_contracts import ORACLE, READY


@pytest.fixture(scope='module', params=['db_pg', 'db_sqlite'])
def databases(request):
    execution = request.getfixturevalue(request.param)
    config = source()
    config.source.get_node('db').attr['implementation'] = execution.adapter.dialect
    tree = AsqueelDb(config)
    try:
        # The shared fixture already loads eight original CSVs. Add the two
        # composite-key tables used by the legacy composite join contracts.
        quote = execution.adapter.adaptSqlName
        for name in ('price_year', 'price_year_note'):
            table = tree.model.table('invc.' + name)
            target = f'{quote(table.sqlschema)}.{quote(table.sqlname)}'
            columns = ', '.join(f'{quote(c.sqlname)} {SQL_TYPES.get(c.dtype, "TEXT")}'
                                for c in table.columns.values())
            execution.execute(f'CREATE TABLE {target} ({columns})')
            with (COMPOSITE_DATA / (name + '.csv')).open() as stream:
                reader = csv.DictReader(stream)
                names = [n for n in reader.fieldnames if n != 'pkey']
                fields = ','.join(quote(table.columns[n].sqlname) for n in names)
                values = ','.join(':'+n for n in names)
                for row in reader:
                    execution.execute(f'INSERT INTO {target} ({fields}) VALUES ({values})',
                                      {n: row[n] or None for n in names})
        execution.commit()
        yield tree, execution
    finally:
        tree.closeConnection()


COMPOSITE_DATA = Path(__file__).parent / 'data'


@pytest.mark.parametrize('name', sorted(READY))
def test_tree_select_matches_legacy_rows(databases, name):
    tree, execution = databases
    case = next(c for c in ORACLE['cases'] if c['request']['name'] == name
                and c['dialect'] == tree.adapter.dialect)
    request, expected = case['request'], case['expected']
    actual = tree.table(request['table']).query(
        request['columns'], sqlparams=request['params'],
        **dict(request['options'], **({'addPkeyColumn': True} if name == 'default_pkey' else {}))).compiled
    reference = CompiledQuery(expected['sql'],
                              {k: v for k, v in expected['params'].items() if k != 'jc_kwargs'},
                              dialect=execution.adapter.dialect, binding=execution.adapter.binding)
    # The tree only compiles. Execution uses the isolated fixture connection,
    # never the old compiler, and does not enable fetch on the tree facade.
    first, second = execution.execute(actual), execution.execute(reference)
    if name == 'star':
        # Source-order divergence recorded separately by the strict SQL xfail.
        # All names and per-name values must still equal the legacy result.
        assert [dict(row) for row in first.fetchall()] == [dict(row) for row in second.fetchall()]
        assert set(c[0] for c in first.description) == set(c[0] for c in second.description)
    else:
        assert [list(row) for row in first.fetchall()] == [list(row) for row in second.fetchall()]
        assert [c[0] for c in first.description] == [c[0] for c in second.description]
    assert tree._connections == {}
