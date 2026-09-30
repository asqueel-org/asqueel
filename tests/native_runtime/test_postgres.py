"""Optional real PostgreSQL checks; ASQUEEL_TEST_DSN selects a disposable database."""
from uuid import uuid4

import pytest

from asqueel.contracts import CompiledQuery, ResultColumn
from asqueel.runtime import PostgresDatabase

from tests.native_support import postgres_dsn

pytestmark = pytest.mark.postgresql


def test_real_postgres_crud_rollback_and_returning():
    table = 'v1_runtime_' + uuid4().hex
    with PostgresDatabase(postgres_dsn()) as db:
        db.execute(CompiledQuery(f'CREATE TABLE "{table}" (id int PRIMARY KEY, value text)'))
        try:
            result = db.execute(CompiledQuery(
                f'INSERT INTO "{table}" VALUES (%(id)s, %(value)s) RETURNING id, value',
                {'id': 1, 'value': "l'apostrofo"}))
            assert result.rows == [{'id': 1, 'value': "l'apostrofo"}]
            with pytest.raises(RuntimeError):
                with db.transaction() as tx:
                    tx.execute(CompiledQuery(f'UPDATE "{table}" SET value = %(v)s', {'v': 'rollback'}))
                    raise RuntimeError('abort')
            result = db.execute(CompiledQuery(f'SELECT value FROM "{table}"'))
            assert result.rows == [{'value': "l'apostrofo"}]
            assert (db.execute(CompiledQuery(f'DELETE FROM "{table}" RETURNING id'))).rows == [{'id': 1}]
        finally:
            db.execute(CompiledQuery(f'DROP TABLE "{table}"'))


def test_real_postgres_metadata_mismatch_rolls_back_prior_write():
    table = 'v1_runtime_' + uuid4().hex
    with PostgresDatabase(postgres_dsn()) as db:
        db.execute(CompiledQuery(f'CREATE TABLE "{table}" (id int PRIMARY KEY)'))
        try:
            with pytest.raises(ValueError, match='Compiled result columns'):
                with db.transaction() as tx:
                    tx.execute(CompiledQuery(f'INSERT INTO "{table}" VALUES (1)'))
                    tx.execute(CompiledQuery('SELECT 1 AS actual', columns=(ResultColumn('wrong'),)))
            assert (db.execute(CompiledQuery(f'SELECT count(*) AS n FROM "{table}"'))).rows == [{'n': 0}]
        finally:
            db.execute(CompiledQuery(f'DROP TABLE "{table}"'))
