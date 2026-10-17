"""Count SQL frozen from legacy; no database access during compilation."""
import json
from pathlib import Path

import pytest

from asqueel import UnsupportedFeatureError
from tests.object_tree.test_legacy_rewrite_contracts import database, normalized  # noqa: F401

ORACLE = json.loads((Path(__file__).parents[1]/'oracles/legacy_tree_count.json').read_text())
CASES = [c for c in ORACLE['cases'] if c['dialect'] == 'sqlite']


@pytest.mark.parametrize('case', CASES, ids=lambda c: c['request']['name'])
def test_count_legacy_contract(database, case):  # noqa: F811
    request = case['request']
    expected = next(c['expected'] for c in ORACLE['cases']
                    if c['dialect'] == database.adapter.dialect and c['request']['name'] == request['name'])
    query = database.table(request['table']).query(request['columns'], sqlparams=request['params'], **request['options'])
    before = query.compiled
    actual = query._compile(database.compiler.count)
    assert normalized(actual.sql) == normalized(expected['sql'])
    assert dict(actual.params) == {k:v for k,v in expected['params'].items() if k != 'jc_kwargs'}
    again = query._compile(database.compiler.count)
    assert (again.sql,dict(again.params)) == (actual.sql,dict(actual.params))
    assert (query.compiled.sql,dict(query.compiled.params)) == (before.sql,dict(before.params))
    assert 'ORDER BY' not in actual.sql
    assert database._connections == {}


@pytest.mark.parametrize('options', [dict(columns='@invoices.sum($total)'),
    dict(columns='$id',where='@invoices.sum($total)>0'),
    dict(columns='@invoices.total',distinct=True),
    dict(columns='$id',where='@invoices.total>0')])
def test_many_still_unsupported(database, options):  # noqa: F811
    with pytest.raises(UnsupportedFeatureError):
        database.compiler.count('invc.customer', **options)


def test_count_ignores_automatic_pkey(database):  # noqa: F811
    result = database.compiler.count('invc.invoice', '$id', addPkeyColumn=True)
    assert [c.name for c in result.columns] == ['gnr_row_count']
    assert ' AS "pkey"' not in result.sql


def test_all_74_tables_compile_count_without_static_formula_execution(database):  # noqa: F811
    assert len(database.model.tables) == 74
    for name in database.model.tables:
        result = database.compiler.count(name)
        assert [c.name for c in result.columns] == ['gnr_row_count']
        assert 'count(*)' in result.sql
        assert 'ORDER BY' not in result.sql
    assert not database._connections


def test_count_environment_and_preparation_are_local(database, monkeypatch):  # noqa: F811
    compiler = database.compiler
    calls = []
    prepare = compiler.adapter.prepare_sql

    def recording(*args, **kwargs):
        calls.append(args)
        return prepare(*args, **kwargs)

    monkeypatch.setattr(compiler.adapter, 'prepare_sql', recording)
    query = database.table('invc.invoice').query('$status_label', distinct=True,
        where='$total>:env_minimum', order_by='$total')
    for minimum in (10, 20, 10):
        with database.temp_env(minimum=minimum):
            result = query._compile(compiler.count)
            assert result.params['env_minimum'] == minimum
            assert result.environment.values['minimum'] == minimum
            assert len(calls) == 1
            assert 'ORDER BY' not in result.sql
            calls.clear()
    assert not database._connections
