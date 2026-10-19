"""Phase 2: legacy to-one contracts and the explicitly agreed many-call boundary."""
from copy import deepcopy
import json
from pathlib import Path

import pytest

from asqueel import SqlDatabase, UnsupportedFeatureError
from asqueel.configuration import _owned_handler
from asqueel.adapters.postgres import SqlDbAdapter as PostgresAdapter
from asqueel.adapters.sqlite import SqlDbAdapter as SqliteAdapter
from asqueel.compiler import _TreeContext
from asqueel.sql_compiled_query import SqlCompiledQuery
from examples.test_invoice_pg import source
from tests.object_tree.test_legacy_rewrite_contracts import normalized

ORACLE = json.loads((Path(__file__).parents[1]/'oracles/legacy_tree_relations.json').read_text())


@pytest.fixture(scope='module', params=['postgres', 'sqlite'])
def db(request):
    def forbidden(*args, **kwargs):
        pytest.fail('Compilation attempted database I/O')
    with pytest.MonkeyPatch.context() as patch:
        for driver in (PostgresAdapter, SqliteAdapter):
            patch.setattr(driver, 'connect', forbidden)
            patch.setattr(driver, 'execute', forbidden)
        patch.setattr(SqlDatabase, 'execute', forbidden)
        config = source()
        config.source.get_node('db').attr['implementation'] = request.param
        database = SqlDatabase(model=config.render(mode='objects_tree'), config=_owned_handler(config))
        try:
            yield database
        finally:
            database.closeConnection()


@pytest.mark.parametrize('name', [c['request']['name'] for c in ORACLE['cases']
                                 if c['dialect'] == 'sqlite'])
def test_all_declared_relations_against_frozen_legacy(db, name):
    record = next(c for c in ORACLE['cases'] if c['request']['name'] == name
                  and c['dialect'] == db.adapter.dialect)
    request, expected = record['request'], record['expected']
    joiner = request['joiner']
    query = db.table(request['table']).query(request['columns'], **request['options'])
    if joiner['mode'] != 'O' and not joiner.get('one_one'):
        # Includes the two legacy KeyError limits: neither is repaired or compiled.
        with pytest.raises(UnsupportedFeatureError, match='a path through the many relation .* is not available in this release'):
            query.compiled
    else:
        actual = query.compiled
        assert normalized(actual.sql) == normalized(expected['sql'])
        assert dict(actual.params) == {k: v for k, v in expected['params'].items() if k != 'jc_kwargs'}
        assert query.compiled == actual
    assert db._connections == {}


@pytest.mark.parametrize('expression, operation, arguments', [
    ('@invoices.sum($total)', 'sum', ('$total',)),
    ('@invoices.calc($total:sum AS total_sum,$total:avg AS total_avg)', 'calc',
     ('$total:sum AS total_sum', '$total:avg AS total_avg')),
    ('@invoices.first($id, order_by $total ASC, limit 1)', 'first',
     ('$id', ' order_by $total ASC', ' limit 1')),
    ('@invoices.last($id)', 'last', ('$id',)),
    ("@invoices.sum(COALESCE($total,0), 'a)b,c', :amount)", 'sum',
     ('COALESCE($total,0)', " 'a)b,c'", ' :amount')),
    ('@invoices.unknown()', 'unknown', ()),
])
def test_recognition_and_getattr_without_handlers(db, monkeypatch, expression, operation, arguments):
    seen = []
    original = _TreeContext._dispatch_many_operation

    def record(self, relation, name, args, **context):
        seen.append((relation.label, name, args, list(self.cpl.joins)))
        return original(self, relation, name, args, **context)

    monkeypatch.setattr(_TreeContext, '_dispatch_many_operation', record)
    lookups = []

    def missing(self, name):
        lookups.append(name)
        raise AttributeError(name)

    monkeypatch.setattr(_TreeContext, '__getattr__', missing, raising=False)
    assert {name for name in vars(_TreeContext) if name.startswith('many_')} == {'many_aggr'}
    with pytest.raises(UnsupportedFeatureError, match=f'many_{operation} is not available in this release'):
        db.compiler.plan_select('invc.customer', columns=expression,
                                exclude_draft=False, exclude_logical_deleted=False,
                                ignore_partition=True)
    assert seen == [('@invoices', operation, arguments, [])]
    assert lookups == [f'many_{operation}']


