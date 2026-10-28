"""cleanup_cached_tables(owner=...): drop the cached fetches of some owners."""
import pytest

from asqueel.contracts import UnsupportedFeatureError
from tests.cached_fetch.test_fetch import declare, enable, fill, memory_model
from tests.option_tables_support import IMPLEMENTATIONS, migrated_db

OWNERS = ['foo', 'bar', 'baz', 'qux']


@pytest.fixture(params=IMPLEMENTATIONS)
def db(request, tmp_path):
    with migrated_db(request.param, tmp_path, declare, declare_db=enable) as db:
        fill(db, 20)
        for owner in OWNERS:
            db.table('app.item').query(columns='$id, $grp').fetch(destinationName=f'{owner}:first')
            db.table('app.item').query(columns='$id, $grp').fetch(destinationName=f'{owner}:second')
            db.table('app.item').cached(f'{owner}:second').sort('grp desc')
        yield db


def catalog_owners(db):
    rows = db.table('_asql_._asql_cached_fetch').query(columns='$owner').fetch()
    return sorted({row['owner'] for row in rows})


def stored_tables(db):
    if db.implementation == 'postgres':
        sql = "SELECT tablename FROM pg_tables WHERE schemaname = '_asql_' AND tablename <> '_asql_cached_fetch'"
    else:
        sql = "SELECT name FROM _asql_.sqlite_master WHERE type = 'table' AND name <> '_asql_cached_fetch'"
    return sorted(row[0] for row in db.execute(sql).fetchall())


def owner_tables(owners):
    return sorted(f'{prefix}{owner}_{name}' for owner in owners for prefix, name in
                  (('p', 'first'), ('p', 'second'), ('s', 'second')))


def test_every_owner_has_result_and_sort_tables(db):
    assert catalog_owners(db) == sorted(OWNERS)
    assert stored_tables(db) == owner_tables(OWNERS)


def test_named_owners_are_dropped(db):
    db.cleanup_cached_tables(owner='foo,bar')
    assert catalog_owners(db) == ['baz', 'qux']
    assert stored_tables(db) == owner_tables(['baz', 'qux'])


def test_a_single_owner_is_dropped(db):
    db.cleanup_cached_tables(owner='qux')
    assert catalog_owners(db) == ['bar', 'baz', 'foo']
    assert stored_tables(db) == owner_tables(['bar', 'baz', 'foo'])


def test_negated_owners_drop_every_other_owner(db):
    db.cleanup_cached_tables(owner=' ! ( foo , baz ) ')
    assert catalog_owners(db) == ['baz', 'foo']
    assert stored_tables(db) == owner_tables(['baz', 'foo'])
    assert db.table('app.item').cached('foo:second').query(columns='id', start=0, count=3).fetch()


def test_an_unknown_owner_drops_nothing(db):
    db.cleanup_cached_tables(owner='nobody')
    assert catalog_owners(db) == sorted(OWNERS)
    assert stored_tables(db) == owner_tables(OWNERS)


def test_a_dropped_fetch_can_be_created_again(db):
    db.cleanup_cached_tables(owner='foo')
    assert db.table('app.item').query(columns='$id').fetch(destinationName='foo:first') == 20
    assert catalog_owners(db) == sorted(OWNERS)


@pytest.mark.parametrize('owner', [None, '', '  ', ',', '!()', '! ( , )', '!foo', 'foo)', '(foo)', 'foo,!bar',
                                   '!(foo,(bar))', 7])
def test_a_malformed_owner_raises(db, owner):
    with pytest.raises(ValueError, match='owner must be'):
        db.cleanup_cached_tables(owner=owner)
    assert catalog_owners(db) == sorted(OWNERS)


def test_a_missing_owner_argument_raises(db):
    with pytest.raises(ValueError, match='owner must be'):
        db.cleanup_cached_tables()


def test_a_model_without_cached_fetch_raises(tmp_path):
    with migrated_db('sqlite', tmp_path, declare) as db:
        with pytest.raises(UnsupportedFeatureError, match='cachedFetch'):
            db.cleanup_cached_tables(owner='foo')


@pytest.mark.parametrize('implementation', ['mysql', 'mssql'])
def test_mysql_and_sql_server_raise(implementation):
    db = memory_model(implementation)
    try:
        with pytest.raises(UnsupportedFeatureError, match='cached fetch is not available'):
            db.cleanup_cached_tables(owner='foo')
    finally:
        db.shared.close()
