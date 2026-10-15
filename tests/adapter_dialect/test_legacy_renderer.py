"""Clause assembly oracle from eight original adapters; SQL is not parsed here."""
import json
from pathlib import Path

import pytest

from asqueel.contracts import ResultColumn
from asqueel.dialects.postgres import PostgresDialect
from asqueel.dialects.sqlite import SqliteDialect
from asqueel.query_plan import Projection, QueryPlan, TableRef, concat


ORACLE = json.loads((Path(__file__).parents[1] / 'oracles/legacy_renderer.json').read_text())


@pytest.mark.parametrize('dialect_type', [PostgresDialect, SqliteDialect])
@pytest.mark.parametrize('case', ORACLE)
def test_clause_assembly_matches_original_adapter_without_scanning(dialect_type, case, monkeypatch):
    dialect = dialect_type()

    def forbidden(*args, **kwargs):
        pytest.fail('Renderer must not invoke the expression scanner')

    monkeypatch.setattr(dialect, 'tokens', forbidden)
    monkeypatch.setattr('asqueel.dialects.postgres._tokens', forbidden)
    monkeypatch.setattr('asqueel.dialects.sqlite._tokens', forbidden)
    options = case['arguments']
    kwargs = {name: concat(options[name]) for name in ('where', 'group_by', 'having', 'order_by')
              if name in options}
    kwargs.update({name: options[name] for name in ('limit', 'offset') if name in options})
    plan = QueryPlan('select', TableRef('s', 't'), dialect=dialect.name,
                     projections=(Projection(concat(options['columns']), None, ResultColumn('value')),),
                     **kwargs)
    statement = dialect.render(plan)
    # The legacy SELECT prefix has two spaces; fragment text stays byte-for-byte.
    assert ''.join(statement.parts) == case['sql'].replace('SELECT  ', 'SELECT ', 1)


@pytest.mark.parametrize('dialect_type', [PostgresDialect, SqliteDialect])
def test_multiple_projection_separator_matches_legacy_compiled_query(dialect_type, monkeypatch):
    dialect = dialect_type()
    monkeypatch.setattr(dialect, 'tokens', lambda *args: pytest.fail('Unexpected scanner'))
    plan = QueryPlan('select', TableRef('s', 't'), dialect=dialect.name, projections=tuple(
        Projection(concat(f'{value} AS c{value}'), None, ResultColumn(f'c{value}')) for value in (1, 2)))
    assert ''.join(dialect.render(plan).parts).startswith('SELECT 1 AS c1,\n2 AS c2\n FROM ')
