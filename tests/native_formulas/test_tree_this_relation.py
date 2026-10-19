"""GenroPy ba377674f7: #THIS.@relation.column in a SQL formula.

Port TestFormulaSqlThisRelation using a native declaration instead of the
legacy test's dynamic column override. Compile on the tree, execute separately.
"""
import pytest

from asqueel import SqlDatabase
from asqueel.configuration import _owned_handler
from examples.test_invoice_pg import source


@pytest.mark.parametrize('backend', ['db_pg', 'db_sqlite'])
@pytest.mark.parametrize('table,formula,direct,condition', [
    ('invc.invoice', '$this_customer', '$customer_name', '$customer_id IS NOT NULL'),
    ('invc.invoice_row', '@invoice_id.this_customer',
     '@invoice_id.@customer_id.account_name', '@invoice_id.customer_id IS NOT NULL'),
])
def test_this_relation_in_sql_formula_returns_related_value(
        request, backend, table, formula, direct, condition):
    executor = request.getfixturevalue(backend)
    config = source()
    config.source['db'].attr['implementation'] = executor.adapter.dialect
    invoice = config.source['db'].packages().package('invc').table('invoice')
    invoice.formulaColumn('this_customer', '#THIS.@customer_id.account_name', dtype='T')
    tree = SqlDatabase(model=config.render(mode='objects_tree'), config=_owned_handler(config))
    try:
        tree.currentEnv.update(dict(executor.currentEnv))
        compiled = tree.table(table).query(
            f'{direct} AS customer_name,{formula} AS this_customer',
            where=condition, limit=5, excludeDraft=False,
            excludeLogicalDeleted=False, ignorePartition=True, order_by='').compiled
        assert '#THIS' not in compiled.sql
        # Legacy keys include the traversal path: through invoice_row, the
        # direct path and the formula-local path keep distinct customer aliases.
        assert compiled.sql.count('LEFT JOIN') == (1 if table == 'invc.invoice' else 3)
        rows = executor.execute(compiled).fetchall()
        assert rows
        assert any(row['customer_name'] is not None for row in rows)
        for row in rows:
            assert row['this_customer'] == row['customer_name']
        assert not tree._connections
    finally:
        tree.closeConnection()
