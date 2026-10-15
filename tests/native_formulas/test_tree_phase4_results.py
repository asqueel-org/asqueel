"""Replay legacy option/Bag bodies; all SELECTs compile on the new tree."""
import inspect

import pytest

from examples.test_invoice_pg import source
from tests.native_formulas import test_legacy_options, test_legacy_bag_items
from tests.native_formulas.conftest import (db_pg as execution_pg, db_sqlite as execution_sqlite,  # noqa: F401
    partition_pg as execution_partition_pg, partition_sqlite as execution_partition_sqlite)  # noqa: F401
from tests.native_formulas.tree_execution import TreeExecution
from tests.object_tree.test_phase4_options import tree_database


def bind(executor, state=None):
    with pytest.MonkeyPatch.context() as patch:
        if state is None:
            patch.delenv('INVC_STATE', raising=False)
        else:
            patch.setenv('INVC_STATE', state)
        config = source()
        config.source['db'].attr['implementation'] = executor.dialect.name
        with tree_database(config) as tree:
            tree.currentEnv.update(dict(executor.currentEnv))
            yield TreeExecution(tree, executor)
            assert not tree._connections


@pytest.fixture(scope='module')
def db_pg(request):
    yield from bind(request.getfixturevalue('execution_pg'))


@pytest.fixture(scope='module')
def db_sqlite(request):
    yield from bind(request.getfixturevalue('execution_sqlite'))


@pytest.fixture(scope='module')
def partition_pg(request):
    yield from bind(request.getfixturevalue('execution_partition_pg'), 'NSW')


@pytest.fixture(scope='module')
def partition_sqlite(request):
    yield from bind(request.getfixturevalue('execution_partition_sqlite'), 'NSW')


def cases():
    for module in (test_legacy_options, test_legacy_bag_items):
        for name, cls in vars(module).items():
            if not name.startswith('Test') or not inspect.isclass(cls):
                continue
            for name, method in vars(cls).items():
                if name.startswith('test_'):
                    yield pytest.param(cls, method, list(inspect.signature(method).parameters)[1],
                                       marks=getattr(method, 'pytestmark', ()), id=f'{cls.__name__}.{name}')


@pytest.mark.parametrize('cls,method,fixture', list(cases()))
def test_legacy_result_body(request, cls, method, fixture):
    method(cls(), request.getfixturevalue(fixture))
