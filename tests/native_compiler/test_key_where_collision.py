"""asqueel#24: the key parameters of a record write never overwrite a record value."""
import pytest

from asqueel import AsqueelDb, SqlDatabaseConfig
from asqueel.write_compiler import WriteCompiler


@pytest.fixture
def db():
    source = SqlDatabaseConfig()
    pkg = source.source.db('collision', implementation='postgres').packages().package('app', sqlschema='app')
    invoice = pkg.table('invoice', pkey='id')
    invoice.column('id', dtype='L')
    invoice.column('amount', dtype='N')
    return AsqueelDb(source)


def writer(db):
    return WriteCompiler(db.adapter)


def model(db):
    return db.table('app.invoice').model


def test_update_refuses_a_record_key_named_as_a_key_parameter(db):
    with pytest.raises(ValueError, match='__pkey__0'):
        writer(db).update(model(db), {'id': 1, 'amount': 4, '__pkey__0': 9}, {})


def test_update_by_explicit_pkey_refuses_the_same_collision(db):
    with pytest.raises(ValueError, match='__pkey__0'):
        writer(db).update(model(db), {'amount': 4, '__pkey__0': 9}, {}, pkey=1)


def test_update_without_collision_binds_the_key(db):
    query = writer(db).update(model(db), {'id': 1, 'amount': 4}, {})
    assert query.params['__pkey__0'] == 1


def test_delete_binds_the_key_of_the_record_only(db):
    # delete builds its parameters from the key alone: a record key never reaches them.
    query = writer(db).delete(model(db), {'id': 1, '__pkey__0': 9}, {})
    assert query.params['__pkey__0'] == 1
