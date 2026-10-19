"""Minimal SELECT over the real hierarchy: no descriptor conversion or DB I/O."""
from copy import deepcopy
from datetime import date
from decimal import Decimal
import re

import pytest

from asqueel import SqlDatabase, SqlDatabaseConfig, UnusedQueryParameterWarning
from asqueel.configuration import _owned_handler
from asqueel.adapters.postgres import SqlDbAdapter as PostgresAdapter
from asqueel.adapters.sqlite import SqlDbAdapter as SqliteAdapter
from examples.test_invoice_pg import source as invoice_source
from tests.object_tree.test_invoice import TABLES


@pytest.fixture(autouse=True)
def no_io(monkeypatch):
    def denied(*args, **kwargs):
        pytest.fail('Compilation must not open a connection or execute SQL')
    for driver in (PostgresAdapter, SqliteAdapter):
        monkeypatch.setattr(driver, 'connect', denied)
        monkeypatch.setattr(driver, 'execute', denied)
    monkeypatch.setattr(SqlDatabase, 'execute', denied)


def recipe(implementation):
    source = SqlDatabaseConfig()
    db = source.source.db('compile_only', implementation=implementation)
    pkg = db.packages().package('sales', sqlschema='main', sqlprefix=True)
    customer = pkg.table('customer', pkey='id')
    customer.column('id', dtype='L')
    customer.column('name')
    invoice = pkg.table('invoice', pkey='id')
    invoice.column('id', dtype='L')
    invoice.column('customer_id', dtype='L').relation('sales.customer.id')
    invoice.column('total', dtype='N')
    invoice.column('issued', dtype='D')
    invoice.column('label', sqlname='label_sql')
    invoice.formulaColumn('double_total', sql_formula='$total * 2', dtype='N')
    invoice.aliasColumn('copied_id', relation_path='id')
    return source, invoice


def bind(source):
    return SqlDatabase(model=source.render(mode='objects_tree'), config=_owned_handler(source))


@pytest.fixture(params=['postgres', 'sqlite'])
def db(request):
    source, _ = recipe(request.param)
    with bind(source) as database:
        database.currentEnv.update(workdate=date(2026, 10, 14))
        yield database


def assert_bindings(query):
    pattern = r'%\((\w+)\)s' if query.dialect == 'postgres' else r':(\w+)'
    assert set(re.findall(pattern, query.sql)) == set(query.params)


def test_legacy_physical_expression_where_order_limit(db):
    # Same case as probes/test_legacy_minimal_select.py, without legacy's hidden pkey.
    params = dict(threshold=Decimal('100.50'), day=date(2026, 10, 14), empty=None)
    compiled = db.table('sales.invoice').query(
        columns='$id AS code, COALESCE($total,0) AS amount, '
                'CASE WHEN $total >= :threshold THEN 1 ELSE 0 END AS category',
        where='$issued <= :day AND (:empty IS NULL OR $id = :empty)',
        order_by='$total DESC, $id', limit=3, offset=2, sqlparams=params).compiled
    assert 'COALESCE("t0"."total",0)' in compiled.sql
    assert 'CASE WHEN "t0"."total" >=' in compiled.sql
    assert 'FROM "main"."sales_invoice"' in compiled.sql
    assert 'ORDER BY "t0"."total" DESC, "t0"."id"' in compiled.sql
    assert 'LIMIT 3' in compiled.sql and 'OFFSET 2' in compiled.sql
    assert 'JOIN' not in compiled.sql
    assert compiled.params == params
    assert isinstance(compiled.params['threshold'], Decimal)
    assert isinstance(compiled.params['day'], date)
    assert compiled.input_parameters == ('day', 'empty', 'threshold')
    assert [(c.name, c.dtype, c.source) for c in compiled.columns] == [
        ('code', 'L', 'sales.invoice.id'), ('amount', None, None), ('category', None, None)]
    assert compiled.columns[0].ui == {}
    assert_bindings(compiled)
    assert db.outcome == 'not_started'
    assert db._connections == {}


