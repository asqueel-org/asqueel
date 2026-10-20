"""Enable the existing compiler-simplify flag in disposable coverage fixtures."""
import pytest


@pytest.fixture(autouse=True)
def select_new_compiler(request):
    for name in ('db_pg', 'db_sqlite', 'db_pg3'):
        if name in request.fixturenames:
            db = request.getfixturevalue(name)
            with db.tempEnv(use_new_compiler=True):
                yield
            return
    yield
