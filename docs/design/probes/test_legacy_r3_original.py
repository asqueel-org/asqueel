"""Run the original PostgreSQL cast test bodies without their unrelated MySQL setup.

The source class's setup imports MySQLdb unconditionally, absent in this frozen
runtime. Only the adapter fixture is narrowed; test method bodies are unchanged.
"""
import importlib.util
from pathlib import Path

import pytest
from gnr.sql.adapters.gnrpostgres import SqlDbAdapter

path = Path('/tmp/asqueel-formula-baseline/legacy/gnrpy/tests/sql/test_gnrbaseadapter.py')
spec = importlib.util.spec_from_file_location('r3_original_adapter_tests', path)
original = importlib.util.module_from_spec(spec)
spec.loader.exec_module(original)


@pytest.mark.parametrize('name', [
    'test_double_colon_not_matched', 'test_param_still_matched',
    'test_cast_and_param_mixed', 'test_multiple_casts_and_params',
])
def test_original_postgres_cast_body(name):
    adapter = SqlDbAdapter(original.FakeDbRoot(False))
    getattr(original.TestPrepareSqlTextDoubleColon(), name)(adapter)
