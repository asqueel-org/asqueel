"""CREATE TABLE ... AS SELECT with a bound parameter, through the adapter's own binding."""
import pytest

from tests.option_tables_support import IMPLEMENTATIONS, migrated_db


def declare(pkg):
    note = pkg.table('note', pkey='id')
    note.column('id', size=':22')
    note.column('text')


@pytest.fixture(params=IMPLEMENTATIONS)
def db(request, tmp_path):
    with migrated_db(request.param, tmp_path, declare) as db:
        db.table('app.note').sql_insert([{'id': 'a', 'text': 'x'}, {'id': 'b', 'text': 'y'},
                                         {'id': 'c', 'text': 'x'}])
        db.commit()
        yield db


def test_ctas_with_a_bound_parameter_materializes_the_matching_rows(db):
    model = db.table('app.note').model
    source = f'{model.sqlschema}.{model.sqlname}'
    target = f'{model.sqlschema}.note_ctas'
    unlogged = 'UNLOGGED ' if db.adapter.dialect == 'postgres' else ''
    db.execute(f'CREATE {unlogged}TABLE {target} AS SELECT id FROM {source} WHERE text = :p', {'p': 'x'})
    db.commit()
    assert [row['id'] for row in db.execute(f'SELECT id FROM {target} ORDER BY id').fetchall()] == ['a', 'c']
