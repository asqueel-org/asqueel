"""Execute the legacy alias/formula redefinition contracts on both adapters."""
import pytest

from asqueel import SqlDatabase
from asqueel.configuration import _owned_handler
from examples.test_invoice_pg import source


@pytest.mark.parametrize('backend', ['db_pg', 'db_sqlite'])
@pytest.mark.parametrize('grouped', [False, True])
@pytest.mark.parametrize('reverse', [False, True])
def test_redefined_virtual_returns_the_new_definition(request, backend, grouped, reverse):
    executor = request.getfixturevalue(backend)
    config = source()
    config.source['db'].attr['implementation'] = executor.adapter.dialect
    table = config.source['db'].packages().package('invc').table('invoice')
    target = table.colgroup('redefinition') if grouped else table
    first, second = ('formulaColumn', 'aliasColumn') if reverse else ('aliasColumn', 'formulaColumn')
    definitions = {'aliasColumn': {'relation_path': '@customer_id.account_name'},
                   'formulaColumn': {'sql_formula': "'from_formula'"}}
    getattr(target, first)('redefined_customer', **definitions[first], name_long='Customer')
    with config.contribution('later'):
        getattr(target, second)('redefined_customer', **definitions[second])
    tree = SqlDatabase(model=config.render(mode='objects_tree'), config=_owned_handler(config))
    try:
        compiled = tree.table('invc.invoice').query(
            '$redefined_customer AS actual,$customer_name AS expected',
            where='$customer_id IS NOT NULL', limit=5, excludeDraft=False,
            excludeLogicalDeleted=False, ignorePartition=True, order_by='').compiled
        rows = executor.execute(compiled).fetchall()
        assert rows
        assert any(row['expected'] is not None for row in rows)
        for row in rows:
            assert row['actual'] == (row['expected'] if reverse else 'from_formula')
        assert not tree._connections
    finally:
        tree.closeConnection()
