"""The original adapter clause oracle through SqlCompiledQuery."""
import json
from pathlib import Path

import pytest

from asqueel.dialects.postgres import PostgresDialect
from asqueel.dialects.sqlite import SqliteDialect
from asqueel.sql_compiled_query import SqlCompiledQuery

ORACLE = json.loads((Path(__file__).parents[1] / 'oracles/legacy_renderer.json').read_text())


@pytest.mark.parametrize('dialect_type', [PostgresDialect, SqliteDialect])
@pytest.mark.parametrize('case', ORACLE)
def test_clause_assembly_matches_original_adapter_without_scanning(dialect_type, case):
    dialect = dialect_type()
    assert not hasattr(dialect, 'tokens')
    assert not hasattr(dialect, 'render')
    query = SqlCompiledQuery(**dict(case['arguments'], maintable_as='t0'))
    assert query.get_sqltext(dialect) == case['sql'].replace('SELECT  ', 'SELECT ', 1)


@pytest.mark.parametrize('dialect_type', [PostgresDialect, SqliteDialect])
def test_multiple_projection_separator_matches_legacy_compiled_query(dialect_type):
    query = SqlCompiledQuery('"s"."t"', columns='1 AS c1,\n2 AS c2')
    assert query.get_sqltext(dialect_type()).startswith('SELECT 1 AS c1,\n2 AS c2\n FROM ')