@pytest.mark.parametrize('clause', ['columns', 'where', 'order_by', 'group_by', 'having'])
def test_many_operations_recognized_in_clauses(db, clause):
    options = dict(columns='$id', exclude_draft=False, exclude_logical_deleted=False,
                   ignore_partition=True)
    options[clause] = '@invoices.sum($total)'
    with pytest.raises(UnsupportedFeatureError, match='many_sum is not available in this release'):
        db.compiler.plan_select('invc.customer', **options)


def test_nested_to_one_then_many_and_symbolic_input(db):
    with pytest.raises(UnsupportedFeatureError, match='many_sum is not available in this release'):
        db.compiler.plan_select('invc.invoice', '@customer_id.@invoices.sum($total)')
    with pytest.raises(UnsupportedFeatureError, match='many_sum is not available in this release'):
        db.compiler.plan_select('invc.customer', '$id', where='$id=:other',
                                sqlparams={'other': '@invoices.sum($total)'},
                                exclude_draft=False, exclude_logical_deleted=False,
                                ignore_partition=True)


def test_recognizer_requires_closing_parenthesis(db):
    with pytest.raises(ValueError, match='missing closing parenthesis'):
        db.compiler.plan_select('invc.customer', '@invoices.sum(COALESCE($total,0)')


def test_many_traversal_does_not_allocate_join(db):
    context = db.compiler._context('invc.customer')
    with pytest.raises(UnsupportedFeatureError, match='a path through the many relation @invoices is not available'):
        context.get_field_alias('@invoices.total')
    assert not context.cpl.joins
    assert list(context.aliases.values()) == ['t0']
    assert not hasattr(context.cpl, 'explodingColumns')


def test_new_container_is_independent_and_compilation_is_local(db, monkeypatch):
    import importlib.util
    import asqueel.compiler as compiler
    assert importlib.util.find_spec('asqueel.query_plan') is None
    assert not hasattr(compiler, '_SelectCompiler')
    assert not hasattr(db.adapter, 'render')
    attrs = {table.fullname: deepcopy(table.attributes) for table in db.model.tables.values()}
    relations = db.model.relations.to_xml()
    params = {'minimum': 12}
    plan = db.compiler.plan_select('invc.invoice', '$id,@customer_id.account_name AS customer',
                                  where='$total>:minimum', sqlparams=params,
                                  order_by='@customer_id.account_name',
                                  exclude_draft=False, exclude_logical_deleted=False,
                                  ignore_partition=True)
    assert type(plan) is SqlCompiledQuery
    assert isinstance(plan.columns, str) and isinstance(plan.where, str)
    assert len(plan.joins) == 1
    assert plan.aliasDict == {'"customer"': '$_customer_id_account_name'}
    assert plan.relationDict == {'pkey': 'id', 'id': 'id',
                                '_customer_id_account_name': '@customer_id.account_name', 'total': 'total'}
    first = db.compiler.compile_plan(plan)
    params['minimum'] = 99
    other = db.compiler.plan_select('invc.invoice_row', '$id,@invoice_id.@customer_id.account_name',
                                   order_by='$id',
                                   exclude_draft=False, exclude_logical_deleted=False,
                                   ignore_partition=True)
    assert 'AS "t2"' in other.joins[1]
    assert db.compiler.compile_plan(plan) == first
    assert first.params == {'minimum': 12}
    assert {t.fullname: t.attributes for t in db.model.tables.values()} == attrs
    assert db.model.relations.to_xml() == relations


@pytest.mark.parametrize('name', ['on_root', 'on_parent'])
def test_on_references_and_parent_qualification(db, name):
    records = json.loads((Path(__file__).parents[1]/'oracles/legacy_tree_join_conditions.json').read_text())
    case = next(c for c in records['cases'] if c['dialect'] == db.adapter.dialect
                and c['request']['name'] == name)
    config = source()
    config.source.get_node('db').attr['implementation'] = db.adapter.dialect
    model = config.render(mode='objects_tree')
    node = model.relations.get_node('invc.invoice.@customer_id')
    node.attr['join_on'] = '$customer_id=@customer_id.id AND $total>:minimum'
    # Fixture-only declaration, before resolving any per-table view. The compiler
    # must read it through the registry, not reconstruct it from the source.
    before = model.relations.to_xml()
    database = SqlDatabase(model=model, config=_owned_handler(config))
    try:
        request, expected = case['request'], case['expected']
        query = database.table(request['table']).query(
            request['columns'], sqlparams=request['params'], **request['options'])
        actual = query.compiled
        assert normalized(actual.sql) == normalized(expected['sql'])
        assert dict(actual.params) == {k: v for k, v in expected['params'].items() if k != 'jc_kwargs'}
        assert query.compiled == actual
        assert model.relations.to_xml() == before
    finally:
        database.closeConnection()
