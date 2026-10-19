"""The explicit adapter path executes the same V1 operations on PostgreSQL."""

import pytest

from asqueel.catalog_provider import PostgresCatalogProvider
from asqueel.compiler import QueryCompiler
from asqueel.contracts import CompiledQuery
from asqueel.adapters.postgres import SqlDbAdapter as PostgresAdapter
from asqueel.model import resolve_model
from asqueel.runtime import Database
from asqueel.write_compiler import WriteCompiler
from tests.native_integration.test_postgres_vertical import (
    native_database as native_database, recipe,
)

pytestmark = pytest.mark.postgresql


def test_explicit_pipeline_and_catalog_provider(native_database):
    params, schema, connection = native_database
    adapter = PostgresAdapter(None)
    model = resolve_model(recipe(schema))
    compiler = QueryCompiler(model, adapter)
    writer = WriteCompiler(adapter)

    def scenario():
        db = Database(implementation='postgres', connect_kwargs=params)
        try:
            db.execute(writer.insert(model.table('crm.customer'), {'id': 1, 'name': "L'impresa 50%"},
                                     db.environment.snapshot()))
            # Literal SQL reaches psycopg as written: the author doubles its %.
            plan = compiler.plan_select(
                'crm.customer', columns="$name, '50%%' AS percent",
                where='$id = :id', sqlparams={'id': 1},
            )
            prepared = compiler.compile_plan(plan)
            assert "'50%%'" in prepared.sql
            assert '%(id)s' in prepared.sql
            rows = (db.execute(prepared)).fetchall()
            assert [dict(row) for row in rows] == [{'name': "L'impresa 50%", 'percent': '50%'}]
            assert db.execute(CompiledQuery('SELECT 1 AS ok'))
        finally:
            db.closeConnection()
    scenario()
    imported = PostgresCatalogProvider().inspect(connection, [schema])
    assert not imported.warnings
    assert imported.model.table('crm_customer').columns['display name'].dtype == 'T'
