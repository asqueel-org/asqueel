"""Sibling order beyond legacy: last position on move, bounded _h_count, locked max + 1 (doc 36 §10.2)."""
import pytest

from asqueel.errors import BusinessLogicException
from tests.option_tables_support import IMPLEMENTATIONS, migrated_db, row


def ranked_category(package):
    table = package.table('category', name_long='Category', name_plural='Categories')
    table.options().sysFields()
    table.options().hierarchical('code')
    table.options().counter()
    table.column('code')


@pytest.fixture(params=IMPLEMENTATIONS)
def db(request, tmp_path):
    with migrated_db(request.param, tmp_path, ranked_category) as database:
        yield database


def insert(table, code, parent=None, **values):
    return table.insert(dict(values, code=code, parent_id=parent['id'] if parent else None))


def test_a_moved_node_takes_the_last_position_under_its_new_parent(db):
    table = db.table('app.category')
    a = insert(table, 'a')
    insert(table, 'a1', a)
    insert(table, 'a2', a)
    b = insert(table, 'b')
    b1 = insert(table, 'b1', b)
    b1x = insert(table, 'b1x', b1)
    old = row(table, b1['id'])
    table.update(dict(old, parent_id=a['id']), old_record=old)
    assert row(table, b1['id'], '$_row_count,$_h_count') == {'_row_count': 3, '_h_count': '0103'}
    assert row(table, b1x['id'], '$_h_count')['_h_count'] == '010301'


def test_the_1296th_sibling_is_an_explicit_error(db):
    table = db.table('app.category')
    last = insert(table, 'last', _row_count=1295)
    assert last['_h_count'] == 'ZZ'
    with pytest.raises(BusinessLogicException, match='at most 1295 siblings under one parent'):
        insert(table, 'overflow')
    db.rollback()
    insert(table, 'last', _row_count=1295)
    with pytest.raises(BusinessLogicException, match='at most 1295 siblings under one parent'):
        insert(table, 'explicit', _row_count=1296)


@pytest.mark.postgresql
def test_concurrent_inserts_under_one_parent_get_distinct_positions():
    # wf:contract: on PostgreSQL, two AsqueelDb instances on the same schema insert a child
    # wf:contract: under the same parent, each in its own open transaction, from two threads.
    # wf:contract: the second insert waits for the first transaction to commit, then both
    # wf:contract: children are committed with _row_count 1 and 2 (never both 1).
    # wf:contract: the same holds for two concurrent root inserts (parent_id None).
    # wf:contract: every wait in the test is bounded by a timeout, so a missing lock fails, never hangs.
    from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeout
    from uuid import uuid4

    import psycopg
    from psycopg import sql

    from asqueel import AsqueelDb, SqlDatabaseConfig
    from tests.native_support import postgres_dsn

    schema = 'opt_' + uuid4().hex[:12]
    with psycopg.connect(postgres_dsn(), autocommit=True) as conn:
        conn.execute(sql.SQL('CREATE SCHEMA {}').format(sql.Identifier(schema)))

    def open_db():
        source = SqlDatabaseConfig()
        root = source.source.db('options', implementation='postgres', conninfo=postgres_dsn())
        ranked_category(root.packages().package('app', sqlschema=schema, sqlprefix=False))
        return AsqueelDb(source).session()

    first, second = open_db(), open_db()
    try:
        first.migrate()
        first.commit()
        parent = insert(first.table('app.category'), 'parent')
        first.commit()

        def concurrent_insert(code, parent_id):
            second.execute("SET lock_timeout = '10s'")
            second.table('app.category').insert(dict(code=code, parent_id=parent_id))
            second.commit()
            second.closeConnection()

        with ThreadPoolExecutor(max_workers=1) as pool:
            for code, parent_id in (('child', parent['id']), ('root', None)):
                first.table('app.category').insert(dict(code=f'{code}_1', parent_id=parent_id))
                waiting = pool.submit(concurrent_insert, f'{code}_2', parent_id)
                with pytest.raises(FutureTimeout):
                    waiting.result(timeout=1)
                first.commit()
                waiting.result(timeout=10)
        table = first.table('app.category')
        positions = {record['code']: record['_row_count']
                     for record in table.query(columns='$code,$_row_count').fetch()}
        assert positions == {'parent': 1, 'child_1': 1, 'child_2': 2, 'root_1': 2, 'root_2': 3}
    finally:
        first.shared.close()
        second.shared.close()
        with psycopg.connect(postgres_dsn(), autocommit=True) as conn:
            conn.execute(sql.SQL('DROP SCHEMA {} CASCADE').format(sql.Identifier(schema)))
