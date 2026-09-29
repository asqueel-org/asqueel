"""Optional real PostgreSQL checks; GENRO_SQL_TEST_DSN selects a disposable database."""
import asyncio
from uuid import uuid4

import pytest

from genro_sql.contracts import CompiledQuery, ResultColumn
from genro_sql.runtime import PostgresDatabase

from tests.native_support import postgres_dsn

pytestmark = pytest.mark.postgresql


def test_real_postgres_crud_rollback_and_returning():
    async def scenario():
        table = 'v1_runtime_' + uuid4().hex
        async with PostgresDatabase(postgres_dsn(), max_workers=2) as db:
            await db.execute(CompiledQuery(f'CREATE TABLE "{table}" (id int PRIMARY KEY, value text)'))
            try:
                result = await db.execute(CompiledQuery(
                    f'INSERT INTO "{table}" VALUES (%(id)s, %(value)s) RETURNING id, value',
                    {'id': 1, 'value': "l'apostrofo"}))
                assert result.rows == [{'id': 1, 'value': "l'apostrofo"}]
                with pytest.raises(RuntimeError):
                    async with db.transaction() as tx:
                        await tx.execute(CompiledQuery(f'UPDATE "{table}" SET value = %(v)s', {'v': 'rollback'}))
                        raise RuntimeError('abort')
                result = await db.execute(CompiledQuery(f'SELECT value FROM "{table}"'))
                assert result.rows == [{'value': "l'apostrofo"}]
                assert (await db.execute(CompiledQuery(f'DELETE FROM "{table}" RETURNING id'))).rows == [{'id': 1}]
            finally:
                await db.execute(CompiledQuery(f'DROP TABLE "{table}"'))
    asyncio.run(scenario())


def test_real_postgres_does_not_block_event_loop():
    async def scenario():
        async with PostgresDatabase(postgres_dsn(), max_workers=1) as db:
            task = asyncio.create_task(db.execute(CompiledQuery('SELECT pg_sleep(0.15)')))
            ticks = 0
            while not task.done():
                await asyncio.sleep(.01)
                ticks += 1
            await task
            assert ticks >= 5
    asyncio.run(scenario())


def test_real_postgres_metadata_mismatch_rolls_back_prior_write():
    async def scenario():
        table = 'v1_runtime_' + uuid4().hex
        async with PostgresDatabase(postgres_dsn()) as db:
            await db.execute(CompiledQuery(f'CREATE TABLE "{table}" (id int PRIMARY KEY)'))
            try:
                with pytest.raises(ValueError, match='Compiled result columns'):
                    async with db.transaction() as tx:
                        await tx.execute(CompiledQuery(f'INSERT INTO "{table}" VALUES (1)'))
                        await tx.execute(CompiledQuery('SELECT 1 AS actual', columns=(ResultColumn('wrong'),)))
                assert (await db.execute(CompiledQuery(f'SELECT count(*) AS n FROM "{table}"'))).rows == [{'n': 0}]
            finally:
                await db.execute(CompiledQuery(f'DROP TABLE "{table}"'))
    asyncio.run(scenario())
