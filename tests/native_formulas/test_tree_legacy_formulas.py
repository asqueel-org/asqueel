"""Replay existing legacy assertions; compile on the tree, execute separately.

The test-only terminal preserves the explicit no-filter/no-default-order fixture
from phase 3 to keep compilation and execution separately verified. count() in cross-checks is len of fetched ids, not a new
compiler count API. Real tree terminals are covered separately by test_tree_terminals_legacy. No old compiler
is used to obtain results. Original assertion bodies and skip marks are reused.
"""
import inspect

import pytest

from asqueel import AsqueelDb
from examples.test_invoice_pg import source
from tests.native_formulas import (legacy_sql_formulas, legacy_subqueries,
                                   legacy_method_formulas, legacy_subquery_columns)
from tests.native_formulas.conftest import db_pg as execution_pg, db_sqlite as execution_sqlite  # noqa: F401

MODULES = (legacy_sql_formulas, legacy_subqueries,
           legacy_method_formulas, legacy_subquery_columns)


class ResultQuery:
    def __init__(self, query, executor):
        self.query, self.executor = query, executor

    def fetch(self):
        return self.executor.execute(self.query.compiled).fetchall()

    def count(self):
        return len(self.fetch())


class ResultTable:
    def __init__(self, table, executor):
        self.table, self.executor = table, executor

    def query(self, columns=None, **kwargs):
        kwargs.setdefault('excludeDraft', False)
        kwargs.setdefault('excludeLogicalDeleted', False)
        kwargs.setdefault('ignorePartition', True)
        kwargs.setdefault('order_by', '')
        return ResultQuery(self.table.query(columns or '$'+self.table.model.pkey, **kwargs), self.executor)


class Results:
    def __init__(self, tree, executor):
        self.tree, self.executor = tree, executor

    def table(self, name):
        return ResultTable(self.tree.table(name), self.executor)


@pytest.fixture(scope='module')
def db_pg(request):
    yield from bound_tree(request.getfixturevalue('execution_pg'))


@pytest.fixture(scope='module')
def db_sqlite(request):
    yield from bound_tree(request.getfixturevalue('execution_sqlite'))


def bound_tree(executor):
    config = source()
    config.source.get_node('db').attr['implementation'] = executor.adapter.dialect
    tree = AsqueelDb(config)
    try:
        tree.currentEnv.update(dict(executor.currentEnv))
        yield Results(tree, executor)
        assert tree._connections == {}
    finally:
        tree.closeConnection()


def parameters():
    for module in MODULES:
        for name, cls in vars(module).items():
            if not name.startswith('Test') or not inspect.isclass(cls):
                continue
            for method_name, method in vars(cls).items():
                if not method_name.startswith('test_'):
                    continue
                marks = list(getattr(method, 'pytestmark', ()))
                fixture = list(inspect.signature(method).parameters)[1]
                yield pytest.param(cls, method, fixture, marks=marks, id=f'{name}.{method_name}')


@pytest.mark.parametrize('cls,method,fixture', list(parameters()))
def test_original_assertions_on_tree(request, cls, method, fixture):
    method(cls(), request.getfixturevalue(fixture))