def test_reuse_keeps_legacy_binding_names_and_detached_inputs(db):
    values = [1, 2]
    query = db.table('sales.invoice').query(
        columns='$id', where='$id IN :ids AND $id <> :ids_0 AND $issued=:env_workdate',
        ids=values, ids_0=3)
    values.append(99)
    first = query.compiled
    with db.tempEnv(workdate=date(2026, 10, 15)):
        second = query.compiled
    third = query.compiled
    assert first is second is third
    assert 'workdate' in first.environment_keys
    # The legacy postgres3 allocator overwrites ids_0; SQLite uses ids0/ids1.
    # Preserve this observed contract, rather than silently add a new allocator.
    pg = db.adapter.dialect == 'postgres'
    assert first.params['ids_0'] == (1 if pg else 3)
    assert sorted(v for v in first.params.values() if isinstance(v, int)) == ([1, 2] if pg else [1, 2, 3])
    for compiled in (first, second, third):
        assert_bindings(compiled)


def test_legacy_references_in_literals_comments_and_cast(db):
    compiled = db.table('sales.invoice').query(
        columns="CAST($total AS NUMERIC) AS amount, '$id' AS literal",
        where='$id=:id /* $total */', id=3).compiled
    assert "'\"t0\".\"id\"' AS literal" in compiled.sql
    assert '/* "t0"."total" */' in compiled.sql
    assert 'CAST("t0"."total" AS NUMERIC)' in compiled.sql
    assert compiled.params == {'id': 3}
    assert compiled.input_parameters == ('id',)


@pytest.mark.parametrize('db', ['postgres'], indirect=True)
def test_postgres_cast(db):
    query = db.table('sales.invoice').query(
        columns='$total::numeric AS amount',
        where='$id=:id', id=7).compiled
    assert '"t0"."total"::numeric' in query.sql
    assert query.params == {'id': 7}


@pytest.mark.parametrize('columns,where', [
    ("'$missing' AS literal", None),
    ('$id', '$id=3 /* $missing */'),
    ('$$:unused $missing$$ AS literal', None),
])
def test_legacy_discovers_unknown_fields_in_all_sql_text(db, columns, where):
    with pytest.raises(ValueError, match='Unknown column.*missing'):
        db.table('sales.invoice').query(columns=columns, where=where).compiled


def test_physical_name_and_quoted_result_alias(db):
    compiled = db.table('sales.invoice').query(columns='$label AS "Display label"').compiled
    assert '"t0"."label_sql" AS "Display label"' in compiled.sql
    assert compiled.columns[0].source == 'sales.invoice.label'


@pytest.mark.parametrize('kwargs,error,message', [
    ({'columns': '$missing'}, ValueError, 'Unknown column'),
    ({'columns': '$id', 'limit': -1}, ValueError, 'nonnegative'),
    ({'columns': '$id', 'offset': True}, ValueError, 'nonnegative'),
])
def test_unavailable_features_fail_explicitly(db, kwargs, error, message):
    with pytest.raises(error, match=message):
        db.table('sales.invoice').query(**kwargs).compiled
    assert db._connections == {}


def test_unused_keyword_warns_and_the_query_compiles(db):
    with pytest.warns(UnusedQueryParameterWarning, match="query keyword 'unused' is not used by the query"):
        db.table('sales.invoice').query(columns='$id', unused=3).compiled


def test_no_model_conversion_and_no_sql_state_on_objects(db, monkeypatch):
    def denied(*args, **kwargs):
        pytest.fail('Compilation tried to build/use the old descriptor model')
    monkeypatch.setattr('asqueel.model.resolve_model', denied)
    monkeypatch.setattr('asqueel.compiler.QueryCompiler', denied)
    table = db.table('sales.invoice').model
    attrs = deepcopy(table.attributes)
    columns = {name: deepcopy(col.attributes) for name, col in table.columns.items()}
    relations = db.model.relations.to_xml()
    db.model.src = None  # compilation must only use the objects
    for _ in range(2):
        assert table.dbtable.query(columns='$id,$label', where='$id=:id', id=2).compiled.sql
    assert db.compiler.model is db.model
    assert table.attributes == attrs
    assert {name: col.attributes for name, col in table.columns.items()} == columns
    assert db.model.relations.to_xml() == relations
    assert table._relation_tree is not None  # structural resolver cache, no SQL state


