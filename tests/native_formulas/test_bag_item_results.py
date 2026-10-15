"""Controlled PostgreSQL values beyond the legacy no-crash bagItem tests."""
from datetime import date, datetime, time, timezone
from decimal import Decimal
from uuid import uuid4

import pytest

from asqueel import build_database
from tests.native_compiler.test_bag_items import source
from tests.native_support import postgres_dsn

XML = '''<GenRoBag><specs><weight unit="kg">12.5</weight><color>blue &amp; &lt;sky&gt;</color>
<price>19.95</price></specs><repeated>first</repeated><repeated>second</repeated>
<typed><integer>42</integer><bigint>12345678901</bigint><real>1.25</real>
<boolean>true</boolean><date>2026-02-03</date><time>04:05:06</time>
<stamp>2026-02-03T04:05:06</stamp><utc>2026-02-03T04:05:06Z</utc></typed></GenRoBag>'''


@pytest.fixture(scope='module')
def db():
    config = source()
    root = config.source['db']
    schema = 'bag_items_' + uuid4().hex
    root.packages().package('app', sqlschema=schema)
    root.connection('main', dsn=postgres_dsn())
    with build_database(config) as database:
        quote = database.dialect.quote_identifier
        target = quote(schema) + '.app_item'
        try:
            database.execute('CREATE SCHEMA ' + quote(schema))
            database.execute(f'CREATE TABLE {target} (id BIGINT, payload TEXT, parent_id BIGINT)')
            for id, xml, parent in [(1, XML, None), (2, None, 1),
                                    (3, '<GenRoBag/>', None), (4, '<GenRoBag><specs><color/></specs></GenRoBag>', None),
                                    (5, '<GenRoBag><specs><weight>0</weight><color>red</color></specs></GenRoBag>', 1)]:
                database.execute(f'INSERT INTO {target} VALUES (:id,:xml,:parent)',
                                 dict(id=id, xml=xml, parent=parent))
            database.commit()
            yield database
        finally:
            database.rollback()
            database.execute('DROP SCHEMA ' + quote(schema) + ' CASCADE')
            database.commit()


def read(db, columns, id=1):
    return db.table('item').query(columns, where='$id=:id', id=id).fetch()[0]


def test_exact_text_numeric_attribute_position_and_first_match(db):
    row = read(db, '$weight,$color,$price,$unit,$position,$first,$missing,$default')
    assert dict(row) == dict(weight=Decimal('12.5'), price=Decimal('19.95'),
                            color='blue &amp; &lt;sky&gt;', unit='kg',
                            position='blue &amp; &lt;sky&gt;', first='first',
                            missing=None, default='blue &amp; &lt;sky&gt;')
    # Legacy casts the XML node to text; it does not XML-decode it in Python.
    assert row['color'] != 'blue & <sky>'


def test_typed_values_use_postgres_casts_and_existing_driver_codecs(db):
    row = read(db, '$integer,$bigint,$real,$boolean,$date,$time,$stamp,$utc')
    assert dict(row) == dict(integer=42, bigint=12345678901, real=1.25, boolean=True,
                            date=date(2026, 2, 3), time=time(4, 5, 6),
                            stamp=datetime(2026, 2, 3, 4, 5, 6),
                            utc=datetime(2026, 2, 3, 4, 5, 6, tzinfo=timezone.utc))
    assert type(row['boolean']) is bool
    assert type(row['integer']) is int


@pytest.mark.parametrize('id', [2, 3, 4])
def test_null_missing_and_empty_elements_stay_null(db, id):
    assert dict(read(db, '$weight,$color,$missing', id)) == dict(weight=None, color=None, missing=None)


def test_alias_dependencies_and_correlated_subquery_keep_values(db):
    assert dict(read(db, '$weight,$alias,$total')) == dict(
        weight=Decimal('12.5'), alias=Decimal('12.5'), total=Decimal('34.45'))
    assert dict(read(db, '$related,$nested', id=2)) == dict(related=Decimal('12.5'), nested=Decimal('12.5'))
    query = db.table('item').query('$weight, @parent_id.weight AS parent',
        where='$id=:calculated_path', calculated_path=5)
    assert dict(query.fetch()[0]) == dict(weight=0, parent=Decimal('12.5'))
    assert dict(query.fetch()[0]) == dict(weight=0, parent=Decimal('12.5'))


def test_where_order_group_and_distinct_count_use_extraction(db):
    table = db.table('item')
    query = table.query('$id,$weight', where='$weight IS NOT NULL', order_by='$weight DESC')
    assert [dict(row) for row in query.fetch()] == [dict(id=1, weight=Decimal('12.5')), dict(id=5, weight=0)]
    grouped = table.query('$weight,COUNT(*) AS n', where='$weight IS NOT NULL',
                          group_by='$weight', having='COUNT(*)>0', order_by='$weight')
    assert [dict(row) for row in grouped.fetch()] == [dict(weight=0, n=1), dict(weight=Decimal('12.5'), n=1)]
    assert table.query('$color', distinct=True).count() == 3


@pytest.mark.parametrize('xml', ['not XML', '<GenRoBag><specs><weight>not numeric</weight></specs></GenRoBag>'])
def test_bad_xml_and_bad_cast_remain_database_errors(db, xml):
    import psycopg
    quote = db.dialect.quote_identifier
    schema = db.model.table('app.item').physical_schema
    try:
        db.execute(f'UPDATE {quote(schema)}.app_item SET payload=:xml WHERE id=1', {'xml': xml})
        with pytest.raises(psycopg.DataError):
            read(db, '$weight')
    finally:
        db.rollback()
    assert read(db, '$weight')['weight'] == Decimal('12.5')
