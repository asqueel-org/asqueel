"""Original legacy bodies run on the real hierarchical query terminals."""
import inspect

import pytest

from asqueel import AsqueelDb
from asqueel.runtime import connection_settings
from examples.test_invoice_pg import source
from tests.native_formulas import test_tree_count_legacy, test_legacy_options, legacy_sql_formulas
from tests.native_formulas.conftest import (db_pg as execution_pg, db_sqlite as execution_sqlite,  # noqa: F401
    partition_pg as execution_partition_pg, partition_sqlite as execution_partition_sqlite)  # noqa: F401


def live_database(executor, state=None):
    with pytest.MonkeyPatch.context() as patch:
        if state is None:
            patch.delenv('INVC_STATE', raising=False)
        else:
            patch.setenv('INVC_STATE', state)
        config = source()
        implementation, conninfo, connect_kwargs = connection_settings(executor.config)
        config.source['db'].attr.update(implementation=implementation, conninfo=conninfo,
                                        connect_kwargs=connect_kwargs)
        tree = AsqueelDb(config)
        try:
            tree.currentEnv.update(dict(executor.currentEnv))
            yield tree
        finally:
            tree.closeConnection()


@pytest.fixture(scope='module')
def db_pg(execution_pg):  # noqa: F811
    yield from live_database(execution_pg)


@pytest.fixture(scope='module')
def db_sqlite(execution_sqlite):  # noqa: F811
    yield from live_database(execution_sqlite)


@pytest.fixture(scope='module')
def partition_pg(execution_partition_pg):  # noqa: F811
    yield from live_database(execution_partition_pg, 'NSW')


@pytest.fixture(scope='module')
def partition_sqlite(execution_partition_sqlite):  # noqa: F811
    yield from live_database(execution_partition_sqlite, 'NSW')


def cases():
    classes = [cls for module in (test_tree_count_legacy, test_legacy_options)
               for name, cls in vars(module).items() if name.startswith('Test') and inspect.isclass(cls)]
    classes.extend((legacy_sql_formulas.TestAliasColumn, legacy_sql_formulas.TestFormulaSql))
    for cls in classes:
        for name, method in vars(cls).items():
            if name.startswith('test_'):
                yield pytest.param(cls, method, list(inspect.signature(method).parameters)[1],
                                   id=f'{cls.__module__}.{cls.__name__}.{name}')


@pytest.mark.parametrize('cls,method,fixture', list(cases()))
def test_original_body_on_live_tree(request, cls, method, fixture):
    db = request.getfixturevalue(fixture)
    method(cls(), db)
    assert db._connections  # The real SqlQuery terminal used its owning database.