@pytest.mark.parametrize('feature', ['draft', 'deleted', 'partition', 'order'])
def test_implicit_behaviour_and_explicit_bypass(feature):
    source, table = recipe('sqlite')
    if feature == 'draft':
        table.options().sys_fields(id=False, draft=True, ldel=False)
    elif feature == 'deleted':
        table.options().sys_fields(id=False, ldel=True)
    elif feature == 'partition':
        table.attr['partition_customer_id'] = 'customer'
    else:
        table.attr['order_by'] = '$total DESC'
    with bind(source) as db:
        db.currentEnv.update(current_customer=12)
        table = db.table('sales.invoice')
        default = table.query(columns='$id').compiled
        if feature == 'order':
            assert 'ORDER BY "t0"."total" DESC' in default.sql
        else:
            assert 'WHERE' in default.sql
        if feature == 'partition':
            assert list(default.params.values()) == [12]
        query = table.query(columns='$id', excludeDraft=False, excludeLogicalDeleted=False,
                            ignorePartition=True, order_by='$id').compiled
        assert 'WHERE' not in query.sql


@pytest.fixture(scope='module', params=['postgres', 'sqlite'])
def invoice_databases(request):
    source = invoice_source()
    source.source.get_node('db').attr['implementation'] = request.param
    with bind(source) as tree, source.render() as previous:
        yield tree, previous


@pytest.mark.parametrize('name', TABLES)
def test_physical_select_matches_previous_compiler_on_74_models(invoice_databases, name):
    tree, previous = invoice_databases
    model = tree.model.table(name)
    # Compare physical fields independently of star expansion and implicit filters.
    columns = ','.join('$' + name for name in model.columns)
    kwargs = dict(columns=columns, order_by=columns.split(',')[0], limit=3, excludeDraft=False,
                  excludeLogicalDeleted=False, ignorePartition=True)
    actual = tree.table(name).query(**kwargs).compiled
    expected = previous.table(name).query(**kwargs).compiled
    assert actual == expected


@pytest.mark.parametrize('columns,limit,names', [
    ('$account_name', 5, ['account_name']),
    ('$account_name, $email, $phone', 3, ['account_name', 'email', 'phone']),
])
def test_port_of_legacy_physical_columns(invoice_databases, columns, limit, names):
    tree, _ = invoice_databases
    compiled = tree.table('invc.customer').query(
        columns=columns, limit=limit, excludeDraft=False,
        excludeLogicalDeleted=False, ignorePartition=True).compiled
    assert f'LIMIT {limit}' in compiled.sql
    assert [c.name for c in compiled.columns] == names
    assert 'JOIN' not in compiled.sql


@pytest.mark.parametrize('implementation', ['postgres', 'sqlite'])
def test_quoted_physical_names_and_live_object_identity(implementation):
    source, table = recipe(implementation)
    table.attr['sqlname'] = 'Invoice Records'
    table.column('logical_name', sqlname='db"name')
    with bind(source) as db:
        table = db.table('sales.invoice')
        compiled = table.query(columns='$logical_name AS "Value"').compiled
        assert '"main"."Invoice Records"' in compiled.sql
        assert '"t0"."db""name" AS "Value"' in compiled.sql
        assert compiled.columns[0].source == 'sales.invoice.logical_name'
        column = table.model.columns['logical_name']
        column.attributes['sqlname'] = 'renamed'
        assert '"t0"."renamed"' in table.query(columns='$logical_name').compiled.sql
        assert table.column('logical_name') is column


def test_empty_collection_and_legacy_params(db):
    compiled = db.table('sales.invoice').query(
        columns='$id', where='$id IN :ids', sqlparams={'ids': [], 'unused': 3}).compiled
    pg = db.adapter.dialect == 'postgres'
    assert compiled.params == ({'ids': [], 'unused': 3} if pg else {'unused': 3})
    assert compiled.input_parameters == ('ids',)
    empty = 'WHERE (FALSE)' if pg else 'IN ()'
    assert empty in compiled.sql


def test_result_metadata_uses_existing_validation():
    from asqueel.model import column_ui
    with pytest.raises(ValueError, match='UI metadata cannot override column semantics'):
        column_ui('sales.invoice.id', 'sales.invoice.id', {'sales.invoice.id': {'dtype': 'T'}})
