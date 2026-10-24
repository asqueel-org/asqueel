"""Export with query().fetch(destination=) and import with sql_insert(file) as CSV, JSON and TYTX."""
import datetime
from decimal import Decimal
from io import StringIO

import pytest

from tests.option_tables_support import IMPLEMENTATIONS, migrated_db
from tests.package_layout_support import write_layout

ROWS = [
    {'id': 1, 'name': 'Tea', 'price': Decimal('1.50'), 'stock': 8, 'active': True,
     'since': datetime.date(2026, 10, 20)},
    {'id': 2, 'name': 'Coffee', 'price': Decimal('2.25'), 'stock': None, 'active': False,
     'since': datetime.date(2025, 1, 31)},
]
COLUMNS = '$id, $name, $price, $stock, $active, $since'


UPPER = '''
class Table:
    def config_db(self, pkg):
        table = pkg.table('upper', pkey='id')
        table.column('id', dtype='L')
        table.column('name')
        table.column('price', dtype='N', size='10,2')
        table.column('stock', dtype='L')
        table.column('active', dtype='B')
        table.column('since', dtype='D')

    def adaptRecord(self, record):
        record = super().adaptRecord(record)
        record['name'] = record['name'].upper()
        return record
'''


def declare(pkg):
    for name in ('product', 'copy'):
        table = pkg.table(name, pkey='id')
        table.column('id', dtype='L')
        table.column('name')
        table.column('price', dtype='N', size='10,2')
        table.column('stock', dtype='L')
        table.column('active', dtype='B')
        table.column('since', dtype='D')


@pytest.fixture(params=IMPLEMENTATIONS)
def db(request, tmp_path):
    with migrated_db(request.param, tmp_path, declare, path=write_layout(tmp_path / 'app', upper=UPPER)) as db:
        db.table('app.product').sql_insert([dict(row) for row in ROWS])
        db.commit()
        yield db


def rows(db, table):
    return [dict(row) for row in db.table(table).query(columns=COLUMNS, order_by='$id').fetch()]


@pytest.mark.parametrize('extension', ['csv', 'json', 'tytx'])
def test_a_file_export_reimports_with_the_same_typed_values(db, tmp_path, extension):
    path = tmp_path / f'products.{extension}'
    assert db.table('app.product').query(columns=COLUMNS, order_by='$id').fetch(destination=path) == 2
    with open(path, encoding='utf-8') as stream:
        assert db.table('app.copy').sql_insert(stream) == 2
    db.commit()
    assert rows(db, 'app.copy') == ROWS


def test_tytx_keeps_the_types_one_record_per_line(db):
    stream = StringIO()
    db.table('app.product').query(columns=COLUMNS, order_by='$id').fetch(destination=stream, format='tytx')
    lines = stream.getvalue().splitlines()
    assert len(lines) == 2
    assert '::N"' in lines[0] and '"2026-10-20::D"' in lines[0] and lines[0].endswith('::JS')


def test_csv_text_is_adapted_to_the_column_dtype(db):
    data = StringIO('id,name,price,stock,active,since\n7,Mug,3.10,,yes,2026-01-02\n')
    assert db.table('app.copy').sql_insert(data, format='csv') == 1
    db.commit()
    assert rows(db, 'app.copy') == [{'id': 7, 'name': 'Mug', 'price': Decimal('3.10'), 'stock': None,
                                     'active': True, 'since': datetime.date(2026, 1, 2)}]


def test_a_text_that_does_not_convert_names_record_and_column(db):
    data = StringIO('id,name,stock\n1,ok,3\n2,bad,many\n')
    with pytest.raises(ValueError, match=r"app\.copy record 2: column 'stock': 'many' is not a L value"):
        db.table('app.copy').sql_insert(data, format='csv')
    db.rollback()


def test_a_key_that_is_not_a_column_raises(db):
    with pytest.raises(ValueError, match="'colour' is not a column of app.copy"):
        db.table('app.copy').sql_insert(StringIO('[{"id": 1, "colour": "red"}]'), format='json')
    db.rollback()


def test_a_table_class_can_override_adaptRecord(db):
    db.table('app.upper').sql_insert(StringIO('id,name\n1,tea\n'), format='csv')
    db.commit()
    assert [row['name'] for row in rows(db, 'app.upper')] == ['TEA']


def test_adapt_false_inserts_the_values_as_they_are(db):
    db.table('app.upper').sql_insert(StringIO('{"id": 1, "name": "tea"}::JS\n'), format='tytx', adapt=False)
    db.commit()
    assert [row['name'] for row in rows(db, 'app.upper')] == ['tea']


def test_adapt_true_on_a_list(db):
    db.table('app.copy').sql_insert([{'id': '5', 'name': 'x', 'since': '2026-02-03'}], adapt=True)
    db.commit()
    assert rows(db, 'app.copy')[0]['since'] == datetime.date(2026, 2, 3)


def test_many_rows_move_in_blocks(db, tmp_path):
    products = db.table('app.copy')
    products.sql_insert([{'id': n, 'name': f'p{n}', 'price': Decimal(n) / 100, 'stock': n,
                          'active': n % 2 == 0, 'since': datetime.date(2026, 1, 1)}
                         for n in range(1, 2501)])
    db.commit()
    path = tmp_path / 'many.json'
    assert products.query(columns=COLUMNS, order_by='$id').fetch(destination=path) == 2500
    db.table('app.product').sql_delete({'id': 1})
    db.table('app.product').sql_delete({'id': 2})
    with open(path, encoding='utf-8') as stream:
        assert db.table('app.product').sql_insert(stream, format='json') == 2500
    db.commit()
    assert rows(db, 'app.product') == rows(db, 'app.copy')


@pytest.mark.parametrize('call, message', [
    (lambda q, t: q.fetch(destination=t / 'x.xlsx'), "extension '.xlsx'"),
    (lambda q, _: q.fetch(destination=StringIO()), 'needs format='),
    (lambda q, _: q.fetch(format='csv'), 'format= needs destination='),
    (lambda q, _: q.fetch(destination=StringIO(), format='xml'), "Unknown data format 'xml'"),
])
def test_outside_the_grammar_raises(db, tmp_path, call, message):
    with pytest.raises(ValueError, match=message):
        call(db.table('app.product').query(columns=COLUMNS), tmp_path)


def test_format_is_for_files_only(db):
    with pytest.raises(ValueError, match='format= is for a file'):
        db.table('app.copy').sql_insert({'id': 1}, format='csv')
