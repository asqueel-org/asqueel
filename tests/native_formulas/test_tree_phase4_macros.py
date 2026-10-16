"""Same macro result assertions; tree compilation and separate fixture execution."""
from datetime import date
from types import SimpleNamespace

import pytest

from asqueel import SqlDatabaseConfig
from tests.query_completion_support import shop as execution_shop  # noqa: F401
from tests.native_compiler.test_query_macros import (
    test_inclusive_range_with_nullable_bound_parameters as test_inclusive_range_with_nullable_bound_parameters,
    test_null_value_range_retains_sql_unknown_in_where as test_null_value_range_retains_sql_unknown_in_where,
    test_period_bound_dates_execute_on_a_date_column as test_period_bound_dates_execute_on_a_date_column,
)
from tests.object_tree.test_phase4_options import tree_database


@pytest.fixture
def shop(execution_shop):  # noqa: F811
    execution = execution_shop
    config = SqlDatabaseConfig()
    physical = execution.db.model.table('sales.invoice')
    pkg = config.source.db('macros', implementation=execution.backend).packages().package('sales', sqlschema=physical.sqlschema)
    table = pkg.table('invoice', sqlname=physical.sqlname, pkey='id', x_logical_deletion_field='__del_ts')
    table.column('id', dtype='L')
    table.column('total', dtype='N')
    table.column('__del_ts', dtype='DH')
    with tree_database(config) as tree:
        tree.currentEnv.update(workdate=date(2026, 10, 15), locale='en')
        execution.db.currentEnv.update(workdate=date(2026, 10, 15), locale='en')
        db = SimpleNamespace(compiler=tree.compiler, execute=execution.db.execute, currentEnv=tree.currentEnv)
        yield SimpleNamespace(query=tree.table('sales.invoice').query, db=db, invoice_sql=execution.invoice_sql)
        assert not tree._connections
