"""Record lookup and row locks on the public hierarchical PostgreSQL path."""
import psycopg
import pytest

from tests.native_formulas.conftest import db_pg  # noqa: F401


@pytest.mark.postgresql
def test_record_uses_owning_transaction_and_postgres_row_lock(db_pg):  # noqa: F811
    db = db_pg
    table = db.table('invc.customer')
    key = table.query('$id', limit=1).fetch()[0]['id']
    db.rollback()
    record = table.record(key, for_update=True)
    query = record.query.compiled
    assert 'FOR UPDATE OF t0' in query.sql
    assert query.for_update
    assert record.output()['id'] == key
    connection = db._connection_state['connection']
    with psycopg.connect(connection.info.dsn, autocommit=True) as other:
        other.execute("SET lock_timeout='100ms'")
        with pytest.raises(psycopg.errors.LockNotAvailable):
            other.execute('UPDATE invc.invc_customer SET id=id WHERE id=%s', (key,))
        assert table.record(key).output()['id'] == key
        assert db._connection_state['connection'] is connection
        db.rollback()
        other.execute('UPDATE invc.invc_customer SET id=id WHERE id=%s', (key,))
    assert table.record('missing', ignoreMissing=True).output() == {}
    db.rollback()
