"""The explicit adapter path executes the same V1 operations on PostgreSQL."""

import pytest

from asqueel.catalog_provider import PostgresCatalogProvider
from asqueel.compiler import QueryCompiler
from asqueel.contracts import CompiledQuery
from asqueel.dialects.postgres import PostgresDialect
from asqueel.drivers.psycopg import PsycopgDriver
from asqueel.model import resolve_model
from asqueel.query_plan import Parameter
from asqueel.runtime import Database
from tests.native_integration.test_postgres_vertical import (
    native_database as native_database, recipe,
)

pytestmark = pytest.mark.postgresql


def test_explicit_pipeline_and_catalog_provider(native_database):
    params, schema, connection = native_database
    dialect, driver = PostgresDialect(), PsycopgDriver()
    compiler = QueryCompiler(resolve_model(recipe(schema)), dialect, driver)

    def scenario():
        with Database(driver=driver, connect_kwargs=params) as db:
            db.execute(compiler.insert('crm.customer', {'id': 1, 'name': "L'impresa 50%"}))
            plan = compiler.plan_select(
                'crm.customer', columns="$name, '50%' AS percent",
                where='$id = :id', sqlparams={'id': 1},
            )
            statement = dialect.render(plan)
            assert any(isinstance(part, Parameter) for part in statement.parts)
            assert "'50%'" in ''.join(part for part in statement.parts if isinstance(part, str))
            prepared = driver.prepare(statement)
            assert "'50%%'" in prepared.sql
            rows = (db.execute(prepared)).rows
            assert rows == [{'name': "L'impresa 50%", 'percent': '50%'}]
            assert db.execute(CompiledQuery('SELECT 1 AS ok'))
    scenario()
    imported = PostgresCatalogProvider().inspect(connection, [schema])
    assert not imported.warnings
    assert imported.model.table('crm_customer').columns['display name'].dtype == 'T'
