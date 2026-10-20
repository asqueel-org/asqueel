"""The original adapter clause oracle through SqlCompiledQuery."""
import json
from pathlib import Path

import pytest

from asqueel.adapters.postgres import SqlDbAdapter as PostgresAdapter
from asqueel.adapters.sqlite import SqlDbAdapter as SqliteAdapter
from asqueel.sql_compiled_query import SqlCompiledQuery

ORACLE = json.loads((Path(__file__).parents[1] / 'oracles/legacy_renderer.json').read_text())


@pytest.mark.parametrize('adapter_type', [PostgresAdapter, SqliteAdapter])
@pytest.mark.parametrize('case', ORACLE)
def test_clause_assembly_matches_original_adapter_without_scanning(adapter_type, case):
    adapter = adapter_type(None)
    assert not hasattr(adapter, 'tokens')
    assert not hasattr(adapter, 'render')
    query = SqlCompiledQuery(**dict(case['arguments'], maintable_as='t0'))
    assert query.get_sqltext(adapter) == case['sql'].replace('SELECT  ', 'SELECT ', 1)


@pytest.mark.parametrize('adapter_type', [PostgresAdapter, SqliteAdapter])
def test_multiple_projection_separator_matches_legacy_compiled_query(adapter_type):
    query = SqlCompiledQuery('"s"."t"', columns='1 AS c1,\n2 AS c2')
    assert query.get_sqltext(adapter_type(None)).startswith('SELECT 1 AS c1,\n2 AS c2\n FROM ')
