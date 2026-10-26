"""asqueel#19: every '%' outside a binding reaches PostgreSQL as one literal '%'."""
import pytest

from asqueel.adapters.postgres import SqlDbAdapter
from tests.option_tables_support import migrated_db


def prepared(sql, params):
    return SqlDbAdapter(None).prepareSqlText(sql, dict(params))[0]


def test_percent_doubled_in_identifiers_literals_and_comments():
    sql = 'SELECT "a%" FROM t WHERE x LIKE \'a%\' AND y=:p -- 5%'
    assert prepared(sql, {'p': 1}) == 'SELECT "a%%" FROM t WHERE x LIKE \'a%%\' AND y=%(p)s -- 5%%'


def test_percent_doubled_in_block_comments_and_dollar_and_escape_strings():
    sql = "SELECT /* 1% */ $$b%$$, E'c%' WHERE z=:p"
    assert prepared(sql, {'p': 1}) == "SELECT /* 1%% */ $$b%%$$, E'c%%' WHERE z=%(p)s"


def test_percent_doubled_without_parameters():
    assert prepared("SELECT 1 WHERE 'a' LIKE 'a%'", {}) == "SELECT 1 WHERE 'a' LIKE 'a%%'"


def declare(pkg):
    note = pkg.table('note', pkey='id')
    note.column('id', dtype='L')
    note.column('text')


@pytest.fixture
def db(tmp_path):
    with migrated_db('postgres', tmp_path, declare) as db:
        db.table('app.note').sql_insert([{'id': 1, 'text': 'apple'}, {'id': 2, 'text': 'pear'}])
        db.commit()
        yield db


@pytest.mark.postgresql
def test_like_with_a_parameter_runs_on_postgres(db):
    rows = db.table('app.note').query(columns='$id', where="$text LIKE 'a%' AND $id>:low", low=0).fetch()
    assert [row['id'] for row in rows] == [1]


@pytest.mark.postgresql
def test_like_without_parameters_runs_on_postgres(db):
    rows = db.table('app.note').query(columns='$id', where="$text LIKE '%r'").fetch()
    assert [row['id'] for row in rows] == [2]


@pytest.mark.postgresql
def test_percent_in_a_comment_runs_on_postgres(db):
    model = db.table('app.note').model
    cursor = db.execute(f"SELECT id FROM {model.sqlschema}.{model.sqlname} -- 100%\nWHERE id=:pk", {'pk': 2})
    assert [row['id'] for row in cursor.fetchall()] == [2]
