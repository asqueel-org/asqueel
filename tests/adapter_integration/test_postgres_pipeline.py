"""The explicit adapter path executes the same V1 operations on PostgreSQL."""
import asyncio

import pytest

from genro_sql.catalog_provider import PostgresCatalogProvider
from genro_sql.compiler import QueryCompiler
from genro_sql.contracts import CompiledQuery
from genro_sql.dialects.postgres import PostgresDialect
from genro_sql.drivers.psycopg import PsycopgDriver
from genro_sql.model import resolve_model
from genro_sql.query_plan import Parameter
from genro_sql.runtime import ThreadedDatabase
from tests.native_integration.test_postgres_vertical import (
    native_database as native_database, recipe,
)

pytestmark = pytest.mark.postgresql


def test_explicit_pipeline_and_catalog_provider(native_database):
    params, schema, connection = native_database
    dialect, driver = PostgresDialect(), PsycopgDriver()
    compiler = QueryCompiler(resolve_model(recipe(schema)), dialect, driver)

    async def scenario():
        async with ThreadedDatabase(driver=driver, connect_kwargs=params, max_workers=1) as db:
            await db.execute(compiler.insert('crm.customer', {'id': 1, 'name': "L'impresa 50%"}))
            plan = compiler.plan_select(
                'crm.customer', columns="$name, '50%' AS percent",
                where='$id = :id', params={'id': 1},
            )
            statement = dialect.render(plan)
            assert any(isinstance(part, Parameter) for part in statement.parts)
            assert "'50%'" in ''.join(part for part in statement.parts if isinstance(part, str))
            prepared = driver.prepare(statement)
            assert "'50%%'" in prepared.sql
            rows = (await db.execute(prepared)).rows
            assert rows == [{'name': "L'impresa 50%", 'percent': '50%'}]
            assert await db.execute(CompiledQuery('SELECT 1 AS ok'))
    asyncio.run(scenario())
    imported = PostgresCatalogProvider().inspect(connection, [schema])
    assert not imported.warnings
    assert imported.model.table('crm_customer').columns['display name'].dtype == 'T'
