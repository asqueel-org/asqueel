"""Execute native subQueryColumn against controlled rows on both dialects."""

from datetime import datetime, timezone
from decimal import Decimal
from uuid import uuid4
import xml.etree.ElementTree as ET

import pytest

from asqueel import SqlEnvironment, build_database
from tests.native_compiler.test_subquery_columns import source
from tests.native_formulas.conftest import SQL_TYPES
from tests.native_support import postgres_dsn


@pytest.fixture(scope='module', params=['postgres', 'sqlite'])
def db(request, tmp_path_factory):
    backend = request.param
    config = source(backend)
    root = config.source['db']
    schema = 'sq_columns_' + uuid4().hex
    root.packages().package('app', sqlschema=schema)
    root.connection(
        implementation=backend,
        **(
            {'dsn': postgres_dsn()}
            if backend == 'postgres'
            else {'database': str(tmp_path_factory.mktemp('sq_columns') / 'test.db')}
        ),
    )
    db = build_database(config, environment=SqlEnvironment({'current_owner': 99}))
    try:
        quote = db.adapter.adaptSqlName
        try:
            if backend == 'postgres':
                db.execute('CREATE SCHEMA ' + quote(schema))
            for table in db.model.tables.values():
                columns = ','.join(
                    f'{quote(c.sqlname)} {SQL_TYPES.get(c.dtype, "TEXT")}'
                    for c in table.columns.values()

                )
                db.execute(f'CREATE TABLE {quote(schema)}.{quote(table.sqlname)} ({columns})')
            for id, parent in [(1, None), (2, 1), (3, None), (99, None)]:
                db.execute(
                    f'INSERT INTO {quote(schema)}.app_owner(id,parent_id) VALUES (:id,:parent)',
                    dict(id=id, parent=parent),
                )
            values = [
                (1, 1, 10, 'a', None, None),
                (2, 1, 20, 'b<&>', True, None),
                (3, 1, 30, None, False, datetime(2026, 1, 1, tzinfo=timezone.utc)),
                (4, 1, None, 'd', False, None),
                (5, 2, 7, 'e', False, None),
                (6, 99, 50, 'f', False, None),
                (7, 99, 60, 'g', True, None),
            ]
            for id, owner, amount, label, draft, deleted in values:
                db.execute(
                    f'INSERT INTO {quote(schema)}.app_item '
                    '(id,owner_id,amount,label,__is_draft,__del_ts) '
                    'VALUES (:id,:owner,:amount,:label,:draft,:deleted)',
                    dict(
                        id=id, owner=owner, amount=amount, label=label, draft=draft, deleted=deleted
                    ),
                )
            db.commit()
            yield db
        finally:
            db.rollback()
            if backend == 'postgres':
                db.execute('DROP SCHEMA ' + quote(schema) + ' CASCADE')
                db.commit()
    finally:
        db.closeConnection()


def read(db, columns, id=1, **kwargs):
    return db.table('app.owner').query(columns, where='$id=:id', id=id, **kwargs).fetch()[0]


def test_scalar_alias_dependency_null_and_locals_match_values(db):
    row = read(db, '$maximum,$max_alias,$dependent,$twice,$triple')
    assert dict(row) == dict(maximum=30, max_alias=30, dependent=150, twice=120, triple=180)
    assert dict(read(db, '$maximum,$twice', id=3)) == dict(maximum=None, twice=None)
    assert read(db, '$aggr_max')['aggr_max'] == 30
    query = db.table('app.owner').query(
        '$id,$maximum', where='$maximum>:minimum', minimum=15, order_by='$maximum DESC'
    )
    assert [dict(row) for row in query.fetch()] == [{'id': 99, 'maximum': 60}, {'id': 1, 'maximum': 30}]
    assert [dict(row) for row in query.fetch()] == [{'id': 99, 'maximum': 60}, {'id': 1, 'maximum': 30}]


@pytest.fixture
def pg(db):
    if db.adapter.dialect != 'postgres':
        pytest.skip('Legacy JSON/XML subQueryColumn wrappers are PostgreSQL-specific')
    return db


def xml_rows(value):
    return [
        dict((c.tag, c.text) for c in node) for node in ET.fromstring('<root>' + value + '</root>')
    ]


def test_json_pagination_nulls_and_distinct(pg):
    expected = [dict(id=3, label=None, amount=30), dict(id=2, label='b<&>', amount=20)]
    assert read(pg, '$json')['json'] == expected
    assert read(pg, '$json', distinct=True)['json'] == expected
    assert read(pg, '$json', id=3)['json'] is None


def test_xml_pagination_escaping_null_omission_and_distinct(pg):
    value = read(pg, '$xml')['xml']
    assert isinstance(value, str)
    assert 'b&lt;&amp;&gt;' in value
    assert xml_rows(value) == [dict(id='3', amount='30'), dict(id='2', label='b<&>', amount='20')]
    # SQL/XML escapes "_x" in identifiers, identically for the legacy wrapper.
    assert all(
        n.tag == 'app_owner_x005F_xml_x005F_xml'
        for n in ET.fromstring('<root>' + value + '</root>')
    )
    assert read(pg, '$xml', distinct=True)['xml'] == value
    assert read(pg, '$xml', id=3)['xml'] is None


def test_grouping_nested_queries_and_sql_aliases(pg):
    assert read(pg, '$json_group')['json_group'] == [dict(owner_id=1, total=60)]
    assert read(pg, '$json_group', id=2)['json_group'] is None  # HAVING excludes it.
    assert xml_rows(read(pg, '$xml_group')['xml_group']) == [dict(owner_id='1', total='60')]
    assert read(pg, '$nested_json')['nested_json'] == [dict(id=2, maximum=7, json=None)]
    result = read(pg, '$json_join')['json_join']
    assert len(result) == 4 and all(row['owner'] == 1 for row in result)
    assert sorted(row['label'] or '' for row in result) == ['', 'a', 'b<&>', 'd']


def test_aggregate_var_bindings_and_visibility_overrides(pg):
    row = read(pg, '$json_locals,$xml_locals,$twice')
    assert sorted(x['value'] for x in row['json_locals'] if x['value'] is not None) == [40, 80, 120]
    assert sorted(Decimal(x['value']) for x in xml_rows(row['xml_locals']) if 'value' in x) == [
        40,
        80,
        120,
    ]
    assert row['twice'] == 120
    assert read(pg, '$json_visible')['json_visible'] is None  # explicit partition=99
    assert read(pg, '$json_visible', id=99)['json_visible'] == [dict(id=6)]
    assert xml_rows(read(pg, '$xml_visible', id=99)['xml_visible']) == [dict(id='6')]
